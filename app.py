from flask import Flask, jsonify
from src.bill_utils import get_popular_bills_sql, clean_law_name
from src.db_config import get_db
from sqlalchemy import text

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "message": "法案分析系統 API",
        "status": "運作中"
    })

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
    app.run(debug=True) 