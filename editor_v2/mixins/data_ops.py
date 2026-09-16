import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class DataOpsMixin:
    def _normalize_data(self, data):
        """데이터 정규화: 'buttons ' 공백 제거 등"""
        normalized = {}
        if not isinstance(data, dict): return data
        
        for key, val in data.items():
            if isinstance(val, dict):
                # "buttons " 키 처리
                if "buttons " in val:
                    b_val = val.pop("buttons ")
                    if "buttons" not in val or val["buttons"] == 0:
                        val["buttons"] = b_val
                
                # 버튼 값이 홀수인 경우 짝수(2,4,6)로 맞추기 위해 +1 처리
                if "buttons" in val:
                    try:
                        b_num = int(val["buttons"])
                        if b_num % 2 != 0:
                            b_num += 1
                        val["buttons"] = b_num
                    except (ValueError, TypeError):
                        pass
                
                # developer 필드 보장
                if "developer" not in val:
                    val["developer"] = ""
                    
            normalized[key] = val
        return normalized

    def auto_load_default(self):
        """실행 파일 기준 support/support_game_list.json 자동 로드"""
        default_path = os.path.join(self.base_dir, "support", "support_game_list.json")
        if os.path.exists(default_path):
            self.file_path = default_path
            with open(self.file_path, 'r', encoding='utf-8-sig') as f:
                raw_data = json.load(f)
            self.data = self._normalize_data(raw_data)
            self.refresh_all_lists()
            self.update_listbox()
            self.update_version_display()

    def delete_item(self):
        """선택된 게임 항목을 삭제하는 기능"""
        if not self.listbox.curselection():
            messagebox.showwarning("경고", "삭제할 항목을 먼저 선택하세요.")
            return
        
        raw_text = self.listbox.get(self.listbox.curselection())
        selected_key = raw_text.replace("   └─ ", "").strip()
        
        # 삭제 확인 창
        confirm = messagebox.askyesno("삭제 확인", f"'{selected_key}' 항목을 정말로 삭제하시겠습니까?\n(메모리에서 즉시 삭제되며 저장 시 반영됩니다.)", parent=self.root)
        
        if confirm:
            if selected_key in self.data:
                del self.data[selected_key]
                if selected_key in self.newly_added_keys:
                    self.newly_added_keys.remove(selected_key)
                self.update_listbox()
                # 입력창 초기화
                self.key_entry.delete(0, tk.END)
                for widget in self.entries.values():
                    if isinstance(widget, (tk.Entry, ttk.Combobox, tk.Spinbox)):
                        widget.delete(0, tk.END)
                    elif isinstance(widget, tk.Text):
                        widget.delete("1.0", tk.END)
                self.buttons_var.set(0)
                self.img_label.config(image="", text="미리보기")
                self.marquee_label.config(image="", text="마키 이미지")
                messagebox.showinfo("성공", f"'{selected_key}' 항목이 삭제되었습니다.", parent=self.root)

    def delete_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("경고", "삭제할 게임을 선택해주세요.", parent=self.root)
            return

        confirm = messagebox.askyesno("삭제 확인", f"선택한 {len(sel)}개의 게임을 삭제하시겠습니까?\n\n(참고: 부모 게임 삭제 시 자식 데이터가 트리에서 분리될 수 있습니다)", parent=self.root)
        if not confirm:
            return

        keys_to_delete = []
        for idx in sel:
            raw_text = self.listbox.get(idx)
            key = raw_text.replace("   └─ ", "").strip()
            keys_to_delete.append(key)

        for key in keys_to_delete:
            if key in self.data:
                del self.data[key]
            if key in self.newly_added_keys:
                self.newly_added_keys.remove(key)

        self.update_listbox()
        self.key_entry.delete(0, tk.END)
        self.current_selected_key = ""
        messagebox.showinfo("완료", "선택한 게임이 성공적으로 삭제되었습니다.", parent=self.root)

    def load_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not self.file_path: return
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            raw_data = json.load(f)
        self.data = self._normalize_data(raw_data)
        self.refresh_all_lists()
        self.update_listbox()

    def save_file(self):
        if not self.file_path: return
        
        # 저장 전 데이터 검증: url이 파일명만 있다면 전체 경로로 변환
        for key in self.data:
            url_val = str(self.data[key].get("url", ""))
            if url_val and not url_val.startswith("http"):
                filename = os.path.basename(url_val)
                sys_val = str(self.data[key].get("system", "ekmame")).strip()
                if sys_val in ["ekmame", "fbneo"]:
                    prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
                else:
                    prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_val}/"
                self.data[key]["url"] = f"{prefix}{filename}"

        # 부모-자식 순서 유지
        ordered = {}
        parents = [k for k, v in self.data.items() if not v.get("parent")]
        clones = [k for k, v in self.data.items() if v.get("parent")]
        for p in parents:
            ordered[p] = self.data[p]
            for c in clones:
                if self.data[c].get("parent") == p:
                    ordered[c] = self.data[c]

        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(ordered, f, indent=4, ensure_ascii=False)
        
        if self.newly_added_keys:
            txt_path = os.path.join(self.base_dir, "newly_added_titles.txt")
            
            titles_ko = []
            titles_en = []
            for k in self.newly_added_keys:
                item = self.data.get(k)
                if item:
                    title_str = item.get('title', '').strip()
                    title_en_str = item.get('title_en', '').strip()
                    if title_str:
                        titles_ko.append(title_str)
                    if title_en_str:
                        titles_en.append(title_en_str)

            with open(txt_path, 'w', encoding='utf-8') as tf:
                for t in titles_ko:
                    tf.write(f"<P>{t}</P>\n")
                for t in titles_en:
                    tf.write(f"<P>{t}</P>\n")
            
            self.newly_added_keys.clear()
        
        self.update_json_version()
        messagebox.showinfo("성공", "파일이 저장되고 updates.json이 갱신됨.\n(새로 추가된 게임 목록은 newly_added_titles.txt에 저장되었습니다.)", parent=self.root)

    def append_json(self):
        append_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")], title="추가할 JSON 파일 선택")
        if not append_path: return
        try:
            with open(append_path, 'r', encoding='utf-8-sig') as f:
                new_data = json.load(f)
            new_data = self._normalize_data(new_data)
            
            count = 0
            for key, val in new_data.items():
                if key not in self.data:
                    self.data[key] = val
                    self.newly_added_keys.add(key)
                    count += 1
            
            self.refresh_all_lists()
            self.update_listbox()
            messagebox.showinfo("완료", f"총 {count}개의 게임 항목이 목록에 추가되었습니다.\n(메뉴에서 '저장하기'를 눌러야 파일에 반영됩니다.)", parent=self.root)
        except Exception as e:
            messagebox.showerror("오류", f"JSON 병합 중 오류가 발생했습니다.\n{e}", parent=self.root)

    def batch_link_roms(self):
        missing_url_keys = [k for k, v in self.data.items() if not v.get("url")]
        if not missing_url_keys:
            messagebox.showinfo("알림", "현재 목록에 url이 비어있는 게임이 없습니다.", parent=self.root)
            return

        source_dir = filedialog.askdirectory(title="자동 매칭할 원본 롬파일들이 있는 폴더 선택")
        if not source_dir:
            return

        import os, random, shutil

        linked_count = 0
        missing_files = []

        for key in missing_url_keys:
            found_file = None
            # key 이름과 동일한 롬파일 찾기 (.bin, .zip, .rom 등 확장자 고려)
            for ext in [".bin", ".zip", ".rom", ""]:
                target = os.path.join(source_dir, key + ext)
                if os.path.isfile(target):
                    found_file = target
                    break
            
            if found_file:
                prefix = random.randint(1000, 9999)
                suffix = random.randint(1000, 9999)
                
                new_filename = f"{prefix}_{key}_{suffix}.bin"
                
                sys_val = str(self.data[key].get("system", "ekmame")).strip()
                if sys_val in ["ekmame", "fbneo"]:
                    dest_dir = os.path.join(self.base_dir, "files")
                    url_prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
                else:
                    dest_dir = os.path.join(self.base_dir, "konfiles", sys_val)
                    url_prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_val}/"
                os.makedirs(dest_dir, exist_ok=True)
                
                dest_path = os.path.join(dest_dir, new_filename)
                
                try:
                    shutil.copy2(found_file, dest_path)
                    self.data[key]["url"] = f"{url_prefix}{new_filename}"
                    linked_count += 1
                except Exception as e:
                    missing_files.append(f"{key} (복사실패: {e})")
            else:
                missing_files.append(key)
        
        if self.current_selected_key in self.data:
            self.select_listbox_key(self.current_selected_key)
            self.on_select(None)
            
        msg = f"총 {linked_count}개의 롬파일을 찾아 연동 및 파일 난수화 복사를 완료했습니다.\n\n"
        if missing_files:
            msg += f"[폴더에서 롬파일을 찾지 못한 게임: {len(missing_files)}개]\n" + ", ".join(missing_files)
        else:
            msg += "url이 빈 모든 게임의 롬파일을 완벽히 매칭했습니다!"
            
        self.show_scrollable_info("일괄 연동 결과", msg)

    def batch_set_year(self):
        """임시 버튼: 모든 항목의 year를 0으로 일괄 설정"""
        confirm = messagebox.askyesno("일괄 처리", "모든 게임의 year 값을 0으로 변경하시겠습니까?", parent=self.root)
        if confirm:
            count = 0
            for key in self.data:
                self.data[key]["year"] = 0
                count += 1
            if self.current_selected_key and "year" in self.entries:
                self.entries["year"].delete(0, tk.END)
                self.entries["year"].insert(0, "0")
            messagebox.showinfo("완료", f"총 {count}개의 항목이 year=0으로 변경되었습니다.\n메뉴에서 '저장하기'를 눌러 파일에 반영하세요.", parent=self.root)

    def batch_set_dev(self):
        """임시 버튼: 모든 항목의 developer를 ''로 일괄 설정"""
        confirm = messagebox.askyesno("일괄 처리", "모든 게임의 developer 값을 비우시겠습니까?", parent=self.root)
        if confirm:
            count = 0
            for key in self.data:
                self.data[key]["developer"] = ""
                count += 1
            if self.current_selected_key and "developer" in self.entries:
                if isinstance(self.entries["developer"], ttk.Combobox):
                    self.entries["developer"].set("")
                else:
                    self.entries["developer"].delete(0, tk.END)
            self.refresh_developer_list()
            messagebox.showinfo("완료", f"총 {count}개의 항목이 developer=''로 변경되었습니다.\n메뉴에서 '저장하기'를 눌러 파일에 반영하세요.", parent=self.root)

    def add_new_game(self):
        """새로운 게임 항목을 추가하는 기능 (parent 또는 clone)"""
        import random
        import shutil
        import datetime
        import string

        # 커스텀 dialog 생성
        dialog = tk.Toplevel(self.root)
        dialog.title("새 게임 추가")
        dialog.geometry("400x200") # 크기를 약간 키움
        dialog.resizable(False, False)
        
        # 다이얼로그를 화면 중앙에 띄우기
        self.root.update_idletasks()
        width = 400
        height = 200
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.transient(self.root)
        dialog.grab_set()
        
        selected_file_name = tk.StringVar()

        # 게임 ID 입력
        tk.Label(dialog, text="게임 Key(ID):").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        id_entry = tk.Entry(dialog, width=20)
        id_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        id_entry.focus()
        
        # 부모 게임 입력
        tk.Label(dialog, text="부모 게임 Key:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        parent_entry = tk.Entry(dialog, width=20)
        parent_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # System 입력
        tk.Label(dialog, text="System:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        system_combo = ttk.Combobox(dialog, values=["ekmame", "fbneo", "snes", "genesis","gba"], width=17)
        system_combo.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        system_combo.set("ekmame")

        # 게임파일 추가 버튼
        def pick_game_file():
            source_file = filedialog.askopenfilename(title="게임 파일 선택")
            if source_file:
                # 파일 처리
                dir_name = os.path.dirname(source_file)
                base_name = os.path.basename(source_file)
                name_only, ext = os.path.splitext(base_name)
                
                # system 에 따른 경로
                sys_val = system_combo.get().strip() or "ekmame"
                
                if sys_val not in ["ekmame", "fbneo"] and ext.lower() in [".zip", ".rar", ".7z", ".gz", ".tar"]:
                    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
                    new_filename = f"{random_str}.bin"
                    name_only = random_str
                else:
                    # 무작위 숫자 생성
                    prefix = random.randint(1000, 9999)
                    suffix = random.randint(1000, 9999)
                    new_filename = f"{prefix}_{name_only}_{suffix}.bin"
                
                if sys_val in ["ekmame", "fbneo"]:
                    dest_dir = os.path.join(self.base_dir, "files")
                else:
                    dest_dir = os.path.join(self.base_dir, "konfiles", sys_val)
                os.makedirs(dest_dir, exist_ok=True)
                
                dest_path = os.path.join(dest_dir, new_filename)
                shutil.copy2(source_file, dest_path)
                
                selected_file_name.set(new_filename)
                
                # Key가 비어 있으면 파일 이름(원본)을 기본값으로 제안
                if not id_entry.get():
                    id_entry.insert(0, name_only)
                
                messagebox.showinfo("성공", f"파일이 복사되었습니다: {new_filename}", parent=dialog)

        def pick_snapshot_file():
            cur_game_file = selected_file_name.get()
            if not cur_game_file:
                messagebox.showwarning("경고", "먼저 게임 파일을 추가해주세요.", parent=dialog)
                return
                
            source_img = filedialog.askopenfilename(title="스냅샷 파일 선택", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
            if source_img:
                img_dir = os.path.dirname(source_img)
                _, img_ext = os.path.splitext(source_img)
                
                # 게임 파일명 획득 (확장자 제외)
                game_name_only, _ = os.path.splitext(cur_game_file)
                new_img_name = f"{game_name_only}{img_ext}"
                new_img_path = os.path.join(img_dir, new_img_name)
                
                try:
                    os.rename(source_img, new_img_path)
                    messagebox.showinfo("성공", f"스냅샷 파일 이름이 변경되었습니다:\n{new_img_name}", parent=dialog)
                except Exception as e:
                    messagebox.showerror("오류", f"이름 변경 실패:\n{e}", parent=dialog)

        btn_container = tk.Frame(dialog)
        btn_container.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        tk.Button(btn_container, text="게임파일 추가", command=pick_game_file).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_container, text="스냅샷 추가", command=pick_snapshot_file).pack(side=tk.LEFT, padx=5)
        tk.Label(btn_container, textvariable=selected_file_name, fg="darkgreen", font=("Consolas", 8)).pack(side=tk.LEFT, padx=5)

        result = {"new_key": None, "parent_key": None, "url_file": None, "system_val": None}
        
        def on_ok():
            new_key = id_entry.get().strip()
            parent_key = parent_entry.get().strip()
            if not new_key:
                messagebox.showwarning("경고", "게임 Key를 입력하세요.", parent=dialog)
                return
            if new_key in self.data:
                confirm = messagebox.askyesno("덮어쓰기 확인", f"'{new_key}' 키가 이미 존재합니다. 덮어쓰시겠습니까?", parent=dialog)
                if not confirm:
                    return
            if parent_key and parent_key not in self.data:
                messagebox.showwarning("경고", f"'{parent_key}' 부모 게임이 존재하지 않습니다.", parent=dialog)
                return
            result["new_key"] = new_key
            result["parent_key"] = parent_key if parent_key else ""
            result["url_file"] = selected_file_name.get()
            result["system_val"] = system_combo.get().strip() or "ekmame"
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # 버튼
        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="추가", command=on_ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="취소", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        self.root.wait_window(dialog)
        
        if not result["new_key"]:
            return
        
        new_key = result["new_key"]
        parent_key = result["parent_key"]
        sys_val = result["system_val"]

        if sys_val in ["ekmame", "fbneo"]:
            url_prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
        else:
            url_prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_val}/"
        
        # 기본 템플릿으로 새 게임 추가
        new_url = ""
        if result["url_file"]:
            new_url = f"{url_prefix}{result['url_file']}"

        self.data[new_key] = {
            "url": new_url,
            "title": "",
            "title_en": "",
            "desc": "",
            "category": "",
            "genre": "",
            "genre_en": "",
            "series": "",
            "series_en": "",
            "parent": parent_key,
            "year": 0,
            "developer": "",
            "portrait": False,
            "buttons": 0,
            "system": sys_val,
            "LRbuttons": False
        }
        self.newly_added_keys.add(new_key)
        self.refresh_all_lists()
        self.update_listbox()
        self.select_listbox_key(new_key)
        self.on_select(None)

    def copy_item(self):
        """선택된 게임 항목을 복사하여 새로운 항목으로 추가하는 기능"""
        if not self.listbox.curselection():
            messagebox.showwarning("경고", "복사할 항목을 먼저 선택하세요.")
            return
        
        raw_text = self.listbox.get(self.listbox.curselection())
        source_key = raw_text.replace("   └─ ", "").strip()
        
        # 커스텀 dialog 생성
        dialog = tk.Toplevel(self.root)
        dialog.title("게임 복사")
        dialog.geometry("350x150")
        dialog.resizable(False, False)
        
        # 다이얼로그를 화면 중앙에 띄우기
        self.root.update_idletasks()
        width = 350
        height = 150
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.transient(self.root)
        dialog.grab_set()

        # 원본 Key 표시
        tk.Label(dialog, text=f"원본 Key: {source_key}", fg="gray").pack(pady=5)
        
        # 새 Key 입력 프레임
        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=5)
        
        tk.Label(input_frame, text="새 Key(ID):").pack(side=tk.LEFT, padx=5)
        new_key_entry = tk.Entry(input_frame, width=20)
        new_key_entry.pack(side=tk.LEFT, padx=5)
        new_key_entry.insert(0, source_key + "_copy")
        new_key_entry.focus()
        new_key_entry.selection_range(0, tk.END)

        selected_file_name = tk.StringVar()

        # 게임파일 추가 버튼 (add_new_game의 로직과 동일)
        def pick_game_file():
            import random
            import shutil
            import string
            source_file = filedialog.askopenfilename(title="게임 파일 선택")
            if source_file:
                base_name = os.path.basename(source_file)
                name_only, ext = os.path.splitext(base_name)
                
                sys_val = self.data[source_key].get("system", "ekmame").strip()
                
                if sys_val not in ["ekmame", "fbneo"] and ext.lower() in [".zip", ".rar", ".7z", ".gz", ".tar"]:
                    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
                    new_filename = f"{random_str}.bin"
                else:
                    prefix = random.randint(1000, 9999)
                    suffix = random.randint(1000, 9999)
                    new_filename = f"{prefix}_{name_only}_{suffix}.bin"
                
                if sys_val in ["ekmame", "fbneo"]:
                    dest_dir = os.path.join(self.base_dir, "files")
                else:
                    dest_dir = os.path.join(self.base_dir, "konfiles", sys_val)
                os.makedirs(dest_dir, exist_ok=True)
                
                dest_path = os.path.join(dest_dir, new_filename)
                shutil.copy2(source_file, dest_path)
                
                selected_file_name.set(new_filename)
                
                # 새 Key가 기본값(_copy)이면 파일 이름으로 제안
                if new_key_entry.get() == source_key + "_copy":
                    new_key_entry.delete(0, tk.END)
                    new_key_entry.insert(0, name_only)
                
                messagebox.showinfo("성공", f"파일이 복사되었습니다: {new_filename}", parent=dialog)

        def pick_snapshot_file():
            cur_game_file = selected_file_name.get()
            if not cur_game_file:
                messagebox.showwarning("경고", "먼저 게임 파일을 추가해주세요.", parent=dialog)
                return
                
            source_img = filedialog.askopenfilename(title="스냅샷 파일 선택", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
            if source_img:
                img_dir = os.path.dirname(source_img)
                _, img_ext = os.path.splitext(source_img)
                
                game_name_only, _ = os.path.splitext(cur_game_file)
                new_img_name = f"{game_name_only}{img_ext}"
                new_img_path = os.path.join(img_dir, new_img_name)
                
                try:
                    os.rename(source_img, new_img_path)
                    messagebox.showinfo("성공", f"스냅샷 파일 이름이 변경되었습니다:\n{new_img_name}", parent=dialog)
                except Exception as e:
                    messagebox.showerror("오류", f"이름 변경 실패:\n{e}", parent=dialog)

        file_frame = tk.Frame(dialog)
        file_frame.pack(pady=5)
        tk.Button(file_frame, text="게임파일 추가", command=pick_game_file).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="스냅샷 추가", command=pick_snapshot_file).pack(side=tk.LEFT, padx=5)
        tk.Label(file_frame, textvariable=selected_file_name, fg="darkgreen", font=("Consolas", 8)).pack(side=tk.LEFT, padx=5)

        result = {"new_key": None, "url_file": None}

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

        # 버튼 프레임
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="복사", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="취소", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

        if result["new_key"]:
            new_key = result["new_key"]
            self.data[new_key] = self.data[source_key].copy()
            
            # 파일이 선택된 경우 URL 업데이트
            if result["url_file"]:
                sys_val = self.data[source_key].get("system", "ekmame").strip()
                if sys_val in ["ekmame", "fbneo"]:
                    url_prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
                else:
                    url_prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_val}/"
                self.data[new_key]["url"] = f"{url_prefix}{result['url_file']}"

            # parent 게임을 복사하면 clone으로 만들고 parent 설정
            if self.data[source_key].get("parent") == "":
                self.data[new_key]["parent"] = source_key
            
            self.newly_added_keys.add(new_key)
            
            self.refresh_all_lists()
            self.update_listbox()
            self.select_listbox_key(new_key)
            self.on_select(None)

