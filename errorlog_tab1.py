import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PySide6.QtCore import QThread, Signal
from utils.config_loader import load_config


class ConverterThread(QThread):
    progress_changed = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, exe_path, list_path, output_dir):
        super().__init__()
        self.exe_path = exe_path
        self.list_path = list_path
        self.output_dir = output_dir

    def run(self):
        try:
            if not os.path.exists(self.exe_path):
                self.finished.emit(False, f"g4_converter.exe 경로 오류: {self.exe_path}")
                return
            if not os.path.exists(self.list_path):
                self.finished.emit(False, f"변환 대상 목록 파일 없음: {self.list_path}")
                return

            with open(self.list_path, 'r', encoding='utf-8') as f:
                file_list = [line.strip() for line in f if line.strip()]
            total = len(file_list)
            if total == 0:
                self.finished.emit(False, "변환할 파일이 없습니다.")
                return

            for i, input_file in enumerate(file_list, 1):
                try:
                    filename = os.path.basename(input_file).replace('.log', '.txt')
                    output_path = os.path.join(self.output_dir, filename)
                    subprocess.run([self.exe_path, '-i', input_file, '-o', output_path], check=True)
                except Exception as e:
                    print(f"[에러] 변환 실패: {input_file} → {e}")
                    continue

                percent = int(i / total * 100)
                self.progress_changed.emit(percent)

            self.finished.emit(True, f"총 {total}개 파일 변환 완료.")
        except Exception as e:
            self.finished.emit(False, str(e))


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # ▒ 설명 라벨 ▒
        self.description_label = QLabel("ooooooooooooooooooooooooooooo")
        layout.addWidget(self.description_label)

        # ▒ 버튼 + 프로그래스바 ▒
        button_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        button_layout.addWidget(self.progress_bar, stretch=1)

        self.run_button = QPushButton("변환 실행")
        self.run_button.setFixedWidth(120)
        self.run_button.clicked.connect(self.on_convert_clicked)
        button_layout.addWidget(self.run_button)
        layout.addLayout(button_layout)

        self.result_label = QLabel()
        layout.addWidget(self.result_label)

        # ▒ config 경로 로드 ▒
        cfg = load_config()
        self.exe_path = cfg.get("g4_converter", "C:/monitoring/g4_converter.exe")
        self.list_path = cfg.get("convert_list", "C:/monitoring/convert_list.txt")
        self.output_dir = cfg.get("output_dir", "C:/monitoring/errorlog")

        print(">> g4_converter:", self.exe_path)
        print(">> 파일 목록:", self.list_path)
        print(">> 출력 폴더:", self.output_dir)

    def on_convert_clicked(self):
        self.run_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.result_label.setText("변환 중입니다...")

        self.thread = ConverterThread(self.exe_path, self.list_path, self.output_dir)
        self.thread.progress_changed.connect(self.progress_bar.setValue)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, success: bool, message: str):
        self.run_button.setEnabled(True)
        self.result_label.setText(message)