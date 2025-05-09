import streamlit as st
import sqlite3
from src.database import Database
from src.bill_utils import get_popular_bills_sql, clean_law_name
import re
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from st_utils import (
    extract_article_numbers, 
    get_status_group, 
    get_bill_type, 
    process_members,
    display_party_statistics,
    count_party_members,
    format_members_with_party_colors
)

# 設置 matplotlib 支援中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Microsoft YaHei', 'SimHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False  # 解決負號顯示問題

# 設置頁面標題
st.set_page_config(page_title="立法院法案分析", page_icon="📜", layout="wide")

# 自定義CSS來增大文字尺寸和設置按鈕顏色
st.markdown("""
<style>
    html, body, [class*="st-"] {
        font-size: 18px !important;
    }
    .stButton button {
        font-size: 16px !important;
    }
    .stSelectbox, .stMultiSelect {
        font-size: 16px !important;
    }
    h1 {
        font-size: 2.5rem !important;
    }
    h2 {
        font-size: 2rem !important;
    }
    h3 {
        font-size: 1.7rem !important;
    }
    p, div, span, label {
        font-size: 18px !important;
    }
    .stExpander {
        font-size: 18px !important;
    }
    .stExpander > div {
        font-size: 18px !important;
    }
    /* 修改國民黨標籤顏色 */
    .party-tag-kmt {
        background-color: #1B54B3 !important;
        color: white !important;
    }
    
    /* 政府機關按鈕樣式 */
    .gov-button button {
        background-color: #F08080 !important;
        color: black !important; 
        border: 1px solid rgba(0,0,0,0.1) !important;
    }
    
    /* 民進黨按鈕樣式 */
    .dpp-button button {
        background-color: #45B035 !important;
        color: black !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
    }
    
    /* 國民黨按鈕樣式 */
    .kmt-button button {
        background-color: #1B54B3 !important;
        color: white !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
    }
    
    /* 民眾黨按鈕樣式 */
    .tpp-button button {
        background-color: #27B8CC !important;
        color: black !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
    }
    
    /* 時代力量按鈕樣式 */
    .npp-button button {
        background-color: #FFD035 !important;
        color: black !important;
        border: 1px solid rgba(0,0,0,0.1) !important;
    }
</style>
""", unsafe_allow_html=True)

# 定義函數
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

def advanced_clean_law_name(bill_name: str, proposer_type: str = None) -> str:
    """更精確地清理法案名稱，考慮提案者類型
    
    Args:
        bill_name: 法案名稱
        proposer_type: 提案者類型 (government, party_group, legislator)
        
    Returns:
        str: 清理後的法案名稱
    """
    # 針對行政院提案的特殊處理
    if proposer_type == 'government':
        # 公務人員相關法規
        if '公務人員保障暨培訓委員會組織法' in bill_name or '公務人員保障訓練委員會組織法' in bill_name:
            return '公務人員保障暨培訓委員會組織法'
        elif '公務人員保障法施行細則' in bill_name:
            return '公務人員保障法施行細則'
        elif '公務人員考試法' in bill_name:
            return '公務人員考試法'
        elif '公務人員任用法' in bill_name:
            return '公務人員任用法'
            
        # 組織改造相關
        elif '行政院功能業務與組織調整' in bill_name:
            return '行政院組織改造'
        elif '考試院組織法' in bill_name or '考試院組織條例' in bill_name:
            return '考試院組織法'
        elif '考選部組織法' in bill_name:
            return '考選部組織法'
        elif '銓敘部組織法' in bill_name:
            return '銓敘部組織法'
        elif '公務人員退休撫卹基金管理委員會組織條例' in bill_name:
            return '公務人員退休撫卹基金管理委員會組織條例'
        elif '審計部組織法' in bill_name:
            return '審計部組織法'
        elif '監察院組織法' in bill_name:
            return '監察院組織法'
        elif '中央選舉委員會組織法' in bill_name:
            return '中央選舉委員會組織法'
        elif '國家通訊傳播委員會組織法' in bill_name:
            return '國家通訊傳播委員會組織法'
        elif '司法院組織法' in bill_name:
            return '司法院組織法'
        elif '組織法' in bill_name:
            # 擷取 "XXX組織法"
            org_law_match = re.search(r'「?([^「」]+(?:委員會|部|署|局|處)組織法)', bill_name)
            if org_law_match:
                return org_law_match.group(1)
                
    # 移除引號
    bill_name = bill_name.strip('「」')
    
    # 特殊處理某些常見法案
    if '陸海空軍刑法' in bill_name or '軍刑法' in bill_name:
        return '陸海空軍刑法'
    if '刑法' in bill_name and '陸海空軍刑法' not in bill_name:
        return '中華民國刑法'
    if '民法' in bill_name and '國民法官法' not in bill_name and '入出國及移民法' not in bill_name:
        return '民法'
    if '國民法官法' in bill_name:
        return '國民法官法'
    if '入出國及移民法' in bill_name:
        return '入出國及移民法'
    if '所得稅法' in bill_name:
        return '所得稅法'
    if '國土計畫法' in bill_name:
        return '國土計畫法'
    if '環境基本法' in bill_name:
        return '環境基本法'
    if '公務人員退休資遣撫卹法' in bill_name or '退撫法' in bill_name:
        return '公務人員退休資遣撫卹法'
    if '性別平等工作法' in bill_name or '性工法' in bill_name:
        return '性別平等工作法'
    if '貨物稅條例' in bill_name:
        return '貨物稅條例'
    if '勞動基準法' in bill_name or '勞基法' in bill_name:
        return '勞動基準法'
    if '就業服務法' in bill_name or '就服法' in bill_name:
        return '就業服務法'
    if '全民健康保險法' in bill_name or '健保法' in bill_name:
        return '全民健康保險法'
    if '社會秩序維護法' in bill_name or '社維法' in bill_name:
        return '社會秩序維護法'
    if '道路交通管理處罰條例' in bill_name or '道交條例' in bill_name:
        return '道路交通管理處罰條例'
    if '消費者保護法' in bill_name or '消保法' in bill_name:
        return '消費者保護法'
    if '公司法' in bill_name:
        return '公司法'
    
    # 依序移除後綴
    suffixes = ['修正條文', '修正草案', '部分條文修正草案', '條文', '草案']
    for suffix in suffixes:
        if suffix in bill_name:
            bill_name = bill_name[:bill_name.index(suffix)].strip()
            break
            
    # 移除條號（如果還有的話）
    if '第' in bill_name and '條' in bill_name:
        # 找到最後一個「第」的位置
        last_index = bill_name.rindex('第')
        bill_name = bill_name[:last_index].strip()
        
    return bill_name.strip()

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
    
    # 移除"本院委員XXX等N人"的部分
    names_str = re.sub(r'本院委員.+?等\d+人', '', names_str)
    
    # 首先嘗試匹配原住民名字（中文+英文組合）
    aboriginal_names = []
    aboriginal_pattern = r'([\u4e00-\u9fa5]{2,4}\s*[A-Za-z]+\s*[A-Za-z]+(?:\s*[A-Za-z]+)?)'
    aboriginal_matches = re.finditer(aboriginal_pattern, names_str)
    
    for match in aboriginal_matches:
        aboriginal_name = match.group(0).strip()
        if aboriginal_name:
            aboriginal_names.append(aboriginal_name)
            # 將匹配到的原住民名字從原始字串中移除，避免重複匹配
            names_str = names_str.replace(aboriginal_name, '')
    
    # 然後匹配一般中文名字
    chinese_names = []
    chinese_pattern = r'([\u4e00-\u9fa5]{2,4})'
    chinese_matches = re.finditer(chinese_pattern, names_str)
    
    for match in chinese_matches:
        chinese_name = match.group(0).strip()
        if chinese_name:
            chinese_names.append(chinese_name)
    
    # 合併原住民名字和中文名字
    all_names = aboriginal_names + chinese_names
    
    # 如果沒有找到任何名字，嘗試使用分隔符號分割
    if not all_names:
        for sep in ['、', '，', ',', ' ']:
            if sep in names_str:
                parts = [part.strip() for part in names_str.split(sep)]
                all_names.extend([part for part in parts if part and len(part) >= 2])
                break
    
    # 移除重複的名字
    return list(dict.fromkeys(all_names))

# 自訂SQL查詢取得熱門法案（含會期篩選）
def get_popular_bills_sql_with_session(session_period=None):
    base_sql = """
    WITH RawBillNames AS (
        SELECT 
            CASE 
                WHEN billName LIKE '%刑法%' AND billName NOT LIKE '%陸海空軍刑法%' THEN '中華民國刑法'
                WHEN billName LIKE '%所得稅法%' THEN '所得稅法'
                WHEN billName LIKE '%國土計畫法%' THEN '國土計畫法'
                WHEN billName LIKE '%環境基本法%' THEN '環境基本法'
                WHEN billName LIKE '%公務人員退休資遣撫卹法%' THEN '公務人員退休資遣撫卹法'
                WHEN billName LIKE '%性別平等工作法%' THEN '性別平等工作法'
                WHEN billName LIKE '%貨物稅條例%' THEN '貨物稅條例'
                WHEN billName LIKE '「%」%' THEN
                    CASE
                        WHEN SUBSTR(
                            SUBSTR(billName, INSTR(billName, '「') + 1),
                            1,
                            INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '」') - 1
                        ) LIKE '%部分條文%' THEN
                            REPLACE(
                                SUBSTR(
                                    SUBSTR(billName, INSTR(billName, '「') + 1),
                                    1,
                                    INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '部分條文') - 1
                                ),
                                '修正草案',
                                ''
                            )
                        ELSE
                            SUBSTR(
                                SUBSTR(billName, INSTR(billName, '「') + 1),
                                1,
                                INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '」') - 1
                            )
                    END
                ELSE billName
            END as raw_name,
            term,
            sessionPeriod
        FROM bills
        WHERE term = '11'
    """
    
    # 添加會期過濾條件
    if session_period and session_period != "全部":
        base_sql += f" AND sessionPeriod = '{session_period}'"
    
    base_sql += """
    ),
    CleanBillNames AS (
        SELECT 
            CASE
                WHEN raw_name = '中華民國刑法' THEN '中華民國刑法'
                WHEN raw_name = '所得稅法' THEN '所得稅法'
                WHEN raw_name = '國土計畫法' THEN '國土計畫法'
                WHEN raw_name = '環境基本法' THEN '環境基本法'
                WHEN raw_name = '公務人員退休資遣撫卹法' THEN '公務人員退休資遣撫卹法'
                WHEN raw_name = '性別平等工作法' THEN '性別平等工作法'
                WHEN raw_name = '貨物稅條例' THEN '貨物稅條例'
                WHEN raw_name LIKE '%部分條文%' THEN
                    REPLACE(
                        SUBSTR(raw_name, 1, INSTR(raw_name, '部分條文') - 1),
                        '修正草案',
                        ''
                    )
                WHEN raw_name LIKE '%第%條%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '第') - 1)
                WHEN raw_name LIKE '%修正條文%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '修正條文') - 1)
                WHEN raw_name LIKE '%修正草案%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '修正草案') - 1)
                WHEN raw_name LIKE '%條文%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '條文') - 1)
                WHEN raw_name LIKE '%草案%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '草案') - 1)
                ELSE raw_name
            END as clean_name,
            term,
            sessionPeriod
        FROM RawBillNames
    )
    SELECT 
        TRIM(clean_name) as law_name,
        COUNT(*) as total_count
    FROM CleanBillNames
    WHERE TRIM(clean_name) != ''
    GROUP BY TRIM(clean_name)
    ORDER BY total_count DESC, law_name
    LIMIT 30
    """
    return base_sql

# 自定義函數用於顯示法案狀態標籤
def display_status_badge(status):
    if not status:
        status = "待審查"
    
    # 根據不同狀態選擇不同顏色
    status_colors = {
        "三讀": "#28a745",  # 綠色
        "二讀": "#17a2b8",  # 青色
        "一讀": "#007bff",  # 藍色
        "審查完畢": "#6f42c1",  # 紫色
        "委員會審查": "#fd7e14",  # 橙色
        "待審查": "#6c757d",  # 灰色
        "退回": "#dc3545",  # 紅色
        "撤回": "#dc3545"   # 紅色
    }
    
    # 為狀態選擇顏色
    color = "#6c757d"  # 預設灰色
    for key, value in status_colors.items():
        if key in status:
            color = value
            break
    
    # 返回HTML標籤
    return f"""<span style='background-color: {color}; 
                      color: white; 
                      padding: 0.4em 0.8em; 
                      border-radius: 0.3em; 
                      font-size: 20px;'>
                {status}
            </span>"""

# 創建處理委員名單的函數，包括提案人和連署人
def process_all_members(bill):
    """處理提案人和連署人，合併計算政黨統計
    
    Args:
        bill: 法案數據
        
    Returns:
        dict: 包含政黨統計的字典
    """
    # 處理提案機關
    if bill['billOrg'] and '本院委員' not in bill['billOrg']:
        if '行政院' in bill['billOrg']:
            return {'行政院': 1}
        elif '民主進步黨' in bill['billOrg'] or '民進黨' in bill['billOrg']:
            return {'民進黨': 1}
        elif '中國國民黨' in bill['billOrg'] or '國民黨' in bill['billOrg']:
            return {'國民黨': 1}
        elif '台灣民眾黨' in bill['billOrg'] or '民眾黨' in bill['billOrg']:
            return {'民眾黨': 1}
        elif '時代力量' in bill['billOrg']:
            return {'時代力量': 1}
        elif '台灣基進' in bill['billOrg']:
            return {'其他': 1}
        else:
            return {'其他': 1}
    
    # 初始化政黨統計
    party_stats = {'民進黨': 0, '國民黨': 0, '民眾黨': 0, '時代力量': 0, '無黨籍': 0, '其他': 0}
    
    # 處理提案人
    if bill['billProposer']:
        proposer_parties = count_party_members(bill['billProposer'])
        for party, count in proposer_parties.items():
            if party in party_stats:
                party_stats[party] += count
            else:
                party_stats['其他'] += count
    
    # 處理連署人
    if bill['billCosignatory']:
        cosignatory_parties = count_party_members(bill['billCosignatory'])
        for party, count in cosignatory_parties.items():
            if party in party_stats:
                party_stats[party] += count
            else:
                party_stats['其他'] += count
    
    # 移除計數為0的政黨
    return {k: v for k, v in party_stats.items() if v > 0}

# 自定義函數顯示政黨標籤
def display_party_tags(parties):
    """顯示政黨標籤，使用HTML格式化
    
    Args:
        parties: 政黨統計字典
    
    Returns:
        str: HTML格式的標籤字串
    """
    if not parties:
        return ""
    
    # 將輸入轉換為字典以防萬一
    if not isinstance(parties, dict):
        st.warning(f"輸入格式異常: {parties}")
        return ""
    
    colors = {
        '民進黨': '#45B035',  # 較柔和的綠色
        '國民黨': '#1B54B3',  # 較深的藍色
        '民眾黨': '#27B8CC',  # 青色
        '時代力量': '#FFD035',  # 黃色
        '無黨籍': '#888888',  # 灰色
        '行政院': '#A256C5',  # 紫色
        '其他': '#CCCCCC'     # 淺灰色
    }
    
    # 創建標籤
    tags_html = ""
    for party, count in parties.items():
        color = colors.get(party, '#CCCCCC')
        text_color = "white" if party == "國民黨" else "black"
        tags_html += f"""<span class='party-tag{'-kmt' if party == '國民黨' else ''}' 
                       style='background-color:{color};
                              color:{text_color};
                              padding:3px 8px;
                              border-radius:12px;
                              font-size:0.9em;
                              margin-right:5px;
                              display:inline-block;'>
                    {party} {count}
                </span>"""
    
    return tags_html

# 顯示政黨比例，使用原生Streamlit組件
def display_party_ratio(parties, container=None):
    """顯示政黨比例，使用Streamlit原生組件
    
    Args:
        parties: 政黨統計字典
        container: 可選，顯示的容器
    """
    if not parties or not isinstance(parties, dict) or sum(parties.values()) == 0:
        return
    
    colors = {
        '民進黨': '#45B035',  # 較柔和的綠色
        '國民黨': '#1B54B3',  # 較深的藍色
        '民眾黨': '#27B8CC',  # 青色
        '時代力量': '#FFD035',  # 黃色
        '無黨籍': '#888888',  # 灰色
        '行政院': '#A256C5',  # 紫色
        '其他': '#CCCCCC'     # 淺灰色
    }
    
    # 使用指定容器或默認st
    display = container if container else st
    
    # 計算總數
    total_count = sum(parties.values())
    
    # 排序政黨
    party_order = {'國民黨': 1, '民進黨': 2, '民眾黨': 3, '時代力量': 4, '無黨籍': 5, '行政院': 6, '其他': 7}
    sorted_parties = sorted(parties.items(), key=lambda x: party_order.get(x[0], 99))
    
    # 顯示百分比
    legend_cols = display.columns(len(sorted_parties))
    for i, (party, count) in enumerate(sorted_parties):
        pct = count / total_count * 100
        color = colors.get(party, '#CCCCCC')
        with legend_cols[i]:
            display.markdown(f"<div style='text-align:center;'><div style='display:inline-block;width:12px;height:12px;background-color:{color};margin-right:4px;'></div> {party}</div>", unsafe_allow_html=True)
    
    # 使用進度條顯示比例
    for party, count in sorted_parties:
        pct = count / total_count
        color = colors.get(party, '#CCCCCC')
        display.progress(pct, f"{party}: {count} ({pct*100:.1f}%)")

# 主頁面
def home():
    st.title("立法院法案分析")
    st.subheader("搜尋與查詢立法委員提案")
    
    db = Database()
    try:
        # 獲取所有屆別
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT term FROM bills ORDER BY CAST(term AS INTEGER) DESC")
        terms = [row['term'] for row in cursor.fetchall()]
        
        # 獲取第11屆的所有會期
        cursor.execute("SELECT DISTINCT sessionPeriod FROM bills WHERE term = '11' ORDER BY CAST(sessionPeriod AS INTEGER)")
        session_periods = [row['sessionPeriod'] for row in cursor.fetchall()]
        
        # 創建搜尋表單
        col1, col2 = st.columns([3, 1])
        
        with col1:
            law_name = st.text_input("輸入法律名稱", placeholder="例如：民法、刑法", key="law_name_input")
        
        with col2:
            selected_term = st.selectbox("選擇屆別", ["全部"] + terms, key="term_select")
        
        # 搜尋按鈕
        search_button = st.button("搜尋法案", key="search_button")
        
        # 顯示熱門法案區域
        st.subheader("熱門法案")
        
        # 會期過濾功能
        selected_session = st.selectbox("選擇會期", ["全部"] + session_periods, key="session_filter")
        
        # 獲取過濾後的熱門法案
        cursor.execute(get_popular_bills_sql_with_session(selected_session if selected_session != "全部" else None))
        popular_bills = [dict(row) for row in cursor.fetchall()]
        
        # 使用Grid佈局顯示熱門法案
        hot_cols = 3
        rows = (len(popular_bills) + hot_cols - 1) // hot_cols  # 計算需要的行數
        
        # 創建熱門法案網格
        for row in range(rows):
            cols = st.columns(hot_cols)
            for col_idx in range(hot_cols):
                i = row * hot_cols + col_idx
                if i < len(popular_bills):
                    bill = popular_bills[i]
                    with cols[col_idx]:
                        # 使用更大的字體和更美觀的按鈕
                        if st.button(f"{bill['law_name']} ({bill['total_count']}件)", 
                                    key=f"popular_{i}", 
                                    use_container_width=True):
                            st.session_state['law_name'] = bill['law_name']
                            st.session_state['term'] = "11"  # 熱門法案只顯示第11屆
                            st.session_state['session_period'] = selected_session
                            st.session_state['search'] = True
                            st.rerun()
        
        # 如果點擊搜尋按鈕或從熱門法案選擇
        if search_button or ('search' in st.session_state and st.session_state['search']):
            if search_button:
                st.session_state['law_name'] = law_name
                st.session_state['term'] = selected_term
                st.session_state['session_period'] = "全部"  # 搜尋按鈕不套用會期過濾
                st.session_state['search'] = True
            
            search_law_name = st.session_state['law_name']
            search_term = None if st.session_state['term'] == "全部" else st.session_state['term']
            search_session = None if st.session_state['session_period'] == "全部" else st.session_state['session_period']
            
            # 搜尋法案
            if search_law_name:
                # 構建搜尋條件
                base_name = search_law_name.strip('「」')  # 移除可能的引號
                
                # 特殊處理某些法案
                if '刑法' in base_name and '陸海空軍刑法' not in base_name:
                    search_condition = "billName LIKE '%中華民國刑法%' AND billName NOT LIKE '%施行法%' AND billName NOT LIKE '%陸海空軍刑法%'"
                    params = tuple()
                elif base_name == '民法':
                    search_condition = "billName LIKE '%民法%' AND billName NOT LIKE '%施行法%' AND billName NOT LIKE '%入出國及移民法%'"
                    params = tuple()
                elif base_name == '入出國及移民法':
                    search_condition = "billName LIKE '%入出國及移民法%' AND billName NOT LIKE '%施行法%'"
                    params = tuple()
                else:
                    # 一般法律搜尋
                    search_condition = "billName LIKE ? AND billName NOT LIKE '%施行法%'"
                    params = (f"%{base_name}%",)
                
                # 添加屆別條件
                if search_term:
                    search_condition += " AND term = ?"
                    params = params + (search_term,)
                
                # 添加會期條件
                if search_session:
                    search_condition += " AND sessionPeriod = ?"
                    params = params + (search_session,)
                
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
                
                # 顯示搜尋結果
                st.header(f"搜尋結果：{clean_law_name(search_law_name)}")
                
                # 顯示過濾條件
                filter_info = f"第{search_term}屆" if search_term else "全部屆別"
                if search_session:
                    filter_info += f" 第{search_session}會期"
                st.write(f"{filter_info}，共找到 {len(bills)} 個法案")
                
                if len(bills) > 0:
                    # 排序選項
                    sort_by = st.radio("排序方式", ["按條號排序", "按審查進度排序"], horizontal=True, key="sort_option")
                    
                    if sort_by == "按條號排序":
                        # 按條號分組
                        articles_dict = defaultdict(lambda: {'bills': [], 'bills_count': 0})
                        
                        for bill in bills:
                            # 提取條號
                            articles = extract_article_numbers(bill['billName'])
                            
                            # 處理提案人和連署人資訊（改為處理所有委員）
                            bill['party_stats'] = process_all_members(bill)
                            
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
                        
                        # 排序條號
                        def get_sort_key(article_text):
                            if article_text == '其他修正':
                                return (float('inf'), 0)
                            match = re.search(r'第(\d+)條(?:之(\d+))?', article_text)
                            if match:
                                number = int(match.group(1))
                                sub_number = int(match.group(2)) if match.group(2) else 0
                                return (number, sub_number)
                            return (float('inf'), 0)
                        
                        # 顯示條號分組結果
                        sorted_articles = sorted(articles_dict.items(), key=lambda x: get_sort_key(x[0]))
                        
                        for article_text, data in sorted_articles:
                            # 使用更明顯的樣式來顯示摺疊區塊
                            with st.expander(f"### {article_text} ({data['bills_count']}件)", expanded=False):
                                for bill in data['bills']:
                                    bill_type = get_bill_type(bill['billName'])
                                    col1, col2 = st.columns([4, 1])
                                    with col1:
                                        st.markdown(f"**{bill['billName']}**")
                                        
                                        # 修改提案人顯示方式：使用帶有政黨顏色的委員名稱
                                        if bill['billProposer']:
                                            st.markdown(f"**提案人**: {format_members_with_party_colors(bill['billProposer'])}", unsafe_allow_html=True)
                                        elif bill['billOrg']:
                                            st.write(f"**提案人**: {bill['billOrg']}")
                                        else:
                                            st.write(f"**提案人**: 無資料")
                                        
                                        # 添加連署人信息，使用帶有政黨顏色的委員名稱
                                        if bill['billCosignatory']:
                                            st.markdown(f"**連署人**: {format_members_with_party_colors(bill['billCosignatory'])}", unsafe_allow_html=True)
                                        
                                        st.write(f"**提案日期**: 第{bill['term']}屆第{bill['sessionPeriod']}會期")
                                        
                                        # 顯示政黨統計（使用新的標籤函數）
                                        st.markdown(display_party_tags(bill['party_stats']), unsafe_allow_html=True)
                                        display_party_ratio(bill['party_stats'])
                                    
                                    with col2:
                                        # 顯示法案狀態標籤，而非法案類型
                                        st.markdown(display_status_badge(bill.get('billStatus', '')), unsafe_allow_html=True)
                                        
                                        if bill['pdfUrl']:
                                            st.markdown(f"[<span style='font-size: 18px;'>PDF</span>]({bill['pdfUrl']})", unsafe_allow_html=True)
                                        if bill['docUrl']:
                                            st.markdown(f"[<span style='font-size: 18px;'>DOC</span>]({bill['docUrl']})", unsafe_allow_html=True)
                                    st.divider()
                    
                    else:  # 按審查進度排序
                        # 按審查進度分組
                        status_groups = defaultdict(lambda: {'bills': [], 'bills_count': 0})
                        
                        for bill in bills:
                            # 處理提案人和連署人資訊（改為處理所有委員）
                            bill['party_stats'] = process_all_members(bill)
                            
                            # 獲取審查進度分組
                            status_group = get_status_group(bill.get('billStatus', ''))
                            status_groups[status_group]['bills'].append(bill)
                            status_groups[status_group]['bills_count'] += 1
                        
                        # 顯示審查進度分組結果
                        status_order = ['三讀', '二讀', '一讀', '審查完畢', '委員會審查', '待審查', '退回/撤回']
                        
                        for status in status_order:
                            if status in status_groups:
                                with st.expander(f"### {status} ({status_groups[status]['bills_count']}件)", expanded=False):
                                    for bill in status_groups[status]['bills']:
                                        col1, col2 = st.columns([4, 1])
                                        with col1:
                                            st.markdown(f"**{bill['billName']}**")
                                            
                                            # 修改提案人顯示方式：使用帶有政黨顏色的委員名稱
                                            if bill['billProposer']:
                                                st.markdown(f"**提案人**: {format_members_with_party_colors(bill['billProposer'])}", unsafe_allow_html=True)
                                            elif bill['billOrg']:
                                                st.write(f"**提案人**: {bill['billOrg']}")
                                            else:
                                                st.write(f"**提案人**: 無資料")
                                            
                                            # 添加連署人信息，使用帶有政黨顏色的委員名稱
                                            if bill['billCosignatory']:
                                                st.markdown(f"**連署人**: {format_members_with_party_colors(bill['billCosignatory'])}", unsafe_allow_html=True)
                                                
                                            st.write(f"**提案日期**: 第{bill['term']}屆第{bill['sessionPeriod']}會期")
                                            
                                            # 顯示政黨統計（使用新的標籤函數）
                                            st.markdown(display_party_tags(bill['party_stats']), unsafe_allow_html=True)
                                            display_party_ratio(bill['party_stats'])
                                            
                                        with col2:
                                            # 顯示法案狀態標籤，而非法案類型
                                            st.markdown(display_status_badge(bill.get('billStatus', '')), unsafe_allow_html=True)
                                            
                                            if bill['pdfUrl']:
                                                st.markdown(f"[<span style='font-size: 18px;'>PDF</span>]({bill['pdfUrl']})", unsafe_allow_html=True)
                                            if bill['docUrl']:
                                                st.markdown(f"[<span style='font-size: 18px;'>DOC</span>]({bill['docUrl']})", unsafe_allow_html=True)
                                        st.divider()
                else:
                    st.warning("沒有找到符合條件的法案")
            
            # 新增功能：依提案者分析法案
            st.header("提案單位分析")
            
            # 建立提案分析表單
            analysis_col1, analysis_col2, analysis_col3 = st.columns([2, 1, 1])
            
            with analysis_col1:
                analysis_type = st.selectbox("選擇分析類型", ["按立委分析", "按政黨分析", "按政府機關分析"], key="analysis_type")
            
            with analysis_col2:
                analysis_term = st.selectbox("選擇屆別", ["11"] + terms, key="analysis_term")
            
            with analysis_col3:
                analysis_session = st.selectbox("選擇會期", ["全部"] + session_periods, key="analysis_session_select")
            
            # 分析按鈕
            analysis_button = st.button("分析提案", key="analysis_button")
            
            if analysis_button:
                # 根據不同類型分析
                if analysis_type == "按立委分析":
                    # 查詢立委提案數
                    session_filter = f"AND sessionPeriod = '{analysis_session}'" if analysis_session != "全部" else ""
                    
                    query = f"""
                    SELECT billProposer, billName, billStatus, COUNT(*) as count
                    FROM bills
                    WHERE term = '{analysis_term}' 
                    {session_filter}
                    AND billProposer IS NOT NULL 
                    AND billProposer != ''
                    GROUP BY billProposer
                    ORDER BY count DESC
                    LIMIT 20
                    """
                    
                    cursor.execute(query)
                    results = [dict(row) for row in cursor.fetchall()]
                    
                    if results:
                        st.subheader(f"第{analysis_term}屆{'' if analysis_session == '全部' else f'第{analysis_session}會期'}立委提案數量前20名")
                        
                        # 顯示立委提案統計
                        legislator_data = defaultdict(int)
                        for row in results:
                            proposers = extract_names(row['billProposer'])
                            for proposer in proposers:
                                legislator_data[proposer] += 1
                        
                        # 篩選前10名
                        sorted_legislators = sorted(legislator_data.items(), key=lambda x: x[1], reverse=True)[:10]
                        
                        # 使用Matplotlib生成圓餅圖
                        plt.figure(figsize=(10, 6))
                        labels = [name for name, _ in sorted_legislators]
                        sizes = [count for _, count in sorted_legislators]
                        colors = plt.cm.tab20(np.linspace(0, 1, len(labels)))
                        
                        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                        plt.axis('equal')
                        plt.title(f"前10名立委提案數量佔比", fontsize=16, pad=20)
                        
                        # 顯示在Streamlit中
                        st.pyplot(plt)
                        
                        # 顯示詳細資料
                        st.subheader("立委提案詳細統計")
                        for legislator, count in sorted_legislators:
                            st.write(f"**{legislator}**: {count}件")
                            
                            # 查詢此立委提案的法案類型分布
                            law_query = f"""
                            SELECT billName, billStatus
                            FROM bills
                            WHERE term = '{analysis_term}'
                            {session_filter}
                            AND billProposer LIKE '%{legislator}%'
                            """
                            
                            cursor.execute(law_query)
                            law_results = [dict(row) for row in cursor.fetchall()]
                            
                            if law_results:
                                # 分析法案類型
                                law_types = defaultdict(int)
                                for law in law_results:
                                    # 清理法案名稱，獲取基本法律名稱
                                    clean_name = clean_law_name(law['billName'])
                                    law_types[clean_name] += 1
                                
                                # 顯示此立委的法案類型分布
                                top_laws = sorted(law_types.items(), key=lambda x: x[1], reverse=True)[:5]
                                
                                # 使用Matplotlib生成柱狀圖
                                plt.figure(figsize=(10, 4))
                                plt.bar(
                                    [name[:8] + '...' if len(name) > 8 else name for name, _ in top_laws], 
                                    [count for _, count in top_laws],
                                    color='skyblue'
                                )
                                plt.title(f"{legislator}的前5項法案提案")
                                plt.xticks(rotation=45, ha='right')
                                plt.tight_layout()
                                
                                # 顯示在Streamlit中
                                st.pyplot(plt)
                                
                                # 顯示審查狀態分佈
                                status_stats = defaultdict(int)
                                for law in law_results:
                                    status = get_status_group(law.get('billStatus', ''))
                                    status_stats[status] += 1
                                
                                # 使用Matplotlib生成圓餅圖
                                plt.figure(figsize=(8, 6))
                                status_labels = list(status_stats.keys())
                                status_sizes = list(status_stats.values())
                                status_colors = {
                                    '三讀': "#28a745",  # 綠色
                                    '二讀': "#17a2b8",  # 青色
                                    '一讀': "#007bff",  # 藍色
                                    '審查完畢': "#6f42c1",  # 紫色
                                    '委員會審查': "#fd7e14",  # 橙色
                                    '待審查': "#6c757d",  # 灰色
                                    '退回/撤回': "#dc3545"   # 紅色
                                }
                                colors = [status_colors.get(status, "#6c757d") for status in status_labels]
                                
                                plt.pie(status_sizes, labels=status_labels, autopct='%1.1f%%', startangle=90, colors=colors)
                                plt.axis('equal')
                                plt.title(f"{legislator}的法案審查狀態分佈", fontsize=16, pad=20)
                                
                                # 顯示在Streamlit中
                                st.pyplot(plt)
                            
                            st.divider()
                            
                    else:
                        st.warning("沒有找到相關立委提案資料")
                    
                elif analysis_type == "按政黨分析":
                    # 查詢政黨提案數
                    session_filter = f"AND sessionPeriod = '{analysis_session}'" if analysis_session != "全部" else ""
                    
                    st.subheader(f"第{analysis_term}屆{'' if analysis_session == '全部' else f'第{analysis_session}會期'}政黨提案分析")
                    
                    # 取得所有法案，然後分析政黨分布
                    query = f"""
                    SELECT billNo, billName, billOrg, billProposer, billCosignatory, 
                           term, sessionPeriod, billStatus
                    FROM bills 
                    WHERE term = '{analysis_term}'
                    {session_filter}
                    """
                    
                    cursor.execute(query)
                    bills = [dict(row) for row in cursor.fetchall()]
                    
                    if bills:
                        # 初始化政黨統計
                        party_stats = {'民進黨': 0, '國民黨': 0, '民眾黨': 0, '時代力量': 0, '無黨籍': 0, '行政院': 0, '其他': 0}
                        
                        # 按法案類型分類的政黨統計
                        party_law_stats = {
                            '民進黨': defaultdict(int),
                            '國民黨': defaultdict(int),
                            '民眾黨': defaultdict(int),
                            '時代力量': defaultdict(int),
                            '無黨籍': defaultdict(int),
                            '行政院': defaultdict(int),
                            '其他': defaultdict(int)
                        }
                        
                        # 審查狀態分布
                        party_status_stats = {
                            '民進黨': defaultdict(int),
                            '國民黨': defaultdict(int),
                            '民眾黨': defaultdict(int),
                            '時代力量': defaultdict(int),
                            '無黨籍': defaultdict(int),
                            '行政院': defaultdict(int),
                            '其他': defaultdict(int)
                        }
                        
                        # 分析每個法案
                        for bill in bills:
                            # 取得主要提案政黨
                            bill_parties = process_all_members(bill)
                            
                            # 跳過沒有提案人/機關的情況
                            if not bill_parties:
                                continue
                                
                            # 找出提案最多的政黨作為主要提案政黨
                            main_party = max(bill_parties.items(), key=lambda x: x[1])[0]
                            
                            # 增加政黨計數
                            party_stats[main_party] = party_stats.get(main_party, 0) + 1
                            
                            # 分析法案類型
                            clean_name = clean_law_name(bill['billName'])
                            party_law_stats[main_party][clean_name] += 1
                            
                            # 分析審查狀態
                            status = get_status_group(bill.get('billStatus', ''))
                            party_status_stats[main_party][status] += 1
                        
                        # 移除沒有提案的政黨
                        party_stats = {k: v for k, v in party_stats.items() if v > 0}
                        
                        # 顯示政黨提案統計圓餅圖
                        plt.figure(figsize=(10, 6))
                        labels = list(party_stats.keys())
                        sizes = list(party_stats.values())
                        colors = {
                            '民進黨': '#45B035',  # 較柔和的綠色
                            '國民黨': '#1B54B3',  # 較深的藍色
                            '民眾黨': '#27B8CC',  # 青色
                            '時代力量': '#FFD035',  # 黃色
                            '無黨籍': '#888888',  # 灰色
                            '行政院': '#A256C5',  # 紫色
                            '其他': '#CCCCCC'     # 淺灰色
                        }
                        pie_colors = [colors.get(party, '#CCCCCC') for party in labels]
                        
                        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors)
                        plt.axis('equal')
                        plt.title(f"政黨提案比例", fontsize=16, pad=20)
                        
                        # 顯示在Streamlit中
                        st.pyplot(plt)
                        
                        # 顯示每個政黨的法案統計
                        for party in [p for p in party_stats.keys() if party_stats[p] > 0]:
                            if party in party_law_stats:
                                st.subheader(f"{party}的提案法案分析")
                                
                                # 顯示此政黨的法案類型分布
                                party_laws = party_law_stats[party]
                                if party_laws:
                                    top_laws = sorted(party_laws.items(), key=lambda x: x[1], reverse=True)[:10]
                                    
                                    # 使用Matplotlib生成柱狀圖
                                    plt.figure(figsize=(12, 5))
                                    plt.bar(
                                        [name[:10] + '...' if len(name) > 10 else name for name, _ in top_laws], 
                                        [count for _, count in top_laws],
                                        color=colors.get(party, '#CCCCCC')
                                    )
                                    plt.title(f"{party}的前10項法案提案")
                                    plt.xticks(rotation=45, ha='right')
                                    plt.tight_layout()
                                    
                                    # 顯示在Streamlit中
                                    st.pyplot(plt)
                                
                                # 顯示審查狀態分佈
                                status_stats = party_status_stats[party]
                                if status_stats:
                                    # 使用Matplotlib生成圓餅圖
                                    plt.figure(figsize=(8, 6))
                                    status_labels = list(status_stats.keys())
                                    status_sizes = list(status_stats.values())
                                    status_colors = {
                                        '三讀': "#28a745",  # 綠色
                                        '二讀': "#17a2b8",  # 青色
                                        '一讀': "#007bff",  # 藍色
                                        '審查完畢': "#6f42c1",  # 紫色
                                        '委員會審查': "#fd7e14",  # 橙色
                                        '待審查': "#6c757d",  # 灰色
                                        '退回/撤回': "#dc3545"   # 紅色
                                    }
                                    pie_colors = [status_colors.get(status, "#6c757d") for status in status_labels]
                                    
                                    plt.pie(status_sizes, labels=status_labels, autopct='%1.1f%%', startangle=90, colors=pie_colors)
                                    plt.axis('equal')
                                    plt.title(f"{party}的法案審查狀態分佈", fontsize=16, pad=20)
                                    
                                    # 顯示在Streamlit中
                                    st.pyplot(plt)
                                
                                st.divider()
                    else:
                        st.warning("沒有找到相關法案資料")
                
                elif analysis_type == "按政府機關分析":
                    # 政府機關提案分析
                    session_filter = f"AND sessionPeriod = '{analysis_session}'" if analysis_session != "全部" else ""
                    
                    st.subheader(f"第{analysis_term}屆{'' if analysis_session == '全部' else f'第{analysis_session}會期'}政府機關提案分析")
                    
                    # 查詢政府機關提案
                    query = f"""
                    SELECT billOrg, billName, billStatus, COUNT(*) as count
                    FROM bills
                    WHERE term = '{analysis_term}' 
                    {session_filter}
                    AND billOrg IS NOT NULL 
                    AND billOrg != ''
                    GROUP BY billOrg
                    ORDER BY count DESC
                    """
                    
                    cursor.execute(query)
                    results = [dict(row) for row in cursor.fetchall()]
                    
                    if results:
                        # 初始化機關分類
                        gov_categories = {
                            '行政院': 0,
                            '立法院': 0,
                            '司法院': 0,
                            '考試院': 0,
                            '監察院': 0,
                            '其他': 0
                        }
                        
                        # 詳細機關列表
                        gov_details = defaultdict(int)
                        
                        # 五院的法案類型統計
                        gov_law_stats = {
                            '行政院': defaultdict(int),
                            '立法院': defaultdict(int),
                            '司法院': defaultdict(int),
                            '考試院': defaultdict(int),
                            '監察院': defaultdict(int),
                            '其他': defaultdict(int)
                        }
                        
                        # 整理分類
                        for result in results:
                            org = result['billOrg']
                            count = result['count']
                            gov_details[org] += count
                            
                            # 分類到五院
                            if '行政院' in org:
                                gov_categories['行政院'] += count
                            elif '立法院' in org:
                                gov_categories['立法院'] += count
                            elif '司法院' in org:
                                gov_categories['司法院'] += count
                            elif '考試院' in org:
                                gov_categories['考試院'] += count
                            elif '監察院' in org:
                                gov_categories['監察院'] += count
                            else:
                                # 判斷是否為行政院下屬部會
                                if any(keyword in org for keyword in ['部', '署', '委員會', '局', '處', '會']):
                                    gov_categories['行政院'] += count
                                else:
                                    gov_categories['其他'] += count
                        
                        # 移除沒有提案的機構
                        gov_categories = {k: v for k, v in gov_categories.items() if v > 0}
                        
                        # 顯示五院提案統計圓餅圖
                        plt.figure(figsize=(10, 6))
                        labels = list(gov_categories.keys())
                        sizes = list(gov_categories.values())
                        
                        colors = {
                            '行政院': '#F08080',  # 淺紅色
                            '立法院': '#20B2AA',  # 淺綠色
                            '司法院': '#4682B4',  # 鋼藍色
                            '考試院': '#DAA520',  # 金黃色
                            '監察院': '#9370DB',  # 紫色
                            '其他': '#A9A9A9'     # 灰色
                        }
                        pie_colors = [colors.get(org, '#A9A9A9') for org in labels]
                        
                        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors)
                        plt.axis('equal')
                        plt.title(f"五院提案比例", fontsize=16, pad=20)
                        
                        # 顯示在Streamlit中
                        st.pyplot(plt)
                        
                        # 分析五院提案的法案類型
                        for org in results:
                            org_name = org['billOrg']
                            
                            # 歸類到哪個院
                            if '行政院' in org_name:
                                main_org = '行政院'
                            elif '立法院' in org_name:
                                main_org = '立法院'
                            elif '司法院' in org_name:
                                main_org = '司法院'
                            elif '考試院' in org_name:
                                main_org = '考試院'
                            elif '監察院' in org_name:
                                main_org = '監察院'
                            else:
                                # 判斷是否為行政院下屬部會
                                if any(keyword in org_name for keyword in ['部', '署', '委員會', '局', '處', '會']):
                                    main_org = '行政院'
                                else:
                                    main_org = '其他'
                            
                            # 查詢此機關提案的法案
                            law_query = f"""
                            SELECT billName, billStatus
                            FROM bills
                            WHERE term = '{analysis_term}'
                            {session_filter}
                            AND billOrg = '{org_name}'
                            """
                            
                            cursor.execute(law_query)
                            law_results = [dict(row) for row in cursor.fetchall()]
                            
                            for law in law_results:
                                # 清理法案名稱，獲取基本法律名稱
                                clean_name = advanced_clean_law_name(law['billName'], 'government')
                                gov_law_stats[main_org][clean_name] += 1
                        
                        # 顯示每個院的法案統計
                        for org, laws in gov_law_stats.items():
                            if not laws:  # 跳過沒有提案的機構
                                continue
                                
                            # 只取前10項法案
                            top_laws = sorted(laws.items(), key=lambda x: x[1], reverse=True)[:10]
                            if not top_laws:
                                continue
                                
                            st.subheader(f"{org}提案法案分析")
                            
                            # 轉換為DataFrame以便繪圖
                            df = pd.DataFrame(top_laws, columns=['法律名稱', '提案數量'])
                            
                            # 使用Matplotlib生成柱狀圖
                            plt.figure(figsize=(12, 6))
                            plt.bar(
                                df['法律名稱'].apply(lambda x: x[:15] + '...' if len(x) > 15 else x),
                                df['提案數量'],
                                color=colors.get(org, '#A9A9A9')
                            )
                            
                            # 添加數據標籤
                            for i, v in enumerate(df['提案數量']):
                                plt.text(i, v + 0.1, str(v), ha='center')
                                
                            plt.title(f"{org}的前10項法案提案", fontsize=16)
                            plt.xticks(rotation=45, ha='right')
                            plt.tight_layout()
                            plt.ylabel('提案數量')
                            
                            # 顯示在Streamlit中
                            st.pyplot(plt)
                            
                            # 在展開區段顯示詳細提案機構
                            with st.expander(f"查看{org}下屬提案機構詳細統計"):
                                # 過濾屬於此院的機構
                                if org == '行政院':
                                    related_orgs = {k: v for k, v in gov_details.items() 
                                                if '行政院' in k or any(keyword in k for keyword in ['部', '署', '委員會', '局', '處', '會'])
                                                and not any(other in k for other in ['立法院', '司法院', '考試院', '監察院'])}
                                else:
                                    related_orgs = {k: v for k, v in gov_details.items() if org in k}
                                
                                if related_orgs:
                                    # 排序並顯示
                                    sorted_orgs = sorted(related_orgs.items(), key=lambda x: x[1], reverse=True)
                                    
                                    # 創建表格顯示機構統計，更美觀
                                    org_df = pd.DataFrame(sorted_orgs, columns=['提案機構', '提案數量'])
                                    st.dataframe(org_df, use_container_width=True)
                                    
                                    # 提供下載按鈕
                                    csv = org_df.to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        label=f"下載{org}提案統計資料",
                                        data=csv,
                                        file_name=f"{org}_提案統計_{analysis_term}_{analysis_session}.csv",
                                        mime='text/csv',
                                    )
                    
    
    except Exception as e:
        st.error(f"發生錯誤: {str(e)}")
    finally:
        db.close()

# 新增立委提案檢視頁面
def legislator_page():
    st.title("立委提案與連署檢視")
    
    db = Database()
    try:
        # 獲取所有屆別
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT term FROM bills ORDER BY CAST(term AS INTEGER) DESC")
        terms = [row['term'] for row in cursor.fetchall()]
        
        # 選擇屆別和會期
        col1, col2 = st.columns(2)
        with col1:
            selected_term = st.selectbox("選擇屆別", ["11"] + [t for t in terms if t != "11"], key="leg_term_select")
        
        with col2:
            cursor.execute(f"SELECT DISTINCT sessionPeriod FROM bills WHERE term = '{selected_term}' ORDER BY CAST(sessionPeriod AS INTEGER)")
            session_periods = [row['sessionPeriod'] for row in cursor.fetchall()]
            selected_session = st.selectbox("選擇會期", ["全部"] + session_periods, key="leg_session_select")
        
        # 獲取此屆期的立委名單
        session_filter = f"AND sessionPeriod = '{selected_session}'" if selected_session != "全部" else ""
        query = f"""
        SELECT DISTINCT billProposer FROM bills 
        WHERE term = '{selected_term}' 
        {session_filter}
        AND billProposer IS NOT NULL 
        AND billProposer != ''
        """
        
        cursor.execute(query)
        proposers_data = [row['billProposer'] for row in cursor.fetchall()]
        
        # 另外獲取法案提案機關
        org_query = f"""
        SELECT DISTINCT billOrg FROM bills 
        WHERE term = '{selected_term}' 
        {session_filter}
        AND billOrg IS NOT NULL 
        AND billOrg != ''
        """
        cursor.execute(org_query)
        org_data = [row['billOrg'] for row in cursor.fetchall()]
        
        # 提取所有立委姓名並按政黨分類
        legislators_by_party = {
            '民進黨': [],
            '國民黨': [],
            '民眾黨': [],
            '時代力量': [],
            '無黨籍': [],
            '其他': []
        }
        
        # 黨團和政府機關分類
        party_groups = []
        government_orgs = []
        
        # 處理機關提案
        for org in org_data:
            if '民主進步黨' in org or '民進黨黨團' in org:
                if '民進黨黨團' not in party_groups:
                    party_groups.append('民進黨黨團')
            elif '中國國民黨' in org or '國民黨黨團' in org:
                if '國民黨黨團' not in party_groups:
                    party_groups.append('國民黨黨團')
            elif '台灣民眾黨' in org or '民眾黨黨團' in org:
                if '民眾黨黨團' not in party_groups:
                    party_groups.append('民眾黨黨團')
            elif '時代力量' in org:
                if '時代力量黨團' not in party_groups:
                    party_groups.append('時代力量黨團')
            elif '行政院' in org:
                if '行政院' not in government_orgs:
                    government_orgs.append('行政院')
            elif '司法院' in org:
                if '司法院' not in government_orgs:
                    government_orgs.append('司法院')
            elif '監察院' in org:
                if '監察院' not in government_orgs:
                    government_orgs.append('監察院')
            elif '考試院' in org:
                if '考試院' not in government_orgs:
                    government_orgs.append('考試院')
            elif '立法院' in org:
                if '立法院' not in government_orgs:
                    government_orgs.append('立法院')
            # 捕捉其他政府機關
            elif any(keyword in org for keyword in ['部', '署', '委員會', '局', '處', '會', '中心']):
                # 過濾掉明確的黨團
                if not any(party in org for party in ['民進黨', '國民黨', '民眾黨', '時代力量']) and org not in government_orgs:
                    government_orgs.append(org)
        
        # 處理立委提案
        for proposer in proposers_data:
            legislators = extract_names(proposer)
            for legislator in legislators:
                # 使用st_utils中的函數判斷立委所屬政黨
                parties = count_party_members(legislator)
                if parties:
                    # 按政黨數量排序，取數量最多的政黨
                    sorted_parties = sorted(parties.items(), key=lambda x: x[1], reverse=True)
                    main_party = sorted_parties[0][0]
                    
                    # 將立委添加到對應政黨列表中
                    if main_party in legislators_by_party:
                        if legislator not in legislators_by_party[main_party]:
                            legislators_by_party[main_party].append(legislator)
                    else:
                        if legislator not in legislators_by_party['其他']:
                            legislators_by_party['其他'].append(legislator)
                else:
                    if legislator not in legislators_by_party['其他']:
                        legislators_by_party['其他'].append(legislator)
        
        # 處理完所有立委後，添加調試資訊
        # 計算每個政黨的立委數量
        party_counts = {party: len(members) for party, members in legislators_by_party.items()}
        
        # 確保民眾黨立委都存在
        tpp_members = ['劉書彬', '吳春城', '張啓楷', '林國成', '林憶君', '陳昭姿', '麥玉珍', '黃國昌', '黃珊珊']
        for member in tpp_members:
            if member not in legislators_by_party['民眾黨']:
                legislators_by_party['民眾黨'].append(member)
                
        # 重新計算民眾黨立委數量        
        party_counts['民眾黨'] = len(legislators_by_party['民眾黨'])
        
        # 如果啟用調試
        if st.checkbox("顯示政黨立委數量統計", key="debug_party_counts"):
            st.subheader("各政黨立委數量")
            for party, count in party_counts.items():
                st.write(f"**{party}**: {count}人")
                if count > 0:
                    with st.expander(f"查看{party}立委名單"):
                        st.write(", ".join(sorted(legislators_by_party[party])))
        
        # 政黨顏色對應表
        party_colors = {
            '民進黨': '#45B035',  # 綠色
            '國民黨': '#1B54B3',  # 藍色
            '民眾黨': '#27B8CC',  # 青色
            '時代力量': '#FFD035',  # 黃色
            '無黨籍': '#888888',  # 灰色
            '其他': '#CCCCCC'     # 淺灰色
        }
        
        # 政府機構顏色 - 統一使用淺紅色
        gov_color = '#F08080'  # 淺紅色 (Light Coral)
        
        # 黨團顏色 - 使用對應政黨的顏色
        group_colors = {
            '民進黨黨團': party_colors['民進黨'],  # 綠色
            '國民黨黨團': party_colors['國民黨'],  # 藍色
            '民眾黨黨團': party_colors['民眾黨'],  # 青色
            '時代力量黨團': party_colors['時代力量']  # 黃色
        }
        
        st.header(f"第{selected_term}屆{'' if selected_session == '全部' else f'第{selected_session}會期'}提案單位")
        
        # 政府機關區域
        if government_orgs:
            st.subheader("政府機關")
            gov_cols = st.columns(min(len(government_orgs), 4))  # 最多4個按鈕一排
            for idx, org in enumerate(government_orgs):
                col_idx = idx % 4
                with gov_cols[col_idx]:
                    # 使用CSS類包裝按鈕
                    with st.container():
                        st.markdown(f'<div class="gov-button">', unsafe_allow_html=True)
                        if st.button(
                            org, 
                            key=f"org_{org}_{selected_term}_{selected_session}",
                            help="點擊查看此機關的提案資訊",
                            use_container_width=True
                        ):
                            st.session_state['selected_legislator'] = org
                            st.session_state['selected_type'] = 'government'
                            st.session_state['selected_term'] = selected_term
                            st.session_state['selected_session'] = selected_session
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                        
        # 政黨黨團區域
        if party_groups:
            st.subheader("政黨黨團")
            group_cols = st.columns(min(len(party_groups), 4))  # 最多4個按鈕一排
            for idx, group in enumerate(party_groups):
                col_idx = idx % 4
                with group_cols[col_idx]:
                    # 獲取對應的CSS類
                    if '民進黨' in group:
                        css_class = 'dpp-button'
                    elif '國民黨' in group:
                        css_class = 'kmt-button'
                    elif '民眾黨' in group:
                        css_class = 'tpp-button'
                    elif '時代力量' in group:
                        css_class = 'npp-button'
                    else:
                        css_class = 'gov-button'  # 默認樣式
                    
                    # 使用CSS類包裝按鈕
                    with st.container():
                        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                        if st.button(
                            group, 
                            key=f"group_{group}_{selected_term}_{selected_session}", 
                            help="點擊查看此黨團的提案資訊",
                            use_container_width=True
                        ):
                            st.session_state['selected_legislator'] = group
                            st.session_state['selected_type'] = 'party_group'
                            st.session_state['selected_term'] = selected_term
                            st.session_state['selected_session'] = selected_session
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
        
        # 立委區域 - 按政黨分類顯示
        st.subheader("立法委員 (按政黨分類)")
        
        # 政黨選項卡
        party_tabs = st.tabs(["全部"] + [party for party, members in legislators_by_party.items() if members])
        
        # 全部立委選項卡
        with party_tabs[0]:
            # 合併所有立委
            all_legislators = []
            for party, members in legislators_by_party.items():
                all_legislators.extend(members)
            all_legislators = sorted(all_legislators)
            
            # 計算每行顯示的按鈕數量
            cols_per_row = 8
            num_rows = (len(all_legislators) + cols_per_row - 1) // cols_per_row
            
            # 為每位立委創建按鈕
            for row_idx in range(num_rows):
                cols = st.columns(cols_per_row)
                for col_idx in range(cols_per_row):
                    idx = row_idx * cols_per_row + col_idx
                    if idx < len(all_legislators):
                        legislator = all_legislators[idx]
                        with cols[col_idx]:
                            if st.button(legislator, key=f"leg_all_{legislator}_{selected_term}_{selected_session}"):
                                st.session_state['selected_legislator'] = legislator
                                st.session_state['selected_type'] = 'legislator'
                                st.session_state['selected_term'] = selected_term
                                st.session_state['selected_session'] = selected_session
                                st.rerun()
        
        # 各政黨立委選項卡
        tab_idx = 1
        for party, members in legislators_by_party.items():
            if not members:
                continue
                
            with party_tabs[tab_idx]:
                tab_idx += 1
                
                # 按照姓名排序
                members = sorted(members)
                
                # 計算每行顯示的按鈕數量
                cols_per_row = 8
                num_rows = (len(members) + cols_per_row - 1) // cols_per_row
                
                # 為每位立委創建按鈕
                for row_idx in range(num_rows):
                    cols = st.columns(cols_per_row)
                    for col_idx in range(cols_per_row):
                        idx = row_idx * cols_per_row + col_idx
                        if idx < len(members):
                            legislator = members[idx]
                            with cols[col_idx]:
                                if st.button(legislator, key=f"leg_{party}_{legislator}_{selected_term}_{selected_session}"):
                                    st.session_state['selected_legislator'] = legislator
                                    st.session_state['selected_type'] = 'legislator'
                                    st.session_state['selected_term'] = selected_term
                                    st.session_state['selected_session'] = selected_session
                                    st.rerun()
        
        # 如果有選擇的立委或機構，顯示其詳細資訊
        if 'selected_legislator' in st.session_state:
            legislator = st.session_state['selected_legislator']
            term = st.session_state['selected_term']
            session = st.session_state['selected_session']
            entity_type = st.session_state.get('selected_type', 'legislator')
            
            st.header(f"{legislator} - 第{term}屆{'' if session == '全部' else f'第{session}會期'}")
            
            # 設置標籤頁
            tab1, tab2, tab3, tab4 = st.tabs(["提案法案統計", "連署法案統計", "提案法案列表", "連署法案列表"])
            
            session_filter = f"AND sessionPeriod = '{session}'" if session != "全部" else ""
            
            # 根據不同類型構建不同的查詢條件
            if entity_type == 'legislator':
                proposer_condition = f"AND billProposer LIKE '%{legislator}%'"
                cosign_condition = f"AND billCosignatory LIKE '%{legislator}%'"
            elif entity_type == 'government':
                proposer_condition = f"AND billOrg LIKE '%{legislator}%'"
                cosign_condition = "AND 1=0"  # 政府機關不連署
            elif entity_type == 'party_group':
                party_name = legislator.replace('黨團', '')
                proposer_condition = f"AND billOrg LIKE '%{party_name}%'"
                cosign_condition = "AND 1=0"  # 黨團不連署
            else:
                proposer_condition = f"AND billProposer LIKE '%{legislator}%'"
                cosign_condition = f"AND billCosignatory LIKE '%{legislator}%'"
            
            with tab1:
                # 1. 提案：長條圖顯示前十名法案
                st.subheader("提案法案分析")
                
                # 查詢立委提案的法案
                proposer_query = f"""
                SELECT billName, billStatus
                FROM bills
                WHERE term = '{term}'
                {session_filter}
                {proposer_condition}
                """
                
                cursor.execute(proposer_query)
                proposer_results = [dict(row) for row in cursor.fetchall()]
                
                if proposer_results:
                    st.write(f"共提案 {len(proposer_results)} 件法案")
                    
                    # 分析法案類型
                    law_types = defaultdict(int)
                    
                    # 先顯示原始法案名稱用於調試
                    if st.checkbox("顯示原始法案清單", key=f"show_raw_bills_{legislator}"):
                        st.subheader("原始法案名稱")
                        for i, law in enumerate(proposer_results):
                            st.write(f"{i+1}. {law['billName']}")
                            
                    # 改進法案分類邏輯
                    for law in proposer_results:
                        bill_name = law['billName']
                        # 使用改進的法案名稱清理函數
                        clean_name = advanced_clean_law_name(bill_name, entity_type)
                        law_types[clean_name] += 1
                    
                    # 顯示此提案者的法案類型分布
                    top_laws = sorted(law_types.items(), key=lambda x: x[1], reverse=True)[:10]
                    
                    if top_laws:
                        # 轉換為DataFrame以便繪圖
                        df = pd.DataFrame(top_laws, columns=['法律名稱', '提案數量'])
                        
                        # 使用Matplotlib生成柱狀圖
                        plt.figure(figsize=(12, 6))
                        plt.bar(
                            df['法律名稱'].apply(lambda x: x[:15] + '...' if len(x) > 15 else x),
                            df['提案數量'],
                            color='skyblue'
                        )
                        
                        # 添加數據標籤
                        for i, v in enumerate(df['提案數量']):
                            plt.text(i, v + 0.1, str(v), ha='center')
                            
                        plt.title(f"{legislator}的前10項法案提案", fontsize=16)
                        plt.xticks(rotation=45, ha='right')
                        plt.tight_layout()
                        plt.ylabel('提案數量')
                        
                        # 顯示在Streamlit中
                        st.pyplot(plt)
                        plt.close()  # 關閉圖表以避免警告
                        
                        # 顯示法案詳情
                        with st.expander("查看法案類型詳細統計"):
                            for name, count in top_laws:
                                st.write(f"**{name}**: {count}件")
                                
                                # 顯示該法律名稱下的所有法案
                                matching_bills = [bill['billName'] for bill in proposer_results 
                                                if advanced_clean_law_name(bill['billName'], entity_type) == name]
                                for i, bill_name in enumerate(matching_bills[:5]):  # 只顯示前5個
                                    st.write(f"  {i+1}. {bill_name}")
                                if len(matching_bills) > 5:
                                    st.write(f"  ... 以及其他 {len(matching_bills)-5} 件")
                    else:
                        st.warning("沒有足夠的提案數據生成圖表")
                else:
                    st.warning("沒有找到相關提案數據")
            
            with tab2:
                # 2. 連署：長條圖顯示前十名法案
                st.subheader("連署法案分析")
                
                # 查詢立委連署的法案
                cosign_query = f"""
                SELECT billName, billStatus
                FROM bills
                WHERE term = '{term}'
                {session_filter}
                {cosign_condition}
                """
                
                cursor.execute(cosign_query)
                cosign_results = [dict(row) for row in cursor.fetchall()]
                
                if cosign_results:
                    st.write(f"共連署 {len(cosign_results)} 件法案")
                    
                    # 先顯示原始法案名稱用於調試
                    if st.checkbox("顯示原始法案清單", key=f"show_raw_cosign_{legislator}"):
                        st.subheader("原始法案名稱")
                        for i, law in enumerate(cosign_results):
                            st.write(f"{i+1}. {law['billName']}")
                    
                    # 分析法案類型
                    law_types = defaultdict(int)
                    for law in cosign_results:
                        # 清理法案名稱，獲取基本法律名稱
                        clean_name = advanced_clean_law_name(law['billName'], entity_type)
                        law_types[clean_name] += 1
                    
                    # 顯示此立委的法案類型分布
                    top_laws = sorted(law_types.items(), key=lambda x: x[1], reverse=True)[:10]
                    
                    if top_laws:
                        # 轉換為DataFrame以便繪圖
                        df = pd.DataFrame(top_laws, columns=['法律名稱', '連署數量'])
                        
                        # 使用Matplotlib生成柱狀圖
                        plt.figure(figsize=(12, 6))
                        plt.bar(
                            df['法律名稱'].apply(lambda x: x[:15] + '...' if len(x) > 15 else x),
                            df['連署數量'],
                            color='lightgreen'
                        )
                        
                        # 添加數據標籤
                        for i, v in enumerate(df['連署數量']):
                            plt.text(i, v + 0.1, str(v), ha='center')
                            
                        plt.title(f"{legislator}的前10項法案連署", fontsize=16)
                        plt.xticks(rotation=45, ha='right')
                        plt.tight_layout()
                        plt.ylabel('連署數量')
                        
                        # 顯示在Streamlit中
                        st.pyplot(plt)
                        plt.close()  # 關閉圖表以避免警告
                        
                        # 顯示法案詳情
                        with st.expander("查看法案類型詳細統計"):
                            for name, count in top_laws:
                                st.write(f"**{name}**: {count}件")
                                
                                # 顯示該法律名稱下的所有法案
                                matching_bills = [bill['billName'] for bill in cosign_results 
                                                if advanced_clean_law_name(bill['billName'], entity_type) == name]
                                for i, bill_name in enumerate(matching_bills[:5]):  # 只顯示前5個
                                    st.write(f"  {i+1}. {bill_name}")
                                if len(matching_bills) > 5:
                                    st.write(f"  ... 以及其他 {len(matching_bills)-5} 件")
                    else:
                        st.warning("沒有足夠的連署數據生成圖表")
                else:
                    st.warning("沒有找到相關連署數據")
            
            with tab3:
                # 3. 直接列出提案，依進度排列
                st.subheader("提案法案列表 (依審查進度排序)")
                
                # 查詢更詳細的法案信息
                proposer_detailed_query = f"""
                SELECT billNo, billName, billOrg, billProposer, billCosignatory, 
                       term, sessionPeriod, billStatus, pdfUrl, docUrl
                FROM bills
                WHERE term = '{term}'
                {session_filter}
                {proposer_condition}
                """
                
                cursor.execute(proposer_detailed_query)
                proposer_results = [dict(row) for row in cursor.fetchall()]
                
                if proposer_results:
                    # 按審查進度分組
                    status_groups = defaultdict(list)
                    for bill in proposer_results:
                        # 處理提案人和連署人資訊
                        bill['party_stats'] = process_all_members(bill)
                        
                        status = get_status_group(bill.get('billStatus', ''))
                        status_groups[status].append(bill)
                    
                    # 顯示審查進度分組結果
                    status_order = ['三讀', '二讀', '一讀', '審查完畢', '委員會審查', '待審查', '退回/撤回']
                    
                    for status in status_order:
                        if status in status_groups:
                            with st.expander(f"### {status} ({len(status_groups[status])}件)", expanded=status in ['三讀', '二讀']):
                                for bill in status_groups[status]:
                                    col1, col2 = st.columns([4, 1])
                                    with col1:
                                        st.markdown(f"**{bill['billName']}**")
                                        
                                        # 修改提案人顯示方式：使用帶有政黨顏色的委員名稱
                                        if bill['billProposer']:
                                            st.markdown(f"**提案人**: {format_members_with_party_colors(bill['billProposer'])}", unsafe_allow_html=True)
                                        elif bill['billOrg']:
                                            st.write(f"**提案人**: {bill['billOrg']}")
                                        else:
                                            st.write(f"**提案人**: 無資料")
                                        
                                        # 添加連署人信息，使用帶有政黨顏色的委員名稱
                                        if bill['billCosignatory']:
                                            st.markdown(f"**連署人**: {format_members_with_party_colors(bill['billCosignatory'])}", unsafe_allow_html=True)
                                        
                                        st.write(f"**提案日期**: 第{bill['term']}屆第{bill['sessionPeriod']}會期")
                                        
                                        # 顯示政黨統計（使用標籤函數）
                                        st.markdown(display_party_tags(bill['party_stats']), unsafe_allow_html=True)
                                        display_party_ratio(bill['party_stats'])
                                    
                                    with col2:
                                        # 顯示法案狀態標籤
                                        st.markdown(display_status_badge(bill.get('billStatus', '')), unsafe_allow_html=True)
                                        
                                        if bill['pdfUrl']:
                                            st.markdown(f"[<span style='font-size: 18px;'>PDF</span>]({bill['pdfUrl']})", unsafe_allow_html=True)
                                        if bill['docUrl']:
                                            st.markdown(f"[<span style='font-size: 18px;'>DOC</span>]({bill['docUrl']})", unsafe_allow_html=True)
                                    st.divider()
                else:
                    st.warning("沒有找到相關提案數據")
            
            with tab4:
                # 4. 列出連署的法案，依進度排列
                st.subheader("連署法案列表 (依審查進度排序)")
                
                if cosign_results:
                    # 按審查進度分組
                    status_groups = defaultdict(list)
                    for bill in cosign_results:
                        status = get_status_group(bill.get('billStatus', ''))
                        status_groups[status].append(bill)
                    
                    # 顯示審查進度分組結果
                    status_order = ['三讀', '二讀', '一讀', '審查完畢', '委員會審查', '待審查', '退回/撤回']
                    
                    for status in status_order:
                        if status in status_groups:
                            with st.expander(f"{status} ({len(status_groups[status])}件)", expanded=status in ['三讀', '二讀']):
                                for bill in status_groups[status]:
                                    st.write(f"**{bill['billName']}**")
                                    st.markdown(display_status_badge(bill.get('billStatus', '')), unsafe_allow_html=True)
                                    st.divider()
                else:
                    st.warning("沒有找到相關連署數據")
    
    except Exception as e:
        st.error(f"發生錯誤: {str(e)}")
    finally:
        db.close()

# 設定session_state變數
if 'search' not in st.session_state:
    st.session_state['search'] = False
if 'session_period' not in st.session_state:
    st.session_state['session_period'] = "全部"
    
# 新增頁面選擇功能
def main():
    # 創建頁面選單
    pages = {
        "法案搜尋與分析": home,
        "立委提案檢視": legislator_page
    }
    
    # 顯示頁面選單
    st.sidebar.title("功能選單")
    selection = st.sidebar.radio("選擇功能", list(pages.keys()))
    
    # 顯示選擇的頁面
    pages[selection]()
    
# 執行主程式
if __name__ == "__main__":
    main()
