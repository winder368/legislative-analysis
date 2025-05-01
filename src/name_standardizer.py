import re
from database import Database

def standardize_name(name: str) -> str:
    """標準化姓名
    
    Args:
        name: 原始姓名
        
    Returns:
        str: 標準化後的姓名
    """
    if not name:
        return ""
    
    # 移除所有空白字元（包括全形空格）
    name = re.sub(r'\s+', '', name)
    
    # 移除特殊符號
    name = name.replace('　', '')  # 移除全形空格
    
    return name

def update_bills_proposer_names():
    """更新提案資料庫中的提案人姓名"""
    db = Database()
    
    try:
        # 獲取所有提案
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, billProposer FROM bills WHERE billProposer IS NOT NULL")
        bills = cursor.fetchall()
        
        # 更新每個提案的提案人姓名
        for bill in bills:
            bill_id = bill['id']
            proposers = bill['billProposer']
            
            if not proposers:
                continue
                
            # 如果是委員會或行政院的提案，跳過
            if '委員會' in proposers or '行政院' in proposers:
                continue
            
            # 分割多個提案人
            proposer_list = proposers.split('　')  # 使用全形空格分割
            
            # 標準化每個提案人的姓名
            standardized_proposers = []
            for proposer in proposer_list:
                if proposer.strip():  # 確保不是空字串
                    standardized_name = standardize_name(proposer)
                    standardized_proposers.append(standardized_name)
            
            # 使用半形逗號合併提案人
            new_proposers = ','.join(standardized_proposers)
            
            # 更新資料庫
            try:
                cursor.execute("""
                UPDATE bills 
                SET billProposer = ?
                WHERE id = ?
                """, (new_proposers, bill_id))
                
            except Exception as e:
                print(f"更新提案 {bill_id} 時發生錯誤：{str(e)}")
                continue
        
        # 提交更改
        db.conn.commit()
        print("提案人姓名標準化完成")
        
    finally:
        db.close()

def check_name_consistency():
    """檢查委員資料和提案資料中的姓名一致性"""
    db = Database()
    
    try:
        # 獲取所有委員姓名
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM legislators")
        legislator_names = set(standardize_name(row['name']) for row in cursor.fetchall())
        
        # 獲取所有提案人姓名
        cursor.execute("""
        SELECT DISTINCT billProposer 
        FROM bills 
        WHERE billProposer IS NOT NULL 
        AND billProposer NOT LIKE '%委員會%' 
        AND billProposer NOT LIKE '%行政院%'
        """)
        
        proposer_names = set()
        for row in cursor.fetchall():
            if row['billProposer']:
                names = row['billProposer'].split(',')  # 使用逗號分割
                proposer_names.update(standardize_name(name) for name in names if name.strip())
        
        # 比較差異
        only_in_legislators = legislator_names - proposer_names
        only_in_bills = proposer_names - legislator_names
        
        print("\n姓名一致性檢查結果：")
        print(f"委員資料庫中有 {len(legislator_names)} 位委員")
        print(f"提案資料庫中有 {len(proposer_names)} 位提案人")
        
        if only_in_legislators:
            print("\n只在委員資料庫中出現的姓名：")
            for name in sorted(only_in_legislators):
                print(f"- {name}")
        
        if only_in_bills:
            print("\n只在提案資料庫中出現的姓名：")
            for name in sorted(only_in_bills):
                print(f"- {name}")
                
    finally:
        db.close()

if __name__ == "__main__":
    # 更新提案資料庫中的姓名
    print("開始更新提案資料庫中的姓名...")
    update_bills_proposer_names()
    
    # 檢查姓名一致性
    print("\n開始檢查姓名一致性...")
    check_name_consistency() 