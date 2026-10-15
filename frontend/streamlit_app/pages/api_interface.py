import streamlit as st
import requests
import json
import os
import time
from auth_utils import check_login

check_login()

BASE_API = os.environ["API_BASE_URL"]
API_BASE = f"{BASE_API}/birds"
PRESIGN_ENDPOINT = f"{BASE_API}/presigned-upload"

st.set_page_config(page_title="BirdTag API Interface", layout="wide")
st.title("BirdTag API Interface")

tabs = st.tabs([
    "Search by Tags",
    "Search by Species",
    "Thumbnail → Full-size",
    "Search by File",
    "Manage Tags",
    "Delete Files"
])

# ─── Helpers ────────────────────────────────────────────────────────────────
def fetch_fullsize_urls(thumb_url):
    """
    Given a thumbnail URL, call your /search-thumbnails API,
    unwrap the proxy envelope and return a list of full-size URLs.
    """
    resp = requests.post(f"{API_BASE}/search-thumbnails", json={"url": thumb_url})
    if not resp.ok:
        st.error(f"Error fetching full-size: {resp.status_code} {resp.text}")
        return []

    data = resp.json()
    body = data.get("body", data)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            st.error("Malformed JSON from full-size API")
            return []

    # Try the keys in order of preference
    if "links" in body:
        return body["links"]
    if "full_url" in body:
        return [body["full_url"]]
    if "url" in body:
        return [body["url"]]
    return []


def display_fullsize(thumb_url):
    """
    Fetch and then display the full-size images/videos/audios.
    """
    urls = fetch_fullsize_urls(thumb_url)
    if not urls:
        st.info(f"No full-size version found for\n{thumb_url}")
    else:
        for url in urls:
            display_media(url)

def unwrap(resp):
    """
    Unwrap Lambda‐proxy style responses.
    If the `body` field is a JSON string, parse it.
    If it’s already a dict, just return that dict.
    Otherwise fall back to the full resp.json() blob.
    """
    data = resp.json()
    body = data.get("body")
    # Case 1: proxy‐style returns body as a JSON‐encoded string
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            # not a JSON string, return it raw
            return {"value": body}
    # Case 2: body is already a dict (e.g. your /test endpoint)
    if isinstance(body, dict):
        return body
    # Fallback: no body field or something unexpected
    return data

def display_media(url):
    """
    Render a URL as image, video or audio based on its file extension.
    """
    ext = os.path.splitext(url.split("?",1)[0])[1].lower()
    if ext in (".mp4", ".mov", ".avi", ".webm"):
        st.subheader("A video is as follows")
        st.video(url)
    elif ext in (".mp3", ".wav", ".ogg"):
        st.subheader("An audio is as follows")
        st.audio(url)
    else:
        st.subheader("An image is as follows")
        st.image(url, use_container_width=True)


# ─── 1) Search by Tags ───────────────────────────────────────────────
with tabs[0]:
    st.header("Search Files by Tags")

    tags_json = st.text_area("Enter tags (JSON)", '{"Crow":1}')
    if st.button("Search Tags", key="search_by_tags"):
        # 1) parse JSON
        try:
            tags_dict = json.loads(tags_json)
            if not isinstance(tags_dict, dict):
                raise ValueError("must be a JSON object mapping tag→count")
        except Exception as e:
            st.error(f"Invalid JSON for tags: {e}")
            st.stop()

        # 2) call the API
        resp = requests.post(f"{API_BASE}/search-tags", json={"tags": tags_dict}, headers={"bird-token": st.session_state["token"]})
        if not resp.ok:
            st.error(f"Error {resp.status_code}: {resp.text}")
            st.stop()

        # 3) unwrap if proxy-style
        data = resp.json()
        body = data.get("body", data)
        if isinstance(body, str):
            body = json.loads(body)
        links = body.get("links", [])

        # 4) display each result
        if not links:
            st.info(f"No media found for {tags_dict}")
        else:
            for idx, link in enumerate(links, start=1):
                st.markdown(f"**File {idx}:**")
                ext = os.path.splitext(link.split("?",1)[0])[1].lower()

                # ── Thumbnail or media preview ─────────────────────────
                if ext in (".jpg", ".jpeg", ".png", ".gif"):
                    # thumbnail
                    st.image(link, use_container_width=True)

                    # inline expander
                    with st.expander("🔍 VIEW FULL SIZE IMAGE"):
                        display_fullsize(link)
                else:
                    # for video/audio embed
                    display_media(link)

                # ── Download link for videos ───────────────────────────
                ext = os.path.splitext(link.split("?",1)[0])[1].lower()
                if ext in (".mp4", ".mov", ".avi", ".webm"):
                    st.markdown(f"[Download video]({link})")

                st.write("---")


# ─── 2) Search by Species ────────────────────────────────────────────
with tabs[1]:
    st.header("Search Files by Bird Species")
    species = st.text_input("Enter Species", "Crow")
    if st.button("Search Species"):
        # API expects uppercase species in an array
        resp = requests.post(f"{API_BASE}/search-species", json={"tags": [species]}, headers={"bird-token": st.session_state["token"]})
        if resp.ok:
            payload = unwrap(resp)
            links = payload.get("links", [])
            if not links:
                st.write("No media found for species", species)
            for i in range(len(links)):
                st.markdown(f"**File {i+1}:**")
                display_media(links[i])
        else:
            st.error(f"{resp.status_code}: {resp.text}")


# ─── 3) Thumbnail → Full-size URL ───────────────────────────────────────────────
with tabs[2]:
    st.header("Thumbnail to Full-size URL")
    thumb_url = st.text_input(
        "Thumbnail URL",
        "https://<bucket>.s3.amazonaws.com/thumbnails/<id>-owl_3.jpg"
    )
    if st.button("Get Full-size URL", key="thumb_to_full"):
        urls = fetch_fullsize_urls(thumb_url)
        st.write("The URL is as follows : ")
        for url in urls:
            st.write("The full-sized image URL is : ", url)


# ─── 4) Upload & Search by File (URL) ────────────────────────────────────────
with tabs[3]:
    st.header("Upload & Search by File")

    uploaded_file = st.file_uploader(
        "Choose a media file (image/audio/video)",
        type=["jpg","jpeg","png","gif","mp4","mov","mp3","wav"]
    )

    if uploaded_file:
        mime = uploaded_file.type
        if mime.startswith("image/"):
            st.image(uploaded_file, caption="Preview", use_container_width=True)
        elif mime.startswith("video/"):
            st.video(uploaded_file)
        elif mime.startswith("audio/"):
            st.audio(uploaded_file)

        uploaded_file.seek(0)

        if st.button("Upload & Search", key="upload_search_tab4"):
            # 1) presign + upload
            filename   = uploaded_file.name
            mime_type  = uploaded_file.type
            file_bytes = uploaded_file.read()

            presign_resp = requests.get(
                PRESIGN_ENDPOINT,
                params={"filename": filename, "contentType": mime_type},
                timeout=30,
                headers={"bird-token": st.session_state["token"]}
            )
            if presign_resp.status_code != 200:
                st.error(f"Presign failed: {presign_resp.status_code} {presign_resp.text}")
                st.stop()

            pr         = presign_resp.json()
            upload_url = pr.get("presignedUrl")
            s3_key     = pr.get("s3Key")
            file_url   = pr.get("fileUrl")
            if not upload_url or not s3_key or not file_url:
                st.error("Invalid presign response.")
                st.stop()

            put_resp = requests.put(
                upload_url,
                data=file_bytes,
                headers={"Content-Type": mime_type},
                timeout=300
            )
            if put_resp.status_code not in (200, 201):
                st.error(f"S3 upload failed: {put_resp.status_code} {put_resp.text}")
                st.stop()

            st.success("✅ Uploaded to S3 Successfully.")

            # 2) Poll the search-file API until 200 or 404

            time.sleep(10)

            max_tries = 30
            for attempt in range(max_tries):
                api_resp = requests.post(
                    f"{API_BASE}/search-file",
                    json={"link": file_url},
                    timeout=30,
                    headers={"bird-token": st.session_state["token"]}
                )
                # unwrap the lambda proxy envelope
                payload = unwrap(api_resp)

                # grab the logical statusCode from the body
                body_status = payload.get("statusCode")

                # 202 = still tagging, 404 = worker hasn't recorded the file yet
                if body_status in (202, 404):
                    st.info(f"Inference pending… ({attempt+1}/{max_tries})")
                    time.sleep(5)
                    continue

                # 200 → show links
                if body_status == 200:
                    links = payload.get("links", [])
                    if not links:
                        st.info("No stored files share the uploaded file's tags.")
                    else:
                        st.subheader("The files with similar tags are as follows: ")
                        for i in range(len(links)):
                            st.markdown(f"**File {i + 1}:**")
                            display_media(links[i])
                    break

                st.error(f"Unexpected statusCode {body_status}: {payload}")
                break
            else:
                st.error("⏱ Timed out waiting for inference. Try again in a moment.")


# ─── 5) Add/Remove Tags (Batch Update + Show Response) ────────────────────────
with tabs[4]:
    st.header("Add/Remove Tags")

    urls = st.text_area(
        "URLs (comma-separated)",
        "https://<bucket>.s3.amazonaws.com/image/<id>-owl_3.jpg"
    )
    operation = st.selectbox("Operation", ["Add", "Remove"])
    tags_json = st.text_area(
        "Tags (JSON mapping tag→count)",
        '{"Owl": 2}'
    )

    if st.button("Submit Tags"):
        # build URL list
        url_list = [u.strip() for u in urls.split(",") if u.strip()]

        # parse the tags JSON
        try:
            tags_dict = json.loads(tags_json)
            if not isinstance(tags_dict, dict):
                raise ValueError("must be a JSON object")
        except Exception as e:
            st.error(f"Invalid JSON for tags: {e}")
            st.stop()

        # call the batch‐update API
        payload = {
            "urls":      url_list,
            "operation": 1 if operation == "Add" else 0,
            "tags":      tags_dict
        }
        resp = requests.post(f"{API_BASE}/batch-update", json=payload, headers={"bird-token": st.session_state["token"]})

        if not resp.ok:
            st.error(f"Batch-update failed: {resp.status_code} {resp.text}")
            st.stop()

        # Unwrap the Lambda‐proxy response
        data = resp.json()
        body = data.get("body")

        # If body is a JSON‐encoded string, unquote it
        if isinstance(body, str):
            try:
                result = json.loads(body)
            except json.JSONDecodeError:
                # still plain text
                st.success(body)
                st.stop()
        else:
            result = data

        # If the unwrapped result is still a simple string, show it
        if isinstance(result, str):
            st.success(result)
        else:
            # Otherwise render the JSON structure
            st.success("Batch update result:")
            st.json(result)


# ─── 6) Delete Files ────────────────────────────────────────────────
with tabs[5]:
    st.header("Delete Files")
    urls_delete = st.text_area("URLs to delete (comma-separated)",
      "Put urls here.")
    if st.button("Delete"):
        delete_list = [u.strip() for u in urls_delete.split(",") if u.strip()]
        resp = requests.delete(f"{API_BASE}", json={"links": delete_list}, headers={"bird-token": st.session_state["token"]})
        if resp.ok:
            st.success("✅ The files are deleted from the database successfully.")
            st.snow()
        else:
            st.write("File not present, or some error has occured.")
            st.error(f"{resp.status_code}: {resp.text}")
