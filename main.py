import os
import json
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from db_handler import DB_Handler

# ------------------------- LOAD ENVIRONMENT -------------------------
load_dotenv()

app = FastAPI(title="Google Calendar Integration API")

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
TOKEN_FILE = "tokens.json"
db = DB_Handler()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# ------------------------- AUTHENTICATION -------------------------
@app.get("/auth/login")
def login():
    """Redirect user to Google OAuth consent screen."""
    try:
        print("🔹 [LOGIN] Starting Google OAuth login flow...")
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
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        print(f"🔸 [LOGIN] Redirecting user to: {authorization_url}")
        return RedirectResponse(authorization_url)
    except Exception as e:
        print("❌ [ERROR] Login initialization failed:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/auth/callback")
def callback(request: Request):
    """Handle Google callback and store tokens."""
    try:
        code = request.query_params.get("code")
        print("🔹 [CALLBACK] Received OAuth callback from Google...")

        if not code:
            print("❌ [ERROR] Missing authorization code in callback URL")
            return JSONResponse({"error": "Missing authorization code"}, status_code=400)

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
        print("✅ [CALLBACK] Access token fetched successfully!")

        # Save tokens persistently
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat()
        }

        db.save_token(token_data)
        print("💾 [CALLBACK] Tokens saved to tokens.json")

        # Fetch user info
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"}
        ).json()
        print(f"👤 [USER] Logged in as: {user_info.get('email')}")

        return JSONResponse({
            "message": "Login successful! Tokens saved.",
            "user": user_info
        })

    except Exception as e:
        print("❌ [ERROR] OAuth callback failed:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ------------------------- UTILITIES -------------------------
def load_credentials():
    """Load saved credentials and refresh if expired."""
    try:
        data = db.get_last_token()

        creds = Credentials.from_authorized_user_info(data)
        print("🔹 [TOKEN] Loaded credentials from tokens.json")

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                print("♻️ [TOKEN] Token expired — refreshing...")
                creds.refresh(requests.Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                print("✅ [TOKEN] Token refreshed successfully.")
            else:
                raise Exception("Credentials invalid or missing refresh token.")

        return creds
    except Exception as e:
        print("❌ [ERROR] Loading credentials failed:", e)
        raise


# ------------------------- CALENDAR API -------------------------
@app.get("/calendar/events")
def get_calendar_events(
    month: int = Query(None, description="Month number (1-12)"),
    year: int = Query(None, description="Year, e.g. 2025"),
    attendee_email: str = Query(None, description="Filter by attendee email"),
    save_to_file: bool = Query(True, description="Save results to events.txt")
):
    """Fetch business-related events and write them to a text file."""
    try:
        credentials = load_credentials()
        headers = {"Authorization": f"Bearer {credentials.token}"}

        now = datetime.utcnow()
        month = month or now.month
        year = year or now.year

        time_min = datetime(year, month, 1).isoformat() + "Z"
        time_max = (
            datetime(year + 1, 1, 1).isoformat() + "Z"
            if month == 12
            else datetime(year, month + 1, 1).isoformat() + "Z"
        )
        print(f"📅 [CALENDAR] Fetching events for {month}/{year}...")

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

        keywords = ["meeting", "business", "sync", "client", "review", "kickoff"]
        filtered = [e for e in events if any(kw in e.get("summary", "").lower() for kw in keywords)]
        print(f"🔹 [FILTER] Found {len(filtered)} business-related events.")

        if attendee_email:
            filtered = [
                e for e in filtered
                if "attendees" in e and any(
                    attendee_email.lower() in a.get("email", "").lower()
                    for a in e["attendees"]
                )
            ]
            print(f"🔹 [FILTER] After attendee filter: {len(filtered)} events remain.")

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

            print(f"💾 [WRITE] Saved {len(filtered)} events to events.txt")

        return {
            "total": len(filtered),
            "saved_to": "events.txt" if save_to_file else None,
            "filters": {"month": month, "year": year, "attendee_email": attendee_email},
            "events": filtered
        }

    except Exception as e:
        print("❌ [ERROR] Calendar event fetch failed:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/")
def root():
    print("✅ [ROOT] API health check: running fine.")
    return {"message": "Google Calendar API Backend is running!"}


# ------------------------- ENTRY POINT -------------------------
if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting FastAPI Google Calendar Backend...")
    print("📡 Listening on http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="debug")
