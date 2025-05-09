import requests
import sqlite3
import os
import json
import time
from datetime import datetime
import ssl
import urllib3
import random
import sys

# 關閉SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 解決SSL問題
ssl._create_default_https_context = ssl._create_unverified_context

# 確保data目錄存在
os.makedirs("data", exist_ok=True)

# 資料庫相關函數
def get_db_connection():
    """創建並返回一個資料庫連接"""
    db_path = "data/bills.db"
    
    # 如果資料庫被鎖定，嘗試使用臨時資料庫
    for attempt in range(3):
        try:
            # 設置超時以避免長時間等待鎖定
            conn = sqlite3.connect(db_path, timeout=30)
            # 啟用外鍵約束
            conn.execute("PRAGMA foreign_keys = ON")
            # 配置連接以返回行作為字典
            conn.row_factory = sqlite3.Row
            return conn, db_path
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < 2:
                print(f"資料庫鎖定，嘗試使用臨時資料庫 (嘗試 {attempt+1}/3)...")
                # 創建一個帶有隨機後綴的新資料庫文件
                random_suffix = random.randint(1000, 9999)
                db_path = f"data/bills_{random_suffix}.db"
                print(f"嘗試使用臨時資料庫文件: {db_path}")
                continue
            else:
                print(f"資料庫連接錯誤: {e}")
                raise
        except sqlite3.Error as e:
            print(f"資料庫連接錯誤: {e}")
            raise
    
    # 如果所有嘗試都失敗，拋出異常
    raise sqlite3.OperationalError("無法連接到任何資料庫")

def init_db(conn):
    """初始化資料庫，創建必要的表格"""
    try:
        cursor = conn.cursor()
        # 建立表格(如果不存在)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comparison (
            term TEXT,
            sessionPeriod TEXT,
            sessionTimes TEXT,
            meetingTimes TEXT,
            billNo TEXT,
            docNo TEXT,
            docUrl TEXT,
            lawCompareTitle TEXT,
            reviseLaw TEXT,
            activeLaw TEXT, 
            description TEXT,
            selectTerm TEXT,
            download_date TEXT
        )
        ''')
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"資料庫初始化錯誤: {e}")
        return False

# 設置請求頭
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://data.ly.gov.tw/',
    'Origin': 'https://data.ly.gov.tw',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache'
}

# 創建會話以重用連接
session = requests.Session()
session.headers.update(headers)
session.verify = False  # 禁用SSL證書驗證，以防出現證書問題

# 定義API URL基本路徑和參數
base_url = "https://data.ly.gov.tw/odw/openDatasetJson.action"

# 取得當前日期時間作為下載時間記錄
download_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 修改獲取數據函數，以更好地處理連接問題
def get_comparison_data(page, max_retries=10, initial_delay=5):
    params = {
        'id': '19',
        'selectTerm': 'all',
        'page': page
    }
    
    retry_delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            print(f"\n嘗試獲取第 {page} 頁數據 (嘗試 {attempt+1}/{max_retries})...")
            print(f"API URL: {base_url} 參數: {params}")
            
            # 增加超時設置，連接超時和讀取超時分開設置
            response = session.get(
                base_url, 
                params=params, 
                timeout=(30, 120),  # (連接超時, 讀取超時)
                stream=True
            )
            
            # 檢查HTTP狀態碼
            if response.status_code != 200:
                print(f"API返回錯誤狀態碼: {response.status_code}")
                print(f"回應內容: {response.text[:500]}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒後重試...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # 指數退避，但不要增長太快
                    continue
                return None
            
            # 檢查回應內容類型
            content_type = response.headers.get('Content-Type', '')
            print(f"回應內容類型: {content_type}")
            
            # 嘗試解析JSON
            try:
                # 使用更安全的方式讀取內容
                content = ''
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        content += chunk.decode('utf-8', errors='ignore')
                
                if not content:
                    print("回應內容為空")
                    if attempt < max_retries - 1:
                        print(f"等待 {retry_delay} 秒後重試...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    return None
                
                # 嘗試解析收到的內容
                try:
                    data = json.loads(content)
                    # 成功獲取數據
                    if isinstance(data, dict):
                        if 'dataList' in data:
                            return {'dataList': data['dataList']}
                        elif 'jsonList' in data:  # 有些API使用jsonList而不是dataList
                            return {'dataList': data['jsonList']}
                        else:
                            print(f"API回應缺少 'dataList' 鍵: {list(data.keys())}")
                    else:
                        print(f"API回應不是字典格式: {type(data)}")
                        
                except json.JSONDecodeError as e:
                    print(f"解析JSON時發生錯誤: {e}")
                    print(f"回應內容前500個字符: {content[:500]}")
                    # 如果是HTML而非JSON，可能需要登入或有其他限制
                    if '<html' in content.lower():
                        print("API返回了HTML而非JSON，可能需要登入或有其他限制")
                    
            except Exception as e:
                print(f"處理回應內容時發生錯誤: {e}")
            
            # 如果到這裡，表示請求成功但數據有問題，等待後重試
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                
        except requests.exceptions.Timeout:
            print(f"請求超時 (嘗試 {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                
        except requests.exceptions.ConnectionError as e:
            print(f"連接錯誤: {e}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                
        except requests.exceptions.RequestException as e:
            print(f"請求API時發生錯誤: {e}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                
    return None

# 嘗試使用備用API方法：直接使用不同的URL和參數
def try_alternative_api(term="all", max_retries=3):
    """嘗試使用立法院網站其他API獲取數據"""
    print("嘗試使用備用API獲取數據...")
    
    # 嘗試不同的API端點列表
    api_endpoints = [
        {
            'url': "https://data.ly.gov.tw/odw/lwReviewAnalysis.action",
            'params': {'selectTerm': term}
        },
        {
            'url': "https://data.ly.gov.tw/odw/openDatasetJson.action",
            'params': {'id': '20', 'selectTerm': term, 'page': '1'}  # 嘗試不同的ID
        }
    ]
    
    for endpoint in api_endpoints:
        print(f"嘗試備用API: {endpoint['url']}")
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                response = session.get(
                    endpoint['url'], 
                    params=endpoint['params'], 
                    timeout=(30, 120),
                    stream=True
                )
                
                if response.status_code != 200:
                    print(f"備用API返回錯誤狀態碼: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    break  # 嘗試下一個API
                
                # 解析回應
                content = ''
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        content += chunk.decode('utf-8', errors='ignore')
                        
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        if 'dataList' in data:
                            print("成功從備用API獲取數據")
                            return data
                        elif 'jsonList' in data:
                            print("成功從備用API獲取數據 (jsonList格式)")
                            return {'dataList': data['jsonList']}
                        else:
                            print(f"備用API回應格式不符預期: {list(data.keys())}")
                except json.JSONDecodeError:
                    print("無法解析備用API回應")
                    
            except Exception as e:
                print(f"備用API請求失敗: {e}")
                
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
    
    # 所有備用API都失敗            
    return None

# 保存數據到資料庫
def save_records_to_db(records, conn, download_date):
    """將記錄保存到資料庫"""
    cursor = conn.cursor()
    record_count = 0
    
    try:
        for record in records:
            cursor.execute('''
            INSERT INTO comparison VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.get('term', ''),
                record.get('sessionPeriod', ''),
                record.get('sessionTimes', ''),
                record.get('meetingTimes', ''),
                record.get('billNo', ''),
                record.get('docNo', ''),
                record.get('docUrl', ''),
                record.get('lawCompareTitle', ''),
                record.get('reviseLaw', ''),
                record.get('activeLaw', ''),
                record.get('description', ''),
                record.get('selectTerm', ''),
                download_date
            ))
            record_count += 1
            
        conn.commit()
        return record_count
    except sqlite3.Error as e:
        print(f"資料庫插入錯誤: {e}")
        conn.rollback()
        return 0

# 主程序
def main():
    total_records = 0
    empty_pages = 0
    page = 1
    max_pages = 30  # 設置一個最大頁數限制
    
    try:
        # 初始化資料庫連接
        conn, db_path = get_db_connection()
        if not init_db(conn):
            print("資料庫初始化失敗，程序終止")
            sys.exit(1)
            
        print(f"使用資料庫: {db_path}")
        cursor = conn.cursor()
        
        # 清空現有資料 - 使用事務確保原子性
        try:
            cursor.execute("DELETE FROM comparison")
            conn.commit()
            print("已清空現有資料")
        except sqlite3.Error as e:
            print(f"清空數據時發生錯誤: {e}")
            print("繼續執行程序，數據將被附加而非替換")
        
        while page <= max_pages and empty_pages < 3:  # 連續3頁都沒有資料才停止
            print(f"\n開始處理第 {page} 頁...")
            
            # 獲取數據
            data = get_comparison_data(page)
            
            # 如果標準API失敗，嘗試備用方法
            if data is None and page == 1:
                print("標準API失敗，嘗試備用方法...")
                data = try_alternative_api()
            
            if data is None:
                print(f"無法獲取第 {page} 頁數據，跳過...")
                empty_pages += 1
                page += 1
                continue
            
            # 處理回應數據
            if 'dataList' in data:
                records = data['dataList']
                record_count = len(records)
                print(f"找到 {record_count} 筆記錄")
                
                if record_count == 0:
                    print(f"第 {page} 頁沒有數據")
                    empty_pages += 1
                    page += 1
                    continue
                
                # 重置空頁計數
                empty_pages = 0
                
                # 插入新數據
                saved_count = save_records_to_db(records, conn, download_date)
                
                # 累計總記錄數
                total_records += saved_count
                print(f"成功將 {saved_count} 筆資料新增至資料庫")
            else:
                print(f"API回應缺少 'dataList' 鍵")
                empty_pages += 1
            
            # 等待一下以避免過快請求
            print("等待5秒後繼續請求下一頁...")
            time.sleep(5)
            
            # 下一頁
            page += 1
    
    except KeyboardInterrupt:
        print("\n程序被使用者中斷")
    except Exception as e:
        print(f"\n執行過程中發生錯誤: {e}")
    finally:
        # 顯示最終結果
        print(f"\n總共成功將 {total_records} 筆資料儲存到 {db_path} 的 comparison 表格")
        
        # 關閉資料庫連接
        try:
            conn.close()
            print("資料庫連接已關閉")
        except:
            pass

if __name__ == "__main__":
    main()
