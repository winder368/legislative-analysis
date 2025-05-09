import json
import logging
import time
import os
from datetime import datetime
from api_client import LYAPIClient
from database import Database

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("download_logs.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DownloadBills")

def ensure_data_dir():
    """確保資料目錄存在"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"已創建資料目錄: {data_dir}")
    return data_dir

def main():
    # 確保資料目錄存在
    data_dir = ensure_data_dir()
    
    # 初始化 API 客戶端和資料庫
    # 設置較長的超時時間和更多的重試次數
    client = LYAPIClient(timeout=60, max_retries=5, retry_delay=3)
    db = Database()
    
    start_time = time.time()
    logger.info("==========================================")
    logger.info("開始執行下載任務...")
    
    try:
        # 獲取資料庫中最新的屆別和會期
        latest_db_info = db.get_latest_term_session()
        
        # 嘗試先獲取總數
        total_count = client.get_total_bills_count()
        logger.info(f"API 總資料量估計: {total_count} 筆")
        
        if latest_db_info:
            term, session = latest_db_info
            logger.info(f"資料庫中最新的資料是第 {term} 屆第 {session} 會期")
            logger.info("開始獲取新資料...")
            
            try:
                # 使用新的逆序下載方法
                bills = client.get_latest_bills_reversed(term, session)
            except Exception as e:
                logger.error(f"獲取最新法案時發生錯誤: {str(e)}")
                # 嘗試使用較保守的參數重新連接
                logger.info("使用較保守的參數重試...")
                client = LYAPIClient(timeout=120, max_retries=3, retry_delay=10)
                bills = client.get_latest_bills_reversed(term, session)
        else:
            logger.info("資料庫為空，開始下載所有資料...")
            
            try:
                bills = client.get_all_bills()
            except Exception as e:
                logger.error(f"獲取所有法案時發生錯誤: {str(e)}")
                # 嘗試使用較保守的參數重新連接
                logger.info("使用較保守的參數重試...")
                client = LYAPIClient(timeout=120, max_retries=3, retry_delay=10)
                bills = client.get_all_bills()
        
        if not bills:
            logger.info("沒有新資料需要下載")
            return
            
        # 生成備份檔案名稱（包含時間戳）並儲存為 JSON 檔案作為備份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(data_dir, f"bills_backup_{timestamp}.json")

        logger.info(f"正在將資料備份到 {filename}...")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(bills, f, ensure_ascii=False, indent=2)

        # 將資料存入資料庫
        logger.info(f"正在將 {len(bills)} 筆資料存入資料庫...")
        db.save_bills(bills)
        
        # 顯示資料庫統計資訊
        total_bills = db.get_bills_count()
        elapsed_time = time.time() - start_time
        
        logger.info("\n下載完成！總耗時: {:.2f} 秒".format(elapsed_time))
        logger.info(f"本次新增 {len(bills)} 筆資料")
        logger.info(f"資料庫中目前共有 {total_bills} 筆法案資料")
        logger.info(f"資料備份已儲存至：{filename}")
        
        # 顯示資料庫中的屆別統計
        cursor = db.conn.cursor()
        cursor.execute("""
        SELECT term, COUNT(*) as count 
        FROM bills 
        GROUP BY term 
        ORDER BY CAST(term AS INTEGER) DESC
        """)
        logger.info("\n各屆別資料統計：")
        for row in cursor.fetchall():
            logger.info(f"第 {row['term']} 屆：{row['count']} 筆")
        
    except Exception as e:
        logger.error(f"發生錯誤：{str(e)}")
    finally:
        db.close()
        logger.info("下載任務結束")
        logger.info("==========================================")

if __name__ == "__main__":
    main() 