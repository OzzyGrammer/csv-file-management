import json
import boto3


def lambda_handler(event, context):

    try:
        cognito_client = boto3.client("cognito-idp")
        s3 = boto3.client("s3")
        user_pool_id = "eu-west-2_RstIkMHQr"
        user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
        bucket_name = "storage-eu-west-2"
        print(event)
        if user_sub:
            response = cognito_client.admin_get_user(
                UserPoolId=user_pool_id, Username=user_sub
            )

            for attribute in response["UserAttributes"]:
                if attribute["Name"] == "email":
                    email = attribute["Value"]
                    break
        prefix = f"{user_sub}/{email}/files/"
        s3 = boto3.client("s3")

        s3_result = s3.list_objects_v2(
            Bucket=bucket_name, Prefix=prefix, Delimiter="/")

        if "Contents" not in s3_result:
            print(s3_result)
            return {
                "statusCode": 404,
                "body": f"this user has no files stored in {prefix}",
            }

        file_list = []
        print(s3_result)
        for key in s3_result["Contents"]:
            file_list.append(key["Key"])
        print(f"List count = {len(file_list)}")

        while s3_result["IsTruncated"]:
            continuation_key = s3_result["NextContinuationToken"]
            s3_result = s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter="/",
                ContinuationToken=continuation_key,
            )
            for key in s3_result["Contents"]:
                file_list.append(key["Key"])
            print(f"List count = {len(file_list)}")
        filename = event["queryStringParameters"]["filename"]
        file_name_to_find = f"{prefix}{filename}.csv"
        file_found = False
        for obj in s3_result["Contents"]:
            if obj["Key"] == file_name_to_find:
                file_found = True
                break
        if file_found:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": file_name_to_find},
                ExpiresIn=100,
            )
            return {
                "statusCode": 200,
                "body": f"you can download here {json.dumps(url)}",
            }
        else:
            return {"statusCode": 404, "body": "File not found."}

    except Exception as e:
        # Handle exceptions
        print("Error:", e)
        return {"statusCode": 500, "body": {"error": json.dumps(str(e))}}
