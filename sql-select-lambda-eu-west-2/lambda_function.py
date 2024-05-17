import json
import boto3
import csv
from io import StringIO


def lambda_handler(event, context):
    s3 = boto3.client("s3")

    cognito_client = boto3.client("cognito-idp")

    user_pool_id = "eu-west-2_RstIkMHQr"
    user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
    body = json.loads(event["body"])
    filename = body.get("filename")
    expression = body.get("expression")
    print(filename)
    print("expression", expression)

    if user_sub:
        response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id, Username=user_sub
        )

        for attribute in response["UserAttributes"]:
            if attribute["Name"] == "email":
                email = attribute["Value"]
                break

    key = f"{user_sub}/{email}/files/{filename}.csv"
    try:
        resp = s3.select_object_content(
            Bucket="storage-eu-west-2",
            Key=key,
            ExpressionType="SQL",
            Expression=expression,
            InputSerialization={
                "CSV": {"FileHeaderInfo": "Use"},
                "CompressionType": "NONE",
            },
            OutputSerialization={"CSV": {}},
        )

        # Initialize variables to hold CSV data and stats
        csv_data = []
        stats_data = {
            "BytesScanned": 0,
            "BytesProcessed": 0,
            "BytesReturned": 0}

        # Process the response
        for event in resp["Payload"]:
            if "Records" in event:
                records = event["Records"]["Payload"].decode("utf-8")
                # Parse CSV records into a list of dictionaries
                reader = csv.DictReader(StringIO(records))
                for row in reader:
                    csv_data.append(row)
            elif "Stats" in event:
                statsDetails = event["Stats"]["Details"]
                stats_data["BytesScanned"] = statsDetails["BytesScanned"]
                stats_data["BytesProcessed"] = statsDetails["BytesProcessed"]
                stats_data["BytesReturned"] = statsDetails["BytesReturned"]

        # Create the JSON response
        response_data = {"csv_data": csv_data, "stats": stats_data}

        # Return the JSON response
        return {"statusCode": 200, "body": json.dumps(response_data)}

    except Exception as e:
        # Handle exceptions
        print("Error:", e)
        return {"statusCode": 500, "body": str(e)}
