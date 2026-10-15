import os
import streamlit as st
import requests

from auth_utils import check_login

check_login()

BASE_API = os.environ["API_BASE_URL"]
PRESIGN_ENDPOINT = f"{BASE_API}/presigned-upload"

# ── STREAMLIT UI ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Upload Large Media", layout="centered")
st.title("⬆️ Upload Image/Audio/Video")

st.caption("Files upload straight to S3 through a presigned URL, so large videos never pass through the API.")

uploaded_file = st.file_uploader(
    label="Choose a media file",
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
    else:
        st.write(f"Preview not supported for `{mime}`.")

    uploaded_file.seek(0)

    if st.button("Upload via Presigned URL"):
        filename = uploaded_file.name   # e.g. "bigvideo.mp4"
        mime_type = uploaded_file.type  # e.g. "video/mp4"
        file_bytes = uploaded_file.read()

        # 1) Request a presigned URL from the API (GET /presigned-upload)
        params = {
            "filename":    filename,
            "contentType": mime_type
        }
        with st.spinner("Getting presigned URL..."):
            try:
                presign_resp = requests.get(PRESIGN_ENDPOINT, params=params, timeout=30, headers={"bird-token": st.session_state["token"]})
            except Exception as e:
                st.error(f"Failed to get presigned URL: {e}")
                st.stop()

        if presign_resp.status_code != 200:
            st.error(f"Presign request failed: {presign_resp.status_code} {presign_resp.text}")
            st.stop()

        data = presign_resp.json()
        presigned_url = data.get("presignedUrl")
        s3_key = data.get("s3Key")

        if not presigned_url or not s3_key:
            st.error("Invalid presign response (missing presignedUrl or s3Key).")
            st.stop()

        # 2) Use the presigned URL to upload directly to S3
        headers = {
            "Content-Type": mime_type
        }
        with st.spinner("Uploading file to S3..."):
            try:
                put_resp = requests.put(presigned_url, data=file_bytes, headers=headers, timeout=300)
            except Exception as e:
                st.error(f"Failed to PUT to S3: {e}")
                st.stop()

        if put_resp.status_code not in (200, 201):
            st.error(f"S3 upload failed: {put_resp.status_code} {put_resp.text}")
        else:
            st.success(f"✅ Upload complete! Tagging starts automatically.\n\nFile URL: {data.get('fileUrl', s3_key)}")
