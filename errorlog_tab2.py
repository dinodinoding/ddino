import os
import subprocess
import sys
import json
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QProgressBar, QFrame, QMessageBox, QApplication, QCheckBox,
    QMainWindow, QTabWidget, QScrollArea # QScrollArea 추가
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from collections import OrderedDict

class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # 설명 라벨
        self.description_label = QLabel(
            "이 탭은 g4_converter.exe를 실행하여 지정된 로그 파일을 변환하고, "
            "변환된 파일에서 최근 24시간 이내의 오류(ERROR) 및 경고(WARNING) 로그를 표시합니다. "
            "'config.json' 파일에 정의된 그룹별 로그를 선택하여 변환할 수 있습니다."
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
        self.reload_button.setFixedWidth(200)
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        # "All" 및 "Selected" 체크박스 섹션
        selection_layout = QHBoxLayout()
        self.all_checkbox = QCheckBox("모든 로그 (All)")
        self.selected_checkbox = QCheckBox("선택된 로그 그룹 (Selected)")
        selection_layout.addWidget(self.all_checkbox)
        selection_layout.addWidget(self.selected_checkbox)
        selection_layout.addStretch(1) # 우측으로 밀기
        layout.addLayout(selection_layout) # 먼저 추가

        # 로그 그룹 선택 체크박스 섹션 (가로 정렬)
        layout.addWidget(QLabel("변환할 로그 그룹 선택:"))

        # 그룹 체크박스를 담을 컨테이너 위젯과 가로 레이아웃
        self.group_checkbox_container = QWidget()
        self.group_checkbox_layout = QHBoxLayout(self.group_checkbox_container) # QHBoxLayout로 변경
        self.group_checkbox_layout.setAlignment(Qt.AlignLeft) # 왼쪽 정렬
        self.group_checkbox_layout.addStretch(1) # 체크박스들 배치 후 남은 공간을 밀어줌

        # 체크박스 수가 많아질 경우를 대비해 스크롤 영역 추가
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.group_checkbox_container)
        scroll_area.setFixedHeight(80) # 스크롤 영역 높이 조절
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded) # 가로 스크롤바 필요할 때만
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # 세로 스크롤바는 항상 끔

        layout.addWidget(scroll_area) # 스크롤 영역을 레이아웃에 추가

        self.group_checkboxes = {} # 그룹별 QCheckBox 객체를 저장할 딕셔너리 (이름:객체)


        layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        # --- 설정 파일 로드 및 경로 초기화 ---
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(current_script_dir, "settings", "config.json")

        self.config = self._load_config()
        if not self.config:
            self.reload_button.setEnabled(False)
            for widget in self.findChildren(QWidget):
                if widget is not self.description_label:
                    widget.setEnabled(False)
            return

        self.converter_path = self.config.get("converter_path")
        self.output_dir = self.config.get("output_dir")

        updated_conversion_group_files = OrderedDict()
        for group_name, relative_path in self.config.get("conversion_groups", {}).items():
            if not os.path.isabs(relative_path):
                updated_conversion_group_files[group_name] = os.path.join(current_script_dir, "settings", relative_path)
            else:
                updated_conversion_group_files[group_name] = relative_path
        self.conversion_group_files = updated_conversion_group_files


        self._ensure_output_directory_exists()

        # 체크박스 시그널 연결
        self.all_checkbox.toggled.connect(self._handle_all_checkbox_toggled)
        self.selected_checkbox.toggled.connect(self._handle_selected_checkbox_toggled)

        # 시작 시 그룹 정보 로드 및 체크박스 생성
        self.log_groups = self._parse_all_group_files()
        self._create_group_checkboxes()

        # 초기 상태 설정: "All" 체크박스를 기본으로 선택
        self.all_checkbox.setChecked(True)

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

    def _load_config(self):
        """
        config.json 파일을 로드하여 설정을 반환합니다.
        """
        if not os.path.exists(self.config_path):
            QMessageBox.critical(self, "설정 파일 없음",
                                 f"설정 파일 '{self.config_path}'을(를) 찾을 수 없습니다.\n"
                                 "애플리케이션을 시작할 수 없습니다.")
            return None
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "설정 파일 오류",
                                 f"설정 파일 '{self.config_path}' 파싱 중 오류 발생: {e}\n"
                                 "JSON 형식을 확인해주세요. 애플리케이션을 시작할 수 없습니다.")
            return None
        except Exception as e:
            QMessageBox.critical(self, "설정 파일 오류",
                                 f"설정 파일 '{self.config_path}' 로드 중 알 수 없는 오류 발생: {e}\n"
                                 "애플리케이션을 시작할 수 없습니다.")
            return None

    def _parse_all_group_files(self):
        """
        config.json에 정의된 모든 그룹 파일들을 파싱하여
        그룹명과 해당 그룹에 속하는 로그 파일 경로 목록을 로드합니다.
        반환 형식: OrderedDict[str, List[str]]
        """
        all_parsed_groups = OrderedDict()
        for group_name, file_path in self.conversion_group_files.items():
            parsed_files = self._parse_single_list_file(file_path)
            all_parsed_groups[group_name] = parsed_files
        return all_parsed_groups

    def _parse_single_list_file(self, file_path):
        """
        단일 그룹 목록 파일(예: convert_motor_list.txt)을 파싱하여
        해당 그룹에 속하는 로그 파일 경로 목록을 반환합니다.
        """
        files_in_group = []
        if not os.path.exists(file_path):
            print(f"경고: 그룹 목록 파일 '{file_path}'을(를) 찾을 수 없습니다. 이 그룹은 비어있습니다.")
            return files_in_group

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): # 빈 줄 또는 주석 무시
                        continue
                    files_in_group.append(line)
        except Exception as e:
            QMessageBox.warning(self, "그룹 파일 읽기 오류",
                                 f"그룹 파일 '{os.path.basename(file_path)}'을(를) 읽는 중 오류 발생: {e}\n"
                                 "일부 로그가 누락될 수 있습니다.")
            print(f"오류: 그룹 파일 읽기 실패 '{file_path}': {e}")
        return files_in_group

    def _create_group_checkboxes(self):
        """
        로드된 그룹 정보를 기반으로 UI에 그룹 선택 체크박스를 동적으로 생성합니다.
        """
        # 기존 체크박스가 있다면 모두 제거
        while self.group_checkbox_layout.count():
            item = self.group_checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.group_checkboxes = {} # 딕셔너리 초기화

        # self.log_groups에서 키(그룹명)를 가져와 체크박스 생성
        for group_name in self.log_groups.keys():
            chk_box = QCheckBox(group_name)
            chk_box.toggled.connect(lambda checked, name=group_name: self._handle_group_checkbox_toggled(name, checked))
            self.group_checkbox_layout.addWidget(chk_box)
            self.group_checkboxes[group_name] = chk_box

        # 초기에는 그룹 체크박스들을 비활성화 (All이 기본 선택이므로)
        for chk_box in self.group_checkboxes.values():
            chk_box.setEnabled(False)

    def _handle_all_checkbox_toggled(self, checked):
        """
        'All' 체크박스가 토글될 때 다른 체크박스의 상태를 제어합니다.
        """
        if checked:
            self.selected_checkbox.setChecked(False)
            for chk_box in self.group_checkboxes.values():
                chk_box.setChecked(False)
                chk_box.setEnabled(False)
        else:
            if not self.selected_checkbox.isChecked():
                for chk_box in self.group_checkboxes.values():
                    chk_box.setEnabled(True)

    def _handle_selected_checkbox_toggled(self, checked):
        """
        'Selected' 체크박스가 토글될 때 다른 체크박스의 상태를 제어합니다.
        """
        if checked:
            self.all_checkbox.setChecked(False)
            for chk_box in self.group_checkboxes.values():
                chk_box.setEnabled(True)
        else:
            if not self.all_checkbox.isChecked():
                for chk_box in self.group_checkboxes.values():
                    chk_box.setEnabled(False)
                    chk_box.setChecked(False)

    def _handle_group_checkbox_toggled(self, group_name, checked):
        """
        개별 그룹 체크박스가 토글될 때 'All'/'Selected' 체크박스의 상태를 제어합니다.
        """
        if checked:
            if self.all_checkbox.isChecked():
                self.all_checkbox.setChecked(False)
                QApplication.processEvents()
                self.group_checkboxes[group_name].setChecked(True)

            if not self.selected_checkbox.isChecked():
                self.selected_checkbox.setChecked(True)
        else:
            any_group_selected = any(chk.isChecked() for chk in self.group_checkboxes.values())
            if not any_group_selected and self.selected_checkbox.isChecked():
                self.selected_checkbox.setChecked(False)

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.error_view.clear()

        if not self.converter_path or not os.path.exists(self.converter_path):
            QMessageBox.critical(self, "파일 없음",
                                 f"g4_converter.exe를 찾을 수 없거나 경로가 유효하지 않습니다: {self.converter_path}\n"
                                 "config.json 파일을 확인해주세요.")
            self.error_view.setPlainText(f"오류: g4_converter.exe 파일 경로가 유효하지 않습니다.")
            self.reload_button.setEnabled(True)
            return

        log_files_to_convert = []
        if self.all_checkbox.isChecked():
            for files in self.log_groups.values():
                log_files_to_convert.extend(files)
            log_files_to_convert = list(set(log_files_to_convert))
            self.error_view.setPlainText("모든 로그 파일을 변환합니다...")
            QApplication.processEvents()
        elif self.selected_checkbox.isChecked():
            selected_groups = [name for name, chk_box in self.group_checkboxes.items() if chk_box.isChecked()]
            if not selected_groups:
                QMessageBox.warning(self, "선택 필요", "선택된 로그 그룹이 없습니다. 변환할 로그를 선택해주세요.")
                self.reload_button.setEnabled(True)
                self.error_view.setPlainText("변환할 로그 그룹이 선택되지 않았습니다.")
                return

            for group_name in selected_groups:
                log_files_to_convert.extend(self.log_groups.get(group_name, []))
            log_files_to_convert = list(set(log_files_to_convert))
            self.error_view.setPlainText(f"선택된 그룹 ({', '.join(selected_groups)})의 로그 파일을 변환합니다...")
            QApplication.processEvents()
        else:
            QMessageBox.warning(self, "선택 필요", "변환할 로그 그룹 옵션 ('모든 로그' 또는 '선택된 로그 그룹')을 선택해주세요.")
            self.reload_button.setEnabled(True)
            self.error_view.setPlainText("변환 옵션이 선택되지 않았습니다.")
            return

        if not log_files_to_convert:
            self.error_view.setPlainText("정보: 변환할 로그 파일 경로가 없습니다. 'config.json' 및 그룹 파일들을 확인해주세요.")
            self.reload_button.setEnabled(True)
            return

        total_files = len(log_files_to_convert)
        self.total_steps = total_files * 2
        self.progress_bar.setRange(0, self.total_steps)
        self.current_step = 0

        converted_paths = []
        for i, log_path in enumerate(log_files_to_convert):
            self.error_view.setPlainText(f"변환 중... ({i+1}/{total_files}): {os.path.basename(log_path)}")
            QApplication.processEvents()

            if not os.path.exists(log_path):
                print(f"경고: 원본 파일 없음 (변환 스킵): {log_path}")
                self._increment_progress()
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            try:
                result = subprocess.run(
                    [self.converter_path, log_path, out_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                if result.returncode == 0:
                    converted_paths.append(out_path)
                    print(f"변환 성공: {log_path} -> {out_path}")
                else:
                    error_message = result.stderr or result.stdout or "알 수 없는 오류"
                    print(f"오류: 변환 실패 (Return Code: {result.returncode}): {log_path}")
                    self.error_view.setPlainText(f"오류: 변환 실패: {os.path.basename(log_path)}\n{error_message.strip()}")
                    QApplication.processEvents()

            except FileNotFoundError:
                QMessageBox.critical(self, "실행 파일 없음",
                                     f"g4_converter.exe를 찾을 수 없습니다: {self.converter_path}")
                print(f"오류: g4_converter.exe 실행 파일 찾을 수 없음: {self.converter_path}")
                break
            except Exception as e:
                QMessageBox.critical(self, "변환 중 오류",
                                     f"파일 '{os.path.basename(log_path)}' 변환 중 예외 발생: {e}")
                print(f"오류: 변환 중 예외 발생: {e}")
                break

            self._increment_progress()

        self.error_files = converted_paths

        if self.error_files:
            self.load_error_log()
        else:
            self.error_view.setPlainText("주의: 변환된 로그 파일이 없거나, 변환 과정에서 문제가 발생했습니다.")

        self.reload_button.setEnabled(True)

    def _increment_progress(self):
        """진행률 바를 한 단계 증가시킵니다."""
        self.current_step += 1
        if self.current_step > self.total_steps:
            self.current_step = self.total_steps
        self.progress_bar.setValue(self.current_step)
        QApplication.processEvents()

    def try_parse_time(self, text):
        """
        주어진 텍스트에서 시간 정보를 파싱합니다.
        예상되는 시간 형식: "YYYY-MM-DD HH:MM:SS.ms" 또는 "YYYY-MM-DD HH:MM:SS"
        """
        if not isinstance(text, str) or len(text) > 50:
            return None

        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt_obj = datetime.strptime(text.strip(), fmt)
                return dt_obj
            except ValueError:
                continue
            except Exception as e:
                print(f"디버그: try_parse_time에서 알 수 없는 예외 발생: {e}, 입력 텍스트: '{text}'")
                return None
        return None

    def load_error_log(self):
        """
        변환된 로그 파일에서 최근 24시간 이내의 오류/경고 로그를 로드하여 표시합니다.
        """
        self.error_view.clear()
        if not self.error_files:
            self.error_view.setPlainText("변환된 에러 로그 파일이 없습니다.")
            return

        time_range = timedelta(days=1)
        all_lines = []
        latest_time = None

        total_files_to_process = len(self.error_files)
        processed_files_count = 0

        for path in self.error_files:
            self.error_view.setPlainText(f"로그 로딩 및 분석 중... ({processed_files_count+1}/{total_files_to_process}): {os.path.basename(path)}")
            QApplication.processEvents()

            self._increment_progress()

            if not os.path.exists(path):
                print(f"경고: 변환된 파일 없음 (로딩 스킵): {path}")
                processed_files_count += 1
                continue

            name = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        if line.strip().lower().startswith("time pid tid"):
                            continue

                        parts = line.strip().split(None, 6)

                        if len(parts) < 7:
                            continue

                        timestamp_str = f"{parts[0]} {parts[1]}"
                        ts = self.try_parse_time(timestamp_str)
                        if not ts:
                            continue

                        lvl = parts[4].lower()
                        msg = parts[6].strip()

                        if latest_time is None or ts > latest_time:
                            latest_time = ts
                        all_lines.append((ts, lvl, msg, name))

            except Exception as e:
                print(f"오류: 파일 '{name}' 처리 중 예외 발생: {e}")
                QMessageBox.warning(self, "파일 처리 오류",
                                     f"'{name}' 파일을 읽는 중 오류가 발생했습니다: {e}\n"
                                     "해당 파일의 로그는 표시되지 않을 수 있습니다.")
            processed_files_count += 1

        if latest_time is None:
            self.error_view.setPlainText("주의: 로그 파일에서 유효한 시간 정보를 찾을 수 없습니다. 로그 형식을 확인해주세요.")
            self.progress_bar.setValue(self.total_steps)
            QApplication.processEvents()
            return

        cutoff = latest_time - time_range
        levels_to_display = ['error', 'warning']
        html_lines = []

        for ts, lvl, msg, name in sorted(all_lines, key=lambda x: x[0], reverse=True):
            if ts < cutoff or lvl not in levels_to_display:
                continue

            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red; font-weight:bold;">ERROR</span>',
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper())

            html_lines.append(
                f'<span style="font-family:Courier New; white-space:pre-wrap;">'
                f'{file_col:<30}{ts_str:<25}'
                f'{level_colored:<10}{msg}</span>'
            )

        self.progress_bar.setValue(self.total_steps)
        QApplication.processEvents()

        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("정보: 해당 시간 구간 (최근 24시간)에 오류 또는 경고 로그가 없습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("로그 뷰어")
            self.setGeometry(100, 100, 1000, 800)

            tab_widget = QTabWidget()
            self.setCentralWidget(tab_widget)

            error_log_tab = ErrorLogTab()
            tab_widget.addTab(error_log_tab, "오류/경고 로그")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
