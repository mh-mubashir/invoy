import os
import json
import requests
from datetime import datetime
from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleRequest

from src.database.db import UserToken, SessionLocal

# Load env
load_dotenv()

router = APIRouter()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]


# ---------- AUTH FLOW ----------
@router.get("/auth/login")
def login():
    print("🔹 Starting OAuth flow...")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return RedirectResponse(auth_url)


@router.get("/auth/callback")
def callback(request: Request):
    """Handle Google callback and store tokens in DB."""
    code = request.query_params.get("code")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Fetch user info
    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"}
    ).json()
    email = user_info.get("email")

    db = SessionLocal()
    user = db.query(UserToken).filter(UserToken.email == email).first()

    if not user:
        user = UserToken(email=email)
        db.add(user)

    user.access_token = creds.token
    user.refresh_token = creds.refresh_token
    user.token_uri = creds.token_uri
    user.client_id = creds.client_id
    user.client_secret = creds.client_secret
    user.expiry = creds.expiry
    user.scopes = json.dumps(creds.scopes)

    db.commit()
    db.close()

    print(f"✅ Tokens saved for {email}")
    return JSONResponse({"message": f"Login successful for {email}!"})


# ---------- TOKEN HELPER ----------
def load_credentials(email: str):
    db = SessionLocal()
    if email is None:
        user = db.query(UserToken).order_by(UserToken.id.desc()).first()
        email = user.email
    else:
        user = db.query(UserToken).filter(UserToken.email == email).first()
    if not user:
        raise Exception(f"No tokens found for {email}. Please authenticate first.")
    db.close()

    creds_data = {
        "token": user.access_token,
        "refresh_token": user.refresh_token,
        "token_uri": user.token_uri,
        "client_id": user.client_id,
        "client_secret": user.client_secret,
        "scopes": json.loads(user.scopes),
    }
    print(f"♻️ Loading credentials for {creds_data}...")

    creds = Credentials.from_authorized_user_info(creds_data)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print(f"♻️ Refreshing token for {email}...")
            creds.refresh(GoogleRequest())
            db = SessionLocal()
            user = db.query(UserToken).filter(UserToken.email == email).first()
            user.access_token = creds.token
            user.expiry = creds.expiry
            db.commit()
            db.close()
            print(f"✅ Token refreshed for {email}")
        else:
            raise Exception("Credentials invalid or missing refresh token.")

    return creds


# ---------- CALENDAR ----------
@router.get("/calendar/events")
def get_calendar_events(
    email: str = Query(None, description="User email to fetch calendar"),
    month: int = Query(None, description="Month number (1-12)"),
    year: int = Query(None, description="Year"),
):
    try:
        creds = load_credentials(email)
        headers = {"Authorization": f"Bearer {creds.token}"}

        now = datetime.utcnow()
        month = month or now.month
        year = year or now.year
        time_min = datetime(year, month, 1).isoformat() + "Z"
        time_max = (
            datetime(year + 1, 1, 1).isoformat() + "Z"
            if month == 12 else datetime(year, month + 1, 1).isoformat() + "Z"
        )

        params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"}
        resp = requests.get("https://www.googleapis.com/calendar/v3/calendars/primary/events",
                            headers=headers, params=params)

        if resp.status_code != 200:
            print("❌ Google Calendar API failed:", resp.text)
            return {"error": resp.text}

        events = resp.json().get("items", [])
        print(f"📅 Retrieved {len(events)} events for {email}")
        return {"email": email, "count": len(events), "events": events}

    except Exception as e:
        print("❌ Error fetching events:", e)
        return {"error": str(e)}
