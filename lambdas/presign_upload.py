import os
import json
import boto3
import urllib.parse
import uuid

s3 = boto3.client("s3")
BUCKET = os.environ["MEDIA_BUCKET"]
MEDIA_TYPES = ("image", "video", "audio")


def response(status, body):
    return {
        "statusCode": status,
        "body": json.dumps(body),
        "headers": {"Content-Type": "application/json"}
    }


def lambda_handler(event, context):
    """
    GET /presigned-upload?filename=myvideo.mp4&contentType=video/mp4

    Returns 200 + { "presignedUrl": "...", "s3Key": "video/<id>-myvideo.mp4", "fileUrl": "..." }.
    The key prefix (image/ video/ audio/) routes the object through the dispatch Lambda,
    and the "<id>-" filename prefix becomes the DynamoDB item id.
    """
    try:
        qs = event.get("queryStringParameters") or {}
        filename = qs.get("filename")
        content_type = qs.get("contentType")

        if not filename or not content_type:
            return response(400, {"error": "Missing filename or contentType"})

        media_type = content_type.split("/")[0]
        if media_type not in MEDIA_TYPES:
            return response(400, {"error": f"Unsupported content type: {content_type}"})

        # Strip any path from the filename
        base_name = os.path.basename(urllib.parse.unquote_plus(filename))
        s3_key = f"{media_type}/{uuid.uuid4().hex}-{base_name}"

        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": s3_key, "ContentType": content_type},
            ExpiresIn=300  # 5 minutes
        )

        return response(200, {
            "presignedUrl": presigned_url,
            "s3Key": s3_key,
            "fileUrl": f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
        })

    except Exception as e:
        return response(500, {"error": str(e)})
