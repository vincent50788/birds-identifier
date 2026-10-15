import jwt
import streamlit as st
import os

JWT_SECRET = os.getenv("JWT_SECRET", "local-dev-secret-change-me-before-deploying")
JWT_ALGORITHM = "HS256"
LOGIN_URL = f"{os.getenv('AUTH_URL', 'http://localhost:8500')}/login"

def check_login():
    if "user" in st.session_state and "token" in st.session_state:
        return

    token = st.query_params.get("auth_token")

    if isinstance(token, list):
        token = token[0]  # handle multiple values

    if not token:
        # No token → send to Flask login
        st.markdown(f'<meta http-equiv="refresh" content="0; url={LOGIN_URL}">', unsafe_allow_html=True)
        st.stop()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        st.session_state["user"] = payload["user"]
        st.session_state["token"] = token

        if "auth_token" not in st.query_params:
            st.query_params.update({"auth_token": token})

    except jwt.ExpiredSignatureError:
        st.warning("🔐 Session expired. Redirecting to login...")
        st.markdown(f'<meta http-equiv="refresh" content="1; url={LOGIN_URL}">', unsafe_allow_html=True)
        st.stop()

    except jwt.InvalidTokenError:
        st.warning("🔐 Invalid token. Redirecting to login...")
        st.markdown(f'<meta http-equiv="refresh" content="1; url={LOGIN_URL}">', unsafe_allow_html=True)
        st.stop()
