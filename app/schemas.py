# app/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime

from typing import Optional, Literal
from enum import Enum

from typing import List


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

# ====== Item関連Schema（Start） ======
class ConditionRank(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class ItemStatus(str, Enum):
    active = "active"
    archived = "archived"

# カテゴリー関連
class CategoryBase(BaseModel):
    category_name: str
    parent_category_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    category_id: int

    class Config:
        from_attributes = True

# 物品関連
class ItemBase(BaseModel):
    item_name: str
    group_id: int
    category_id: int
    description: Optional[str] = None
    condition_rank: ConditionRank

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    item_name: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    condition_rank: Optional[ConditionRank] = None
    status: Optional[ItemStatus] = None

class ItemImage(BaseModel):
    image_id: int
    image_url: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class ItemResponse(ItemBase):
    item_id: int
    user_id: int
    status: ItemStatus
    created_at: datetime
    updated_at: Optional[datetime]
    category_name: str
    images: List[ItemImage]
    detection_confidence: Optional[float] = None

    class Config:
        from_attributes = True

class ItemList(BaseModel):
    items: List[ItemResponse]
    total: int
    
    class Config:
        from_attributes = True

# 画像認識結果
class ImageAnalysisResponse(BaseModel):
    detected_name: str
    confidence: Optional[float] = None
# ====== Item関連Schema（End） ======
