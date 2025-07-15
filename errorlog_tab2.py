import os
import sys
import time
import json
import signal
import re
from datetime import datetime, timedelta

# 콘솔 한글 깨짐 방지 설정 추가
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

# 🔧 [1] PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# 🔧 [2] PID 파일 기록 → 나중에 종료 가능하도록
def write_pid():
    pid_path = get_path("worker.pid")
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] PID {os.getpid()} recorded in {pid_path}.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to write PID file: {e}")

# 🔧 [3] 설정 파일 로드 함수
def load_settings():
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] settings.json not found at {config_path}.")
        print("[WORKER INFO] Using default settings. Please save settings via GUI.")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] settings.json loaded successfully: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] settings.json parsing error: {e}. Please check file content.")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Unknown error loading settings.json: {e}")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}


# 🔧 [4] 로그에서 heating 메시지 필터링 (converted_log.txt 에서 읽음)
# 이 함수는 이제 converted_log.txt의 전체를 읽는 대신, 새로운 내용만 처리합니다.
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

            if file_size < current_read_pos: # File rotated or truncated
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{log_path}' seems to have been rotated or truncated. Resetting position to 0 and reading from start.")
                 current_read_pos = 0

            f.seek(current_read_pos) # Move to the last read position

            for line_num_in_new_content, line in enumerate(f, 1):
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
                            if found_fmt:
                                # print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] 'heating' detected, timestamp parsed: {timestamp_str} (format: {found_fmt})")
                                pass
                            else:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but unknown timestamp format: '{timestamp_str}' in '{line.strip()}'")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Exception parsing timestamp: {timestamp_str} - {e}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'heating' detected, but timestamp pattern mismatch: '{line.strip()}'")
            
            new_pos = f.tell() # New position after reading

        # Save the new read position for the next scan
        with open(last_read_pos_converted_file, "w") as f_pos:
            f_pos.write(str(new_pos))
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] {len(new_timestamps)} new heating timestamps extracted from '{log_path}'. New read position: {new_pos}.")
        return new_timestamps, new_pos

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error reading '{log_path}' file: {e}")
        return new_timestamps, current_read_pos


# 🔧 [5] 원본 로그 파일에서 새로운 내용을 읽어 converted_log.txt에 추가
def update_converted_log(original_log_path, converted_log_path, last_read_pos_original_file):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Checking for new content in '{original_log_path}' and updating '{converted_log_path}'...")
    current_read_pos = 0
    if os.path.exists(last_read_pos_original_file):
        try:
            with open(last_read_pos_original_file, "r") as f:
                content = f.read().strip()
                if content:
                    current_read_pos = int(content)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] '{last_read_pos_original_file}' is empty. Initializing.")
                    current_read_pos = 0
        except (ValueError, FileNotFoundError):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] '{last_read_pos_original_file}' corrupt or not found. Initializing position to 0.")
            current_read_pos = 0

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Previous read position for original log file: {current_read_pos} bytes.")

    if not os.path.exists(original_log_path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Original log file '{original_log_path}' not found. Please check path in settings.json.")
        return current_read_pos

    try:
        with open(original_log_path, "r", encoding="utf-8", errors="ignore") as original_f:
            original_f.seek(0, os.SEEK_END) # Move to end of file to get total size
            file_size = original_f.tell()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Original log file size: {file_size} bytes.")

            if file_size < current_read_pos: # File rotated or truncated
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Original log file seems to have been rotated or truncated. Resetting position to 0 and reading from start.")
                 current_read_pos = 0

            original_f.seek(current_read_pos) # Seek to the last read position
            new_content = original_f.read() # Read new content
            new_pos = original_f.tell() # New position after reading

        if new_content:
            with open(converted_log_path, "a", encoding="utf-8") as converted_f: # 'a' (append) mode
                converted_f.write(new_content)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Added {len(new_content)} bytes of new log content to '{converted_log_path}'. New read position: {new_pos}.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] No new content in original log file.")
            
        # Save the new read position for the next scan
        with open(last_read_pos_original_file, "w") as f:
            f.write(str(new_pos))
        
        return new_pos

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error reading/writing log file: {e}")
        return current_read_pos # Maintain current position on error

# 🔧 [6] 주기적으로 모니터링
def monitor_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] Monitoring loop started.")
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    original_log_file = settings.get("original_log_file_path", "")
    converted_log_file = get_path("converted_log.txt")
    last_read_pos_original_file = get_path("last_read_pos_original.txt")
    last_read_pos_converted_file = get_path("last_read_pos_converted.txt")

    # This cache stores all detected heating timestamps
    extracted_heating_events_cache = []

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Settings: Monitor Interval={interval_minutes} minutes, Threshold={threshold} occurrences.")
    if not original_log_file:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] 'original_log_file_path' is empty in settings. Please specify a correct path via GUI.")
        print("[WORKER INFO] Worker is terminating due to configuration error.")
        sys.exit(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Original Log File: '{original_log_file}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Converted Log File (output): '{converted_log_file}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Original Log Read Position File: '{last_read_pos_original_file}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Converted Log Read Position File: '{last_read_pos_converted_file}'")


    # Initialize read position files if they don't exist
    for pos_file in [last_read_pos_original_file, last_read_pos_converted_file]:
        if not os.path.exists(pos_file):
            try:
                with open(pos_file, "w") as f:
                    f.write("0")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] '{pos_file}' initialized.")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to initialize '{pos_file}': {e}")

    while True:
        print(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WORKER MONITORING CYCLE START ---")
        
        # [Step 1] Update converted_log.txt with new content from original log file
        update_converted_log(original_log_file, converted_log_file, last_read_pos_original_file)

        if not os.path.exists(converted_log_file):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] '{converted_log_file}' does not exist yet. Waiting for next cycle.")
            time.sleep(60)
            continue

        # [Step 2] Extract new heating timestamps from converted_log.txt incrementally
        new_heating_times, _ = extract_heating_timestamps_incrementally(converted_log_file, last_read_pos_converted_file)
        extracted_heating_events_cache.extend(new_heating_times)
        # Sort is important for proper filtering and potentially for "first heating" logic
        extracted_heating_events_cache.sort()

        # [Step 3] Clean up old events from cache (memory management)
        # Remove events older than (current_time - interval_minutes - buffer_time)
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
        time.sleep(60) # Wait for 1 minute

# 🔧 [7] Alert function (Windows MessageBox)
def show_alert():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ALERT!!!] Attempting to show popup alert: Excessive heating detected!")
    try:
        import ctypes
        # Title and message will be in English as requested for consistency
        ctypes.windll.user32.MessageBoxW(0, "⚠ Excessive Heating Detected!", "Heating Alert", 0x40 | 0x1) # MB_ICONWARNING | MB_OK
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to show alert: {e}. (May not be a Windows environment or a permission issue.)")

# 🔧 [8] Signal handler for graceful termination
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
        temp_pos_files = [get_path("last_read_pos_original.txt"), get_path("last_read_pos_converted.txt")]
        for tf in temp_pos_files:
            if os.path.exists(tf):
                os.remove(tf)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Temporary file '{tf}' deleted.")
        # converted_log.txt is retained as it holds historical log data for analysis
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error during termination cleanup: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid() # Record PID once at startup
    monitor_loop()
