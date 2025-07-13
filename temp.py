import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import json
import winreg

# --- 실행 파일 여부 확인 ---
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

# --- config 로드 ---
def load_config():
    config_path = os.path.join(base_path, "settings", "config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- 윈도우 자동 실행 설정 ---
APP_NAME = "QuickLogViewer"
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

# --- 로그 요약 추출 ---
def extract_summary_items(filepath):
    config = load_config()
    keyword_map = config.get("keyword_display_map", {})

    if os.path.isdir(filepath):
        txts = [f for f in os.listdir(filepath) if f.endswith(".txt")]
        if txts:
            filepath = os.path.join(filepath, txts[0])
        else:
            return []

    if not os.path.isfile(filepath):
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except PermissionError:
        return []

    summary = []
    for line in lines:
        clean_line = line.strip().lower()
        for keyword in keyword_map:
            if keyword in clean_line:
                fmt = keyword_map[keyword]
                try:
                    value = clean_line.split()[-1]
                    display = fmt.replace("{value}", value)
                    summary.append((keyword, display))
                except Exception:
                    pass
                break
    return summary

# --- 상세 보기 실행 ---
def launch_detail_view():
    target = os.path.join("C:\\monitoring", "listlist.txt")
    try:
        subprocess.Popen(["start", "", target], shell=True)
    except Exception as e:
        messagebox.showerror("Launch error", f"Failed to open: {e}")

# --- GUI 생성 ---
def create_gui():
    config = load_config()
    filepath = config.get("data_file", "")
    filepath = os.path.abspath(os.path.join(base_path, filepath)) if not os.path.isabs(filepath) else filepath

    left_keywords = config.get("left_keywords", [])
    right_keywords = config.get("right_keywords", [])

    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel()
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.5)

    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    width = 300
    height = 270
    x = screen_width - width - 20
    y = (screen_height // 2) - (height // 2)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    def start_move(event):
        popup.x = event.x
    def do_move(event):
        dx = event.x - popup.x
        dy = event.y - popup.y
        popup.geometry(f"+{popup.winfo_x() + dx}+{popup.winfo_y() + dy}")
    popup.bind("<ButtonPress-1>", start_move)
    popup.bind("<B1-Motion>", do_move)

    # 하나의 텍스트 위젯에 좌우 데이터 포맷팅해서 넣기
    text_area = tk.Text(popup, wrap="none", font=("Courier", 9))
    text_area.place(x=10, y=10, width=280, height=170)
    text_area.config(state="disabled")

    bottom_text = tk.Text(popup, wrap="none", font=("Courier", 9), height=1)
    bottom_text.place(x=10, y=185, width=280, height=20)
    bottom_text.insert("1.0", "▼ Loading...")
    bottom_text.config(state="disabled")

    def update_text_area(summary_items):
        left_lines = []
        right_lines = []
        for keyword, line in summary_items:
            if keyword in left_keywords:
                left_lines.append(line)
            elif keyword in right_keywords:
                right_lines.append(line)

        max_len = max(len(left_lines), len(right_lines))
        left_lines += [""] * (max_len - len(left_lines))
        right_lines += [""] * (max_len - len(right_lines))

        merged_lines = []
        for l, r in zip(left_lines, right_lines):
            merged_lines.append(f"{l:<25}  {r}")

        text_area.config(state="normal")
        text_area.delete("1.0", tk.END)
        text_area.insert("1.0", "\n".join(merged_lines))
        text_area.config(state="disabled")

        bottom_text.config(state="normal")
        bottom_text.delete("1.0", tk.END)
        bottom_text.insert("1.0", f"▲ Updated - Total: {len(summary_items)} items")
        bottom_text.config(state="disabled")

    def refresh_summary():
        items = extract_summary_items(filepath)
        update_text_area(items)
        popup.after(3600000, refresh_summary)

    # 초기 표시
    items = extract_summary_items(filepath)
    update_text_area(items)

    # 하단 제어 영역
    bottom_frame = tk.Frame(popup, bg=popup["bg"])
    bottom_frame.place(relx=0, rely=1.0, anchor="sw", x=10, y=-10)

    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    def on_autorun_toggle():
        set_autorun(var_autorun.get())
    check_autorun = tk.Checkbutton(bottom_frame, text="Auto-run on Startup", variable=var_autorun, command=on_autorun_toggle, bg=popup["bg"])
    check_autorun.pack(side="left")

    secret_close_btn = tk.Button(
        bottom_frame,
        text="",
        command=lambda: sys.exit(),
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        width=2,
        height=1,
        bg=popup["bg"],
        activebackground=popup["bg"]
    )
    secret_close_btn.pack(side="left", padx=10)

    details_frame = tk.Frame(bottom_frame, bg=popup["bg"])
    tk.Label(details_frame, text="Details", font=("Arial", 9), bg=popup["bg"]).pack(side="left")
    tk.Button(details_frame, text="⚙", font=("Arial", 10), command=launch_detail_view).pack(side="left")
    details_frame.pack(side="left")

    refresh_summary()
    popup.mainloop()

if __name__ == "__main__":
    create_gui()