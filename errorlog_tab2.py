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
        # original_log_file_path 대신 worker_target_log_file_path 사용
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
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?).*?heating"
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

            if file_size < current_read_pos: # File rotated or truncated (or simply overwritten by copier)
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{log_path}' seems to have been reset or truncated. Resetting position to 0 and reading from start.")
                 current_read_pos = 0

            f.seek(current_read_pos) # Move to the last read position

            # Read new lines, assuming log copier overwrites the file or appends
            new_lines = f.readlines() # Read all new lines from current_read_pos
            
            for line_num_in_new_content, line in enumerate(new_lines, 1):
                if "heating" in line.lower():
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            found_fmt = None
                            for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"]:
                                try:
                                    ts = datetime.strptime(timestamp_str, fmt)
                                    new_timestamps.append(ts)
                                    found_fmt = fmt
                                    break
                                except ValueError:
                                    pass
                            if not found_fmt:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but unknown timestamp format: '{timestamp_str}' in '{line.strip()}'")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Exception parsing timestamp: {timestamp_str} - {e}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but timestamp pattern mismatch: '{line.strip()}'")
            
            new_pos = f.tell() # New position after reading (at the end of the file)

        # Save the new read position for the next scan
        with open(last_read_pos_converted_file, "w") as f_pos:
            f_pos.write(str(new_pos))
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] {len(new_timestamps)} new heating timestamps extracted from '{log_path}'. New read position: {new_pos}.")
        return new_timestamps, new_pos

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error reading '{log_path}' file: {e}")
        return new_timestamps, current_read_pos


# 주기적으로 모니터링
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] Monitoring loop started.")
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    # 워커는 이제 log_copier가 복사한 임시 파일을 읽습니다.
    worker_target_log_file = settings.get("worker_target_log_file_path", get_path("temp_log_for_worker.txt"))
    converted_log_file = get_path("converted_log.txt") # 워커가 임시 파일의 내용을 추가할 곳
    last_read_pos_original_file = get_path("last_read_pos_original.txt") # 사용 안 함 (원래 원본 파일용)
    last_read_pos_converted_file = get_path("last_read_pos_converted.txt") # converted_log.txt용 read pos

    # This cache stores all detected heating timestamps
    extracted_heating_events_cache = []

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Settings: Monitor Interval={interval_minutes} minutes, Threshold={threshold} occurrences.")
    if not worker_target_log_file:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] 'worker_target_log_file_path' is empty in settings. Please specify a correct path via GUI.")
        print("[WORKER INFO] Worker is terminating due to configuration error.")
        sys.exit(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Worker will monitor: '{worker_target_log_file}' (created by log copier)")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Converted Log File (output): '{converted_log_file}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Converted Log Read Position File: '{last_read_pos_converted_file}'")

    # Initialize read position file for converted_log.txt if it doesn't exist
    if not os.path.exists(last_read_pos_converted_file):
        try:
            with open(last_read_pos_converted_file, "w") as f:
                f.write("0")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] '{last_read_pos_converted_file}' initialized.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to initialize '{last_read_pos_converted_file}': {e}")
    
    # 🚨 Crucial Change: Update converted_log.txt to always be identical to worker_target_log_file
    # This assumes worker_target_log_file is always overwritten by log_copier
    def synchronize_converted_log():
        if not os.path.exists(worker_target_log_file):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Worker target log '{worker_target_log_file}' does not exist yet. Cannot synchronize.")
            return

        try:
            # Read entire content of the worker's target log file (temp_log_for_worker.txt)
            with open(worker_target_log_file, "r", encoding="utf-8", errors="ignore") as source_f:
                content = source_f.read()
            
            # Overwrite converted_log.txt with this content
            with open(converted_log_file, "w", encoding="utf-8") as dest_f:
                dest_f.write(content)
            
            # Reset read position for converted_log.txt since it's completely rewritten
            with open(last_read_pos_converted_file, "w") as pos_f:
                pos_f.write("0")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Synchronized '{converted_log_file}' with '{worker_target_log_file}'. Resetting read position.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error synchronizing converted log: {e}")


    while True:
        print(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WORKER MONITORING CYCLE START ---")
        
        # [Step 1] Synchronize converted_log.txt with the latest from log_copier's output
        synchronize_converted_log()

        # [Step 2] Extract new heating timestamps from converted_log.txt (which is now synchronized)
        new_heating_times, _ = extract_heating_timestamps_incrementally(converted_log_file, last_read_pos_converted_file)
        extracted_heating_events_cache.extend(new_heating_times)
        # Sort is important for proper filtering and potentially for "first heating" logic
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
        # Title and message will be in English as requested for consistency
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
        
        # Clean up temporary position files
        temp_pos_files = [get_path("last_read_pos_converted.txt")] # last_read_pos_original.txt는 더이상 사용 안함
        for tf in temp_pos_files:
            if os.path.exists(tf):
                os.remove(tf)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Temporary file '{tf}' deleted.")
        # converted_log.txt는 분석용으로 유지
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error during termination cleanup: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid() # Record PID once at startup
    monitor_loop()
