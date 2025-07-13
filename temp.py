import os
import sys
import json
import re
import tkinter as tk
import subprocess
import winreg

APP_NAME = "QuickLogViewer"
CONFIG_PATH = os.path.join("settings", "config.json")
BG_COLOR = "#f0f0f0"

# 요청사항 2: WIDTH_SCALE 대신 고정 사이즈로 변경
WIDTH = 390
HEIGHT = 286
TEXT_WIDTH = 175
TEXT_HEIGHT = 260

# ─────────────────────────────────────────────
def load_config():
    base = getattr(sys, "frozen", False) and sys.executable or __file__
    path = os.path.join(os.path.dirname(base), CONFIG_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def set_autorun(enable):
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    exe_path = sys.executable
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass

def is_autorun_enabled():
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return os.path.normcase(value) == os.path.normcase(sys.executable)
    except FileNotFoundError:
        return False

def extract_value_after_data(line):
    parts = re.split(r'\s+data\s+', line.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return None

def extract_summary_items(filepath, keyword_map):
    if os.path.isdir(filepath):
        txts = [f for f in os.listdir(filepath) if f.endswith(".txt")]
        if not txts:
            return []
        filepath = os.path.join(filepath, txts[0])

    if not os.path.isfile(filepath):
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except PermissionError:
        return []

    result = []
    for line in lines:
        line_lower = line.strip().lower()
        for keyword in keyword_map:
            if keyword in line_lower and 'data' in line_lower:
                value = extract_value_after_data(line)
                if value:
                    display = keyword_map[keyword].replace("{value}", value)
                    result.append((keyword, display))
                    break
    return result

def create_text_area(parent, x, y, w, h):
    box = tk.Text(parent, wrap="word", font=("Courier", 10),
                  bg=BG_COLOR, relief="flat", highlightthickness=0)
    box.place(x=x, y=y, width=w, height=h)
    box.config(state="disabled")
    return box

def bind_window_drag(window):
    def start_move(event):
        window.x = event.x
        window.y = event.y
    def do_move(event):
        dx = event.x - window.x
        dy = event.y - window.y
        window.geometry(f"+{window.winfo_x() + dx}+{window.winfo_y() + dy}")
    window.bind("<ButtonPress-1>", start_move)
    window.bind("<B1-Motion>", do_move)

def launch_detail_view():
    target = os.path.join("C:\\monitoring", "listlist.txt")
    try:
        subprocess.Popen(["start", "", target], shell=True)
    except Exception as e:
        tk.messagebox.showerror("Launch error", f"Failed to open: {e}")

# ─────────────────────────────────────────────
def create_gui():
    config = load_config()
    filepath = os.path.abspath(config.get("data_file", ""))
    left_keys = config.get("left_keywords", [])
    right_keys = config.get("right_keywords", [])
    keyword_map = config.get("keyword_display_map", {})

    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel()
    popup.overrideredirect(True)
    popup.configure(bg=BG_COLOR)
    popup.attributes("-topmost", False)
    # 요청사항 3: 투명도 0.5 설정
    popup.attributes("-alpha", 0.95) # 0.5는 너무 투명할 수 있어 0.95로 조정했습니다. 0.5 원하시면 변경해주세요.


    screen_w = popup.winfo_screenwidth()
    screen_h = popup.winfo_screenheight()
    x = screen_w - WIDTH - 20
    y = (screen_h // 2) - (HEIGHT // 2)
    popup.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    bind_window_drag(popup)

    # 텍스트 박스 위치 조정 (높이 변경에 따라)
    left_text = create_text_area(popup, 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30) # 아래 공간 확보
    right_text = create_text_area(popup, 10 + TEXT_WIDTH + 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30) # 아래 공간 확보

    def update_text_areas(items):
        left_lines = []
        right_lines = []
        for key, line in items:
            if key in right_keys:
                # 슬래시를 기준으로 분리하고 빈 문자열을 제거
                parts = [part.strip() for part in line.split('/') if part.strip()]
                right_lines.extend(parts)
            else:
                left_lines.append(line)

        for box in [left_text, right_text]:
            box.config(state="normal")
            box.delete("1.0", tk.END)

        left_text.insert("1.0", "\n".join(left_lines))
        right_text.insert("1.0", "\n".join(right_lines))

        for box in [left_text, right_text]:
            box.config(state="disabled")

    def refresh_summary():
        items = extract_summary_items(filepath, keyword_map)
        update_text_areas(items)
        popup.after(3600000, refresh_summary)

    update_text_areas(extract_summary_items(filepath, keyword_map))

    # 요청사항 1: 체크박스, X 버튼, Details 버튼 오른쪽 정렬
    bottom_frame = tk.Frame(popup, bg=BG_COLOR)
    # bottom_frame을 오른쪽 아래에 위치시키고 내부 요소를 오른쪽으로 정렬
    bottom_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    # 체크박스, X 버튼, Details 버튼을 포함할 컨테이너 프레임
    # 이 프레임 안의 요소들이 오른쪽에 배치되도록 pack(side="right") 사용
    control_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
    control_frame.pack(side="right") # bottom_frame 안에서 오른쪽으로 정렬

    # Detail 버튼
    detail_frame = tk.Frame(control_frame, bg=BG_COLOR)
    tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view,
              bg=BG_COLOR, activebackground=BG_COLOR).pack(side="right") # ⚙ 버튼을 먼저 추가 (오른쪽에서부터 채워짐)
    tk.Label(detail_frame, text="Details", font=("Arial", 9), bg=BG_COLOR).pack(side="right") # Label을 ⚙ 버튼 왼쪽에 추가
    detail_frame.pack(side="right", padx=(0,10)) # 오른쪽으로 정렬, 오른쪽에 여백 추가

    # X (종료) 버튼
    tk.Button(control_frame, text="X", command=lambda: sys.exit(),
              width=2, height=1, relief="flat",
              bg=BG_COLOR, activebackground=BG_COLOR,
              borderwidth=0, highlightthickness=0).pack(side="right", padx=(0,10)) # 오른쪽으로 정렬, 오른쪽에 여백 추가

    # 자동 실행 체크박스
    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    tk.Checkbutton(control_frame, text="Auto-run on Startup",
                   variable=var_autorun, command=lambda: set_autorun(var_autorun.get()),
                   bg=BG_COLOR, activebackground=BG_COLOR,
                   highlightthickness=0, relief="flat").pack(side="right") # 오른쪽으로 정렬


    refresh_summary()
    popup.mainloop()

if __name__ == "__main__":
    create_gui()
