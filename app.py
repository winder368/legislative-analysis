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

def cn_to_arab(cn_str):
    """將中文數字轉換為阿拉伯數字
    
    Args:
        cn_str: 中文數字字串
        
    Returns:
        int: 阿拉伯數字
    """
    # 中文數字對照表
    cn_num = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '萬': 10000,
        '０': 0, '１': 1, '２': 2, '３': 3, '４': 4, '５': 5,
        '６': 6, '７': 7, '８': 8, '９': 9
    }
    
    # 如果是純數字，直接返回
    if cn_str.isdigit():
        return int(cn_str)
        
    # 如果字串中包含非中文數字，返回原始字串
    for char in cn_str:
        if char not in cn_num and char not in ['百', '千', '萬']:
            return cn_str
            
    # 處理特殊情況
    if not cn_str:
        return 0
        
    # 處理一位數
    if len(cn_str) == 1:
        return cn_num.get(cn_str, cn_str)
        
    # 處理「十」開頭的數字
    if cn_str.startswith('十'):
        if len(cn_str) == 1:
            return 10
        return 10 + cn_to_arab(cn_str[1:])
        
    # 處理帶「百」的數字
    if '百' in cn_str:
        parts = cn_str.split('百')
        base = cn_num[parts[0]] * 100
        if not parts[1]:
            return base
        if parts[1].startswith('零'):
            return base + cn_to_arab(parts[1][1:])
        return base + cn_to_arab(parts[1])
        
    # 處理帶「十」的數字
    if '十' in cn_str:
        parts = cn_str.split('十')
        base = cn_num[parts[0]] * 10
        if not parts[1]:
            return base
        return base + cn_num[parts[1]]
        
    # 處理其他情況
    return cn_num.get(cn_str, cn_str)

def extract_article_numbers(bill_name: str) -> list:
    """從法案名稱中提取條號
    
    Args:
        bill_name: 法案名稱
        
    Returns:
        list: 條號列表，每個條號是一個字典，包含 full_text 和 number
    """
    articles = []
    
    # 處理中文數字的條號，如「第二條及第三條」
    cn_pattern = r'第([零一二三四五六七八九十百千萬０１２３４５６７８９]+)條(?:之([零一二三四五六七八九十百千萬０１２３４５６７８９]+))?(?:及|、|，|和|暨)第([零一二三四五六七八九十百千萬０１２３４５６７８９]+)條(?:之([零一二三四五六七八九十百千萬０１２３４５６７８９]+))?'
    cn_matches = re.finditer(cn_pattern, bill_name)
    
    for match in cn_matches:
        # 第一個條號
        first_number = cn_to_arab(match.group(1))
        if isinstance(first_number, str):
            continue
        first_sub = cn_to_arab(match.group(2)) if match.group(2) else 0
        if isinstance(first_sub, str):
            first_sub = 0
        
        if first_sub:
            first_text = f"第{first_number}條之{first_sub}"
        else:
            first_text = f"第{first_number}條"
            
        articles.append({
            'full_text': first_text,
            'number': first_number,
            'sub_number': first_sub
        })
        
        # 第二個條號
        second_number = cn_to_arab(match.group(3))
        if isinstance(second_number, str):
            continue
        second_sub = cn_to_arab(match.group(4)) if match.group(4) else 0
        if isinstance(second_sub, str):
            second_sub = 0
        
        if second_sub:
            second_text = f"第{second_number}條之{second_sub}"
        else:
            second_text = f"第{second_number}條"
            
        articles.append({
            'full_text': second_text,
            'number': second_number,
            'sub_number': second_sub
        })
    
    # 處理單一中文數字條號，如「第二條」
    cn_single_pattern = r'第([零一二三四五六七八九十百千萬０１２３４５６７８９]+)條(?:之([零一二三四五六七八九十百千萬０１２３４５６７８９]+))?'
    cn_single_matches = re.finditer(cn_single_pattern, bill_name)
    
    for match in cn_single_matches:
        number = cn_to_arab(match.group(1))
        if isinstance(number, str):
            continue
        sub_number = cn_to_arab(match.group(2)) if match.group(2) else 0
        if isinstance(sub_number, str):
            sub_number = 0
        
        # 檢查是否已經在多條模式中處理過
        already_processed = False
        for article in articles:
            if article['number'] == number and article['sub_number'] == sub_number:
                already_processed = True
                break
                
        if already_processed:
            continue
            
        if sub_number:
            full_text = f"第{number}條之{sub_number}"
        else:
            full_text = f"第{number}條"
            
        articles.append({
            'full_text': full_text,
            'number': number,
            'sub_number': sub_number
        })
    
    # 處理阿拉伯數字條號，如「第1條及第2條」
    arab_pattern = r'第(\d+)條(?:之(\d+))?(?:及|、|，|和|暨)第(\d+)條(?:之(\d+))?'
    arab_matches = re.finditer(arab_pattern, bill_name)
    
    for match in arab_matches:
        # 第一個條號
        first_number = int(match.group(1))
        first_sub = int(match.group(2)) if match.group(2) else 0
        
        # 檢查是否已經處理過
        already_processed = False
        for article in articles:
            if article['number'] == first_number and article['sub_number'] == first_sub:
                already_processed = True
                break
                
        if not already_processed:
            if first_sub:
                first_text = f"第{first_number}條之{first_sub}"
            else:
                first_text = f"第{first_number}條"
                
            articles.append({
                'full_text': first_text,
                'number': first_number,
                'sub_number': first_sub
            })
        
        # 第二個條號
        second_number = int(match.group(3))
        second_sub = int(match.group(4)) if match.group(4) else 0
        
        # 檢查是否已經處理過
        already_processed = False
        for article in articles:
            if article['number'] == second_number and article['sub_number'] == second_sub:
                already_processed = True
                break
                
        if not already_processed:
            if second_sub:
                second_text = f"第{second_number}條之{second_sub}"
            else:
                second_text = f"第{second_number}條"
                
            articles.append({
                'full_text': second_text,
                'number': second_number,
                'sub_number': second_sub
            })
    
    # 處理單一阿拉伯數字條號，如「第1條」
    arab_single_pattern = r'第(\d+)條(?:之(\d+))?'
    arab_single_matches = re.finditer(arab_single_pattern, bill_name)
    
    for match in arab_single_matches:
        number = int(match.group(1))
        sub_number = int(match.group(2)) if match.group(2) else 0
        
        # 檢查是否已經處理過
        already_processed = False
        for article in articles:
            if article['number'] == number and article['sub_number'] == sub_number:
                already_processed = True
                break
                
        if already_processed:
            continue
            
        if sub_number:
            full_text = f"第{number}條之{sub_number}"
        else:
            full_text = f"第{number}條"
            
        articles.append({
            'full_text': full_text,
            'number': number,
            'sub_number': sub_number
        })
    
    # 處理中文區間條號，如「第一條至第十條」
    cn_range_pattern = r'第([零一二三四五六七八九十百千萬０１２３４５６７８９]+)條至第([零一二三四五六七八九十百千萬０１２３４５６７８９]+)條'
    cn_range_matches = re.finditer(cn_range_pattern, bill_name)
    
    for match in cn_range_matches:
        start_number = cn_to_arab(match.group(1))
        end_number = cn_to_arab(match.group(2))
        
        for num in range(start_number, end_number + 1):
            # 檢查是否已經處理過
            already_processed = False
            for article in articles:
                if article['number'] == num and article['sub_number'] == 0:
                    already_processed = True
                    break
                    
            if already_processed:
                continue
                
            full_text = f"第{num}條"
            articles.append({
                'full_text': full_text,
                'number': num,
                'sub_number': 0
            })
    
    # 處理阿拉伯數字區間條號，如「第1條至第10條」
    arab_range_pattern = r'第(\d+)條至第(\d+)條'
    arab_range_matches = re.finditer(arab_range_pattern, bill_name)
    
    for match in arab_range_matches:
        start_number = int(match.group(1))
        end_number = int(match.group(2))
        
        for num in range(start_number, end_number + 1):
            # 檢查是否已經處理過
            already_processed = False
            for article in articles:
                if article['number'] == num and article['sub_number'] == 0:
                    already_processed = True
                    break
                    
            if already_processed:
                continue
                
            full_text = f"第{num}條"
            articles.append({
                'full_text': full_text,
                'number': num,
                'sub_number': 0
            })
    
    # 打印調試信息
    print(f"從 '{bill_name}' 提取條號: {[a['full_text'] for a in articles]}")
    
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

def get_bill_type(bill_name: str) -> str:
    """判斷法案類型
    
    Args:
        bill_name: 法案名稱
        
    Returns:
        str: 法案類型（modify/add/delete/abolish）
    """
    if '廢止' in bill_name:
        return 'abolish'
    elif '增訂' in bill_name:
        return 'add'
    elif '刪除' in bill_name:
        return 'delete'
    else:
        return 'modify'

# 將函數添加到模板全局變數中
app.jinja_env.globals.update(get_bill_type=get_bill_type)

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
    sort_by = request.args.get('sort_by', 'article')  # 預設按條號排序
    
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
        
        # 特殊處理某些法案
        if '刑法' in base_name and '陸海空軍刑法' not in base_name:
            search_condition = "billName LIKE '%中華民國刑法%' AND billName NOT LIKE '%施行法%' AND billName NOT LIKE '%陸海空軍刑法%'"
            params = tuple()
        elif base_name == '民法':
            search_condition = "billName LIKE '%民法%' AND billName NOT LIKE '%施行法%'"
            params = tuple()
        else:
            # 一般法律搜尋
            search_condition = "billName LIKE ? AND billName NOT LIKE '%施行法%'"
            params = (f"%{base_name}%",)
        
        # 添加屆別條件
        if term:
            search_condition += " AND term = ?"
            params = params + (term,)
        
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
        bills = [dict(row) for row in cursor.fetchall()]
        
        print(f"搜尋 '{law_name}' 找到 {len(bills)} 個法案")
        
        # 處理搜尋結果
        articles_dict = defaultdict(lambda: {'bills': [], 'bills_count': 0})
        
        for bill in bills:
            print(f"處理法案: {bill['billName']}")
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
                print(f"  未找到條號，歸入「其他修正」")
                key = '其他修正'
                articles_dict[key]['bills'].append(bill)
                articles_dict[key]['bills_count'] += 1
                continue
            
            # 將法案加入對應的條號
            for article in articles:
                key = article['full_text']
                print(f"  加入條號 {key}")
                articles_dict[key]['bills'].append(bill)
                articles_dict[key]['bills_count'] += 1
        
        # 轉換為列表
        articles_list = []
        for article_text, data in articles_dict.items():
            articles_list.append({
                'article': article_text,
                'bills': data['bills'],
                'bills_count': data['bills_count']
            })
        
        # 根據排序方式進行排序
        if sort_by == 'article':
            # 按條號排序
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
        else:
            # 按審查進度排序
            def get_status_priority(status):
                if not status:
                    return 0
                if '三讀' in status:
                    return 7
                if '二讀' in status:
                    return 6
                if '一讀' in status:
                    return 5
                if '審查完畢' in status:
                    return 4
                if '審查' in status:
                    return 3
                if '退回' in status or '撤回' in status:
                    return 1
                return 2
            
            # 將每個條號下的法案按狀態排序
            for article in articles_list:
                article['bills'].sort(
                    key=lambda x: (
                        get_status_priority(x.get('billStatus')),
                        int(x.get('term', 0)),
                        int(x.get('sessionPeriod', 0)),
                        int(x.get('sessionTimes', 0) or 0)
                    ),
                    reverse=True
                )
            
            # 將條號群組按其中最高優先級的法案狀態排序
            articles_list.sort(
                key=lambda x: max(
                    (get_status_priority(bill.get('billStatus')) for bill in x['bills']),
                    default=0
                ),
                reverse=True
            )
        
        return render_template('search_results.html',
                             law_name=clean_law_name(law_name),
                             articles=articles_list,
                             total=len(bills),
                             sort_by=sort_by)
    except Exception as e:
        print(f"搜尋時發生錯誤: {str(e)}")
        return render_template('search_results.html',
                             law_name=clean_law_name(law_name),
                             message=f'搜尋時發生錯誤: {str(e)}',
                             articles=[],
                             total=0,
                             sort_by=sort_by)
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