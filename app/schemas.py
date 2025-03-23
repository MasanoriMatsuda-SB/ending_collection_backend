# app/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime

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

class MessageResponse(BaseModel):
    message_id: int
    thread_id: int
    user_id: int
    content: str
    created_at: datetime
    username: str
    photoURL: str | None = None

    class Config:
        from_attributes = True

# ====== Chat関連Schema（EndEnd）====== 