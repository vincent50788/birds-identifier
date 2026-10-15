import os
import json
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'bird_tags'))

def lambda_handler(event, context):
    try:
        body = event['tags']
        response = table.scan()
        items = response.get('Items', [])

        matching_links = []


        for item in items:
            item_tags = item['tags'] if 'tags' in item else []
            if all(tag in item_tags and item_tags[tag] >= count for tag, count in body.items()):
                matching_links.append(item['file_url'])

        return {
            "statusCode": 200,
            "body": json.dumps({
                "links": matching_links
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }
