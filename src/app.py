from flask import Flask, render_template, request, jsonify
from database import Database
import re
import webbrowser
import threading
import time
from collections import defaultdict
import os

app = Flask(__name__)

def cn2num(cn_str):
    """將中文數字轉換為阿拉伯數字"""
    CN_NUM = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '〇': 0
    }
    
    if not cn_str:
        return 0
        
    # 處理特殊情況
    if cn_str == '十':
        return 10
    
    # 處理十幾、幾十的情況
    if '十' in cn_str:
        if len(cn_str) == 2:
            if cn_str.startswith('十'):
                return 10 + CN_NUM.get(cn_str[1], 0)
            else:
                return CN_NUM.get(cn_str[0], 0) * 10
        elif len(cn_str) == 3 and cn_str[1] == '十':
            return CN_NUM.get(cn_str[0], 0) * 10 + CN_NUM.get(cn_str[2], 0)
    
    # 處理一般情況
    result = 0
    unit = 1
    for i in range(len(cn_str) - 1, -1, -1):
        if cn_str[i] in ['百', '千']:
            unit = CN_NUM[cn_str[i]]
            if i == 0:
                result += unit
        elif cn_str[i] in CN_NUM:
            result += CN_NUM[cn_str[i]] * unit
            unit = 1
            
    return result

def open_browser():
    """在新執行緒中開啟瀏覽器"""
    time.sleep(1.5)  # 等待伺服器啟動
    webbrowser.open('http://127.0.0.1:5000/')

def extract_article_numbers(bill_name):
    """從法案名稱中提取條號"""
    # 匹配中文數字和阿拉伯數字的條號
    patterns = [
        r'第([零一二三四五六七八九十百千]+)條(?:之([零一二三四五六七八九十百千]+))?',  # 中文數字
        r'第(\d+)條(?:之(\d+))?'  # 阿拉伯數字
    ]
    
    articles = []
    for pattern in patterns:
        matches = re.finditer(pattern, bill_name)
        for match in matches:
            if match.group(1):
                # 判斷是否為阿拉伯數字
                if match.group(1).isdigit():
                    number = int(match.group(1))
                else:
                    number = cn2num(match.group(1))
                
                # 處理「之X」的部分
                sub_number = 0
                if match.group(2):
                    if match.group(2).isdigit():
                        sub_number = int(match.group(2))
                    else:
                        sub_number = cn2num(match.group(2))
                
                # 只有在成功轉換數字時才加入清單
                if number > 0:
                    articles.append({
                        'number': number,
                        'sub_number': sub_number,
                        'full_text': f"第{match.group(1)}條" + (f"之{match.group(2)}" if match.group(2) else "")
                    })
    
    return articles

@app.route('/')
def index():
    """首頁"""
    db = Database()
    try:
        # 獲取所有屆別
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT term FROM bills ORDER BY CAST(term AS INTEGER) DESC")
        terms = [row['term'] for row in cursor.fetchall()]
        return render_template('index.html', terms=terms)
    finally:
        db.close()

@app.route('/search')
def search():
    """搜尋法案"""
    law_name = request.args.get('law_name', '')
    term = request.args.get('term', '')
    
    if not law_name or not term:
        return jsonify({'error': '請輸入法律名稱並選擇屆別'})
    
    db = Database()
    try:
        # 搜尋相關法案
        cursor = db.conn.cursor()
        cursor.execute("""
        SELECT billName, term, sessionPeriod, sessionTimes, billNo, billStatus, pdfUrl, docUrl
        FROM bills 
        WHERE billName LIKE ? AND term = ?
        ORDER BY sessionPeriod DESC, sessionTimes DESC
        """, (f"%{law_name}%", term))
        
        # 用於儲存每個條號的資訊
        articles_dict = defaultdict(list)
        total_bills = 0
        
        # 處理每個法案
        for row in cursor.fetchall():
            bill = dict(row)
            total_bills += 1
            articles = extract_article_numbers(bill['billName'])
            
            # 如果沒有找到條號，將其歸類為「其他修正」
            if not articles:
                articles_dict['其他修正'].append(bill)
                continue
            
            # 將法案資訊加入對應的條號中
            for article in articles:
                articles_dict[article['full_text']].append(bill)
        
        # 將條號資訊轉換為列表並排序
        articles_list = []
        
        # 先處理有條號的法案
        numbered_articles = []
        for article_text, bills in articles_dict.items():
            if article_text != '其他修正':
                numbered_articles.append({
                    'article': article_text,
                    'bills_count': len(bills)
                })
        
        # 按照條號排序（使用 number 和 sub_number）
        def get_article_numbers(article_text):
            # 嘗試從條號中提取數字
            for pattern in [
                r'第([零一二三四五六七八九十百千]+)條(?:之([零一二三四五六七八九十百千]+))?',  # 中文數字
                r'第(\d+)條(?:之(\d+))?'  # 阿拉伯數字
            ]:
                match = re.search(pattern, article_text)
                if match:
                    main_num = match.group(1)
                    sub_num = match.group(2) or '0'
                    
                    # 轉換為數字
                    if main_num.isdigit():
                        main_num = int(main_num)
                    else:
                        main_num = cn2num(main_num)
                        
                    if sub_num.isdigit():
                        sub_num = int(sub_num)
                    else:
                        sub_num = cn2num(sub_num)
                        
                    return [main_num, sub_num]
            return [0, 0]  # 如果無法解析，返回 [0, 0]
        
        # 使用新的排序函數
        numbered_articles.sort(key=lambda x: get_article_numbers(x['article']))
        
        # 加入排序後的條號
        articles_list.extend(numbered_articles)
        
        # 最後加入其他修正
        if '其他修正' in articles_dict:
            articles_list.append({
                'article': '其他修正',
                'bills_count': len(articles_dict['其他修正'])
            })
        
        return jsonify({
            'articles': articles_list,
            'total': total_bills
        })
    finally:
        db.close()

@app.route('/article')
def article_details():
    """條號詳細資訊頁面"""
    law_name = request.args.get('law_name', '')
    term = request.args.get('term', '')
    article = request.args.get('article', '')
    
    if not law_name or not term or not article:
        return jsonify({'error': '參數不完整'})
    
    db = Database()
    try:
        # 搜尋相關法案
        cursor = db.conn.cursor()
        cursor.execute("""
        SELECT billName, term, sessionPeriod, sessionTimes, billNo, billStatus, 
               pdfUrl, docUrl, billProposer, billCosignatory
        FROM bills 
        WHERE billName LIKE ? AND term = ?
        ORDER BY sessionPeriod DESC, sessionTimes DESC
        """, (f"%{law_name}%", term))
        
        # 篩選法案
        bills = []
        for row in cursor.fetchall():
            bill = dict(row)
            if article == '其他修正':
                # 如果是其他修正，則檢查是否不包含任何條號
                articles = extract_article_numbers(bill['billName'])
                if not articles:
                    bills.append(bill)
            else:
                # 如果是特定條號，則檢查是否包含該條號
                articles = extract_article_numbers(bill['billName'])
                if any(a['full_text'] == article for a in articles):
                    bills.append(bill)
            
            # 處理提案人和連署人
            if bill.get('billProposer'):
                bill['proposers'] = [p.strip() for p in bill['billProposer'].split('、') if p.strip()]
            else:
                bill['proposers'] = []
                
            if bill.get('billCosignatory'):
                bill['cosigners'] = [c.strip() for c in bill['billCosignatory'].split('、') if c.strip()]
            else:
                bill['cosigners'] = []
        
        return render_template('article.html', 
                             article=article,
                             law_name=law_name,
                             term=term,
                             bills=bills)
    finally:
        db.close()

if __name__ == '__main__':
    # 只在本地開發時自動開啟瀏覽器
    if os.environ.get('FLASK_ENV') != 'production':
        threading.Thread(target=open_browser).start()
        print("正在啟動網頁應用程式...")
        print("請稍候，瀏覽器將自動開啟...")
        app.run(debug=True)
    else:
        # 生產環境使用 gunicorn
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000))) 