from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import logging

from app.models import (
    Message,
    MessageAttachment,
    MessageReaction,
    Category,
    Item,
    ItemImage,
    Thread
)
from app.schemas import (
    MessageCreate,
    MessageReactionCreate,
    ItemCreate,
    CategoryCreate,
    ItemUpdate
)
from app.services.blob import delete_blob_by_url

# ロガーの設定
logger = logging.getLogger(__name__)

# メッセージ関連CRUD
def create_message(db: Session, message: MessageCreate):
    new_message = Message(**message.dict())
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message

def get_messages(db: Session, limit: int = 50):
    return db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()

def delete_message(db: Session, message_id: int):
    # 添付ファイルを取得してBlob削除
    attachments = db.query(MessageAttachment).filter(MessageAttachment.message_id == message_id).all()
    for att in attachments:
        try:
            delete_blob_by_url(att.attachment_url)  # 実ファイル削除
        except Exception as e:
            logger.warning(f"Blob削除失敗: {att.attachment_url} - {e}")

    # DB上の添付データ削除
    db.query(MessageAttachment).filter(MessageAttachment.message_id == message_id).delete()

    # メッセージ本体削除
    message = db.query(Message).filter(Message.message_id == message_id).first()
    if message:
        db.delete(message)
        db.commit()

    return message


# =====Chatreaction関連CRUD(Start)=====
def create_reaction(db: Session, reaction: MessageReactionCreate):
    db_reaction = MessageReaction(**reaction.dict())
    db.add(db_reaction)
    db.commit()
    db.refresh(db_reaction)
    return db_reaction

def get_reactions_by_message(db: Session, message_id: int):
    return db.query(MessageReaction).filter(
        MessageReaction.message_id == message_id
    ).all()

def delete_reaction(db: Session, message_id: int, user_id: int):
    db.query(MessageReaction).filter(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == user_id
    ).delete()
    db.commit()
# =====Chatreaction関連CRUD(End)=====

# =====Item関連CRUD(Start)=====
# カテゴリー関連CRUD
def create_category(db: Session, category: CategoryCreate) -> Category:
    """カテゴリーを作成"""
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def get_categories(db: Session) -> List[Category]:
    """全カテゴリーを取得"""
    return db.query(Category).all()

def get_category(db: Session, category_id: int) -> Optional[Category]:
    """指定したカテゴリーを取得"""
    return db.query(Category).filter(Category.category_id == category_id).first()

# 物品関連CRUD
def create_item(
    db: Session,
    user_id: int,
    item_data: ItemCreate,
    image_url: str
) -> Item:
    """物品を登録"""
    try:
        # 物品の登録
        db_item = Item(
            user_id=user_id,
            group_id=item_data.group_id,
            category_id=item_data.category_id,
            item_name=item_data.item_name,
            description=item_data.description,
            condition_rank=item_data.condition_rank
        )
        db.add(db_item)
        db.flush()

        # 画像の登録
        db_image = ItemImage(
            item_id=db_item.item_id,
            image_url=image_url
        )
        db.add(db_image)

        # スレッドの自動作成
        thread = Thread(
            item_id=db_item.item_id,
            title=f"「{item_data.item_name}」についての思い出"
        )
        db.add(thread)
        
        db.commit()
        db.refresh(db_item)
        return db_item
        
    except Exception as e:
        db.rollback()
        raise e

def get_item(db: Session, item_id: int) -> Optional[Item]:
    """指定した物品を取得"""
    return db.query(Item).filter(Item.item_id == item_id).first()

def get_user_items(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50
) -> List[Item]:
    """ユーザーの物品一覧を取得"""
    return db.query(Item)\
        .filter(Item.user_id == user_id)\
        .order_by(desc(Item.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_group_items(
    db: Session,
    group_id: int,
    skip: int = 0,
    limit: int = 50
) -> List[Item]:
    """グループの物品一覧を取得"""
    return db.query(Item)\
        .filter(Item.group_id == group_id)\
        .order_by(desc(Item.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()

def update_item(
    db: Session,
    item_id: int,
    item_data: ItemUpdate
) -> Optional[Item]:
    """物品情報を更新"""
    try:
        db_item = db.query(Item).filter(Item.item_id == item_id).first()
        if not db_item:
            return None

        update_data = item_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)

        db_item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_item)
        return db_item

    except Exception as e:
        db.rollback()
        raise e

def delete_item(db: Session, item_id: int) -> bool:
    """物品を削除"""
    try:
        # 画像の削除
        images = db.query(ItemImage).filter(ItemImage.item_id == item_id).all()
        for image in images:
            try:
                delete_blob_by_url(image.image_url)
            except Exception as e:
                logger.warning(f"Blob deletion failed for URL {image.image_url}: {e}")

        # 物品の削除（関連するスレッド、画像は CASCADE で自動削除）
        result = db.query(Item).filter(Item.item_id == item_id).delete()
        db.commit()
        return result > 0

    except Exception as e:
        db.rollback()
        raise e

def add_item_image(
    db: Session,
    item_id: int,
    image_url: str
) -> ItemImage:
    """物品に画像を追加"""
    try:
        db_image = ItemImage(
            item_id=item_id,
            image_url=image_url
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        return db_image

    except Exception as e:
        db.rollback()
        raise e
# =====Item関連CRUD(End)=====