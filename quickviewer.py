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

WIDTH = 390
HEIGHT = 300
TEXT_WIDTH = 175
TEXT_HEIGHT = 270

_config = {}

def load_config():
    global _config
    base = getattr(sys, "frozen", False) and sys.executable or __file__
    path = os.path.join(os.path.dirname(base), CONFIG_PATH)
    if not os.path.exists(path):
        _config = {}
        return _config
    with open(path, "r", encoding="utf-8") as f:
        _config = json.load(f)
        return _config

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

        new_x = window.winfo_x() + dx
        new_y = window.winfo_y() + dy

        # 오른쪽 모니터의 경계 제한 (1920~3840), 1080 높이 기준
        MONITOR_X_MIN = 1920
        MONITOR_X_MAX = 3840
        MONITOR_Y_MIN = 0
        MONITOR_Y_MAX = 1080

        new_x = max(MONITOR_X_MIN, min(new_x, MONITOR_X_MAX - WIDTH))
        new_y = max(MONITOR_Y_MIN, min(new_y, MONITOR_Y_MAX - HEIGHT))

        window.geometry(f"+{new_x}+{new_y}")

    window.bind("<ButtonPress-1>", start_move)
    window.bind("<B1-Motion>", do_move)

def launch_detail_view():
    target = _config.get("detail_file_path", "")
    if not target:
        tk.messagebox.showerror("경로 오류", "config.json에 'detail_file_path'가 설정되지 않았습니다.")
        return
    if not os.path.exists(target):
        tk.messagebox.showerror("파일 없음", f"지정된 경로의 파일이나 폴더가 존재하지 않습니다:\n{target}")
        return
    try:
        subprocess.Popen(["start", "", target], shell=True)
    except Exception as e:
        tk.messagebox.showerror("실행 오류", f"파일을 열 수 없습니다:\n{e}")

def create_gui():
    load_config()
    filepath = os.path.abspath(_config.get("data_file", ""))
    left_keys = _config.get("left_keywords", [])
    right_keys = _config.get("right_keywords", [])
    keyword_map = _config.get("keyword_display_map", {})

    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel()
    popup.overrideredirect(True)
    popup.configure(bg=BG_COLOR)
    popup.attributes("-topmost", False)
    popup.attributes("-alpha", 0.95)
    popup.lower()

    # 화면 위치 고정 (오른쪽 모니터 끝)
    x = 3510
    y = 390
    popup.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    bind_window_drag(popup)

    left_text = create_text_area(popup, 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)
    right_text = create_text_area(popup, 10 + TEXT_WIDTH + 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)

    def update_text_areas(items):
        left_lines = []
        right_lines = []
        for key, line in items:
            if key in right_keys:
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

    bottom_frame = tk.Frame(popup, bg=BG_COLOR)
    bottom_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    control_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
    control_frame.pack(side="right")

    detail_frame = tk.Frame(control_frame, bg=BG_COLOR)
    tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view,
              bg=BG_COLOR, activebackground=BG_COLOR).pack(side="right")
    tk.Label(detail_frame, text="Details", font=("Arial", 9), bg=BG_COLOR).pack(side="right")
    detail_frame.pack(side="right", padx=(0,10))

    tk.Button(control_frame, text="X", command=lambda: sys.exit(),
              width=2, height=1, relief="flat",
              bg=BG_COLOR, activebackground=BG_COLOR,
              borderwidth=0, highlightthickness=0).pack(side="right", padx=(0,10))

    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    tk.Checkbutton(control_frame, text="Auto-run on Startup",
                   variable=var_autorun, command=lambda: set_autorun(var_autorun.get()),
                   bg=BG_COLOR, activebackground=BG_COLOR,
                   highlightthickness=0, relief="flat").pack(side="right")

    refresh_summary()
    popup.mainloop()

if __name__ == "__main__":
    create_gui()