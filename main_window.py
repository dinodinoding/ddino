import os
import sys
import logging
import traceback
from datetime import datetime

from PySide2.QtWidgets import QMainWindow, QTabWidget

# 탭 클래스들 import
from text_view_tab import TextViewTab
from graph_tab import GraphTab
from error_log_tab import ErrorLogTab
from registry_tab import RegistryTabGroup

# ===== [1] 로그 디렉터리 및 파일 설정 ===== #
# 사용자 홈 디렉터리 하위에 로그 폴더 생성 (Windows 7 대응)
home_dir = os.path.expanduser("~")
LOG_DIR = os.path.join(home_dir, "my_logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

try:
    logging.basicConfig(
        filename=log_filename,
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
except Exception as e:
    print("로깅 설정 실패:", e)

# 콘솔에도 출력하도록 설정 (console이 없을 수도 있음)
class LoggerWriter:
    def __init__(self, stream, level):
        self.stream = stream
        self.level = level

    def write(self, message):
        message = message.strip()
        if message and callable(self.level):  # 함수 여부 확인
            try:
                self.level(message)
            except Exception:
                pass
        if self.stream:
            try:
                self.stream.write(message + "\n")
            except Exception:
                pass

    def flush(self):
        if self.stream:
            try:
                self.stream.flush()
            except Exception:
                pass

sys.stdout = LoggerWriter(getattr(sys, 'stdout', None), logging.info)
sys.stderr = LoggerWriter(getattr(sys, 'stderr', None), logging.error)

# 예외 자동 기록
def exception_hook(exctype, value, tb):
    logging.error("예외 발생", exc_info=(exctype, value, tb))
    traceback.print_exception(exctype, value, tb)

sys.excepthook = exception_hook

# ===== [2] MainWindow 정의 ===== #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        logging.info("MainWindow 초기화 시작")
        self.setWindowTitle("Multi-Tool Application")
        self.setGeometry(100, 100, 1400, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 탭 정의 및 생성 순서
        tab_list = [
            (RegistryTabGroup, "Registry Editor"),
            (TextViewTab,      "Text Viewer"),
            (GraphTab,         "Graph Log"),
            (ErrorLogTab,      "Error Logs"),
        ]

        for TabClass, title in tab_list:
            logging.info(f"{title} 탭 생성 시도")
            try:
                tab = TabClass()
                self.tabs.addTab(tab, title)
                logging.info(f"{title} 탭 생성 완료")
            except Exception as e:
                logging.error(f"[탭 생성 실패] {title}: {e}")
                traceback.print_exc()

        logging.info("MainWindow 초기화 완료")

    def closeEvent(self, event):
        try:
            if hasattr(self, 'registry_view'):
                self.registry_view.save_settings()
                logging.info("레지스트리 설정 저장 완료")
        except Exception as e:
            logging.error(f"[종료 오류] 레지스트리 저장 중 오류: {e}")
            traceback.print_exc()
        super().closeEvent(event)