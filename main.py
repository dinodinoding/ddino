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