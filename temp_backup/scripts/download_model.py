import os
from pathlib import Path
from ultralytics import YOLO


def download_model():
    # モデルを保存するディレクトリのパスを設定
    base_dir = Path(__file__).resolve().parent.parent
    models_dir = base_dir / 'app' / 'models'
    
    # ディレクトリが存在しない場合は作成
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # モデルのダウンロードと保存
    model_path = models_dir / 'yolov8n.pt'
    if not model_path.exists():
        print(f"Downloading YOLOv8n model to {model_path}")
        model = YOLO('yolov8n.pt')
        # モデルファイルをコピー
        import shutil
        cache_dir = Path.home() / '.cache' / 'ultralytics'
        source_path = cache_dir / 'models' / 'yolov8n.pt'
        shutil.copy(source_path, model_path)
        print("Model downloaded successfully")
    else:
        print("Model already exists")


if __name__ == "__main__":
    download_model()