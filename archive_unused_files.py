import os
import shutil
import logging
from datetime import datetime

# 設置日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("archive_files.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ArchiveFiles")

# 核心文件列表 - 這些文件是項目的主要部分，不應被歸檔
CORE_FILES = [
    'app.py',  # Flask 應用主文件
    'streamlit_app.py',  # Streamlit 應用主文件
    'st_utils.py',       # Streamlit 工具函數
    
    # src 目錄核心文件
    'src/database.py',  # 資料庫處理
    'src/api_client.py',  # API 客戶端
    'src/bill_utils.py',  # 提案處理工具
    'src/db_config.py',   # 資料庫配置
    'src/update_bills.py',  # 更新提案 (render.yaml 中使用)
    'src/update_bills_from_page.py',  # 更新提案的主要工具
    'src/organize_backups.py',  # 備份整理工具
    'src/reset_and_download_all.py',  # 重置並下載所有資料
    'src/name_standardizer.py',  # 姓名標準化工具
    'src/analyzer.py',  # 分析工具
    'src/query_bills.py'  # 查詢提案
]

# 可能需要歸檔的文件 (這些是診斷、測試、輔助工具，可能不常用)
CANDIDATE_FILES = [
    'check_api.py',
    'check_api_simple.py',
    'download_bill_comparison.py',
    'download_historical_legislators.py',
    'download_legislators.py',  # 已有src/download_legislators.py
    'import_backup.py',
    
    'src/check_latest_data.py',  # 測試工具
    'src/clear_database.py',     # 可由reset_database.py替代
    'src/create_tables.py',      # 資料庫初始化已包含在database.py中
    'src/diagnose_api.py',       # 診斷工具
    'src/download_bills.py',     # 可由update_bills_from_page.py替代
    'src/download_legislators.py',  # 立法委員下載工具
    'src/reset_database.py',     # 可由reset_and_download_all.py替代
    'src/test_api.py',           # 測試工具
    'src/update_party_colors.py'  # 更新黨派顏色的輔助工具
]

def ensure_archive_dir():
    """確保歸檔目錄存在"""
    archive_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'archive')
    src_archive_dir = os.path.join(archive_dir, 'src')
    
    # 確保目錄存在
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(src_archive_dir, exist_ok=True)
    
    logger.info(f"歸檔目錄: {archive_dir}")
    return archive_dir

def archive_file(file_path, archive_dir):
    """將文件移動到歸檔目錄"""
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return False
    
    # 確定目標路徑
    if file_path.startswith('src/'):
        rel_path = file_path[4:]  # 移除 'src/'
        dest_dir = os.path.join(archive_dir, 'src')
    else:
        rel_path = os.path.basename(file_path)
        dest_dir = archive_dir
    
    dest_path = os.path.join(dest_dir, rel_path)
    
    # 如果目標文件已存在，添加時間戳
    if os.path.exists(dest_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name, file_ext = os.path.splitext(rel_path)
        dest_path = os.path.join(dest_dir, f"{file_name}_{timestamp}{file_ext}")
    
    # 移動文件
    try:
        shutil.copy2(file_path, dest_path)
        logger.info(f"已複製文件到歸檔目錄: {file_path} -> {dest_path}")
        return True
    except Exception as e:
        logger.error(f"歸檔文件時發生錯誤: {file_path} -> {e}")
        return False

def interactive_archive():
    """交互式歸檔不再使用的文件"""
    archive_dir = ensure_archive_dir()
    
    logger.info("開始交互式歸檔...")
    logger.info("核心文件 (不會被歸檔):")
    for file in CORE_FILES:
        logger.info(f"  - {file}")
    
    logger.info("\n建議歸檔的文件:")
    for i, file in enumerate(CANDIDATE_FILES, 1):
        exists = "✓" if os.path.exists(file) else "✗"
        logger.info(f"  {i}. {file} {exists}")
    
    # 詢問用戶要歸檔哪些文件
    print("\n請選擇要歸檔的文件編號 (用逗號分隔，輸入 'all' 全選，輸入 'q' 退出):")
    choice = input("> ").strip().lower()
    
    if choice == 'q':
        logger.info("操作已取消")
        return
    
    # 確定要歸檔的文件列表
    files_to_archive = []
    if choice == 'all':
        # 僅選擇存在的文件
        files_to_archive = [f for f in CANDIDATE_FILES if os.path.exists(f)]
        if len(files_to_archive) < len(CANDIDATE_FILES):
            logger.warning(f"注意: 有 {len(CANDIDATE_FILES) - len(files_to_archive)} 個文件不存在，將被跳過")
    else:
        try:
            indices = [int(idx.strip()) for idx in choice.split(',') if idx.strip()]
            for idx in indices:
                if 1 <= idx <= len(CANDIDATE_FILES):
                    file_path = CANDIDATE_FILES[idx-1]
                    if os.path.exists(file_path):
                        files_to_archive.append(file_path)
                    else:
                        logger.warning(f"文件不存在，將被跳過: {file_path}")
                else:
                    logger.warning(f"無效的編號: {idx}")
        except ValueError:
            logger.error("輸入格式不正確")
            return
    
    if not files_to_archive:
        logger.info("沒有選擇任何有效文件，操作已取消")
        return
    
    # 執行歸檔
    logger.info("\n正在歸檔以下文件:")
    for file in files_to_archive:
        logger.info(f"  - {file}")
    
    confirm = input("\n確認歸檔這些文件？ (y/n): ").strip().lower()
    if confirm != 'y':
        logger.info("操作已取消")
        return
    
    # 執行歸檔
    archived_count = 0
    for file in files_to_archive:
        if archive_file(file, archive_dir):
            archived_count += 1
    
    logger.info(f"歸檔完成！共歸檔了 {archived_count} 個文件")

def main():
    logger.info("======= 開始歸檔不再使用的文件 =======")
    interactive_archive()
    logger.info("======= 歸檔操作完成 =======")

if __name__ == "__main__":
    main() 