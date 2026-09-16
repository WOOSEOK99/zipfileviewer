import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
import urllib.parse
from io import BytesIO
from PIL import Image, ImageTk


class UiSetupMixin:
    def setup_ui(self):
        # 상단 메뉴
        menubar = tk.Menu(self.root)
        menubar.add_command(label="파일 열기", command=self.load_file)
        menubar.add_command(label="JSON 추가하기", command=self.append_json)
        menubar.add_command(label="롬파일 일괄 연동", command=self.batch_link_roms)
        menubar.add_command(label="저장하기", command=self.save_file)
        self.root.config(menu=menubar)

        # 메인 프레임 (3열: 리스트 | 게임정보 | 치트)
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.paned_win = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5)
        self.paned_win.pack(fill=tk.BOTH, expand=True)

        # --- 1열: 리스트박스 및 검색 ---
        list_frame = tk.Frame(self.paned_win)
        self.paned_win.add(list_frame, minsize=200, stretch="never")
        
        search_frame = tk.Frame(list_frame)
        search_frame.pack(fill=tk.X, pady=(0, 2))
        
        self.search_entry = tk.Entry(search_frame, width=15)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", self.perform_search)
        
        tk.Button(search_frame, text="Next", command=self.go_next_search, font=("Malgun Gothic", 8)).pack(side=tk.LEFT, padx=2)
        tk.Label(search_frame, textvariable=self.search_info_var, font=("Consolas", 8), width=5).pack(side=tk.LEFT)

        # 장르 필터
        genre_frame = tk.Frame(list_frame)
        genre_frame.pack(fill=tk.X, pady=(0, 2))
        tk.Label(genre_frame, text="장르:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.genre_filter_var = tk.StringVar(value="전체")
        self.genre_filter_cb = ttk.Combobox(genre_frame, textvariable=self.genre_filter_var,
                                             state="readonly", font=("Malgun Gothic", 8), width=14)
        self.genre_filter_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.genre_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.update_listbox())
        self.count_var = tk.StringVar(value="")
        tk.Label(genre_frame, textvariable=self.count_var, font=("Malgun Gothic", 8), fg="gray").pack(side=tk.RIGHT)

        # 시스템 필터
        system_frame = tk.Frame(list_frame)
        system_frame.pack(fill=tk.X, pady=(0, 2))
        tk.Label(system_frame, text="기종:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.system_filter_var = tk.StringVar(value="전체")
        self.system_filter_cb = ttk.Combobox(system_frame, textvariable=self.system_filter_var,
                                             state="readonly", font=("Malgun Gothic", 8), width=14)
        self.system_filter_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.system_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.update_listbox())

        # 카테고리 필터
        category_frame = tk.Frame(list_frame)
        category_frame.pack(fill=tk.X, pady=(0, 2))
        tk.Label(category_frame, text="분류:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.category_filter_var = tk.StringVar(value="전체")
        self.category_filter_cb = ttk.Combobox(category_frame, textvariable=self.category_filter_var,
                                               state="readonly", font=("Malgun Gothic", 8), width=14)
        self.category_filter_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.category_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.update_listbox())

        # 화면 방향 필터 (가로/세로)
        orient_frame = tk.Frame(list_frame)
        orient_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Label(orient_frame, text="방향:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.orient_filter_var = tk.StringVar(value="전체")
        for label, val in [("전체", "전체"), ("가로", "가로"), ("세로", "세로")]:
            tk.Radiobutton(orient_frame, text=label, variable=self.orient_filter_var, value=val,
                           font=("Malgun Gothic", 8), command=self.update_listbox).pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(list_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        tk.Button(btn_frame, text="현재 목록 title 추출", command=self.extract_current_titles, font=("Malgun Gothic", 9)).pack(fill=tk.X, pady=(0, 2))
        tk.Button(btn_frame, text="Key 비교 (diff)", command=self.compare_keys_with_txt, font=("Malgun Gothic", 9), fg="darkblue").pack(fill=tk.X, pady=(0, 2))
        self.duplicate_btn = tk.Button(btn_frame, text="중복 title 모아보기", command=self.toggle_duplicate_mode, font=("Malgun Gothic", 9), fg="purple")
        self.duplicate_btn.pack(fill=tk.X, pady=(0, 2))
        tk.Button(btn_frame, text="선택 게임 삭제", command=self.delete_selected, font=("Malgun Gothic", 9), fg="red").pack(fill=tk.X)
        
        lb_frame = tk.Frame(list_frame)
        lb_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(lb_frame, width=25, font=("Malgun Gothic", 9), selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        
        scrollbar = tk.Scrollbar(lb_frame)
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        # --- 2열: 게임 정보 편집 ---
        mid_frame = tk.Frame(self.paned_win)
        self.paned_win.add(mid_frame, minsize=350, stretch="never")

        edit_frame = tk.LabelFrame(mid_frame, text="게임 정보", pady=5)
        edit_frame.pack(fill=tk.X)

        self.entries = {}
        self.bool_vars = {}
        self.buttons_var = tk.IntVar(value=0)
        self.current_selected_key = ""

        # Key (ID)
        tk.Label(edit_frame, text="Key (ID):").grid(row=0, column=0, sticky="e", padx=2)
        self.key_entry = tk.Entry(edit_frame, fg="red", font=("Consolas", 10, "bold"), width=35)
        self.key_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        # URL(파일명)
        tk.Label(edit_frame, text="파일명:").grid(row=1, column=0, sticky="e", padx=2)
        url_ent = tk.Entry(edit_frame, fg="blue", font=("Consolas", 10, "bold"), width=35)
        url_ent.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        url_ent.bind("<FocusOut>", self.clean_url_input)
        self.entries["url"] = url_ent

        tk.Label(edit_frame, text="title").grid(row=2, column=0, sticky="e", padx=2)
        self.entries["title"] = tk.Entry(edit_frame, width=35)
        self.entries["title"].grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="title_en").grid(row=3, column=0, sticky="e", padx=2)
        self.entries["title_en"] = tk.Entry(edit_frame, width=35)
        self.entries["title_en"].grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="series").grid(row=4, column=0, sticky="e", padx=2)
        self.entries["series"] = ttk.Combobox(edit_frame, values=self.series_list, width=35)
        self.entries["series"].grid(row=4, column=1, sticky="ew", padx=5, pady=2)
        self.entries["series"].set("")

        tk.Label(edit_frame, text="series_en").grid(row=5, column=0, sticky="e", padx=2)
        self.entries["series_en"] = tk.Entry(edit_frame, width=35)
        self.entries["series_en"].grid(row=5, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="parent").grid(row=7, column=0, sticky="e", padx=2)
        self.entries["parent"] = ttk.Combobox(edit_frame, values=self.parent_list, width=35)
        self.entries["parent"].grid(row=7, column=1, sticky="ew", padx=5, pady=2)
        self.entries["parent"].set("")

        tk.Label(edit_frame, text="genre").grid(row=8, column=0, sticky="e", padx=2)
        self.entries["genre"] = ttk.Combobox(edit_frame, values=self.genre_list, width=35)
        self.entries["genre"].grid(row=8, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="genre_en").grid(row=9, column=0, sticky="e", padx=2)
        self.entries["genre_en"] = ttk.Combobox(edit_frame, values=self.genre_en_list, width=35)
        self.entries["genre_en"].grid(row=9, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="system").grid(row=10, column=0, sticky="e", padx=2)
        self.entries["system"] = ttk.Combobox(edit_frame, values=["ekmame", "fbneo", "snes", "genesis","gba"], width=35)
        self.entries["system"].grid(row=10, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(edit_frame, text="category").grid(row=11, column=0, sticky="e", padx=2)
        self.entries["category"] = ttk.Combobox(edit_frame, values=self.category_list if hasattr(self, 'category_list') else ["arcade", "console"], width=35)
        self.entries["category"].grid(row=11, column=1, sticky="ew", padx=5, pady=2)

        # tk.Label(edit_frame, text="year").grid(row=12, column=0, sticky="e", padx=2)
        self.entries["year"] = tk.Spinbox(edit_frame, from_=1980, to=2030, width=35)
        # self.entries["year"].grid(row=12, column=1, sticky="ew", padx=5, pady=2)

        self.bool_vars["portrait"] = tk.BooleanVar()
        tk.Checkbutton(edit_frame, text="portrait", variable=self.bool_vars["portrait"]).grid(row=12, column=1, sticky="w", padx=5, pady=2)

        tk.Label(edit_frame, text="buttons").grid(row=13, column=0, sticky="e", padx=2)
        btn_chk_frame = tk.Frame(edit_frame)
        btn_chk_frame.grid(row=13, column=1, sticky="w", padx=5, pady=2)
        tk.Checkbutton(btn_chk_frame, text="2", variable=self.buttons_var, onvalue=2, offvalue=0).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(btn_chk_frame, text="4", variable=self.buttons_var, onvalue=4, offvalue=0).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(btn_chk_frame, text="6", variable=self.buttons_var, onvalue=6, offvalue=0).pack(side=tk.LEFT, padx=2)

        self.bool_vars["LRbuttons"] = tk.BooleanVar()
        # tk.Checkbutton(edit_frame, text="LRbuttons(6버튼일때 R1 L1 사용)", variable=self.bool_vars["LRbuttons"]).grid(row=13, column=1, sticky="w", padx=5, pady=2)

        # tk.Label(edit_frame, text="developer").grid(row=14, column=0, sticky="e", padx=2)
        self.entries["developer"] = ttk.Combobox(edit_frame, values=self.dev_list, width=35)
        # self.entries["developer"].grid(row=14, column=1, sticky="ew", padx=5, pady=2)

        # 이미지 미리보기
        img_container = tk.Frame(mid_frame, bd=1, relief="sunken", bg="white", height=170)
        img_container.pack(fill=tk.X, pady=5)
        img_container.pack_propagate(False)
        self.img_label = tk.Label(img_container, text="미리보기", bg="white")
        self.img_label.pack(expand=True, fill=tk.BOTH)

        # 마키 이미지 미리보기
        marquee_container = tk.Frame(mid_frame, bd=1, relief="sunken", bg="black", height=80)
        marquee_container.pack(fill=tk.X, pady=(0, 5))
        marquee_container.pack_propagate(False)
        self.marquee_label = tk.Label(marquee_container, text="마키 이미지", bg="black", fg="white")
        self.marquee_label.pack(expand=True, fill=tk.BOTH)

        # 버전 + 하단 버튼
        version_frame = tk.Frame(mid_frame)
        version_frame.pack(fill=tk.X, pady=(0, 2))
        tk.Label(version_frame, textvariable=self.version_var, font=("Malgun Gothic", 9, "bold"), fg="#1976d2").pack(side=tk.RIGHT)

        btn_frame = tk.Frame(mid_frame)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="새로운게임추가", command=self.add_new_game, bg="#c8e6c9").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btn_frame, text="복사", command=self.copy_item, bg="#e1f5fe").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btn_frame, text="적용", command=self.apply_changes, bg="#e8f5e9").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btn_frame, text="삭제", command=self.delete_item, bg="#ffebee").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        #batch_btn_frame = tk.Frame(mid_frame)
        #batch_btn_frame.pack(fill=tk.X, pady=(2, 0))
        #tk.Button(batch_btn_frame, text="모든 year=0", command=self.batch_set_year, bg="#fff3e0").#pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        #tk.Button(batch_btn_frame, text="모든 developer=''", command=self.batch_set_dev, #bg="#e0f7fa").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # --- Description (게임 설명) ---
        desc_label_frame = tk.LabelFrame(self.paned_win, text="Description", pady=5)
        self.paned_win.add(desc_label_frame, minsize=150, stretch="always")

        desc_text_frame = tk.Frame(desc_label_frame)
        desc_text_frame.pack(fill=tk.BOTH, expand=True)

        self.entries["desc"] = tk.Text(
            desc_text_frame,
            font=("Malgun Gothic", 9),
            wrap=tk.WORD,
            undo=True,
            width=15,
        )
        desc_yscroll = tk.Scrollbar(desc_text_frame, command=self.entries["desc"].yview)
        self.entries["desc"].configure(yscrollcommand=desc_yscroll.set)

        desc_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.entries["desc"].pack(fill=tk.BOTH, expand=True)

        # --- 3열: Cheat Data ---
        cheat_frame = tk.LabelFrame(self.paned_win, text="Cheat Data", pady=5)
        self.paned_win.add(cheat_frame, minsize=150, stretch="always")

        # 치트 텍스트 + 스크롤바
        cheat_text_frame = tk.Frame(cheat_frame)
        cheat_text_frame.pack(fill=tk.BOTH, expand=True)

        self.cheat_text = tk.Text(
            cheat_text_frame,
            font=("Consolas", 9),
            wrap=tk.NONE,
            undo=True,
            width=15,
        )
        cheat_yscroll = tk.Scrollbar(cheat_text_frame, command=self.cheat_text.yview)
        cheat_xscroll = tk.Scrollbar(cheat_text_frame, orient=tk.HORIZONTAL, command=self.cheat_text.xview)
        self.cheat_text.configure(yscrollcommand=cheat_yscroll.set, xscrollcommand=cheat_xscroll.set)

        cheat_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        cheat_xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.cheat_text.pack(fill=tk.BOTH, expand=True)

        # Cheat 찾기/바꾸기 프레임
        cheat_replace_frame = tk.Frame(cheat_frame)
        cheat_replace_frame.pack(fill=tk.X, pady=(2, 0))
        
        tk.Label(cheat_replace_frame, text="찾을문자:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.cheat_find_entry = tk.Entry(cheat_replace_frame, width=8)
        self.cheat_find_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        tk.Label(cheat_replace_frame, text="바꿀문자:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT)
        self.cheat_replace_entry = tk.Entry(cheat_replace_frame, width=8)
        self.cheat_replace_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        tk.Button(
            cheat_replace_frame, 
            text="모두변경", 
            command=self.cheat_replace_all, 
            bg="#f0f0f0", 
            font=("Malgun Gothic", 8)
        ).pack(side=tk.LEFT, padx=2)

        # 저장 버튼
        cheat_btn_frame = tk.Frame(cheat_frame)
        cheat_btn_frame.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            cheat_btn_frame,
            text="검색",
            command=self.open_cheat_search,
            bg="#f0f0f0",
            font=("Malgun Gothic", 9)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(
            cheat_btn_frame,
            text="cheat.dat 저장",
            command=self.save_cheat_dat,
            bg="#fff9c4",
            font=("Malgun Gothic", 9, "bold")
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # --- 4열: Command Data ---
        cmd_frame = tk.LabelFrame(self.paned_win, text="Command Data", pady=5)
        self.paned_win.add(cmd_frame, minsize=150, stretch="always")

        cmd_text_frame = tk.Frame(cmd_frame)
        cmd_text_frame.pack(fill=tk.BOTH, expand=True)

        self.command_text = tk.Text(
            cmd_text_frame,
            font=("Consolas", 9),
            wrap=tk.NONE,
            undo=True,
            width=15,
        )
        cmd_yscroll = tk.Scrollbar(cmd_text_frame, command=self.command_text.yview)
        cmd_xscroll = tk.Scrollbar(cmd_text_frame, orient=tk.HORIZONTAL, command=self.command_text.xview)
        self.command_text.configure(yscrollcommand=cmd_yscroll.set, xscrollcommand=cmd_xscroll.set)

        cmd_yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        cmd_xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.command_text.pack(fill=tk.BOTH, expand=True)

        cmd_btn_frame = tk.Frame(cmd_frame)
        cmd_btn_frame.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            cmd_btn_frame,
            text="검색",
            command=self.open_command_search,
            bg="#f0f0f0",
            font=("Malgun Gothic", 9)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(
            cmd_btn_frame,
            text="command.dat 저장",
            command=self.save_command_dat,
            bg="#e8f4ff",
            font=("Malgun Gothic", 9, "bold")
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    def bind_paste_cleaning(self):
        """모든 입력 위젯에 붙여넣기 클리닝 바인딩"""
        widgets = [self.key_entry, self.cheat_text, self.command_text] + list(self.entries.values())
        for w in widgets:
            if getattr(w, "bind", None):
                w.bind("<Control-v>", self.on_paste)
                w.bind("<Shift-Insert>", self.on_paste)

    def on_paste(self, event):
        """붙여넣기 시 '출처' 이후 문구 자동 제거 및 줄바꿈 보정"""
        try:
            text = self.root.clipboard_get()
            if "출처" in text:
                text = text.split("출처")[0].strip()
            
            # 윈도우/맥/웹 등에서 복사한 줄바꿈 문자를 표준 \n으로 강제 통일
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            
            widget = event.widget
            if isinstance(widget, tk.Text):
                try: widget.delete("sel.first", "sel.last")
                except: pass
                widget.insert(tk.INSERT, text)
            elif isinstance(widget, (tk.Entry, ttk.Combobox, tk.Spinbox)):
                # 한 줄 입력창인 경우 붙여넣을 때 줄바꿈을 공백으로 교체 (한줄로 쭉 이어지게 방어)
                text = text.replace("\n", " ").strip()
                try: widget.delete("sel.first", "sel.last")
                except: pass
                widget.insert(tk.INSERT, text)
            
            return "break" # 기본 붙여넣기 동작 방지
        except:
            pass # 클립보드가 비어있거나 오류 시 기본 동작 수행

    def clean_url_input(self, event):
        """파일명만 입력하면 전체 경로로 자동 완성 (붙여넣기 대응)"""
        widget = event.widget
        val = widget.get().strip()
        if val and not val.startswith("http"):
            # 입력된 값이 파일명뿐이라면 기본 경로를 앞에 붙임
            import os
            filename = os.path.basename(val)
            sys_val = self.entries.get("system")
            sys_str = sys_val.get().strip() if sys_val else "ekmame"
            if sys_str in ["ekmame", "fbneo"]:
                prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
            else:
                prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_str}/"
            full_url = f"{prefix}{filename}"
            widget.delete(0, tk.END)
            widget.insert(0, full_url)

    def update_listbox(self):
        self.listbox.delete(0, tk.END)

        if getattr(self, "show_duplicates_mode", False):
            self._render_duplicates_list()
            return

        # 장르 필터 콤보박스 목록 갱신
        all_genres = sorted(set(
            v.get("genre", "") for v in self.data.values() if v.get("genre")
        ))
        cb_values = ["전체"] + all_genres
        self.genre_filter_cb["values"] = cb_values
        if self.genre_filter_var.get() not in cb_values:
            self.genre_filter_var.set("전체")

        # 시스템 필터 콤보박스 목록 갱신
        if hasattr(self, 'system_filter_cb'):
            all_systems = sorted(set(
                v.get("system", "") for v in self.data.values() if v.get("system")
            ))
            sys_values = ["전체"] + all_systems
            self.system_filter_cb["values"] = sys_values
            if self.system_filter_var.get() not in sys_values:
                self.system_filter_var.set("전체")

        # 카테고리 필터 콤보박스 목록 갱신
        if hasattr(self, 'category_filter_cb'):
            all_categories = sorted(set(
                v.get("category", "") for v in self.data.values() if v.get("category")
            ))
            cat_values = ["전체"] + all_categories
            self.category_filter_cb["values"] = cat_values
            if self.category_filter_var.get() not in cat_values:
                self.category_filter_var.set("전체")

        selected_genre = self.genre_filter_var.get()
        selected_system = self.system_filter_var.get() if hasattr(self, 'system_filter_var') else "전체"
        selected_category = self.category_filter_var.get() if hasattr(self, 'category_filter_var') else "전체"
        selected_orient = self.orient_filter_var.get()

        def item_match(key):
            d = self.data[key]
            # 장르 필터
            if selected_genre != "전체" and d.get("genre", "") != selected_genre:
                return False
            # 시스템 필터
            if selected_system != "전체" and d.get("system", "") != selected_system:
                return False
            # 카테고리 필터
            if selected_category != "전체" and d.get("category", "") != selected_category:
                return False
            # 화면 방향 필터
            if selected_orient == "세로" and not d.get("portrait", False):
                return False
            if selected_orient == "가로" and d.get("portrait", False):
                return False
            return True

        parents = [k for k, v in self.data.items() if not v.get("parent")]
        clones  = [k for k, v in self.data.items() if v.get("parent")]
        shown = 0
        for p in parents:
            children_match = [c for c in clones if self.data[c].get("parent") == p and item_match(c)]
            if not item_match(p) and not children_match:
                continue
            if item_match(p):
                self.listbox.insert(tk.END, p)
                shown += 1
                if p in self.newly_added_keys:
                    self.listbox.itemconfig(self.listbox.size() - 1, {'fg': 'blue', 'bg': '#e6f7ff'})
            for c in children_match:
                self.listbox.insert(tk.END, f"   └─ {c}")
                shown += 1
                if c in self.newly_added_keys:
                    self.listbox.itemconfig(self.listbox.size() - 1, {'fg': 'blue', 'bg': '#e6f7ff'})

        self.count_var.set(f"{shown}개")
        self.update_version_display()

    def load_image(self, key):
        """GitHub에서 이미지를 가져와서 UI 크기에 맞게 조절"""
        try:
            encoded_key = urllib.parse.quote(key)
            img_url = f"{self.img_base}{encoded_key}.png"
            try:
                with urllib.request.urlopen(img_url) as url:
                    img_data = url.read()
            except:
                jpg_url = f"{self.img_base}{encoded_key}.jpg"
                with urllib.request.urlopen(jpg_url) as url:
                    img_data = url.read()
            
            img = Image.open(BytesIO(img_data))
            
            # UI가 커지는 것을 막기 위해 최대 크기를 200x150 정도로 제한
            # 슬림한 UI를 원하신다면 이 수치를 더 줄이셔도 됩니다.
            img.thumbnail((250, 150)) 
            
            self.photo = ImageTk.PhotoImage(img)
            self.img_label.config(image=self.photo, text="")
        except:
            # 이미지가 없거나 로드 실패 시 공간을 최소화
            self.img_label.config(image="", text="이미지 없음")

    def load_marquee_image(self, key):
        """GitHub에서 마키 이미지를 가져와서 UI 크기에 맞게 조절"""
        try:
            encoded_key = urllib.parse.quote(key)
            marquee_url = f"{self.marquee_base}{encoded_key}.png"
            try:
                with urllib.request.urlopen(marquee_url) as url:
                    img_data = url.read()
            except:
                marquee_jpg_url = f"{self.marquee_base}{encoded_key}.jpg"
                with urllib.request.urlopen(marquee_jpg_url) as url:
                    img_data = url.read()
            
            img = Image.open(BytesIO(img_data))
            
            # 마키 이미지의 특성에 맞게 가로로 길게 조절
            img.thumbnail((350, 75)) 
            
            self.marquee_photo = ImageTk.PhotoImage(img)
            self.marquee_label.config(image=self.marquee_photo, text="")
        except:
            self.marquee_label.config(image="", text="마키 없음")

    def show_scrollable_info(self, title, message):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("500x300")
        
        self.root.update_idletasks()
        width = 500
        height = 300
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        top.geometry(f"{width}x{height}+{x}+{y}")
        
        txt = tk.Text(top, wrap=tk.WORD, padx=10, pady=10)
        scroll = tk.Scrollbar(top, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        
        txt.insert("1.0", message)
        txt.config(state=tk.DISABLED)
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(expand=True, fill=tk.BOTH)
        
        btn = tk.Button(top, text="확인", command=top.destroy)
        btn.pack(pady=5)

    def update_version_display(self):
        """UI에 현재 updates.json의 버전 표시"""
        updates_path = os.path.join(self.base_dir, "update", "updates.json")
        game_count = len(self.data) if hasattr(self, 'data') else 0
        if os.path.exists(updates_path):
            with open(updates_path, 'r', encoding='utf-8') as f:
                try:
                    updates_data = json.load(f)
                    version = updates_data.get("support_game_list.json", "-")
                    self.version_var.set(f"Version: {version} (총 게임 수: {game_count})")
                except:
                    self.version_var.set(f"Version: Error (총 게임 수: {game_count})")
        else:
            self.version_var.set(f"Version: N/A (총 게임 수: {game_count})")

    def update_json_version(self):
        """update/updates.json 갱신 및 UI 표시"""
        import datetime
        import shutil

        updates_path = os.path.join(self.base_dir, "update", "updates.json")
        updates_data = {}

        # 1. 파일 읽기 및 예외 처리
        if os.path.exists(updates_path):
            with open(updates_path, 'r', encoding='utf-8') as f:
                try:
                    updates_data = json.load(f)
                except json.JSONDecodeError:
                    # 파일이 깨진 경우 기존 파일을 .bak로 백업하여 데이터 보존
                    shutil.copy(updates_path, updates_path + ".bak")
                    updates_data = {}

        # 2. 날짜 및 버전 계산
        today = datetime.datetime.now().strftime("%Y%m%d")
        current_val = str(updates_data.get("support_game_list.json", ""))

        new_val = today
        if current_val.startswith(today):
            # 오늘 이미 업데이트된 경우 접미사 숫자를 올림
            if "_" in current_val:
                # "_"가 여러 개 들어있을 경우를 대비해 rsplit 사용
                parts = current_val.rsplit("_", 1)
                try:
                    new_val = f"{today}_{int(parts[1]) + 1}"
                except (ValueError, IndexError):
                    new_val = f"{today}_1"
            else:
                new_val = f"{today}_1"

        # 3. 데이터 갱신 (기존 key-value는 그대로 유지)
        updates_data["support_game_list.json"] = new_val

        # 4. 폴더 생성 및 저장
        os.makedirs(os.path.dirname(updates_path), exist_ok=True)
        with open(updates_path, 'w', encoding='utf-8') as f:
            json.dump(updates_data, f, indent=4, ensure_ascii=False)

        self.update_version_display()

