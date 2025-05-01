import sys
import os
from pathlib import Path
from datetime import datetime

# 將 src 目錄加入 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import LYAPIClient
from src.database import Database

def update_bills():
    """更新法案資料"""
    client = LYAPIClient()
    db = Database()
    
    try:
        # 獲取資料庫中最新的屆期資料
        latest_in_db = db.get_latest_term_session()
        
        # 獲取當前最新的屆期資料
        current_term, current_session = client.get_current_term_session()
        
        print(f"資料庫中最新資料：{latest_in_db if latest_in_db else '無資料'}")
        print(f"立法院目前資料：第 {current_term} 屆 第 {current_session} 會期")
        
        # 如果資料庫為空，下載所有資料
        if not latest_in_db:
            print("資料庫為空，開始下載所有資料...")
            bills = client.get_all_bills()
            if bills:
                db.save_bills(bills)
                print(f"成功下載並儲存 {len(bills)} 筆資料")
        else:
            db_term, db_session = latest_in_db
            
            # 檢查是否需要更新
            if (current_term > db_term) or (current_term == db_term and current_session > db_session):
                print("發現新資料，開始更新...")
                new_bills = client.get_latest_bills(db_term, db_session)
                if new_bills:
                    db.save_bills(new_bills)
                    print(f"成功更新 {len(new_bills)} 筆新資料")
            else:
                print("資料庫已是最新狀態")
        
        # 顯示資料庫統計
        total_bills = db.get_bills_count()
        print(f"\n資料庫現有 {total_bills} 筆法案資料")
        
    finally:
        db.close()

if __name__ == "__main__":
    print(f"開始更新資料 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    update_bills()
    print(f"更新完成 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})") 