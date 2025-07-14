import os
import time
import subprocess
import json
from datetime import datetime, timedelta
from PySide6.QtWidgets import QApplication, QMessageBox
import sys

# PySide6를 사용하여 알람창을 띄우기 위한 QApplication 객체 생성
app = QApplication(sys.argv)

# ========== [1] 설정 파일 로드 ==========
def load_config(config_path='config.json'):
    with open(config_path, 'r') as f:
        return json.load(f)

# ========== [2] 알람 창 표시 ==========
def show_alert():
    msg = QMessageBox()
    msg.setWindowTitle("Heating 과다 발생")
    msg.setText("최근 1시간 내에 heating 이벤트가 3회 이상 감지되었습니다.")
    msg.setIcon(QMessageBox.Warning)
    msg.exec()

# ========== [3] heating 발생 시간 저장 리스트 ==========
heating_times = []

# ========== [4] 변환된 로그(txt) 파싱 후 heating 시간 추출 ==========
def parse_converted_log(log_path):
    global heating_times

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[ERROR] 로그 파일 읽기 실패: {e}")
        return

    now = datetime.now()

    for line in lines:
        if 'heating' in line.lower():
            try:
                # 타임스탬프는 로그의 앞부분에 있음: "2024-07-20 11:23:35.076"
                timestamp_str = line[:23]
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")

                # 유효한 heating만 시간 리스트에 추가
                heating_times.append(timestamp)

                # 1시간보다 오래된 이벤트 제거 (슬라이딩 윈도우 유지)
                heating_times[:] = [t for t in heating_times if now - t <= timedelta(hours=1)]

                # 1시간 내 3회 이상이면 알람 표시
                if len(heating_times) >= 3:
                    show_alert()
                    # 알람 후 리스트 초기화 (중복 방지, 이후 이벤트 기준으로 새 감시)
                    heating_times.clear()

            except Exception as e:
                print(f"[ERROR] 타임스탬프 파싱 실패: {e}")
                continue

# ========== [5] 로그 변경 감지 및 주기적 파싱 ==========
def monitor_loop(config):
    raw_log = config["raw_log_path"]
    bat_file = config["bat_file_path"]
    converted_log = config["converted_log_path"]

    last_modified_time = 0

    print(">> 모니터링 시작...")
    while True:
        try:
            current_modified_time = os.path.getmtime(raw_log)
        except FileNotFoundError:
            print(f"[ERROR] 로그 파일 없음: {raw_log}")
            time.sleep(5)
            continue

        if current_modified_time != last_modified_time:
            last_modified_time = current_modified_time
            print(">> 로그 변경 감지됨 - 변환 및 분석 수행")

            # [1] .bat 실행하여 로그 변환
            try:
                subprocess.run(bat_file, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] bat 실행 실패: {e}")
                continue

            # [2] 변환된 로그에서 heating 감지 및 조건 판단
            parse_converted_log(converted_log)

        # 너무 자주 확인하지 않도록 10초 대기
        time.sleep(10)

# ========== [6] 실행 시작 ==========
if __name__ == "__main__":
    config = load_config()
    monitor_loop(config)