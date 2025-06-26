# error_log_tab.py

import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QComboBox, QCheckBox, QProgressBar,
    QStackedLayout, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from utils.config_loader import load_config
import subprocess


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        print(">> ErrorLogTab 초기화 시작")

        layout = QVBoxLayout(self)

        # 상단 필터 옵션
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        filter_layout.addWidget(QLabel("기간 선택:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["30분", "1시간", "6시간", "12시간", "1일"])
        self.time_combo.currentTextChanged.connect(self.load_error_log)
        filter_layout.addWidget(self.time_combo)

        self.include_warning = QCheckBox("Warning 포함")
        self.include_warning.stateChanged.connect(self.load_error_log)
        filter_layout.addWidget(self.include_warning)

        self.stretchy_layout = QStackedLayout()
        spacer = QFrame()
        spacer.setFrameShape(QFrame.NoFrame)
        self.stretchy_layout.addWidget(spacer)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 20000)
        self.progress_bar.setTextVisible(True)
        self.stretchy_layout.addWidget(self.progress_bar)

        filter_layout.addLayout(self.stretchy_layout, 1)

        self.reload_button = QPushButton("bat 실행 후 로그 다시 불러오기")
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        layout.addWidget(QLabel("선택한 기간의 오류/경고 로그:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        print(">> config.json 로드 시도")
        cfg = load_config()
        self.error_files = cfg.get("error_logs", [])
        self.bat_path = cfg.get("batch_file", "")
        print(f">> 로드된 로그 파일 목록: {self.error_files}")
        print(f">> 실행할 배치 파일 경로: {self.bat_path}")

        self.load_error_log()
        print(">> ErrorLogTab 초기화 완료")

    def on_reload_clicked(self):
        print(">> [사용자 클릭] bat 실행 및 로그 재로드 요청")
        if not os.path.exists(self.bat_path):
            msg = f"[오류] 배치 파일이 존재하지 않습니다: {self.bat_path}"
            self.error_view.setPlainText(msg)
            print(msg)
            return

        try:
            subprocess.Popen(self.bat_path, shell=True)
            print(f">> bat 실행: {self.bat_path}")
        except Exception as e:
            print(f"[예외] bat 실행 실패: {e}")
            self.error_view.setPlainText(f"bat 실행 실패: {e}")
            return

        self.reload_button.setEnabled(False)
        self.stretchy_layout.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.elapsed_time = 0
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(100)

    def _update_progress(self):
        self.elapsed_time += 100
        self.progress_bar.setValue(self.elapsed_time)
        if self.elapsed_time >= 20000:
            print(">> 진행 완료. 로그 불러오기 실행")
            self.progress_timer.stop()
            self.stretchy_layout.setCurrentIndex(0)
            self.reload_button.setEnabled(True)
            self.load_error_log()

    def load_error_log(self):
        print(">> 로그 로드 시작")
        self.error_view.clear()

        if not self.error_files:
            print(">> 로그 파일 경로 없음")
            self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
            return

        selected = self.time_combo.currentText()
        print(f">> 선택된 시간 필터: {selected}")
        delta_map = {
            "30분": timedelta(minutes=30),
            "1시간": timedelta(hours=1),
            "6시간": timedelta(hours=6),
            "12시간": timedelta(hours=12),
            "1일": timedelta(days=1),
        }
        time_range = delta_map.get(selected, timedelta(minutes=30))

        try:
            max_len = max(len(f"[{os.path.basename(p)}]") for p in self.error_files)
            file_col_width = max_len + 2
        except Exception as e:
            print(f">> [경고] 파일명 길이 계산 실패: {e}")
            file_col_width = 20

        all_lines = []
        latest_time = None
        print(">> 로그 파일 순회 시작")
        for path in self.error_files:
            print(f">> 파일 확인: {path}")
            if not os.path.exists(path):
                print(f"   !! 존재하지 않음: {path}")
                continue
            name = os.path.basename(path)
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        ts = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
                        latest_time = ts if latest_time is None or ts > latest_time else latest_time
                        all_lines.append((ts, line.strip(), name))
                    except ValueError:
                        continue

        if latest_time is None:
            print(">> 유효한 로그 시간 없음")
            self.error_view.setPlainText("로그에서 유효한 시간 정보를 찾을 수 없습니다.")
            return

        cutoff = latest_time - time_range
        print(f">> 로그 시간 기준: 최신={latest_time}, 필터기준={cutoff}")

        levels = ['error']
        if self.include_warning.isChecked():
            levels.append('warning')
        print(f">> 필터링 대상 로그 레벨: {levels}")

        html_lines = []
        for ts, line, name in all_lines:
            if ts < cutoff:
                continue
            try:
                parts = line.split(None, 5)
                lvl = parts[4].lower()
                if lvl in levels:
                    file_col = f"[{name}]"
                    ts_col = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    msg = ' '.join(parts[5].split()[2:]) if len(parts[5].split()) > 2 else ''

                    if lvl == "error":
                        level_colored = '<span style="color:red;">ERROR</span>'
                    elif lvl == "warning":
                        level_colored = '<span style="color:orange;">WARNING</span>'
                    else:
                        level_colored = lvl.upper()

                    html_line = (
                        f'<span style="color:black; font-family:Courier New;">'
                        f'{file_col:<{file_col_width}}{ts_col:<25}'
                        f'{level_colored:<10}{msg}'
                        f'</span>'
                    )
                    html_lines.append(html_line)
            except IndexError:
                continue

        if html_lines:
            print(f">> 필터링된 라인 수: {len(html_lines)}")
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            print(">> 필터링된 로그 없음")
            self.error_view.setPlainText("해당 시간 구간의 로그가 없습니다.")
