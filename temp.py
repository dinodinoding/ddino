import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from PySide2.QtWidgets import QApplication, QMessageBox
import sys

# === [1] 현재 파일 기준 베이스 경로 설정 ===
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# === [2] JSON 로더 ===
def load_json(filename):
    path = get_path(filename)
    if not os.path.exists(path):
        print(f">> [ERROR] 파일 없음: {path}")
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# === [3] 알람창 띄우기 ===
def show_alert(message):
    msg = QMessageBox()
    msg.setWindowTitle("Heating 감지")
    msg.setText(message)
    msg.setIcon(QMessageBox.Warning)
    msg.exec_()

# === [4] 메인 함수 ===
def main():
    app = QApplication(sys.argv)

    # 설정 파일 불러오기
    settings = load_json("settings.json")
    config = load_json("config.json")

    interval = timedelta(minutes=settings["interval_minutes"])
    threshold = settings["threshold"]

    # 모든 경로를 BASE_PATH 기준으로 고정
    raw_log = get_path(config["raw_log_path"])
    bat_file = get_path(config["bat_file_path"])
    converted_log = get_path(config["converted_log_path"])

    heating_times = []
    last_modified_time = 0

    # PID 기록 (옵션)
    with open(get_path("worker.pid"), "w") as f:
        f.write(str(os.getpid()))

    print(">> heating_worker 시작됨")

    # === [5] 감시 루프 시작 ===
    while True:
        try:
            current_modified_time = os.path.getmtime(raw_log)
        except FileNotFoundError:
            print(">> [INFO] 로그 파일 없음. 재시도 대기중...")
            time.sleep(5)
            continue

        if current_modified_time != last_modified_time:
            print(">> 로그 파일 변경 감지 → 변환 시작")
            last_modified_time = current_modified_time

            # BAT 실행
            try:
                subprocess.run(bat_file, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f">> [ERROR] bat 실행 실패: {e}")
                continue

            # 변환된 로그 읽기
            try:
                with open(converted_log, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                print(f">> [ERROR] 변환 로그 읽기 실패: {e}")
                continue

            now = datetime.now()

            # heating 로그 시간 추출
            for line in lines:
                if 'heating' in line.lower():
                    try:
                        timestamp = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
                        heating_times.append(timestamp)
                    except:
                        continue

            # 지정된 시간 안에 발생한 heating만 유지
            heating_times = [t for t in heating_times if now - t <= interval]

            print(f">> 감지된 heating 수: {len(heating_times)} (임계값: {threshold})")

            if len(heating_times) >= threshold:
                show_alert(f"{settings['interval_minutes']}분 안에 heating {threshold}회 감지됨")
                heating_times.clear()

        time.sleep(10)

# === [6] 프로그램 시작 ===
if __name__ == "__main__":
    main()