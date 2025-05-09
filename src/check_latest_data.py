import logging
import time
import os
import json
from datetime import datetime
from api_client import LYAPIClient
from database import Database

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("check_latest.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CheckLatestData")

def ensure_data_dir():
    """確保資料目錄存在"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"已創建資料目錄: {data_dir}")
    return data_dir

def check_api_latest_data():
    """檢查API最新資料狀態"""
    logger.info("檢查API最新資料狀態...")
    
    # 初始化API客戶端
    client = LYAPIClient(timeout=60, max_retries=3, retry_delay=2)
    
    try:
        # 獲取第一頁資料（最新資料）
        logger.info("獲取第一頁資料...")
        start_time = time.time()
        bills = client.get_bills(page=1)
        elapsed_time = time.time() - start_time
        
        if not bills:
            logger.error("獲取資料失敗，API返回空資料")
            return
        
        logger.info(f"成功獲取 {len(bills)} 筆資料，耗時: {elapsed_time:.2f} 秒")
        
        # 獲取當前最新的屆別和會期
        term_session_map = {}
        
        # 分析第一頁資料
        for bill in bills[:10]:  # 只分析前10筆資料
            term = bill.get('term', '')
            session = bill.get('sessionPeriod', '')
            
            key = f"{term}_{session}"
            term_session_map[key] = term_session_map.get(key, 0) + 1
        
        # 顯示最新的屆別和會期統計
        logger.info("\n最新資料的屆別和會期統計:")
        for key, count in sorted(term_session_map.items(), key=lambda x: (-int(x[0].split('_')[0]), -int(x[0].split('_')[1]))):
            term, session = key.split('_')
            logger.info(f"第 {term} 屆第 {session} 會期: {count} 筆")
        
        # 保存最新的10筆資料進行分析
        data_dir = ensure_data_dir()
        sample_file = os.path.join(data_dir, f"latest_10_bills_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(sample_file, 'w', encoding='utf-8') as f:
            json.dump(bills[:10], f, ensure_ascii=False, indent=2)
        
        logger.info(f"已將最新的10筆資料保存至: {sample_file}")
        
        # 估算總資料量
        total_count = client.get_total_bills_count()
        logger.info(f"API 總資料量估計: {total_count} 筆")
        
        # 檢查資料庫中的資料
        db = Database()
        try:
            # 獲取資料庫中最新的屆別和會期
            latest_db_info = db.get_latest_term_session()
            total_bills = db.get_bills_count()
            
            if latest_db_info:
                db_term, db_session = latest_db_info
                logger.info(f"\n資料庫中最新的資料是第 {db_term} 屆第 {db_session} 會期")
                logger.info(f"資料庫中目前共有 {total_bills} 筆法案資料")
                
                # 計算資料庫與API最新資料的差異
                api_newest_term = next(iter(sorted(term_session_map.keys(), key=lambda x: (-int(x.split('_')[0]), -int(x.split('_')[1]))))).split('_')[0]
                api_newest_session = next(iter(sorted(term_session_map.keys(), key=lambda x: (-int(x.split('_')[0]), -int(x.split('_')[1]))))).split('_')[1]
                
                if (api_newest_term > db_term) or (api_newest_term == db_term and api_newest_session > db_session):
                    logger.info(f"API有更新的資料: 第 {api_newest_term} 屆第 {api_newest_session} 會期")
                    logger.info(f"建議執行更新")
                else:
                    logger.info("資料庫已經是最新的了")
            else:
                logger.info("資料庫為空，建議執行完整下載")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"檢查API過程中發生錯誤: {str(e)}")

def main():
    logger.info("=== 開始檢查最新資料 ===")
    start_time = time.time()
    
    check_api_latest_data()
    
    elapsed_time = time.time() - start_time
    logger.info(f"檢查完成，總耗時: {elapsed_time:.2f} 秒")
    logger.info("=== 檢查結束 ===")

if __name__ == "__main__":
    main() 