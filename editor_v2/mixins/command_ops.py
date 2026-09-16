import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class CommandOpsMixin:
    def _parse_command_dat(self):
        """command.dat 전체를 한 번만 파싱하여 {romkey: str} 딕셔너리로 캐시.
        구조: $info=rom1,rom2  →  $cmd ... $end  (한 key에 여러 $cmd~$end 가능)
        """
        cache = {}
        if not os.path.exists(self.command_dat_path):
            self.command_cache = cache
            return
        with open(self.command_dat_path, 'r', encoding='euc-kr', errors='replace') as f:
            lines = f.readlines()

        current_keys = []
        buf = []

        for line in lines:
            stripped = line.rstrip('\r\n')
            lower = stripped.lower()

            if lower.startswith('$info='):
                # 이전 키 버퍼 저장
                if current_keys and buf:
                    content = ''.join(buf)
                    for k in current_keys:
                        cache[k] = content
                    buf = []
                current_keys = [k.strip() for k in stripped[6:].split(',')]
                buf.append(line)
            elif current_keys:
                buf.append(line)

        # 마지막 키 처리
        if current_keys and buf:
            content = ''.join(buf)
            for k in current_keys:
                cache[k] = content

        self.command_cache = cache

    def load_command_data(self, key):
        """현재 선택된 key의 $cmd 블록을 Text 위젯에 표시."""
        if self.command_cache is None:
            self._parse_command_dat()
        self.command_text.delete("1.0", tk.END)
        content = self.command_cache.get(key.lower(), "")
        if content:
            self.command_text.insert(tk.END, content)
        else:
            self.command_text.insert(tk.END, f"; '{key}' 에 대한 커맨드 데이터가 없습니다.\n")

    def save_command_dat(self):
        """Text 위젯의 내용으로 command.dat의 해당 key 블록을 교체 후 저장."""
        if not self.current_selected_key:
            messagebox.showwarning("경고", "선택된 게임이 없습니다.", parent=self.root)
            return
            
        new_content = self.command_text.get("1.0", tk.END)
        self._save_command_dat_internal(self.current_selected_key, new_content, self.root)
        
        self.load_command_data(self.current_selected_key)

    def _save_command_dat_internal(self, key, new_content, parent_window):
        if not os.path.exists(self.command_dat_path):
            messagebox.showerror("오류", f"command.dat 파일을 찾을 수 없습니다:\n{self.command_dat_path}", parent=parent_window)
            return

        if new_content.strip().startswith("; '") and "커맨드 데이터가 없습니다" in new_content:
            messagebox.showinfo("안내", "커맨드 내용이 없습니다. 저장을 건너뜁니다.", parent=parent_window)
            return

        with open(self.command_dat_path, 'r', encoding='euc-kr', errors='replace') as f:
            orig_lines = f.readlines()

        key_lower = key.lower()

        # $info=key 콤마 포함하여 검색
        start_idx = None
        for i, line in enumerate(orig_lines):
            stripped_line = line.strip().lower()
            if stripped_line.startswith('$info='):
                keys_in_line = [k.strip() for k in stripped_line[6:].split(',')]
                if key_lower in keys_in_line:
                    start_idx = i
                    break

        # 다음 $info= 를 만나기 직전까지를 한 블록으로 취급
        end_idx = len(orig_lines) - 1
        if start_idx is not None:
            for i in range(start_idx + 1, len(orig_lines)):
                if orig_lines[i].strip().lower().startswith('$info='):
                    end_idx = i - 1
                    break

        new_lines_raw = new_content.splitlines(keepends=True)
        if new_lines_raw and new_lines_raw[-1] in ('\n', '\r\n', ''):
            new_lines_raw = new_lines_raw[:-1]

        if start_idx is not None:
            result = orig_lines[:start_idx] + new_lines_raw + ['\n'] + orig_lines[end_idx + 1:]
        else:
            # 없으면 파일 끝에 추가
            result = orig_lines + ['\n'] + new_lines_raw + ['\n']

        with open(self.command_dat_path, 'w', encoding='euc-kr', errors='replace') as f:
            f.writelines(result)

        # 캐시 갱신
        self.command_cache = None
        self._parse_command_dat()

        self.update_command_dat_version()
        messagebox.showinfo("성공", "command.dat 저장 완료 및 updates.json 갱신되었습니다.", parent=parent_window)

    def update_command_dat_version(self):
        """updates.json 의 'command.dat' 키 날짜 값을 갱신."""
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
        current_val = str(updates_data.get("command.dat", ""))

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

        updates_data["command.dat"] = new_val
        os.makedirs(os.path.dirname(updates_path), exist_ok=True)
        with open(updates_path, 'w', encoding='utf-8') as f:
            json.dump(updates_data, f, indent=4, ensure_ascii=False)

