# app/main.py
import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.models import User
from app.schemas import UserCreate, UserOut, UserLogin, Token
from app.utils import get_password_hash, verify_password
from app.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.dependencies import get_db

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meme_mori_backend")

app = FastAPI()

# CORS 設定
origins = [
    "http://192.168.10.102:3000",  
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "https://tech0-techbrain-front-bhh0bjenh5caguch.francecentral-01.azurewebsites.net"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバル例外ハンドラーの追加
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    # 例外内容をJSONとして返す
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {exc}"}
    )

@app.get("/")
def read_root():
    return {"message": "Hello from meme mori backend!"}

# signup エンドポイント（フォームデータおよび画像アップロード対応）
@app.post("/signup", response_model=UserOut)
async def signup(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        # ユーザー重複チェック
        db_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ユーザー名またはメールアドレスは既に登録されています"
            )

        # 画像がアップロードされ、かつファイル名がある場合のみアップロード処理を実行
        photo_url = None
        if photo and photo.filename:
            try:
                connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                container_name = os.getenv("AZURE_CONTAINER_NAME")
                if not connection_string or not container_name:
                    raise HTTPException(status_code=500, detail="Azure Blob Storage の設定が不十分です")
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                container_client = blob_service_client.get_container_client(container_name)
                # ファイル名に拡張子があるかチェック
                if "." in photo.filename:
                    file_extension = photo.filename.split(".")[-1]
                    unique_filename = f"{uuid.uuid4()}.{file_extension}"
                else:
                    unique_filename = str(uuid.uuid4())
                blob_client = container_client.get_blob_client(unique_filename)
                content_settings = ContentSettings(content_type=photo.content_type)
                file_data = await photo.read()
                blob_client.upload_blob(file_data, overwrite=True, content_settings=content_settings)
                photo_url = blob_client.url
                logger.info(f"Image uploaded successfully: {photo_url}")
            except Exception as e:
                logger.error(f"Image upload failed: {e}")
                raise HTTPException(status_code=500, detail=f"画像アップロードに失敗しました: {e}")

        # ユーザー作成
        hashed_password = get_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            photoURL=photo_url
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    except Exception as e:
        logger.error(f"Signup failed: {e}")
        raise

# ログインエンドポイント（メールアドレスとパスワード）
@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報が無効です"
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
