# CSV File Management

This project aims to provide a secure solution for users to store, retrieve and query their csv files.

## Aws Services used 

- **AWS LAMBDA** : a compute service that lets you run code without provisioning or managing servers.
- **AWS COGNITO** : the service helps you implement customer identity and access management (CIAM) into your web and mobile applications.
- **AWS SIMPLE STORAGE SERVICE (S3)** : used to store and retrieve any amount of data at any time, from anywhere
- **AWS API Gateway** : acts as a mediator between client applications and backend services in microservices architecture.


## Cost and perfomance anylisis 

-You can find them in this [directory](costs-and-metrics/)

## Postman Collection
- [CSV File Management Collection](postman-collection)
## Lambda's used for api gateway endpoints

- [/upload](s3-upload-eu-west-2/lambda_function.py)
- [/download](s3-download-eu-west-2/lambda_function.py)
- [/download-all](s3-list-files-eu-west-2/lambda_function.py)
- [/query](sql-select-lambda-eu-west-2/lambda_function.py)

## Bucket Policy on Bucket

```sh
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ListObjects",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::storage-eu-west-2",
            "Condition": {
                "StringLike": {
                    "s3:prefix": "${cognito-identity.amazonaws.com:sub}/*"
                }
            }
        },
        {
            "Sid": "ReadWriteDeleteObjects",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:DeleteObject",
                "s3:GetObject",
                "s3:PutObject",
                "s3:GetObjectAttributes"
            ],
            "Resource": "arn:aws:s3:::storage-eu-west-2/${cognito-identity.amazonaws.com:sub}/*"
        }
    ]
}
```