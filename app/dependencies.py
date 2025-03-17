# app/dependencies.py
from .db import SessionLocal
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
