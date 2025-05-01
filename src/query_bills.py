import sys
import os
from pathlib import Path
from typing import List, Dict

# 將 src 目錄加入 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import Database

def print_bills(bills: List[Dict], limit: int = None):
    """打印法案資料
    
    Args:
        bills: 法案列表
        limit: 限制顯示筆數
    """
    for i, bill in enumerate(bills, 1):
        if limit and i > limit:
            break
        print(f"\n第 {i} 筆提案:")
        print(f"提案名稱: {bill['billName']}")
        print(f"提案人: {bill['billProposer']}")
        print(f"連署人: {bill['billCosignatory']}")
        print(f"提案狀態: {bill['billStatus']}")
        print("-" * 80)

def main():
    db = Database()
    
    try:
        while True:
            print("\n=== 法案查詢系統 ===")
            print("1. 搜尋特定法律的提案")
            print("2. 查看最新提案")
            print("3. 依提案人查詢")
            print("4. 依連署人查詢")
            print("5. 查看提案狀態統計")
            print("0. 退出")
            
            choice = input("\n請選擇功能 (0-5): ")
            
            if choice == "0":
                break
            elif choice == "1":
                law_name = input("請輸入法律名稱（例如：刑法）: ")
                cursor = db.conn.cursor()
                cursor.execute("""
                SELECT * FROM bills 
                WHERE billName LIKE ? 
                ORDER BY term DESC, sessionPeriod DESC
                LIMIT 10
                """, (f"%{law_name}%",))
                bills = [dict(row) for row in cursor.fetchall()]
                print(f"\n找到 {len(bills)} 筆相關提案（顯示前10筆）：")
                print_bills(bills)
                
            elif choice == "2":
                cursor = db.conn.cursor()
                cursor.execute("""
                SELECT * FROM bills 
                ORDER BY term DESC, sessionPeriod DESC, sessionTimes DESC 
                LIMIT 5
                """)
                bills = [dict(row) for row in cursor.fetchall()]
                print("\n最新5筆提案：")
                print_bills(bills)
                
            elif choice == "3":
                proposer = input("請輸入提案人姓名: ")
                cursor = db.conn.cursor()
                cursor.execute("""
                SELECT * FROM bills 
                WHERE billProposer LIKE ? 
                ORDER BY term DESC, sessionPeriod DESC
                LIMIT 10
                """, (f"%{proposer}%",))
                bills = [dict(row) for row in cursor.fetchall()]
                print(f"\n找到 {len(bills)} 筆相關提案（顯示前10筆）：")
                print_bills(bills)
                
            elif choice == "4":
                cosignatory = input("請輸入連署人姓名: ")
                cursor = db.conn.cursor()
                cursor.execute("""
                SELECT * FROM bills 
                WHERE billCosignatory LIKE ? 
                ORDER BY term DESC, sessionPeriod DESC
                LIMIT 10
                """, (f"%{cosignatory}%",))
                bills = [dict(row) for row in cursor.fetchall()]
                print(f"\n找到 {len(bills)} 筆相關提案（顯示前10筆）：")
                print_bills(bills)
                
            elif choice == "5":
                cursor = db.conn.cursor()
                cursor.execute("""
                SELECT billStatus, COUNT(*) as count 
                FROM bills 
                GROUP BY billStatus 
                ORDER BY count DESC
                """)
                stats = cursor.fetchall()
                print("\n提案狀態統計：")
                for status in stats:
                    print(f"{status['billStatus']}: {status['count']} 件")
            
            input("\n按 Enter 繼續...")
            
    finally:
        db.close()

if __name__ == "__main__":
    main() 