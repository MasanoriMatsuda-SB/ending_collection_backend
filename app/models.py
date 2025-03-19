# app/models.py
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from app.db import Base

class User(Base):
    __tablename__ = "users"  # 既存のテーブル名と一致させる
    user_id = Column(Integer, primary_key=True, index=True)  # 主キーはuser_id
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(100), nullable=False)
    photoURL = Column(String(255), nullable=True)  # ユーザーのプロフィール画像のURLを保存
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
