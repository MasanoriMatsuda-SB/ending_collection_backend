from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import logging
import uuid
import os
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.models import (
    Message,
    MessageAttachment,
    MessageReaction,
    Category,
    Item,
    ItemImage,
    Thread,
    GroupInvite,
    UserFamilyGroup,
    User
)
from app.schemas import (
    MessageCreate,
    MessageReactionCreate,
    ItemCreate,
    CategoryCreate,
    ItemUpdate,
    ThreadCreate
)
from app.services.blob import delete_blob_by_url

from app.utils import get_password_hash

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
    # すでに同じユーザーのリアクションが存在するか確認
    existing = db.query(MessageReaction).filter(
        MessageReaction.message_id == reaction.message_id,
        MessageReaction.user_id == reaction.user_id
    ).first()

    if existing:
        # 同じリアクションタイプの場合は何もしない
        if existing.reaction_type == reaction.reaction_type:
            return existing
        # 違うリアクションなら更新
        existing.reaction_type = reaction.reaction_type
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # なければ新規作成
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

# ====== ChatReaction関連CRUD（End） ====== 


# ====== threads 作成関数CRUD（Start） ====== 
def create_thread(db: Session, thread: ThreadCreate):
    new_thread = Thread(**thread.dict())
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)
    return new_thread
# ====== threads 作成関数CRUD（End） ====== 


# ====== RAG関連CRUD（Start） ====== 
def get_messages_by_item_id(db: Session, item_id: str) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.thread.has(item_id=item_id))  # Threadの外部キーを利用
        .order_by(Message.created_at)
        .all()
    )
# ====== RAG関連CRUD（End） ====== 


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

# ===== ここから招待機能関連 CRUD を追加 =====

def create_group_invite(
    db: Session,
    group_id: int,
    inviter_user_id: int,
    expires_at: Optional[datetime] = None
) -> GroupInvite:
    """
    指定グループへの招待を作成。
    一意のトークンを UUID4 で生成して保存します。
    """
    token = str(uuid.uuid4())
    invite = GroupInvite(
        group_id=group_id,
        token=token,
        inviter_user_id=inviter_user_id,
        expires_at=expires_at
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def get_group_invite_by_token(db: Session, token: str) -> Optional[GroupInvite]:
    """
    招待トークンに対応する GroupInvite レコードを取得。
    存在しなければ None。
    """
    return db.query(GroupInvite).filter(GroupInvite.token == token).first()


def accept_group_invite(
    db: Session,
    token: str,
    invited_user_id: int
) -> Optional[GroupInvite]:
    """
    招待トークンを使って参加を承認。
    - トークンが存在し、未使用かつ有効期限内なら、
      UserFamilyGroup に viewer 権限で追加し、
      invite.used を True、used_at を設定。
    - それ以外は None を返します。
    """
    invite = get_group_invite_by_token(db, token)
    if not invite:
        return None
    # 有効期限チェック
    if invite.used or (invite.expires_at and invite.expires_at < datetime.utcnow()):
        return None

    # まだ所属していなければ追加
    existing = db.query(UserFamilyGroup).filter_by(
        user_id=invited_user_id,
        group_id=invite.group_id
    ).first()
    if not existing:
        membership = UserFamilyGroup(
            user_id=invited_user_id,
            group_id=invite.group_id,
            role="viewer"
        )
        db.add(membership)

    # 招待レコードを更新
    invite.used = True
    invite.used_at = datetime.utcnow()
    invite.invited_user_id = invited_user_id

    db.commit()
    db.refresh(invite)
    return invite


def list_group_invites(db: Session, group_id: int) -> List[GroupInvite]:
    """
    指定グループに対するすべての招待レコードを取得。
    """
    return db.query(GroupInvite).filter(GroupInvite.group_id == group_id).all()


def revoke_group_invite(db: Session, invite_id: int) -> bool:
    """
    招待を取り消し（レコード削除）。
    """
    count = db.query(GroupInvite).filter(GroupInvite.invite_id == invite_id).delete()
    if count:
        db.commit()
        return True
    return False

# ===== 招待機能 CRUD ここまで =====

# ===== ここからプロフィール変更関連 CRUD を追加 =====
def update_user(
    db: Session,
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    password: str | None = None,
    photo_file: bytes | None = None,
    photo_content_type: str | None = None
) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None

    # ユーザー名／メール
    if username:
        user.username = username
    if email:
        user.email = email

    # パスワード
    if password:
        user.password_hash = get_password_hash(password)

    # プロフィール画像
    if photo_file is not None and photo_content_type:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name    = os.getenv("AZURE_CONTAINER_NAME")
        blob_service      = BlobServiceClient.from_connection_string(connection_string)
        container_client  = blob_service.get_container_client(container_name)
        # ファイル名を一意に
        ext = photo_content_type.split("/")[-1]
        blob_name = f"profile-{user_id}/{uuid.uuid4()}.{ext}"
        blob = container_client.get_blob_client(blob_name)
        blob.upload_blob(photo_file, overwrite=True,
                         content_settings=ContentSettings(content_type=photo_content_type))
        user.photoURL = blob.url

    db.commit()
    db.refresh(user)
    return user
# ===== プロフィール変更関連 CRUD ここまで =====