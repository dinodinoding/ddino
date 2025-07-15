import os
import sys
import time
import json
import signal
import re
from datetime import datetime, timedelta

# 콘솔 한글 깨짐 방지 설정
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

# PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# PID 파일 기록 → 나중에 종료 가능하도록
def write_pid():
    pid_path = get_path("worker.pid")
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] PID {os.getpid()} recorded in {pid_path}.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to write PID file: {e}")

# 설정 파일 로드 함수
def load_settings():
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] settings.json not found at {config_path}.")
        print("[WORKER INFO] Using default settings. Please save settings via GUI.")
        return {"interval_minutes": 60, "threshold": 3, "worker_target_log_file_path": get_path("temp_log_for_worker.txt")}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] settings.json loaded successfully: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] settings.json parsing error: {e}. Please check file content.")
        return {"interval_minutes": 60, "threshold": 3, "worker_target_log_file_path": get_path("temp_log_for_worker.txt")}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Unknown error loading settings.json: {e}")
        return {"interval_minutes": 60, "threshold": 3, "worker_target_log_file_path": get_path("temp_log_for_worker.txt")}

# 로그에서 heating 메시지 필터링 (converted_log.txt에서 읽음)
def extract_heating_timestamps_incrementally(log_path, last_read_pos_converted_file):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Starting incremental extraction from '{log_path}'...")
    # 알려주신 로그 형식에 맞춰 타임스탬프 패턴 재확인
    # "2024-07-17 10:12:45.333" 이 부분을 정확히 매칭하도록 합니다.
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}).*?heating" 
    new_timestamps = []
    current_read_pos = 0

    if os.path.exists(last_read_pos_converted_file):
        try:
            with open(last_read_pos_converted_file, "r") as f:
                content = f.read().strip()
                if content:
                    current_read_pos = int(content)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] '{last_read_pos_converted_file}' is empty. Initializing.")
                    current_read_pos = 0
        except (ValueError, FileNotFoundError):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] '{last_read_pos_converted_file}' corrupt or not found. Initializing position to 0.")
            current_read_pos = 0

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Previous read position for '{log_path}': {current_read_pos} bytes.")

    if not os.path.exists(log_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] '{log_path}' does not exist.")
        return new_timestamps, current_read_pos

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] '{log_path}' file size: {file_size} bytes.")

            if file_size < current_read_pos: # File truncated or reset
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{log_path}' seems to have been reset or truncated. Resetting position to 0 and reading from start.")
                 current_read_pos = 0

            f.seek(current_read_pos) # Move to the last read position

            new_lines = f.readlines()
            
            for line in new_lines:
                if "heating" in line.lower():
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            # 고객님이 알려주신 정확한 형식으로 파싱 시도
                            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                            new_timestamps.append(ts)
                        except ValueError:
                            # 혹시 .333이 없는 경우 대비하여 다른 형식도 시도
                            try:
                                ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                new_timestamps.append(ts)
                            except ValueError:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but unknown timestamp format: '{timestamp_str}' in '{line.strip()}'")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Exception parsing timestamp: {timestamp_str} - {e}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but timestamp pattern mismatch: '{line.strip()}'")
            
            new_pos = f.tell()

        with open(last_read_pos_converted_file, "w") as f_pos:
            f_pos.write(str(new_pos))
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] {len(new_timestamps)} new heating timestamps extracted from '{log_path}'. New read position: {new_pos}.")
        return new_timestamps, new_pos

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error reading '{log_path}' file: {e}")
        return new_timestamps, current_read_pos


# 🚨🚨🚨 이 함수가 핵심적으로 수정되었습니다 (이제 실제 컨버팅 없이 복사만 진행) 🚨🚨🚨
# 원본 임시 로그 파일(log_copier가 복사한)을 읽어 converted_log.txt로 "컨버팅"하는 함수
def convert_and_synchronize_log(source_log_path, dest_converted_log_path, original_read_pos_tracker_path):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Starting log synchronization from '{source_log_path}' to '{dest_converted_log_path}'...")
    
    current_source_read_pos = 0
    if os.path.exists(original_read_pos_tracker_path):
        try:
            with open(original_read_pos_tracker_path, "r") as f:
                content = f.read().strip()
                if content:
                    current_source_read_pos = int(content)
        except (ValueError, FileNotFoundError):
            current_source_read_pos = 0 # 파일이 없거나 깨졌을 경우 초기화

    if not os.path.exists(source_log_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Source log '{source_log_path}' not found for synchronization.")
        with open(original_read_pos_tracker_path, "w") as f: f.write("0") # 파일이 사라졌다면 읽기 위치 초기화
        return False

    try:
        with open(source_log_path, "r", encoding="utf-8", errors="ignore") as source_f:
            source_f.seek(0, os.SEEK_END)
            source_file_size = source_f.tell()

            if source_file_size < current_source_read_pos:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Source log '{source_log_path}' truncated or reset. Reading from beginning.")
                current_source_read_pos = 0 # 읽기 위치 초기화
            
            source_f.seek(current_source_read_pos) # 이전 읽은 위치로 이동
            new_content = source_f.read() # 새로 추가된 내용만 읽기
            new_source_read_pos = source_f.tell() # 새 읽기 위치 기록
            
        if not new_content:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] No new content in source log '{source_log_path}' for synchronization.")
            # 파일 크기가 같으면 읽기 위치 업데이트 (매번 0으로 리셋되지 않도록)
            if source_file_size == current_source_read_pos:
                 with open(original_read_pos_tracker_path, "w") as f: f.write(str(new_source_read_pos))
            return False

        # 🚨 컨버팅 로직이 필요 없으므로, 새로운 내용을 그대로 converted_log.txt에 추가
        with open(dest_converted_log_path, "a", encoding="utf-8") as dest_f: # 'a' (append) 모드 유지
            dest_f.write(new_content) # 새로운 내용을 그대로 씁니다.
        
        # 원본 임시 파일의 읽기 위치 업데이트
        with open(original_read_pos_tracker_path, "w") as f:
            f.write(str(new_source_read_pos))

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Synchronized and appended new content to '{dest_converted_log_path}'.")
        return True

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error during log synchronization: {e}")
        return False


# 주기적으로 모니터링
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] Monitoring loop started.")
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    
    worker_target_log_file = settings.get("worker_target_log_file_path", get_path("temp_log_for_worker.txt"))
    dest_converted_log_file = get_path("converted_log.txt") 
    source_log_read_pos_tracker = get_path("last_read_pos_original_for_worker.txt") 
    converted_log_extract_pos_tracker = get_path("last_read_pos_converted.txt")

    extracted_heating_events_cache = []

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Settings: Monitor Interval={interval_minutes} minutes, Threshold={threshold} occurrences.")
    if not worker_target_log_file:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] 'worker_target_log_file_path' is empty in settings. Please specify a correct path via GUI.")
        print("[WORKER INFO] Worker is terminating due to configuration error.")
        sys.exit(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Worker will read from (Log Copier output): '{worker_target_log_file}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Final Log for analysis (output): '{dest_converted_log_file}'")
    
    # Initialize read position files if they don't exist
    for pos_file in [source_log_read_pos_tracker, converted_log_extract_pos_tracker]:
        if not os.path.exists(pos_file):
            try:
                with open(pos_file, "w") as f:
                    f.write("0")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] '{pos_file}' initialized.")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to initialize '{pos_file}': {e}")
    
    while True:
        print(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WORKER MONITORING CYCLE START ---")
        
        # [Step 1] log_copier가 만든 임시 파일의 내용을 converted_log.txt에 추가
        convert_and_synchronize_log(worker_target_log_file, dest_converted_log_file, source_log_read_pos_tracker)

        # [Step 2] 컨버팅된 converted_log.txt에서 heating 타임스탬프 추출
        new_heating_times, _ = extract_heating_timestamps_incrementally(dest_converted_log_file, converted_log_extract_pos_tracker)
        extracted_heating_events_cache.extend(new_heating_times)
        extracted_heating_events_cache.sort()

        # [Step 3] Clean up old events from cache (memory management)
        clean_up_time = datetime.now() - timedelta(minutes=interval_minutes + 10) # 10 min buffer
        extracted_heating_events_cache = [
            t for t in extracted_heating_events_cache if t >= clean_up_time
        ]
        
        # [Step 4] Check alarm condition (Rolling Window)
        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        filtered_heating_events = [t for t in extracted_heating_events_cache if window_start <= t <= now]

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Current Time: {now.strftime('%H:%M:%S')}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Monitoring Window Start: {window_start.strftime('%H:%M:%S')}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Total heating events in cache: {len(extracted_heating_events_cache)}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Detected heating events (last {interval_minutes} minutes): {len(filtered_heating_events)}")
        
        # --- Alarm Condition Check ---
        if len(filtered_heating_events) >= threshold:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ALERT!!!] Threshold ({threshold} occurrences) exceeded! Detected {len(filtered_heating_events)} occurrences.")
            show_alert()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Below threshold ({threshold} occurrences). Detected {len(filtered_heating_events)} occurrences. No alert.")

        print(f"--- [{datetime.now().strftime('%H:%M:%S')}] WORKER MONITORING CYCLE END. Waiting for {60} seconds ---")
        time.sleep(60) # Wait for 1 minute for the next cycle

# Alert function (Windows MessageBox)
def show_alert():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ALERT!!!] Attempting to show popup alert: Excessive heating detected!")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "⚠ Excessive Heating Detected!", "Heating Alert", 0x40 | 0x1) # MB_ICONWARNING | MB_OK
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to show alert: {e}. (May not be a Windows environment or a permission issue.)")

# Signal handler for graceful termination
def signal_handler(sig, frame):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Termination requested. Attempting to delete PID file.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{pid_path}' deleted.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{pid_path}' already does not exist.")
        
        temp_pos_files = [get_path("last_read_pos_converted.txt"), get_path("last_read_pos_original_for_worker.txt")]
        for tf in temp_pos_files:
            if os.path.exists(tf):
                os.remove(tf)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Temporary file '{tf}' deleted.")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error during termination cleanup: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid() # Record PID once at startup
    monitor_loop()
