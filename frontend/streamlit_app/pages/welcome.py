import streamlit as st
import streamlit.components.v1 as components
from auth_utils import check_login
from pathlib import Path
import base64
import requests
import urllib.parse
import os

ASSETS_DIR = Path(__file__).parent.parent / "assets"
# Carousel shows the first image of each species (*_1.jpg) in demo/media, or CAROUSEL_DIR
CAROUSEL_DIR = Path(os.getenv("CAROUSEL_DIR", Path(__file__).resolve().parents[3] / "demo" / "media"))
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8500")
API_URL = f"{os.environ['API_BASE_URL']}/subscribe"

check_login()

# ----------------------------
# Sidebar: Actions
# ----------------------------
st.sidebar.markdown("## 👤 Logged in User")

if "auth_token" not in st.session_state:
    query_token = st.query_params.get("auth_token")
    if query_token:
        st.session_state["auth_token"] = query_token

# Extract user info
user_email = st.session_state.get("user", "N/A")
auth_token = st.session_state.get("auth_token", "Not set")
encoded_token = urllib.parse.quote(auth_token) if auth_token else ""

st.sidebar.markdown(f"**Email:** `{user_email}`")

if not auth_token:
    st.sidebar.markdown("Login again")

if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.sidebar.success("Logged out. Redirecting...")
    st.markdown(f'<meta http-equiv="refresh" content="1; url={AUTH_URL}/login">', unsafe_allow_html=True)


st.markdown(
    """
    <style>
      /* Make the entire Streamlit page dark (if you’re in dark mode) */
      body { background-color: #0E1117; }
      h1 { color: #FFFFFF; font-family: 'Segoe UI', sans-serif; text-align: center; margin-bottom: 0.2rem; }
      p.subtitle { color: #DDDDDD; font-size:18px; text-align: center; margin-top: -0.4rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h1>👋 Welcome to BirdTag!</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='subtitle'>An AWS-powered Serverless Media Storage System with Advanced Tagging Capabilities</p>",
    unsafe_allow_html=True,
)

slide_sources = [
    f"data:image/jpeg;base64,{base64.b64encode(p.read_bytes()).decode()}"
    for p in sorted(CAROUSEL_DIR.glob("*_1.jpg"))[:5]
]

# ------------------------------------------------------------
# Build Carousel Items (400px tall, object-fit:cover)
# ------------------------------------------------------------
carousel_items = ""
for idx, src in enumerate(slide_sources):
    active = "active" if idx == 0 else ""
    carousel_items += f"""
      <div class="carousel-item {active}">
        <img 
          src="{src}"
          class="d-block w-100"
          style="display:block; height:400px; object-fit:cover; margin:0; padding:0;"
          alt="Slide {idx+1}"
        />
      </div>
    """

# ------------------------------------------------------------
# Wrap Carousel in Two Layers:
#  1) .frame-wrapper = full-width dark background (eliminates white)
#  2) .card-container  = centered “card” with rounded corners + shadow
# Also force html & body to dark (#0E1117)
# ------------------------------------------------------------
carousel_html = f"""
<!DOCTYPE html>
<html style="background-color: #0E1117; margin: 0; padding: 0;">
<head>
  <meta charset="utf-8" />
  <style>
    /* Ensure the iframe’s HTML & body are dark */
    html, body {{
      background-color: #0E1117;
      margin: 0;
      padding: 0;
    }}
    /* Full-width wrapper: covers entire iframe with dark background */
    .frame-wrapper {{
      width: 100%;
      background-color: #0E1117;   /* match the rest of the page */
      padding: 1rem 0;              /* vertical padding above & below the card */
      box-sizing: border-box;
    }}
    /* The “card” around the carousel */
    .card-container {{
      background-color: #0E1117;   /* same dark background */
      border-radius: 12px;
      box-shadow: rgba(0, 0, 0, 0.4) 0px 4px 12px;
      overflow: hidden;             /* ensures rounded corners clip images */
      max-width: 820px;             /* slightly wider than 800px slide */
      margin: 0 auto;               /* center horizontally */
    }}

    .card-container img {{
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }}

    /* Hide default dots/indicators (optional) */
    .carousel-indicators {{
      display: none;
    }}
    /* Ensure the carousel itself has no white background */
    #birdCarousel {{
      background-color: transparent;
    }}
    /* Remove default padding/margins inside .carousel-inner */
    .carousel-inner {{
      margin: 0;
      padding: 0;
    }}
  </style>
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
    rel="stylesheet"
  />
</head>
<body>
  <div class="frame-wrapper">
    <div class="card-container">
      <div 
        id="birdCarousel" 
        class="carousel slide" 
        data-bs-ride="carousel" 
        data-bs-interval="2000"  <!-- 2-second auto-advance -->
      >
        <div class="carousel-inner">
          {carousel_items}
        </div>
        <button
          class="carousel-control-prev"
          type="button"
          data-bs-target="#birdCarousel"
          data-bs-slide="prev"
        >
          <span class="carousel-control-prev-icon" aria-hidden="true"></span>
          <span class="visually-hidden">Previous</span>
        </button>
        <button
          class="carousel-control-next"
          type="button"
          data-bs-target="#birdCarousel"
          data-bs-slide="next"
        >
          <span class="carousel-control-next-icon" aria-hidden="true"></span>
          <span class="visually-hidden">Next</span>
        </button>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# ------------------------------------------------------------
# Render the HTML in an iframe that’s just tall enough.
# Height = 400px (slide) + ~40px for controls + ~16px padding top/bottom.
# ------------------------------------------------------------
if slide_sources:
    components.html(carousel_html, height=456, scrolling=False)

# Add vertical space before the features
st.markdown("<br><br>", unsafe_allow_html=True)


# Give the side‐pads more relative weight, and narrow the cards slightly.
pad_left, col1, spacer1, col2, spacer2, col3, pad_right = st.columns([3, 3, 2, 3, 2, 3, 2])
with col1:
    st.image(ASSETS_DIR / "icon_auto_tagging.png", width=80)
    st.subheader("Auto-Tagging")
    st.write("Upload any media—BirdTag auto-tags species in S3 & DynamoDB.")
with col2:
    st.image(ASSETS_DIR / "icon_search.png", width=80)
    st.subheader("Search by Species")
    st.write("Type “sparrow ≥ 2” to see all files with ≥2 sparrows.")
with col3:
    st.image(ASSETS_DIR / "icon_serverless.png", width=80)
    st.subheader("Serverless & Scalable")
    st.write("Leverages API Gateway & Lambda—no servers, no worries.")

st.markdown("<br><br>", unsafe_allow_html=True)

# ----------------------------------------
# Subscription Section: Vertical Layout
# ----------------------------------------

ALL_BIRD_TAGS = ["Crow", "Sparrow", "Peacock", "Myna", "Owl", "Pigeon","Kingfisher"]

# Inject custom CSS for the form “card” and button
st.markdown(
    """
    <style>
      /* 1) Let the page stretch wider */
      div.block-container {
        max-width: 1000px !important;   /* or whatever you want */
      }
      /* 2) Force the form itself to sit at a fixed width (and center it) */
      div[data-testid="stForm"] {
        width: 1000px !important;        /* your desired form width */
        max-width: 90% !important;      /* responsive fallback */
        margin: 2rem auto !important;   /* horizontally center */
        background: #1E1E24;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
      }
      /* 3) Make the button fill that width */
      div[data-testid="stForm"] .stButton>button {
        width: 100% !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# center the heading
st.markdown(
    "<h2 style='text-align:center; margin-top:2rem;'>📬 Subscribe to Bird-Tag Notifications</h2>",
    unsafe_allow_html=True,
)

with st.form("subscribe_form"):
    email = st.text_input(
        "✉️ Email address",
        placeholder="you@example.com"
    )
    tags = st.multiselect(
        "🦅 Bird species to follow",
        options=ALL_BIRD_TAGS,
        help="Pick one or more species"
    )
    submitted = st.form_submit_button("🚀 Subscribe")

    # Handle submission
    if submitted:
        # Basic validation
        if not email or "@" not in email:
            st.error("⚠️ Please enter a valid email address.")
        elif not tags:
            st.error("⚠️ Pick at least one bird species.")
        else:
            # Show spinner while calling API
            with st.spinner("Processing your subscription…"):
                try:
                    payload = {"email": email, "tags": tags}
                    resp = requests.post(API_URL, json=payload, timeout=10)
                    data = resp.json()
                    if resp.status_code == 200:
                        st.success("✅ Subscription request sent! Check your email to confirm.")
                        st.balloons()
                    else:
                        st.error(f"Error {resp.status_code}: {data.get('error')}")
                except Exception as e:
                    st.error(f"❌ Failed to call subscription API: {e}")