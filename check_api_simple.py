import requests
import time

# 設置請求頭
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://data.ly.gov.tw/'
}

# API URL
api_url = "https://data.ly.gov.tw/odw/openDatasetJson.action"
params = {
    'id': '19',
    'selectTerm': 'all',
    'page': 1
}

print("開始請求API...")
start_time = time.time()

try:
    # 設置超時時間為30秒
    response = requests.get(api_url, params=params, headers=headers, timeout=30)
    
    end_time = time.time()
    print(f"請求花費時間：{end_time - start_time:.2f} 秒")
    print(f"狀態碼：{response.status_code}")
    print(f"回應頭：{dict(response.headers)}")
    
    if response.status_code == 200:
        print("\n回應內容前1000個字符：")
        print(response.text[:1000])
        
        # 嘗試解析JSON
        try:
            data = response.json()
            print("\nJSON解析成功")
            print(f"資料類型：{type(data)}")
            
            if isinstance(data, dict):
                print(f"資料鍵：{list(data.keys())}")
                
                if 'dataList' in data:
                    records = data['dataList']
                    print(f"記錄數量：{len(records)}")
                    
                    if records:
                        print("\n第一筆記錄：")
                        for key, value in records[0].items():
                            print(f"{key}: {value}")
                else:
                    print("資料中沒有'dataList'鍵")
        except Exception as e:
            print(f"解析JSON失敗：{e}")
    else:
        print("請求失敗")
        
except requests.exceptions.Timeout:
    print("請求超時")
except requests.exceptions.RequestException as e:
    print(f"請求失敗：{e}")
except Exception as e:
    print(f"發生錯誤：{e}") 