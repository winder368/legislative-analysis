from sqlalchemy import create_engine, text
from db_config import DATABASE_URL

def create_tables():
    """建立資料表"""
    engine = create_engine(DATABASE_URL)
    
    # 建立 bills 表格
    create_bills_table = """
    CREATE TABLE IF NOT EXISTS bills (
        id SERIAL PRIMARY KEY,
        term VARCHAR(10),
        billName TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(create_bills_table))
            conn.commit()
            print("資料表建立成功！")
    except Exception as e:
        print(f"建立資料表時發生錯誤：{str(e)}")

if __name__ == "__main__":
    create_tables() 