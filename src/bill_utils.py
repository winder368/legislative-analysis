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
                    CASE
                        WHEN SUBSTR(
                            SUBSTR(billName, INSTR(billName, '「') + 1),
                            1,
                            INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '」') - 1
                        ) LIKE '%部分條文%' THEN
                            REPLACE(
                                SUBSTR(
                                    SUBSTR(billName, INSTR(billName, '「') + 1),
                                    1,
                                    INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '部分條文') - 1
                                ),
                                '修正草案',
                                ''
                            )
                        ELSE
                            SUBSTR(
                                SUBSTR(billName, INSTR(billName, '「') + 1),
                                1,
                                INSTR(SUBSTR(billName, INSTR(billName, '「') + 1), '」') - 1
                            )
                    END
                ELSE billName
            END as raw_name
        FROM bills
        WHERE term = '11'
    ),
    CleanBillNames AS (
        SELECT 
            CASE
                WHEN raw_name = '中華民國刑法' THEN '中華民國刑法'
                WHEN raw_name = '所得稅法' THEN '所得稅法'
                WHEN raw_name = '國土計畫法' THEN '國土計畫法'
                WHEN raw_name = '環境基本法' THEN '環境基本法'
                WHEN raw_name = '公務人員退休資遣撫卹法' THEN '公務人員退休資遣撫卹法'
                WHEN raw_name = '性別平等工作法' THEN '性別平等工作法'
                WHEN raw_name = '貨物稅條例' THEN '貨物稅條例'
                WHEN raw_name LIKE '%部分條文%' THEN
                    REPLACE(
                        SUBSTR(raw_name, 1, INSTR(raw_name, '部分條文') - 1),
                        '修正草案',
                        ''
                    )
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
    if '陸海空軍刑法' in name or '軍刑法' in name:
        return '陸海空軍刑法'
    if '刑法' in name and '陸海空軍刑法' not in name:
        return '中華民國刑法'
    if '民法' in name and '國民法官法' not in name and '入出國及移民法' not in name:
        return '民法'
    if '國民法官法' in name:
        return '國民法官法'
    if '入出國及移民法' in name:
        return '入出國及移民法'
    if '所得稅法' in name:
        return '所得稅法'
    if '國土計畫法' in name:
        return '國土計畫法'
    if '環境基本法' in name:
        return '環境基本法'
    if '公務人員退休資遣撫卹法' in name or '退撫法' in name:
        return '公務人員退休資遣撫卹法'
    if '性別平等工作法' in name or '性工法' in name:
        return '性別平等工作法'
    if '貨物稅條例' in name:
        return '貨物稅條例'
    if '勞動基準法' in name or '勞基法' in name:
        return '勞動基準法'
    if '就業服務法' in name or '就服法' in name:
        return '就業服務法'
    if '全民健康保險法' in name or '健保法' in name:
        return '全民健康保險法'
    if '社會秩序維護法' in name or '社維法' in name:
        return '社會秩序維護法'
    if '道路交通管理處罰條例' in name or '道交條例' in name:
        return '道路交通管理處罰條例'
    if '消費者保護法' in name or '消保法' in name:
        return '消費者保護法'
    if '著作權法' in name:
        return '著作權法'
    if '商標法' in name:
        return '商標法'
    if '專利法' in name:
        return '專利法'
    if '公司法' in name:
        return '公司法'
    if '證券交易法' in name or '證交法' in name:
        return '證券交易法'
    if '銀行法' in name:
        return '銀行法'
    if '保險法' in name:
        return '保險法'
    if '信託法' in name:
        return '信託法'
    if '票據法' in name:
        return '票據法'
    if '海商法' in name:
        return '海商法'
    if '破產法' in name:
        return '破產法'
    if '強制執行法' in name:
        return '強制執行法'
    if '民事訴訟法' in name or '民訴' in name:
        return '民事訴訟法'
    if '刑事訴訟法' in name or '刑訴' in name:
        return '刑事訴訟法'
    if '行政訴訟法' in name or '行訴' in name:
        return '行政訴訟法'
    if '行政程序法' in name or '行程' in name:
        return '行政程序法'
    if '國家賠償法' in name or '國賠' in name:
        return '國家賠償法'
    if '公務員服務法' in name or '服勤法' in name:
        return '公務員服務法'
    if '公務人員任用法' in name or '任用條例' in name:
        return '公務人員任用法'
    if '公務人員考績法' in name or '考績法' in name:
        return '公務人員考績法'
    if '公務人員保障法' in name or '保障法' in name:
        return '公務人員保障法'
    if '公務人員陞遷法' in name or '陞遷法' in name:
        return '公務人員陞遷法'
    if '公務人員撫卹法' in name or '撫卹法' in name:
        return '公務人員撫卹法'
    if '公務人員保險法' in name or '公保法' in name:
        return '公務人員保險法'
    if '公務人員俸給法' in name or '俸給法' in name:
        return '公務人員俸給法'
    if '公務人員交代條例' in name or '交代條例' in name:
        return '公務人員交代條例'
    if '公務人員財產申報法' in name or '財產申報法' in name:
        return '公務人員財產申報法'
    if '公務人員行政中立法' in name or '行政中立法' in name:
        return '公務人員行政中立法'
    if '公務人員協會法' in name or '協會法' in name:
        return '公務人員協會法'
    if '公務人員訓練進修法' in name or '訓練進修法' in name:
        return '公務人員訓練進修法'
    if '公務人員懲戒法' in name or '公懲法' in name:
        return '公務人員懲戒法'
    if '公務人員考績法施行細則' in name or '考績法施行細則' in name:
        return '公務人員考績法施行細則'
    if '公務人員退休法施行細則' in name or '退休法施行細則' in name:
        return '公務人員退休法施行細則'
    if '公務人員撫卹法施行細則' in name or '撫卹法施行細則' in name:
        return '公務人員撫卹法施行細則'
    if '公務人員保險法施行細則' in name or '公保法施行細則' in name:
        return '公務人員保險法施行細則'
    if '公務人員俸給法施行細則' in name or '俸給法施行細則' in name:
        return '公務人員俸給法施行細則'
    if '公務人員請假規則施行細則' in name or '請假規則施行細則' in name:
        return '公務人員請假規則施行細則'
    if '公務人員交代條例施行細則' in name or '交代條例施行細則' in name:
        return '公務人員交代條例施行細則'
    if '公務人員財產申報法施行細則' in name or '財產申報法施行細則' in name:
        return '公務人員財產申報法施行細則'
    if '公務人員行政中立法施行細則' in name or '行政中立法施行細則' in name:
        return '公務人員行政中立法施行細則'
    if '公務人員協會法施行細則' in name or '協會法施行細則' in name:
        return '公務人員協會法施行細則'
    if '公務人員訓練進修法施行細則' in name or '訓練進修法施行細則' in name:
        return '公務人員訓練進修法施行細則'
    if '公務人員懲戒法施行細則' in name or '懲戒法施行細則' in name:
        return '公務人員懲戒法施行細則'
    
    # 依序移除後綴
    suffixes = ['修正條文', '修正草案', '條文', '草案']
    for suffix in suffixes:
        if suffix in name:
            name = name[:name.index(suffix)].strip()
            break
            
    # 移除條號（如果還有的話）
    if '第' in name and '條' in name:
        # 找到最後一個「第」的位置
        last_index = name.rindex('第')
        name = name[:last_index].strip()
        
    return name 