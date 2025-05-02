import requests
import sqlite3
import json
from datetime import datetime

def create_legislators_table(cursor):
    """建立立委資料表"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS legislators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT,
        name TEXT,
        party TEXT,
        constituency TEXT,
        start_date TEXT,
        end_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

def download_legislators():
    """下載立法院委員資料"""
    url = "https://data.ly.gov.tw/odw/openDatasetJson.action?id=16&selectTerm=all&page=1"
    
    # 設定請求標頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://data.ly.gov.tw/odw/useCase.action?id=16&type=json',
        'Origin': 'https://data.ly.gov.tw',
        'Connection': 'keep-alive'
    }
    
    try:
        # 下載資料
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 檢查是否下載成功
        data = response.json()
        
        # 印出資料結構
        print("API 回傳的資料結構：")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 連接到資料庫
        conn = sqlite3.connect('legislative.db')
        cursor = conn.cursor()
        
        # 建立資料表
        create_legislators_table(cursor)
        
        # 清空現有資料
        cursor.execute("DELETE FROM legislators")
        
        # 檢查資料格式並進行相應處理
        if isinstance(data, str):
            data = json.loads(data)
        
        if isinstance(data, dict) and 'jsonList' in data:
            legislators_data = data['jsonList']
        else:
            legislators_data = data
        
        # 插入新資料
        for item in legislators_data:
            cursor.execute('''
            INSERT INTO legislators (term, name, party, constituency, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                item.get('term', ''),
                item.get('name', ''),
                item.get('party', ''),
                item.get('constituency', ''),
                item.get('startDate', ''),
                item.get('endDate', '')
            ))
        
        # 提交變更
        conn.commit()
        print(f"成功下載並儲存 {len(legislators_data)} 筆立委資料")
        
    except requests.exceptions.RequestException as e:
        print(f"下載資料時發生錯誤: {str(e)}")
    except sqlite3.Error as e:
        print(f"資料庫操作時發生錯誤: {str(e)}")
    except Exception as e:
        print(f"發生未預期的錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    download_legislators() 