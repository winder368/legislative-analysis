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
        logging.FileHandler("update_from_page_logs.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("UpdateFromPage")

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
        
    # 確保頁面備份子目錄存在
    page_backup_dir = os.path.join(backup_dir, 'pages')
    if not os.path.exists(page_backup_dir):
        os.makedirs(page_backup_dir)
        logger.info(f"已創建頁面備份目錄: {page_backup_dir}")
        
    # 確保資料庫備份子目錄存在
    db_backup_dir = os.path.join(backup_dir, 'database')
    if not os.path.exists(db_backup_dir):
        os.makedirs(db_backup_dir)
        logger.info(f"已創建資料庫備份目錄: {db_backup_dir}")
        
    return data_dir

def get_backup_dir():
    """獲取備份目錄路徑"""
    data_dir = ensure_data_dir()
    backup_dir = os.path.join(data_dir, 'backups')
    return backup_dir

def get_page_backup_dir():
    """獲取頁面備份目錄路徑"""
    backup_dir = get_backup_dir()
    page_backup_dir = os.path.join(backup_dir, 'pages')
    return page_backup_dir

def get_db_backup_dir():
    """獲取資料庫備份目錄路徑"""
    backup_dir = get_backup_dir()
    db_backup_dir = os.path.join(backup_dir, 'database')
    return db_backup_dir

def get_min_page_number(db: Database) -> int:
    """獲取資料庫中的最小頁碼
    
    Returns:
        int: 最小頁碼，如果沒有頁碼信息則返回1
    """
    cursor = db.conn.cursor()
    cursor.execute("""
    SELECT MIN(page_number) as min_page
    FROM bills
    WHERE page_number IS NOT NULL
    """)
    
    row = cursor.fetchone()
    if row and row['min_page'] is not None:
        return row['min_page']
    return 1

def get_latest_page_info(db: Database) -> dict:
    """獲取資料庫中最新的頁碼和統計信息
    
    Returns:
        dict: 包含最新頁碼和統計信息的字典
    """
    result = {
        'max_page': 1,
        'total_bills': 0,
        'page_stats': {}
    }
    
    cursor = db.conn.cursor()
    
    # 獲取最大頁碼
    cursor.execute("""
    SELECT MAX(page_number) as max_page
    FROM bills
    WHERE page_number IS NOT NULL
    """)
    
    row = cursor.fetchone()
    if row and row['max_page'] is not None:
        result['max_page'] = row['max_page']
    
    # 獲取總記錄數
    cursor.execute("SELECT COUNT(*) as count FROM bills")
    row = cursor.fetchone()
    if row:
        result['total_bills'] = row['count']
    
    # 獲取頁碼統計
    cursor.execute("""
    SELECT page_number, COUNT(*) as count
    FROM bills
    WHERE page_number IS NOT NULL
    GROUP BY page_number
    ORDER BY page_number DESC
    LIMIT 10
    """)
    
    for row in cursor.fetchall():
        result['page_stats'][row['page_number']] = row['count']
    
    return result

# 添加資料庫備份函數
def backup_database(db: Database):
    """備份資料庫
    
    Args:
        db: 資料庫對象
    """
    try:
        # 獲取資料庫檔案路徑
        db_path = db.db_path
        
        # 建立備份檔案名稱
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"bills_backup_{timestamp}.db"
        
        # 獲取資料庫備份目錄
        db_backup_dir = get_db_backup_dir()
        backup_path = os.path.join(db_backup_dir, backup_filename)
        
        # 備份資料庫 (使用sqlite3自身的backup功能)
        # 這裡我們簡單地複製檔案
        import shutil
        shutil.copy2(db_path, backup_path)
        
        logger.info(f"已將資料庫備份至: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"備份資料庫時發生錯誤: {str(e)}")
        return None

def update_bills_from_page(start_page: int = None, max_pages_to_check: int = 10, mode: str = "smart"):
    """從指定頁碼開始更新法案資料
    
    Args:
        start_page: 開始頁碼，如果為None則根據mode決定起始頁碼
        max_pages_to_check: 最多檢查的頁數
        mode: 更新模式
            - "latest": 從第1頁開始，獲取最新資料
            - "continue": 從資料庫最大頁碼+1開始，繼續之前的下載
            - "smart"(默認): 智能決定起始頁碼
    """
    logger.info("開始更新法案資料...")
    
    # 初始化客戶端和資料庫
    client = LYAPIClient(timeout=60, max_retries=5, retry_delay=3)
    db = Database()
    
    try:
        # 在更新前先備份資料庫
        backup_database(db)
        
        # 獲取最新的頁碼信息
        page_info = get_latest_page_info(db)
        logger.info(f"資料庫統計: 最大頁碼={page_info['max_page']}, 總記錄數={page_info['total_bills']}")
        
        # 顯示資料庫中的頁碼統計信息
        if page_info['page_stats']:
            logger.info("資料庫中的頁碼統計:")
            for page, count in sorted(page_info['page_stats'].items(), key=lambda x: x[0])[:5]:
                logger.info(f"第 {page} 頁: {count} 筆")
            if len(page_info['page_stats']) > 5:
                logger.info("...以及更多頁面")
                for page, count in sorted(page_info['page_stats'].items(), key=lambda x: x[0], reverse=True)[:3]:
                    logger.info(f"第 {page} 頁: {count} 筆")
        else:
            logger.warning("資料庫中沒有頁碼信息")
        
        # 根據模式決定起始頁碼
        if start_page is None:
            if mode == "latest":
                # 從第1頁開始（最新資料）
                start_page = 1
                logger.info(f"使用 latest 模式: 從第 {start_page} 頁（最新資料）開始更新")
            elif mode == "continue" and page_info['max_page'] > 0:
                # 從最大頁碼+1開始
                start_page = page_info['max_page'] + 1
                logger.info(f"使用 continue 模式: 從第 {start_page} 頁（資料庫最大頁碼+1）開始更新")
            elif mode == "smart":
                # 智能決定起始頁碼:
                # 1. 如果資料庫為空或很少資料，從第1頁開始
                # 2. 如果資料庫已有大量資料，先檢查最新頁面，再跳到接續處
                if page_info['total_bills'] < 1000 or page_info['max_page'] < 5:
                    start_page = 1
                    logger.info(f"使用 smart 模式(資料少): 從第 {start_page} 頁開始更新")
                else:
                    # 我們採用分段更新策略：
                    # 1. 先檢查第1頁是否有最新資料
                    # 2. 完成後再從最大頁碼+1繼續
                    start_page = 1
                    logger.info(f"使用 smart 模式(資料多): 先從第 {start_page} 頁檢查最新資料")
                    # 設置旗標以便後續跳轉到下一階段
                    smart_mode_stage2 = True
                    smart_mode_check_latest_pages = 3  # 檢查最新的前3頁
            else:
                # 默認從第1頁開始
                start_page = 1
                logger.info(f"使用默認模式: 從第 {start_page} 頁開始更新")
        else:
            logger.info(f"使用指定頁碼: 從第 {start_page} 頁開始更新")
            
        # 根據模式確定最小檢查頁數
        if mode == "continue":
            min_pages_to_check = start_page + max_pages_to_check - 1
        else:
            # 確保至少檢查指定的頁數
            min_pages_to_check = start_page + max_pages_to_check - 1
        
        logger.info(f"將從第 {start_page} 頁開始檢查，計劃檢查到第 {min_pages_to_check} 頁")
        
        # 開始下載更新
        start_time = time.time()
        total_processed_bills = 0
        new_bills_count = 0  # 新增資料計數
        
        # Smart模式的特殊控制變量
        if mode == "smart" and 'smart_mode_stage2' in locals() and smart_mode_stage2:
            smart_mode_current_stage = 1
            smart_mode_switch_page = start_page + smart_mode_check_latest_pages
            logger.info(f"Smart模式第1階段: 檢查最新的 {smart_mode_check_latest_pages} 頁")
        else:
            smart_mode_current_stage = 0  # 非Smart模式或不需要階段性處理
        
        # 設定停止條件標誌
        consecutive_unchanged_pages = 0
        max_consecutive_unchanged = 5  # 允許連續5頁沒有新資料
        
        current_page = start_page
        while current_page <= min_pages_to_check:
            # Smart模式階段切換
            if (smart_mode_current_stage == 1 and 
                current_page >= smart_mode_switch_page):
                # 從第一階段切換到第二階段
                current_page = page_info['max_page'] + 1
                min_pages_to_check = current_page + max_pages_to_check - 1
                logger.info(f"Smart模式切換到第2階段: 跳轉到第 {current_page} 頁繼續更新")
                logger.info(f"將繼續檢查到第 {min_pages_to_check} 頁")
                smart_mode_current_stage = 2
                consecutive_unchanged_pages = 0  # 重置計數
            
            logger.info(f"正在檢查第 {current_page} 頁...")
            
            try:
                bills = client.get_bills(term="all", page=current_page)
                
                if not bills:
                    logger.info(f"第 {current_page} 頁沒有資料，更新結束")
                    break
                
                logger.info(f"成功獲取第 {current_page} 頁資料，共 {len(bills)} 筆")
                
                # 計算此頁新增的資料量
                before_count = db.get_bills_count()
                
                # 備份頁面資料
                page_backup_dir = get_page_backup_dir()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"page_{current_page}_{timestamp}.json"
                backup_path = os.path.join(page_backup_dir, backup_filename)
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(bills, f, ensure_ascii=False, indent=2)
                logger.info(f"已將第 {current_page} 頁資料備份至: {backup_path}")
                
                # 儲存資料並記錄頁碼
                db.save_bills(bills, page_number=current_page)
                
                # 計算新增資料量
                after_count = db.get_bills_count()
                page_new_bills = after_count - before_count
                new_bills_count += page_new_bills
                total_processed_bills += len(bills)
                
                logger.info(f"第 {current_page} 頁: 已處理 {len(bills)} 筆，新增 {page_new_bills} 筆")
                
                # 檢查是否已經到達已有資料
                if page_new_bills == 0:
                    consecutive_unchanged_pages += 1
                    logger.info(f"連續 {consecutive_unchanged_pages} 頁沒有新資料")
                    
                    # 如果連續多頁無新資料，則考慮停止
                    if consecutive_unchanged_pages >= max_consecutive_unchanged:
                        logger.info(f"已連續 {consecutive_unchanged_pages} 頁無新資料，停止當前階段更新")
                        
                        # 如果是Smart模式第一階段，還需要切換到第二階段
                        if smart_mode_current_stage == 1:
                            # 直接跳到下一循環，會觸發階段切換
                            current_page = smart_mode_switch_page
                            continue
                        else:
                            # 其他情況直接結束
                            break
                else:
                    consecutive_unchanged_pages = 0  # 重置計數
                
                # 更新頁碼統計
                page_info['page_stats'][current_page] = len(bills)
                
                # 隨機延遲
                delay = 2 + (time.time() % 3)  # 2-5秒延遲
                logger.info(f"等待 {delay:.2f} 秒後繼續...")
                time.sleep(delay)
                
                # 移動到下一頁
                current_page += 1
                
            except Exception as e:
                logger.error(f"檢查第 {current_page} 頁時發生錯誤: {str(e)}")
                # 延遲後繼續嘗試下一頁
                time.sleep(10)
                current_page += 1
                continue
        
        elapsed_time = time.time() - start_time
        logger.info(f"更新完成！共處理 {total_processed_bills} 筆資料，新增 {new_bills_count} 筆，耗時 {elapsed_time:.2f} 秒")
        
        # 查詢最新的資料庫統計
        new_page_info = get_latest_page_info(db)
        logger.info(f"更新後資料庫統計: 最大頁碼={new_page_info['max_page']}, 總記錄數={new_page_info['total_bills']}")
        
    except Exception as e:
        logger.error(f"更新過程中發生錯誤: {str(e)}")
    finally:
        db.close()

def main():
    logger.info("======= 開始從特定頁碼更新法案 =======")
    
    import argparse
    parser = argparse.ArgumentParser(description='從指定頁碼開始更新法案資料')
    parser.add_argument('--page', type=int, help='起始頁碼，預設自動決定')
    parser.add_argument('--max-pages', type=int, default=10, help='最多檢查的頁數，預設10頁')
    parser.add_argument('--mode', type=str, default='smart', choices=['latest', 'continue', 'smart'],
                        help='更新模式: latest=從第1頁開始, continue=從最大頁碼+1開始, smart=智能決定(預設)')
    parser.add_argument('--backup', action='store_true', help='在開始更新前備份資料庫')
    parser.add_argument('--verbose', '-v', action='store_true', help='顯示詳細日誌信息')
    parser.add_argument('--organize', action='store_true', help='整理備份檔案 (需要先安裝 organize_backups.py)')
    
    args = parser.parse_args()
    
    # 如果啟用詳細模式，設置更詳細的日誌級別
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("啟用詳細日誌模式")
    
    start_page = args.page
    max_pages = args.max_pages
    mode = args.mode
    
    # 顯示更新模式說明
    if start_page is None:
        if mode == 'latest':
            logger.info("使用 latest 模式: 將從第1頁開始獲取最新資料")
        elif mode == 'continue':
            logger.info("使用 continue 模式: 將從資料庫最大頁碼+1繼續下載")
        elif mode == 'smart':
            logger.info("使用 smart 模式: 智能決定更新策略")
    else:
        logger.info(f"使用指定頁碼: 從第 {start_page} 頁開始更新")
    
    # 如果需要整理備份文件
    if args.organize:
        try:
            logger.info("開始整理備份文件...")
            from organize_backups import organize_backups
            organize_backups()
            logger.info("備份文件整理完成")
        except ImportError:
            logger.error("無法導入 organize_backups 模組，請檢查是否已經安裝")
        except Exception as e:
            logger.error(f"整理備份文件時發生錯誤: {str(e)}")
    
    # 執行更新
    update_bills_from_page(start_page, max_pages, mode)
    
    logger.info("======= 更新完成 =======")

if __name__ == "__main__":
    main() 