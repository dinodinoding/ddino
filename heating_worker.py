import os
import sys
import time
import json
import signal
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

# PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# 로그 설정
log_file_path = get_path("worker.log")
handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# PID 파일 기록
def write_pid():
    pid_path = get_path("worker.pid")
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        logging.info(f"PID {os.getpid()} recorded in {pid_path}.")
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")

# 설정 파일 로드 함수
def load_settings():
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        logging.error(f"settings.json not found at {config_path}.")
        logging.info("Using default settings. Please save settings via GUI.")
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        logging.info(f"settings.json loaded successfully: {settings}")
        return settings
    except json.JSONDecodeError as e:
        logging.error(f"settings.json parsing error: {e}. Please check file content.")
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}
    except Exception as e:
        logging.error(f"Unknown error loading settings.json: {e}")
        return {"interval_minutes": 60, "threshold": 3, "monitoring_log_file_path": ""}

# 로그에서 'Heating Steadfast ON' 메시지 필터링
def extract_heating_timestamps_incrementally(log_path, last_read_pos_file):
    pattern = r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?); Heating Steadfast ON"
    new_timestamps = []
    current_read_pos = 0

    if os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "r") as f:
                content = f.read().strip()
                current_read_pos = int(content) if content else 0
        except (ValueError, FileNotFoundError):
            logging.warning(f"'{last_read_pos_file}' corrupt or not found. Initializing position to 0.")
            current_read_pos = 0

    if not os.path.exists(log_path):
        return new_timestamps, current_read_pos

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size < current_read_pos:
                logging.info(f"'{log_path}' seems to have been reset or truncated. Resetting position to 0.")
                current_read_pos = 0

            f.seek(current_read_pos)
            new_lines = f.readlines()

            for line in new_lines:
                if "Heating Steadfast ON" in line:
                    match = re.search(pattern, line)
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S.%f")
                        except ValueError:
                            ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
                        new_timestamps.append(ts)

            new_pos = f.tell()

        with open(last_read_pos_file, "w") as f_pos:
            f_pos.write(str(new_pos))

        return new_timestamps, new_pos

    except Exception as e:
        logging.error(f"Error reading '{log_path}': {e}")
        return new_timestamps, current_read_pos

# 알람 팝업
def show_alert():
    logging.warning("Showing alert popup: Excessive heating detected")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            " 과도한 FIB Heating이 감지 되었습니다.\n Maint Call 해주세요. \n -2964-",
            "Heating Alert",
            0x40 | 0x0
        )
    except Exception as e:
        logging.error(f"Failed to show alert: {e}")

# 모니터링 루프
def monitor_loop():
    logging.info("Monitoring loop started.")
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    monitoring_log_file = settings.get("monitoring_log_file_path", "")
    last_read_pos_file = get_path("last_read_pos_for_monitoring_log.txt")
    extracted_cache = []

    last_alert_time = None  # 마지막 알람 발생 시각

    if not monitoring_log_file:
        logging.error("monitoring_log_file_path is empty.")
        sys.exit(1)

    if not os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "w") as f:
                f.write("0")
            logging.info(f"Initialized '{last_read_pos_file}'.")
        except Exception as e:
            logging.error(f"Failed to initialize '{last_read_pos_file}': {e}")

    while True:
        logging.info("\n--- MONITORING CYCLE ---")
        new_times, _ = extract_heating_timestamps_incrementally(monitoring_log_file, last_read_pos_file)
        extracted_cache.extend(new_times)
        extracted_cache.sort()

        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        recent = [t for t in extracted_cache if window_start <= t <= now]

        logging.info(f"Heating events in window ({window_start.strftime('%H:%M')} ~ {now.strftime('%H:%M')}): {len(recent)}")

        # 알람 발생 조건
        if len(recent) >= threshold:
            latest_heating_time = max(recent)

            if last_alert_time is None or latest_heating_time > last_alert_time:
                show_alert()
                last_alert_time = now
                logging.info(f"🚨 Alert triggered. New heating event(s) since last alert at {last_alert_time}")
            else:
                logging.info("❗ Enough events but no new heating since last alert → No alert")
        else:
            logging.info("ℹ️ Not enough heating events for alert")

        time.sleep(60)

# 시그널 핸들러
def signal_handler(sig, frame):
    logging.info("Termination requested. Cleaning up PID and temp files.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("worker.pid deleted.")
        temp_file = get_path("last_read_pos_for_monitoring_log.txt")
        if os.path.exists(temp_file):
            os.remove(temp_file)
            logging.info("Temporary read position file deleted.")
    except Exception as e:
        logging.error(f"Cleanup error: {e}")
    sys.exit(0)

# 메인 실행
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid()
    monitor_loop()