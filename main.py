# main.py
# main.py

# PySide6의 QApplication 클래스를 임포트합니다.
# QApplication은 Qt 애플리케이션의 진입점으로, 이벤트 루프 및 전역 설정을 관리합니다.
from PySide6.QtWidgets import QApplication

# 프로젝트의 UI 모듈에서 MainWindow 클래스를 임포트합니다.
# MainWindow는 애플리케이션의 메인 윈도우(창) 역할을 수행합니다.
from main_window import MainWindow

# 시스템 관련 기능(ex: 명령줄 인수(sys.argv), 종료 코드 전달)을 사용하기 위한 모듈입니다.
import sys

# 이 파일이 직접 실행될 때에만 아래 코드를 실행하도록 합니다.
# 다른 모듈에서 import될 경우에는 실행되지 않습니다.
if __name__ == "__main__":
    # QApplication 객체를 생성합니다.
    # sys.argv를 전달하여 커맨드라인 인수를 Qt 애플리케이션에 넘깁니다.
    app = QApplication(sys.argv)

    # MainWindow 인스턴스를 생성하여 메인 창을 초기화합니다.
    window = MainWindow()

    # 생성된 메인 윈도우를 화면에 표시합니다.
    # show() 호출 전까지는 윈도우가 사용자에게 보이지 않습니다.
    window.show()

    # 이벤트 루프를 실행하고, 종료 시 반환되는 상태 코드를
    # sys.exit()를 통해 운영체제에 전달하며 프로그램을 정상 종료합니다.
    sys.exit(app.exec())
    
    
    import sys
import xml.etree.ElementTree as ET
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QFileDialog
)

class ParameterFinder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fixed ParameterID Finder")
        self.setGeometry(300, 300, 600, 400)

        layout = QVBoxLayout()

        # [1] 파일 선택
        file_layout = QHBoxLayout()
        self.file_button = QPushButton("XML 파일 선택")
        self.file_button.clicked.connect(self.select_file)
        self.file_label = QLabel("선택된 파일 없음")
        file_layout.addWidget(self.file_button)
        file_layout.addWidget(self.file_label)
        layout.addLayout(file_layout)

        # [2] 고정된 Parameter 이름 출력
        fixed_names = [
            "e-Column.IGP1", "e-Column.IGP2", "e-Column.IGP3",
            "e-Column.IGP4", "e-Column.IGP5", "e-Column.IGP6",
            "e-Column.IGP7", "e-Column.IGP8", "e-Column.IGP9",
            "e-Column.IGP10", "e-Column.IGP11"
        ]
        self.fixed_names = fixed_names  # 고정 이름 저장

        # [3] 결과 출력
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        # [4] 검색 버튼
        self.search_button = QPushButton("ParameterID 검색")
        self.search_button.clicked.connect(self.search_parameter_ids)
        layout.addWidget(self.search_button)

        self.setLayout(layout)
        self.xml_file = None

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "XML 파일 선택", "", "XML Files (*.xml)")
        if file_path:
            self.xml_file = file_path
            self.file_label.setText(file_path)

    def search_parameter_ids(self):
        if not self.xml_file:
            self.result_area.setText("⚠ XML 파일을 먼저 선택하세요.")
            return

        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            found_map = {name: None for name in self.fixed_names}

            for value_data in root.iter("ValueData"):
                pname = value_data.get("Parameter")
                pid = value_data.get("ParameterID")
                if pname in found_map and found_map[pname] is None:
                    found_map[pname] = pid

            result_lines = []
            for name in self.fixed_names:
                if found_map[name]:
                    result_lines.append(f"[{name}] → ParameterID: {found_map[name]}")
                else:
                    result_lines.append(f"[{name}] → ❌ 찾을 수 없음")

            self.result_area.setText("\n".join(result_lines))

        except Exception as e:
            self.result_area.setText(f"❌ XML 파싱 실패: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParameterFinder()
    window.show()
    sys.exit(app.exec_())