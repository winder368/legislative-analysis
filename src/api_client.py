import requests
from typing import Dict, List, Optional, Tuple
import json
import time
import random
from datetime import datetime, timedelta
import logging
import os
import math

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_logs.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LYAPIClient")

class LYAPIClient:
    """立法院 API 客戶端"""
    
    BASE_URL = "https://data.ly.gov.tw/odw/openDatasetJson.action"
    
    def __init__(self, timeout=30, max_retries=5, retry_delay=2):
        """
        初始化 API 客戶端
        
        Args:
            timeout: 請求超時時間（秒）
            max_retries: 最大重試次數
            retry_delay: 初始重試延遲（秒）
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.ITEMS_PER_PAGE = 1000  # 每頁顯示的項目數量
        
        # 使用多種不同的 User-Agent
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
        ]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://data.ly.gov.tw/',
            'Origin': 'https://data.ly.gov.tw',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })
        
        # 檢查並創建日誌目錄
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
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
        
        retry_delay = self.retry_delay
        
        for attempt in range(self.max_retries):
            try:
                # 隨機延遲，避免頻繁請求
                jitter = random.uniform(0.5, 1.5)
                time.sleep(retry_delay * jitter if attempt > 0 else 0)
                
                # 隨機選擇 User-Agent
                user_agents = [
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
                ]
                self.session.headers.update({'User-Agent': random.choice(user_agents)})
                
                logger.info(f"正在請求第 {page} 頁的法案資料 (嘗試 {attempt + 1}/{self.max_retries})...")
                start_time = time.time()
                
                # 直接訪問帶有參數的URL
                url = f"{self.BASE_URL}?id=20&selectTerm={term}&page={page}"
                
                response = self.session.get(
                    url, 
                    timeout=self.timeout
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"請求完成，耗時 {elapsed_time:.2f} 秒，狀態碼: {response.status_code}")
                
                # 如果返回403，記錄更多信息
                if response.status_code == 403:
                    logger.error(f"收到403 Forbidden響應。URL: {url}")
                    logger.error(f"請求頭: {self.session.headers}")
                    raise requests.exceptions.HTTPError("403 Forbidden")
                
                response.raise_for_status()
                data = response.json()
                
                bills = data.get("jsonList", [])
                logger.info(f"成功獲取 {len(bills)} 筆資料")
                return bills
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"請求超時 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒後重試...")
                    retry_delay = min(retry_delay * 2, 60)  # 指數退避，但最大等待時間為60秒
                else:
                    logger.error(f"達到最大重試次數，請求失敗: {str(e)}")
                    raise
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"連接錯誤 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒後重試...")
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    logger.error(f"達到最大重試次數，請求失敗: {str(e)}")
                    raise
                    
            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP錯誤 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒後重試...")
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    logger.error(f"達到最大重試次數，請求失敗: {str(e)}")
                    raise
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"請求錯誤 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒後重試...")
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    logger.error(f"達到最大重試次數，請求失敗: {str(e)}")
                    raise
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析錯誤: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒後重試...")
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    logger.error(f"達到最大重試次數，請求失敗: {str(e)}")
                    raise
                    
        return []  # 如果所有嘗試都失敗，返回空列表
    
    def get_total_bills_count(self, term: str = "all") -> int:
        """獲取法案總數量
        
        Args:
            term: 屆別，預設為 "all"
            
        Returns:
            int: 法案總數量
        """
        # 先獲取第一頁，檢查回應中是否有總數資訊
        logger.info(f"獲取法案總數量 (term={term})...")
        
        # 嘗試直接通過頁碼計算總數
        # 立法院API可能沒有提供總數資訊，我們先嘗試獲取第一頁
        try:
            bills = self.get_bills(term=term, page=1)
            if not bills:
                logger.warning(f"無法獲取 {term} 屆的資料，返回0")
                return 0
                
            # 假設平均每屆有10頁資料，我們估算10屆約有100頁
            # 這裡只是一個粗略估計，較保守地估計為50頁
            estimated_pages = 50
            logger.info(f"將總頁數估計為 {estimated_pages} 頁")
            estimated_total = estimated_pages * self.ITEMS_PER_PAGE
            logger.info(f"估算總數: {estimated_total} 筆")
            return estimated_total
            
        except Exception as e:
            logger.error(f"獲取總數時出錯: {str(e)}")
            # 出錯時返回較小的估計值
            return 10000
    
    def get_latest_bills_reversed(self, latest_term: str, latest_session: str) -> List[Dict]:
        """從最新的資料開始獲取法案資料
        
        Args:
            latest_term: 資料庫中最新的屆別
            latest_session: 資料庫中最新的會期
            
        Returns:
            List[Dict]: 最新的法案資料列表
        """
        all_bills = []
        consecutive_errors = 0
        max_consecutive_errors = 3
        max_pages_to_check = 10  # 最多檢查10頁
        
        logger.info(f"開始獲取最新資料（從第 {latest_term} 屆 第 {latest_session} 會期之後的資料）...")
        
        page = 1
        found_old_data = False
        
        while page <= max_pages_to_check and not found_old_data:
            try:
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"連續 {consecutive_errors} 次錯誤，停止獲取資料")
                    break
                    
                logger.info(f"正在獲取第 {page} 頁資料 (最多檢查 {max_pages_to_check} 頁)...")
                bills = self.get_bills(term="all", page=page)
                
                if not bills:
                    logger.info(f"第 {page} 頁沒有資料，停止獲取")
                    break
                
                # 檢查每筆資料是否為新資料
                new_bills = []
                for bill in bills:
                    term = bill.get('term', '')
                    session = bill.get('sessionPeriod', '')
                    
                    # 處理數據中可能的非數字屆別和會期
                    try:
                        term_int = int(term) if term else 0
                        session_int = int(session) if session else 0
                        latest_term_int = int(latest_term) if latest_term else 0
                        latest_session_int = int(latest_session) if latest_session else 0
                    except ValueError:
                        logger.warning(f"無法轉換屆別或會期為整數: term={term}, session={session}")
                        continue
                    
                    # 記錄詳細的比較資訊
                    logger.debug(f"比較: 當前資料 (第 {term} 屆 第 {session} 會期) vs 資料庫最新 (第 {latest_term} 屆 第 {latest_session} 會期)")
                    
                    # 如果找到舊資料，就停止
                    if (term_int < latest_term_int) or (term_int == latest_term_int and session_int <= latest_session_int):
                        logger.info(f"已找到舊資料 (第 {term} 屆 第 {session} 會期)，停止獲取")
                        found_old_data = True
                        break
                    
                    new_bills.append(bill)
                
                # 添加新資料到結果列表
                all_bills.extend(new_bills)
                logger.info(f"第 {page} 頁: 共 {len(new_bills)} 筆新資料（累計 {len(all_bills)} 筆新資料）")
                
                if found_old_data:
                    break
                
                page += 1
                consecutive_errors = 0  # 重置連續錯誤計數
                
                # 添加隨機延遲避免請求過快
                delay = random.uniform(2, 5)
                logger.info(f"等待 {delay:.2f} 秒後繼續...")
                time.sleep(delay)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"獲取第 {page} 頁資料時發生錯誤 ({consecutive_errors}/{max_consecutive_errors}): {str(e)}")
                
                # 如果發生錯誤，增加等待時間
                wait_time = min(5 * consecutive_errors, 30)
                logger.info(f"等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                
                # 如果已嘗試多次但仍失敗，則跳過當前頁面
                if consecutive_errors >= 3:
                    logger.warning(f"連續 {consecutive_errors} 次失敗，跳過第 {page} 頁")
                    page += 1
                    consecutive_errors = 0
        
        logger.info(f"資料獲取完成，共 {len(all_bills)} 筆新資料")
        return all_bills
    
    def get_latest_bills(self, latest_term: str, latest_session: str) -> List[Dict]:
        """獲取最新的法案資料（使用新的逆序方法）
        
        Args:
            latest_term: 最新的屆別
            latest_session: 最新的會期
            
        Returns:
            List[Dict]: 最新的法案資料列表
        """
        return self.get_latest_bills_reversed(latest_term, latest_session)
    
    def get_current_term_session(self) -> Tuple[str, str]:
        """獲取當前的屆別和會期
        
        Returns:
            Tuple[str, str]: (屆別, 會期)
        """
        logger.info("嘗試獲取當前的屆別和會期...")
        bills = self.get_bills(page=1)
        if not bills:
            error_msg = "無法獲取最新資料"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 取得第一筆資料的屆別和會期
        latest_bill = bills[0]
        term = latest_bill.get('term', '')
        session = latest_bill.get('sessionPeriod', '')
        logger.info(f"當前屆別和會期: 第 {term} 屆 第 {session} 會期")
        return term, session
    
    def get_all_bills(self, term: str = "all") -> List[Dict]:
        """獲取所有頁面的法案資料
        
        Args:
            term: 屆別，預設為 "all"
            
        Returns:
            List[Dict]: 所有法案資料列表
        """
        all_bills = []
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        # 先獲取總數，計算總頁數
        total_count = self.get_total_bills_count(term)
        if total_count == 0:
            logger.warning(f"無法獲取 {term} 屆的總數，將使用舊方法獲取資料")
            return self._get_all_bills_old_method(term)
        
        total_pages = math.ceil(total_count / self.ITEMS_PER_PAGE)
        logger.info(f"{term} 屆總資料量: {total_count} 筆，共 {total_pages} 頁")
        
        for page in range(1, total_pages + 1):
            try:
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"連續 {consecutive_errors} 次錯誤，停止獲取資料")
                    break
                    
                logger.info(f"正在獲取第 {page}/{total_pages} 頁資料...")
                bills = self.get_bills(term=term, page=page)
                
                if not bills:
                    logger.warning(f"第 {page} 頁沒有資料，但預期應該有資料")
                    consecutive_errors += 1
                    continue
                
                all_bills.extend(bills)
                logger.info(f"成功獲取第 {page} 頁資料，共 {len(bills)} 筆（累計 {len(all_bills)} 筆）")
                
                consecutive_errors = 0  # 重置連續錯誤計數
                
                # 添加延遲避免請求過快
                delay = 2
                logger.info(f"等待 {delay} 秒後繼續...")
                time.sleep(delay)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"獲取第 {page} 頁資料時發生錯誤 ({consecutive_errors}/{max_consecutive_errors}): {str(e)}")
                
                # 如果發生錯誤，增加等待時間
                wait_time = min(5 * consecutive_errors, 30)
                logger.info(f"等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                
                # 如果已嘗試多次但仍失敗，則跳過當前頁面
                if consecutive_errors >= 3:
                    logger.warning(f"連續 {consecutive_errors} 次失敗，跳過第 {page} 頁")
                    consecutive_errors = 0
        
        logger.info(f"資料獲取完成，共 {len(all_bills)} 筆資料")
        return all_bills
        
    def _get_all_bills_old_method(self, term: str = "all") -> List[Dict]:
        """使用舊方法獲取所有頁面的法案資料（當無法獲取總數時使用）
        
        Args:
            term: 屆別，預設為 "all"
            
        Returns:
            List[Dict]: 所有法案資料列表
        """
        all_bills = []
        page = 1
        empty_pages = 0  # 連續空頁計數
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        logger.info(f"開始使用舊方法獲取 {term} 屆的所有資料...")
        
        while empty_pages < 3:  # 連續3頁都沒有資料才停止
            try:
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"連續 {consecutive_errors} 次錯誤，停止獲取資料")
                    break
                    
                logger.info(f"正在獲取第 {page} 頁資料...")
                bills = self.get_bills(term=term, page=page)
                
                if not bills:
                    empty_pages += 1
                    logger.info(f"第 {page} 頁沒有資料 ({empty_pages}/3)")
                else:
                    empty_pages = 0  # 重置空頁計數
                    all_bills.extend(bills)
                    logger.info(f"成功獲取第 {page} 頁資料，共 {len(bills)} 筆（累計 {len(all_bills)} 筆）")
                
                page += 1
                consecutive_errors = 0  # 重置連續錯誤計數
                
                # 添加延遲避免請求過快
                delay = 2
                logger.info(f"等待 {delay} 秒後繼續...")
                time.sleep(delay)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"獲取第 {page} 頁資料時發生錯誤 ({consecutive_errors}/{max_consecutive_errors}): {str(e)}")
                
                # 如果發生錯誤，增加等待時間
                wait_time = min(5 * consecutive_errors, 30)
                logger.info(f"等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                
                # 如果已嘗試多次但仍失敗，則跳過當前頁面
                if consecutive_errors >= 3:
                    logger.warning(f"連續 {consecutive_errors} 次失敗，跳過第 {page} 頁")
                    page += 1
                    consecutive_errors = 0
        
        logger.info(f"舊方法資料獲取完成，共 {len(all_bills)} 筆資料")
        return all_bills 