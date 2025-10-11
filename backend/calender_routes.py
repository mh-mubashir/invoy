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
from scripts.generate_invoices import generate_my_invoice
from backend.db import UserToken, SessionLocal

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
    # Redirect to the main app after successful authentication
    return RedirectResponse(url="http://localhost:8000/")
    

@router.get("/auth/signup")
def signup():
    """Handle signup - same as login flow since we auto-create users."""
    print("🔹 Starting signup OAuth flow...")
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
    print(f"🔹 Loading tokens for {email}...")
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

@router.get("/auth/existing-user-login")
async def existing_user_login():
    """Handle existing user login using stored tokens."""
    db = SessionLocal()
    try:
        # Get the most recent user (you could also pass email as query param)
        user = db.query(UserToken).order_by(UserToken.id.desc()).first()
        
        if not user:
            return JSONResponse(
                {"error": "No user found. Please sign up first."}, 
                status_code=404
            )
        
        # Check if tokens are valid and refresh if needed
        try:
            creds = load_credentials(user.email)
            print(f"✅ Existing user {user.email} authenticated successfully")
            # Redirect to main app
            return RedirectResponse(url="http://localhost:8000/")
        except Exception as e:
            print(f"❌ Token validation failed for {user.email}: {e}")
            return JSONResponse(
                {"error": "Authentication expired. Please sign in again."}, 
                status_code=401
            )
    finally:
        db.close()


def get_min_max_time(periodLabel):
    # Example inputs
    # periodLabel = "2025-09-30:2025-10-15"
    # month, year = None, None

    now = datetime.utcnow()

    # Default to current month if no month/year provided
    month = now.month
    year = now.year

    # Check if periodLabel contains a date range (e.g. "YYYY-MM-DD:YYYY-MM-DD")
    start_time = None
    end_time = None

    if periodLabel and ":" in periodLabel:
        try:
            start_str, end_str = periodLabel.split(":")
            start_time = datetime.strptime(start_str, "%Y-%m-%d").isoformat() + "Z"
            end_time = datetime.strptime(end_str, "%Y-%m-%d").isoformat() + "Z"
        except ValueError:
            print(f"⚠️ Invalid periodLabel format: {periodLabel} (expected YYYY-MM-DD:YYYY-MM-DD)")

    # Use provided start/end times, or default to the first and last day of the month
    if start_time and end_time:
        time_min = start_time
        time_max = end_time
    else:
        time_min = datetime(year, month, 1).isoformat() + "Z"
        time_max = (
            datetime(year + 1, 1, 1).isoformat() + "Z"
            if month == 12
            else datetime(year, month + 1, 1).isoformat() + "Z"
        )

    print("🕓 time_min:", time_min)
    print("🕓 time_max:", time_max)

    return time_min, time_max

# ---------- CALENDAR ----------
@router.get("/calendar/events")
def get_calendar_events(
    attendee: str = Query(..., description="Attendee email to fetch calendar"),  # required
    periodLabel: str = Query(..., description="Time period label"),  # ✅ now str not int
    email: str = Query(None, description="Optional user email"),  # optional if needed
    save_to_file: bool = Query(True, description="Save results to events.txt")
):
    # try:
        credentials = load_credentials(email)
        headers = {"Authorization": f"Bearer {credentials.token}"}

        print(f"🔹 Fetching calendar events for {periodLabel}...")
        time_min, time_max = get_min_max_time(periodLabel)
        print("🕓 time_min:", time_min, time_max)
        params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"}
        response = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            print("❌ [ERROR] Calendar API failed:", response.text)
            return {"error": "Failed to fetch events", "details": response.text}

        events = response.json().get("items", [])
        print(f"✅ [CALENDAR] Retrieved {len(events)} total events.")

        # # Removed Filtering for business-related events for broader use case
        # keywords = ["meeting", "business", "sync", "client", "review", "kickoff"]
        # filtered = [e for e in events if any(kw in e.get("summary", "").lower() for kw in keywords)]
        
        filtered = events
        print(f"🔹 [FILTER] Found {len(filtered)} business-related events.")

        if attendee:
            filtered = [
                e for e in filtered
                if "attendees" in e and any(
                    attendee.lower() in a.get("email", "").lower()
                    for a in e["attendees"]
                )
            ]
            print(f"🔹 [FILTER] After attendee filter: {len(filtered)} events remain.")

        print(f"filtered events: {filtered}")
        filename = "events.txt"
        is_txt = os.path.splitext(filename)[1].lower() == ".txt"
        if save_to_file:
            if not is_txt:
                event_data = [] # Prepare a list to store event data
                attendees_list = []
                for ev in filtered: # Process each event
                    attendees = ev.get("attendees", [])
                    if attendees:
                        attendees_list = [
                            {
                                "displayName": a.get("displayName", ""),
                                "email": a.get("email", "")
                            }
                            for a in attendees
                        ]
                    event = {
                        "id": ev.get('id', ''),
                        "title": ev.get('summary', ''),
                        "description": ev.get('description', ''),
                        "start": ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date")),
                        "end": ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date")),
                        "status": ev.get('status', ''),
                        "attendees": attendees_list
                    }
                    event_data.append(event)

                # Write to JSON file (compact format)
                events_filename = 'events.json'
                with open(events_filename, 'w') as f:
                    json.dump(event_data, f, separators=(',', ':'))
                print(f"💾 [WRITE] Saved {len(filtered)} events to {events_filename}")
            else:
                with open('events.txt', 'w') as f:
                    billing_period = periodLabel.replace(":", " to ")
                    f.write(f"Calendar export - Billing Period: {billing_period}\n")
                    f.write("Timezone: America/Boston\n")
                    f.write("Source: Google Calendar API (simulated)\n")
                    for ev in filtered:
                        f.write("Event:\n")
                        f.write(f"  id: {ev.get('id', '-')}\n")
                        f.write(f"  title: {ev.get('summary', '-')}\n")
                        f.write(f"  description: {ev.get('description', '-')}\n")
                        start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date"))
                        end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date"))
                        f.write(f"  start: {start}\n")
                        f.write(f"  end: {end}\n")
                        f.write(f"  status: {ev.get('status', '')}\n")
                        attendees = ev.get("attendees", [])
                        if attendees:
                            f.write(f"  attendees:\n")
                            for a in attendees:
                                f.write(f"    - name: {a.get('displayName', '_')}\n")
                                f.write(f"      email: {a.get('email', '')}\n")
                        f.write("\n")
                print(f"💾 [WRITE] Saved {len(filtered)} events to events.txt")
        print(f"Saving file: {filename}")  
        out, duration_hours, rate = generate_my_invoice(filename)

        # return {
        #     "total": len(filtered),
        #     "saved_to": "events.txt" if save_to_file else None,
        #     "filters": {"month": month, "year": year, "attendee": attendee},
        #     "events": filtered
        # }
    
        # Convert absolute path to relative path for frontend
        invoice_filename = out.name  # Get just the filename
        invoice_relative_path = f"/invoices/{invoice_filename}"
        
        # Fake data for testing
        data = {
            "totalH": duration_hours,
            "hourly": rate,
            "invoicePath": invoice_relative_path,
            "attendee": attendee,
            "periodLabel": periodLabel,
        }
        # Return as JSON (explicitly)
        print("data", data)
        return JSONResponse(content=data)
    # except Exception as e:
    #     print("❌ [ERROR] Calendar event fetch failed:", e)
    #     return JSONResponse({"error": str(e)}, status_code=500)
    
        # # Fake data for testing
        # data = {
        #     "totalH": 12.5,
        #     "hourly": 200,
        #     "invoicePath": "/invoices/sample.pdf",
        #     "attendee": attendee,
        #     "periodLabel": periodLabel,
        # }
        # # Return as JSON (explicitly)
        # return JSONResponse(content=data)

