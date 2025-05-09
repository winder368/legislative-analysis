"""Streamlit 工具函數模組"""
import re
from collections import defaultdict
import streamlit as st

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
    
    # 處理阿拉伯數字條號，如「第1條」
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
    
    return articles

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
    
    # 原住民特定委員名稱映射
    aboriginal_special_cases = {
        '伍麗華Saidhai Tahovecahe': '伍麗華',
        '鄭天財Sra Kacaw': '鄭天財',
        '伍麗華 Saidhai Tahovecahe': '伍麗華',
        '鄭天財 Sra Kacaw': '鄭天財',
        '高金素梅Ciwas Ali': '高金素梅',
        '高金素梅 Ciwas Ali': '高金素梅',
        '萬美玲Walis Pelin': '萬美玲',
        '萬美玲 Walis Pelin': '萬美玲'
    }
    
    # 檢查是否有特定原住民委員名稱
    all_names = []
    for full_name, short_name in aboriginal_special_cases.items():
        if full_name in names_str:
            all_names.append(short_name)
            names_str = names_str.replace(full_name, '')  # 從原字串中移除已識別的名稱
    
    # 匹配原住民名字（中文+英文組合）
    aboriginal_pattern = r'([\u4e00-\u9fa5]{2,4}\s*[A-Za-z]+\s*[A-Za-z]+(?:\s*[A-Za-z]+)?)'
    aboriginal_matches = re.finditer(aboriginal_pattern, names_str)
    
    for match in aboriginal_matches:
        aboriginal_name = match.group(0).strip()
        if aboriginal_name:
            # 檢查是否需要轉換為短名稱
            short_name = None
            for full, short in aboriginal_special_cases.items():
                if aboriginal_name in full or full in aboriginal_name:
                    short_name = short
                    break
            
            # 如有短名稱則使用短名稱，否則使用原名
            name_to_append = short_name if short_name else aboriginal_name
            
            # 如果是短名稱，或原名不在特殊映射中，則添加到列表
            if short_name or aboriginal_name not in aboriginal_special_cases.keys():
                all_names.append(name_to_append)
            
            # 將匹配到的原住民名字從原始字串中移除，避免重複匹配
            names_str = names_str.replace(aboriginal_name, '')
    
    # 然後匹配一般中文名字
    chinese_pattern = r'([\u4e00-\u9fa5]{2,4})'
    chinese_matches = re.finditer(chinese_pattern, names_str)
    
    for match in chinese_matches:
        chinese_name = match.group(0).strip()
        if chinese_name:
            all_names.append(chinese_name)
    
    # 如果沒有找到任何名字，嘗試使用分隔符號分割
    if not all_names:
        for sep in ['、', '，', ',', ' ']:
            if sep in names_str:
                parts = [part.strip() for part in names_str.split(sep)]
                all_names.extend([part for part in parts if part and len(part) >= 2])
                break
    
    # 移除重複的名字
    return list(dict.fromkeys(all_names))

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

def count_party_members(names_str: str) -> dict:
    """統計名單中各黨籍人數
    
    Args:
        names_str: 包含多個姓名的字串
        
    Returns:
        dict: 各黨籍人數統計
    """
    if not names_str:
        return {}
        
    # 立委黨籍對照表（第8-11屆）
    legislators = {
        # 第11屆立委
        # 民進黨籍立委
        '伍麗華': '民進黨', '伍麗華Saidhai Tahovecahe': '民進黨', '伍麗華 Saidhai Tahovecahe': '民進黨',
        '何欣純': '民進黨', '劉建國': '民進黨', '吳思瑤': '民進黨',
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
        '翁曉玲': '國民黨', '萬美玲': '國民黨', '萬美玲Walis Pelin': '國民黨', '萬美玲 Walis Pelin': '國民黨',
        '葉元之': '國民黨', '葛如鈞': '國民黨',
        '蘇清泉': '國民黨', '許宇甄': '國民黨', '謝衣鳯': '國民黨', '謝龍介': '國民黨',
        '賴士葆': '國民黨', '邱若華': '國民黨', '邱鎮軍': '國民黨', 
        '鄭天財': '國民黨', '鄭天財Sra Kacaw': '國民黨', '鄭天財 Sra Kacaw': '國民黨',
        '鄭正鈐': '國民黨', '陳永康': '國民黨', '陳玉珍': '國民黨', '陳菁徽': '國民黨',
        '陳雪生': '國民黨', '韓國瑜': '國民黨', '顏寬恒': '國民黨', '馬文君': '國民黨',
        '魯明哲': '國民黨', '黃仁': '國民黨', '黃健豪': '國民黨', '黃建賓': '國民黨',
        '溫玉霞': '國民黨', '李貴敏': '國民黨',
        
        # 民眾黨籍立委
        '劉書彬': '民眾黨', '吳春城': '民眾黨', '張啟楷': '民眾黨', '林國成': '民眾黨',
        '林憶君': '民眾黨', '陳昭姿': '民眾黨', '麥玉珍': '民眾黨', '黃國昌': '民眾黨',
        '黃珊珊': '民眾黨', '張啟楷': '民眾黨',  # 加入異體字寫法
        
        # 時代力量立委
        '王婉諭': '時代力量', '邱顯智': '時代力量', '陳椒華': '時代力量',
        
        # 無黨籍立委
        '陳超明': '無黨籍', '高金素梅': '無黨籍', '高金素梅Ciwas Ali': '無黨籍', '高金素梅 Ciwas Ali': '無黨籍'
    }
    
    # 初始化計數器
    party_counts = {
        '民進黨': 0,
        '國民黨': 0,
        '民眾黨': 0,
        '時代力量': 0,
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
        elif max_party == '時代力量':
            result['tag_class'] = 'npp-tag'
            result['tag_name'] = '時代力量'
            
    return result

def create_party_tag(party_name, count=None):
    """根據政黨名稱創建標籤
    
    Args:
        party_name: 政黨名稱
        count: 人數，若有則顯示
        
    Returns:
        str: HTML 標籤字串
    """
    colors = {
        '民進黨': '#45B035',  # 較柔和的綠色
        '國民黨': '#1B54B3',  # 較深的藍色
        '民眾黨': '#27B8CC',  # 青色
        '時代力量': '#FFD035',  # 黃色
        '無黨籍': '#888888',  # 灰色
        '行政院': '#A256C5',  # 紫色
        '其他': '#CCCCCC'     # 淺灰色
    }
    color = colors.get(party_name, '#CCCCCC')
    
    # 為國民黨設置白色文字
    text_color = "white" if party_name == "國民黨" else "black"
    
    if count:
        return f'<span style="background-color:{color};color:{text_color};padding:3px 8px;border-radius:12px;font-size:0.8em;margin-right:5px;">{party_name} {count}</span>'
    else:
        return f'<span style="background-color:{color};color:{text_color};padding:3px 8px;border-radius:12px;font-size:0.8em;margin-right:5px;">{party_name}</span>'

def get_member_with_party_color(member_name):
    """根據委員名稱取得其黨籍並以對應顏色顯示
    
    Args:
        member_name: 委員名稱
        
    Returns:
        str: 添加了政黨顏色的委員名稱HTML字串
    """
    # 原住民委員名稱映射（完整名稱 -> 簡短名稱）
    aboriginal_name_mapping = {
        '伍麗華Saidhai Tahovecahe': '伍麗華',
        '伍麗華 Saidhai Tahovecahe': '伍麗華',
        '鄭天財Sra Kacaw': '鄭天財',
        '鄭天財 Sra Kacaw': '鄭天財',
        '高金素梅Ciwas Ali': '高金素梅',
        '高金素梅 Ciwas Ali': '高金素梅',
        '萬美玲Walis Pelin': '萬美玲',
        '萬美玲 Walis Pelin': '萬美玲'
    }
    
    # 原住民委員名稱映射（簡短名稱 -> 完整標準名稱）
    aboriginal_full_names = {
        '伍麗華': '伍麗華 Saidhai Tahovecahe',
        '鄭天財': '鄭天財 Sra Kacaw',
        }
    
    # 立委黨籍對照表
    legislators = {
        # 第11屆立委
        # 民進黨籍立委
        '伍麗華': '民進黨', '伍麗華Saidhai Tahovecahe': '民進黨', '伍麗華 Saidhai Tahovecahe': '民進黨',
        '何欣純': '民進黨', '劉建國': '民進黨', '吳思瑤': '民進黨',
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
        '翁曉玲': '國民黨', '萬美玲': '國民黨', '萬美玲Walis Pelin': '國民黨', '萬美玲 Walis Pelin': '國民黨',
        '葉元之': '國民黨', '葛如鈞': '國民黨',
        '蘇清泉': '國民黨', '許宇甄': '國民黨', '謝衣鳯': '國民黨', '謝龍介': '國民黨',
        '賴士葆': '國民黨', '邱若華': '國民黨', '邱鎮軍': '國民黨', 
        '鄭天財': '國民黨', '鄭天財Sra Kacaw': '國民黨', '鄭天財 Sra Kacaw': '國民黨',
        '鄭正鈐': '國民黨', '陳永康': '國民黨', '陳玉珍': '國民黨', '陳菁徽': '國民黨',
        '陳雪生': '國民黨', '韓國瑜': '國民黨', '顏寬恒': '國民黨', '馬文君': '國民黨',
        '魯明哲': '國民黨', '黃仁': '國民黨', '黃健豪': '國民黨', '黃建賓': '國民黨',
        '溫玉霞': '國民黨', '李貴敏': '國民黨',
        
        # 民眾黨籍立委
        '劉書彬': '民眾黨', '吳春城': '民眾黨', '張啟楷': '民眾黨', '林國成': '民眾黨',
        '林憶君': '民眾黨', '陳昭姿': '民眾黨', '麥玉珍': '民眾黨', '黃國昌': '民眾黨',
        '黃珊珊': '民眾黨', '張啟楷': '民眾黨',  # 加入異體字寫法
        
        # 時代力量立委
        '王婉諭': '時代力量', '邱顯智': '時代力量', '陳椒華': '時代力量',
        
        # 無黨籍立委
        '陳超明': '無黨籍', '高金素梅': '無黨籍', '高金素梅Ciwas Ali': '無黨籍', '高金素梅 Ciwas Ali': '無黨籍'
    }
    
    # 政黨顏色對照 - 使用更美觀的色調
    party_colors = {
        '民進黨': '#45B035',  # 較柔和的綠色
        '國民黨': '#1B54B3',  # 較深的藍色
        '民眾黨': '#27B8CC',  # 青色
        '時代力量': '#FFD035',  # 黃色
        '無黨籍': '#888888',  # 灰色
        '其他': '#CCCCCC'     # 淺灰色
    }
    
    # 處理原住民委員名稱
    display_name = member_name
    lookup_name = member_name
    
    # 檢查是否為原住民委員的簡短名稱
    if member_name in aboriginal_full_names:
        display_name = aboriginal_full_names[member_name]
        lookup_name = member_name
    else:
        # 檢查是否為原住民委員的完整名稱
        for full_name, short_name in aboriginal_name_mapping.items():
            if full_name in member_name:
                display_name = full_name
                lookup_name = short_name
                break
    
    # 尋找委員所屬政黨
    party = legislators.get(lookup_name, '其他')
    color = party_colors.get(party, '#CCCCCC')
    
    # 為國民黨委員設置白色文字
    text_color = "white" if party == "國民黨" else "black"
    
    # 返回添加了顏色的HTML字串，調整了樣式使其更美觀
    return f'''<span style="
        background-color:{color};
        color:{text_color};
        padding:3px 6px;
        margin:2px 4px;
        border-radius:8px;
        font-size:0.95em;
        display:inline-block;
        font-weight:500;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        ">{display_name}</span>'''

def format_members_with_party_colors(names_str):
    """處理一串委員名稱，為每位委員添加政黨顏色
    
    Args:
        names_str: 包含多個委員姓名的字串
        
    Returns:
        str: HTML格式的帶顏色的委員名單
    """
    if not names_str:
        return ""
    
    # 提取人名列表
    names = extract_names(names_str)
    
    # 為每個人名添加政黨顏色
    colored_names = []
    for name in names:
        colored_names.append(get_member_with_party_color(name))
    
    # 將彩色名稱以空格分隔，並添加換行樣式
    # 使用flex佈局使標籤自然排列
    return f'''
    <div style="
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 4px;
        margin-bottom: 8px;
    ">
        {''.join(colored_names)}
    </div>
    '''

def display_party_statistics(parties):
    """顯示政黨統計資訊
    
    Args:
        parties: 政黨統計字典
    """
    if not parties:
        return
    
    html = ""
    for party, count in parties.items():
        html += create_party_tag(party, count)
    
    st.markdown(html, unsafe_allow_html=True)

def process_members(bill: dict) -> dict:
    """處理法案的提案人和連署人資訊
    
    Args:
        bill: 法案資訊字典
        
    Returns:
        dict: 包含成員列表和政黨統計的字典
    """
    party_stats = {'民進黨': 0, '國民黨': 0, '民眾黨': 0, '無黨籍': 0, '其他': 0}
    
    # 處理提案機關
    if bill['billOrg'] and '本院委員' not in bill['billOrg']:
        if '行政院' in bill['billOrg']:
            return {
                'party_stats': {'行政院': 1},
                'total': 1
            }
        elif '民主進步黨' in bill['billOrg'] or '民進黨' in bill['billOrg']:
            return {
                'party_stats': {'民進黨': 1},
                'total': 1
            }
        elif '中國國民黨' in bill['billOrg'] or '國民黨' in bill['billOrg']:
            return {
                'party_stats': {'國民黨': 1},
                'total': 1
            }
        elif '台灣民眾黨' in bill['billOrg'] or '民眾黨' in bill['billOrg']:
            return {
                'party_stats': {'民眾黨': 1},
                'total': 1
            }
        elif '時代力量' in bill['billOrg']:
            return {
                'party_stats': {'時代力量': 1},
                'total': 1
            }
        elif '台灣基進' in bill['billOrg']:
            return {
                'party_stats': {'其他': 1},
                'total': 1
            }
        else:
            return {
                'party_stats': {'其他': 1},
                'total': 1
            }
    
    # 處理提案人
    proposer_parties = {}
    if bill['billProposer']:
        proposer_parties = count_party_members(bill['billProposer'])
        for party, count in proposer_parties.items():
            if party in party_stats:
                party_stats[party] += count
            else:
                party_stats['其他'] += count
    
    # 處理連署人
    cosignatory_parties = {}
    if bill['billCosignatory']:
        cosignatory_parties = count_party_members(bill['billCosignatory'])
    
    # 移除計數為0的政黨
    party_stats = {k: v for k, v in party_stats.items() if v > 0}
    total = sum(party_stats.values())
    
    return {
        'party_stats': party_stats,
        'total': total
    } 