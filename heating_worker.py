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
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_file_path = get_path("worker.log")
file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
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
        logging.info(f"[CONFIG] 설정 로드 완료: {settings}")
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
    except (IOError, PermissionError) as e:
        logging.error(f"[CSV_WATCH] 파일 접근 중 오류 발생 (잠금 또는 권한 문제): {e}")
    except Exception as e:
        logging.error(f"[CSV_WATCH] CSV 파싱 중 알 수 없는 오류 발생: {e}")
    return False, None

# 참고: 이 함수는 나중에 현장 적용 시 'g4_converter.exe'를 사용하도록 수정될 예정입니다.
def convert_log():
    try:
        exe_path = get_path("log_converter.exe") 
        if not os.path.exists(exe_path):
            logging.error(f"[LOG_WATCH] 변환기 log_converter.exe 없음: {exe_path}")
            return False
        
        # 변환기 타임아웃(15초) 설정 추가
        subprocess.run([exe_path], check=True, capture_output=True, text=True, timeout=15)
        logging.debug("[LOG_WATCH] 변환기 실행 성공")
        return True
    except subprocess.TimeoutExpired:
        logging.error("[LOG_WATCH] 변환기 실행 시간 초과(15초). 변환기 프로세스가 멈췄을 수 있습니다.")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"[LOG_WATCH] 변환기 실행 실패: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"[LOG_WATCH] 변환기 실행 중 예외 발생: {e}")
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
                                logging.debug(f"[LOG_WATCH] 유효한 'working properly' 로그 발견: {line.strip()}")
                                reset = True
                                break
                            else:
                                logging.debug(f"[LOG_WATCH] 기준 시간 이전의 'working properly' 로그 무시: {log_ts}")
                        except ValueError:
                            continue
                
                if "The FIB source is heating" in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                            if initial_time and log_ts > initial_time:
                                logging.debug(f"[LOG_WATCH] 유효 heating 로그 감지: {line.strip()}")
                                count += 1
                            else:
                                logging.debug(f"[LOG_WATCH] 기준 시간 이전 로그이므로 무시: {log_ts}")
                        except ValueError:
                            continue
                    if count >= threshold:
                        break
    except (IOError, PermissionError) as e:
        logging.error(f"[LOG_WATCH] 변환된 로그 파일 접근 오류 (잠금 또는 권한 문제): {e}")
    except Exception as e:
        logging.error(f"[LOG_WATCH] 변환된 로그 파싱 중 알 수 없는 오류 발생: {e}")
    return count, reset

def monitor_loop(settings):
    threshold = settings.get("threshold", 3)
    csv_path = settings.get("monitoring_log_file_path", "")
    log_mode_timeout_minutes = settings.get("interval_minutes", 60)
    
    # 테스트를 위해 기존의 단순한 converted_log_path 방식을 유지합니다.
    converted_log_path = get_path(os.path.join("log", "converted_log.txt"))
    logging.info(f"[CONFIG] 변환될 로그 파일 경로 (테스트용): {converted_log_path}")
    logging.info(f"[CONFIG] LOG 모드 타임아웃: {log_mode_timeout_minutes}분")

    state = "CSV"
    last_alert_time = None
    log_mode_start_time = None
    initial_heating_time = None
    last_processed_time = datetime.now()
    logging.info(f"[START] 모니터링 시작 시간: {last_processed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        if state == "CSV":
            logging.info(f"[CSV_WATCH] '{os.path.basename(csv_path)}' 파일에서 새 트리거 감시 시작...")
            if not os.path.exists(csv_path):
                logging.warning(f"[CSV_WATCH] 감시 대상 파일 없음: {csv_path}")
            else:
                trigger, ts = parse_csv_for_trigger(csv_path, last_processed_time)
                if trigger:
                    logging.info(f"[CSV_WATCH] 'Heating Steadfast ON' 트리거 발견({ts}) → LOG 모드 진입")
                    state = "LOG"
                    log_mode_start_time = datetime.now()
                    initial_heating_time = ts
                    heating_count = 1
                    
        elif state == "LOG":
            logging.info(f"[LOG_WATCH] 변환된 로그 분석 시작 (트리거 시간: {initial_heating_time})...")
            now = datetime.now()
            timeout_delta = timedelta(minutes=log_mode_timeout_minutes)
            if log_mode_start_time and now - log_mode_start_time > timeout_delta:
                logging.warning(f"[LOG_WATCH] 감시 {log_mode_timeout_minutes}분 초과, 타임아웃.")
                logging.info("[ALERT] 타임아웃 조건 충족 → 알람 실행")
                show_alert()
                last_alert_time = now
                state = "CSV"
                last_processed_time = now
                
            elif not convert_log():
                logging.warning("[LOG_WATCH] 변환 실패 - 다음 주기에 재시도")
            elif os.path.exists(converted_log_path):
                needed_count = threshold - heating_count
                count, reset = parse_converted_log(converted_log_path, needed_count, initial_heating_time)
                total_count = heating_count + count
                logging.debug(f"[LOG_WATCH] 분석 결과: 추가 감지({count}), 리셋({reset}), 합계({total_count})")

                if reset:
                    logging.info("[LOG_WATCH] 'working properly' 리셋 조건 발견 → CSV 복귀")
                    state = "CSV"
                    last_processed_time = now
                    
                elif total_count >= threshold:
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        logging.info(f"[ALERT] 임계값 조건 충족 (Total: {total_count} >= {threshold}) → 알람 실행")
                        show_alert()
                        last_alert_time = now
                        state = "CSV"
                        last_processed_time = now
                    else:
                        logging.info("[ALERT] 조건은 충족되었으나 60초 내 재알람 방지 기능으로 인해 팝업 생략")
        
        logging.info("... 60초 후 다음 감시를 시작합니다 ...")
        time.sleep(60)

def signal_handler(sig, frame):
    logging.info("[EXIT] 종료 시그널 수신됨, 정리 시작")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            logging.info("[EXIT] PID 파일 삭제 완료")
    except Exception as e:
        logging.error(f"[EXIT] 종료 처리 중 오류 발생: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    settings = load_settings()
    if settings.get("test_mode", False):
        console_handler.setLevel(logging.DEBUG)
        logging.debug("[MODE] 테스트 모드 활성화됨 (콘솔에 DEBUG 로그 출력)")
    write_pid()
    monitor_loop(settings)
