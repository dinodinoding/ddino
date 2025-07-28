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

# 경로 설정
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

# 콘솔 출력도 디버깅용으로 추가
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

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
        if settings.get("test_mode", False):
            logger.setLevel(logging.DEBUG)
            logging.debug("[MODE] 테스트 모드 활성화됨")
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

def parse_csv_for_trigger(csv_path):
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
                    logging.debug(f"[CSV] 트리거 감지됨: {ts}")
                    return True, ts
    except Exception as e:
        logging.error(f"[CSV] 파싱 실패: {e}")
    return False, None

def convert_log():
    try:
        exe_path = get_path("log_converter.exe")
        if not os.path.exists(exe_path):
            logging.error("[LOG] 변환기 log_converter.exe 없음")
            return False
        subprocess.run([exe_path], check=True)
        logging.debug("[LOG] 변환기 실행 성공")
        return True
    except Exception as e:
        logging.error(f"[LOG] 변환기 실행 실패: {e}")
        return False

def parse_converted_log(txt_path, threshold, initial_time=None):
    count = 0
    reset = False
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-1000:]
            for line in reversed(lines):
                if "FIB source is working properly." in line:
                    logging.debug(f"[LOG] working properly 로그 발견됨: {line.strip()}")
                    reset = True
                    break
                if "FIB source is heating" in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        ts_str = ts_match.group(1)
                        try:
                            log_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue
                        logging.debug(f"[LOG] heating 로그 시간: {log_ts}")
                        if initial_time and abs((log_ts - initial_time).total_seconds()) <= 5:
                            logging.debug(f"[LOG] 중복 무시됨: {log_ts} (기준 {initial_time})")
                            continue
                    count += 1
                    logging.debug(f"[LOG] heating 카운트 증가: {count}")
                    if count >= threshold:
                        break
    except Exception as e:
        logging.error(f"[LOG] 로그 파싱 실패: {e}")
    return count, reset

def monitor_loop():
    settings = load_settings()
    interval = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    csv_path = settings.get("monitoring_log_file_path", "")
    converted_log_path = get_path(os.path.join("log", "converted_log.txt"))

    state = "CSV"
    last_alert_time = None
    log_mode_start_time = None
    initial_heating_time = None

    logging.info("[START] 감시 시작됨")

    while True:
        logging.debug(f"[LOOP] 현재 상태: {state}")

        if state == "CSV":
            if not os.path.exists(csv_path):
                logging.warning("[CSV] 파일 없음 또는 경로 오류")
            else:
                trigger, ts = parse_csv_for_trigger(csv_path)
                if trigger:
                    logging.info("[CSV] Heating Steadfast ON 감지 → LOG 진입")
                    state = "LOG"
                    log_mode_start_time = datetime.now()
                    initial_heating_time = ts
                    heating_count = 1  # CSV에서 1회 감지
                    logging.debug(f"[LOG] 초기 heating 카운트: {heating_count}")
                    continue

        elif state == "LOG":
            now = datetime.now()
            if log_mode_start_time and now - log_mode_start_time > timedelta(hours=1):
                logging.warning("[LOG] 감시 1시간 초과 → CSV 복귀")
                state = "CSV"
                continue

            if not convert_log():
                logging.warning("[LOG] 변환 실패 - 재시도 대기")
            elif os.path.exists(converted_log_path):
                count, reset = parse_converted_log(converted_log_path, threshold, initial_heating_time)
                total_count = heating_count + count
                logging.debug(f"[LOG] 감지 합산: CSV(1) + LOG({count}) = {total_count}, reset: {reset}")

                if reset:
                    logging.info("[LOG] working properly 로그 감지됨 → CSV 복귀")
                    state = "CSV"
                    continue

                if total_count >= threshold:
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        show_alert()
                        last_alert_time = now
                        logging.info("[ALERT] 조건 충족 → 알람 실행됨 → CSV 복귀")
                        state = "CSV"
                        continue

        time.sleep(60)

def signal_handler(sig, frame):
    logging.info("[EXIT] 종료 시그널 수신됨")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("[EXIT] PID 파일 삭제 완료")
    except Exception as e:
        logging.error(f"[EXIT] 종료 처리 오류: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid()
    monitor_loop()