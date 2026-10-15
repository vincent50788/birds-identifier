import os
import csv
import shutil
import time
import json
import boto3
import subprocess
import glob
import sys

# Constants
region = os.environ.get('AWS_REGION', 'us-east-1')
table_name = os.environ['TABLE_NAME']
sqs_queue_endpoint = os.environ['QUEUE_URL']

SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
sns = boto3.client('sns', region_name=region)

# Clients
s3 = boto3.client('s3', region_name=region)
dynamo = boto3.client('dynamodb', region_name=region)
sqs = boto3.client('sqs', region_name=region)

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
                Subject=f"New recording tagged: {bird_tag}",
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


def build_folder(case_id: str):
    folder_name = f"{case_id}_case"
    os.makedirs(folder_name, exist_ok=True)
    return folder_name

def get_audio_file(bucket: str, src: str, dst: str):
    s3.download_file(bucket, src, dst)

def audio_inference(target_folder: str, target_file: str):
    subprocess.run([sys.executable, "-m", "birdnet_analyzer.analyze", "--rtyp", "csv", "--min_conf", "0.5", "-o", target_folder, target_file], text=True)

def parse_tags_from_csv(target_folder: str):
    result = {}
    file = glob.glob(os.path.join(target_folder, "*.results.csv"))[0]
    with open(file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            result[row['Common name']] = 1
    return result

def store_dynamo(id: str, file_url: str, tags, is_inference: bool):
    item = {
        'id': {'S': id},
        'file_url': {'S': file_url},
        'tags': {
            'M': {k: {'N': str(v)} for k, v in tags.items()}
        },
        'isInferenced': {'BOOL': is_inference}
    }
    dynamo.put_item(
        TableName=table_name,
        Item=item
    )

def process(message):
    # parse param
    attributes = message.get('MessageAttributes', {})
    case_id = attributes['id']['StringValue']
    file_url = attributes['file_url']['StringValue']
    bucket = attributes['bucket']['StringValue']
    key = attributes['key']['StringValue']

    # setup folder
    case_folder_path = build_folder(case_id)

    # build download destination
    target_file_path = os.path.join(case_folder_path, os.path.basename(key))

    try:
        # download audio file into destination folder
        get_audio_file(bucket, key, target_file_path)

        # setup item
        store_dynamo(case_id, file_url, {}, False)

        # inference and store result in folder
        audio_inference(case_folder_path, target_file_path)

    except Exception as e:
        # clean up
        dynamo.delete_item(TableName=table_name, Key={'id': {'S': case_id}})
        shutil.rmtree(case_folder_path)
        sqs.delete_message(QueueUrl=sqs_queue_endpoint, ReceiptHandle=message['ReceiptHandle'])
        print(f'[process] Exception raised: {e}')
        return

    # parse tag from the result
    tags = parse_tags_from_csv(case_folder_path)

    # store result
    store_dynamo(case_id, file_url, tags, True)

    if tags:
        publish_notifications(case_id, file_url, tags)
    else:
        print("No tags found; skipping SNS publish.")

    # cleanup
    shutil.rmtree(case_folder_path)


def poll_sqs():
    print("Polling SQS...")
    while True:
        messages = sqs.receive_message(
            QueueUrl=sqs_queue_endpoint,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            MessageAttributeNames=['All']
        ).get('Messages', [])

        for message in messages:
            try:
                # Parse message from queue
                if not message['MessageAttributes']['key']['StringValue'].startswith('audio/'):
                    print(f"{message['MessageAttributes']['key']['StringValue']} is not an audio file, abort.")
                    continue

                # Process
                process(message)

                # Delete message after successful processing
                sqs.delete_message(
                    QueueUrl=sqs_queue_endpoint,
                    ReceiptHandle=message['ReceiptHandle']
                )
                print("mission completed")
            except Exception as e:
                print(f"Error processing message: {e}")
        time.sleep(2)

def main():
    poll_sqs()

if __name__ == '__main__':
    main()