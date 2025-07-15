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
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        print(f"[INIT] PID {os.getpid()}가 {pid_path}에 기록되었습니다.")
    except Exception as e:
        print(f"[ERROR] PID 파일 기록 실패: {e}")

# 🔧 [3] 설정 파일 로드 함수
def load_settings():
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        print(f"[ERROR] settings.json 파일이 존재하지 않습니다: {config_path}")
        print("[INFO] 기본값을 사용합니다. GUI에서 설정을 저장해 주세요.")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        print(f"[INFO] settings.json 파일 로드 성공: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[ERROR] settings.json 파일 파싱 오류: {e}. 파일을 확인해주세요.")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}
    except Exception as e:
        print(f"[ERROR] settings.json 로드 중 알 수 없는 오류: {e}")
        return {"interval_minutes": 60, "threshold": 3, "original_log_file_path": ""}


# 🔧 [4] 로그에서 heating 메시지 필터링 (converted_log.txt 에서 읽음)
def extract_heating_timestamps(log_path):
    print(f"[DEBUG] '{log_path}'에서 heating 타임스탬프 추출 시작...")
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?).*?heating"
    timestamps = []
    if not os.path.exists(log_path):
        print(f"[DEBUG] '{log_path}' 파일이 존재하지 않습니다.")
        return timestamps

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                if "heating" in line.lower():
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            found_fmt = None
                            for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"]:
                                try:
                                    ts = datetime.strptime(timestamp_str, fmt)
                                    timestamps.append(ts)
                                    found_fmt = fmt
                                    break
                                except ValueError:
                                    pass
                            if found_fmt:
                                print(f"[DEBUG] 라인 {line_num}: 'heating' 감지, 타임스탬프 파싱 성공: {timestamp_str} (형식: {found_fmt})")
                            else:
                                print(f"[WARNING] 라인 {line_num}: 'heating' 감지, 알 수 없는 타임스탬프 형식: '{timestamp_str}'")
                        except Exception as e:
                            print(f"[ERROR] 라인 {line_num}: 타임스탬프 파싱 중 예외 발생: {timestamp_str} - {e}")
                    else:
                        print(f"[WARNING] 라인 {line_num}: 'heating' 감지했지만 타임스탬프 패턴 불일치: '{line.strip()}'")
    except Exception as e:
        print(f"[ERROR] '{log_path}' 파일 읽기 중 오류 발생: {e}")

    print(f"[DEBUG] '{log_path}'에서 총 {len(timestamps)}개의 heating 타임스탬프 추출 완료.")
    return timestamps

# 🔧 [5] 원본 로그 파일에서 새로운 내용을 읽어 converted_log.txt에 추가
def update_converted_log(original_log_path, converted_log_path, last_read_pos_file):
    print(f"[DEBUG] '{original_log_path}'에서 새 내용 확인 및 '{converted_log_path}' 업데이트 시작...")
    current_read_pos = 0
    if os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "r") as f:
                content = f.read().strip()
                if content:
                    current_read_pos = int(content)
                else:
                    print(f"[DEBUG] '{last_read_pos_file}' 파일이 비어 있습니다. 초기화합니다.")
                    current_read_pos = 0
        except (ValueError, FileNotFoundError):
            print(f"[WARNING] '{last_read_pos_file}' 파일 손상 또는 없음. 위치를 0으로 초기화합니다.")
            current_read_pos = 0

    print(f"[DEBUG] 이전 읽기 위치: {current_read_pos} 바이트.")

    if not os.path.exists(original_log_path):
        print(f"[ERROR] 원본 로그 파일 '{original_log_path}'을(를) 찾을 수 없습니다. 경로를 확인해주세요.")
        return current_read_pos

    try:
        with open(original_log_path, "r", encoding="utf-8", errors="ignore") as original_f:
            original_f.seek(0, os.SEEK_END) # 파일 끝으로 이동하여 총 크기 확인
            file_size = original_f.tell()
            print(f"[DEBUG] 원본 로그 파일 크기: {file_size} 바이트.")

            if file_size < current_read_pos: # 파일이 이전보다 작아졌으면 (로그 로테이션 등)
                print(f"[INFO] 원본 로그 파일이 로테이션되거나 축소된 것 같습니다. 위치를 0으로 초기화하고 처음부터 다시 읽습니다.")
                current_read_pos = 0 # 위치 초기화
                # converted_log.txt도 비울지 여부는 정책에 따라 결정 (여기서는 기존 내용을 유지)

            original_f.seek(current_read_pos) # 다시 마지막으로 읽은 위치로 이동
            new_content = original_f.read() # 새로운 내용 읽기
            new_pos = original_f.tell() # 새로 읽은 후의 파일 위치

        if new_content:
            with open(converted_log_path, "a", encoding="utf-8") as converted_f: # 'a' (append) 모드
                converted_f.write(new_content)
            print(f"[INFO] 새로운 로그 내용 {len(new_content)} 바이트를 '{converted_log_path}'에 추가했습니다. 새 읽기 위치: {new_pos}.")
        else:
            print(f"[DEBUG] 원본 로그 파일에 새로운 내용이 없습니다.")
            
        # 다음 스캔을 위해 마지막으로 읽은 위치 저장
        with open(last_read_pos_file, "w") as f:
            f.write(str(new_pos))
        
        return new_pos

    except Exception as e:
        print(f"[ERROR] 로그 파일 읽기/쓰기 중 예외 발생: {e}")
        return current_read_pos # 오류 발생 시 위치 유지

# 🔧 [6] 주기적으로 모니터링
def monitor_loop():
    print("[INIT] 모니터링 루프 시작.")
    settings = load_settings()
    interval_minutes = settings.get("interval_minutes", 60)
    threshold = settings.get("threshold", 3)
    original_log_file = settings.get("original_log_file_path", "") # 원본 로그 파일 경로
    converted_log_file = get_path("converted_log.txt") # 변환된 로그 파일 (이 스크립트가 업데이트)
    last_read_pos_file = get_path("last_read_pos.txt") # 마지막으로 읽은 위치 기록 파일

    print(f"[INFO] 설정: 감시 시간={interval_minutes}분, 허용 횟수={threshold}회.")
    if not original_log_file:
        print("[ERROR] 'original_log_file_path' 설정이 비어 있습니다. GUI에서 정확한 경로를 지정해주세요.")
        print("[INFO] 워커를 종료합니다.")
        sys.exit(1) # 설정 오류 시 종료
    
    print(f"[INFO] 원본 로그 파일: '{original_log_file}'")
    print(f"[INFO] 변환된 로그 파일 (기록): '{converted_log_file}'")
    print(f"[INFO] 마지막 읽기 위치 기록 파일: '{last_read_pos_file}'")

    # last_read_pos.txt 파일이 없으면 초기화
    if not os.path.exists(last_read_pos_file):
        try:
            with open(last_read_pos_file, "w") as f:
                f.write("0")
            print(f"[INIT] '{last_read_pos_file}' 파일이 초기화되었습니다.")
        except Exception as e:
            print(f"[ERROR] '{last_read_pos_file}' 파일 초기화 실패: {e}")

    while True:
        print(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 주기 시작 ---")
        # [1단계] 원본 로그 파일에서 새로운 내용을 converted_log.txt로 업데이트
        update_converted_log(original_log_file, converted_log_file, last_read_pos_file)

        if not os.path.exists(converted_log_file):
            print(f"[WARNING] '{converted_log_file}' 파일이 아직 존재하지 않습니다. 다음 주기까지 대기.")
            time.sleep(60) # 1분 대기
            continue

        # [2단계] converted_log.txt에서 heating 타임스탬프 추출 및 알람 로직 실행
        heating_times = extract_heating_timestamps(converted_log_file)
        heating_times.sort() # 추출된 타임스탬프 정렬

        # 최근 감시 범위 내에서 필터링 (롤링 윈도우)
        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        filtered_heating_events = [t for t in heating_times if window_start <= t <= now]

        print(f"[INFO] 현재 시간: {now.strftime('%H:%M:%S')}")
        print(f"[INFO] 감시 창 시작: {window_start.strftime('%H:%M:%S')}")
        print(f"[INFO] 총 추출된 heating 이벤트 수: {len(heating_times)}")
        print(f"[INFO] 감지된 heating 수 (최근 {interval_minutes}분): {len(filtered_heating_events)}")
        
        # --- 알람 조건 확인 ---
        if len(filtered_heating_events) >= threshold:
            print(f"!!! [ALERT] 임계값 ({threshold}회) 초과 감지! 현재 {len(filtered_heating_events)}회.")
            show_alert()
        else:
            print(f"[INFO] 임계값 ({threshold}회) 미만. 현재 {len(filtered_heating_events)}회. 알림 없음.")

        print(f"--- 모니터링 주기 완료. 다음 주기까지 {60}초 대기 ---")
        time.sleep(60) # 1분 대기

# 🔧 [7] 알림 함수 (단순 메시지 출력 또는 팝업으로 교체 가능)
def show_alert():
    print("!!! [ALERT] 팝업 알림 시도: Heating이 과도하게 반복되었습니다!")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "⚠ Heating이 과도하게 반복되었습니다!", "Heating 경고", 0x40 | 0x1)
    except Exception as e:
        print(f"[ERROR] 알림 실패: {e}. (Windows 환경이 아니거나 권한 문제가 있을 수 있습니다.)")

# 🔧 [8] 종료 신호 처리
def signal_handler(sig, frame):
    print("\n[INFO] 종료 요청됨. PID 파일 삭제 시도.")
    try:
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            os.remove(pid_path)
            print(f"[INFO] '{pid_path}' 파일이 삭제되었습니다.")
        else:
            print(f"[INFO] '{pid_path}' 파일이 이미 존재하지 않습니다.")
    except Exception as e:
        print(f"[ERROR] PID 파일 삭제 중 오류 발생: {e}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid() # PID 기록은 시작 시 한 번만
    monitor_loop()

