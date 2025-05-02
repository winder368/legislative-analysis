import requests
import sqlite3
import json
from datetime import datetime
import time

def create_historical_legislators_table(cursor):
    """建立歷屆立委資料表"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS historical_legislators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT,                    -- 屆別
        name TEXT,                    -- 姓名
        party TEXT,                   -- 黨籍
        party_group TEXT,             -- 黨團
        constituency TEXT,            -- 選區
        committee TEXT,               -- 委員會
        onboard_date TEXT,            -- 到職日期
        degree TEXT,                  -- 學歷
        experience TEXT,              -- 經歷
        birthday TEXT,                -- 生日
        gender TEXT,                  -- 性別
        in_office INTEGER DEFAULT 1,  -- 是否在職
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

def download_historical_legislators():
    """下載歷屆立委資料"""
    base_url = "https://data.ly.gov.tw/odw/openDatasetJson.action?id=16&selectTerm=all&page={}"
    
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
        # 連接到資料庫
        conn = sqlite3.connect('legislative.db')
        cursor = conn.cursor()
        
        # 建立資料表
        create_historical_legislators_table(cursor)
        
        # 清空現有資料
        cursor.execute("DELETE FROM historical_legislators")
        
        # 初始化計數器
        total_count = 0
        page = 1
        all_legislators_data = []
        
        while True:
            print(f"正在下載第 {page} 頁的資料...")
            
            # 下載資料
            response = requests.get(base_url.format(page), headers=headers)
            response.raise_for_status()
            
            # 解析 JSON 資料
            data = response.json()
            
            # 解析資料
            if isinstance(data, str):
                data = json.loads(data)
                
            if isinstance(data, dict):
                if 'jsonList' in data:
                    legislators_data = data['jsonList']
                else:
                    legislators_data = [data]
            else:
                legislators_data = data
            
            # 如果沒有更多資料，跳出迴圈
            if not legislators_data:
                break
                
            # 加入資料列表
            all_legislators_data.extend(legislators_data)
            
            # 插入新資料
            for item in legislators_data:
                cursor.execute('''
                INSERT INTO historical_legislators (
                    term, name, party, party_group, constituency, 
                    committee, onboard_date, degree, experience, 
                    birthday, gender, in_office
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.get('term', ''),
                    item.get('name', ''),
                    item.get('party', ''),
                    item.get('partyGroup', ''),
                    item.get('areaName', ''),  # 選區
                    item.get('committee', ''),
                    item.get('onboardDate', ''),
                    item.get('degree', ''),
                    item.get('experience', ''),
                    item.get('birthday', ''),
                    item.get('sex', ''),
                    1 if item.get('inOffice', '').lower() == 'true' else 0
                ))
            
            # 提交變更
            conn.commit()
            
            # 更新計數
            total_count += len(legislators_data)
            print(f"已下載 {total_count} 筆資料")
            
            # 下一頁
            page += 1
            
            # 適當的延遲，避免請求過於頻繁
            time.sleep(1)
        
        # 顯示統計資訊
        cursor.execute("SELECT COUNT(*) FROM historical_legislators")
        final_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT term, COUNT(*) as count, 
                   COUNT(DISTINCT party) as party_count,
                   GROUP_CONCAT(DISTINCT party) as parties
            FROM historical_legislators 
            GROUP BY term 
            ORDER BY CAST(term AS INTEGER)
        """)
        term_stats = cursor.fetchall()
        
        print(f"\n成功下載並儲存 {final_count} 筆歷屆立委資料")
        print("\n各屆立委詳細統計：")
        for term, count, party_count, parties in term_stats:
            print(f"第 {term:>2} 屆：{count:>3} 人，{party_count} 個政黨（{parties}）")
        
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
    download_historical_legislators() 