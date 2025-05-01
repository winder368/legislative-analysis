import sqlite3
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path
import os

class Database:
    """資料庫管理類"""
    
    def __init__(self):
        """初始化資料庫連接"""
        # 獲取當前腳本的目錄
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 確保 data 目錄存在
        data_dir = os.path.join(current_dir, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        self.db_path = os.path.join(data_dir, 'bills.db')
        print(f"連接資料庫: {os.path.abspath(self.db_path)}")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # 確保資料表存在
        self.create_tables()
    
    def create_tables(self):
        """創建資料表"""
        cursor = self.conn.cursor()
        
        # 建立法案資料表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            billNo TEXT,
            billName TEXT,
            billOrg TEXT,
            billProposer TEXT,
            billCosignatory TEXT,
            term TEXT,
            sessionPeriod TEXT,
            sessionTimes TEXT,
            billStatus TEXT,
            pdfUrl TEXT,
            docUrl TEXT,
            PRIMARY KEY (term, billNo)
        )
        """)
        
        # 建立立委資料表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS legislators (
            name TEXT,
            party TEXT,
            term TEXT,
            party_color TEXT
        )
        """)
        
        # 建立索引以加速查詢
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_name ON bills(billName)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_term_session ON bills(term, sessionPeriod)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legislators_name ON legislators(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legislators_term ON legislators(term)")
        
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
    
    def save_legislators(self, legislators: List[Dict]):
        """儲存立法委員資料
        
        Args:
            legislators: 立法委員資料列表
        """
        cursor = self.conn.cursor()
        
        # 政黨顏色對照表
        party_colors = {
            '中國國民黨': '#0000FF',  # 藍色
            '台灣民眾黨': '#87CEEB',  # 淺藍色
            '民主進步黨': '#008000',  # 綠色
            '新黨': '#FFFF00',        # 黃色
            '時代力量': '#FFD700',    # 鵝黃色
            '台灣基進': '#8B0000'     # 深紅色
        }
        
        for legislator in legislators:
            try:
                # 獲取政黨顏色
                party = legislator.get('party', '')
                party_color = party_colors.get(party, '#808080')  # 預設為灰色
                
                cursor.execute("""
                INSERT OR REPLACE INTO legislators (
                    term, name, party, party_color, constituency, committee,
                    education, experience, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    legislator.get('term'),
                    legislator.get('name'),
                    party,
                    party_color,
                    legislator.get('constituency'),
                    legislator.get('committee'),
                    legislator.get('education'),
                    legislator.get('experience')
                ))
            except sqlite3.Error as e:
                print(f"儲存立法委員資料時發生錯誤: {e}")
                print(f"委員資料: {json.dumps(legislator, ensure_ascii=False)}")
                continue
        
        self.conn.commit()
    
    def get_all_legislators(self) -> List[Dict]:
        """獲取所有立法委員資料
        
        Returns:
            List[Dict]: 立法委員資料列表
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM legislators")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_legislators_by_term(self, term: str) -> List[Dict]:
        """獲取特定屆別的立法委員資料
        
        Args:
            term: 屆別
            
        Returns:
            List[Dict]: 立法委員資料列表
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM legislators WHERE term = ?", (term,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_legislators_count(self) -> int:
        """獲取資料庫中的立法委員總數
        
        Returns:
            int: 立法委員總數
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM legislators")
        return cursor.fetchone()['count']
    
    def clear_legislators_data(self):
        """清除立法委員資料表中的所有資料"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM legislators")
            self.conn.commit()
            print("已成功清除所有立法委員資料")
        except sqlite3.Error as e:
            print(f"清除立法委員資料時發生錯誤: {e}")
            self.conn.rollback()
    
    def get_bills_with_party_colors(self, search_term: str = None) -> List[Dict]:
        """獲取法案資料，包含提案人的政黨顏色
        
        Args:
            search_term: 搜尋關鍵字
            
        Returns:
            List[Dict]: 法案資料列表，包含提案人的政黨顏色
        """
        cursor = self.conn.cursor()
        
        if search_term:
            cursor.execute("""
            SELECT b.*, l.party_color
            FROM bills b
            LEFT JOIN legislators l ON b.billProposer LIKE '%' || l.name || '%'
            WHERE b.billName LIKE ? OR b.billProposer LIKE ?
            ORDER BY b.term DESC, b.sessionPeriod DESC, b.sessionTimes DESC
            """, (f"%{search_term}%", f"%{search_term}%"))
        else:
            cursor.execute("""
            SELECT b.*, l.party_color
            FROM bills b
            LEFT JOIN legislators l ON b.billProposer LIKE '%' || l.name || '%'
            ORDER BY b.term DESC, b.sessionPeriod DESC, b.sessionTimes DESC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """關閉資料庫連接"""
        self.conn.close() 