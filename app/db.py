# app/db.py
import os
import urllib.parse
from os.path import join, exists, dirname
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# DB接続情報の取得
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "step4_team3_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
# パスワードのURLエンコード
encoded_password = urllib.parse.quote_plus(DB_PASS)

# ローカル環境とAzure環境で証明書パスを分岐
certificate_dir = join(dirname(__file__), "certificates")
cert_file = "DigiCertGlobalRootG2.crt.pem"
if exists(join(certificate_dir, cert_file)):
    CERT_PATH = join(certificate_dir, cert_file)
else:
    CERT_PATH = None

# SSL接続用のオプション設定（CERT_PATHが存在する場合のみ）
connect_args = {}
if CERT_PATH:
    connect_args["ssl"] = {"ca": CERT_PATH}  # pymysql用の設定

# ローカル環境かAzure環境かで接続URLを切り替え
def get_database_url():
    # 例として、ホストが127.0.0.1の場合はローカル接続
    if DB_HOST == "127.0.0.1":
        return f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        # Azure環境の場合、クエリパラメータでSSL設定を追加
        return f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca={CERT_PATH}&ssl_verify_cert=true"

DATABASE_URL = get_database_url()

# エンジン作成時にconnect_argsを渡す（CERT_PATHが存在する場合のみ有効）
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# セッションの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Baseクラスの定義
Base = declarative_base()
