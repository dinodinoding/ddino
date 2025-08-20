# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

import os  # 운영체제 관련 기능 (예: 파일 경로 다루기)
import sys  # 파이썬 인터프리터 관련 기능 (예: .exe로 실행 중인지 확인)
import json  # JSON 형식의 설정 파일을 읽고 쓰기 위한 도구
import re  # 정규 표현식을 사용하여 텍스트에서 특정 패턴을 찾기 위한 도구
import tkinter as tk  # 파이썬의 표준 GUI 라이브러리. 창, 버튼 등을 만듦
import subprocess  # 다른 외부 프로그램을 실행시키기 위한 도구
import winreg  # Windows 레지스트리를 제어하기 위한 도구 (자동 시작 기능에 사용)

# ## 전역 상수 및 변수 설정 ##

# 프로그램의 이름 (레지스트리 등록 시 사용)
APP_NAME = "QuickLogViewer"
# 설정 파일의 상대 경로
CONFIG_PATH = os.path.join("settings", "config.json")
# GUI의 기본 배경색
BG_COLOR = "#f0f0f0"

# 창의 크기 및 텍스트 영역 크기
WIDTH = 390
HEIGHT = 300
TEXT_WIDTH = 180
TEXT_HEIGHT = 270

# 프로그램 전체에서 사용할 설정 정보를 담을 딕셔너리 변수
_config = {}

# ## 핵심 기능 함수 정의 ##

def load_config():
    """settings/config.json 파일을 읽어 전역 변수 _config에 저장하는 함수"""
    global _config
    # .py 파일로 실행하든 .exe 파일로 실행하든 올바른 기준 경로를 찾음
    base = getattr(sys, "frozen", False) and sys.executable or __file__
    path = os.path.join(os.path.dirname(base), CONFIG_PATH)
    
    # 설정 파일이 없으면 빈 딕셔셔너리로 초기화하고 종료
    if not os.path.exists(path):
        _config = {}
        return _config
        
    # 설정 파일이 있으면 파일을 열어 JSON 내용을 읽고 _config에 저장
    with open(path, "r", encoding="utf-8") as f:
        _config = json.load(f)
        return _config

def set_autorun(enable):
    """Windows 시작 시 프로그램이 자동 실행되도록 레지스트리에 등록하거나 해제하는 함수"""
    # 자동 실행 프로그램 목록이 저장된 레지스트리 경로
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    # 현재 실행 중인 이 프로그램(.exe)의 전체 경로
    exe_path = sys.executable
    
    # 레지스트리 키를 열어서 작업 (KEY_ALL_ACCESS는 읽고 쓸 수 있는 모든 권한을 의미)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS) as key:
        if enable: # 자동 실행을 활성화하는 경우
            # 'APP_NAME'이라는 이름으로 프로그램의 경로를 레지스트리에 저장
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else: # 자동 실행을 비활성화하는 경우
            try:
                # 'APP_NAME'이라는 이름의 값을 레지스트리에서 삭제
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                # 만약 삭제하려는 값이 이미 없어서 오류가 나도 조용히 넘어감
                pass

def is_autorun_enabled():
    """현재 자동 실행이 설정되어 있는지 레지스트리를 확인하는 함수"""
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        # 레지스트리 키를 읽기 전용으로 열기
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            # 'APP_NAME'으로 저장된 값을 읽어옴
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            # 레지스트리에 저장된 경로와 현재 실행 파일의 경로가 같은지 확인 (대소문자 무시)
            return os.path.normcase(value) == os.path.normcase(sys.executable)
    except FileNotFoundError:
        # 값을 찾지 못하면 (등록되지 않았으면) False를 반환
        return False

def extract_value_after_data(line):
    """' data '라는 문자열을 기준으로 뒷부분의 값을 추출하는 함수"""
    # ' data '를 기준으로 줄을 최대 1번만 나눔 -> [앞부분, 뒷부분]
    parts = re.split(r'\s+data\s+', line.strip(), maxsplit=1)
    if len(parts) == 2: # 정확히 두 부분으로 나뉘었다면
        return parts[1].strip() # 뒷부분의 값을 반환
    return None

def extract_summary_items(filepath, keyword_map):
    """지정된 파일에서 키워드에 해당하는 줄을 찾아 요약 정보를 추출하는 함수"""
    # 만약 주어진 경로가 폴더이면, 그 안의 첫 번째 .txt 파일을 대상으로 함
    if os.path.isdir(filepath):
        txts = [f for f in os.listdir(filepath) if f.endswith(".txt")]
        if not txts: return [] # .txt 파일이 없으면 빈 리스트 반환
        filepath = os.path.join(filepath, txts[0])

    if not os.path.isfile(filepath): return [] # 파일이 아니면 빈 리스트 반환

    try:
        # 파일을 읽되, 인코딩 오류는 무시하고, 권한이 없으면 빈 리스트 반환
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except PermissionError:
        return []

    result = []
    # 파일의 각 줄을 순회
    for line in lines:
        line_lower = line.strip().lower() # 비교를 위해 줄을 소문자로 변환
        # 설정 파일에 정의된 키워드들을 순회
        for keyword in keyword_map:
            # 현재 줄에 키워드와 'data'가 모두 포함되어 있다면
            if keyword in line_lower and 'data' in line_lower:
                value = extract_value_after_data(line) # 실제 값을 추출
                if value:
                    # 설정된 표시 형식에 따라 최종 출력 문자열을 만듦
                    display = keyword_map[keyword].replace("{value}", value)
                    result.append((keyword, display)) # (원본키워드, 최종문자열) 쌍으로 결과에 추가
                    break # 이 줄에서는 원하는 것을 찾았으므로 다음 줄로 넘어감
    return result

def create_text_area(parent, x, y, w, h):
    """화면에 텍스트를 표시할 상자를 생성하고 배치하는 함수"""
    # tk.Text: 여러 줄의 텍스트를 표시할 수 있는 위젯
    box = tk.Text(parent, wrap="word", font=("Courier", 10),
                  bg=BG_COLOR, relief="flat", highlightthickness=0)
    # place: 절대 좌표(x, y)와 크기(w, h)를 이용해 위젯을 배치
    box.place(x=x, y=y, width=w, height=h)
    box.config(state="disabled") # 사용자가 직접 수정할 수 없도록 비활성화
    return box

def bind_window_drag(window):
    """제목 표시줄이 없는 창을 마우스로 드래그할 수 있게 만드는 함수"""
    # 마우스 왼쪽 버튼을 눌렀을 때 실행될 함수
    def start_move(event):
        # 창 내에서 마우스 클릭이 시작된 x, y 좌표를 기록
        window.x = event.x
        window.y = event.y

    # 마우스 왼쪽 버튼을 누른 채로 움직일 때 실행될 함수
    def do_move(event):
        # 마우스가 움직인 거리(dx, dy)를 계산
        dx = event.x - window.x
        dy = event.y - window.y

        # 현재 창의 위치에 움직인 거리를 더해 새 위치를 계산
        new_x = window.winfo_x() + dx
        new_y = window.winfo_y() + dy

        # 창이 특정 모니터 경계를 벗어나지 않도록 제한
        MONITOR_X_MIN = 1920
        MONITOR_X_MAX = 3840
        MONITOR_Y_MIN = 0
        MONITOR_Y_MAX = 1080
        new_x = max(MONITOR_X_MIN, min(new_x, MONITOR_X_MAX - WIDTH))
        new_y = max(MONITOR_Y_MIN, min(new_y, MONITOR_Y_MAX - HEIGHT))

        # 계산된 새 위치로 창을 이동
        window.geometry(f"+{new_x}+{new_y}")

    # 마우스 이벤트와 위에서 만든 함수들을 연결
    window.bind("<ButtonPress-1>", start_move) # 마우스 왼쪽 버튼 누름
    window.bind("<B1-Motion>", do_move)      # 마우스 왼쪽 버튼 누른 채로 이동

def launch_detail_view():
    """상세 보기 파일이나 폴더를 여는 함수"""
    target = _config.get("detail_file_path", "")
    if not target:
        tk.messagebox.showerror("경로 오류", "config.json에 'detail_file_path'가 설정되지 않았습니다.")
        return
    if not os.path.exists(target):
        tk.messagebox.showerror("파일 없음", f"지정된 경로의 파일이나 폴더가 존재하지 않습니다:\n{target}")
        return
    try:
        # Windows의 'start' 명령어를 사용하여 파일을 기본 연결 프로그램으로 염
        subprocess.Popen(["start", "", target], shell=True)
    except Exception as e:
        tk.messagebox.showerror("실행 오류", f"파일을 열 수 없습니다:\n{e}")

def create_gui():
    """메인 GUI를 생성하고 실행하는 함수"""
    load_config() # 설정 파일 로드
    filepath = os.path.abspath(_config.get("data_file", ""))
    # 설정에서 왼쪽/오른쪽 열에 표시할 키워드 목록을 가져옴
    left_keys = _config.get("left_keywords", [])
    right_keys = _config.get("right_keywords", [])
    keyword_map = _config.get("keyword_display_map", {})

    root = tk.Tk()
    root.withdraw() # 기본으로 생성되는 메인 창은 숨김

    # 우리가 사용할 커스텀 창을 Toplevel로 생성
    popup = tk.Toplevel()
    popup.overrideredirect(True) # 제목 표시줄, 테두리 등을 모두 제거
    popup.configure(bg=BG_COLOR)
    popup.attributes("-topmost", False) # 항상 위 속성은 해제
    popup.attributes("-alpha", 0.5) # 창을 50% 투명하게 만듦
    popup.lower() # 창을 다른 창들 아래로 보냄

    # 창 위치를 오른쪽 모니터 끝으로 고정
    x = 3450
    y = 390
    popup.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    bind_window_drag(popup) # 창 드래그 기능 연결

    # 왼쪽과 오른쪽 텍스트 영역 생성
    left_text = create_text_area(popup, 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)
    right_text = create_text_area(popup, 10 + TEXT_WIDTH + 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)

    def update_text_areas(items):
        """추출된 요약 정보로 텍스트 영역을 업데이트하는 함수"""
        left_lines = []
        right_lines = []
        # 추출된 아이템들을 키워드에 따라 왼쪽/오른쪽으로 분류
        for key, line in items:
            if key in right_keys:
                # '/'를 기준으로 나누어 여러 줄로 만듦
                parts = [part.strip() for part in line.split('/') if part.strip()]
                right_lines.extend(parts)
            else:
                left_lines.append(line)

        # 텍스트를 넣기 위해 잠시 활성화
        for box in [left_text, right_text]: box.config(state="normal")
        left_text.delete("1.0", tk.END) # 기존 내용 삭제
        right_text.delete("1.0", tk.END)

        left_text.insert("1.0", "\n".join(left_lines)) # 새 내용 추가
        right_text.insert("1.0", "\n".join(right_lines))

        # 다시 비활성화
        for box in [left_text, right_text]: box.config(state="disabled")

    def refresh_summary():
        """파일을 다시 읽어 요약 정보를 새로고침하는 함수"""
        items = extract_summary_items(filepath, keyword_map)
        update_text_areas(items)
        # 3600000 밀리초(1시간) 후에 이 함수를 다시 실행하도록 예약
        popup.after(3600000, refresh_summary)

    # 처음 실행 시 요약 정보 표시
    update_text_areas(extract_summary_items(filepath, keyword_map))

    # --- 하단 컨트롤 버튼들 생성 ---
    # 버튼들을 담을 프레임(컨테이너) 생성 및 배치
    bottom_frame = tk.Frame(popup, bg=BG_COLOR)
    bottom_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    control_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
    control_frame.pack(side="right")

    # Details 버튼과 라벨
    detail_frame = tk.Frame(control_frame, bg=BG_COLOR)
    tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view,
              bg=BG_COLOR, activebackground=BG_COLOR).pack(side="right")
    tk.Label(detail_frame, text="Details", font=("Arial", 9), bg=BG_COLOR).pack(side="right")
    detail_frame.pack(side="right", padx=(0,10))

    # 종료(X) 버튼
    tk.Button(control_frame, text="X", command=lambda: sys.exit(),
              width=2, height=1, relief="flat",
              bg=BG_COLOR, activebackground=BG_COLOR,
              borderwidth=0, highlightthickness=0).pack(side="right", padx=(0,10))

    # 자동 실행 체크박스
    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    tk.Checkbutton(control_frame, text="Auto-run on Startup",
                   variable=var_autorun, command=lambda: set_autorun(var_autorun.get()),
                   bg=BG_COLOR, activebackground=BG_COLOR,
                   highlightthickness=0, relief="flat").pack(side="right")

    refresh_summary() # 데이터 새로고침 함수 최초 실행
    popup.mainloop() # GUI 이벤트 루프 시작 (창이 닫히기 전까지 여기서 대기)

# 이 스크립트가 직접 실행되었을 때만 create_gui() 함수를 호출
if __name__ == "__main__":
    create_gui()
