import os
import uuid
import logging
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.storage.blob import BlobServiceClient, ContentSettings
from typing import List

from app.models import User, Thread, Message, MessageAttachment, Category, Item, ItemImage
from app.schemas import (
    UserCreate, UserOut, UserLogin, Token,
    MessageCreate, MessageResponse, AttachmentType, 
    MessageAttachmentBase, MessageAttachmentCreate, 
    MessageAttachment as MessageAttachmentSchema,
    MessageReaction, MessageReactionCreate,
    CategoryResponse, ItemCreate, ItemResponse, ItemUpdate,
    ConditionRank, ImageAnalysisResponse
)
from app.utils import (
    get_password_hash, 
    verify_password,
    ItemRecognitionService
)
from app.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_db
from app.crud import (
    create_message, get_messages, delete_message, 
    create_reaction, get_reactions_by_message, delete_reaction,
    get_categories, create_item, get_item,
    get_user_items, get_group_items, update_item,
    delete_item
)
import socketio

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meme_mori_backend")

# Socket.IO サーバー作成
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
fastapi_app = FastAPI()
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

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

# ItemRecognitionService のインスタンス作成
item_recognition_service = ItemRecognitionService()

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

@sio.on("add_reaction")
async def handle_add_reaction(sid, data):
    logger.info(f"リアクション追加: {data}")
    await sio.emit("reaction_added", data)

@sio.on("remove_reaction")
async def handle_remove_reaction(sid, data):
    logger.info(f"リアクション削除: {data}")
    await sio.emit("reaction_removed", data)

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
        # 名前の重複は除外してよさそう
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

## モックサーバー
## 仮のグループ作成エンドポイント（モック）
#@app.post("/grouping")
#async def mock_create_group(payload: GroupCreate):
    #group_name = payload.groupName
    #return {"message": f"グループ '{group_name}' を作成しました"}

# item_id → thread_id
@fastapi_app.get("/threads/by-item/{item_id}")
def get_thread_by_item(item_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.item_id == item_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread.thread_id}

# メッセージ取得
@fastapi_app.get("/messages", response_model=List[MessageResponse])
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
            parent_message_id=m.parent_message_id
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

# メッセージ添付ファイル対応
@fastapi_app.post("/message_attachments", response_model=MessageAttachmentSchema)
async def upload_attachment(
    message_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="ファイルが指定されていません")

        content_type = file.content_type or "application/octet-stream"
        if content_type.startswith("image/"):
            attachment_type = AttachmentType.image
        elif content_type.startswith("audio/"):
            attachment_type = AttachmentType.voice
        elif content_type.startswith("video/"):
            attachment_type = AttachmentType.video
        else:
            attachment_type = AttachmentType.file

        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "message-attachments"
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

        attachment = MessageAttachment(
            message_id=message_id,
            attachment_type=attachment_type,
            attachment_url=attachment_url,
        )
        try:
            db.add(attachment)
            db.commit()
            db.refresh(attachment)
            logger.info(f"DB登録成功: attachment_id={attachment.attachment_id}")
        except Exception as db_err:
            logger.error(f"DB保存中にエラー: {db_err}")
            raise HTTPException(status_code=500, detail=f"DB保存に失敗しました: {db_err}")

        return attachment

    except Exception as e:
        logger.error(f"添付ファイルアップロード失敗: {e}")
        raise HTTPException(status_code=500, detail=f"アップロードエラー: {e}")

@fastapi_app.get("/attachments/by-message/{message_id}", response_model=List[MessageAttachmentSchema])
def get_attachments_by_message_id(message_id: int, db: Session = Depends(get_db)):
    attachments = (
        db.query(MessageAttachment)
        .filter(MessageAttachment.message_id == message_id)
        .order_by(MessageAttachment.uploaded_at)
        .all()
    )
    return attachments

@fastapi_app.delete("/messages/{message_id}")
def delete_message_endpoint(message_id: int, db: Session = Depends(get_db)):
    message = delete_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"detail": "Message deleted"}

# ====== Chat リアクション対応 ======
@fastapi_app.post("/reactions", response_model=MessageReaction)
def add_reaction(
    reaction: MessageReactionCreate,
    db: Session = Depends(get_db)
):
    return create_reaction(db, reaction)

@fastapi_app.get("/reactions/{message_id}", response_model=List[MessageReaction])
def get_reactions(message_id: int, db: Session = Depends(get_db)):
    return get_reactions_by_message(db, message_id)

@fastapi_app.delete("/reactions")
def remove_reaction(
    message_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    delete_reaction(db, message_id, user_id)
    return {"message": "Reaction removed"}

# ====== Item関連エンドポイント ======
@fastapi_app.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: Session = Depends(get_db)):
    """カテゴリー一覧を取得"""
    return get_categories(db)

@fastapi_app.post("/items/analyze")
async def analyze_item_image(
    image: UploadFile = File(...)
) -> ImageAnalysisResponse:
    """画像を分析して物品名を認識"""
    try:
        image_data = await image.read()
        result = await item_recognition_service.analyze_image(image_data)
        return ImageAnalysisResponse(**result)
    except Exception as e:
        logger.error(f"画像分析に失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.post("/items", response_model=ItemResponse)
async def create_new_item(
    image: UploadFile = File(...),
    item_name: str = Form(...),
    group_id: int = Form(...),
    category_id: int = Form(...),
    condition_rank: ConditionRank = Form(...),
    description: str = Form(...),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """物品を登録"""
    try:
        # 画像のアップロード
        image_data = await image.read()
        image_url = await item_recognition_service.upload_image(image_data)

        # 物品情報の作成
        item_data = ItemCreate(
            item_name=item_name,
            group_id=group_id,
            category_id=category_id,
            condition_rank=condition_rank,
            description=description
        )

        # データベースに保存。create_item 関数内部で ItemImage レコードも作成される前提。
        db_item = create_item(db, user_id, item_data, image_url)
        
        # レスポンスの作成（全必須フィールドを含める）
        return ItemResponse(
            item_id=db_item.item_id,
            user_id=db_item.user_id,
            group_id=db_item.group_id,
            item_name=db_item.item_name,
            category_id=db_item.category_id,
            category_name=db_item.category.category_name if db_item.category else "",
            condition_rank=db_item.condition_rank,
            description=db_item.description,
            status=db_item.status,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
            images=[{
                "image_id": img.image_id,
                "image_url": img.image_url,
                "uploaded_at": img.uploaded_at
            } for img in db_item.images],
            detection_confidence=getattr(db_item, "detection_confidence", None)
        )

    except Exception as e:
        logger.error(f"物品登録に失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item_by_id(item_id: int, db: Session = Depends(get_db)):
    """物品の詳細を取得"""
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    # GET エンドポイントでも必要なフィールドを明示的に返す
    return ItemResponse(
        item_id=item.item_id,
        user_id=item.user_id,
        group_id=item.group_id,
        item_name=item.item_name,
        category_id=item.category_id,
        category_name=item.category.category_name if item.category else "",
        condition_rank=item.condition_rank,
        description=item.description,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
        images=[{
            "image_id": img.image_id,
            "image_url": img.image_url,
            "uploaded_at": img.uploaded_at
        } for img in item.images],
        detection_confidence=getattr(item, "detection_confidence", None)
    )

@fastapi_app.get("/items/user/{user_id}", response_model=List[ItemResponse])
async def list_user_items(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """ユーザーの物品一覧を取得"""
    items = get_user_items(db, user_id, skip, limit)
    return [
        ItemResponse(
            item_id=item.item_id,
            user_id=item.user_id,
            group_id=item.group_id,
            item_name=item.item_name,
            category_id=item.category_id,
            category_name=item.category.category_name if item.category else "",
            condition_rank=item.condition_rank,
            description=item.description,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            images=[{
                "image_id": img.image_id,
                "image_url": img.image_url,
                "uploaded_at": img.uploaded_at
            } for img in item.images],
            detection_confidence=getattr(item, "detection_confidence", None)
        )
        for item in items
    ]

@fastapi_app.get("/items/group/{group_id}", response_model=List[ItemResponse])
async def list_group_items(
    group_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """グループの物品一覧を取得"""
    items = get_group_items(db, group_id, skip, limit)
    return [
        ItemResponse(
            item_id=item.item_id,
            user_id=item.user_id,
            group_id=item.group_id,
            item_name=item.item_name,
            category_id=item.category_id,
            category_name=item.category.category_name if item.category else "",
            condition_rank=item.condition_rank,
            description=item.description,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            images=[{
                "image_id": img.image_id,
                "image_url": img.image_url,
                "uploaded_at": img.uploaded_at
            } for img in item.images],
            detection_confidence=getattr(item, "detection_confidence", None)
        )
        for item in items
    ]

@fastapi_app.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item_by_id(item_id: int, item_data: ItemUpdate, db: Session = Depends(get_db)):
    """物品情報を更新"""
    updated_item = update_item(db, item_id, item_data)
    if not updated_item:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated_item

@fastapi_app.delete("/items/{item_id}")
async def delete_item_by_id(item_id: int, db: Session = Depends(get_db)):
    """物品を削除"""
    success = delete_item(db, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"detail": "Item successfully deleted"}

# ====== Chat リアクション対応 ======
@fastapi_app.post("/reactions", response_model=MessageReaction)
def add_reaction(reaction: MessageReactionCreate, db: Session = Depends(get_db)):
    return create_reaction(db, reaction)

@fastapi_app.get("/reactions/{message_id}", response_model=List[MessageReaction])
def get_reactions(message_id: int, db: Session = Depends(get_db)):
    return get_reactions_by_message(db, message_id)

@fastapi_app.delete("/reactions")
def remove_reaction(message_id: int, user_id: int, db: Session = Depends(get_db)):
    delete_reaction(db, message_id, user_id)
    return {"message": "Reaction removed"}

# ====== 起動ポイント ======
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
