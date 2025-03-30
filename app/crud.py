from sqlalchemy.orm import Session
from app.models import Message, MessageAttachment
from app.schemas import MessageCreate
from app.services.blob import delete_blob_by_url

def create_message(db: Session, message: MessageCreate):
    new_message = Message(**message.dict())
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message

def get_messages(db: Session, limit: int = 50):
    return db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()

# def delete_message(db: Session, message_id: int):
#     db.query(MessageAttachment).filter(MessageAttachment.message_id == message_id).delete
#     message = db.query(Message).filter(Message.message_id == message_id).first()
#     if message:
#         db.delete(message)
#         db.commit()
#     return message


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

