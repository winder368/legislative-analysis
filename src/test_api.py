import sys
import os
from pathlib import Path

# 將 src 目錄加入 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api_client import LYAPIClient
from src.analyzer import BillAnalyzer
from src.database import Database

def fetch_and_save_bills():
    """從 API 獲取資料並儲存到資料庫"""
    client = LYAPIClient()
    db = Database()
    
    try:
        print("開始從 API 獲取資料...")
        bills = client.get_all_bills()
        print(f"成功獲取 {len(bills)} 筆資料")
        
        print("正在儲存到資料庫...")
        db.save_bills(bills)
        print("資料儲存完成！")
        
    finally:
        db.close()

def analyze_bills():
    """分析資料庫中的法案資料"""
    db = Database()
    
    try:
        print("從資料庫讀取資料...")
        bills = db.get_all_bills()
        print(f"讀取到 {len(bills)} 筆資料")
        
        # 創建分析器
        analyzer = BillAnalyzer(bills)
        
        # 獲取修法熱點
        print("\n=== 修法熱點（前10名）===")
        hot_laws = analyzer.get_hot_laws(top_n=10)
        for law_name, count in hot_laws:
            print(f"\n{law_name}: {count} 件提案")
            
            # 顯示每個熱門法案的熱門條號
            print("熱門條號：")
            hot_articles = analyzer.get_hot_articles(law_name)
            if hot_articles:
                for article, article_count in hot_articles:
                    print(f"  第 {article} 條: {article_count} 件提案")
            else:
                print("  無法解析條號")
                
            # 顯示一些原始提案名稱作為範例
            print("\n提案範例：")
            sample_count = 0
            for bill in bills:
                if sample_count >= 3:  # 只顯示前3個範例
                    break
                bill_name = bill.get('billName', '')
                if law_name in analyzer.extract_law_name(bill_name):
                    print(f"  - {bill_name}")
                    sample_count += 1
            print("-" * 80)
            
    finally:
        db.close()

def main():
    # 檢查資料庫是否存在
    db_path = Path("data/bills.db")
    if not db_path.exists():
        print("資料庫不存在，開始從 API 獲取資料...")
        fetch_and_save_bills()
    
    # 分析資料
    analyze_bills()

if __name__ == "__main__":
    main() 