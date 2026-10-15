from flask import Flask, render_template, request, redirect, url_for, session, make_response
import boto3
import os
import hmac
import hashlib
import base64
from dotenv import load_dotenv
import jwt
import datetime
import urllib.parse

load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Demo mode skips Cognito: any email/password signs in, so the UI can be explored without AWS.
DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"

# Cognito config
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

JWT_SECRET = os.getenv("JWT_SECRET", "local-dev-secret-change-me-before-deploying")
JWT_ALGORITHM = "HS256"
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")


def get_secret_hash(username, client_id, client_secret):
    message = username + client_id
    dig = hmac.new(client_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


def redirect_to_app(email):
    """Issue a short-lived JWT and hand it to the Streamlit app."""
    payload = {
        "user": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    resp = make_response(redirect(f"{STREAMLIT_URL}?auth_token={urllib.parse.quote(token)}"))
    resp.set_cookie("auth_token", token, httponly=True, secure=False)
    return resp


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if DEMO_MODE:
        return render_template("login.html", message="Demo mode: sign in with any email and password.")

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")
        secret_hash = get_secret_hash(email, CLIENT_ID, CLIENT_SECRET)

        client = boto3.client("cognito-idp", region_name=AWS_REGION)

        try:
            client.sign_up(
                ClientId=CLIENT_ID,
                Username=email,
                Password=password,
                SecretHash=secret_hash,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "given_name", "Value": first_name},
                    {"Name": "family_name", "Value": last_name}
                ]
            )
            # Redirect to confirmation page after signup
            return redirect(url_for("confirm", email=email))
        except client.exceptions.UsernameExistsException:
            return render_template("signup.html", error="User already exists.")
        except Exception as e:
            return render_template("signup.html", error=str(e))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if DEMO_MODE:
            session["user"] = email
            return redirect_to_app(email)

        secret_hash = get_secret_hash(email, CLIENT_ID, CLIENT_SECRET)
        client = boto3.client("cognito-idp", region_name=AWS_REGION)

        try:
            response = client.initiate_auth(
                ClientId=CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                    "SECRET_HASH": secret_hash
                }
            )

            session["user"] = email
            session["tokens"] = response["AuthenticationResult"]
            return redirect_to_app(email)

        except client.exceptions.UserNotConfirmedException:
            return redirect(url_for("confirm", email=email))
        except client.exceptions.NotAuthorizedException:
            return render_template("login.html", error="Invalid credentials.")
        except Exception as e:
            return render_template("login.html", error=str(e))

    return render_template("login.html")


@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    if request.method == "POST":
        email = request.form.get("email")
        code = request.form.get("code")
        secret_hash = get_secret_hash(email, CLIENT_ID, CLIENT_SECRET)

        client = boto3.client("cognito-idp", region_name=AWS_REGION)

        try:
            client.confirm_sign_up(
                ClientId=CLIENT_ID,
                Username=email,
                ConfirmationCode=code,
                SecretHash=secret_hash
            )
            return render_template("login.html", message="Account confirmed successfully! You can now log in.")
        except Exception as e:
            return render_template("confirm.html", error=str(e))

    return render_template("confirm.html", email=request.args.get("email", ""))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(port=8500)
