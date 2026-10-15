import os
import json
import boto3

dynamo = boto3.resource('dynamodb')
table = dynamo.Table(os.environ.get('TABLE_NAME', 'bird_tags'))

def lambda_handler(event, context):
    try:
        thumbnail_url = event['url']
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('thumbnail_url').eq(thumbnail_url)
        )

        items = response.get('Items', [])
        if not items:
            return {
                "statusCode": 404,
                "body": "No matching item found"
            }

        file_url = items[0].get('file_url', '')

        return {
            "statusCode": 200,
            "body": json.dumps({
                "url": file_url
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }
