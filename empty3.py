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
import ctypes

# Path Configuration
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# --- Critical Modification for Logging ---
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_file_path = get_path("worker.log")

# Completely remove the encoding parameter from RotatingFileHandler
# Note: Using default system encoding, which is often 'cp949' on Windows
file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3)

file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# --- End of Modification ---


def write_pid():
    try:
        with open(get_path("worker.pid"), "w") as f:
            f.write(str(os.getpid()))
        logging.info(f"[PID] PID {os.getpid()} saved successfully.")
    except Exception as e:
        logging.error(f"[PID] Failed to save PID: {e}")

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
    logging.warning("[ALERT] Displaying alarm pop-up.")
    
    # --- Start of MODIFIED code: 1. 로깅을 먼저 수행합니다. ---
    alert_log_path = r"C:\monitering\heating_alert.log"
    try:
        # 디렉터리가 없으면 생성합니다.
        os.makedirs(os.path.dirname(alert_log_path), exist_ok=True)
        with open(alert_log_path, "a") as f:
            f.write("1\n")
        logging.info(f"[ALERT_LOG] Successfully logged '1' to {alert_log_path}")
    except Exception as log_e:
        logging.error(f"[ALERT_LOG] Failed to write to alert log: {log_e}")
    # --- End of MODIFIED code ---

    try:
        # 2. 팝업창을 띄웁니다. (로깅 완료 후 실행되며, 사용자가 닫을 때까지 블로킹됩니다.)
        # MB_SYSTEMMODAL 플래그 (0x00001000)를 사용하여 팝업을 최상단에 고정합니다.
        MB_SYSTEMMODAL = 0x00001000
        alert_style = 0x40 | 0x0 | MB_SYSTEMMODAL
        
        ctypes.windll.user32.MessageBoxW(
            0,
            "FIB Heating작업이 비정상적으로 반복되거나 정상완료되지 않고 있습니다.\n Please call Maint. P&T1-52964-, M14-46848-",
            "Heating Alert",
            alert_style
        )
        
    except Exception as e:
        logging.error(f"[ALERT] Failed to display pop-up: {e}")

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
        logging.error(f"[CSV_WATCH] Error accessing file (locked or permission issue): {e}")
    except Exception as e:
        logging.error(f"[CSV_WATCH] Unknown error occurred during CSV parsing: {e}")
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
            logging.error(f"[LOG_WATCH] Source log file path is invalid or file does not exist: {source_log_path}")
            return False
        if not target_txt_path:
            logging.error(f"[LOG_WATCH] Path to save converted log is not set")
            return False

        command = [converter_exe_path, source_log_path, target_txt_path]

        logging.debug(f"[LOG_WATCH] Executing converter: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
        
        logging.debug(f"[LOG_WATCH] Converter executed successfully, result file: {target_txt_path}")
        return True
        
    except subprocess.TimeoutExpired:
        logging.error("[LOG_WATCH] Converter execution timed out (15 seconds). The converter process might be stuck.")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"[LOG_WATCH] Converter execution failed: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"[LOG_WATCH] Exception occurred during converter execution: {e}")
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
        logging.error(f"[LOG_WATCH] Converted log file access error (locked or permission issue): {e}")
    except Exception as e:
        logging.error(f"[LOG_WATCH] Unknown error occurred during converted log parsing: {e}")
    return count, reset

def monitor_loop(settings):
    threshold = settings.get("threshold", 3)
    csv_path = settings.get("monitoring_log_file_path", "")
    log_mode_timeout_minutes = settings.get("interval_minutes", 60)
    
    converted_log_path = settings.get("converted_log_file_path")
    if not converted_log_path:
        logging.critical("[CONFIG] Fatal error: Converted log file path (converted_log_file_path) is missing in settings.json.")
        return # Exit if critical path is missing

    logging.info(f"[CONFIG] Monitoring CSV path: {csv_path}")
    logging.info(f"[CONFIG] Monitoring converted log path: {converted_log_path}")
    logging.info(f"[CONFIG] LOG mode timeout: {log_mode_timeout_minutes} minutes")

    state = "CSV"
    last_alert_time = None
    log_mode_start_time = None
    initial_heating_time = None
    last_processed_time = datetime.now()
    logging.info(f"[START] Monitoring started at: {last_processed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        if state == "CSV":
            logging.info(f"[CSV_WATCH] Monitoring '{os.path.basename(str(csv_path))}' for new triggers...")
            if not csv_path or not os.path.exists(csv_path):
                logging.warning(f"[CSV_WATCH] Target file not found: {csv_path}")
            else:
                trigger, ts = parse_csv_for_trigger(csv_path, last_processed_time)
                if trigger:
                    logging.info(f"[CSV_WATCH] 'Heating Steadfast ON' trigger detected ({ts}) → Entering LOG mode.")
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
                logging.info("[ALERT] Timeout condition met → Executing alarm.")
                show_alert()
                last_alert_time = now
                state = "CSV"
                last_processed_time = now
            
            elif not convert_log(settings):
                logging.warning("[LOG_WATCH] Conversion failed - Retrying in next cycle.")
            
            elif converted_log_path and os.path.exists(converted_log_path):
                needed_count = threshold - heating_count
                count, reset = parse_converted_log(converted_log_path, needed_count, initial_heating_time)
                total_count = heating_count + count
                logging.debug(f"[LOG_WATCH] Analysis result: additional detected ({count}), reset ({reset}), total ({total_count})")

                if reset:
                    logging.info("[LOG_WATCH] 'working properly' reset condition found → Returning to CSV mode.")
                    state = "CSV"
                    last_processed_time = now
                    
                elif total_count >= threshold:
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        logging.info(f"[ALERT] Threshold condition met (Total: {total_count} >= {threshold}) → Executing alarm.")
                        show_alert()
                        last_alert_time = now
                        state = "CSV"
                        last_processed_time = now
                    else:
                        logging.info("[ALERT] Condition met, but pop-up skipped due to 60-second re-alarm prevention.")
            else:
                logging.warning(f"[LOG_WATCH] Converted log file not found: {converted_log_path}")

        logging.info(f"... Next monitoring will start in 60 seconds ...")
        time.sleep(60)

def signal_handler(sig, frame):
    logging.info("[EXIT] Termination signal received, starting cleanup.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("[EXIT] PID file deleted successfully.")
    except Exception as e:
        logging.error(f"[EXIT] Error during termination: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    settings = load_settings()
    if not settings:
        logging.critical("[EXIT] Program terminated as settings file could not be loaded.")
        sys.exit(1)
        
    write_pid()
    monitor_loop(settings)
