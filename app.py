from flask import Flask, jsonify, render_template
from src.bill_utils import get_popular_bills_sql, clean_law_name
from src.db_config import get_db
from sqlalchemy import text
import os

# 設定模板目錄的絕對路徑
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)

@app.route('/')
def home():
    return render_template('index.html', 
                         title="法案分析系統",
                         message="歡迎使用法案分析系統")

@app.route('/api/popular-bills')
def popular_bills():
    try:
        db = next(get_db())
        result = db.execute(text(get_popular_bills_sql()))
        bills = [dict(row) for row in result]
        return jsonify({
            "message": "熱門法案列表",
            "data": bills
        })
    except Exception as e:
        return jsonify({
            "message": "發生錯誤",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # 確保 templates 目錄存在
    os.makedirs(template_dir, exist_ok=True)
    app.run(debug=True) 