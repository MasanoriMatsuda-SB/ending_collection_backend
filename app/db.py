# app/db.py
import os
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
    connect_args["ssl"] = {"ca": CERT_PATH}

# MySQL用の接続文字列（pymysqlドライバを使用）
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# エンジン作成時にconnect_argsを渡す（SSL証明書が存在する場合のみ有効）
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# セッションの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Baseクラスの定義
Base = declarative_base()
