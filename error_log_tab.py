def try_parse_time(text):
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def load_error_log(self):
    print(">> 로그 로드 시작")
    self.error_view.clear()

    if not self.error_files:
        print(">> 로그 파일 경로 없음")
        self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
        return

    selected = self.time_combo.currentText()
    delta_map = {
        "30분": timedelta(minutes=30),
        "1시간": timedelta(hours=1),
        "6시간": timedelta(hours=6),
        "12시간": timedelta(hours=12),
        "1일": timedelta(days=1),
    }
    time_range = delta_map.get(selected, timedelta(minutes=30))
    print(f">> 선택된 시간 필터: {selected} → {time_range}")

    try:
        max_len = max(len(f"[{os.path.basename(p)}]") for p in self.error_files)
        file_col_width = max_len + 2
    except Exception as e:
        print(f">> [경고] 파일명 길이 계산 실패: {e}")
        file_col_width = 20

    all_lines = []
    latest_time = None
    for path in self.error_files:
        print(f">> 파일 확인: {path}")
        if not os.path.exists(path):
            print(f"   !! 존재하지 않음: {path}")
            continue
        name = os.path.basename(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    # 헤더 스킵
                    if line.lower().startswith("time pid tid"):
                        continue

                    parts = line.strip().split(None, 6)  # 최대 7개 필드
                    if len(parts) < 7:
                        print(f"   !! 필드 부족: {line.strip()}")
                        continue

                    # 시간
                    ts = try_parse_time(f"{parts[0]} {parts[1]}")
                    if not ts:
                        print(f"   !! 시간 파싱 실패: {line.strip()}")
                        continue

                    # 로그 레벨
                    lvl = parts[4].lower()
                    msg = parts[6].strip()

                    latest_time = ts if latest_time is None or ts > latest_time else latest_time
                    all_lines.append((ts, lvl, msg, name))
        except Exception as e:
            print(f"   !! 파일 오픈 실패: {path}, 에러: {e}")
            continue

    if latest_time is None:
        self.error_view.setPlainText("로그에서 유효한 시간 정보를 찾을 수 없습니다.")
        return

    cutoff = latest_time - time_range
    levels = ['error']
    if self.include_warning.isChecked():
        levels.append('warning')

    print(f">> 기준 시간: {cutoff} ~ {latest_time}")
    print(f">> 대상 로그 레벨: {levels}")

    html_lines = []
    for ts, lvl, msg, name in all_lines:
        if ts < cutoff:
            continue
        if lvl not in levels:
            continue

        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        file_col = f"[{name}]"
        level_colored = {
            "error": '<span style="color:red;">ERROR</span>',
            "warning": '<span style="color:orange;">WARNING</span>'
        }.get(lvl, lvl.upper())

        html_line = (
            f'<span style="color:black; font-family:Courier New;">'
            f'{file_col:<{file_col_width}}{ts_str:<25}'
            f'{level_colored:<10}{msg}'
            f'</span>'
        )
        html_lines.append(html_line)

    if html_lines:
        self.error_view.setHtml("<br>".join(html_lines))
        print(f">> 출력된 라인 수: {len(html_lines)}")
    else:
        self.error_view.setPlainText("해당 시간 구간의 로그가 없습니다.")
        print(">> 필터링된 로그 없음")