from flask import Flask, render_template, request, jsonify
from src.database import Database
from src.bill_utils import get_popular_bills_sql, clean_law_name
import re
import webbrowser
import threading
import time
from collections import defaultdict
import os

# 獲取當前腳本的目錄
current_dir = os.path.dirname(os.path.abspath(__file__))

# 設定模板目錄
template_dir = os.path.join(current_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)

def extract_article_numbers(bill_name: str) -> list:
    """從法案名稱中提取條號
    
    Args:
        bill_name: 法案名稱
        
    Returns:
        list: 條號列表，每個條號是一個字典，包含 full_text 和 number
    """
    articles = []
    
    # 搜尋「第X條」或「第X條之Y」的格式
    pattern = r'第(\d+)條(?:之(\d+))?'
    matches = re.finditer(pattern, bill_name)
    
    for match in matches:
        article_number = match.group(1)
        sub_number = match.group(2)
        
        if sub_number:
            full_text = f"第{article_number}條之{sub_number}"
        else:
            full_text = f"第{article_number}條"
            
        articles.append({
            'full_text': full_text,
            'number': int(article_number),
            'sub_number': int(sub_number) if sub_number else 0
        })
    
    return articles

def get_party_info(proposer: str) -> tuple:
    """從提案人資訊中獲取政黨資訊
    
    Args:
        proposer: 提案人資訊
        
    Returns:
        tuple: (政黨類別, 政黨名稱)
    """
    if not proposer:
        return 'unknown', ''
        
    # 政黨對照表
    parties = {
        '國民黨': ('kmt', '中國國民黨'),
        '民進黨': ('dpp', '民主進步黨'),
        '民眾黨': ('tpp', '台灣民眾黨'),
        '時代力量': ('npp', '時代力量'),
        '基進黨': ('npp', '台灣基進'),
        '新黨': ('npp', '新黨')
    }
    
    for key, (party_class, party_name) in parties.items():
        if key in proposer:
            return party_class, party_name
            
    return 'unknown', ''

@app.route('/')
def home():
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

@app.route('/api/popular-bills')
def popular_bills():
    try:
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute(get_popular_bills_sql())
        bills = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "message": "熱門法案列表",
            "data": bills
        })
    except Exception as e:
        return jsonify({
            "message": "發生錯誤",
            "error": str(e)
        }), 500
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=True) 