import os
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
from db_handler import DbHandler

from fastapi import FastAPI, HTTPException, Request
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Load environment variables
load_dotenv()

db = DbHandler()

app = FastAPI(title="Google Calendar Integration API")

# Google OAuth Configuration
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# === AUTHENTICATION ===
@app.get("/auth/login")
def login():
    """Redirect user to Google OAuth consent screen."""
    user_info = db.get_last_token()
    if user_info is not None:
        print("User already logged in:", user_info['email'])
        return JSONResponse({
            "message": "User already logged in",
            "user": user_info
        })
    
    print("Login endpoint hit")
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
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return RedirectResponse(authorization_url)


@app.get("/auth/callback")
def callback(request: Request):
    """Handle Google callback, exchange code for access token."""
    print("Callback endpoint hit")
    
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
    credentials = flow.credentials

    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"}
    ).json()

    db.save_tokens(email=user_info['email'], access_token=credentials.token,
                   refresh_token=credentials.refresh_token, 
                   expiry=credentials.expiry.isoformat())

    return JSONResponse({
        "message": "Login successful!",
        "user": user_info,
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_in": credentials.expiry.isoformat()
    })


# === CALENDAR INTEGRATION ===
@app.get("/calendar/events")
def get_calendar_events(
    access_token: str = Query(..., description="OAuth Access Token"),
    month: int = Query(None, description="Month number (1-12)"),
    year: int = Query(None, description="Year, e.g. 2025"),
    attendee_email: str = Query(None, description="Filter by attendee email"),
    save_to_file: bool = Query(True, description="Save results to events.txt")
):
    """
    Fetch business-related events and optionally write them to a text file.
    """
    now = datetime.utcnow()
    month = month or now.month
    year = year or now.year

    time_min = datetime(year, month, 1).isoformat() + "Z"
    time_max = (
        datetime(year + 1, 1, 1).isoformat() + "Z"
        if month == 12
        else datetime(year, month + 1, 1).isoformat() + "Z"
    )

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"}

    response = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        params=params
    )
    if response.status_code != 200:
        return {"error": "Failed to fetch events", "details": response.text}

    events = response.json().get("items", [])
    keywords = ["meeting", "business", "sync", "client", "review", "kickoff"]
    filtered = [e for e in events if any(kw in e.get("summary", "").lower() for kw in keywords)]

    # Optional email filter
    if attendee_email:
        filtered = [
            e for e in filtered
            if "attendees" in e and any(
                attendee_email.lower() in a.get("email", "").lower()
                for a in e["attendees"]
            )
        ]

    # Write to text file if enabled
    if save_to_file:
        with open("events.txt", "w", encoding="utf-8") as f:
            for ev in filtered:
                f.write("Event:\n")
                f.write(f"id: {ev.get('id', 'N/A')}\n")
                f.write(f"title: {ev.get('summary', 'N/A')}\n")
                f.write(f"description: {ev.get('description', 'N/A')}\n")
                start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date"))
                end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date"))
                f.write(f"start: {start}\n")
                f.write(f"end:   {end}\n")
                f.write(f"status: {ev.get('status', 'N/A')}\n")

                attendees = ev.get("attendees", [])
                if attendees:
                    f.write("attendees:\n")
                    for a in attendees:
                        f.write(f"  - name: {a.get('displayName', 'N/A')}\n")
                        f.write(f"    email: {a.get('email', 'N/A')}\n")
                f.write("\n" + "-" * 40 + "\n\n")

    return {
        "total": len(filtered),
        "saved_to": "events.txt" if save_to_file else None,
        "filters": {"month": month, "year": year, "attendee_email": attendee_email},
        "events": filtered
    }

@app.get("/")
def root():
    return {"message": "Google Calendar API Backend is running!"}
