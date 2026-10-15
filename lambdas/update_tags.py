import os
import json
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'bird_tags'))

def lambda_handler(event, context):
    try:
        urls = event['urls']
        operation = event['operation']
        update_tags = event['tags']

        response = table.scan(
            FilterExpression=Attr('file_url').is_in(urls) | Attr('thumbnail_url').is_in(urls)
        )
        items = response.get('Items', [])

        if not items:
            return {
                'statusCode': 404,
                'body': json.dumps('No items found')
            }

        for item in items:
            item_key = {'id': item['id']}

            current_tags = item.get('tags', {})
            for tag, new_count in update_tags.items():
                if operation == 1: 
                        current_tags[tag] = new_count
                elif operation == 0: 
                    if tag in current_tags:
                        del current_tags[tag]

            # Write the merged tags back
            try:
                table.update_item(
                    Key=item_key,
                    UpdateExpression="SET tags = :tags",
                    ExpressionAttributeValues={':tags': current_tags}
                )
            except:
                return {
                    'statusCode': 400,
                    'body': json.dumps('Tags update fail')
                }

        return {
            'statusCode': 200,
            'body': json.dumps('Tags updated successfully')
        }

    except:
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid JSON in request body')
        }
