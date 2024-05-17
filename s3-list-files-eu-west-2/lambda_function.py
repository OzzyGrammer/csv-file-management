import json
import boto3


def lambda_handler(event, context):

    # TODO implement
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
        print("before")
        s3_result = s3.list_objects_v2(
            Bucket=bucket_name, Prefix=prefix, Delimiter="/")
        print("s3 result", s3_result)
        if "Contents" not in s3_result:
            print(s3_result)
            return {
                "statusCode": 404,
                "body": f"this user has no files stored in {prefix}",
            }

        file_dict = {}
        print(s3_result)
        for key in s3_result["Contents"]:
            print("key result")
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": "storage-eu-west-2", "Key": key["Key"]},
                ExpiresIn=100,
            )
            file_dict[key["Key"]] = url
        print(f"Dictionary count = {len(file_dict)}")

        return {"statusCode": 200, "body": json.dumps({"files": file_dict})}

    except Exception as e:
        # Handle exceptions
        print("Error:", e)
        return {"statusCode": 500, "body": {"error": json.dumps(str(e))}}
