import os
import sys
import logging
import traceback
from datetime import datetime

from PySide6.QtWidgets import QMainWindow, QTabWidget

# 탭 클래스들 import
from text_view_tab import TextViewTab
from graph_tab import GraphTab
from error_log_tab import ErrorLogTab
from registry_tab import RegistryTabGroup

# ===== [1] 로그 디렉터리 및 파일 설정 ===== #
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# --- 기존 basicConfig 및 LoggerWriter 대체 시작 ---

# 1. 로거 인스턴스 가져오기 (루트 로거)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG) # 모든 로그를 기록하도록 DEBUG 레벨로 설정

# 2. 기존 핸들러 제거 (중복 로깅 방지)
#    PyInstaller로 실행 시 혹은 다중 실행 시 핸들러가 중복으로 추가될 수 있습니다.
if logger.hasHandlers():
    logger.handlers.clear()

# 3. 포매터 생성
#    파일과 콘솔 로그의 형식을 통일합니다.
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
)

# 4. 파일 핸들러 설정 (encoding 명시)
#    Python 3.8에서 파일에 한글을 정확히 기록하기 위해 encoding='utf-8' 명시
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 5. 콘솔 핸들러 설정 (encoding 명시)
#    sys.stdout에 직접 연결하는 LoggerWriter 대신, 표준 StreamHandler 사용
#    stream=sys.stdout으로 콘솔 출력을 명시하고, encoding도 명시
#    errors='replace'는 인코딩 실패 시 해당 문자를 ? 등으로 대체하여 에러가 나지 않게 함
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO) # 콘솔에는 INFO 레벨 이상만 출력 (선택 사항)
logger.addHandler(console_handler)

# --- 기존 basicConfig 및 LoggerWriter 대체 종료 ---


# 6. 표준 출력/오류 스트림 리다이렉션 (로깅 시스템으로 보내기)
#    sys.stdout과 sys.stderr를 로깅 시스템으로 리다이렉션합니다.
#    이전에 사용했던 LoggerWriter와 유사한 기능이지만,
#    로깅 모듈의 StreamHandler를 이미 사용하고 있으므로,
#    여기서는 print()나 예외 메시지 등을 로깅 시스템으로 보내는 역할만 합니다.
class RedirectStreamToLogger:
    def __init__(self, logger_func):
        self.logger_func = logger_func
        self.buffer = ''

    def write(self, message):
        self.buffer += message
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line.strip(): # 비어있지 않은 라인만 로깅
                self.logger_func(line.strip())

    def flush(self):
        # 버퍼에 남아있는 내용이 있다면 flush 시점에 로깅
        if self.buffer.strip():
            self.logger_func(self.buffer.strip())
            self.buffer = ''

sys.stdout = RedirectStreamToLogger(logging.info)
sys.stderr = RedirectStreamToLogger(logging.error)


# 7. 예외 자동 기록 (기존과 동일)
def exception_hook(exctype, value, tb):
    # 로깅 시스템으로 예외 정보 기록
    logging.critical("치명적인 예외 발생! 프로그램 종료", exc_info=(exctype, value, tb))
    # 콘솔에도 출력하여 개발자가 즉시 확인 가능하도록 함
    traceback.print_exception(exctype, value, tb)

sys.excepthook = exception_hook

# ===== [2] MainWindow 정의 ===== #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # logging.info 대신 logger.info 사용 (일관성 유지)
        logger.info("MainWindow 초기화 시작")
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
            logger.info(f"{title} 탭 생성 시도")
            try:
                tab = TabClass()
                self.tabs.addTab(tab, title)
                logger.info(f"{title} 탭 생성 완료")
            except Exception as e:
                logger.error(f"[탭 생성 실패] {title}: {e}")
                traceback.print_exc()

        logger.info("MainWindow 초기화 완료")

    def closeEvent(self, event):
        try:
            # self.registry_view는 RegistryTabGroup 인스턴스가 탭에 추가될 때
            # MainWindow의 속성으로 저장되지 않으므로 직접 접근이 어려울 수 있습니다.
            # RegistryTabGroup 내부에 save_settings 로직이 있다면 해당 탭 클래스에서 처리하는 것이 좋습니다.
            # 여기서는 예시로 남겨두지만, 실제 구현에 따라 수정이 필요합니다.
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                if isinstance(widget, RegistryTabGroup):
                    widget.save_settings()
                    logger.info("레지스트리 설정 저장 완료")
                    break
        except Exception as e:
            logger.error(f"[종료 오류] 레지스트리 저장 중 오류: {e}")
            traceback.print_exc()
        super().closeEvent(event)

