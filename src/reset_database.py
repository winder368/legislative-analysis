import os
from database import Database

def main():
    db_path = "data/bills.db"
    
    # 關閉現有的資料庫連接
    try:
        db = Database()
        db.close()
    except:
        pass
    
    # 刪除現有的資料庫檔案
    if os.path.exists(db_path):
        print(f"刪除現有的資料庫檔案: {db_path}")
        os.remove(db_path)
    
    # 重新建立資料庫
    print("重新建立資料庫...")
    db = Database()
    db.close()
    
    # 確認資料庫狀態
    db = Database()
    count = db.get_bills_count()
    print(f"新資料庫中的資料數量: {count} 筆")
    db.close()

if __name__ == "__main__":
    main() 