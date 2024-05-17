import json
import boto3
import base64
import csv
import io
import re
import sys
import threading


class TransferCallback:
    """
    Handle callbacks from the transfer manager.

    The transfer manager periodically calls the __call__ method throughout
    the upload and download process so that it can take action, such as
    displaying progress to the user and collecting data about the transfer.
    """

    def __init__(self, target_size):
        self._target_size = target_size
        self._total_transferred = 0
        self._lock = threading.Lock()
        self.thread_info = {}

    def __call__(self, bytes_transferred):
        """
        The callback method that is called by the transfer manager.

        Display progress during file transfer and collect per-thread transfer
        data. This method can be called by multiple threads, so shared instance
        data is protected by a thread lock.
        """
        MB = 1024 * 1024
        thread = threading.current_thread()
        with self._lock:
            self._total_transferred += bytes_transferred
            if thread.ident not in self.thread_info.keys():
                self.thread_info[thread.ident] = bytes_transferred
            else:
                self.thread_info[thread.ident] += bytes_transferred

            target = self._target_size * MB
            sys.stdout.write(
                f"\r{self._total_transferred} of {target} transferred "
                f"({(self._total_transferred / target) * 100:.2f}%)."
            )
            sys.stdout.flush()


bucket_name_validation_rules = [
    lambda v: v is not None or "Name is required",
    lambda v: (
        bool(re.match(r"^[a-z\d\.\-]*$", v)) or (
            "The bucket name can contain only lower-case characters, "
            "numbers, periods, and dashes."
        )
    ),
    lambda v: bool(re.match(r"^[a-z\d]", v))
    or "The bucket name must start with a lowercase letter or number.",
    lambda v: not v.endswith("-") or "The bucket name can't end with a dash",
    lambda v: not re.search(r"\.+", v)
    or "The bucket name can't have consecutive periods",
    lambda v: not re.search(r"\-+\.$", v)
    or "The bucket name can't end with dash adjacent to period",
    lambda v: (
        not bool(re.match(
            r"^(?:(?:^|\.)(?:2(?:5[0-5]|[0-4]\d)|1?\d?\d)){4}$", v
        )) or (
            "The bucket name can't be formatted as an IP address"
        )
    ),
    lambda v: (
        3 <= len(v) <= 63 or
        "The bucket name can be between 3 and 63 characters long."
    ),
    lambda v: (
        "." not in v or
        "The bucket name can't contain a period directly."
    ),
]


def validate_bucket_name(name):
    for rule in bucket_name_validation_rules:
        result = rule(name)
        if not result:
            return result
    return True


def validate_csv_content(content):
    # Validate content to ensure it's a valid CSV file

    try:
        # Create a file-like object for CSV reader
        content_stream = io.StringIO(content.decode("utf-8"))

        # Attempt to parse the CSV content
        csv_reader = csv.reader(content_stream)

        # Check if the CSV content has at least one row
        for row in csv_reader:
            return True  # If there is at least one row, consider it valid
        return False  # If no rows, consider it invalid
    except Exception as e:
        print(f"Error occurred while validating CSV content: {e}")
        return False


def lambda_handler(event, context):

    print(event)
    try:

        MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1gb
        MIN_FILE_SIZE_FOR_MULTIPART = 20 * 1024 * 1024  # 20 MB

        if event["headers"]["Content-Type"] != "text/csv":
            print("headersnn", event["headers"]["Content-Type"])
            return {
                "statusCode": 415,
                "body": json.dumps({"error": "Unsupported media type"}),
            }

        cognito_client = boto3.client("cognito-idp")
        s3 = boto3.client("s3")
        bucket_name = "storage-eu-west-2"
        user_pool_id = "eu-west-2_RstIkMHQr"
        user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
        print(event)
        if user_sub:
            response = cognito_client.admin_get_user(
                UserPoolId=user_pool_id, Username=user_sub
            )

            for attribute in response["UserAttributes"]:
                if attribute["Name"] == "email":
                    email = attribute["Value"]
                    break
        print(event["queryStringParameters"]["filename"])
        file_name = event["queryStringParameters"]["filename"]
        validation_message = validate_bucket_name(file_name)
        if not validation_message:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": validation_message}),
            }

        key = f"{user_sub}/{email}/files/{file_name}.csv"

        file_content = event["body"]
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "File size exceeds the maximum allowed limit."}
                ),
            }

        decode_content = base64.b64decode(file_content)

        if not validate_csv_content(decode_content):
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Uploaded file is not a valid CSV file."
                }),
            }
        print(key)
        print(decode_content)
        if file_size > MIN_FILE_SIZE_FOR_MULTIPART:
            # Initiate multipart upload
            multipart_info = s3.create_multipart_upload(
                Bucket=bucket_name,
                Key=key
            )
            upload_id = multipart_info["UploadId"]
            try:
                # Upload parts
                parts = []
                part_number = 1
                part_size = 5 * 1024 * 1024  # 5 MB
                start_range = 0
                while start_range < file_size:
                    end_range = min(start_range + part_size, file_size)
                    part = decode_content[start_range:end_range]
                    response = s3.upload_part(
                        Bucket=bucket_name,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=part,
                    )
                    parts.append({
                        "PartNumber": part_number, "ETag": response["ETag"]})
                    part_number += 1
                    start_range = end_range

                # Complete multipart upload
                s3.complete_multipart_upload(
                    Bucket=bucket_name,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
            except Exception as e:
                # Abort multipart upload if any part fails to upload
                s3.abort_multipart_upload(
                    Bucket=bucket_name, Key=key, UploadId=upload_id
                )
                raise e

        else:
            s3.put_object(Bucket=bucket_name, Key=key, Body=decode_content)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"uploaded {user_sub}/{email}/files/{file_name}.csv"
            })
        }

    except Exception as e:
        # Handle exceptions
        print("Error:", e)
        return {"statusCode": 500, "body": {"error": json.dumps(str(e))}}
