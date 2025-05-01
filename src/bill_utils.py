"""處理法案相關的工具函數"""

def get_popular_bills_sql() -> str:
    """獲取熱門法案的 SQL 查詢語句"""
    return """
    WITH RawBillNames AS (
        SELECT 
            CASE 
                WHEN billName LIKE '%刑法%' AND billName NOT LIKE '%陸海空軍刑法%' THEN '中華民國刑法'
                WHEN billName LIKE '%所得稅法%' THEN '所得稅法'
                WHEN billName LIKE '%國土計畫法%' THEN '國土計畫法'
                WHEN billName LIKE '%環境基本法%' THEN '環境基本法'
                WHEN billName LIKE '%公務人員退休資遣撫卹法%' THEN '公務人員退休資遣撫卹法'
                WHEN billName LIKE '%性別平等工作法%' THEN '性別平等工作法'
                WHEN billName LIKE '%貨物稅條例%' THEN '貨物稅條例'
                WHEN billName LIKE '「%」%' THEN
                    SUBSTR(
                        SUBSTR(billName, INSTR(billName, '「') + 1),
                        1,
                        INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '」') - 1
                    )
                ELSE billName
            END as raw_name
        FROM bills
        WHERE term = '11'
    ),
    CleanBillNames AS (
        SELECT 
            CASE
                WHEN raw_name LIKE '%第%條%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '第') - 1)
                WHEN raw_name LIKE '%修正條文%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '修正條文') - 1)
                WHEN raw_name LIKE '%修正草案%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '修正草案') - 1)
                WHEN raw_name LIKE '%條文%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '條文') - 1)
                WHEN raw_name LIKE '%草案%' THEN
                    SUBSTR(raw_name, 1, INSTR(raw_name, '草案') - 1)
                ELSE raw_name
            END as clean_name
        FROM RawBillNames
    )
    SELECT 
        TRIM(clean_name) as law_name,
        COUNT(*) as total_count
    FROM CleanBillNames
    WHERE TRIM(clean_name) != ''
    GROUP BY TRIM(clean_name)
    ORDER BY total_count DESC, law_name
    LIMIT 30
    """

def clean_law_name(name: str) -> str:
    """清理法律名稱，移除條號等後綴
    
    Args:
        name: 原始法案名稱
        
    Returns:
        str: 清理後的法案名稱
    """
    # 移除引號
    name = name.strip('「」')
    
    # 特殊處理某些法案
    if '刑法' in name and '陸海空軍刑法' not in name:
        return '中華民國刑法'
    if '貨物稅條例' in name:
        return '貨物稅條例'
    
    # 依序移除後綴
    suffixes = ['修正條文', '修正草案', '條文', '草案']
    for suffix in suffixes:
        if suffix in name:
            name = name[:name.index(suffix)].strip()
            break
            
    # 移除條號（如果還有的話）
    if '第' in name and '條' in name:
        name = name[:name.index('第')].strip()
        
    return name 