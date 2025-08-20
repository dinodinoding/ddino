# main.py

# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

# PySide6 라이브러리에서 QApplication 클래스를 가져옵니다.
# QApplication은 GUI 프로그램 전체를 관리하는 총괄 매니저와 같습니다.
# 프로그램에 대한 전반적인 설정, 이벤트 처리 등을 담당하며 모든 GUI 앱에 반드시 하나만 존재해야 합니다.
from PySide6.QtWidgets import QApplication

# 우리가 별도의 파일(main_window.py)에 만들어 둔 MainWindow 클래스를 가져옵니다.
# MainWindow는 우리가 설계할 프로그램의 메인 창(Window)에 대한 설계도입니다.
from main_window import MainWindow

# sys 모듈은 파이썬 인터프리터와 상호작용하는 기능을 제공합니다.
# 여기서는 프로그램 실행 시 전달된 명령줄 인수(sys.argv)를 사용하고,
# 프로그램 종료 시 상태 코드를 운영체제에 전달하기 위해 사용됩니다.
import sys

# ## 메인 코드 실행 부분 ##

# 이 스크립트 파일이 프로그램의 시작점으로서 직접 실행될 때만 아래의 코드를 실행하라는 의미입니다.
# 만약 다른 파이썬 파일에서 이 파일을 'import'해서 부품처럼 사용할 경우에는 아래 코드가 실행되지 않습니다.
if __name__ == "__main__":
    
    # 1. QApplication 객체 생성
    # GUI 애플리케이션의 총괄 매니저(app)를 만듭니다.
    # sys.argv는 프로그램 실행 시 사용된 명령줄 인수를 전달하는 역할을 합니다. (보통은 특별한 인수가 없음)
    app = QApplication(sys.argv)

    # 2. 메인 윈도우(MainWindow) 객체 생성
    # 위에서 가져온 MainWindow 설계도를 바탕으로 실제 창(window)을 만듭니다.
    window = MainWindow()

    # 3. 윈도우를 화면에 표시
    # 만들어진 창을 사용자에게 보여주는 명령어입니다. 이 코드가 실행되기 전까지는 창이 보이지 않습니다.
    window.show()

    # 4. 애플리케이션 실행 및 이벤트 루프 시작
    # app.exec()는 프로그램이 바로 종료되지 않고 사용자의 행동(클릭, 키보드 입력 등)을 계속 기다리게 만듭니다.
    # 이 '이벤트 루프'는 창의 X 버튼을 누르는 등 종료 신호가 올 때까지 무한 반복됩니다.
    # sys.exit()는 이벤트 루프가 종료될 때 반환된 값을 운영체제에 전달하며 프로그램을 안전하게 종료시킵니다.
    sys.exit(app.exec())  
    
