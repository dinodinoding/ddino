import os
import subprocess
import sys
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QProgressBar, QFrame, QMessageBox, QApplication # QApplication 임포트 추가
)
from PySide6.QtGui import QFont

class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # 설명 라벨 추가
        self.description_label = QLabel(
            "이 탭은 g4_converter.exe를 실행하여 지정된 로그 파일을 변환하고, "
            "변환된 파일에서 최근 24시간 이내의 오류(ERROR) 및 경고(WARNING) 로그를 표시합니다. "
            "로그 파일은 'C:/monitoring/convert_list.txt'에 나열되어 있어야 합니다."
        )
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        # 상단 레이아웃 (진행률 + 버튼)
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        filter_layout.addWidget(self.progress_bar, stretch=1)

        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시")
        self.reload_button.setFixedWidth(200) # 버튼 너비 조정
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

        # 시작 시 출력 디렉토리 존재 여부 확인 및 생성
        self._ensure_output_directory_exists()

    def _ensure_output_directory_exists(self):
        """출력 디렉토리가 존재하는지 확인하고, 없으면 생성합니다."""
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                print(f"출력 디렉토리 생성: {self.output_dir}")
            except OSError as e:
                QMessageBox.critical(self, "디렉토리 생성 오류",
                                     f"출력 디렉토리 '{self.output_dir}'를 생성할 수 없습니다: {e}\n"
                                     "프로그램 실행에 문제가 있을 수 있습니다.")
                print(f"오류: 출력 디렉토리 생성 실패: {e}")

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.error_view.clear() # 새 작업 시작 전 기존 로그 지우기

        # 변환기 실행 파일 존재 여부 확인
        if not os.path.exists(self.converter_path):
            QMessageBox.critical(self, "파일 없음",
                                 f"g4_converter.exe를 찾을 수 없습니다: {self.converter_path}\n"
                                 "경로를 확인하거나 파일을 배치해주세요.")
            self.error_view.setPlainText(f"오류: g4_converter.exe 파일이 '{self.converter_path}' 경로에 존재하지 않습니다.")
            self.reload_button.setEnabled(True)
            return

        self.error_files = self.convert_all_files_from_list()

        if self.error_files:
            self.load_error_log()
        else:
            self.error_view.setPlainText("주의: 변환된 로그 파일이 없거나, 변환 과정에서 문제가 발생했습니다.")

        self.reload_button.setEnabled(True)

    def convert_all_files_from_list(self):
        if not os.path.exists(self.convert_list_path):
            QMessageBox.warning(self, "파일 없음",
                                f"convert_list.txt를 찾을 수 없습니다: {self.convert_list_path}")
            print(f"오류: convert_list.txt가 존재하지 않음: {self.convert_list_path}")
            return []

        with open(self.convert_list_path, 'r', encoding='utf-8') as f:
            log_files = [line.strip() for line in f if line.strip()]

        if not log_files:
            self.error_view.setPlainText("정보: convert_list.txt 파일에 변환할 로그 파일 경로가 없습니다.")
            return []

        total_files = len(log_files)
        # 변환 + 로딩 (변환 실패 파일도 로딩 단계에 포함될 수 있으므로, 총 단계는 동일하게 유지)
        self.total_steps = total_files * 2
        self.progress_bar.setRange(0, self.total_steps)
        self.current_step = 0

        converted_paths = []
        for i, log_path in enumerate(log_files):
            # 변환 진행률 메시지 업데이트
            self.error_view.setPlainText(f"변환 중... ({i+1}/{total_files}): {os.path.basename(log_path)}")
            QApplication.processEvents() # UI 업데이트 강제

            if not os.path.exists(log_path):
                print(f"경고: 원본 파일 없음 (변환 스킵): {log_path}")
                self._increment_progress()
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            try:
                # subprocess.run 호출 시 stdout, stderr 캡처 및 텍스트 모드 사용
                # check=False는 반환 코드가 0이 아니어도 예외를 발생시키지 않음
                result = subprocess.run(
                    [self.converter_path, log_path, out_path],
                    capture_output=True,
                    text=True, # 텍스트 모드로 출력 캡처
                    check=False,
                    encoding='utf-8', # 인코딩 명시
                    creationflags=subprocess.CREATE_NO_WINDOW # 콘솔 창이 뜨지 않도록 함 (Windows only)
                )

                if result.returncode == 0:
                    converted_paths.append(out_path)
                    print(f"변환 성공: {log_path} -> {out_path}")
                else:
                    error_message = result.stderr or result.stdout or "알 수 없는 오류"
                    print(f"오류: 변환 실패 (Return Code: {result.returncode}): {log_path}")
                    print(f"  출력/에러: {error_message.strip()}")
                    # 변환 실패 메시지를 UI에 잠시 표시 (옵션)
                    self.error_view.setPlainText(f"오류: 변환 실패: {os.path.basename(log_path)}\n{error_message.strip()}")
                    QApplication.processEvents() # UI 업데이트 강제

            except FileNotFoundError:
                QMessageBox.critical(self, "실행 파일 없음",
                                     f"g4_converter.exe를 찾을 수 없습니다: {self.converter_path}")
                print(f"오류: g4_converter.exe 실행 파일 찾을 수 없음: {self.converter_path}")
            except Exception as e:
                QMessageBox.critical(self, "변환 중 오류",
                                     f"파일 '{os.path.basename(log_path)}' 변환 중 예외 발생: {e}")
                print(f"오류: 변환 중 예외 발생: {e}")

            self._increment_progress() # 변환 성공/실패 여부와 관계없이 진행률 업데이트

        return converted_paths

    def _increment_progress(self):
        self.current_step += 1
        # 진행률 바가 최대값을 초과하지 않도록 방지
        if self.current_step > self.total_steps:
            self.current_step = self.total_steps
        self.progress_bar.setValue(self.current_step)
        QApplication.processEvents() # UI 업데이트 강제

    def try_parse_time(self, text):
        # 텍스트가 문자열이 아니거나 너무 긴 경우를 방지하여 재귀 오류 가능성 줄임
        if not isinstance(text, str) or len(text) > 50:
            return None

        # 일반적인 두 가지 시간 형식 시도
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt_obj = datetime.strptime(text.strip(), fmt)
                return dt_obj
            except ValueError:
                # ValueError는 예상된 실패이므로 무시하고 다음 형식 시도
                continue
            except Exception as e:
                # 예상치 못한 다른 종류의 예외 발생 시 로그 출력 후 None 반환
                print(f"디버그: try_parse_time에서 알 수 없는 예외 발생: {e}, 입력 텍스트: '{text}'")
                return None
        return None # 모든 형식이 실패하면 None 반환

    def load_error_log(self):
        self.error_view.clear()
        if not self.error_files:
            self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
            return

        time_range = timedelta(days=1) # 최근 24시간
        all_lines = []
        latest_time = None

        total_files_to_process = len(self.error_files)
        processed_files_count = 0

        for path in self.error_files:
            # 로딩 진행률 메시지 업데이트
            self.error_view.setPlainText(f"로그 로딩 및 분석 중... ({processed_files_count+1}/{total_files_to_process}): {os.path.basename(path)}")
            QApplication.processEvents() # UI 업데이트 강제

            self._increment_progress() # 로딩 단계 진행률 업데이트

            if not os.path.exists(path):
                print(f"경고: 변환된 파일 없음 (로딩 스킵): {path}")
                processed_files_count += 1
                continue

            name = os.path.basename(path)
            try:
                # 'errors='ignore'로 인코딩 오류 무시하여 파일 읽기 중단 방지
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        # "Time Pid Tid" 헤더 라인 스킵 (대소문자 무시)
                        if line.strip().lower().startswith("time pid tid"):
                            continue

                        # 로그 라인 분리: 최대 6번 분리하여 메시지 부분을 통째로 가져옴
                        parts = line.strip().split(None, 6)

                        # 최소한의 필드(시간, PID, TID, 레벨, 모듈, 함수, 메시지)가 있는지 확인
                        # 로그 형식에 따라 이 인덱스가 다를 수 있으니 주의
                        if len(parts) < 7:
                            # print(f"디버그: '{name}' 파일의 {line_num+1}번째 줄에서 예상보다 적은 필드 발견: {line.strip()}")
                            continue # 유효하지 않은 라인 스킵

                        # 타임스탬프와 레벨 추출
                        timestamp_str = f"{parts[0]} {parts[1]}"
                        ts = self.try_parse_time(timestamp_str)
                        if not ts:
                            # print(f"디버그: '{name}' 파일의 {line_num+1}번째 줄에서 타임스탬프 파싱 실패: '{timestamp_str}'")
                            continue # 타임스탬프 파싱 실패 시 해당 라인 스킵

                        lvl = parts[4].lower() # 레벨 (예: ERROR, WARNING)
                        msg = parts[6].strip() # 메시지

                        # 가장 최신 시간 업데이트
                        if latest_time is None or ts > latest_time:
                            latest_time = ts
                        all_lines.append((ts, lvl, msg, name))

            except Exception as e:
                print(f"오류: 파일 '{name}' 처리 중 예외 발생: {e}")
                # 오류 발생 시 사용자에게 알림
                QMessageBox.warning(self, "파일 처리 오류",
                                     f"'{name}' 파일을 읽는 중 오류가 발생했습니다: {e}\n"
                                     "해당 파일의 로그는 표시되지 않을 수 있습니다.")
            processed_files_count += 1

        if latest_time is None:
            self.error_view.setPlainText("주의: 로그 파일에서 유효한 시간 정보를 찾을 수 없습니다. 로그 형식을 확인해주세요.")
            return

        cutoff = latest_time - time_range # 필터링할 최소 시간 (최신 시간 - 24시간)
        levels_to_display = ['error', 'warning']
        html_lines = []

        # 시간 역순으로 정렬 후 필터링 및 HTML 생성
        # `all_lines`가 커질 경우 메모리 사용량에 주의해야 하지만, 일반적인 로그 크기에서는 문제 없음
        for ts, lvl, msg, name in sorted(all_lines, key=lambda x: x[0], reverse=True):
            if ts < cutoff or lvl not in levels_to_display:
                continue

            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # 밀리초는 3자리로
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red; font-weight:bold;">ERROR</span>', # 오류는 더 굵게
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper()) # 기본값은 대문자로

            # HTML 형식으로 로그 라인 구성 (고정 너비 폰트 적용 및 줄 바꿈 방지)
            html_lines.append(
                f'<span style="font-family:Courier New; white-space:pre-wrap;">' # pre-wrap으로 공백 유지 및 필요시 자동 줄 바꿈
                f'{file_col:<30}{ts_str:<25}' # 파일명과 시간 열 너비 고정
                f'{level_colored:<10}{msg}</span>'
            )

        # 마지막으로 진행률 바를 최대로 설정하여 완료를 나타냄
        self.progress_bar.setValue(self.total_steps)
        QApplication.processEvents()

        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("정보: 해당 시간 구간 (최근 24시간)에 오류 또는 경고 로그가 없습니다.")


# --- (이 코드를 실행하기 위한 최소한의 메인 앱 구조) ---
# 이 부분은 ErrorLogTab이 단일 파일로 동작하지 않고, 메인 애플리케이션에 포함될 때 필요합니다.
# 실제 애플리케이션에서는 이 부분을 별도의 메인 파일에 구성해야 합니다.
if __name__ == "__main__":
    app = QApplication(sys.argv)

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("로그 뷰어")
            self.setGeometry(100, 100, 900, 700) # 창 크기 조정

            tab_widget = QTabWidget()
            self.setCentralWidget(tab_widget)

            error_log_tab = ErrorLogTab()
            tab_widget.addTab(error_log_tab, "오류/경고 로그")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
