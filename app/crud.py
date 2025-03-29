from sqlalchemy.orm import Session
from app.models import Message
from app.schemas import MessageCreate

def create_message(db: Session, message: MessageCreate):
    new_message = Message(**message.dict())
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message

def get_messages(db: Session, limit: int = 50):
    return db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()

def delete_message(db: Session, message_id: int):
    message = db.query(Message).filter(Message.message_id == message_id).first()
    if message:
        db.delete(message)
        db.commit()
    return message