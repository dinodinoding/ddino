import os
import sys
import time
import shutil
from datetime import datetime

# 콘솔 한글 깨짐 방지 설정
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

# 실행 위치 정확하게 판단: .py, .exe 모두 호환
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# 🔧 복사 주기 설정 (1분 = 60초)
COPY_INTERVAL_SECONDS = 60 

def copy_log_file(source_path, dest_path):
    if not os.path.exists(source_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER ERROR] Original log file source not found: {source_path}")
        return False

    try:
        # 원본 파일을 임시 파일로 복사 (덮어쓰기)
        # shutil.copy2는 메타데이터(수정 시간 등)도 복사하여 PyInstaller 환경에서 오류를 줄입니다.
        shutil.copy2(source_path, dest_path)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER INFO] Log file copied from '{source_path}' to '{dest_path}'.")
        return True
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER ERROR] Failed to copy log file: {e}")
        return False

if __name__ == "__main__":
    # GUI에서 인자를 받도록 변경: sys.argv[1] = original_log_source_path, sys.argv[2] = temp_log_dest_path
    if len(sys.argv) < 3:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER ERROR] Usage: {sys.argv[0]} <original_log_source_path> <temp_log_dest_path>")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER ERROR] This script should be started by the GUI application.")
        sys.exit(1)

    ORIGINAL_LOG_SOURCE_PATH = sys.argv[1]
    TEMP_LOG_DEST_PATH = sys.argv[2]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER START] Log copier started. Copying every {COPY_INTERVAL_SECONDS} seconds.")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER INFO] Original Source: '{ORIGINAL_LOG_SOURCE_PATH}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [COPIER INFO] Temporary Destination: '{TEMP_LOG_DEST_PATH}'")
    
    # 첫 실행 시 바로 한 번 복사 시도
    copy_log_file(ORIGINAL_LOG_SOURCE_PATH, TEMP_LOG_DEST_PATH)

    while True:
        copy_log_file(ORIGINAL_LOG_SOURCE_PATH, TEMP_LOG_DEST_PATH)
        time.sleep(COPY_INTERVAL_SECONDS)

