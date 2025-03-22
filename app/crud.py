from sqlalchemy.orm import Session
from models import Message
from schemas import MessageCreate

def create_message(db: Session, message: MessageCreate):
    new_message = Message(**message.dict())
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message

def get_messages(db: Session, limit: int = 50):
    return db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()
