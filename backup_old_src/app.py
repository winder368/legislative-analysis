from flask import Flask, render_template, request, jsonify
from database import Database
from bill_utils import get_popular_bills_sql, clean_law_name
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
                    # 構建顯示用的條號文字
                    display_text = f"第{number}條" + (f"之{sub_number}" if sub_number > 0 else "")
                    articles.append({
                        'number': number,
                        'sub_number': sub_number,
                        'full_text': display_text
                    })
    
    return articles

def get_party_info(proposers):
    """根據提案委員判斷政黨"""
    if not proposers:
        return 'other', '其他'
    
    # 查詢每個提案委員的政黨
    db = Database()
    try:
        cursor = db.conn.cursor()
        party_counts = defaultdict(int)
        
        for proposer in proposers.split('、'):
            proposer = proposer.strip()
            if proposer:
                cursor.execute("""
                    SELECT party 
                    FROM legislators 
                    WHERE name = ? 
                    ORDER BY term DESC 
                    LIMIT 1
                """, (proposer,))
                result = cursor.fetchone()
                if result and result['party']:
                    party_counts[result['party']] += 1
        
        if not party_counts:
            return 'other', '其他'
        
        # 找出最多的政黨
        majority_party = max(party_counts.items(), key=lambda x: x[1])[0]
        
        # 政黨對應表
        party_map = {
            '中國國民黨': ('kmt', '國民黨'),
            '民主進步黨': ('dpp', '民進黨'),
            '台灣民眾黨': ('tpp', '民眾黨'),
            '時代力量': ('npp', '時代力量'),
            '新黨': ('np', '新黨'),
            '台灣基進': ('tsp', '台灣基進')
        }
        
        return party_map.get(majority_party, ('other', '其他'))
    finally:
        db.close()

@app.route('/')
def index():
    """首頁"""
    print("正在載入首頁...")
    db = Database()
    try:
        # 獲取所有屆別
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT term FROM bills ORDER BY CAST(term AS INTEGER) DESC")
        terms = [row['term'] for row in cursor.fetchall()]
        print(f"找到的屆別: {terms}")
        
        # 獲取第11屆最熱門的30個法律
        cursor.execute(get_popular_bills_sql())
        popular_bills = [dict(row) for row in cursor.fetchall()]
        print(f"找到的熱門法案數量: {len(popular_bills)}")
        
        return render_template('index.html', terms=terms, popular_bills=popular_bills)
    except Exception as e:
        print(f"載入首頁時發生錯誤: {str(e)}")
        return render_template('index.html', terms=[], popular_bills=[], error=str(e))
    finally:
        db.close()

@app.route('/search')
def search():
    """搜尋法案"""
    law_name = request.args.get('law_name', '')
    term = request.args.get('term', '')
    
    if not law_name:
        return render_template('search_results.html', 
                             law_name='',
                             message='請輸入法律名稱',
                             articles=[],
                             total=0)
    
    db = Database()
    try:
        # 搜尋相關法案
        cursor = db.conn.cursor()
        
        # 構建搜尋條件
        base_name = law_name.strip('「」')  # 移除可能的引號
        
        # 特殊處理刑法相關搜尋
        if base_name == '中華民國刑法':
            search_condition = "billName LIKE '%刑法%' AND billName NOT LIKE '%陸海空軍刑法%'"
        else:
            search_condition = "billName LIKE ?"
            base_name = f"%{base_name}%"
        
        # 添加屆別條件
        if term:
            search_condition += " AND term = ?"
            params = (base_name, term) if base_name != '中華民國刑法' else (term,)
        else:
            params = (base_name,) if base_name != '中華民國刑法' else tuple()
        
        # 執行查詢
        query = f"""
        SELECT billNo, billName, billOrg, billProposer, billCosignatory, 
               term, sessionPeriod, sessionTimes, billStatus, pdfUrl, docUrl
        FROM bills 
        WHERE {search_condition}
        ORDER BY 
            CAST(term AS INTEGER) DESC,
            CAST(sessionPeriod AS INTEGER) DESC,
            COALESCE(CAST(sessionTimes AS INTEGER), 0) DESC,
            billNo DESC
        """
        
        cursor.execute(query, params)
        # 將查詢結果轉換為字典列表
        bills = [dict(row) for row in cursor.fetchall()]
        
        # 處理搜尋結果
        articles_dict = defaultdict(lambda: {'bills': [], 'bills_count': 0})
        
        for bill in bills:
            # 提取條號
            articles = extract_article_numbers(bill['billName'])
            
            # 處理政黨資訊
            if bill['billOrg']:
                bill['party_class'] = 'org-tag'
            else:
                party_class, party_name = get_party_info(bill['billProposer'])
                bill['party_class'] = party_class
            
            # 如果沒有找到條號，使用預設值
            if not articles:
                key = '其他修正'
                articles_dict[key]['bills'].append(bill)
                articles_dict[key]['bills_count'] += 1
                continue
            
            # 將法案加入對應的條號
            for article in articles:
                key = article['full_text']
                articles_dict[key]['bills'].append(bill)
                articles_dict[key]['bills_count'] += 1
        
        # 轉換為列表並排序
        articles_list = []
        for article_text, data in articles_dict.items():
            articles_list.append({
                'article': article_text,
                'bills': data['bills'],
                'bills_count': data['bills_count']
            })
        
        # 根據條號排序
        def get_sort_key(article):
            if article['article'] == '其他修正':
                return (float('inf'), 0)
            match = re.search(r'第(\d+)條(?:之(\d+))?', article['article'])
            if match:
                number = int(match.group(1))
                sub_number = int(match.group(2)) if match.group(2) else 0
                return (number, sub_number)
            return (float('inf'), 0)
        
        articles_list.sort(key=get_sort_key)
        
        return render_template('search_results.html',
                             law_name=clean_law_name(law_name),
                             articles=articles_list,
                             total=len(bills))
    except Exception as e:
        print(f"搜尋時發生錯誤: {str(e)}")
        return render_template('search_results.html',
                             law_name=clean_law_name(law_name),
                             message=f'搜尋時發生錯誤: {str(e)}',
                             articles=[],
                             total=0)
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