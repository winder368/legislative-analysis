import json
import logging
import time
import os
import sys
import sqlite3
from datetime import datetime
from api_client import LYAPIClient
from database import Database

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("reset_download_logs.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ResetAndDownload")

def ensure_data_dir():
    """確保資料目錄存在"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"已創建資料目錄: {data_dir}")
        
    # 確保備份子目錄存在
    backup_dir = os.path.join(data_dir, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        logger.info(f"已創建備份目錄: {backup_dir}")
        
    # 確保資料庫備份子目錄存在
    db_backup_dir = os.path.join(backup_dir, 'database')
    if not os.path.exists(db_backup_dir):
        os.makedirs(db_backup_dir)
        logger.info(f"已創建資料庫備份目錄: {db_backup_dir}")
        
    # 確保頁面備份子目錄存在
    page_backup_dir = os.path.join(backup_dir, 'pages')
    if not os.path.exists(page_backup_dir):
        os.makedirs(page_backup_dir)
        logger.info(f"已創建頁面備份目錄: {page_backup_dir}")
        
    return data_dir

def get_backup_dir():
    """獲取備份目錄路徑"""
    data_dir = ensure_data_dir()
    backup_dir = os.path.join(data_dir, 'backups')
    return backup_dir

def get_db_backup_dir():
    """獲取資料庫備份目錄路徑"""
    backup_dir = get_backup_dir()
    db_backup_dir = os.path.join(backup_dir, 'database')
    return db_backup_dir

def get_page_backup_dir():
    """獲取頁面備份目錄路徑"""
    backup_dir = get_backup_dir()
    page_backup_dir = os.path.join(backup_dir, 'pages')
    return page_backup_dir

def reset_database():
    """重置資料庫"""
    logger.info("開始重置資料庫...")
    db = Database()
    try:
        # 先備份資料庫
        backup_db_path = backup_database()
        if backup_db_path:
            logger.info(f"資料庫已成功備份至 {backup_db_path}")
        
        # 先關閉資料庫連接
        db.close()
        
        # 獲取資料庫路徑
        data_dir = ensure_data_dir()
        db_path = os.path.join(data_dir, 'bills.db')
        
        # 嘗試刪除資料庫文件
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info(f"已刪除舊資料庫文件 {db_path}")
        except Exception as e:
            logger.error(f"刪除資料庫文件時發生錯誤: {str(e)}")
            return False
        
        # 重新初始化資料庫
        db = Database()
        logger.info("已重新創建資料表")
        
        return True
    except Exception as e:
        logger.error(f"重置資料庫時發生錯誤: {str(e)}")
        return False
    finally:
        db.close()

def backup_database():
    """備份資料庫"""
    try:
        # 獲取資料庫路徑
        data_dir = ensure_data_dir()
        db_path = os.path.join(data_dir, 'bills.db')
        
        # 如果資料庫不存在則跳過備份
        if not os.path.exists(db_path):
            logger.info("資料庫尚未創建，跳過備份")
            return None
        
        # 創建備份文件名稱
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_backup_dir = get_db_backup_dir()
        backup_path = os.path.join(db_backup_dir, f"bills_backup_{timestamp}.db")
        
        # 複製資料庫文件
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"已將資料庫備份至: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"備份資料庫時發生錯誤: {str(e)}")
        return None

def download_all_bills_with_page():
    """下載所有法案並記錄頁碼"""
    logger.info("開始下載所有法案資料...")
    
    # 初始化客戶端和資料庫
    client = LYAPIClient(timeout=60, max_retries=5, retry_delay=3)
    db = Database()
    
    start_time = time.time()
    total_bills = 0
    max_pages_to_check = 100  # 最多檢查的頁數
    
    try:
        # 估計總頁數
        estimated_total = client.get_total_bills_count()
        if estimated_total > 0:
            max_pages_to_check = min(max_pages_to_check, (estimated_total // 1000) + 5)
        
        logger.info(f"預計檢查 {max_pages_to_check} 頁資料")
        
        # 逐頁下載資料
        for page in range(1, max_pages_to_check + 1):
            logger.info(f"正在下載第 {page}/{max_pages_to_check} 頁...")
            
            try:
                bills = client.get_bills(term="all", page=page)
                
                if not bills:
                    logger.info(f"第 {page} 頁沒有資料，下載結束")
                    break
                
                logger.info(f"成功獲取第 {page} 頁資料，共 {len(bills)} 筆")
                
                # 備份頁面數據
                page_backup_dir = get_page_backup_dir()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"page_{page}_{timestamp}.json"
                backup_path = os.path.join(page_backup_dir, backup_filename)
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(bills, f, ensure_ascii=False, indent=2)
                logger.info(f"已將第 {page} 頁資料備份至: {backup_path}")
                
                # 儲存資料，並記錄頁碼
                db.save_bills(bills, page_number=page)
                total_bills += len(bills)
                
                # 每 10 頁顯示一次進度
                if page % 10 == 0:
                    elapsed_time = time.time() - start_time
                    logger.info(f"已下載 {total_bills} 筆資料，耗時 {elapsed_time:.2f} 秒")
                
                # 隨機延遲
                delay = 2 + (time.time() % 3)  # 2-5秒延遲
                logger.info(f"等待 {delay:.2f} 秒後繼續...")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"下載第 {page} 頁時發生錯誤: {str(e)}")
                # 延遲後繼續嘗試下一頁
                time.sleep(10)
                continue
        
        elapsed_time = time.time() - start_time
        logger.info(f"下載完成！總共下載 {total_bills} 筆資料，耗時 {elapsed_time:.2f} 秒")
        
        # 查詢資料庫中的頁碼統計
        cursor = db.conn.cursor()
        cursor.execute("""
        SELECT page_number, COUNT(*) as count 
        FROM bills 
        GROUP BY page_number 
        ORDER BY page_number
        """)
        
        logger.info("\n各頁資料統計：")
        for row in cursor.fetchall():
            if row['page_number'] is not None:
                logger.info(f"第 {row['page_number']} 頁：{row['count']} 筆")
        
        # 查詢資料庫中的屆別統計
        cursor.execute("""
        SELECT term, COUNT(*) as count 
        FROM bills 
        GROUP BY term 
        ORDER BY CAST(term AS INTEGER) DESC
        """)
        
        logger.info("\n各屆別資料統計：")
        for row in cursor.fetchall():
            logger.info(f"第 {row['term']} 屆：{row['count']} 筆")
            
        return True
    except Exception as e:
        logger.error(f"下載過程中發生錯誤: {str(e)}")
        return False
    finally:
        db.close()

def main():
    logger.info("======= 開始重置並下載所有法案 =======")
    
    # 詢問用戶確認
    if len(sys.argv) <= 1 or sys.argv[1] != "--force":
        confirmation = input("此操作將會重置資料庫並重新下載所有資料。確定要繼續嗎？(y/n): ")
        if confirmation.lower() != 'y':
            logger.info("操作已取消")
            return
    
    # 重置資料庫
    if not reset_database():
        logger.error("資料庫重置失敗，終止操作")
        return
        
    # 下載所有法案
    if not download_all_bills_with_page():
        logger.error("下載法案失敗")
    
    logger.info("======= 操作完成 =======")

if __name__ == "__main__":
    main() 