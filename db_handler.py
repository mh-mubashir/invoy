import sqlite3
import datetime
from pathlib import Path

class DbHandler:
    def __init__(self, db_path: str = "invoy.db"):
        self.db_path = Path(db_path)
        self._ensure_db()

    def _connect(self):
        """Create a connection to the SQLite DB."""
        return sqlite3.connect(self.db_path)

    def _ensure_db(self):
        """Initialize SQLite DB and table if not exists."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS google_tokens (
                    email TEXT PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expiry TEXT
                )
            """)
        print(f"✅ Database initialized at {self.db_path.resolve()}")

    # === TOKEN MANAGEMENT ===

    def save_tokens(self, email, access_token, refresh_token, expiry):
        """Insert or update tokens for a user."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO google_tokens (email, access_token, refresh_token, expiry)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=COALESCE(excluded.refresh_token, google_tokens.refresh_token),
                    expiry=excluded.expiry
            """, (email, access_token, refresh_token, expiry))
            conn.commit()

    def get_tokens(self, email):
        """Retrieve stored tokens for a given email."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT access_token, refresh_token, expiry FROM google_tokens WHERE email=?",
                (email,),
            )
            row = cur.fetchone()

        if row:
            access_token, refresh_token, expiry = row
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expiry": expiry,
            }
        return None

    def get_last_token(self):
        """Retrieve the most recently stored token from any user."""
        with self._connect() as conn:
            cur = conn.execute("""
                SELECT email, access_token, refresh_token, expiry
                FROM google_tokens
                ORDER BY datetime(expiry) DESC
                LIMIT 1
            """)
            row = cur.fetchone()

        if row:
            email, access_token, refresh_token, expiry = row
            return {
                "email": email,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expiry": expiry,
            }
        return None


    def update_access_token(self, email, access_token, expiry):
        """Update access token and expiry (after refresh)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE google_tokens SET access_token=?, expiry=? WHERE email=?",
                (access_token, expiry, email),
            )
            conn.commit()

    def delete_user(self, email):
        """Delete token entry for a user."""
        with self._connect() as conn:
            conn.execute("DELETE FROM google_tokens WHERE email=?", (email,))
            conn.commit()
