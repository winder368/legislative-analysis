from database import Database

def update_party_colors():
    """更新委員資料庫中的政黨顏色"""
    db = Database()
    
    try:
        cursor = db.conn.cursor()
        
        # 政黨顏色對照表
        party_colors = {
            '中國國民黨': '#0000FF',  # 藍色
            '台灣民眾黨': '#87CEEB',  # 淺藍色
            '民主進步黨': '#008000',  # 綠色
            '新黨': '#FFFF00',        # 黃色
            '時代力量': '#FFD700',    # 鵝黃色
            '台灣基進': '#8B0000'     # 深紅色
        }
        
        # 更新每個委員的政黨顏色
        for party, color in party_colors.items():
            cursor.execute("""
            UPDATE legislators 
            SET party_color = ?
            WHERE party = ?
            """, (color, party))
        
        # 將其他政黨設為灰色
        cursor.execute("""
        UPDATE legislators 
        SET party_color = '#808080'
        WHERE party_color IS NULL
        """)
        
        db.conn.commit()
        print("政黨顏色更新完成")
        
    finally:
        db.close()

if __name__ == "__main__":
    update_party_colors() 