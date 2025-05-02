import json
from datetime import datetime
from api_client import LYAPIClient
from database import Database

def main():
    # 初始化 API 客戶端和資料庫
    client = LYAPIClient()
    db = Database()
    
    try:
        # 獲取資料庫中最新的屆別和會期
        latest_db_info = db.get_latest_term_session()
        
        if latest_db_info:
            term, session = latest_db_info
            print(f"資料庫中最新的資料是第 {term} 屆第 {session} 會期")
            print("開始獲取新資料...")
            bills = client.get_latest_bills(term, session)
        else:
            print("資料庫為空，開始下載所有資料...")
            bills = client.get_all_bills()
        
        if not bills:
            print("沒有新資料需要下載")
            return
            
        # 生成備份檔案名稱（包含時間戳）並儲存為 JSON 檔案作為備份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/bills_backup_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(bills, f, ensure_ascii=False, indent=2)

        # 將資料存入資料庫
        print(f"正在將 {len(bills)} 筆資料存入資料庫...")
        db.save_bills(bills)
        
        # 顯示資料庫統計資訊
        total_bills = db.get_bills_count()
        print(f"\n下載完成！")
        print(f"本次新增 {len(bills)} 筆資料")
        print(f"資料庫中目前共有 {total_bills} 筆法案資料")
        print(f"資料備份已儲存至：{filename}")
        
        # 顯示資料庫中的屆別統計
        cursor = db.conn.cursor()
        cursor.execute("""
        SELECT term, COUNT(*) as count 
        FROM bills 
        GROUP BY term 
        ORDER BY CAST(term AS INTEGER) DESC
        """)
        print("\n各屆別資料統計：")
        for row in cursor.fetchall():
            print(f"第 {row['term']} 屆：{row['count']} 筆")
        
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main() 