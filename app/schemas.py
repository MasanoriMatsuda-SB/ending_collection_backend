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

# ====== Grouping Schema（Start） ====== 
class GroupCreate(BaseModel):
    groupName: str

class GroupResponse(BaseModel):
    group_id: int
    group_name: str

    class Config:
        from_attributes = True
# ====== Grouping Schema（end） ====== 

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
    group_id: int
    ref_item_id: Optional[int] = None
    category_id: Optional[int] = None
    item_name: str
    description: Optional[str] = None
    condition_rank: Optional[str] = None
    status: ItemStatus = None
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

# ====== アイテム詳細画面（Start） ======
# ItemDetail.tsx対応

class ItemWithUsername(ItemResponse):
    username: str

    class Config:
        from_attributes = True

class ReferenceItemsResponse(BaseModel):
    ref_item_id: int
    category_id: int
    item_name: str
    brand_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# ending_collection_frontend-main\src\app\item\[id]\page.tsxへ画像表示対応
class ItemImageResponse(BaseModel):
    image_id: int
    item_id: int
    image_url: str

    class Config:
        from_attributes = True

# ItemDetail.tsx(価格推定)対応
class MarketPriceList(BaseModel):
    market_prices: list[int]
# ====== アイテム詳細画面（End） ======

# ====== Threads作成関連Schema（Start） ====== 
class ThreadCreate(BaseModel):
    item_id: int

# ====== Threads作成関連Schema（End） ====== 

# ====== ここから招待機能関連Schema を追加 ======

class GroupInviteBase(BaseModel):
    group_id: int
    expires_at: Optional[datetime] = None

class GroupInviteCreate(GroupInviteBase):
    """招待作成時のリクエストボディ"""
    # inviter_user_id はサーバー側で JWT から取得する想定なので不要

    class Config:
        schema_extra = {
            "example": {
                "group_id": 1,
                "expires_at": "2025-05-01T12:00:00Z"
            }
        }

class GroupInviteResponse(BaseModel):
    invite_id: int
    group_id: int
    token: str
    inviter_user_id: Optional[int]
    invited_user_id: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]
    used_at: Optional[datetime]
    used: bool

    class Config:
        orm_mode = True

class AcceptInviteRequest(BaseModel):
    token: str

    class Config:
        schema_extra = {
            "example": {"token": "123e4567-e89b-12d3-a456-426614174000"}
        }

class AcceptInviteResponse(GroupInviteResponse):
    """招待受諾後に返却されるデータ。GroupInviteResponse と同じフォーマットで問題ありません。"""
    pass

# ====== 招待機能関連Schema ここまで ======

# ====== プロフィール設定関連Schema ======
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
# ====== プロフィール設定関連Schema ======