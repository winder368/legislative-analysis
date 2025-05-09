import requests
import logging
import time
import sys
import json
from datetime import datetime

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_diagnosis.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("APIDiagnosis")

BASE_URL = "https://data.ly.gov.tw/odw/openDatasetJson.action"

def test_network_connection():
    """測試網路連線"""
    try:
        logger.info("測試網路連線...")
        response = requests.get("https://www.google.com", timeout=5)
        response.raise_for_status()
        logger.info(f"網路連線正常，回應時間: {response.elapsed.total_seconds():.3f} 秒")
        return True
    except Exception as e:
        logger.error(f"網路連線測試失敗: {str(e)}")
        return False

def test_api_connection(timeout=10):
    """測試與立法院 API 的連線"""
    try:
        logger.info(f"測試與立法院 API 的連線 (超時時間: {timeout} 秒)...")
        response = requests.get(BASE_URL, timeout=timeout)
        response.raise_for_status()
        logger.info(f"API 連線正常，回應時間: {response.elapsed.total_seconds():.3f} 秒")
        return True
    except Exception as e:
        logger.error(f"API 連線測試失敗: {str(e)}")
        return False

def test_single_page(term="all", page=1, timeout=30):
    """測試獲取單一頁面的數據"""
    params = {
        "id": "20",
        "selectTerm": term,
        "page": page
    }
    
    try:
        logger.info(f"測試獲取第 {page} 頁資料 (超時時間: {timeout} 秒)...")
        start_time = time.time()
        
        response = requests.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        
        elapsed_time = time.time() - start_time
        logger.info(f"請求完成，耗時 {elapsed_time:.2f} 秒")
        
        data = response.json()
        bills = data.get("jsonList", [])
        logger.info(f"成功獲取 {len(bills)} 筆資料")
        
        # 儲存樣本回應進行分析
        sample_file = f"data/api_sample_page_{page}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(sample_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"樣本資料已儲存至: {sample_file}")
        
        return bills
    except Exception as e:
        logger.error(f"獲取第 {page} 頁資料失敗: {str(e)}")
        return None

def measure_response_times(term="all", pages=5, timeout=30):
    """測量多頁的回應時間"""
    logger.info(f"開始測量 {pages} 頁的回應時間...")
    
    results = []
    for page in range(1, pages + 1):
        try:
            params = {
                "id": "20",
                "selectTerm": term,
                "page": page
            }
            
            start_time = time.time()
            response = requests.get(BASE_URL, params=params, timeout=timeout)
            response.raise_for_status()
            elapsed_time = time.time() - start_time
            
            data = response.json()
            count = len(data.get("jsonList", []))
            
            results.append({
                "page": page,
                "time": elapsed_time,
                "count": count,
                "status": response.status_code
            })
            
            logger.info(f"第 {page} 頁: 耗時 {elapsed_time:.2f} 秒, 獲取 {count} 筆資料")
            time.sleep(2)  # 避免請求過快
        except Exception as e:
            logger.error(f"測量第 {page} 頁時出錯: {str(e)}")
            results.append({
                "page": page,
                "time": None,
                "count": 0,
                "status": "error",
                "error": str(e)
            })
    
    # 計算統計資訊
    valid_times = [r["time"] for r in results if r["time"] is not None]
    if valid_times:
        avg_time = sum(valid_times) / len(valid_times)
        max_time = max(valid_times)
        min_time = min(valid_times)
        logger.info(f"統計資訊 - 平均: {avg_time:.2f} 秒, 最大: {max_time:.2f} 秒, 最小: {min_time:.2f} 秒")
    
    # 保存結果
    result_file = f"data/response_times_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"測量結果已保存至: {result_file}")

def test_different_timeouts():
    """測試不同的超時設置"""
    timeouts = [5, 10, 30, 60, 120]
    
    for timeout in timeouts:
        logger.info(f"測試 {timeout} 秒超時設置...")
        try:
            start_time = time.time()
            response = requests.get(f"{BASE_URL}?id=20&page=1", timeout=timeout)
            response.raise_for_status()
            elapsed_time = time.time() - start_time
            logger.info(f"超時設置 {timeout} 秒: 請求成功，耗時 {elapsed_time:.2f} 秒")
        except Exception as e:
            logger.error(f"超時設置 {timeout} 秒: 請求失敗 - {str(e)}")
        
        time.sleep(5)  # 在不同超時測試之間等待

def main():
    """主診斷函數"""
    logger.info("===== 開始 API 診斷 =====")
    
    # 測試網路連線
    if not test_network_connection():
        logger.error("網路連線測試失敗，診斷終止")
        return
    
    # 測試 API 連線
    if not test_api_connection():
        logger.error("API 連線測試失敗，診斷將繼續但可能會有更多錯誤")
    
    # 執行命令列參數指定的測試
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "timeouts":
            test_different_timeouts()
        elif command == "page" and len(sys.argv) > 2:
            page = int(sys.argv[2])
            timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            test_single_page(page=page, timeout=timeout)
        elif command == "measure" and len(sys.argv) > 2:
            pages = int(sys.argv[2])
            timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            measure_response_times(pages=pages, timeout=timeout)
        else:
            logger.info("未知的命令或參數不足")
            logger.info("可用命令: timeouts, page <頁碼> [超時秒數], measure <頁數> [超時秒數]")
    else:
        # 默認診斷流程
        logger.info("執行默認診斷流程")
        test_different_timeouts()
        test_single_page(page=1, timeout=60)
        measure_response_times(pages=3, timeout=60)
    
    logger.info("===== API 診斷完成 =====")

if __name__ == "__main__":
    main() 