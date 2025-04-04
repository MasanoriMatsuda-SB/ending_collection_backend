# app/utils.py
from passlib.context import CryptContext
from ultralytics import YOLO
import cv2
import numpy as np
from azure.storage.blob import BlobServiceClient, ContentSettings
import os
from typing import Dict
import logging
from dotenv import load_dotenv
from pathlib import Path

# 環境変数の読み込み
load_dotenv()

# ロガーの設定
logger = logging.getLogger(__name__)

# パスワードハッシュ化の設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """パスワードをハッシュ化"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワードの検証"""
    return pwd_context.verify(plain_password, hashed_password)

class ItemRecognitionService:
    """
    物品認識サービス
    - YOLOモデルによる物品認識
    - Azure Blob Storageへの画像アップロード
    """
    def __init__(self):
        try:
            # モデルのパスを設定
            base_dir = Path(__file__).resolve().parent
            model_path = base_dir / 'models' / 'yolov8n.pt'
            
            if not model_path.exists():
                logger.warning(f"Local model not found at {model_path}, attempting to use default model")
                self.model = YOLO('yolov8n.pt')
            else:
                logger.info(f"Loading model from: {model_path}")
                self.model = YOLO(str(model_path))
           
            # Azure Blob Storage クライアントの初期化
            connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not connection_string:
                raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set in environment variables")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
           
            # コンテナ名の取得
            self.container_name = os.getenv("AZURE_CONTAINER_NAME")
            if not self.container_name:
                raise ValueError("AZURE_CONTAINER_NAME is not set in environment variables")
               
            logger.info("ItemRecognitionService initialized successfully")
           
        except Exception as e:
            logger.error(f"Failed to initialize ItemRecognitionService: {e}")
            raise

    async def analyze_image(self, image_data: bytes) -> Dict:
        """
        画像を分析して物品を認識
        Args:
            image_data: 画像のバイトデータ
        Returns:
            Dict: 認識結果（物品名と確信度）
        """
        try:
            # 画像の検証
            if not validate_image(image_data):
                raise ValueError("Invalid image data")

            # 画像データをnumpy配列に変換
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
           
            # YOLOモデルで物体検出
            results = self.model(img)[0]
           
            # 検出結果の解析
            detections = []
            for r in results.boxes.data.tolist():
                x1, y1, x2, y2, score, class_id = r
                class_name = results.names[int(class_id)]
                detections.append({
                    'class_name': class_name,
                    'confidence': float(score)
                })
           
            # 最も確信度の高い検出結果を取得
            best_detection = max(detections, key=lambda x: x['confidence']) if detections else None
           
            return {
                'detected_name': best_detection['class_name'] if best_detection else "Unknown Item",
                'confidence': best_detection['confidence'] if best_detection else None
            }
           
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            raise

    async def upload_image(self, image_data: bytes, content_type: str = "image/jpeg") -> str:
        """
        画像をAzure Blob Storageにアップロード
        Args:
            image_data: 画像のバイトデータ
            content_type: 画像のMIMEタイプ
        Returns:
            str: アップロードされた画像のURL
        """
        try:
            # 画像の検証
            if not validate_image(image_data):
                raise ValueError("Invalid image data")


            # コンテナクライアントの取得
            container_client = self.blob_service_client.get_container_client(self.container_name)
           
            # ユニークなファイル名の生成
            blob_name = f"items/{os.urandom(16).hex()}.jpg"
            blob_client = container_client.get_blob_client(blob_name)
           
            # コンテンツ設定
            content_settings = ContentSettings(content_type=content_type)
           
            # アップロード
            blob_client.upload_blob(
                image_data,
                overwrite=True,
                content_settings=content_settings
            )
           
            logger.info(f"Image uploaded successfully: {blob_client.url}")
            return blob_client.url
           
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise

def validate_image(image_data: bytes) -> bool:
    """
    画像データの検証
    Args:
        image_data: 画像のバイトデータ
    Returns:
        bool: 有効な画像の場合True
    """
    try:
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img is not None and img.size > 0
    except Exception as e:
        logger.error(f"Image validation failed: {e}")
        return False