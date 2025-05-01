import json
from datetime import datetime
import requests
from database import Database

class LegislatorDownloader:
    """立法委員資料下載器"""
    
    def __init__(self):
        self.base_url = "https://data.ly.gov.tw/odw/openDatasetJson.action"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def get_current_term(self) -> str:
        """獲取當前屆別"""
        return "11"  # 目前是第11屆
    
    def download_legislators(self) -> list:
        """下載立法委員資料
        
        Returns:
            list: 立法委員資料列表
        """
        try:
            # 設定 API 參數
            params = {
                'id': '9',  # 立法委員資料集 ID
                'selectTerm': 'all',  # 獲取所有屆期資料
                'page': '1'  # 第一頁（目前資料只有一頁）
            }
            
            # 發送請求
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            # 解析 JSON 回應
            data = response.json()
            legislators = []
            
            if 'jsonList' in data:
                for item in data['jsonList']:
                    legislator = {
                        'term': item.get('term', ''),
                        'name': item.get('name', ''),
                        'party': item.get('party', ''),
                        'constituency': item.get('areaName', ''),
                        'committee': item.get('committee', ''),
                        'education': item.get('degree', ''),
                        'experience': item.get('experience', '')
                    }
                    legislators.append(legislator)
                    print(f"已下載委員資料：{legislator['name']}")
            
            return legislators
            
        except Exception as e:
            print(f"下載立法委員資料時發生錯誤：{str(e)}")
            return []

def main():
    # 初始化下載器和資料庫
    downloader = LegislatorDownloader()
    db = Database()
    
    try:
        print("開始下載立法委員資料...")
        legislators = downloader.download_legislators()
        
        if not legislators:
            print("沒有下載到任何委員資料")
            return
        
        # 清除現有資料
        print("清除現有資料...")
        db.clear_legislators_data()
        
        # 儲存新資料
        print(f"正在將 {len(legislators)} 筆資料存入資料庫...")
        db.save_legislators(legislators)
        
        # 生成備份檔案名稱（包含時間戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/legislators_backup_{timestamp}.json"
        
        # 將資料同時儲存為 JSON 檔案作為備份
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(legislators, f, ensure_ascii=False, indent=2)
        
        # 顯示資料庫統計資訊
        total_legislators = db.get_legislators_count()
        print(f"\n下載完成！")
        print(f"本次新增 {len(legislators)} 筆資料")
        print(f"資料庫中目前共有 {total_legislators} 筆委員資料")
        print(f"資料備份已儲存至：{filename}")
        
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main() 