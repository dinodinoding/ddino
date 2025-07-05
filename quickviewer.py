import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import json
import winreg

# --- 기본 실행 파일 여부 확인 & 경로 설정 ---
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

# --- 설정 불러오기 ---
def load_config():
    config_path = os.path.join(base_path, "settings", "config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- 자동 실행 설정 ---
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

# --- 필터 키워드 ---
KEYWORDS = [
    "feg_lifetime", "feg_change", "lmis_lifetime",
    "gis1", "gis2",
    "mis1", "mis2", "mis3", "mis4", "mis5", "mis6"
]

# --- 요약 로그 추출 ---
def extract_summary_lines(filepath):
    if os.path.isdir(filepath):
        txts = [f for f in os.listdir(filepath) if f.endswith(".txt")]
        if txts:
            filepath = os.path.join(filepath, txts[0])
        else:
            return [f"[No .txt files in directory: {filepath}]"]

    if not os.path.isfile(filepath):
        return [f"[Invalid log path: {filepath}]"]

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except PermissionError:
        return [f"[Permission denied opening file: {filepath}]"]

    summary = [line.strip() for line in lines if any(line.startswith(k) for k in KEYWORDS)]
    return summary if summary else ["[No matching keywords in log]"]

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

    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel()
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.5)

    # 위치
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    width = 300
    height = 250
    x = screen_width - width - 20
    y = (screen_height // 2) - (height // 2)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    # 창 이동
    def start_move(event):
        popup.x = event.x
        popup.y = event.y
    def do_move(event):
        dx = event.x - popup.x
        dy = event.y - popup.y
        popup.geometry(f"+{popup.winfo_x() + dx}+{popup.winfo_y() + dy}")
    popup.bind("<ButtonPress-1>", start_move)
    popup.bind("<B1-Motion>", do_move)

    # 텍스트 영역
    text_area = tk.Text(popup, wrap="word", font=("Courier", 9))
    text_area.place(x=10, y=10, width=280, height=170)
    summary = extract_summary_lines(filepath)
    text_area.insert("1.0", "\n".join(summary))
    text_area.config(state="disabled")

    # --- 요약 내용 자동 갱신 함수 ---
    def refresh_summary():
        new_summary = extract_summary_lines(filepath)
        text_area.config(state="normal")
        text_area.delete("1.0", tk.END)
        text_area.insert("1.0", "\n".join(new_summary))
        text_area.config(state="disabled")
        popup.after(3600000, refresh_summary)  # 1시간 후 반복

    refresh_summary()  # 즉시 실행 & 타이머 시작

    # 하단 프레임
    bottom_frame = tk.Frame(popup, bg=popup["bg"])
    bottom_frame.place(relx=0, rely=1.0, anchor="sw", x=10, y=-10)

    # 체크박스
    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    def on_autorun_toggle():
        set_autorun(var_autorun.get())
    check_autorun = tk.Checkbutton(bottom_frame, text="Auto-run on Startup", variable=var_autorun, command=on_autorun_toggle, bg=popup["bg"])
    check_autorun.pack(side="left")

    # 비밀 종료 버튼
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

    # Details + ⚙
    details_frame = tk.Frame(bottom_frame, bg=popup["bg"])
    tk.Label(details_frame, text="Details", font=("Arial", 9), bg=popup["bg"]).pack(side="left")
    tk.Button(details_frame, text="⚙", font=("Arial", 10), command=launch_detail_view).pack(side="left")
    details_frame.pack(side="left")

    popup.mainloop()

if __name__ == "__main__":
    create_gui()