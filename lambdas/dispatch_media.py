import boto3
import cv2
import numpy as np
import os
from urllib.parse import unquote_plus

s3 = boto3.client('s3')
sqs = boto3.client('sqs')

VISUAL_QUEUE_URL = os.environ['VISUAL_QUEUE_URL']
AUDIO_QUEUE_URL = os.environ['AUDIO_QUEUE_URL']


def resize_image(image_bytes, max_size=300):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    height, width = img.shape[:2]
    scale = max_size / max(height, width)
    new_size = (int(width * scale), int(height * scale))
    resized_img = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

    success, buffer = cv2.imencode('.jpg', resized_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not success:
        raise Exception("Image compression failed")
    return buffer.tobytes()


def string_attributes(**values):
    return {k: {'StringValue': v, 'DataType': 'String'} for k, v in values.items()}


def lambda_handler(event, context):
    """Triggered by S3 ObjectCreated: builds image thumbnails and queues the file for inference."""
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote_plus(event['Records'][0]['s3']['object']['key'])
    id = key.split('/')[-1].split('-')[0]

    if key.startswith('thumbnails/'):
        return {"status": "skipped thumbnail to avoid recursion"}

    origin_url = f"https://{bucket}.s3.amazonaws.com/{key}"
    attributes = string_attributes(id=id, file_url=origin_url, bucket=bucket, key=key)

    if key.startswith('image/'):
        image_data = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
        thumbnail_key = f"thumbnails/{os.path.basename(key)}"

        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=resize_image(image_data),
            ContentType='image/jpeg'
        )

        attributes |= string_attributes(thumbnail_url=f"https://{bucket}.s3.amazonaws.com/{thumbnail_key}")
        queue_url = VISUAL_QUEUE_URL
    elif key.startswith('video/'):
        queue_url = VISUAL_QUEUE_URL
    elif key.startswith('audio/'):
        queue_url = AUDIO_QUEUE_URL
    else:
        return {"status": "400, Bad Request"}

    sqs.send_message(QueueUrl=queue_url, MessageBody=id, MessageAttributes=attributes)

    return {"status": "200, queued for inference"}
