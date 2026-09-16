import os
import random
import shutil
import string
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class GameAddCheatMixin:
    """새 게임/게임 복사 창에 콘솔용 치트 파일 추가 기능을 확장한다."""

    CHEAT_FOLDER_BY_SYSTEM = {
        "genesis": "genesischeats",
        "gba": "gbacheats",
        "nes": "nescheats",
        "snes": "snescheats",
    }

    def _select_console_cheat(self, system_value, key_value, parent):
        system_value = (system_value or "").strip().lower()
        key_value = (key_value or "").strip()

        cheat_folder = self.CHEAT_FOLDER_BY_SYSTEM.get(system_value)
        if not cheat_folder:
            messagebox.showwarning(
                "경고",
                "치트 추가는 genesis, gba, nes, snes 시스템에서 사용할 수 있습니다.",
                parent=parent,
            )
            return None

        if not key_value:
            messagebox.showwarning(
                "경고",
                "먼저 게임 Key(ID)를 입력하거나 게임 파일을 추가해주세요.",
                parent=parent,
            )
            return None

        source_cheat = filedialog.askopenfilename(
            title="치트 파일 선택",
            filetypes=[("RetroArch Cheat", "*.cht"), ("All files", "*.*")],
        )
        if not source_cheat:
            return None

        return source_cheat

    def _copy_console_cheat(self, source_cheat, system_value, game_key, parent):
        if not source_cheat:
            return True

        system_value = (system_value or "").strip().lower()
        game_key = (game_key or "").strip()
        cheat_folder = self.CHEAT_FOLDER_BY_SYSTEM.get(system_value)
        if not cheat_folder or not game_key:
            return False

        dest_dir = os.path.join(self.base_dir, "support", cheat_folder)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"{game_key}.cht")

        try:
            if os.path.abspath(source_cheat) == os.path.abspath(dest_path):
                return True

            if os.path.exists(dest_path):
                overwrite = messagebox.askyesno(
                    "치트 덮어쓰기 확인",
                    f"이미 치트 파일이 존재합니다.\n{dest_path}\n\n덮어쓰시겠습니까?",
                    parent=parent,
                )
                if not overwrite:
                    return False

            shutil.copy2(source_cheat, dest_path)
            return True
        except Exception as e:
            messagebox.showerror(
                "치트 복사 오류",
                f"치트 파일을 저장하지 못했습니다.\n{e}",
                parent=parent,
            )
            return False

    def add_new_game(self):
        """새로운 게임 항목을 추가하는 기능 (기존 동작 + 치트 파일 선택)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("새 게임 추가")
        dialog.geometry("520x225")
        dialog.resizable(False, False)

        self.root.update_idletasks()
        width = 520
        height = 225
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.transient(self.root)
        dialog.grab_set()

        selected_file_name = tk.StringVar()
        selected_cheat_name = tk.StringVar()
        selected_cheat_path = {"path": None}

        tk.Label(dialog, text="게임 Key(ID):").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        id_entry = tk.Entry(dialog, width=20)
        id_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        id_entry.focus()

        tk.Label(dialog, text="부모 게임 Key:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        parent_entry = tk.Entry(dialog, width=20)
        parent_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        tk.Label(dialog, text="System:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        system_combo = ttk.Combobox(
            dialog,
            values=["ekmame", "fbneo", "snes", "genesis", "nes", "gba"],
            width=17,
        )
        system_combo.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        system_combo.set("ekmame")

        def pick_game_file():
            source_file = filedialog.askopenfilename(title="게임 파일 선택")
            if source_file:
                base_name = os.path.basename(source_file)
                name_only, ext = os.path.splitext(base_name)
                sys_val = system_combo.get().strip() or "ekmame"

                if sys_val not in ["ekmame", "fbneo"] and ext.lower() in [".zip", ".rar", ".7z", ".gz", ".tar"]:
                    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=15))
                    new_filename = f"{random_str}.bin"
                    name_only = random_str
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

                if not id_entry.get():
                    id_entry.insert(0, name_only)

                messagebox.showinfo("성공", f"파일이 복사되었습니다: {new_filename}", parent=dialog)

        def pick_snapshot_file():
            cur_game_file = selected_file_name.get()
            if not cur_game_file:
                messagebox.showwarning("경고", "먼저 게임 파일을 추가해주세요.", parent=dialog)
                return

            source_img = filedialog.askopenfilename(
                title="스냅샷 파일 선택",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")],
            )
            if source_img:
                img_dir = os.path.dirname(source_img)
                _, img_ext = os.path.splitext(source_img)
                game_name_only, _ = os.path.splitext(cur_game_file)
                new_img_name = f"{game_name_only}{img_ext}"
                new_img_path = os.path.join(img_dir, new_img_name)

                try:
                    os.rename(source_img, new_img_path)
                    messagebox.showinfo(
                        "성공",
                        f"스냅샷 파일 이름이 변경되었습니다:\n{new_img_name}",
                        parent=dialog,
                    )
                except Exception as e:
                    messagebox.showerror("오류", f"이름 변경 실패:\n{e}", parent=dialog)

        def pick_cheat_file():
            cheat_path = self._select_console_cheat(
                system_combo.get(), id_entry.get(), dialog
            )
            if cheat_path:
                selected_cheat_path["path"] = cheat_path
                selected_cheat_name.set(os.path.basename(cheat_path))

        btn_container = tk.Frame(dialog)
        btn_container.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        tk.Button(btn_container, text="게임파일 추가", command=pick_game_file).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_container, text="스냅샷 추가", command=pick_snapshot_file).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_container, text="치트 추가", command=pick_cheat_file).pack(side=tk.LEFT, padx=5)
        tk.Label(btn_container, textvariable=selected_file_name, fg="darkgreen", font=("Consolas", 8)).pack(side=tk.LEFT, padx=5)

        tk.Label(
            dialog,
            textvariable=selected_cheat_name,
            fg="darkblue",
            font=("Consolas", 8),
        ).grid(row=4, column=0, columnspan=2, padx=10, sticky="w")

        result = {
            "new_key": None,
            "parent_key": None,
            "url_file": None,
            "system_val": None,
            "cheat_file": None,
        }

        def on_ok():
            new_key = id_entry.get().strip()
            parent_key = parent_entry.get().strip()
            if not new_key:
                messagebox.showwarning("경고", "게임 Key를 입력하세요.", parent=dialog)
                return
            if new_key in self.data:
                confirm = messagebox.askyesno(
                    "덮어쓰기 확인",
                    f"'{new_key}' 키가 이미 존재합니다. 덮어쓰시겠습니까?",
                    parent=dialog,
                )
                if not confirm:
                    return
            if parent_key and parent_key not in self.data:
                messagebox.showwarning(
                    "경고", f"'{parent_key}' 부모 게임이 존재하지 않습니다.", parent=dialog
                )
                return

            result["new_key"] = new_key
            result["parent_key"] = parent_key if parent_key else ""
            result["url_file"] = selected_file_name.get()
            result["system_val"] = system_combo.get().strip() or "ekmame"
            result["cheat_file"] = selected_cheat_path["path"]
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
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
            "LRbuttons": False,
        }

        self._copy_console_cheat(result["cheat_file"], sys_val, new_key, self.root)

        self.newly_added_keys.add(new_key)
        self.refresh_all_lists()
        self.update_listbox()
        self.select_listbox_key(new_key)
        self.on_select(None)

    def copy_item(self):
        """선택된 게임 항목을 복사하여 새로운 항목으로 추가 (기존 동작 + 치트 선택)."""
        if not self.listbox.curselection():
            messagebox.showwarning("경고", "복사할 항목을 먼저 선택하세요.")
            return

        raw_text = self.listbox.get(self.listbox.curselection())
        source_key = raw_text.replace("   └─ ", "").strip()
        sys_val = self.data[source_key].get("system", "ekmame").strip()

        dialog = tk.Toplevel(self.root)
        dialog.title("게임 복사")
        dialog.geometry("520x190")
        dialog.resizable(False, False)

        self.root.update_idletasks()
        width = 520
        height = 190
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=f"원본 Key: {source_key}", fg="gray").pack(pady=5)

        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="새 Key(ID):").pack(side=tk.LEFT, padx=5)
        new_key_entry = tk.Entry(input_frame, width=20)
        new_key_entry.pack(side=tk.LEFT, padx=5)
        new_key_entry.insert(0, source_key + "_copy")
        new_key_entry.focus()
        new_key_entry.selection_range(0, tk.END)

        selected_file_name = tk.StringVar()
        selected_cheat_name = tk.StringVar()
        selected_cheat_path = {"path": None}

        def pick_game_file():
            source_file = filedialog.askopenfilename(title="게임 파일 선택")
            if source_file:
                base_name = os.path.basename(source_file)
                name_only, ext = os.path.splitext(base_name)

                if sys_val not in ["ekmame", "fbneo"] and ext.lower() in [".zip", ".rar", ".7z", ".gz", ".tar"]:
                    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=15))
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

                if new_key_entry.get() == source_key + "_copy":
                    new_key_entry.delete(0, tk.END)
                    new_key_entry.insert(0, name_only)

                messagebox.showinfo("성공", f"파일이 복사되었습니다: {new_filename}", parent=dialog)

        def pick_snapshot_file():
            cur_game_file = selected_file_name.get()
            if not cur_game_file:
                messagebox.showwarning("경고", "먼저 게임 파일을 추가해주세요.", parent=dialog)
                return

            source_img = filedialog.askopenfilename(
                title="스냅샷 파일 선택",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")],
            )
            if source_img:
                img_dir = os.path.dirname(source_img)
                _, img_ext = os.path.splitext(source_img)
                game_name_only, _ = os.path.splitext(cur_game_file)
                new_img_name = f"{game_name_only}{img_ext}"
                new_img_path = os.path.join(img_dir, new_img_name)

                try:
                    os.rename(source_img, new_img_path)
                    messagebox.showinfo(
                        "성공",
                        f"스냅샷 파일 이름이 변경되었습니다:\n{new_img_name}",
                        parent=dialog,
                    )
                except Exception as e:
                    messagebox.showerror("오류", f"이름 변경 실패:\n{e}", parent=dialog)

        def pick_cheat_file():
            cheat_path = self._select_console_cheat(
                sys_val, new_key_entry.get(), dialog
            )
            if cheat_path:
                selected_cheat_path["path"] = cheat_path
                selected_cheat_name.set(os.path.basename(cheat_path))

        file_frame = tk.Frame(dialog)
        file_frame.pack(pady=5)
        tk.Button(file_frame, text="게임파일 추가", command=pick_game_file).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="스냅샷 추가", command=pick_snapshot_file).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="치트 추가", command=pick_cheat_file).pack(side=tk.LEFT, padx=5)
        tk.Label(file_frame, textvariable=selected_file_name, fg="darkgreen", font=("Consolas", 8)).pack(side=tk.LEFT, padx=5)

        tk.Label(
            dialog,
            textvariable=selected_cheat_name,
            fg="darkblue",
            font=("Consolas", 8),
        ).pack()

        result = {"new_key": None, "url_file": None, "cheat_file": None}

        def on_ok():
            new_key = new_key_entry.get().strip()
            if not new_key:
                messagebox.showwarning("경고", "새로운 Key를 입력하세요.", parent=dialog)
                return
            if new_key in self.data:
                confirm = messagebox.askyesno(
                    "덮어쓰기 확인",
                    f"'{new_key}' 키가 이미 존재합니다. 덮어쓰시겠습니까?",
                    parent=dialog,
                )
                if not confirm:
                    return

            result["new_key"] = new_key
            result["url_file"] = selected_file_name.get()
            result["cheat_file"] = selected_cheat_path["path"]
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="복사", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="취소", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)

        if result["new_key"]:
            new_key = result["new_key"]
            self.data[new_key] = self.data[source_key].copy()

            if result["url_file"]:
                if sys_val in ["ekmame", "fbneo"]:
                    url_prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
                else:
                    url_prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_val}/"
                self.data[new_key]["url"] = f"{url_prefix}{result['url_file']}"

            if self.data[source_key].get("parent") == "":
                self.data[new_key]["parent"] = source_key

            self._copy_console_cheat(result["cheat_file"], sys_val, new_key, self.root)

            self.newly_added_keys.add(new_key)
            self.refresh_all_lists()
            self.update_listbox()
            self.select_listbox_key(new_key)
            self.on_select(None)
