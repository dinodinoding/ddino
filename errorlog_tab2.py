import os
import sys
import time
import json
import signal
import re
from datetime import datetime, timedelta

# PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# PID 파일 기록
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
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] settings.json loaded successfully: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] settings.json parsing error: {e}. Please check file content.")
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Unknown error loading settings.json: {e}")
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}

# 로그에서 'Heating Steadfast ON' 메시지 필터링
def extract_heating_timestamps_incrementally(log_path, last_read_pos_file):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] Starting incremental extraction from '{log_path}'...")
    # 알려주신 새로운 로그 형식에 맞춰 타임스탬프와 키워드 패턴
    # "2025/07/16 16:26:22.770; Heating Steadfast ON; ..."
    pattern = r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{3}); Heating Steadfast ON" 
    new_timestamps = []
    current_read_pos = 0

    if os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "r") as f:
                content = f.read().strip()
                if content:
                    current_read_pos = int(content)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER DEBUG] '{last_read_pos_file}' is empty. Initializing.")
                    current_read_pos = 0
        except (ValueError, FileNotFoundError):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] '{last_read_pos_file}' corrupt or not found. Initializing position to 0.")
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

            # 파일 크기가 줄어들면 (예: 로그 로테이션으로 파일이 새로 생성되거나 잘린 경우)
            if file_size < current_read_pos:
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{log_path}' seems to have been reset or truncated. Resetting position to 0 and reading from start.")
                 current_read_pos = 0

            f.seek(current_read_pos) # 마지막으로 읽은 위치로 이동

            new_lines = f.readlines() # 새로 추가된 라인들 읽기
            
            for line in new_lines:
                # 'Heating Steadfast ON' 문자열이 포함된 줄만 상세 파싱
                if "Heating Steadfast ON" in line:
                    match = re.search(pattern, line) 
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            # 고객님이 알려주신 정확한 새 형식 "%Y/%m/%d %H:%M:%S.%f"로 파싱 시도
                            ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S.%f")
                            new_timestamps.append(ts)
                        except ValueError:
                            # 혹시 밀리초가 없는 경우 대비 (백업 로직, 현재는 덜 중요)
                            try:
                                ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
                                new_timestamps.append(ts)
                            except ValueError:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'Heating Steadfast ON' detected, but unknown timestamp format: '{timestamp_str}' in '{line.strip()}'")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Exception parsing timestamp: {timestamp_str} - {e}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER WARNING] 'Heating Steadfast ON' detected, but timestamp pattern mismatch for new format: '{line.strip()}'")
            
            new_pos = f.tell() # 새로운 읽기 위치 기록

        # 새로운 읽기 위치 저장
        with open(last_read_pos_file, "w") as f_pos:
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
    
    # 워커가 직접 모니터링할 파일은 GUI에서 지정한 CSV 파일
    monitoring_log_file = settings.get("monitoring_log_file_path", "")
    
    # last_read_pos_file은 이제 'monitoring_log_file'의 읽기 위치를 추적
    last_read_pos_file_for_monitoring = get_path("last_read_pos_for_monitoring_log.txt") 

    extracted_heating_events_cache = []

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Settings: Monitor Interval={interval_minutes} minutes, Threshold={threshold} occurrences.")
    if not monitoring_log_file:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] 'monitoring_log_file_path' is empty in settings. Please specify a correct path via GUI.")
        print("[WORKER INFO] Worker is terminating due to configuration error.")
        sys.exit(1)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Worker will directly read from: '{monitoring_log_file}'")
    
    # 읽기 위치 파일 초기화 (없으면 생성)
    if not os.path.exists(last_read_pos_file_for_monitoring):
        try:
            with open(last_read_pos_file_for_monitoring, "w") as f:
                f.write("0")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INIT] '{last_read_pos_file_for_monitoring}' initialized.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to initialize '{last_read_pos_file_for_monitoring}': {e}")
    
    while True:
        print(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WORKER MONITORING CYCLE START ---")
        
        # [Step 1] 지정된 CSV 파일에서 'Heating Steadfast ON' 타임스탬프 추출
        new_heating_times, _ = extract_heating_timestamps_incrementally(monitoring_log_file, last_read_pos_file_for_monitoring)
        extracted_heating_events_cache.extend(new_heating_times)
        extracted_heating_events_cache.sort()

        # [Step 2] 캐시에서 오래된 이벤트 정리 (메모리 관리)
        clean_up_time = datetime.now() - timedelta(minutes=interval_minutes + 10) # 10분 버퍼
        extracted_heating_events_cache = [
            t for t in extracted_heating_events_cache if t >= clean_up_time
        ]
        
        # [Step 3] 알람 조건 확인 (Rolling Window)
        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        filtered_heating_events = [t for t in extracted_heating_events_cache if window_start <= t <= now]

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Current Time: {now.strftime('%H:%M:%S')}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Monitoring Window Start: {window_start.strftime('%H:%M:%S')}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Total heating events in cache: {len(extracted_heating_events_cache)}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Detected heating events (last {interval_minutes} minutes): {len(filtered_heating_events)}")
        
        # --- Alarm Condition Check ---
        # "Heating Steadfast ON" 발생 횟수를 기준으로 threshold 비교
        if len(filtered_heating_events) >= threshold:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ALERT!!!] Threshold ({threshold} occurrences) exceeded! Detected {len(filtered_heating_events)} 'Heating Steadfast ON' occurrences.")
            show_alert()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Below threshold ({threshold} occurrences). Detected {len(filtered_heating_events)} 'Heating Steadfast ON' occurrences. No alert.")

        print(f"--- [{datetime.now().strftime('%H:%M:%S')}] WORKER MONITORING CYCLE END. Waiting for {60} seconds ---")
        time.sleep(60) # 1분 대기

# 알람 함수 (Windows MessageBox)
def show_alert():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ALERT!!!] Attempting to show popup alert: Excessive heating detected!")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "⚠ Excessive Heating Detected!", "Heating Alert", 0x40 | 0x1) # MB_ICONWARNING | MB_OK
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Failed to show alert: {e}. (May not be a Windows environment or a permission issue.)")

# 시그널 핸들러 (정상 종료를 위함)
def signal_handler(sig, frame):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Termination requested. Attempting to delete PID file.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{pid_path}' deleted.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] '{pid_path}' already does not exist.")
        
        # 임시 읽기 위치 파일 삭제
        temp_pos_file = get_path("last_read_pos_for_monitoring_log.txt")
        if os.path.exists(temp_pos_file):
            os.remove(temp_pos_file)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER INFO] Temporary file '{temp_pos_file}' deleted.")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER ERROR] Error during termination cleanup: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid() # 시작 시 PID 기록
    monitor_loop()
