import os
import boto3
import json
from urllib.parse import urlparse

DYNAMODB_TABLE = os.environ.get('TABLE_NAME', 'bird_tags')
S3_BUCKET = os.environ['MEDIA_BUCKET']

dynamo_table = boto3.resource('dynamodb').Table(DYNAMODB_TABLE)
s3 = boto3.client('s3')

def delete_s3_object_with_url(url):
    s3.delete_object(Bucket=S3_BUCKET, Key=extract_s3_key(url))

def extract_s3_key(url):
    # Assumes URL is in the form https://bucket.s3.amazonaws.com/{folder/object.mp4} or similar
    return urlparse(url).path.lstrip('/')

def lambda_handler(event, context):
    try:
        link = event["link"]
        if not link or not isinstance(link, str):
            return {"statusCode": 400, "message": "Invalid 'link' value."}
    except Exception:
        return {"statusCode": 400, "message": "Malformed JSON body."}

    # check dynamodb has item 
    target_items = dynamo_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('file_url').eq(link)
    ).get('Items', [])

    if not target_items or len(target_items) != 1:
        return {"statusCode": 404, "message": f"link {link} not found in database"}

    # check inference status
    target_item = target_items[0]
    is_inferenced = target_item.get('isInferenced')
    if not is_inferenced:
        return {"statusCode": 202, "message": f"link {link} is still being processed"}

    # search similar files
    target_tags = target_item['tags']
    response = dynamo_table.scan()
    items = response.get('Items', [])
    matching_links = []
    for item in items:
        item_tags = item['tags'] if 'tags' in item else []
        if all(tag in item_tags and item_tags[tag] >= count for tag, count in target_tags.items()):
            if link != item['file_url']:
                matching_links.append(item['file_url'])

    # delete original files and table entry
    dynamo_table.delete_item(Key={'id': target_item['id']})
    delete_s3_object_with_url(target_item['file_url'])

    return {
            "statusCode": 200,
            "links": matching_links
        }