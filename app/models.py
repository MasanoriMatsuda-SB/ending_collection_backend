# app/models.py
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, ForeignKey, func
from app.db import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SqlEnum
import enum

class User(Base):
    __tablename__ = "users"  # 既存のテーブル名と一致させる
    user_id = Column(Integer, primary_key=True, index=True)  # 主キーはuser_id
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(100), nullable=False)
    photoURL = Column(String(255), nullable=True)  # ユーザーのプロフィール画像のURLを保存
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Thread(Base):
    __tablename__ = "threads"

    thread_id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.thread_id"))
    user_id = Column(Integer, ForeignKey("users.user_id"))
    parent_message_id = Column(Integer,nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    is_edited = Column(Boolean, default=False)

    user = relationship("User", backref="messages")
    attachments = relationship("MessageAttachment", back_populates="message") 


# Attachments対応
class AttachmentType(str, enum.Enum):
    image = "image"
    voice = "voice"
    video = "video"
    file = "file"

class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    attachment_id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.message_id"), nullable=False)
    attachment_url = Column(String(255), nullable=True)
    attachment_type = Column(SqlEnum(AttachmentType), nullable=False)
    uploaded_at = Column(TIMESTAMP, server_default=func.now())

    message = relationship("Message", back_populates="attachments")