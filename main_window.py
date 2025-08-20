# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

import os          # 운영체제 관련 기능 (예: 파일 경로 다루기)
import sys         # 파이썬 인터프리터 관련 기능 (예: 프로그램 종료, 표준 출력/에러 제어)
import logging     # 프로그램의 동작 상태를 파일에 기록(로깅)하기 위한 도구
import traceback   # 예외(오류) 발생 시 상세한 정보를 얻기 위한 도구
from datetime import datetime  # 현재 날짜와 시간을 다루기 위한 도구

# PySide2 라이브러리에서 GUI를 구성하는 데 필요한 메인 윈도우와 탭 위젯을 가져옵니다.
from PySide2.QtWidgets import QMainWindow, QTabWidget

# ## 다른 파일에 정의된 탭 UI 클래스들을 가져오기 ##
# 각 파일은 프로그램의 한 페이지(탭)에 해당하는 UI와 기능을 담고 있습니다.
from text_view_tab import TextViewTab
from graph_tab import GraphTab
from error_log_tab import ErrorLogTab
# 이전 예제에서 분리했던 레지스트리 관리 탭 그룹 클래스를 가져옵니다.
from registry_tab import RegistryTabGroup

# ===== [1] 프로그램 동작 기록(로깅) 설정 ===== #
# 이 부분은 프로그램이 실행되는 동안 발생하는 모든 일(정보, 경고, 오류)을
# 파일에 자동으로 기록하여, 문제가 발생했을 때 원인을 쉽게 찾을 수 있도록 도와줍니다.

# --- 로그 파일이 저장될 위치와 파일 이름 설정 ---
# os.path.expanduser("~"): 현재 로그인된 사용자의 홈 폴더 경로를 가져옵니다 (예: C:\Users\사용자이름).
home_dir = os.path.expanduser("~")
# 홈 폴더 아래에 'my_logs'라는 폴더 경로를 만듭니다.
LOG_DIR = os.path.join(home_dir, "my_logs")
# os.makedirs: 해당 폴더가 없으면 새로 생성합니다. exist_ok=True는 폴더가 이미 있어도 오류를 내지 않습니다.
os.makedirs(LOG_DIR, exist_ok=True)

# 로그 파일의 이름을 'run_년월일_시간.log' 형식으로 고유하게 만듭니다.
# 이렇게 하면 프로그램을 실행할 때마다 새로운 로그 파일이 생성됩니다.
log_filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

try:
    # logging.basicConfig: 로깅 시스템의 기본 설정을 구성합니다.
    logging.basicConfig(
        filename=log_filename,      # 로그를 저장할 파일 이름
        filemode="w",               # 파일 쓰기 모드 ('w'는 덮어쓰기)
        level=logging.DEBUG,        # 기록할 로그의 최소 수준 (DEBUG가 가장 상세함)
        format="%(asctime)s [%(levelname)s] %(message)s" # 로그 메시지 형식 지정
    )
except Exception as e:
    # 로깅 설정 자체에 실패할 경우를 대비한 예외 처리
    print("로깅 설정 실패:", e)

# --- print() 문과 오류 메시지를 로그 파일에도 기록하도록 설정 ---
# LoggerWriter 클래스는 print()나 오류 메시지를 가로채서 logging 시스템으로 보내는 역할을 합니다.
# 이렇게 하면 GUI 프로그램에서 보이지 않는 출력이나 오류도 모두 로그 파일에 남길 수 있습니다.
class LoggerWriter:
    def __init__(self, stream, level):
        self.stream = stream # 원래의 출력 스트림 (예: sys.stdout)
        self.level = level   # 사용할 로깅 수준 (예: logging.info)

    def write(self, message):
        # 메시지를 가로채서 logging을 통해 기록
        message = message.strip()
        if message:
            try:
                self.level(message)
            except Exception:
                pass # 로깅 중 오류가 나도 무시
        # 원래의 출력 스트림에도 메시지를 전달 (콘솔이 있는 경우)
        if self.stream:
            try:
                self.stream.write(message + "\n")
            except Exception:
                pass

    def flush(self):
        # 스트림의 flush 메서드를 호출
        if self.stream:
            try:
                self.stream.flush()
            except Exception:
                pass

# sys.stdout (기본 출력)과 sys.stderr (기본 에러)를 우리가 만든 LoggerWriter로 교체합니다.
# 이제부터 print()는 logging.info로, 오류는 logging.error로 자동 기록됩니다.
sys.stdout = LoggerWriter(getattr(sys, 'stdout', None), logging.info)
sys.stderr = LoggerWriter(getattr(sys, 'stderr', None), logging.error)

# --- 처리되지 않은 모든 예외(오류)를 자동으로 기록하는 '안전망' 설정 ---
def exception_hook(exctype, value, tb):
    # 프로그램이 예기치 않게 종료될 만한 심각한 오류가 발생했을 때,
    # 그 오류 정보를 자동으로 로그 파일에 기록하는 함수입니다.
    logging.error("예외 발생", exc_info=(exctype, value, tb))
    traceback.print_exception(exctype, value, tb) # 콘솔에도 오류 정보 출력

# sys.excepthook에 우리가 만든 함수를 등록하여 안전망을 활성화합니다.
sys.excepthook = exception_hook

# ===== [2] 메인 윈도우(MainWindow) 정의 ===== #
# 이 클래스는 애플리케이션의 전체 창을 만들고, 여러 탭들을 담는 역할을 합니다.
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        logging.info("MainWindow 초기화 시작") # 프로그램 시작을 로그에 기록
        self.setWindowTitle("Multi-Tool Application") # 창 제목 설정
        self.setGeometry(100, 100, 1400, 800) # 창의 시작 위치와 크기 설정

        # QTabWidget: 여러 탭 페이지를 담을 수 있는 위젯
        self.tabs = QTabWidget()
        # 이 탭 위젯을 메인 윈도우의 중앙 위젯으로 설정합니다.
        self.setCentralWidget(self.tabs)

        # --- 탭 목록 정의 및 생성 ---
        # 추가할 탭의 클래스와 탭의 제목을 튜플로 묶어 리스트로 관리합니다.
        # 이렇게 하면 탭을 추가하거나 순서를 바꾸기가 매우 편리합니다.
        tab_list = [
            (RegistryTabGroup, "Registry Editor"),
            (TextViewTab,      "Text Viewer"),
            (GraphTab,         "Graph Log"),
            (ErrorLogTab,      "Error Logs"),
        ]

        # 리스트를 순회하며 각 탭을 동적으로 생성하고 추가합니다.
        for TabClass, title in tab_list:
            logging.info(f"{title} 탭 생성 시도")
            try:
                # TabClass()를 통해 해당 탭 클래스의 인스턴스(실제 위젯)를 생성
                tab = TabClass()
                # 생성된 탭 위젯을 메인 탭 위젯에 추가
                self.tabs.addTab(tab, title)
                logging.info(f"{title} 탭 생성 완료")
            except Exception as e:
                # 만약 특정 탭을 생성하는 도중 오류가 발생하더라도
                # 프로그램 전체가 멈추지 않고, 오류를 로그에 기록한 후 계속 진행합니다.
                logging.error(f"[탭 생성 실패] {title}: {e}")
                traceback.print_exc() # 오류의 상세 내용을 로그에 기록

        logging.info("MainWindow 초기화 완료")

    def closeEvent(self, event):
        """창이 닫힐 때 (예: X 버튼 클릭) 자동으로 호출되는 특별한 함수"""
        # 창이 닫히기 직전에 수행해야 할 마무리 작업을 여기에 작성합니다.
        try:
            # hasattr는 객체가 특정 속성(변수나 메서드)을 가지고 있는지 확인하는 함수입니다.
            # 'registry_view'라는 이름의 탭이 존재하는지 확인하고,
            # 있다면 해당 탭의 save_settings 메서드를 호출하여 설정을 저장합니다.
            # (주: 현재 코드에는 self.registry_view가 없으므로 이 부분은 동작하지 않지만,
            # 나중에 추가될 것을 대비한 코드로 보입니다.)
            if hasattr(self, 'registry_view'):
                self.registry_view.save_settings()
                logging.info("레지스트리 설정 저장 완료")
        except Exception as e:
            # 설정 저장 중 오류가 발생하더라도 프로그램 종료는 계속되어야 하므로
            # 오류를 로그에만 기록하고 넘어갑니다.
            logging.error(f"[종료 오류] 레지스트리 저장 중 오류: {e}")
            traceback.print_exc()
        
        # super().closeEvent(event)를 호출하여 부모 클래스의 원래 닫기 기능을 마저 수행합니다.
        # 이 줄이 없으면 창이 실제로 닫히지 않습니다.
        super().closeEvent(event)
