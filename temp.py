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
import io

# 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# --- 콘솔 Unicode 출력 오류 방지용 설정 ---
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
except Exception:
    pass

# 로그 설정
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_file_path = get_path("worker.log")

file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 로그 flush 강제
for handler in logger.handlers:
    if isinstance(handler, RotatingFileHandler):
        handler.addFilter(lambda record: handler.flush() or True)

def write_pid():
    try:
        with open(get_path("worker.pid"), "w") as f:
            f.write(str(os.getpid()))
        logging.info(f"[PID] {os.getpid()} 저장 완료")
    except Exception as e:
        logging.error(f"[PID] 저장 실패: {e}")

def load_settings():
    try:
        with open(get_path("settings.json"), "r", encoding="utf-8") as f:
            settings = json.load(f)
        logging.info(f"[CONFIG] 설정 로드 완료: {json.dumps(settings, ensure_ascii=False)}")
        return settings
    except Exception as e:
        logging.error(f"[CONFIG] 설정 로드 실패: {e}")
        return {}

def show_alert():
    logging.warning("[ALERT] 알람 팝업 실행 중")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "과도한 FIB Heating이 감지 되었습니다.\nMaint Call 해주세요. -2964-",
            "Heating Alert",
            0x40 | 0x0
        )
    except Exception as e:
        logging.error(f"[ALERT] 팝업 실패: {e}")

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
                        logging.debug(f"[CSV_WATCH] 유효 트리거 발견: {ts} (기준 시간: {last_processed_time})")
                        return True, ts
    except Exception as e:
        logging.error(f"[CSV_WATCH] CSV 파싱 오류: {e}")
    return False, None

def convert_log(settings):
    try:
        converter_path = get_path(settings.get("converter_exe_name", "g4_converter.exe"))
        source_log = settings.get("log_file_path")
        target_txt = settings.get("converted_log_file_path")

        if not os.path.exists(converter_path):
            logging.error(f"[LOG_WATCH] 변환기 실행 파일 없음: {converter_path}")
            return False
        if not source_log or not os.path.exists(source_log):
            logging.error(f"[LOG_WATCH] 원본 로그 파일 없음: {source_log}")
            return False
        if not target_txt:
            logging.error(f"[LOG_WATCH] 변환 로그 저장 경로가 없음")
            return False

        cmd = [converter_path, source_log, target_txt]
        logging.debug(f"[LOG_WATCH] 변환기 실행: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
        logging.debug(f"[LOG_WATCH] 변환 성공")
        return True
    except subprocess.TimeoutExpired:
        logging.error("[LOG_WATCH] 변환기 실행 시간 초과")
    except subprocess.CalledProcessError as e:
        logging.error(f"[LOG_WATCH] 변환기 실패: {e.stderr}")
    except Exception as e:
        logging.error(f"[LOG_WATCH] 변환 중 오류: {e}")
    return False

def parse_converted_log(txt_path, threshold, initial_time=None):
    count = 0
    reset = False
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-1000:]
            for line in reversed(lines):
                if "working properly" in line:
                    if re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line):
                        reset = True
                        break
                if "FIB source is heating" in line:
                    ts_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line)
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(0), "%Y-%m-%d %H:%M:%S")
                            if initial_time and log_ts > initial_time:
                                count += 1
                        except ValueError:
                            continue
                    if count >= threshold:
                        break
    except Exception as e:
        logging.error(f"[LOG_WATCH] 변환 로그 파싱 실패: {e}")
    return count, reset

def monitor_loop(settings):
    threshold = settings.get("threshold", 3)
    interval = settings.get("interval_minutes", 60)
    csv_path = settings.get("monitoring_log_file_path")
    converted_path = settings.get("converted_log_file_path")

    state = "CSV"
    last_alert_time = None
    log_mode_start_time = None
    initial_heating_time = None
    last_processed_time = datetime.now()

    logging.info(f"[START] 모니터링 시작: {last_processed_time}")

    while True:
        if state == "CSV":
            if not csv_path or not os.path.exists(csv_path):
                logging.warning(f"[CSV_WATCH] CSV 로그 파일 없음: {csv_path}")
            else:
                trigger, ts = parse_csv_for_trigger(csv_path, last_processed_time)
                if trigger:
                    logging.info(f"[CSV_WATCH] 트리거 감지됨 → LOG 모드 진입")
                    state = "LOG"
                    log_mode_start_time = datetime.now()
                    initial_heating_time = ts
                    heating_count = 1

        elif state == "LOG":
            now = datetime.now()
            if log_mode_start_time and now - log_mode_start_time > timedelta(minutes=interval):
                logging.warning("[LOG_WATCH] 타임아웃 도달 → 알람")
                show_alert()
                last_alert_time = now
                state = "CSV"
                last_processed_time = now
            elif not convert_log(settings):
                logging.warning("[LOG_WATCH] 변환 실패")
            elif converted_path and os.path.exists(converted_path):
                count, reset = parse_converted_log(converted_path, threshold - 1, initial_heating_time)
                if reset:
                    logging.info("[LOG_WATCH] 정상 복귀 로그 감지됨 → CSV 복귀")
                    state = "CSV"
                    last_processed_time = now
                elif heating_count + count >= threshold:
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        logging.info("[ALERT] 조건 충족 → 알람 발생")
                        show_alert()
                        last_alert_time = now
                        state = "CSV"
                        last_processed_time = now

        time.sleep(60)

def signal_handler(sig, frame):
    logging.info("[EXIT] 종료 시그널 수신됨")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("[EXIT] PID 파일 삭제 완료")
    except Exception as e:
        logging.error(f"[EXIT] 종료 처리 중 오류: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    settings = load_settings()
    if not settings:
        logging.critical("[EXIT] 설정 파일이 없습니다. 종료합니다.")
        sys.exit(1)
    write_pid()
    monitor_loop(settings)