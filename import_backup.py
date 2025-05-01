import json
from src.database import Database
import sqlite3

def import_backups():
    db = Database()
    
    try:
        # 匯入法案資料
        print("正在匯入法案資料...")
        with open('data/bills_backup_20250502_010459.json', 'r', encoding='utf-8') as f:
            bills = json.load(f)
            cursor = db.conn.cursor()
            
            # 先刪除所有資料和索引
            cursor.execute("DROP TABLE IF EXISTS bills")
            cursor.execute("DROP TABLE IF EXISTS legislators")
            
            # 重新建立資料表
            cursor.execute("""
                CREATE TABLE bills (
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
            
            cursor.execute("""
                CREATE TABLE legislators (
                    name TEXT,
                    party TEXT,
                    term TEXT,
                    party_color TEXT
                )
            """)
            
            # 匯入法案資料
            for bill in bills:
                try:
                    cursor.execute("""
                        INSERT INTO bills (
                            billNo, billName, billOrg, billProposer, billCosignatory,
                            term, sessionPeriod, sessionTimes, billStatus, pdfUrl, docUrl
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bill.get('billNo'), bill.get('billName'), bill.get('billOrg'),
                        bill.get('billProposer'), bill.get('billCosignatory'),
                        bill.get('term'), bill.get('sessionPeriod'), bill.get('sessionTimes'),
                        bill.get('billStatus'), bill.get('pdfUrl'), bill.get('docUrl')
                    ))
                except sqlite3.IntegrityError:
                    continue
        
        # 匯入立委資料
        print("正在匯入立委資料...")
        with open('data/legislators_backup_20250502_025721.json', 'r', encoding='utf-8') as f:
            legislators = json.load(f)
            for legislator in legislators:
                try:
                    cursor.execute("""
                        INSERT INTO legislators (
                            name, party, term, party_color
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        legislator.get('name'), legislator.get('party'),
                        legislator.get('term'), legislator.get('party_color')
                    ))
                except sqlite3.IntegrityError:
                    continue
        
        # 建立索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_name ON bills(billName)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_term_session ON bills(term, sessionPeriod)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legislators_name ON legislators(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_legislators_term ON legislators(term)")
        
        db.conn.commit()
        print("資料匯入完成！")
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
        db.conn.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    import_backups() 