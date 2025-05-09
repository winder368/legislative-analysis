import os
import shutil
import glob
import logging
from pathlib import Path

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("organize_backups.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OrganizeBackups")

def get_data_dir():
    """獲取資料目錄路徑"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

def get_backup_dirs():
    """獲取備份目錄路徑"""
    data_dir = get_data_dir()
    backup_dir = os.path.join(data_dir, 'backups')
    db_backup_dir = os.path.join(backup_dir, 'database')
    page_backup_dir = os.path.join(backup_dir, 'pages')
    
    # 確保目錄存在
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(db_backup_dir, exist_ok=True)
    os.makedirs(page_backup_dir, exist_ok=True)
    
    return {
        'backup': backup_dir,
        'database': db_backup_dir,
        'pages': page_backup_dir
    }

def organize_backups():
    """整理舊的備份文件到新的備份目錄結構"""
    logger.info("開始整理備份文件...")
    
    data_dir = get_data_dir()
    backup_dirs = get_backup_dirs()
    
    # 移動資料庫備份 (*.db) 到 database 資料夾
    db_backup_pattern = os.path.join(data_dir, "*backup*.db")
    db_backup_files = glob.glob(db_backup_pattern)
    
    logger.info(f"找到 {len(db_backup_files)} 個資料庫備份文件")
    for file_path in db_backup_files:
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(backup_dirs['database'], file_name)
        
        if os.path.exists(dest_path):
            logger.warning(f"目標文件已存在，跳過: {dest_path}")
            continue
            
        try:
            shutil.copy2(file_path, dest_path)
            logger.info(f"已複製資料庫備份: {file_name} -> {dest_path}")
        except Exception as e:
            logger.error(f"複製文件時發生錯誤: {file_path} -> {e}")
    
    # 移動頁面備份 (page_*.json) 到 pages 資料夾
    page_backup_pattern = os.path.join(data_dir, "page_*.json")
    page_backup_files = glob.glob(page_backup_pattern)
    
    logger.info(f"找到 {len(page_backup_files)} 個頁面備份文件")
    for file_path in page_backup_files:
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(backup_dirs['pages'], file_name)
        
        if os.path.exists(dest_path):
            logger.warning(f"目標文件已存在，跳過: {dest_path}")
            continue
            
        try:
            shutil.copy2(file_path, dest_path)
            logger.info(f"已複製頁面備份: {file_name} -> {dest_path}")
        except Exception as e:
            logger.error(f"複製文件時發生錯誤: {file_path} -> {e}")
    
    # 移動其他備份文件 (*backup*.json) 到 backup 根目錄
    other_backup_pattern = os.path.join(data_dir, "*backup*.json")
    other_backup_files = glob.glob(other_backup_pattern)
    
    logger.info(f"找到 {len(other_backup_files)} 個其他備份文件")
    for file_path in other_backup_files:
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(backup_dirs['backup'], file_name)
        
        if os.path.exists(dest_path):
            logger.warning(f"目標文件已存在，跳過: {dest_path}")
            continue
            
        try:
            shutil.copy2(file_path, dest_path)
            logger.info(f"已複製其他備份: {file_name} -> {dest_path}")
        except Exception as e:
            logger.error(f"複製文件時發生錯誤: {file_path} -> {e}")
    
    logger.info("備份文件整理完成！")
    
    # 統計信息
    logger.info("備份目錄統計信息:")
    logger.info(f"資料庫備份: {len(glob.glob(os.path.join(backup_dirs['database'], '*.db')))} 個文件")
    logger.info(f"頁面備份: {len(glob.glob(os.path.join(backup_dirs['pages'], '*.json')))} 個文件")
    logger.info(f"其他備份: {len(glob.glob(os.path.join(backup_dirs['backup'], '*.json')))} 個文件")
    
def main():
    organize_backups()
    
if __name__ == "__main__":
    main() 