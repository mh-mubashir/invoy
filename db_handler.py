import sqlite3
import json
from datetime import datetime


class DB_Handler:
    def __init__(self, db_name="tokens.db"):
        self.db_name = db_name
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    token_uri TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    expiry TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_token(self, token_data: dict):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tokens (token, refresh_token, token_uri, client_id, client_secret, scopes, expiry)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                token_data["token"],
                token_data["refresh_token"],
                token_data["token_uri"],
                token_data["client_id"],
                token_data["client_secret"],
                json.dumps(token_data["scopes"]),
                token_data["expiry"]
            ))
            conn.commit()

    def get_token(self, token_id: int):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tokens WHERE id = ?", (token_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "token": row[1],
                    "refresh_token": row[2],
                    "token_uri": row[3],
                    "client_id": row[4],
                    "client_secret": row[5],
                    "scopes": json.loads(row[6]),
                    "expiry": row[7]
                }
            return None

    def get_last_token(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tokens ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
        
    def _row_to_dict(self, row):
        return {
            "id": row[0],
            "token": row[1],
            "refresh_token": row[2],
            "token_uri": row[3],
            "client_id": row[4],
            "client_secret": row[5],
            "scopes": json.loads(row[6]),
            "expiry": row[7]
        }
    
    def list_tokens(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tokens")
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "token": row[1],
                    "refresh_token": row[2],
                    "token_uri": row[3],
                    "client_id": row[4],
                    "client_secret": row[5],
                    "scopes": json.loads(row[6]),
                    "expiry": row[7]
                }
                for row in rows
            ]
