import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 從環境變數獲取資料庫連線字串
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bills.db')

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