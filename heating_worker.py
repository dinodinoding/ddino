# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##
# 이 프로그램이 작동하는 데 필요한 다양한 기능들을 가져옵니다.

import os  # 운영체제(Windows)와 상호작용하기 위한 도구 (예: 파일 경로 다루기)
import sys  # 파이썬 프로그램 자체를 제어하기 위한 도구 (예: .exe로 실행 중인지 확인)
import time  # 시간 관련 기능 도구 (예: 잠시 기다리기)
import json  # 설정 파일(settings.json)을 읽고 쓰기 위한 도구
import signal  # 프로그램에 종료 신호가 왔을 때 깔끔하게 정리할 수 있게 도와주는 도구
import re  # '정규 표현식'이라는 규칙을 사용해 복잡한 텍스트에서 원하는 부분을 찾아내는 도구
import subprocess  # 다른 외부 프로그램(g4_converter.exe 등)을 실행시키기 위한 도구
import logging  # 프로그램의 동작 상태를 파일(worker.log)에 기록(로깅)하기 위한 도구
from logging.handlers import RotatingFileHandler  # 로그 파일이 너무 커지면 자동으로 새 파일로 교체해주는 도구
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 도구

# ## 프로그램의 기준 경로 설정 ##
# 이 코드가 .py 파일로 실행되든, .exe 파일로 실행되든
# 항상 프로그램이 위치한 폴더를 기준으로 파일을 찾게 해줍니다.
if getattr(sys, 'frozen', False):
    # 프로그램이 .exe 파일로 변환되어 '얼려진' 상태일 때의 경로
    BASE_PATH = os.path.dirname(sys.executable)
else:
    # 일반적인 .py 스크립트 파일로 실행될 때의 경로
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# ## 편의 함수 만들기 ##
def get_path(filename):
    """프로그램 폴더 안의 파일 경로를 쉽게 만들어주는 함수"""
    return os.path.join(BASE_PATH, filename)

# --- 로그 기록(logging)을 위한 중요 수정 사항 ---
# worker.log 파일이 깨지는 현상을 막기 위해, 'encoding'(글자 인코딩) 관련 설정을 모두 제거합니다.
# 이렇게 하면 Windows의 기본 방식(CP949)으로 파일이 저장되어 메모장에서 열어도 글자가 깨지지 않습니다.

logger = logging.getLogger()  # 로그 기록을 위한 객체(logger)를 가져옴
logger.setLevel(logging.DEBUG)  # DEBUG 수준 이상의 모든 로그를 기록하도록 설정
log_file_path = get_path("worker.log") # 로그 파일의 전체 경로를 지정

# RotatingFileHandler에서 encoding='utf-8' 같은 파라미터를 완전히 제거.
# 이렇게 하면 시스템 기본 인코딩(보통 cp949)을 사용하게 됨.
file_handler = RotatingFileHandler(log_file_path, maxBytes=2_000_000, backupCount=3) # 2MB가 넘으면 새 파일 생성, 최대 3개까지 백업

file_handler.setLevel(logging.DEBUG) # 파일에는 DEBUG 수준 이상의 모든 것을 기록
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S") # 로그 형식 지정
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 콘솔(터미널) 출력용 핸들러에서도 인코딩 관련 설정을 제거
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO) # 콘솔에는 INFO 수준 이상의 정보만 표시 (너무 자잘한 내용은 제외)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# --- 수정 끝 ---


def write_pid():
    """프로세스 ID(PID)를 파일에 저장하는 함수"""
    # PID는 실행 중인 각 프로그램을 컴퓨터가 구분하기 위해 부여하는 고유 번호입니다.
    # 이 파일을 만들어두면 나중에 이 프로그램을 강제 종료해야 할 때 어떤 것인지 쉽게 찾을 수 있습니다.
    try:
        # 다른 파일 입출력에서도 인코딩 지정을 제거하여 시스템 기본 방식을 따르도록 함
        with open(get_path("worker.pid"), "w") as f:
            f.write(str(os.getpid())) # 현재 프로그램의 PID를 파일에 씀
        logging.info(f"[PID] PID {os.getpid()} 저장 성공.")
    except Exception as e:
        logging.error(f"[PID] PID 저장 실패: {e}")

def load_settings():
    """GUI에서 저장한 settings.json 파일의 내용을 읽어오는 함수"""
    try:
        # settings.json 파일은 GUI가 'utf-8' 방식으로 저장했으므로, 읽을 때도 맞춰줘야 함
        with open(get_path("settings.json"), "r", encoding="utf-8") as f:
            settings = json.load(f) # JSON 파일을 읽어서 파이썬 딕셔너리로 변환
        logging.info(f"[CONFIG] 설정 불러오기 성공: {json.dumps(settings, ensure_ascii=False)}")
        return settings
    except Exception as e:
        logging.error(f"[CONFIG] 설정 불러오기 실패: {e}")
        return {} # 실패 시 빈 딕셔너리 반환

def show_alert():
    """사용자에게 경고 메시지 창을 띄우는 함수"""
    logging.warning("[ALERT] 경고 팝업창을 표시합니다.")
    try:
        # 파이썬에서 Windows 운영체제의 기본 기능을 직접 호출하는 방법
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "Excessive FIB Heating detected.\nPlease call Maint. -2964-", # 메시지 내용
            "Heating Alert", # 창 제목
            0x40 | 0x0 # 창 스타일 (경고 아이콘)
        )
    except Exception as e:
        logging.error(f"[ALERT] 팝업창 표시 실패: {e}")

def parse_csv_for_trigger(csv_path, last_processed_time):
    """모니터링 대상 CSV 파일을 분석하여 'Heating Steadfast ON' 메시지를 찾는 함수"""
    try:
        # 파일을 utf-8로 열되, 혹시 다른 형식의 글자가 있어도 오류 없이 무시하고 읽음
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-300:] # 파일의 마지막 300줄만 읽어서 성능 향상
            for line in reversed(lines): # 최신 로그부터 확인하기 위해 거꾸로 반복
                parts = line.strip().split(";") # 한 줄을 ';' 기준으로 나눔
                if len(parts) < 2: continue # 나뉜 부분이 2개 미만이면 건너뜀

                timestamp_str = parts[0].strip() # 시간 부분
                event = parts[1].strip() # 이벤트 내용 부분

                if "Heating Steadfast ON" in event: # 원하는 메시지가 포함되어 있다면
                    try: # 시간 형식이 두 가지일 수 있으므로 둘 다 시도
                        ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S.%f")
                    except ValueError:
                        ts = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")

                    # 이전에 확인했던 시간보다 더 최신 로그일 때만 유효한 것으로 판단
                    if ts > last_processed_time:
                        logging.debug(f"[CSV_WATCH] 유효한 트리거 발견: {ts} (기준 시간: {last_processed_time})")
                        return True, ts # 찾았다고 알리고, 해당 시간도 함께 반환
    except (IOError, PermissionError) as e:
        logging.error(f"[CSV_WATCH] 파일을 읽는 중 오류 발생 (파일이 잠겨있거나 권한 문제): {e}")
    except Exception as e:
        logging.error(f"[CSV_WATCH] CSV 분석 중 알 수 없는 오류 발생: {e}")
    return False, None # 못 찾았으면 False 반환

def convert_log(settings):
    """g4_converter.exe를 실행하여 원본 .log 파일을 .txt 파일로 변환하는 함수"""
    try:
        # 설정에서 변환에 필요한 정보들을 가져옴
        converter_name = settings.get("converter_exe_name", "g4_converter.exe")
        source_log_path = settings.get("log_file_path")
        target_txt_path = settings.get("converted_log_file_path")
        
        converter_exe_path = get_path(converter_name) # 변환기 프로그램의 전체 경로

        # 필요한 파일이나 경로가 제대로 설정되어 있는지 확인
        if not os.path.exists(converter_exe_path):
            logging.error(f"[LOG_WATCH] 변환기 실행 파일을 찾을 수 없음: {converter_exe_path}")
            return False
        if not source_log_path or not os.path.exists(source_log_path):
            logging.error(f"[LOG_WATCH] 원본 로그 파일 경로가 잘못되었거나 파일이 없음: {source_log_path}")
            return False
        if not target_txt_path:
            logging.error(f"[LOG_WATCH] 변환된 로그를 저장할 경로가 설정되지 않음")
            return False

        # "converter.exe 원본파일.log 결과파일.txt" 형태의 명령어를 만듦
        command = [converter_exe_path, source_log_path, target_txt_path]

        logging.debug(f"[LOG_WATCH] 변환기 실행: {' '.join(command)}")
        # 위 명령어를 실행. 15초 이상 걸리면 문제가 있는 것으로 보고 중단 (timeout=15)
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
        
        logging.debug(f"[LOG_WATCH] 변환기 실행 성공, 결과 파일: {target_txt_path}")
        return True # 성공
        
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
    """변환된 .txt 파일을 분석하여 heating 횟수를 세고, 정상 메시지가 있는지 확인하는 함수"""
    count = 0 # heating 횟수
    reset = False # 정상 메시지 발견 여부
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-1000:] # 파일의 마지막 1000줄만 분석
            for line in reversed(lines): # 최신 로그부터 거꾸로 확인
                # 1. "정상 작동" 메시지 확인 (이게 나오면 카운트를 리셋)
                if "The FIB source is working properly." in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line) # 날짜/시간 부분 찾기
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                            # CSV에서 처음 이상이 감지된 시간(initial_time)보다 최신 로그일 경우에만
                            if initial_time and log_ts > initial_time:
                                logging.debug(f"[LOG_WATCH] 유효한 '정상 작동' 로그 발견: {line.strip()}")
                                reset = True # 리셋 조건 만족
                                break # 더 이상 분석할 필요 없으므로 중단
                        except ValueError: continue
                
                # 2. "heating" 메시지 확인 (이게 나오면 카운트 증가)
                if "The FIB source is heating" in line:
                    ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if ts_match:
                        try:
                            log_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
                            if initial_time and log_ts > initial_time:
                                logging.debug(f"[LOG_WATCH] 유효한 heating 로그 발견: {line.strip()}")
                                count += 1 # 카운트 증가
                        except ValueError: continue
                    if count >= threshold: break # 필요한 만큼 횟수를 다 찾았으면 중단
    except (IOError, PermissionError) as e:
        logging.error(f"[LOG_WATCH] 변환된 로그 파일 접근 오류 (파일 잠김 또는 권한 문제): {e}")
    except Exception as e:
        logging.error(f"[LOG_WATCH] 변환된 로그 분석 중 알 수 없는 오류 발생: {e}")
    return count, reset # 찾은 heating 횟수와 리셋 여부를 반환

def monitor_loop(settings):
    """메인 모니터링 로직을 무한 반복하는 함수"""
    # 설정값들을 변수에 저장
    threshold = settings.get("threshold", 3)
    csv_path = settings.get("monitoring_log_file_path", "")
    log_mode_timeout_minutes = settings.get("interval_minutes", 60)
    
    converted_log_path = settings.get("converted_log_file_path")
    if not converted_log_path: # 이 경로가 없으면 프로그램이 아예 동작할 수 없으므로 종료
        logging.critical("[CONFIG] 치명적 오류: 설정 파일에 converted_log_file_path 경로가 없습니다.")
        return

    logging.info(f"[CONFIG] CSV 감시 경로: {csv_path}")
    logging.info(f"[CONFIG] 변환된 로그 감시 경로: {converted_log_path}")
    logging.info(f"[CONFIG] LOG 모드 타임아웃: {log_mode_timeout_minutes} 분")

    # 프로그램의 현재 상태를 관리하는 변수 ('CSV' 모드 또는 'LOG' 모드)
    state = "CSV"
    last_alert_time = None # 마지막으로 경고창을 띄운 시간 (너무 자주 띄우지 않기 위함)
    log_mode_start_time = None # 'LOG' 모드로 진입한 시간 (타임아웃 계산용)
    initial_heating_time = None # CSV에서 처음 이상을 감지한 시간
    last_processed_time = datetime.now() # 이미 확인한 로그를 다시 확인하지 않기 위한 기준 시간
    logging.info(f"[START] 모니터링 시작: {last_processed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    while True: # 프로그램이 종료되지 않고 계속 반복
        # --- 1. 'CSV' 모드: 평상시 상태 ---
        if state == "CSV":
            logging.info(f"[CSV_WATCH] '{os.path.basename(str(csv_path))}' 파일에서 새 트리거를 감시 중...")
            if not csv_path or not os.path.exists(csv_path):
                logging.warning(f"[CSV_WATCH] 감시 대상 파일을 찾을 수 없음: {csv_path}")
            else:
                # CSV 파일에서 'Heating Steadfast ON'을 찾음
                trigger, ts = parse_csv_for_trigger(csv_path, last_processed_time)
                if trigger: # 만약 찾았다면
                    logging.info(f"[CSV_WATCH] 'Heating Steadfast ON' 트리거 감지 ({ts}) → LOG 모드로 전환합니다.")
                    state = "LOG" # 상태를 'LOG' 모드로 변경
                    log_mode_start_time = datetime.now() # 타임아웃 타이머 시작
                    initial_heating_time = ts # 이상 현상이 시작된 시간 기록
                    heating_count = 1 # CSV에서 한 번 찾았으므로 카운트는 1부터 시작
                    
        # --- 2. 'LOG' 모드: 이상 현상 감지 후 상세 분석 상태 ---
        elif state == "LOG":
            logging.info(f"[LOG_WATCH] 변환된 로그 분석 시작 (트리거 시간: {initial_heating_time})...")
            now = datetime.now()
            timeout_delta = timedelta(minutes=log_mode_timeout_minutes)
            
            # 타임아웃 확인: LOG 모드로 들어온 지 너무 오래 지났는지 확인
            if log_mode_start_time and now - log_mode_start_time > timeout_delta:
                logging.warning(f"[LOG_WATCH] 모니터링이 {log_mode_timeout_minutes}분을 초과하여 타임아웃되었습니다.")
                logging.info("[ALERT] 타임아웃 조건 만족 → 경고 실행.")
                show_alert() # 경고창 띄우기
                last_alert_time = now
                state = "CSV" # 다시 평상시 상태로 복귀
                last_processed_time = now # 기준 시간 갱신
            
            # 변환 실패 시: 다음 주기에 다시 시도
            elif not convert_log(settings):
                logging.warning("[LOG_WATCH] 변환 실패 - 다음 주기에 재시도합니다.")
            
            # 변환 성공 시: 변환된 파일 분석
            elif converted_log_path and os.path.exists(converted_log_path):
                needed_count = threshold - heating_count # 앞으로 더 찾아야 할 heating 횟수
                count, reset = parse_converted_log(converted_log_path, needed_count, initial_heating_time)
                total_count = heating_count + count # 총 heating 횟수

                if reset: # 만약 '정상 작동' 메시지를 찾았다면
                    logging.info("[LOG_WATCH] '정상 작동' 리셋 조건 발견 → CSV 모드로 돌아갑니다.")
                    state = "CSV" # 평상시 상태로 복귀
                    last_processed_time = now
                    
                elif total_count >= threshold: # 총 횟수가 설정된 임계값을 넘었다면
                    # 60초 이내에 경고를 띄운 적이 없을 때만 새로 띄움 (팝업 도배 방지)
                    if not last_alert_time or (now - last_alert_time).seconds > 60:
                        logging.info(f"[ALERT] 임계값 조건 만족 (총 {total_count} >= {threshold}) → 경고 실행.")
                        show_alert() # 경고창 띄우기
                        last_alert_time = now
                        state = "CSV" # 평상시 상태로 복귀
                        last_processed_time = now
                    else:
                        logging.info("[ALERT] 조건은 만족했으나, 60초 재알람 방지 기능으로 팝업은 생략합니다.")
            else:
                logging.warning(f"[LOG_WATCH] 변환된 로그 파일을 찾을 수 없음: {converted_log_path}")

        # 모든 작업이 끝나면 60초 동안 대기
        logging.info(f"... 60초 후 다음 모니터링을 시작합니다 ...")
        time.sleep(60)

def signal_handler(sig, frame):
    """프로그램 종료 신호(Ctrl+C 등)를 받았을 때 실행되는 함수"""
    logging.info("[EXIT] 종료 신호를 수신하여 정리 작업을 시작합니다.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path) # 만들어뒀던 pid 파일을 삭제
            logging.info("[EXIT] PID 파일 삭제 완료.")
    except Exception as e:
        logging.error(f"[EXIT] 종료 중 오류 발생: {e}")
    sys.exit(0) # 프로그램 완전히 종료

# ## 이 스크립트 파일을 직접 실행했을 때만 아래 코드를 실행 ##
if __name__ == "__main__":
    # 종료 신호를 받았을 때 위에서 만든 signal_handler 함수가 실행되도록 연결
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 1. 설정 파일 불러오기
    settings = load_settings()
    if not settings: # 설정 불러오기에 실패하면 프로그램을 시작할 수 없으므로 종료
        logging.critical("[EXIT] 설정 파일을 불러올 수 없어 프로그램을 종료합니다.")
        sys.exit(1)
        
    # 2. PID 파일 작성
    write_pid()
    
    # 3. 메인 모니터링 루프 시작
    monitor_loop(settings)
