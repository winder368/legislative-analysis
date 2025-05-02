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
        if char not in cn_num and char not in ['百', '千', '萬', '零']:
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

    # 處理帶「千」的數字
    if '千' in cn_str:
        parts = cn_str.split('千')
        base = cn_num[parts[0]] * 1000
        if not parts[1]:
            return base
        if parts[1].startswith('零'):
            # 處理「一千零八」這樣的情況
            remaining = parts[1][1:]
            if remaining:
                return base + cn_to_arab(remaining)
            return base
        return base + cn_to_arab(parts[1])
        
    # 處理帶「百」的數字
    if '百' in cn_str:
        parts = cn_str.split('百')
        base = cn_num[parts[0]] * 100
        if not parts[1]:
            return base
        if parts[1].startswith('零'):
            remaining = parts[1][1:]
            if remaining:
                return base + cn_to_arab(remaining)
            return base
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

def normalize_name(name: str) -> str:
    """標準化人名格式
    
    Args:
        name: 原始人名
        
    Returns:
        str: 標準化後的人名
    """
    # 移除全形空格
    name = name.replace('　', '')
    # 移除半形空格
    name = name.replace(' ', '')
    # 移除換行符號
    name = name.replace('\n', '')
    return name

def extract_names(names_str: str) -> list:
    """從字串中提取人名列表
    
    Args:
        names_str: 包含多個姓名的字串
        
    Returns:
        list: 人名列表
    """
    if not names_str:
        return []
    
    # 移除全形空格和換行符號
    names_str = names_str.replace('　', ' ').replace('\n', ' ')
    
    # 使用正則表達式匹配人名
    # 匹配模式：
    # 1. 中文名字（2-4個中文字）
    # 2. 原住民名字（中文+英文）
    # 3. 英文名字
    name_pattern = r'([\u4e00-\u9fa5]{2,4}(?:[A-Za-z]+)?)|([A-Za-z]+)'
    matches = re.finditer(name_pattern, names_str)
    
    names = []
    for match in matches:
        name = match.group(0).strip()
        if name and len(name) >= 2:  # 確保名字至少有2個字
            names.append(name)
    
    # 如果沒有找到任何名字，嘗試使用分隔符號分割
    if not names:
        for sep in ['、', '，', ',', ' ']:
            if sep in names_str:
                parts = [part.strip() for part in names_str.split(sep)]
                names.extend([part for part in parts if part and len(part) >= 2])
                break
    
    # 移除重複的名字
    return list(dict.fromkeys(names))

def count_party_members(names_str: str) -> dict:
    """統計名單中各黨籍人數
    
    Args:
        names_str: 包含多個姓名的字串
        
    Returns:
        dict: 各黨籍人數統計
    """
    if not names_str:
        return {}
        
    # 立委黨籍對照表（第11屆）
    legislators = {
        # 民進黨籍立委
        '伍麗華': '民進黨', '何欣純': '民進黨', '劉建國': '民進黨', '吳思瑤': '民進黨',
        '吳沛憶': '民進黨', '吳琪銘': '民進黨', '吳秉叡': '民進黨', '張宏陸': '民進黨',
        '張雅琳': '民進黨', '徐富癸': '民進黨', '李坤城': '民進黨', '李昆澤': '民進黨',
        '李柏毅': '民進黨', '林俊憲': '民進黨', '林宜瑾': '民進黨', '林岱樺': '民進黨',
        '林月琴': '民進黨', '林楚茵': '民進黨', '林淑芬': '民進黨', '柯建銘': '民進黨',
        '楊曜': '民進黨', '沈伯洋': '民進黨', '沈發惠': '民進黨', '洪申翰': '民進黨',
        '游錫堃': '民進黨', '王世堅': '民進黨', '王定宇': '民進黨', '王正旭': '民進黨',
        '王美惠': '民進黨', '王義川': '民進黨', '羅美玲': '民進黨', '范雲': '民進黨',
        '莊瑞雄': '民進黨', '蔡其昌': '民進黨', '蔡易餘': '民進黨', '蘇巧慧': '民進黨',
        '許智傑': '民進黨', '賴惠員': '民進黨', '賴瑞隆': '民進黨', '邱志偉': '民進黨',
        '邱議瑩': '民進黨', '郭國文': '民進黨', '郭昱晴': '民進黨', '鍾佳濱': '民進黨',
        '陳亭妃': '民進黨', '陳俊宇': '民進黨', '陳冠廷': '民進黨', '陳培瑜': '民進黨',
        '陳瑩': '民進黨', '陳秀寳': '民進黨', '陳素月': '民進黨', '黃捷': '民進黨',
        '黃秀芳': '民進黨',
        
        # 國民黨籍立委
        '丁學忠': '國民黨', '傅崐萁': '國民黨', '吳宗憲': '國民黨', '呂玉玲': '國民黨',
        '廖偉翔': '國民黨', '廖先翔': '國民黨', '張嘉郡': '國民黨', '張智倫': '國民黨',
        '徐巧芯': '國民黨', '徐欣瑩': '國民黨', '李彥秀': '國民黨', '林倩綺': '國民黨',
        '林德福': '國民黨', '林思銘': '國民黨', '林沛祥': '國民黨', '柯志恩': '國民黨',
        '楊瓊瓔': '國民黨', '江啟臣': '國民黨', '洪孟楷': '國民黨', '涂權吉': '國民黨',
        '游顥': '國民黨', '牛煦庭': '國民黨', '王育敏': '國民黨', '王鴻薇': '國民黨',
        '盧縣一': '國民黨', '羅廷瑋': '國民黨', '羅明才': '國民黨', '羅智強': '國民黨',
        '翁曉玲': '國民黨', '萬美玲': '國民黨', '葉元之': '國民黨', '葛如鈞': '國民黨',
        '蘇清泉': '國民黨', '許宇甄': '國民黨', '謝衣鳯': '國民黨', '謝龍介': '國民黨',
        '賴士葆': '國民黨', '邱若華': '國民黨', '邱鎮軍': '國民黨', '鄭天財': '國民黨',
        '鄭正鈐': '國民黨', '陳永康': '國民黨', '陳玉珍': '國民黨', '陳菁徽': '國民黨',
        '陳雪生': '國民黨', '韓國瑜': '國民黨', '顏寬恒': '國民黨', '馬文君': '國民黨',
        '魯明哲': '國民黨', '黃仁': '國民黨', '黃健豪': '國民黨', '黃建賓': '國民黨',
        
        # 民眾黨籍立委
        '劉書彬': '民眾黨', '吳春城': '民眾黨', '張啓楷': '民眾黨', '林國成': '民眾黨',
        '林憶君': '民眾黨', '陳昭姿': '民眾黨', '麥玉珍': '民眾黨', '黃國昌': '民眾黨',
        '黃珊珊': '民眾黨',
        
        # 無黨籍立委
        '陳超明': '無黨籍', '高金素梅': '無黨籍'
    }
    
    # 初始化計數器
    party_counts = {
        '民進黨': 0,
        '國民黨': 0,
        '民眾黨': 0,
        '無黨籍': 0,
        '其他': 0
    }
    
    # 提取並標準化人名
    names = extract_names(names_str)
    
    # 計算各黨籍人數
    for name in names:
        if name in legislators:
            party = legislators[name]
            party_counts[party] += 1
        else:
            party_counts['其他'] += 1
            
    # 移除計數為0的政黨
    return {k: v for k, v in party_counts.items() if v > 0}

def get_party_info(proposer: str, org: str = None) -> dict:
    """從提案人或提案機關資訊中獲取政黨資訊
    
    Args:
        proposer: 提案人資訊
        org: 提案機關資訊
        
    Returns:
        dict: 包含標籤類別和各黨人數統計的字典
    """
    result = {
        'tag_class': 'unknown-tag',
        'tag_name': '',
        'proposer_parties': {},
        'cosignatory_parties': {}
    }
    
    # 如果是行政院或黨團提案
    if org:
        if '行政院' in org:
            result['tag_class'] = 'org-tag'
            result['tag_name'] = '行政院'
        elif '民主進步黨' in org or '民進黨' in org:
            result['tag_class'] = 'dpp-tag'
            result['tag_name'] = '民進黨黨團'
        elif '中國國民黨' in org or '國民黨' in org:
            result['tag_class'] = 'kmt-tag'
            result['tag_name'] = '國民黨黨團'
        elif '台灣民眾黨' in org or '民眾黨' in org:
            result['tag_class'] = 'tpp-tag'
            result['tag_name'] = '民眾黨黨團'
        elif '時代力量' in org:
            result['tag_class'] = 'npp-tag'
            result['tag_name'] = '時代力量黨團'
        elif '台灣基進' in org:
            result['tag_class'] = 'other-tag'
            result['tag_name'] = '台灣基進黨團'
        return result
        
    if not proposer:
        return result
        
    # 統計提案人政黨分布
    result['proposer_parties'] = count_party_members(proposer)
    
    # 根據最多數的政黨設定標籤
    if result['proposer_parties']:
        max_party = max(result['proposer_parties'].items(), key=lambda x: x[1])[0]
        if max_party == '民進黨':
            result['tag_class'] = 'dpp-tag'
            result['tag_name'] = '民進黨'
        elif max_party == '國民黨':
            result['tag_class'] = 'kmt-tag'
            result['tag_name'] = '國民黨'
        elif max_party == '民眾黨':
            result['tag_class'] = 'tpp-tag'
            result['tag_name'] = '民眾黨'
        elif max_party == '無黨籍':
            result['tag_class'] = 'other-tag'
            result['tag_name'] = '無黨籍'
            
    return result

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

def get_status_group(status: str) -> str:
    """根據審查進度獲取分組名稱
    
    Args:
        status: 審查進度
        
    Returns:
        str: 分組名稱
    """
    if not status:
        return '待審查'
    if '三讀' in status:
        return '三讀'
    if '二讀' in status:
        return '二讀'
    if '一讀' in status:
        return '一讀'
    if '審查完畢' in status:
        return '審查完畢'
    if '審查' in status:
        return '委員會審查'
    if '退回' in status or '撤回' in status:
        return '退回/撤回'
    return '待審查'

def get_member_info(name: str) -> dict:
    """獲取成員的政黨資訊
    
    Args:
        name: 成員姓名
        
    Returns:
        dict: 包含成員姓名和政黨標籤的字典
    """
    # 立委黨籍對照表（第11屆）
    legislators = {
        # 民進黨籍立委
        '伍麗華': '民進黨', '何欣純': '民進黨', '劉建國': '民進黨', '吳思瑤': '民進黨',
        '吳沛憶': '民進黨', '吳琪銘': '民進黨', '吳秉叡': '民進黨', '張宏陸': '民進黨',
        '張雅琳': '民進黨', '徐富癸': '民進黨', '李坤城': '民進黨', '李昆澤': '民進黨',
        '李柏毅': '民進黨', '林俊憲': '民進黨', '林宜瑾': '民進黨', '林岱樺': '民進黨',
        '林月琴': '民進黨', '林楚茵': '民進黨', '林淑芬': '民進黨', '柯建銘': '民進黨',
        '楊曜': '民進黨', '沈伯洋': '民進黨', '沈發惠': '民進黨', '洪申翰': '民進黨',
        '游錫堃': '民進黨', '王世堅': '民進黨', '王定宇': '民進黨', '王正旭': '民進黨',
        '王美惠': '民進黨', '王義川': '民進黨', '羅美玲': '民進黨', '范雲': '民進黨',
        '莊瑞雄': '民進黨', '蔡其昌': '民進黨', '蔡易餘': '民進黨', '蘇巧慧': '民進黨',
        '許智傑': '民進黨', '賴惠員': '民進黨', '賴瑞隆': '民進黨', '邱志偉': '民進黨',
        '邱議瑩': '民進黨', '郭國文': '民進黨', '郭昱晴': '民進黨', '鍾佳濱': '民進黨',
        '陳亭妃': '民進黨', '陳俊宇': '民進黨', '陳冠廷': '民進黨', '陳培瑜': '民進黨',
        '陳瑩': '民進黨', '陳秀寳': '民進黨', '陳素月': '民進黨', '黃捷': '民進黨',
        '黃秀芳': '民進黨',
        
        # 國民黨籍立委
        '丁學忠': '國民黨', '傅崐萁': '國民黨', '吳宗憲': '國民黨', '呂玉玲': '國民黨',
        '廖偉翔': '國民黨', '廖先翔': '國民黨', '張嘉郡': '國民黨', '張智倫': '國民黨',
        '徐巧芯': '國民黨', '徐欣瑩': '國民黨', '李彥秀': '國民黨', '林倩綺': '國民黨',
        '林德福': '國民黨', '林思銘': '國民黨', '林沛祥': '國民黨', '柯志恩': '國民黨',
        '楊瓊瓔': '國民黨', '江啟臣': '國民黨', '洪孟楷': '國民黨', '涂權吉': '國民黨',
        '游顥': '國民黨', '牛煦庭': '國民黨', '王育敏': '國民黨', '王鴻薇': '國民黨',
        '盧縣一': '國民黨', '羅廷瑋': '國民黨', '羅明才': '國民黨', '羅智強': '國民黨',
        '翁曉玲': '國民黨', '萬美玲': '國民黨', '葉元之': '國民黨', '葛如鈞': '國民黨',
        '蘇清泉': '國民黨', '許宇甄': '國民黨', '謝衣鳯': '國民黨', '謝龍介': '國民黨',
        '賴士葆': '國民黨', '邱若華': '國民黨', '邱鎮軍': '國民黨', '鄭天財': '國民黨',
        '鄭正鈐': '國民黨', '陳永康': '國民黨', '陳玉珍': '國民黨', '陳菁徽': '國民黨',
        '陳雪生': '國民黨', '韓國瑜': '國民黨', '顏寬恒': '國民黨', '馬文君': '國民黨',
        '魯明哲': '國民黨', '黃仁': '國民黨', '黃健豪': '國民黨', '黃建賓': '國民黨',
        
        # 民眾黨籍立委
        '劉書彬': '民眾黨', '吳春城': '民眾黨', '張啓楷': '民眾黨', '林國成': '民眾黨',
        '林憶君': '民眾黨', '陳昭姿': '民眾黨', '麥玉珍': '民眾黨', '黃國昌': '民眾黨',
        '黃珊珊': '民眾黨',
        
        # 無黨籍立委
        '陳超明': '無黨籍', '高金素梅': '無黨籍'
    }
    
    name = normalize_name(name)
    if name in legislators:
        party = legislators[name]
        if party == '民進黨':
            return {'name': name, 'party_class': 'dpp'}
        elif party == '國民黨':
            return {'name': name, 'party_class': 'kmt'}
        elif party == '民眾黨':
            return {'name': name, 'party_class': 'tpp'}
        else:
            return {'name': name, 'party_class': 'other'}
    
    return {'name': name, 'party_class': 'other'}

def process_members(bill: dict) -> dict:
    """處理法案的提案人和連署人資訊
    
    Args:
        bill: 法案資訊字典
        
    Returns:
        dict: 包含成員列表和政黨統計的字典
    """
    members = []
    party_stats = {'民進黨': 0, '國民黨': 0, '民眾黨': 0, '其他': 0}
    
    # 處理提案機關
    if bill['billOrg']:
        if '行政院' in bill['billOrg']:
            members.append({'name': bill['billOrg'], 'party_class': 'org'})
            party_stats['其他'] += 1
        else:
            members.append({'name': bill['billOrg'], 'party_class': 'org'})
            party_stats['其他'] += 1
    
    # 處理提案人
    if bill['billProposer']:
        proposer_names = extract_names(bill['billProposer'])
        for name in proposer_names:
            member_info = get_member_info(name)
            members.append(member_info)
            if member_info['party_class'] == 'dpp':
                party_stats['民進黨'] += 1
            elif member_info['party_class'] == 'kmt':
                party_stats['國民黨'] += 1
            elif member_info['party_class'] == 'tpp':
                party_stats['民眾黨'] += 1
            else:
                party_stats['其他'] += 1
    
    # 處理連署人
    if bill['billCosignatory']:
        cosignatory_names = extract_names(bill['billCosignatory'])
        for name in cosignatory_names:
            member_info = get_member_info(name)
            members.append(member_info)
            if member_info['party_class'] == 'dpp':
                party_stats['民進黨'] += 1
            elif member_info['party_class'] == 'kmt':
                party_stats['國民黨'] += 1
            elif member_info['party_class'] == 'tpp':
                party_stats['民眾黨'] += 1
            else:
                party_stats['其他'] += 1
    
    # 移除計數為0的政黨
    party_stats = {k: v for k, v in party_stats.items() if v > 0}
    total = sum(party_stats.values())
    
    return {
        'members': members,
        'party_stats': party_stats,
        'total': total
    }

@app.route('/search', methods=['GET'])
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
        
        if sort_by == 'article':
            # 按條號分組
            articles_dict = defaultdict(lambda: {'bills': [], 'bills_count': 0})
            
            for bill in bills:
                print(f"處理法案: {bill['billName']}")
                # 提取條號
                articles = extract_article_numbers(bill['billName'])
                
                # 處理提案人和連署人資訊
                members_info = process_members(bill)
                bill['all_members'] = members_info['members']
                bill['party_stats'] = members_info['party_stats']
                bill['total_members'] = members_info['total']
                
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
            # 按審查進度分組
            status_groups = defaultdict(lambda: {'bills': [], 'bills_count': 0})
            
            for bill in bills:
                # 處理提案人和連署人資訊
                members_info = process_members(bill)
                bill['all_members'] = members_info['members']
                bill['party_stats'] = members_info['party_stats']
                bill['total_members'] = members_info['total']
                
                # 獲取審查進度分組
                status_group = get_status_group(bill.get('billStatus', ''))
                status_groups[status_group]['bills'].append(bill)
                status_groups[status_group]['bills_count'] += 1
            
            # 轉換為列表並排序
            articles_list = []
            status_order = ['三讀', '二讀', '一讀', '審查完畢', '委員會審查', '待審查', '退回/撤回']
            
            for status in status_order:
                if status in status_groups:
                    articles_list.append({
                        'article': status,
                        'bills': status_groups[status]['bills'],
                        'bills_count': status_groups[status]['bills_count']
                    })
        
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