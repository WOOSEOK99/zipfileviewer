import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class CheatOpsMixin:
    def _parse_cheat_dat(self):
        """cheat.dat 전체를 한 번만 파싱하여 {romkey: [lines]} 딕셔너리로 캐시."""
        cache = {}
        if not os.path.exists(self.cheat_dat_path):
            self.cheat_cache = cache
            return
        with open(self.cheat_dat_path, 'r', encoding='euc-kr', errors='replace') as f:
            lines = f.readlines()
        current_key = None
        for line in lines:
            stripped = line.rstrip('\n').rstrip('\r')
            # 치트 엔트리: 첫 문자가 ':' 이고 두 번째 ':' 까지 사이가 romkey
            if stripped.startswith(':'):
                parts = stripped.split(':')
                if len(parts) >= 3:
                    rk = parts[1].lower()
                    if rk not in cache:
                        cache[rk] = []
                    cache[rk].append(line)
                    current_key = rk
            elif stripped.startswith('; [') and current_key is not None:
                # 게임 구분 주석은 해당 키 블록에 포함
                pass
        self.cheat_cache = cache

    def load_cheat_data(self, key):
        """현재 선택된 key의 치트 라인을 Text 위젯에 표시."""
        if self.cheat_cache is None:
            self._parse_cheat_dat()
        self.cheat_text.delete("1.0", tk.END)
        lines = self.cheat_cache.get(key.lower(), [])
        if lines:
            self.cheat_text.insert(tk.END, "".join(lines))
        else:
            self.cheat_text.insert(tk.END, f"; '{key}' 에 대한 치트 데이터가 없습니다.\n")

    def cheat_replace_all(self):
        """Cheat Data 내의 특정 문자열을 일괄 변경"""
        find_str = self.cheat_find_entry.get()
        replace_str = self.cheat_replace_entry.get()
        
        if not find_str:
            messagebox.showwarning("경고", "찾을 문자를 입력하세요.", parent=self.root)
            return
            
        content = self.cheat_text.get("1.0", tk.END)
        # tk.Text가 붙이는 마지막 자동 개행 무시
        if content.endswith("\n"):
            content = content[:-1]
            
        if find_str in content:
            new_content = content.replace(find_str, replace_str)
            self.cheat_text.delete("1.0", tk.END)
            self.cheat_text.insert("1.0", new_content)
            messagebox.showinfo("완료", f"'{find_str}' 문자열이 모두 변경되었습니다.\n\n(아랫방향 '저장' 버튼을 눌러야 파일에 최종 반영됩니다.)", parent=self.root)
        else:
            messagebox.showinfo("결과", f"'{find_str}' 문자열을 찾을 수 없습니다.", parent=self.root)

    def save_cheat_dat(self):
        """Text 위젯의 내용으로 cheat.dat의 해당 key 블록을 교체 후 저장."""
        if not self.current_selected_key:
            messagebox.showwarning("경고", "선택된 게임이 없습니다.", parent=self.root)
            return
        
        new_content = self.cheat_text.get("1.0", tk.END)
        self._save_cheat_dat_internal(self.current_selected_key, new_content, self.root)
        
        self.load_cheat_data(self.current_selected_key)

    def _save_cheat_dat_internal(self, key, new_content, parent_window):
        if not os.path.exists(self.cheat_dat_path):
            messagebox.showerror("오류", f"cheat.dat 파일을 찾을 수 없습니다:\n{self.cheat_dat_path}", parent=parent_window)
            return

        # 빈 문자열이거나 '치트 데이터 없음' 메시지만 있으면 저장하지 않음
        if new_content.strip().startswith("; '") and "치트 데이터가 없습니다" in new_content:
            messagebox.showinfo("안내", "치트 내용이 없습니다. 저장을 건너뜁니다.", parent=parent_window)
            return

        # 원본 파일 읽기
        with open(self.cheat_dat_path, 'r', encoding='euc-kr', errors='replace') as f:
            orig_lines = f.readlines()

        key_lower = key.lower()
        prefix = f":{key_lower}:"

        # key 블록의 첫 줄과 마지막 줄 인덱스 탐색
        start_idx = None
        end_idx = None
        for i, line in enumerate(orig_lines):
            if line.lower().startswith(prefix):
                if start_idx is None:
                    start_idx = i
                end_idx = i

        new_lines_raw = new_content.splitlines(keepends=True)
        # 마지막에 빈 줄이 추가되지 않도록 정리
        if new_lines_raw and new_lines_raw[-1] in ('\n', '\r\n', ''):
            new_lines_raw = new_lines_raw[:-1]

        if start_idx is not None and end_idx is not None:
            # 기존 블록 교체
            result = orig_lines[:start_idx] + new_lines_raw + ['\n'] + orig_lines[end_idx + 1:]
        else:
            # 블록이 없으면 파일 끝에 추가
            result = orig_lines + ['\n'] + new_lines_raw + ['\n']

        with open(self.cheat_dat_path, 'w', encoding='euc-kr', errors='replace') as f:
            f.writelines(result)

        # 캐시 갱신
        self.cheat_cache = None
        self._parse_cheat_dat()

        self.update_cheat_dat_version()
        messagebox.showinfo("성공", "cheat.dat 저장 완료 및 updates.json 갱신되었습니다.", parent=parent_window)

    def update_cheat_dat_version(self):
        """updates.json 의 'cheat.dat' 키 날짜 값을 갱신."""
        import datetime
        updates_path = os.path.join(self.base_dir, "update", "updates.json")
        if os.path.exists(updates_path):
            with open(updates_path, 'r', encoding='utf-8') as f:
                try:
                    updates_data = json.load(f)
                except:
                    updates_data = {}
        else:
            updates_data = {}

        today = datetime.datetime.now().strftime("%Y%m%d")
        current_val = str(updates_data.get("cheat.dat", ""))

        if current_val.startswith(today):
            if "_" in current_val:
                prefix_d, count = current_val.split("_", 1)
                try:
                    new_val = f"{today}_{int(count) + 1}"
                except:
                    new_val = f"{today}_1"
            else:
                new_val = f"{today}_1"
        else:
            new_val = today

        updates_data["cheat.dat"] = new_val
        os.makedirs(os.path.dirname(updates_path), exist_ok=True)
        with open(updates_path, 'w', encoding='utf-8') as f:
            json.dump(updates_data, f, indent=4, ensure_ascii=False)

