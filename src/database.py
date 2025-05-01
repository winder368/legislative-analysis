import sqlite3
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path

class Database:
    """資料庫管理類"""
    
    def __init__(self, db_path: str = "data/bills.db"):
        """初始化資料庫連接
        
        Args:
            db_path: 資料庫檔案路徑
        """
        # 確保資料目錄存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        """創建資料表"""
        cursor = self.conn.cursor()
        
        # 建立法案資料表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT,                    -- 屆別
            sessionPeriod TEXT,           -- 會期
            sessionTimes TEXT,            -- 會次
            meetingTimes TEXT,            -- 臨時會會次
            billNo TEXT,                  -- 議案編號
            billName TEXT,                -- 提案名稱
            billOrg TEXT,                 -- 提案單位/委員
            billProposer TEXT,            -- 提案人
            billCosignatory TEXT,         -- 連署人
            billStatus TEXT,              -- 議案狀態
            pdfUrl TEXT,                  -- PDF檔案位置
            docUrl TEXT,                  -- DOC檔案位置
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(term, billNo)          -- 確保不會重複儲存同一個提案
        )
        """)
        
        # 建立索引以加速查詢
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_name ON bills(billName)")
        except sqlite3.Error as e:
            print(f"建立索引 idx_bills_name 時發生錯誤: {e}")
            
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_term_session ON bills(term, sessionPeriod)")
        except sqlite3.Error as e:
            print(f"建立索引 idx_bills_term_session 時發生錯誤: {e}")
        
        self.conn.commit()
    
    def get_latest_term_session(self) -> Optional[Tuple[str, str]]:
        """獲取資料庫中最新的屆別和會期
        
        Returns:
            Optional[Tuple[str, str]]: (屆別, 會期)，如果資料庫為空則返回 None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT term, sessionPeriod 
        FROM bills 
        ORDER BY CAST(term AS INTEGER) DESC, CAST(sessionPeriod AS INTEGER) DESC 
        LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return row['term'], row['sessionPeriod']
        return None
    
    def save_bills(self, bills: List[Dict]):
        """儲存法案資料
        
        Args:
            bills: 法案資料列表
        """
        cursor = self.conn.cursor()
        
        for bill in bills:
            try:
                cursor.execute("""
                INSERT OR REPLACE INTO bills (
                    term, sessionPeriod, sessionTimes, meetingTimes,
                    billNo, billName, billOrg, billProposer,
                    billCosignatory, billStatus, pdfUrl, docUrl,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    bill.get('term'),
                    bill.get('sessionPeriod'),
                    bill.get('sessionTimes'),
                    bill.get('meetingTimes'),
                    bill.get('billNo'),
                    bill.get('billName'),
                    bill.get('billOrg'),
                    bill.get('billProposer'),
                    bill.get('billCosignatory'),
                    bill.get('billStatus'),
                    bill.get('pdfUrl'),
                    bill.get('docUrl')
                ))
            except sqlite3.Error as e:
                print(f"儲存提案時發生錯誤: {e}")
                print(f"提案資料: {json.dumps(bill, ensure_ascii=False)}")
                continue
        
        self.conn.commit()
    
    def get_all_bills(self) -> List[Dict]:
        """獲取所有法案資料
        
        Returns:
            List[Dict]: 法案資料列表
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM bills")
        return [dict(row) for row in cursor.fetchall()]
    
    def search_bills_by_law(self, law_name: str) -> List[Dict]:
        """搜尋特定法律的相關提案
        
        Args:
            law_name: 法律名稱
            
        Returns:
            List[Dict]: 相關提案列表
        """
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM bills 
        WHERE billName LIKE ? 
        ORDER BY term DESC, sessionPeriod DESC, sessionTimes DESC
        """, (f"%{law_name}%",))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_bills_count(self) -> int:
        """獲取資料庫中的法案總數
        
        Returns:
            int: 法案總數
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM bills")
        return cursor.fetchone()['count']
    
    def clear_all_data(self):
        """清除資料表中的所有資料"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM bills")
            self.conn.commit()
            print("已成功清除所有資料")
        except sqlite3.Error as e:
            print(f"清除資料時發生錯誤: {e}")
            self.conn.rollback()
    
    def close(self):
        """關閉資料庫連接"""
        self.conn.close() 