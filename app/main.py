import os
import uuid
import logging
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from azure.storage.blob import BlobServiceClient, ContentSettings
from typing import List

from app.models import User, Thread, Message, MessageAttachment, Category, Item, ItemImage, ReferenceItems, ReferenceMarketItem, MessageReaction, FamilyGroup, UserFamilyGroup
from app.schemas import (
    UserCreate, UserOut, UserLogin, Token,
    MessageCreate, MessageResponse, AttachmentType, 
    MessageAttachmentBase, MessageAttachmentCreate, 
    MessageAttachment as MessageAttachmentSchema,
    MessageReaction as MessageReactionSchema, MessageReactionCreate, ThreadCreate,
    CategoryResponse, ItemCreate, ItemResponse, ItemUpdate,
    ConditionRank, ImageAnalysisResponse,
    ItemImageResponse, ItemWithUsername, ReferenceItemsResponse, MarketPriceList,
    GroupResponse
)
from app.utils import (
    get_password_hash, 
    verify_password,
    validate_image,
    ItemRecognitionService
)
from app.auth import create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_db
from app.crud import (
    create_message, get_messages, delete_message, 
    create_reaction, get_reactions_by_message, delete_reaction, create_thread, get_messages_by_item_id,
    get_categories, create_item, get_item,
    get_user_items, get_group_items, update_item,
    delete_item
)
import socketio

# RAG用
from app.rag_utils import chat_llm_summarize, index_messages_for_item, search_chat_vector

from openai import AzureOpenAI
import base64
from fastapi import Body
from fastapi.responses import StreamingResponse
import httpx

# Azure OpenAI の設定
client = AzureOpenAI(
  api_key = os.getenv("AZURE_OPENAI_KEY"),  
  api_version = "2024-03-01-preview",
  azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
)

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

@sio.event
async def new_attachment(sid, data):
    logger.info(f"添付ファイル通知: {data}")
    await sio.emit("new_attachment", data)

@sio.on("delete_message")
async def handle_delete_message(sid, data):
    logger.info(f"🗑 メッセージ削除: {data}")
    await sio.emit("delete_message", data)

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

# ====== Grouping（Start） ======
# JWT認証情報からuser_idを取得し、request.state.userに埋め込む
@fastapi_app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    token = request.headers.get("Authorization") # ヘッダーから Authorization を取得
    if token and token.startswith("Bearer "):
        try:
            token_data = decode_access_token(token[7:])  # Authorization: Bearer <JWTトークン>から"Bearer "除去
            request.state.user = token_data  # request.state.user["user_id"] で使える
            logger.info(f"✅ user_id: {token_data.get('user_id')}")
        except Exception as e:
            logger.warning(f"トークンの解析に失敗しました: {e}")
    return await call_next(request) # 次の処理（通常のエンドポイント関数）に制御を渡す

# Group新規作成エンドポイント
@fastapi_app.post("/grouping")
def create_group(
    groupName: str = Body(..., embed=True), # グループ名を受け取る。embed=Trueは"groupName" のキーを期待
    db: Session = Depends(get_db),
    request: Request = None  # 認証情報からuser_idを取得する
):
    try:
        if not hasattr(request.state, "user"):
            raise HTTPException(status_code=401, detail="認証情報が見つかりません（ミドルウェア未通過）")
        
        # 認証済みユーザーの取得（JWTから）「誰がグループを作成したか」をDBに記録
        token_data = request.state.user  # middlewareエンドポイント
        user_id = token_data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="トークンに user_id が含まれていません")

        # family_groups に追加
        new_group = FamilyGroup(group_name=groupName)
        db.add(new_group)
        db.commit()
        db.refresh(new_group)

        # user_family_groups に作成者を追加。role: poster（投稿者という役割を記録）
        user_group = UserFamilyGroup(user_id=user_id, group_id=new_group.group_id, role="poster")
        db.add(user_group)
        db.commit()

        return {
            "message": "グループ作成に成功しました",
            "group_id": new_group.group_id,
            "group_name": new_group.group_name
        }

    except Exception as e:
        logger.warning(f"認証または処理エラー: {e.detail}")# 401などの明示的なHTTPエラーはそのまま返す
        raise e
    except Exception as e:
        logger.error(f"グループ作成失敗: {e}")
        raise HTTPException(status_code=500, detail="グループ作成中にエラーが発生しました")

# ====== Grouping（end） ======


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


# ====== Chat リアクション対応（Start） ====== 
@fastapi_app.post("/reactions", response_model=MessageReactionSchema)
def add_reaction(
    reaction: MessageReactionCreate,
    db: Session = Depends(get_db)
):
    return create_reaction(db, reaction)

#2504201941追加
@fastapi_app.get("/reactions/batch/by-message-ids")
def get_reactions_batch(ids: str = Query(...), db: Session = Depends(get_db)):
    id_list = [int(i) for i in ids.split(",") if i.isdigit()]
    results = {message_id: get_reactions_by_message(db, message_id) for message_id in id_list}
    return results

@fastapi_app.get("/reactions/{message_id}", response_model=List[MessageReactionSchema])
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
# ====== Chat リアクション対応（EndEnd） ====== 

# ====== Thread作成エンドポイント（Start） ====== 
@fastapi_app.post("/threads")
def create_new_thread(thread: ThreadCreate, db: Session = Depends(get_db)):
    try:
        new_thread = create_thread(db, thread)
        return {"thread_id": new_thread.thread_id}
    except Exception as e:
        logger.error(f"スレッド作成失敗: {e}")
        raise HTTPException(status_code=500, detail="スレッド作成中にエラーが発生しました")
# ====== Thread作成エンドポイント（End） ====== 


# ====== RAG関連エンドポイント（Start） ====== 
@fastapi_app.get("/rag/summary/{item_id}")
def get_summary(item_id: str, db: Session = Depends(get_db)):
    messages = get_messages_by_item_id(db, item_id)
    text = "\n".join([m.content for m in messages])
    summary = chat_llm_summarize(text)  # LLM API 連携関数
    return {"summary": summary}

# Step5 - ベクトル登録 & 検索エンドポイント
@fastapi_app.post("/rag/index/{item_id}")
def index_for_item(item_id: str, db: Session = Depends(get_db)):
    index_messages_for_item(db, item_id)
    return {"message": "インデックス作成完了"}

@fastapi_app.get("/rag/vector_search/{item_id}")
def vector_search_chat(item_id: str, query: str):
    results = search_chat_vector(item_id, query)
    return {"results": results}

# ====== RAG関連エンドポイント（End） ====== 

# ====== Chat 関連（End） ============================================================

# ====== Item関連エンドポイント ======
@fastapi_app.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: Session = Depends(get_db)):
    """カテゴリー一覧を取得"""
    return get_categories(db)

@fastapi_app.post("/items/openai_analyze", response_model=ImageAnalysisResponse)
async def openai_analyze_item_image(image: UploadFile = File(...)) -> ImageAnalysisResponse:
    try:
        # アップロードされた画像データを読み込み
        image_data = await image.read()
        # 画像データをBase64にエンコードし、Data URL形式に変換する
        base64_encoded = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{image.content_type};base64,{base64_encoded}"
        
        # 画像を表す辞書（OpenAIのマルチモーダル入力形式）を作成
        image_dict = {
            "type": "image_url",
            "image_url": {
                "url": data_url,
                "detail": "high"
            }
        }
        
        # リクエストメッセージを構築
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "あなたは商品名識別の専門家です。"}]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "画像に最も大きく写っている物の具体的な商品名を提示ください。商品名のみを回答ください。例：大神 (OKAMI) オリジナル・サウンドトラック"},
                    image_dict
                ]
            }
        ]
        
        # チャットコンプリーションを呼び出す
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
        )
        
        detected_name = response.choices[0].message.content.strip()
        result = {"detected_name": detected_name, "confidence": None}
        return ImageAnalysisResponse(**result)
    
    except Exception as e:
        logger.error(f"Azure OpenAI 画像解析に失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 
@fastapi_app.post("/items/openai_analyze_batch")
async def openai_analyze_batch(image_urls: List[str] = Body(...)) -> List[dict]:
    
    results = []
    for url in image_urls:
        try:
            # 画像URLから画像データを取得
            async with httpx.AsyncClient() as client_http:
                resp = await client_http.get(url)
                resp.raise_for_status()
            image_data = resp.content
            # Base64エンコードしてData URL形式に変換（画像のMIMEタイプはここでは "image/jpeg" と仮定）
            base64_encoded = base64.b64encode(image_data).decode("utf-8")
            data_url = f"data:image/jpeg;base64,{base64_encoded}"
            # OpenAI用の画像入力形式の辞書を作成
            image_dict = {
                "type": "image_url",
                "image_url": {
                    "url": data_url,
                    "detail": "high"
                }
            }
            # リクエストメッセージを構築
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "あなたは商品名識別の専門家です。"}]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "画像に最も大きく写っている物の具体的な商品名を、商品名のみで回答してください。"
                        },
                        image_dict
                    ]
                }
            ]
            # Azure OpenAI Service のチャットAPIを呼び出し
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Azure OpenAI Serviceにデプロイしているモデルの名前に置き換えてください
                messages=messages,
                max_tokens=10,
            )
            detected_name = response.choices[0].message.content.strip()
            results.append({
                "image_url": url,
                "detected_name": detected_name
            })
        except Exception as e:
            logger.error(f"Azure OpenAI バッチ解析に失敗 (URL: {url}): {e}")
            results.append({
                "image_url": url,
                "detected_name": "解析失敗"
            })
    return results

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

@fastapi_app.post("/items/yolo_detect")
async def yolo_detect(image: UploadFile = File(...)) -> List[dict]:
    """
    アップロードされた画像からYOLOによる物体検出を行い、
    各検出領域を切り出してAzure Blob StorageにアップロードしたURLなどを返すエンドポイント。
    """
    try:
        # アップロードされた画像データを読み込む
        image_data = await image.read()
        
        # 画像データの検証（utils.py の validate_image 関数を利用する例）
        if not validate_image(image_data):
            raise HTTPException(status_code=400, detail="画像データが不正です")
        
        # 画像データをNumPy配列に変換し、OpenCVで画像をデコード
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # YOLOモデルで検出を実行（ItemRecognitionServiceのmodelを利用）
        results = item_recognition_service.model(img)[0]
        
        detections = []
        idx = 1
        # 検出結果のボックス情報の一覧を取得
        for r in results.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = r
            # 座標を整数に変換
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            # 切り出し（元画像が十分大きいことを前提とする）
            cropped = img[y1:y2, x1:x2]
            # 切り出した画像をJPEG形式でエンコード
            ret, buf = cv2.imencode(".jpg", cropped)
            if not ret:
                continue
            cropped_bytes = buf.tobytes()
            # Azure Blob Storageに切り出し画像をアップロード（upload_imageメソッドを利用）
            crop_url = await item_recognition_service.upload_image(cropped_bytes, content_type="image/jpeg")
            # 検出結果にID、URL、クラス名、信頼度を付与してリストに追加
            detections.append({
                "id": idx,
                "crop_image_url": crop_url,
                "class_name": results.names[int(class_id)],
                "confidence": float(score)
            })
            idx += 1
        
        return detections

    except Exception as e:
        logger.error(f"YOLO検出に失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.get("/proxy_image")
async def proxy_image(url: str = Query(...)):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="画像取得に失敗しました")
        return StreamingResponse(iter([response.content]), media_type=response.headers.get("content-type", "application/octet-stream"))
    except Exception as e:
        logger.error(f"Proxy image fetch failed: {e}")
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

# ====== アイテム詳細画面（Start） ======
# ItemDetail.tsx対応（パス変更後）
@fastapi_app.get("/items/detail/{item_id}", response_model=ItemWithUsername)
def get_item_with_username(item_id: int, db: Session = Depends(get_db)):
    result = (
        db.query(Item, User.username)
        .join(User, Item.user_id == User.user_id)
        .filter(Item.item_id == item_id)
        .first()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item_obj, username = result

    return ItemWithUsername(
        item_id=item_obj.item_id,
        user_id=item_obj.user_id,
        group_id=item_obj.group_id,
        item_name=item_obj.item_name,
        description=item_obj.description,
        ref_item_id=item_obj.ref_item_id,
        category_id=item_obj.category_id,
        category_name=item_obj.category.category_name if item_obj.category else "",
        condition_rank=item_obj.condition_rank,
        status=item_obj.status,
        created_at=item_obj.created_at,
        updated_at=item_obj.updated_at,
        images=[
            {
                "image_id": img.image_id,
                "image_url": img.image_url,
                "uploaded_at": img.uploaded_at
            }
            for img in item_obj.images or []  # None安全
        ],
        username=username
    )

# ItemDetail.tsx(reference_items)対応
@fastapi_app.get("/reference-items/{ref_item_id}", response_model=ReferenceItemsResponse)
def get_reference_item(ref_item_id: int, db: Session = Depends(get_db)):
    ref_item = db.query(ReferenceItems).filter(ReferenceItems.ref_item_id == ref_item_id).first()
    if not ref_item:
        raise HTTPException(status_code=404, detail="Reference item not found")
    return ref_item


# ending_collection_frontend-main\src\app\item\[id]\page.tsxへ画像表示対応
@fastapi_app.get("/item-images/{item_id}", response_model=List[ItemImageResponse])
def get_item_images(item_id: int, db: Session = Depends(get_db)):
    images = db.query(ItemImage).filter(ItemImage.item_id == item_id).all()
    return images

# ending_collection_frontend-main\src\app\item\[id]\page.tsx user_id ごとの item_id 一覧API を作成
@fastapi_app.get("/users/{user_id}/item-ids", response_model=List[int])
def get_item_ids_by_user(user_id: int, db: Session = Depends(get_db)):
    item_ids = (
        db.query(Item.item_id)
        .filter(Item.user_id == user_id)
        .order_by(Item.item_id)
        .all()
    )
    return [item_id for (item_id,) in item_ids]

# ItemDetail.tsx(価格推定)対応
@fastapi_app.get("/reference-market-items", response_model=MarketPriceList)
def get_market_prices(
    ref_item_id: int = Query(...),
    condition_rank: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(ReferenceMarketItem.market_price).filter(ReferenceMarketItem.ref_item_id == ref_item_id)

    if condition_rank and condition_rank != "全て":
        query = query.filter(ReferenceMarketItem.condition_rank == condition_rank)
    elif condition_rank == "全て":
        query = query.filter((ReferenceMarketItem.condition_rank == None) | (ReferenceMarketItem.condition_rank.in_(['S', 'A', 'B', 'C', 'D'])))

    prices = [p[0] for p in query.all()]
    return {"market_prices": prices}
# ====== アイテム詳細画面（End） ======


# ====== メルカリスクレイピング（start） ======


# ====== メルカリスクレイピング（end） ======

# ====== ホーム app/page.tsx（start） ======

@fastapi_app.get("/users/{user_id}/groups", response_model=List[GroupResponse])
def get_user_groups(user_id: int, db: Session = Depends(get_db)):
    user_groups = (
        db.query(UserFamilyGroup.group_id, FamilyGroup.group_name)
        .join(FamilyGroup, UserFamilyGroup.group_id == FamilyGroup.group_id)
        .filter(UserFamilyGroup.user_id == user_id)
        .all()
    )
    return [{"group_id": gid, "group_name": name} for gid, name in user_groups]


# メッセージの新しい順に並び替
@fastapi_app.get("/items/group/{group_id}/with-latest-message")
def get_items_with_latest_message(group_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func

    subquery = (
        db.query(Message.thread_id, func.max(Message.updated_at).label("latest"))
        .group_by(Message.thread_id)
        .subquery()
    )

    results = (
        db.query(Item, subquery.c.latest)
        .outerjoin(Thread, Item.item_id == Thread.item_id)
        .outerjoin(subquery, Thread.thread_id == subquery.c.thread_id)
        .filter(Item.group_id == group_id)
        .all()
    )

    response = []
    for item, latest in results:
        response.append({
            "item_id": item.item_id,
            "item_name": item.item_name,
            "updated_at": item.updated_at,
            "images": [{"image_url": img.image_url} for img in item.images],
            "latest_message_time": latest
        })

    return response

# メッセージの検索
@fastapi_app.get("/group-messages/{group_id}")
def get_messages_for_group(group_id: int, db: Session = Depends(get_db)):
    """group_idに属するitemに紐づくmessage contentのみを返す"""
    results = (
        db.query(Message.thread_id, Message.content)
        .join(Thread, Message.thread_id == Thread.thread_id)
        .join(Item, Thread.item_id == Item.item_id)
        .filter(Item.group_id == group_id)
        .all()
    )
    return [{"thread_id": t_id, "content": content} for t_id, content in results]
# ====== ホーム app/page.tsx（end） ======


#  起動ポイント変更

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
