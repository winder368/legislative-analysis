import requests

# API URL
api_url = "https://data.ly.gov.tw/odw/openDatasetJson.action?id=19&selectTerm=all&page=1"

# 設置請求頭
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 下載數據
print("開始請求立法院API...")
response = requests.get(api_url, headers=headers)
print(f"狀態碼: {response.status_code}")
print(f"回應頭: {response.headers}")
print(f"回應內容前500字符: {response.text[:500]}")

# 嘗試解析JSON
try:
    data = response.json()
    print("成功解析JSON")
    print(f"資料類型: {type(data)}")
    if isinstance(data, dict):
        print(f"鍵: {list(data.keys())}")
except Exception as e:
    print(f"解析JSON失敗: {e}") 