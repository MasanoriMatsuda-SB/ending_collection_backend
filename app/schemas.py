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
    text: str
    uid: int

class MessageResponse(MessageCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ====== Chat関連Schema（EndEnd）====== 