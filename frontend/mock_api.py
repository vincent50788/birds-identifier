"""
Local stand-in for the API Gateway + Lambda backend, used when DEMO_MODE=1.

Every route returns the same payload shape as its Lambda in /lambdas, so the
Streamlit UI runs unchanged. Media comes from demo/media; tags are derived from
filenames (crows_1.jpg -> {"Crow": 1}) instead of running YOLO/BirdNET.
"""
import json
import mimetypes
import os
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

MEDIA_DIR = Path(os.getenv("DEMO_MEDIA_DIR", Path(__file__).resolve().parent.parent / "demo" / "media"))
PORT = 5001
BASE = f"http://localhost:{PORT}"

app = Flask(__name__)
uploads = {}  # s3_key -> (bytes, content_type), kept in memory only
db = {}       # id -> {"file_url", "thumbnail_url", "tags"}


def species_tags(filename):
    word = Path(filename).stem.split("_")[0].lower()
    return {word.removesuffix("s").title(): 1} if word.isalpha() else {}


def add_item(name, url):
    item = {"file_url": url, "tags": species_tags(name)}
    if mimetypes.guess_type(name)[0].startswith("image"):
        item["thumbnail_url"] = url
    db[uuid.uuid4().hex] = item


def matches(item_tags, wanted):
    return bool(wanted) and all(item_tags.get(t, 0) >= n for t, n in wanted.items())


def find(url):
    return [(i, it) for i, it in db.items() if url in (it["file_url"], it.get("thumbnail_url"))]


def proxy_body(body):
    return jsonify({"statusCode": 200, "body": json.dumps(body)})


@app.post("/birds/search-tags")
def search_tags():
    return proxy_body({"links": [it["file_url"] for it in db.values() if matches(it["tags"], request.json["tags"])]})


@app.post("/birds/search-species")
def search_species():
    wanted = {t.title(): 1 for t in request.json["tags"]}
    return proxy_body({"links": [it["file_url"] for it in db.values() if matches(it["tags"], wanted)]})


@app.post("/birds/search-thumbnails")
def thumbnail_to_full():
    hits = find(request.json["url"])
    if not hits:
        return jsonify({"statusCode": 404, "body": "No matching item found"})
    return proxy_body({"url": hits[0][1]["file_url"]})


@app.post("/birds/search-file")
def search_file():
    link = request.json["link"]
    hits = find(link)
    if not hits:
        return jsonify({"statusCode": 404, "message": f"link {link} not found in database"})
    item_id, item = hits[0]
    links = [it["file_url"] for it in db.values() if it is not item and matches(it["tags"], item["tags"])]
    del db[item_id]  # the query file is not kept, same as the Lambda
    return jsonify({"statusCode": 200, "links": links})


@app.post("/birds/batch-update")
def batch_update():
    body = request.json
    hits = [it for url in body["urls"] for _, it in find(url)]
    if not hits:
        return jsonify({"statusCode": 404, "body": json.dumps("No items found")})
    for it in hits:
        for tag, count in body["tags"].items():
            if body["operation"] == 1:
                it["tags"][tag] = count
            else:
                it["tags"].pop(tag, None)
    return jsonify({"statusCode": 200, "body": json.dumps("Tags updated successfully")})


@app.delete("/birds")
def delete_files():
    for url in request.json["links"]:
        for item_id, _ in find(url):
            db.pop(item_id, None)  # removes the record only; files on disk are untouched
    return jsonify({"statusCode": 200})


@app.get("/presigned-upload")
def presigned_upload():
    media_type = request.args["contentType"].split("/")[0]
    key = f"{media_type}/{uuid.uuid4().hex}-{Path(request.args['filename']).name}"
    return jsonify({"presignedUrl": f"{BASE}/upload/{key}", "s3Key": key, "fileUrl": f"{BASE}/media/{key}"})


@app.put("/upload/<path:key>")
def upload(key):
    uploads[key] = (request.get_data(), request.content_type)
    add_item(key.split("-", 1)[-1], f"{BASE}/media/{key}")
    return "", 200


@app.post("/subscribe")
def subscribe():
    return jsonify({"message": "Subscription request sent"})


@app.get("/media/<path:name>")
def media(name):
    if name in uploads:
        data, content_type = uploads[name]
        return Response(data, content_type=content_type)
    return send_from_directory(MEDIA_DIR, name)


for f in sorted(MEDIA_DIR.glob("*")):
    if mimetypes.guess_type(f.name)[0]:
        add_item(f.name, f"{BASE}/media/{f.name}")

if __name__ == "__main__":
    app.run(port=PORT)
