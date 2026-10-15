import boto3
import json
import time
import os
from birds_detection import image_prediction, video_prediction

table_name = os.environ['TABLE_NAME']
sqs_queue_endpoint = os.environ['QUEUE_URL']

region = os.environ.get('AWS_REGION', 'us-east-1')
sqs = boto3.client('sqs', region_name=region)
s3 = boto3.client('s3', region_name=region)
dynamo = boto3.client('dynamodb', region_name=region)
dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table(table_name)
queue_url = sqs_queue_endpoint

SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
sns = boto3.client('sns', region_name=region)

# The worker hot-reloads the YOLO weights whenever this S3 object changes
MODEL_BUCKET = os.environ['MODEL_BUCKET']
MODEL_KEY = os.environ.get('MODEL_KEY', 'model/model.pt')
LOCAL_MODEL_PATH = './model.pt'

model_last_modified = None

def publish_notifications(id, file_url, tags):
    """
    tags is a Python dict like {'Crow': 1, 'Owl': 2}.
    For each tag, send one SNS message with MessageAttribute "tag" = that tag name.
    Subscribers whose filter policy includes that tag value will receive it.
    """
    for bird_tag, count in tags.items():
        message_body = {
            "id":       id,
            "file_url": file_url,
            "tag":      bird_tag,
            "count":    count
        }
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"New image tagged: {bird_tag}",
                Message=json.dumps(message_body),
                MessageAttributes={
                    "tag": {
                        "DataType":    "String",
                        "StringValue": bird_tag
                    }
                }
            )
            print(f"[publish_notifications] Sent SNS for tag='{bird_tag}', count={count}")
        except Exception as e:
            print(f"[publish_notifications] ERROR publishing SNS for '{bird_tag}': {e}")

def ensure_latest_model():
    global model_last_modified
    response = s3.head_object(Bucket=MODEL_BUCKET, Key=MODEL_KEY)

    if not response:
        print("NO MODEL FOUND IN S3")
        return 
    
    latest_modified = response['LastModified']

    if model_last_modified is None or latest_modified != model_last_modified:
        print("Downloading latest model...")
        s3.download_file(MODEL_BUCKET, MODEL_KEY, LOCAL_MODEL_PATH)
        model_last_modified = latest_modified
        print("Model updated.")
    else:
        print("Model is up to date.")

def download_from_s3(bucket, key, download_path):
    s3.download_file(bucket, key, download_path)


def pre_write(key, id, file_url, thumbnail_url):
    if key.startswith('image'):
        item = {
            'id': {'S': id},
            'file_url': {'S': file_url},
            'thumbnail_url': {'S': thumbnail_url},
            'isInferenced': {'BOOL': False}
        }
    else:
        item = {
            'id': {'S': id},
            'file_url': {'S': file_url},
            'isInferenced': {'BOOL': False}
        }

    dynamo.put_item(
        TableName=table_name,
        Item=item
    )


def process_message(message):
    ensure_latest_model()

    attributes = message.get('MessageAttributes', {})

    try:
        id = attributes['id']['StringValue']
        file_url = attributes['file_url']['StringValue']
        bucket = attributes['bucket']['StringValue']
        key = attributes['key']['StringValue']
        thumbnail_url = attributes['thumbnail_url']['StringValue'] if key.startswith('image') else ''
    except KeyError as e:
        print(f"Missing expected attribute: {e}")
        return
    
    # Record the item before inference so search-by-file can report "still processing"
    pre_write(key, id, file_url, thumbnail_url)

    print(f"Processing message for file: {file_url}")

    filename = key.split('/')[-1]
    local_path = f"/tmp/{filename}"
    download_from_s3(bucket, key, local_path)

    file_type = filename.split('.')[-1].lower()

    labels = []
    
    try:
        if file_type in ['jpg', 'jpeg', 'png']:
            labels = image_prediction(local_path, model=LOCAL_MODEL_PATH)
        elif file_type in ['mp4', 'avi', 'mov']:
            labels = video_prediction(local_path, model=LOCAL_MODEL_PATH, inference_per_sec=2)
        else:
            print(f"Unsupported file type: {file_type}")
            return
        
        tags = {}
        for label in labels:
            if label in tags:
                tags[label] += 1
            else:
                tags[label] = 1


        table.update_item(
            Key={'id': id},
            UpdateExpression="SET tags = :tags, isInferenced = :isInferenced",
            ExpressionAttributeValues={
                ':tags': tags,
                ':isInferenced': True
            }
        )

        if tags:
            publish_notifications(id, file_url, tags)
        else:
            print("No tags found; skipping SNS publish.")

    except Exception as e:
        print(f"Prediction or Dynamo insert failed: {e}")

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"Removed file: {local_path}")


def poll_sqs():
    print("Polling SQS...")
    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            MessageAttributeNames = ['All']
        )

        messages = response.get('Messages', [])
        for message in messages:
            try:
                process_message(message)
                # Delete message after successful processing
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                print("successfully processed")
            except Exception as e:
                print(f"Error processing message: {e}")

        time.sleep(2)


if __name__ == '__main__':
    poll_sqs()
