import os
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QProgressBar
)
from PySide6.QtGui import QFont


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        # === [1] 수평 진행바 (버튼 왼쪽) === #
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 무한 로딩 애니메이션
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.hide()  # 초기에는 안 보이게
        filter_layout.addWidget(self.progress_bar, 1)

        # === [2] 변환 실행 버튼 === #
        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시")
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        # === [3] 로그 출력 영역 === #
        layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        # === [4] 고정 경로 설정 === #
        self.converter_path = "C:/monitoring/g4_converter.exe"
        self.convert_list_path = "C:/monitoring/convert_list.txt"
        self.output_dir = "C:/monitoring/errorlog"
        self.error_files = []

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.show()

        self.error_files = self.convert_all_files_from_list()
        if self.error_files:
            self.load_error_log()
        else:
            self.error_view.setPlainText("⚠️ 변환된 로그 파일이 없습니다.")

        self.progress_bar.hide()
        self.reload_button.setEnabled(True)

    def convert_all_files_from_list(self):
        if not os.path.exists(self.convert_list_path):
            print("❌ convert_list.txt가 존재하지 않음")
            return []

        with open(self.convert_list_path, 'r', encoding='utf-8') as f:
            log_files = [line.strip() for line in f if line.strip()]

        converted_paths = []
        for log_path in log_files:
            if not os.path.exists(log_path):
                print(f"❌ 파일 없음: {log_path}")
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            print(f">> 변환: {log_path} -> {out_path}")
            result = subprocess.run([self.converter_path, log_path, out_path])
            if result.returncode == 0:
                converted_paths.append(out_path)
            else:
                print(f"❌ 변환 실패: {log_path}")

        return converted_paths

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