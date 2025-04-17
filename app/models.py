# app/models.py
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SqlEnum
import enum
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

# Grouping
class FamilyGroup(Base):
    __tablename__ = "family_groups"
    group_id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class UserFamilyGroup(Base):
    __tablename__ = "user_family_groups"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("family_groups.group_id"), primary_key=True)
    role = Column(SqlEnum("poster", "viewer", name="user_role_enum"), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now())

class Thread(Base):
    __tablename__ = "threads"

    thread_id = Column(Integer, primary_key=True, autoincrement=True)
    # item_id は items.item_id を参照する外部キー、かつ UNIQUE 制約を付与して一対一を保証
    item_id = Column(Integer, ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False, unique=True)
    title = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="thread")
    
    # Item と Thread の一対一のリレーションシップ（back_populates を使用）
    item = relationship("Item", back_populates="thread")

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.thread_id"))
    user_id = Column(Integer, ForeignKey("users.user_id"))
    parent_message_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    is_edited = Column(Boolean, default=False)

    user = relationship("User", backref="messages")
    attachments = relationship("MessageAttachment", back_populates="message") 

    thread = relationship("Thread", back_populates="messages")

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
    
# リアクション対応
class MessageReaction(Base):
    __tablename__ = "message_reactions"

    reaction_id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.message_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    reaction_type = Column(
        SqlEnum("like", "heart", "smile", "sad", "agree", name="reaction_type_enum"),
        nullable=False
    )
    created_at = Column(TIMESTAMP, server_default=func.now())

# 画像解析対応
class Category(Base):
    __tablename__ = "categories"
    
    category_id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(100), nullable=False)
    parent_category_id = Column(Integer, ForeignKey("categories.category_id"))

    # 自己参照リレーションシップ
    parent_category = relationship("Category", remote_side=[category_id])
    items = relationship("Item", back_populates="category")

class Item(Base):
    __tablename__ = "items"
    
    item_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, nullable=False)  # family_groupsテーブルとの関連
    ref_item_id = Column(Integer)
    category_id = Column(Integer, ForeignKey("categories.category_id"))
    item_name = Column(String(255), nullable=False)
    description = Column(Text)
    condition_rank = Column(
        SqlEnum("S", "A", "B", "C", "D", name="condition_rank_enum"),
        nullable=False
    )
    status = Column(
        SqlEnum("active", "archived", name="item_status_enum"),
        nullable=False,
        server_default="active"
    )
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # リレーションシップ
    user = relationship("User", backref="items")
    category = relationship("Category", back_populates="items")
    images = relationship("ItemImage", back_populates="item", cascade="all, delete-orphan")
    # 一対一の関係：各 Item に対して Thread が1件
    thread = relationship("Thread", back_populates="item", uselist=False)

class ItemImage(Base):
    __tablename__ = "item_images"
    
    image_id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(255), nullable=False)
    uploaded_at = Column(TIMESTAMP, server_default=func.now())

    # リレーションシップ
    item = relationship("Item", back_populates="images")

# ====== アイテム詳細画面（Start） ======
# ItemDetail.tsx対応
class ReferenceItems(Base):
    __tablename__ = "reference_items"

    ref_item_id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, nullable=False)
    item_name = Column(String(255), nullable=False)
    brand_name = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

# ItemDetail.tsx(価格推定)対応
class ReferenceMarketItem(Base):
    __tablename__ = "reference_market_items"

    market_item_id = Column(Integer, primary_key=True, index=True)
    ref_item_id = Column(Integer, nullable=False)
    market_price = Column(Integer, nullable=False)
    condition_rank = Column(String(10), nullable=True)
    listing_date = Column(TIMESTAMP, nullable=False)
    status = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
# ====== アイテム詳細画面（End） ======