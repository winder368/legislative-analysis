# 立法院法案查詢系統

這是一個用於查詢立法院法案的網頁應用程式。使用者可以依據法律名稱和屆別來搜尋相關的修正提案。

## 功能特點

- 依法律名稱和屆別搜尋法案
- 顯示個別條文的修正提案
- 支援中文數字和阿拉伯數字的條號顯示
- 提供提案人和連署人資訊
- 支援 PDF 和 DOC 格式的提案下載

## 本地開發

1. 安裝依賴：
```bash
pip install -r requirements.txt
```

2. 初始化資料庫：
```bash
python src/download_bills.py
```

3. 啟動應用程式：
```bash
python src/app.py
```

應用程式將在 http://127.0.0.1:5000 運行。

## 部署說明

本應用程式可以部署到 Render.com：

1. 在 Render.com 創建新的 Web Service
2. 連接到 GitHub 儲存庫
3. 選擇 Python 環境
4. 設定以下參數：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn src.app:app`

## 資料來源

資料來自立法院開放資料平台。

## 授權

MIT License 