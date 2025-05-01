from flask import Flask, jsonify
from src.bill_utils import get_popular_bills_sql, clean_law_name

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "message": "法案分析系統 API",
        "status": "運作中"
    })

@app.route('/api/popular-bills')
def popular_bills():
    # 這裡之後會加入資料庫查詢
    return jsonify({
        "message": "熱門法案列表",
        "data": []
    })

if __name__ == '__main__':
    app.run(debug=True) 