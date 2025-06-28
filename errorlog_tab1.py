import os
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QProgressBar, QFrame
)
from PySide6.QtGui import QFont


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # 설명 라벨 추가
        self.description_label = QLabel("ooooooooooooooooooooooooooooo")
        layout.addWidget(self.description_label)

        # 상단 레이아웃 (진행률 + 버튼)
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        filter_layout.addWidget(self.progress_bar, stretch=1)

        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시")
        self.reload_button.setFixedWidth(120)
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        # 경로 세팅
        self.converter_path = "C:/monitoring/g4_converter.exe"
        self.convert_list_path = "C:/monitoring/convert_list.txt"
        self.output_dir = "C:/monitoring/errorlog"
        self.error_files = []

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)

        self.error_files = self.convert_all_files_from_list()

        if self.error_files:
            self.load_error_log()
        else:
            self.error_view.setPlainText("⚠️ 변환된 로그 파일이 없습니다.")

        self.reload_button.setEnabled(True)

    def convert_all_files_from_list(self):
        if not os.path.exists(self.convert_list_path):
            print("❌ convert_list.txt가 존재하지 않음")
            return []

        with open(self.convert_list_path, 'r', encoding='utf-8') as f:
            log_files = [line.strip() for line in f if line.strip()]

        total_files = len(log_files)
        self.total_steps = total_files * 2  # 변환 + 로딩
        self.progress_bar.setRange(0, self.total_steps)
        self.current_step = 0

        converted_paths = []
        for log_path in log_files:
            if not os.path.exists(log_path):
                print(f"❌ 파일 없음: {log_path}")
                self._increment_progress()
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            result = subprocess.run([self.converter_path, log_path, out_path])
            if result.returncode == 0:
                converted_paths.append(out_path)
            else:
                print(f"❌ 변환 실패: {log_path}")

            self._increment_progress()

        return converted_paths

    def _increment_progress(self):
        self.current_step += 1
        self.progress_bar.setValue(self.current_step)

    def try_parse_time(self, text):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
        return None

    def load_error_log(self):
        self.error_view.clear()
        if not self.error_files:
            self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
            return

        time_range = timedelta(days=1)
        all_lines = []
        latest_time = None

        for path in self.error_files:
            self._increment_progress()

            if not os.path.exists(path):
                continue

            name = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.lower().startswith("time pid tid"):
                            continue
                        parts = line.strip().split(None, 6)
                        if len(parts) < 7:
                            continue

                        ts = self.try_parse_time(f"{parts[0]} {parts[1]}")
                        if not ts:
                            continue
                        lvl = parts[4].lower()
                        msg = parts[6].strip()

                        latest_time = ts if latest_time is None or ts > latest_time else latest_time
                        all_lines.append((ts, lvl, msg, name))
            except Exception as e:
                print(f"파일 처리 오류: {e}")
                continue

        if latest_time is None:
            self.error_view.setPlainText("유효한 시간 정보 없음")
            return

        cutoff = latest_time - time_range
        levels = ['error', 'warning']
        html_lines = []

        for ts, lvl, msg, name in sorted(all_lines, key=lambda x: x[0], reverse=True):
            if ts < cutoff or lvl not in levels:
                continue
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red;">ERROR</span>',
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper())
            html_lines.append(
                f'<span style="color:black; font-family:Courier New;">'
                f'{file_col:<30}{ts_str:<25}'
                f'{level_colored:<10}{msg}</span>'
            )

        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("해당 시간 구간의 로그가 없습니다.")