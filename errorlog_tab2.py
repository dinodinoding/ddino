import os
import sys
import time
import json
import signal
import re
from datetime import datetime, timedelta

# [1] PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# [2] PID 파일 기록 → 나중에 종료 가능하도록
def write_pid():
    pid_path = get_path("worker.pid")
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

# [3] 로그에서 heating 메시지 필터링
def extract_heating_timestamps(log_path):
    pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+.*?heating"
    timestamps = []
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "heating" in line.lower():
                match = re.match(pattern, line)
                if match:
                    timestamp_str = match.group().split(" ")[0] + " " + match.group().split(" ")[1]
                    try:
                        timestamps.append(datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f"))
                    except ValueError:
                        pass
    return timestamps

# [4] 주기적으로 모니터링
def monitor_loop():
    # 설정 불러오기
    config_path = get_path("settings.json")
    if not os.path.exists(config_path):
        print("settings.json 파일이 존재하지 않습니다.")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    interval_minutes = config.get("interval_minutes", 60)
    threshold = config.get("threshold", 3)
    log_file = get_path("converted_log.txt")  # 컨버팅된 로그 파일 이름

    print(f">> 감시 시작: {interval_minutes}분 안에 {threshold}회 이상 heating 발생 시 알림")

    history = []

    while True:
        if not os.path.exists(log_file):
            print("로그 파일 없음. 다음 주기까지 대기.")
            time.sleep(10)
            continue

        heating_times = extract_heating_timestamps(log_file)
        heating_times.sort()

        # 최근 감시 범위 내에서 필터링
        now = datetime.now()
        window_start = now - timedelta(minutes=interval_minutes)
        filtered = [t for t in heating_times if window_start <= t <= now]

        print(f"[{now.strftime('%H:%M:%S')}] 감지된 heating 수: {len(filtered)}")
        if len(filtered) >= threshold:
            print("⚠️ 경고: 설정된 횟수 초과 감지!")
            show_alert()

        time.sleep(60)

# [5] 알림 함수 (단순 메시지 출력 또는 팝업으로 교체 가능)
def show_alert():
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "⚠ Heating이 과도하게 반복되었습니다!", "Heating 경고", 0x40 | 0x1)
    except Exception as e:
        print("알림 실패:", e)

# [6] 종료 신호 처리
def signal_handler(sig, frame):
    print("종료 요청됨. PID 파일 삭제.")
    try:
        os.remove(get_path("worker.pid"))
    except:
        pass
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid()
    monitor_loop()