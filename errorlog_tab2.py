import os
import sys
import time
import json
import signal
import re
from datetime import datetime, timedelta

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
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

# 🔧 [3] 설정 파일 로드 함수
def load_settings():
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        print("settings.json 파일이 존재하지 않습니다. 기본값을 사용합니다.")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 🔧 [4] 로그에서 heating 메시지 필터링 (converted_log.txt 에서 읽음)
def extract_heating_timestamps(log_path):
    # 이 정규식은 "2024-01-01 12:34:56.789012 some text heating" 와 같은 패턴을 찾습니다.
    # 로그 파일의 실제 타임스탬프 형식에 맞춰 수정해야 할 수 있습니다.
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?).*?heating"
    timestamps = []
    if not os.path.exists(log_path):
        return timestamps

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "heating" in line.lower():
                match = re.search(pattern, line, re.IGNORECASE) # re.search로 변경, IGNORECASE 추가
                if match:
                    timestamp_str = match.group(1) # 그룹 1: 전체 타임스탬프 부분
                    try:
                        # 밀리초까지 고려한 다양한 형식 시도
                        for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"]:
                            try:
                                timestamps.append(datetime.strptime(timestamp_str, fmt))
                                break # 성공하면 다음 라인으로
                            except ValueError:
                                continue # 이 형식 실패하면 다음 형식 시도
                        else: # 모든 형식이 실패하면
                            print(f"경고: 알 수 없는 타임스탬프 형식 '{timestamp_str}'")
                    except Exception as e:
                        print(f"타임스탬프 파싱 오류: {timestamp_str} - {e}")
    return timestamps

# 🔧 [5] 원본 로그 파일에서 새로운 내용을 읽어 converted_log.txt에 추가
def update_converted_log(original_log_path, converted_log_path, last_read_pos_file):
    current_read_pos = 0
    if os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "r") as f:
                current_read_pos = int(f.read().strip())
        except (ValueError, FileNotFoundError):
            current_read_pos = 0 # 파일이 비어있거나 손상되면 처음부터 다시 읽기

    if not os.path.exists(original_log_path):
        print(f"경고: 원본 로그 파일 '{original_log_path}'을(를) 찾을 수 없습니다.")
        return current_read_pos # 현재 위치 그대로 반환

    try:
        with open(original_log_path, "r", encoding="utf-8", errors="ignore") as original_f:
            original_f.seek(current_read_pos) # 마지막으로 읽은 위치로 이동
            new_content = original_f.read() # 새로운 내용 읽기
            new_pos = original_f.tell() # 새로 읽은 후의 파일 위치

        if new_content:
            with open(converted_log_path, "a", encoding="utf-8") as converted_f: # 'a' (append) 모드
                converted_f.write(new_content)
            print(f"새로운 로그 내용 {len(new_content)} 바이트를 {converted_log_path}에 추가했습니다.")
        else:
            # 파일이 축소되었거나(로그 로테이션 등), 새로운 내용이 없을 경우 처리
            if new_pos < current_read_pos: # 파일이 이전보다 작아졌으면 (로테이션 가능성)
                 print(f"로그 파일 '{original_log_path}'이(가 로테이션되거나 축소된 것 같습니다. 처음부터 다시 읽습니다.")
                 new_pos = 0 # 위치 초기화
                 # converted_log.txt도 비울지 여부는 정책에 따라 결정 (여기서는 기존 내용을 유지)
            # 파일에 새 내용이 없어도 new_pos는 계속 업데이트 (다음 번에도 현재 위치부터 읽도록)
            
        # 다음 스캔을 위해 마지막으로 읽은 위치 저장
        with open(last_read_pos_file, "w") as f:
            f.write(str(new_pos))
        
        return new_pos

    except Exception as e:
        print(f"로그 파일 읽기/쓰기 오류: {e}")
        return current_read_pos # 오류 발생 시 위치 유지

# 🔧 [6] 주기적으로 모니터링
def monitor_loop():
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    original_log_file = settings.get("original_log_file_path", "") # 원본 로그 파일 경로
    converted_log_file = get_path("converted_log.txt") # 변환된 로그 파일 (이 스크립트가 업데이트)
    last_read_pos_file = get_path("last_read_pos.txt") # 마지막으로 읽은 위치 기록 파일

    if not original_log_file:
        print("오류: settings.json에 'original_log_file_path'가 설정되지 않았습니다.")
        print("GUI에서 원본 로그 파일 경로를 지정해주세요.")
        return

    print(f">> 감시 시작: '{original_log_file}' 파일을 모니터링하여 '{converted_log_file}'에 복사 후 처리")
    print(f">> 조건: {interval_minutes}분 안에 {threshold}회 이상 heating 발생 시 알림")

    # last_read_pos.txt 파일이 없으면 초기화
    if not os.path.exists(last_read_pos_file):
        with open(last_read_pos_file, "w") as f:
            f.write("0")
        print("last_read_pos.txt 파일이 초기화되었습니다.")

    # 알림 로직을 위한 변수 (고객님 요청에 맞게 수정하려면 이 부분을 변경해야 함)
    # 현재는 rolling window 방식
    
    while True:
        # [1단계] 원본 로그 파일에서 새로운 내용을 converted_log.txt로 업데이트
        update_converted_log(original_log_file, converted_log_file, last_read_pos_file)

        if not os.path.exists(converted_log_file):
            print("변환된 로그 파일 없음. 다음 주기까지 대기.")
            time.sleep(60) # 1분 대기
            continue

        # [2단계] converted_log.txt에서 heating 타임스탬프 추출 및 알람 로직 실행
        heating_times = extract_heating_timestamps(converted_log_file)
        heating_times.sort()

        # 최근 감시 범위 내에서 필터링 (롤링 윈도우)
        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        filtered_heating_events = [t for t in heating_times if window_start <= t <= now]

        print(f"[{now.strftime('%H:%M:%S')}] 감지된 heating 수 (최근 {interval_minutes}분): {len(filtered_heating_events)}")
        
        # --- 고객님 요청의 "첫 heating 기준" 알람 로직 구현 가이드라인 ---
        # 이 부분은 현재 'rolling window' 방식입니다.
        # "첫 heating 메시지가 뜨고 1시간 안에 2번 더 (총 3번) 뜨면"을 구현하려면,
        # heating_times 리스트를 순회하며 특정 상태 변수를 유지해야 합니다.
        # 예시:
        # first_heating_in_sequence = None
        # sequence_count = 0
        # for t in heating_times:
        #     if first_heating_in_sequence is None:
        #         first_heating_in_sequence = t
        #         sequence_count = 1
        #     elif t <= first_heating_in_sequence + timedelta(minutes=interval_minutes):
        #         sequence_count += 1
        #     else: # 1시간 범위를 벗어났으면 새 시퀀스 시작
        #         first_heating_in_sequence = t
        #         sequence_count = 1
        #
        #     if sequence_count >= threshold:
        #         print("⚠️ 경고: 설정된 횟수 초과 감지 (첫 heating 기준)!")
        #         show_alert()
        #         # 알림 후 시퀀스를 초기화할지, 계속 진행할지 결정해야 함
        #         first_heating_in_sequence = None # 알림 후 시퀀스 초기화 예시
        #         sequence_count = 0
        # --------------------------------------------------------------------

        if len(filtered_heating_events) >= threshold:
            print("⚠️ 경고: 설정된 횟수 초과 감지!")
            show_alert()

        time.sleep(60) # 1분 대기

# 🔧 [7] 알림 함수 (단순 메시지 출력 또는 팝업으로 교체 가능)
def show_alert():
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "⚠ Heating이 과도하게 반복되었습니다!", "Heating 경고", 0x40 | 0x1)
    except Exception as e:
        print(f"알림 실패: {e}. (Windows 환경이 아닐 수 있습니다)")

# 🔧 [8] 종료 신호 처리
def signal_handler(sig, frame):
    print("종료 요청됨. PID 파일 삭제 시도.")
    try:
        os.remove(get_path("worker.pid"))
    except FileNotFoundError:
        print("PID 파일이 이미 존재하지 않습니다.")
    except Exception as e:
        print(f"PID 파일 삭제 중 오류 발생: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid()
    monitor_loop()

