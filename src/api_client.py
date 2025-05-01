import requests
from typing import Dict, List, Optional, Tuple
import json
import time
from datetime import datetime, timedelta

class LYAPIClient:
    """立法院 API 客戶端"""
    
    BASE_URL = "https://data.ly.gov.tw/odw/openDatasetJson.action"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://data.ly.gov.tw/',
            'Origin': 'https://data.ly.gov.tw',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })
    
    def get_bills(self, term: str = "all", page: int = 1) -> List[Dict]:
        """獲取單一頁面的法案資料
        
        Args:
            term: 屆別，預設為 "all"
            page: 頁碼，預設為 1
            
        Returns:
            List[Dict]: 法案資料列表
        """
        params = {
            "id": "20",
            "selectTerm": term,
            "page": page
        }
        
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("jsonList", [])
            except requests.exceptions.RequestException as e:
                print(f"請求失敗 (嘗試 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指數退避
                else:
                    raise
    
    def get_latest_bills(self, latest_term: str, latest_session: str) -> List[Dict]:
        """獲取最新的法案資料
        
        Args:
            latest_term: 最新的屆別
            latest_session: 最新的會期
            
        Returns:
            List[Dict]: 最新的法案資料列表
        """
        all_bills = []
        page = 1
        found_old_data = False
        
        print(f"開始獲取最新資料（從第 {latest_term} 屆 第 {latest_session} 會期開始）...")
        
        while not found_old_data:
            try:
                bills = self.get_bills(term="all", page=page)
                if not bills:
                    break
                
                # 檢查每筆資料是否為新資料
                for bill in bills:
                    term = bill.get('term', '')
                    session = bill.get('sessionPeriod', '')
                    
                    # 如果找到舊資料，就停止
                    if (term < latest_term) or (term == latest_term and session <= latest_session):
                        found_old_data = True
                        break
                    
                    all_bills.append(bill)
                
                if found_old_data:
                    break
                
                print(f"成功獲取第 {page} 頁資料，共 {len(bills)} 筆（累計 {len(all_bills)} 筆新資料）")
                page += 1
                time.sleep(1)  # 添加延遲避免請求過快
                
            except Exception as e:
                print(f"獲取第 {page} 頁資料時發生錯誤: {str(e)}")
                time.sleep(5)  # 發生錯誤時多等待一下
                continue
        
        return all_bills
    
    def get_current_term_session(self) -> Tuple[str, str]:
        """獲取當前的屆別和會期
        
        Returns:
            Tuple[str, str]: (屆別, 會期)
        """
        bills = self.get_bills(page=1)
        if not bills:
            raise Exception("無法獲取最新資料")
        
        # 取得第一筆資料的屆別和會期
        latest_bill = bills[0]
        return latest_bill.get('term', ''), latest_bill.get('sessionPeriod', '')
    
    def get_all_bills(self, term: str = "all") -> List[Dict]:
        """獲取所有頁面的法案資料
        
        Args:
            term: 屆別，預設為 "all"
            
        Returns:
            List[Dict]: 所有法案資料列表
        """
        all_bills = []
        page = 1
        empty_pages = 0  # 連續空頁計數
        
        print(f"開始獲取 {term} 屆的資料...")
        
        while empty_pages < 3:  # 連續3頁都沒有資料才停止
            try:
                bills = self.get_bills(term=term, page=page)
                
                if not bills:
                    empty_pages += 1
                    print(f"第 {page} 頁沒有資料")
                else:
                    empty_pages = 0  # 重置空頁計數
                    all_bills.extend(bills)
                    print(f"成功獲取第 {page} 頁資料，共 {len(bills)} 筆（累計 {len(all_bills)} 筆）")
                
                page += 1
                time.sleep(1)  # 添加延遲避免請求過快
                
            except Exception as e:
                print(f"獲取第 {page} 頁資料時發生錯誤: {str(e)}")
                time.sleep(5)  # 發生錯誤時多等待一下
                continue
        
        return all_bills 