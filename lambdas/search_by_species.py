import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'bird_tags'))

def tag_fit(item_tags, tags):
    for tag in tags:
        if tag not in item_tags.keys():
            return False
    return True

def lambda_handler(event, context):
    try:
        request_tags = event["tags"]

        # Full table scan; fine at demo scale
        response = table.scan()
        items = response.get('Items', [])

        matching_links = []
        for item in items:
            item_tags = item['tags'] if 'tags' in item else {}
            if tag_fit(item_tags, request_tags):
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
