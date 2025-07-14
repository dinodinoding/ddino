import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from PySide2.QtWidgets import QApplication, QMessageBox
import sys

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def show_alert(message):
    msg = QMessageBox()
    msg.setWindowTitle("Heating 감지")
    msg.setText(message)
    msg.setIcon(QMessageBox.Warning)
    msg.exec_()

def main():
    app = QApplication(sys.argv)

    # 설정 불러오기
    settings = load_json("settings.json")
    config = load_json("config.json")

    interval = timedelta(minutes=settings["interval_minutes"])
    threshold = settings["threshold"]

    raw_log = config["raw_log_path"]
    bat_file = config["bat_file_path"]
    converted_log = config["converted_log_path"]

    heating_times = []
    last_modified_time = 0

    # PID 기록 (OFF에서 종료 시 사용)
    with open("worker.pid", "w") as f:
        f.write(str(os.getpid()))

    print(">> heating_worker 시작됨")
    while True:
        try:
            current_modified_time = os.path.getmtime(raw_log)
        except FileNotFoundError:
            time.sleep(5)
            continue

        if current_modified_time != last_modified_time:
            last_modified_time = current_modified_time

            try:
                subprocess.run(bat_file, shell=True, check=True)
            except subprocess.CalledProcessError:
                continue

            try:
                with open(converted_log, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except:
                continue

            now = datetime.now()

            for line in lines:
                if 'heating' in line.lower():
                    try:
                        timestamp = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
                        heating_times.append(timestamp)
                    except:
                        continue

            heating_times = [t for t in heating_times if now - t <= interval]

            if len(heating_times) >= threshold:
                show_alert(f"{settings['interval_minutes']}분 안에 heating {threshold}회 감지됨")
                heating_times.clear()

        time.sleep(10)

if __name__ == "__main__":
    main()