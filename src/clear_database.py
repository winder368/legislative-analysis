from database import Database
import os

def main():
    db = Database()
    try:
        # 顯示清除前的資料數量
        count_before = db.get_bills_count()
        print(f"清除前資料庫中有 {count_before} 筆資料")
        
        # 清除資料
        print("開始清除資料...")
        db.clear_all_data()
        
        # 顯示清除後的資料數量
        count_after = db.get_bills_count()
        print(f"清除後資料庫中有 {count_after} 筆資料")
        
        # 檢查資料庫檔案
        db_path = "data/bills.db"
        if os.path.exists(db_path):
            print(f"資料庫檔案大小: {os.path.getsize(db_path)} 位元組")
            
        # 再次確認資料是否真的被清除
        if count_after > 0:
            print("警告：資料似乎沒有被完全清除！")
            print("嘗試使用更強力的清除方式...")
            cursor = db.conn.cursor()
            cursor.execute("DELETE FROM bills")
            cursor.execute("VACUUM")  # 重新整理資料庫檔案
            db.conn.commit()
            
            # 最後一次檢查
            final_count = db.get_bills_count()
            print(f"最終資料數量: {final_count} 筆")
            
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main() 