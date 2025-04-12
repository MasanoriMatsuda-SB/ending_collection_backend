# app/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime

from typing import Optional, Literal
from enum import Enum


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    user_id: int
    username: str
    email: EmailStr

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

# ====== Chat関連Schema（Start） ====== 
class MessageCreate(BaseModel):
    thread_id: int
    user_id: int
    content: str
    parent_message_id: Optional[int] = None

class MessageResponse(BaseModel):
    message_id: int
    thread_id: int
    user_id: int
    content: str
    created_at: datetime
    username: str
    photoURL: str | None = None
    parent_message_id: Optional[int] = None

    class Config:
        from_attributes = True

# ====== Chat関連Schema（EndEnd）====== 

# ====== ChatAttachment関連Schema（Start） ====== 
class AttachmentType(str, Enum):
    image = "image"
    voice = "voice"
    video = "video"
    file = "file"

class MessageAttachmentBase(BaseModel):
    message_id: int
    attachment_url: Optional[str] = None
    attachment_type: AttachmentType

class MessageAttachmentCreate(MessageAttachmentBase):
    pass

class MessageAttachment(MessageAttachmentBase):
    attachment_id: int
    uploaded_at: datetime

    class Config:
        orm_mode = True
        
# ====== ChatAttachment関連Schema（End） ====== 

# ====== ChatReaction関連Schema（Start） ====== 
class MessageReactionBase(BaseModel):
    message_id: int
    user_id: int
    reaction_type: Literal["like", "heart", "smile", "sad", "agree"]

class MessageReactionCreate(MessageReactionBase):
    pass

class MessageReaction(MessageReactionBase):
    reaction_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# ====== ChatAttachment関連Schema（End） ====== 

# ====== Threads作成関連Schema（Start） ====== 
class ThreadCreate(BaseModel):
    item_id: int

# ====== Threads作成関連Schema（End） ====== 