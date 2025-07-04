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
        self.setWindowTitle("ParameterID Finder (진단 포함)")
        self.setGeometry(300, 300, 700, 500)

        layout = QVBoxLayout()

        # 파일 선택
        file_layout = QHBoxLayout()
        self.file_button = QPushButton("XML 파일 선택")
        self.file_button.clicked.connect(self.select_file)
        self.file_label = QLabel("선택된 파일 없음")
        file_layout.addWidget(self.file_button)
        file_layout.addWidget(self.file_label)
        layout.addLayout(file_layout)

        # 결과 출력창
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        # 검색 버튼
        self.search_button = QPushButton("ParameterID 검색")
        self.search_button.clicked.connect(self.search_parameter_ids)
        layout.addWidget(self.search_button)

        self.setLayout(layout)
        self.xml_file = None

        # 고정된 Parameter 이름 목록
        self.fixed_names = [
            "I-Column.IGP1", "I-Column.IGP2", "I-Column.IGP3",
            "I-Column.IGP4", "I-Column.IGP5", "I-Column.IGP6",
            "I-Column.IGP7", "I-Column.IGP8", "I-Column.IGP9",
            "I-Column.IGP10", "I-Column.IGP11"
        ]

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "XML 파일 선택", "", "XML Files (*.xml)")
        if file_path:
            self.xml_file = file_path
            self.file_label.setText(file_path)
            print(f"[파일 선택됨] {file_path}")

    def is_valid_id(self, pid):
        return pid and pid.isdigit() and len(pid) == 4

    def search_parameter_ids(self):
        if not self.xml_file:
            self.result_area.setText("⚠ XML 파일을 먼저 선택하세요.")
            return

        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            found_map = {name: None for name in self.fixed_names}

            print("=== 전체 태그 구조 미리 보기 ===")
            for elem in root.iter():
                print(f"태그: {elem.tag} | 속성: {elem.attrib}")

            print("=== XML 내 Parameter 정보 탐색 ===")
            for elem in root.iter():
                # 네임스페이스 제거 처리
                tag_name = elem.tag.split('}')[-1]  # {namespace}ValueData → ValueData

                if tag_name.lower() == "valuedata":
                    pname = elem.get("Parameter", "").strip()
                    pid = elem.get("ParameterID", "").strip()
                    print(f"발견: Parameter = '{pname}', ID = '{pid}'")

                    if pname in found_map and found_map[pname] is None:
                        if self.is_valid_id(pid):
                            found_map[pname] = pid
                            print(f"✅ 매칭됨: [{pname}] → {pid}")
                        else:
                            print(f"⚠ ID 형식 오류: '{pid}'")

            result_lines = []
            for name in self.fixed_names:
                if found_map[name]:
                    result_lines.append(f"[{name}] → ParameterID: {found_map[name]}")
                else:
                    result_lines.append(f"[{name}] → ❌ 찾을 수 없음")

            self.result_area.setText("\n".join(result_lines))

        except Exception as e:
            self.result_area.setText(f"❌ XML 파싱 실패: {e}")
            print(f"[예외 발생] {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParameterFinder()
    window.show()
    sys.exit(app.exec_())