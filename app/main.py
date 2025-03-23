import os
import uuid
import logging
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.models import User, Thread, Message
from app.schemas import (
    UserCreate, UserOut, UserLogin, Token,
    MessageCreate, MessageResponse, AttachmentType, MessageAttachmentBase, MessageAttachmentCreate, MessageAttachment
)
from app.utils import get_password_hash, verify_password
from app.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_db
from app.crud import create_message, get_messages

import socketio  #  Socket.IO

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meme_mori_backend")

#  Socket.IO サーバー作成
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
fastapi_app = FastAPI()
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)  # 🔧 FastAPI + SocketIOを結合

# CORS設定
origins = [
    "http://192.168.10.102:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://tech0-techbrain-front-bhh0bjenh5caguch.francecentral-01.azurewebsites.net"
]
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバル例外ハンドラー
@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {exc}"}
    )

@fastapi_app.get("/")
def read_root():
    return {"message": "Hello from meme mori backend with Socket.IO!"}

# Socket.IO イベント定義
@sio.event
async def connect(sid, environ):
    logger.info(f"Socket connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Socket disconnected: {sid}")

@sio.event
async def send_message(sid, data):
    logger.info(f"Message from {sid}: {data}")
    await sio.emit("receive_message", data)

# サインアップ
@fastapi_app.post("/signup", response_model=UserOut)
async def signup(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        db_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if db_user:
            raise HTTPException(status_code=400, detail="ユーザー名またはメールアドレスは既に登録されています")

        photo_url = None
        if photo and photo.filename:
            try:
                connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                container_name = os.getenv("AZURE_CONTAINER_NAME")
                if not connection_string or not container_name:
                    raise HTTPException(status_code=500, detail="Azure Blob Storage の設定が不十分です")
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                container_client = blob_service_client.get_container_client(container_name)

                file_extension = photo.filename.split(".")[-1] if "." in photo.filename else ""
                unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())
                blob_client = container_client.get_blob_client(unique_filename)
                content_settings = ContentSettings(content_type=photo.content_type)
                file_data = await photo.read()
                blob_client.upload_blob(file_data, overwrite=True, content_settings=content_settings)
                photo_url = blob_client.url
                logger.info(f"Image uploaded: {photo_url}")
            except Exception as e:
                logger.error(f"Image upload failed: {e}")
                raise HTTPException(status_code=500, detail=f"画像アップロードに失敗しました: {e}")

        hashed_password = get_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password, photoURL=photo_url)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        raise

# ログイン
@fastapi_app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="認証情報が無効です")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": db_user.username,
            "user_id": db_user.user_id,
            "email": db_user.email,
            "photoURL": db_user.photoURL
        },
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# item_id → thread_id
@fastapi_app.get("/threads/by-item/{item_id}")
def get_thread_by_item(item_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.item_id == item_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread.thread_id}

# メッセージ取得
@fastapi_app.get("/messages", response_model=list[MessageResponse])
def read_messages(thread_id: int, db: Session = Depends(get_db)):
    logger.info(f"メッセージ取得 thread_id={thread_id}")
    messages = (
        db.query(Message)
        .join(User, Message.user_id == User.user_id)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at)
        .all()
    )

    return [
        MessageResponse(
            message_id=m.message_id,
            thread_id=m.thread_id,
            user_id=m.user_id,
            content=m.content,
            created_at=m.created_at,
            username=m.user.username,
            photoURL=m.user.photoURL,
        )
        for m in messages
    ]

# メッセージ投稿
@fastapi_app.post("/messages", response_model=MessageResponse)
def post_message(message: MessageCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == message.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_msg = create_message(db, message)
    response = MessageResponse(
        message_id=new_msg.message_id,
        thread_id=new_msg.thread_id,
        user_id=new_msg.user_id,
        content=new_msg.content,
        created_at=new_msg.created_at,
        username=user.username,
        photoURL=user.photoURL
    )
    return response

# メッセージの添付ファイル対応
@fastapi_app.post("/message_attachments", response_model=MessageAttachment)
async def upload_attachment(
    message_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="ファイルが指定されていません")

        # MIMEタイプから attachment_type 判定
        content_type = file.content_type or "application/octet-stream"
        if content_type.startswith("image/"):
            attachment_type = AttachmentType.image
        elif content_type.startswith("audio/"):
            attachment_type = AttachmentType.voice
        elif content_type.startswith("video/"):
            attachment_type = AttachmentType.video
        else:
            attachment_type = AttachmentType.file

        # Azure Blob Storage にアップロード
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "message-attachments"  # ← こちらは、環境変数ではなく固定にしてます（適宜全体感と合わせて調整）

        if not connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage 接続情報が設定されていません")

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
        unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())
        blob_client = container_client.get_blob_client(unique_filename)

        content_settings = ContentSettings(content_type=content_type)
        file_data = await file.read()
        blob_client.upload_blob(file_data, overwrite=True, content_settings=content_settings)

        attachment_url = blob_client.url
        logger.info(f"ファイルをアップロードしました: {attachment_url}")

        # DBに保存
        attachment = MessageAttachment(
            message_id=message_id,
            attachment_type=attachment_type,
            attachment_url=attachment_url,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        return attachment

    except Exception as e:
        logger.error(f"添付ファイルアップロード失敗: {e}")
        raise HTTPException(status_code=500, detail=f"アップロードエラー: {e}")


#  起動ポイント変更
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
