import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class MiscOpsMixin:
        def item_match(key):
            d = self.data[key]
            # 장르 필터
            if selected_genre != "전체" and d.get("genre", "") != selected_genre:
                return False
            # 화면 방향 필터
            if selected_orient == "세로" and not d.get("portrait", False):
                return False
            if selected_orient == "가로" and d.get("portrait", False):
                return False
            return True

        def pick_game_file():
            import random
            import shutil
            source_file = filedialog.askopenfilename(title="게임 파일 선택")
            if source_file:
                base_name = os.path.basename(source_file)
                name_only, ext = os.path.splitext(base_name)
                
                prefix = random.randint(1000, 9999)
                suffix = random.randint(1000, 9999)
                new_filename = f"{prefix}_{name_only}_{suffix}.bin"
                
                dest_dir = os.path.join(self.base_dir, "files")
                os.makedirs(dest_dir, exist_ok=True)
                
                dest_path = os.path.join(dest_dir, new_filename)
                shutil.copy2(source_file, dest_path)
                
                selected_file_name.set(new_filename)
                
                # 새 Key가 기본값(_copy)이면 파일 이름으로 제안
                if new_key_entry.get() == source_key + "_copy":
                    new_key_entry.delete(0, tk.END)
                    new_key_entry.insert(0, name_only)
                
                messagebox.showinfo("성공", f"파일이 복사되었습니다: {new_filename}", parent=dialog)

        def on_ok():
            new_key = new_key_entry.get().strip()
            if not new_key:
                messagebox.showwarning("경고", "새로운 Key를 입력하세요.", parent=dialog)
                return
            if new_key in self.data:
                confirm = messagebox.askyesno("덮어쓰기 확인", f"'{new_key}' 키가 이미 존재합니다. 덮어쓰시겠습니까?", parent=dialog)
                if not confirm:
                    return
            result["new_key"] = new_key
            result["url_file"] = selected_file_name.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        def do_search(*args):
            query = search_entry.get().strip().lower()
            result_text.delete("1.0", tk.END)
            if not query:
                current_search_key["key"] = None
                return
            
            current_search_key["key"] = query
            content = ""
            if "cheat" in cache_attr:
                lines = cache.get(query, [])
                if lines:
                    content = "".join(lines)
            else:
                content = cache.get(query, "")
                
            if content:
                result_text.insert(tk.END, content)
            else:
                if "cheat" in cache_attr:
                    result_text.insert(tk.END, f"; '{query}' 에 대한 치트 데이터가 없습니다.\n")
                else:
                    result_text.insert(tk.END, f"; '{query}' 에 대한 커맨드 데이터가 없습니다.\n")

        def do_save(*args):
            q = current_search_key["key"]
            if not q:
                messagebox.showwarning("경고", "먼저 검색을 통해 대상을 지정해주세요.", parent=dialog)
                return
                
            new_content = result_text.get("1.0", tk.END)
            if "cheat" in cache_attr:
                self._save_cheat_dat_internal(q, new_content, dialog)
                if getattr(self, "current_selected_key", None) == q:
                    self.load_cheat_data(q)
            else:
                self._save_command_dat_internal(q, new_content, dialog)
                if getattr(self, "current_selected_key", None) == q:
                    self.load_command_data(q)

