# utils/config_loader.py

import json
import os
import sys # sys 모듈 임포트 추가

##############수정################
# 기능: 프로그램이 .exe로 실행되었는지, 아니면 .py 스크립트로 실행되었는지 확인하여
#      상대 경로의 기준이 되는 '루트 폴더' 경로를 동적으로 결정합니다.
# 이유: 이 코드는 PyInstaller로 만든 실행 파일이 데이터 파일(config.json, data.txt 등)의
#      경로를 안정적으로 찾게 해주는 표준적인 해결책입니다.

def get_base_path():
    """ 현재 실행 환경에 맞는 베이스 경로를 반환합니다. """
    # PyInstaller로 만들어진 .exe 파일로 실행될 경우
    if getattr(sys, 'frozen', False):
        # .exe 파일이 위치한 폴더를 베이스 경로로 사용합니다.
        # sys._MEIPASS는 실행 시 생성되는 임시 폴더의 경로입니다.
        return sys._MEIPASS
    else:
        # 일반 .py 스크립트로 실행될 경우
        # 이 파일(__file__)이 있는 폴더의 상위 폴더를 베이스 경로로 사용합니다.
        # 즉, 'project6' 폴더가 베이스 경로가 됩니다.
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# 이제 모든 경로는 이 베이스 경로를 기준으로 계산됩니다.
BASE_PATH = get_base_path()
CONFIG_PATH = os.path.join(BASE_PATH, 'settings', 'config.json')

# 기본 설정값의 경로도 BASE_PATH를 사용하도록 변경하면 좋습니다 (선택 사항)
DEFAULT_CONFIG = {
    "data_file": os.path.join(BASE_PATH, "resources", "data.txt"),
    "batch_file": os.path.join(BASE_PATH, "resources", "graph.bat"),
    "error_logs": [
        os.path.join(BASE_PATH, "resources", "errorlog.txt")
    ],
    "xml_log": os.path.join(BASE_PATH, "resources", "ggvaclog.xml")
}
############수정 끝#################


def load_config():
    """
    settings/config.json 파일을 읽어 설정을 반환합니다.
    """
    if not os.path.exists(CONFIG_PATH):
        print(f"[⚠️ 설정 파일 없음] '{CONFIG_PATH}' 경로에 기본 설정으로 config.json을 생성합니다.")
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            # (진단 코드는 이제 필요 없으므로 제거해도 됩니다)
            return config_data
    except Exception as e:
        print(f"[‼️ 설정 로딩 실패] '{CONFIG_PATH}' 파일에 오류가 있습니다: {e}")
        print("[‼️ 기본값으로 프로그램을 실행합니다.]")
        return DEFAULT_CONFIG

# (캐싱 코드는 그대로 둡니다)
_config_cache = None

def get_config():
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


