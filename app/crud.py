from sqlalchemy.orm import Session
from app.models import Message, MessageAttachment, MessageReaction, Thread
from app.schemas import MessageCreate, MessageReactionCreate, ThreadCreate
from app.services.blob import delete_blob_by_url

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
            print(f"[警告] Blob削除失敗: {att.attachment_url} - {e}")

    # DB上の添付データ削除
    db.query(MessageAttachment).filter(MessageAttachment.message_id == message_id).delete()

    # メッセージ本体削除
    message = db.query(Message).filter(Message.message_id == message_id).first()
    if message:
        db.delete(message)
        db.commit()

    return message


# ====== ChatReaction関連CRUD（Start） ====== 
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