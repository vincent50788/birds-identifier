import json
import boto3
from urllib.parse import urlparse
import os


dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

DYNAMODB_TABLE = os.environ.get('TABLE_NAME', 'bird_tags')
S3_BUCKET = os.environ['MEDIA_BUCKET']

def delete_s3_object_with_url(url):
    s3.delete_object(Bucket=S3_BUCKET, Key=extract_s3_key(url))

def extract_s3_key(url):
    # Assumes URL is in the form https://bucket.s3.amazonaws.com/{folder/object.mp4} or similar
    return urlparse(url).path.lstrip('/')

def lambda_handler(event, context):
    table = dynamodb.Table(DYNAMODB_TABLE)

    try:
        links = event["links"]
        if not links or not isinstance(links, list):
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid 'links' array."})}
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"message": "Malformed JSON body."})}
    
    try:
        # Delete links in bucket
        for link in links:
            delete_s3_object_with_url(link)

        # 1. Find the item in DynamoDB
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('file_url').is_in(links) | boto3.dynamodb.conditions.Attr('thumbnail_url').is_in(links)
        )

        items = response.get('Items', [])

        for item in items:
            # 3. Delete the S3 object
            original_file = item.get('file_url')
            if original_file:
                delete_s3_object_with_url(original_file)

            thumbnail_file = item.get('thumbnail_url')
            if thumbnail_file:
                delete_s3_object_with_url(thumbnail_file)

            # 4. Delete the DynamoDB record
            table.delete_item(Key={'id': item['id']})

        return {
            "statusCode": 200
        }

    except Exception as e:
        return {"statusCode": 400, "message": f"unknown error {e}"}
