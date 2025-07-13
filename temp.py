# ─────────────────────────────────────────────
def create_gui():
    load_config()
    filepath = os.path.abspath(_config.get("data_file", ""))
    left_keys = _config.get("left_keywords", [])
    right_keys = _config.get("right_keywords", [])
    keyword_map = _config.get("keyword_display_map", {})

    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel()

    # left_text와 right_text를 create_gui 함수 스코프에 미리 선언합니다.
    # 초기값은 None으로 두어도 되지만, 곧바로 _create_text_display_areas에서 할당될 것입니다.
    left_text = None
    right_text = None

    # --- UI 초기 설정 함수 ---
    def _setup_main_window(popup_window):
        """팝업 창의 기본 속성(테두리, 배경, 투명도, 위치)을 설정합니다."""
        popup_window.overrideredirect(True)
        popup_window.configure(bg=BG_COLOR)
        popup_window.attributes("-topmost", False)
        popup_window.attributes("-alpha", 0.95)
        popup_window.lower() # 창을 맨 뒤로 보내려고 시도

        screen_w = popup_window.winfo_screenwidth()
        screen_h = popup_window.winfo_screenheight()
        x = screen_w - WIDTH - 20
        y = (screen_h // 2) - (HEIGHT // 2)
        popup_window.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

        bind_window_drag(popup_window) # 창 드래그 기능 바인딩

    # --- 텍스트 영역 생성 함수 ---
    def _create_text_display_areas(popup_window):
        """로그 요약 내용을 표시할 좌우 텍스트 박스를 생성합니다."""
        # nonlocal 대신, 함수가 값을 반환하도록 변경하거나,
        # 외부 스코프의 변수를 직접 할당합니다.
        # 여기서는 외부 스코프의 left_text, right_text에 직접 할당합니다.
        nonlocal left_text, right_text # <-- 이 줄은 그대로 둡니다.

        left_text = create_text_area(popup_window, 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)
        right_text = create_text_area(popup_window, 10 + TEXT_WIDTH + 10, 10, TEXT_WIDTH, TEXT_HEIGHT - 30)


    # --- 하단 컨트롤 버튼 생성 함수 ---
    def _create_bottom_controls(popup_window):
        """자동 실행 체크박스, 종료 버튼, Details 버튼을 포함하는 하단 컨트롤 영역을 생성합니다."""
        bottom_frame = tk.Frame(popup_window, bg=BG_COLOR)
        bottom_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        control_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
        control_frame.pack(side="right")

        detail_frame = tk.Frame(control_frame, bg=BG_COLOR)
        tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view,
                  bg=BG_COLOR, activebackground=BG_COLOR).pack(side="right")
        tk.Label(detail_frame, text="Details", font=("Arial", 9), bg=BG_COLOR).pack(side="right")
        detail_frame.pack(side="right", padx=(0,10))

        tk.Button(control_frame, text="X", command=lambda: popup.destroy(), # sys.exit() 대신 popup.destroy() 사용
                  width=2, height=1, relief="flat",
                  bg=BG_COLOR, activebackground=BG_COLOR,
                  borderwidth=0, highlightthickness=0).pack(side="right", padx=(0,10))

        var_autorun = tk.BooleanVar(value=is_autorun_enabled())
        tk.Checkbutton(control_frame, text="Auto-run on Startup",
                       variable=var_autorun, command=lambda: set_autorun(var_autorun.get()),
                       bg=BG_COLOR, activebackground=BG_COLOR,
                       highlightthickness=0, relief="flat").pack(side="right")

    # --- 실제 GUI 구성 실행 순서 조정 ---
    _setup_main_window(popup)
    _create_text_display_areas(popup) # 텍스트 영역 먼저 생성하여 변수 초기화

    # 이제 left_text와 right_text는 _create_text_display_areas에서 실제 위젯 객체로 할당되었습니다.

    def update_text_areas(items):
        # nonlocal 키워드는 _create_text_display_areas에서 이미 변수를 할당했으므로,
        # 여기서는 더 이상 필요하지 않습니다. 외부 스코프의 변수를 사용합니다.
        # nonlocal left_text, right_text # 이 줄을 제거하거나 주석 처리합니다.
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

    _create_bottom_controls(popup) # 텍스트 영역 생성 후 컨트롤 생성

    # 첫 요약 업데이트 호출 (이제 left_text와 right_text가 유효합니다)
    update_text_areas(extract_summary_items(filepath, keyword_map))
    refresh_summary() # 초기 호출 및 주기적 갱신 설정
    popup.mainloop()

if __name__ == "__main__":
    create_gui()
