from collections import Counter
from typing import Dict, List, Tuple
import re

class BillAnalyzer:
    """法案分析器"""
    
    # 中文數字對照表
    CN_NUM = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '〇': 0
    }
    
    def __init__(self, bills: List[Dict]):
        self.bills = bills
        
    def cn2num(self, cn_str: str) -> int:
        """將中文數字轉換為阿拉伯數字
        
        Args:
            cn_str: 中文數字字串
            
        Returns:
            int: 阿拉伯數字
        """
        if not cn_str:
            return 0
            
        # 處理特殊情況
        if cn_str == '十':
            return 10
            
        result = 0
        unit = 1
        for i in range(len(cn_str) - 1, -1, -1):
            if cn_str[i] in ['十', '百', '千']:
                unit = self.CN_NUM[cn_str[i]]
                if i == 0:
                    result += unit
            elif cn_str[i] in self.CN_NUM:
                result += self.CN_NUM[cn_str[i]] * unit
                unit = 1
                
        return result
        
    def extract_law_name(self, bill_name: str) -> str:
        """從提案名稱中提取法律名稱
        
        Args:
            bill_name: 提案名稱
            
        Returns:
            str: 法律名稱
        """
        # 移除「審查」、「審議」等字樣
        bill_name = re.sub(r'[「」『』]', '', bill_name)
        bill_name = re.sub(r'[，。、；：].*$', '', bill_name)
        bill_name = re.sub(r'審查|審議|決議|函請|研處|研議|研商|建請|建議|建言|提案|草案|修正案|修正草案|修正條文|部分條文', '', bill_name)
        
        # 常見的法律名稱結尾
        patterns = [
            r"^(.*?)(法|條例|通則|規程|規則|辦法)(?:第.*條.*|修正|廢止|刪除|）|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, bill_name)
            if match:
                return (match.group(1) + match.group(2)).strip()
        return bill_name.strip()
    
    def extract_article_numbers(self, bill_name: str) -> List[int]:
        """從提案名稱中提取條號
        
        Args:
            bill_name: 提案名稱
            
        Returns:
            List[int]: 條號列表
        """
        # 移除「審查」、「審議」等字樣
        bill_name = re.sub(r'[「」『』]', '', bill_name)
        
        article_numbers = []
        
        # 匹配阿拉伯數字條號
        patterns = [
            r'第([0-9]+)條(?:之[0-9]+)?',  # 匹配「第X條」和「第X條之Y」
            r'第([0-9]+)條至第[0-9]+條',   # 匹配範圍條號的起始
            r'至第([0-9]+)條',             # 匹配範圍條號的結束
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, bill_name)
            for match in matches:
                try:
                    article_numbers.append(int(match.group(1)))
                except (ValueError, IndexError):
                    continue
        
        # 匹配中文數字條號
        cn_patterns = [
            r'第([零一二三四五六七八九十百千]+)條(?:之[零一二三四五六七八九十百千]+)?',
            r'第([零一二三四五六七八九十百千]+)條至第[零一二三四五六七八九十百千]+條',
            r'至第([零一二三四五六七八九十百千]+)條'
        ]
        
        for pattern in cn_patterns:
            matches = re.finditer(pattern, bill_name)
            for match in matches:
                try:
                    cn_num = match.group(1)
                    num = self.cn2num(cn_num)
                    if num > 0:
                        article_numbers.append(num)
                except (ValueError, IndexError):
                    continue
                    
        return sorted(list(set(article_numbers)))
    
    def get_hot_laws(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """獲取修法熱點
        
        Args:
            top_n: 返回前N名，預設為10
            
        Returns:
            List[Tuple[str, int]]: (法律名稱, 提案數量) 的列表
        """
        law_counter = Counter()
        
        for bill in self.bills:
            bill_name = bill.get('billName', '')
            if not bill_name:
                continue
                
            law_name = self.extract_law_name(bill_name)
            if law_name and len(law_name) > 2:  # 過濾可能的雜訊
                law_counter[law_name] += 1
        
        return law_counter.most_common(top_n)
    
    def get_hot_articles(self, law_name: str, top_n: int = 5) -> List[Tuple[int, int]]:
        """獲取特定法律的熱門條號
        
        Args:
            law_name: 法律名稱
            top_n: 返回前N名，預設為5
            
        Returns:
            List[Tuple[int, int]]: (條號, 提案數量) 的列表
        """
        article_counter = Counter()
        
        for bill in self.bills:
            bill_name = bill.get('billName', '')
            if not bill_name:
                continue
                
            if law_name in self.extract_law_name(bill_name):
                article_numbers = self.extract_article_numbers(bill_name)
                for article in article_numbers:
                    article_counter[article] += 1
        
        return article_counter.most_common(top_n) 