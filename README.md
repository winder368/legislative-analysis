# 立法院法案查詢系統

這是一個用於查詢和分析立法院法案的網頁應用程式。系統提供法案搜尋、政黨分布分析等功能。

## 功能特點

- 法案搜尋：依法律名稱搜尋相關法案
- 政黨分析：顯示提案人與連署人的政黨分布
- 審查進度追蹤：顯示法案的審查狀態
- 條號分類：依條號整理相關法案
- 檔案下載：提供 PDF 和 DOC 格式的法案檔案下載

## 系統需求

- Python 3.9 或以上版本
- Flask
- SQLite3

## 安裝步驟

1. 克隆專案：
```bash
git clone https://github.com/您的使用者名稱/legislative_analysis.git
cd legislative_analysis
```

2. 建立虛擬環境：
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

3. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

4. 初始化資料庫：
```bash
python3 src/init_db.py
```

5. 啟動應用程式：
```bash
python3 app.py
```

## 使用說明

1. 開啟瀏覽器，訪問 http://127.0.0.1:5000
2. 在搜尋框中輸入法律名稱（如：刑法、民法等）
3. 選擇要搜尋的屆期
4. 點擊搜尋按鈕
5. 查看搜尋結果，可以：
   - 依條號或審查進度排序
   - 查看提案人與連署人的政黨分布
   - 下載法案檔案

## 專案結構

```
legislative_analysis/
├── app.py              # 主應用程式
├── requirements.txt    # 依賴套件列表
├── src/               # 原始碼目錄
│   ├── database.py    # 資料庫操作
│   └── bill_utils.py  # 法案處理工具
└── templates/         # HTML 模板
    ├── index.html     # 首頁
    └── search_results.html  # 搜尋結果頁面
```

## 授權

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。 