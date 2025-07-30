import os
import sys
import time
import json
import signal
import re
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta

# --- Force UTF-8 encoding for all output streams (Windows 7 specific) ---
# This code must be at the very top of the file, right after imports.
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = open(sys.__stdout__.fileno(), mode='w', encoding='utf-8', buffering=1)
except Exception as e:
    sys.__stderr__.write(f"Warning: Failed to re-open sys.stdout with UTF-8 encoding: {e}\n")
    sys.stdout = open(sys.__stdout__.fileno(), mode='w', encoding='utf-8', errors='ignore', buffering=1)

try:
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = open(sys.__stderr__.fileno(), mode='w', encoding='utf-8', buffering=1)
except Exception as e:
    sys.__stderr__.write(f"Warning: Failed to re-open sys.stderr with UTF-8 encoding: {e}\n")
    sys.stderr = open(sys.__stderr__.fileno(), mode='w', encoding='utf-8', errors='ignore', buffering=1)

# Set PYTHONIOENCODING environment variable (additional safeguard for PyInstaller)
os.environ['PYTHONIOENCODING'] = 'utf-8'
# --- End of forced encoding settings ---


# Path settings
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# --- Logging setup ---
logger = logging.getLogger()
logger.setLevel(logging.DEBUG) # Log all levels

log_file_path = get_path("worker.log")

# RotatingFileHandler: Manage log file (size limit, backup)
# Explicitly set 'encoding="utf-8"' for file logging
try:
    file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
except Exception as e:
    sys.__stderr__.write(f"Error creating file_handler (might be permissions): {e}\n")
    file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8", errors='ignore')

file_handler.setLevel(logging.DEBUG) # Log all levels to file
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Force immediate write to file (address buffering issues)
for handler in logger.handlers:
    if isinstance(handler, RotatingFileHandler):
        handler.addFilter(lambda record: handler.flush() or True)

# Console output setup (sys.stdout should already be UTF-8 reconfigured)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG) # Log all levels to console
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# --- End of logging setup ---


def write_pid():
    try:
        with open(get_path("worker.pid"), "w") as f:
            f.write(str(os.getpid()))
        logging.info(f"[PID] {os.getpid()} saved successfully")
    except Exception as e:
        logging.error(f"[PID] Failed to save: {e}")

def load_settings():
    try:
        with open(get_path("settings.json"), "r", encoding="utf-8") as f:
            settings = json.load(f)
        logging.info(f"[CONFIG] Settings loaded successfully: {json.dumps(settings, ensure_ascii=False)}")
        return settings
    except Exception as e:
        logging.error(f"[CONFIG] Failed to load settings: {e}")
        return {}

def show_alert():
    logging.warning("[ALERT] Alarm popup executing")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "Excessive FIB Heating detected.\nPlease call for maintenance. -2964-", # Changed alert message to English
            "Heating Alert",
            0x40 | 0x0
        )
    except Exception as e:
        logging.error(f"[ALERT] Popup failed: {e}")

def parse_csv_for_trigger(csv_path, last_processed_time):
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-300:]
            for line in reversed(lines):
                parts = line.strip().split(";")
                if len(parts) < 2:
                    continue
                timestamp_str = parts[0].strip()
                event = parts[1].strip()
                if "Heating Steadfast ON" in event:
                    try:
                        ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S.%f")
                    except ValueError:
                        ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")

                    if ts > last_processed_time:
                        logging.debug(f"[CSV_WATCH] Valid trigger found: {ts} (Reference time: {last_processed_time})")
                        return True, ts
    except (IOError, PermissionError) as e:
        logging.error(f"[CSV_WATCH] File access error (lock or permission issue): {e}")
    except Exception as e:
        logging.error(f"[CSV_WATCH] Unknown error during CSV parsing: {e}")
    return False, None

def convert_log(settings):
    try:
        converter_name = settings.get("converter_exe_name", "g4_converter.exe")
        source_log_path = settings.get("log_file_path")
        target_txt_path = settings.get("converted_log_file_path")

        converter_exe_path = get_path(converter_name)

        if not os.path.exists(converter_exe_path):
            logging.error(f"[LOG_WATCH] Converter executable not found: {converter_exe_path}")
            return False
        if not source_log_path or not os.path.exists(source_log_path):
            logging.error(f"[LOG_WATCH] Source log file path is invalid or file not found: {source_log_path}")
            return False
        if not target_txt_path:
            logging.error(f"[LOG_WATCH] Converted log save path is not set")
            return False

        command = [converter_exe_path, source_log_path, target_txt_path]

        logging.debug(f"[LOG_WATCH] Executing converter: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)

        logging.debug(f"[LOG_WATCH] Converter execution successful, result file: {target_txt_path}")
        return True

    except subprocess.TimeoutExpired:
        logging.error("[LOG_WATCH] Converter execution timed out (15 seconds). Converter process might be stuck.")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"[LOG_WATCH] Converter execution failed: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"[LOG_WATCH] Exception during converter execution: {e}")
        return False

def parse_converted_log(txt_path, threshold, initial_time=None):
    count = 0
    reset = False
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-1000:]
            for line in reversed(lines):
                if "The FIB source is working properly." in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                            if initial_time and log_ts > initial_time:
                                logging.debug(f"[LOG_WATCH] Valid 'working properly' log found: {line.strip()}")
                                reset = True
                                break
                        except ValueError: continue

                if "The FIB source is heating" in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                            if initial_time and log_ts > initial_time:
                                logging.debug(f"[LOG_WATCH] Valid heating log detected: {line.strip()}")
                                count += 1
                        except ValueError: continue
                    if count >= threshold: break
    except (IOError, PermissionError) as e:
        logging.error(f"[LOG_WATCH] Converted log file access error (lock or permission issue): {e}")
    except Exception as e:
        logging.error(f"[LOG_WATCH] Unknown error during converted log parsing: {e}")
    return count, reset

def monitor_loop(settings):
    threshold = settings.get("threshold", 3)
    csv_path = settings.get("monitoring_log_file_path", "")
    log_mode_timeout_minutes = settings.get("interval_minutes", 60)

    converted_log_path = settings.get("converted_log_file_path")
    if not converted_log_path:
        logging.error("[CONFIG] Critical error: Converted log file path (converted_log_file_path) is missing in settings.json.")

    logging.info(f"[CONFIG] Monitoring CSV path: {csv_path}")
    logging.info(f"[CONFIG] Log path after conversion: {converted_log_path}")
    logging.info(f"[CONFIG] Log mode timeout: {log_mode_timeout_minutes} minutes")

    state = "CSV"
    last_alert_time = None
    log_mode_start_time = None
    initial_heating_time = None
    last_processed_time = datetime.now()
    logging.info(f"[START] Monitoring started at: {last_processed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        if state == "CSV":
            logging.info(f"[CSV_WATCH] Starting new trigger monitoring from '{os.path.basename(str(csv_path))}'...")
            if not csv_path or not os.path.exists(csv_path):
                logging.warning(f"[CSV_WATCH] Monitoring target file not found: {csv_path}")
            else:
                trigger, ts = parse_csv_for_trigger(csv_path, last_processed_time)
                if trigger:
                    logging.info(f"[CSV_WATCH] 'Heating Steadfast ON' trigger detected ({ts}) → Entering LOG mode")
                    state = "LOG"
                    log_mode_start_time = datetime.now()
                    initial_heating_time = ts
                    heating_count = 1

        elif state == "LOG":
            logging.info(f"[LOG_WATCH] Starting analysis of converted log (Trigger time: {initial_heating_time})...")
            now = datetime.now()
            timeout_delta = timedelta(minutes=log_mode_timeout_minutes)
            if log_mode_start_time and now - log_mode_start_time > timeout_delta:
                logging.warning(f"[LOG_WATCH] Monitoring exceeded {log_mode_timeout_minutes} minutes, timeout.")
                logging.info("[ALERT] Timeout condition met → Executing alarm")
                show_alert()
                last_alert_time = now
                state = "CSV"
                last_processed_time = now

            elif not convert_log(settings):
                logging.warning("[LOG_WATCH] Conversion failed - Retrying next cycle")

            elif converted_log_path and os.path.exists(converted_log_path):
                needed_count = threshold - heating_count
                count, reset = parse_converted_log(converted_log_path, needed_count, initial_heating_time)
                total_count = heating_count + count
                logging.debug(f"[LOG_WATCH] Analysis result: Additional detections ({count}), reset ({reset}), total ({total_count})")

                if reset:
                    logging.info("[LOG_WATCH] 'working properly' reset condition found → Returning to CSV mode")
                    state = "CSV"
                    last_processed_time = now

                elif total_count >= threshold:
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        logging.info(f"[ALERT] Threshold condition met (Total: {total_count} >= {threshold}) → Executing alarm")
                        show_alert()
                        last_alert_time = now
                        state = "CSV"
                        last_processed_time = now
                    else:
                        logging.info("[ALERT] Condition met, but popup skipped due to 60-second re-alarm prevention")
            else:
                logging.warning(f"[LOG_WATCH] Converted log file not found: {converted_log_path}")

        logging.info(f"... Next monitoring cycle starts in 60 seconds ...")
        time.sleep(60)

def signal_handler(sig, frame):
    logging.info("[EXIT] Termination signal received, starting cleanup")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("[EXIT] PID file deleted successfully")
    except Exception as e:
        logging.error(f"[EXIT] Error during termination: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    settings = load_settings()
    if not settings:
        logging.critical("[EXIT] Failed to load settings file, program terminating.")
        sys.exit(1)

    write_pid()
    monitor_loop(settings)
