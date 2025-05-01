import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse

# 從環境變數獲取資料庫連線字串
DATABASE_URL = os.getenv('DATABASE_URL')

# 處理 Postgres 連線字串
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# 如果沒有設定環境變數，使用 SQLite（用於本地開發）
if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///bills.db'

# 建立資料庫引擎
engine = create_engine(DATABASE_URL)

# 建立 Session 工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """獲取資料庫連線"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 