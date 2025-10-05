import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# Database setup
Base = declarative_base()
engine = create_engine("sqlite:///tokens.db", echo=False)
SessionLocal = sessionmaker(bind=engine)

class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    access_token = Column(String)
    refresh_token = Column(String)
    token_uri = Column(String)
    client_id = Column(String)
    client_secret = Column(String)
    expiry = Column(DateTime)
    scopes = Column(String)

Base.metadata.create_all(bind=engine)

# Utility to get session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
