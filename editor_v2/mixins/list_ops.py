import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class ListOpsMixin:
    def perform_search(self, event=None):
        """Key(ID) 또는 Title로 검색"""
        query = self.search_entry.get().strip().lower()
        if not query:
            self.search_results = []
            self.current_search_index = -1
            self.search_info_var.set("0/0")
            return

        # 검색 결과 수집 (Key 또는 Title 매칭)
        self.search_results = []
        for key, val in self.data.items():
            title = str(val.get("title", "")).lower()
            if query in key.lower() or query in title:
                self.search_results.append(key)
        
        if self.search_results:
            self.current_search_index = 0
            self.update_search_display()
        else:
            self.current_search_index = -1
            self.search_info_var.set("0/0")
            messagebox.showinfo("검색", "검색 결과가 없습니다.")

    def go_next_search(self):
        """다음 검색 결과로 이동"""
        if not self.search_results:
            return
        
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self.update_search_display()

    def update_search_display(self):
        """현재 검색 결과 선택 및 정보 갱신"""
        idx = self.current_search_index
        total = len(self.search_results)
        self.search_info_var.set(f"{idx + 1}/{total}")
        
        key = self.search_results[idx]
        self.select_listbox_key(key)
        # on_select를 수동으로 호출하여 데이터 로드
        self.on_select(None)

    def select_listbox_key(self, key):
        """Listbox에서 해당 Key(부모/자식 무관)를 찾아 선택"""
        for idx in range(self.listbox.size()):
            lb_text = self.listbox.get(idx).replace("   └─ ", "").strip()
            if lb_text == key:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(idx)
                self.listbox.activate(idx)
                self.listbox.see(idx)
                return

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        raw_text = self.listbox.get(sel[0])
        selected_key = raw_text.replace("   └─ ", "").strip()
        self.current_selected_key = selected_key
        item_data = self.data.get(selected_key)
        
        self.key_entry.delete(0, tk.END)
        self.key_entry.insert(0, selected_key)

        for field, widget in self.entries.items():
            if isinstance(widget, (tk.Entry, ttk.Combobox, tk.Spinbox)):
                widget.delete(0, tk.END)
                widget.insert(0, str(item_data.get(field, "")))
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                text_val = str(item_data.get(field, ""))
                if field == "desc":
                    text_val = text_val.replace("\\n", "\n")
                widget.insert("1.0", text_val)
        
        for field in self.bool_vars:
            self.bool_vars[field].set(item_data.get(field, False))
            
        self.buttons_var.set(int(item_data.get("buttons") or 0))

        self.load_image(selected_key)
        self.load_marquee_image(selected_key)
        self.load_cheat_data(selected_key)
        self.load_command_data(selected_key)

    def apply_changes(self):
        """데이터 업데이트 시 URL 형식 확인"""
        if not self.listbox.curselection():
            if not self.current_selected_key:
                return
            selected_key = self.current_selected_key
        else:
            raw_text = self.listbox.get(self.listbox.curselection()[0])
            selected_key = raw_text.replace("   └─ ", "").strip()

        # Key 변경 처리
        new_key = self.key_entry.get().strip()
        if not new_key:
            messagebox.showwarning("경고", "Key (ID) 값은 비워둘 수 없습니다.", parent=self.root)
            return
            
        if new_key != selected_key:
            if new_key in self.data:
                confirm = messagebox.askyesno("덮어쓰기 확인", f"'{new_key}' 키가 이미 존재합니다. 기존 데이터를 이 내용으로 덮어쓰시겠습니까?", parent=self.root)
                if not confirm:
                    # 원래 Key 값으로 입력칸 복구
                    self.key_entry.delete(0, tk.END)
                    self.key_entry.insert(0, selected_key)
                    return
            # Key 이름 변경
            self.data[new_key] = self.data.pop(selected_key)
            if selected_key in self.newly_added_keys:
                self.newly_added_keys.remove(selected_key)
                self.newly_added_keys.add(new_key)
            # 자식 게임들의 parent 참조 업데이트
            for k, v in self.data.items():
                if v.get("parent") == selected_key:
                    v["parent"] = new_key
            self.current_selected_key = new_key
            selected_key = new_key
            # 목록 갱신
            self.refresh_all_lists()
            self.update_listbox()
            self.select_listbox_key(selected_key)

        for field, widget in self.entries.items():
            if isinstance(widget, tk.Text):
                val = widget.get("1.0", tk.END).strip()
                if field == "desc":
                    # UI의 실제 줄바꿈을 JSON 저장 시 문자열 '\n'으로 자동 변환 (붙여넣기)
                    val = val.replace("\n", "\\n")
            else:
                val = widget.get().strip()
            
            # url 필드인데 파일명만 있다면 전체 경로로 보정 후 저장
            if field == "url" and val and not val.startswith("http"):
                import os
                sys_val = self.entries.get("system")
                sys_str = sys_val.get().strip() if sys_val else "ekmame"
                if sys_str in ["ekmame", "fbneo"]:
                    prefix = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
                else:
                    prefix = f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{sys_str}/"
                val = f"{prefix}{os.path.basename(val)}"
            
            # 숫자형 변환
            if field in ["year"]:
                try: val = int(val)
                except: val = 0
                
            self.data[selected_key][field] = val
            
        self.data[selected_key]["buttons"] = self.buttons_var.get()
        
        for field in self.bool_vars:
            self.data[selected_key][field] = self.bool_vars[field].get()
        
        self.refresh_all_lists()
        
        self.select_listbox_key(selected_key)
        messagebox.showinfo("완료", "데이터가 전체 경로 형식으로 업데이트되었습니다.", parent=self.root)

    def refresh_series_list(self):
        series_values = sorted({
            str(v.get("series", "")).strip()
            for v in self.data.values()
            if v.get("series")
        })
        self.series_list = series_values
        if "series" in self.entries:
            self.entries["series"]["values"] = self.series_list

    def refresh_parent_list(self):
        parent_values = sorted({
            str(v.get("parent", "")).strip()
            for v in self.data.values()
            if v.get("parent")
        })
        self.parent_list = parent_values
        if "parent" in self.entries:
            self.entries["parent"]["values"] = self.parent_list

    def refresh_genre_list(self):
        genres = set(self.default_genres) # 기존 기본값 유지하며 추가
        for v in self.data.values():
            g = str(v.get("genre", "")).strip()
            if g:
                genres.add(g)
        self.genre_list = sorted(list(genres))
        if "genre" in self.entries:
            self.entries["genre"]["values"] = self.genre_list

    def refresh_genre_en_list(self):
        genres_en = set()
        for v in self.data.values():
            g = str(v.get("genre_en", "")).strip()
            if g:
                genres_en.add(g)
        self.genre_en_list = sorted(list(genres_en))
        if "genre_en" in self.entries:
            self.entries["genre_en"]["values"] = self.genre_en_list

    def refresh_developer_list(self):
        devs = set(self.default_devs) # 기존 기본값 유지하며 추가
        for v in self.data.values():
            d = str(v.get("developer", "")).strip()
            if d:
                devs.add(d)
        self.dev_list = sorted(list(devs))
        if "developer" in self.entries:
            self.entries["developer"]["values"] = self.dev_list

    def refresh_category_list(self):
        categories = set(["arcade", "console"])
        for v in self.data.values():
            c = str(v.get("category", "")).strip()
            if c:
                categories.add(c)
        self.category_list = sorted(list(categories))
        if "category" in self.entries:
            self.entries["category"]["values"] = self.category_list

    def refresh_all_lists(self):
        self.refresh_series_list()
        self.refresh_parent_list()
        self.refresh_genre_list()
        self.refresh_genre_en_list()
        self.refresh_developer_list()
        self.refresh_category_list()

    def toggle_duplicate_mode(self):
        """중복 title 모드 ON/OFF 토글"""
        self.show_duplicates_mode = not getattr(self, "show_duplicates_mode", False)
        
        if self.show_duplicates_mode:
            self.duplicate_btn.config(text="일반 목록으로 돌아가기", fg="red")
            messagebox.showinfo("안내", "title이 중복된 게임들을 찾아서 리스트에 표시합니다.", parent=self.root)
        else:
            self.duplicate_btn.config(text="중복 title 모아보기", fg="purple")
            
        self.update_listbox()

    def _render_duplicates_list(self):
        """중복된 title을 가진 게임들만 찾아서 리스트박스에 렌더링"""
        # 1. title 그룹화
        title_groups = {}
        for k, v in self.data.items():
            title = str(v.get("title", "")).strip()
            if title:
                if title not in title_groups:
                    title_groups[title] = []
                title_groups[title].append(k)
                
        # 2. 중복된 title 추출
        duplicate_titles = {t: keys for t, keys in title_groups.items() if len(keys) > 1}
        
        if not duplicate_titles:
            self.count_var.set("중복: 0개")
            # 강제로 중복 모드 해제
            self.show_duplicates_mode = False
            self.duplicate_btn.config(text="중복 title 모아보기", fg="purple")
            self.update_listbox()
            messagebox.showinfo("결과", "중복된 title이 없습니다.", parent=self.root)
            return

        # 3. 리스트박스에 중복된 게임들만 추가 (title 순 정렬)
        shown = 0
        for title in sorted(duplicate_titles.keys()):
            keys = duplicate_titles[title]
            for k in keys:
                self.listbox.insert(tk.END, k)
                # 같은 타이틀끼리 묶여 보이도록 표시 (파란색 등)
                self.listbox.itemconfig(self.listbox.size() - 1, {'fg': 'purple'})
                shown += 1
                
        self.count_var.set(f"중복: {shown}개")

    def extract_current_titles(self):
        """현재 리스트박스에 보이는 항목들의 title만 추출하여 팝업으로 표시"""
        titles = []
        for idx in range(self.listbox.size()):
            raw_text = self.listbox.get(idx)
            key = raw_text.replace("   └─ ", "").strip()
            item_data = self.data.get(key, {})
            title = item_data.get("title", "")
            if title:
                titles.append(title)
            else:
                titles.append(f"(No Title: {key})")
        
        result_text = "\n".join(titles)
        if not result_text:
            messagebox.showinfo("결과", "추출할 제목이 없습니다.", parent=self.root)
            return
            
        self.show_scrollable_info(f"현재 목록 타이틀 추출 (총 {len(titles)}개)", result_text)

    def compare_keys_with_txt(self):
        """TXT 파일의 Key 목록과 현재 게임 목록의 Key를 비교하여 diff_key.txt 저장"""
        if not self.data:
            messagebox.showwarning("경고", "먼저 게임 목록을 불러오세요.", parent=self.root)
            return

        txt_path = filedialog.askopenfilename(
            title="비교할 Key 목록 TXT 파일 선택",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not txt_path:
            return

        try:
            with open(txt_path, 'r', encoding='utf-8-sig') as f:
                txt_keys = set(line.strip() for line in f if line.strip())
        except Exception as e:
            messagebox.showerror("오류", f"파일을 읽는 중 오류가 발생했습니다.\n{e}", parent=self.root)
            return

        game_keys = set(self.data.keys())

        # txt에는 있는데 게임 목록에 없는 key
        only_in_txt = sorted(txt_keys - game_keys)
        # 게임 목록에는 있는데 txt에 없는 key
        only_in_game = sorted(game_keys - txt_keys)

        if not only_in_txt and not only_in_game:
            messagebox.showinfo("결과", "두 목록의 Key가 완전히 일치합니다. 차이가 없습니다.", parent=self.root)
            return

        lines = []
        lines.append(f"[비교 파일] {os.path.basename(txt_path)}")
        lines.append(f"[TXT Key 수] {len(txt_keys)}개  /  [게임 목록 Key 수] {len(game_keys)}개")
        lines.append("")
        lines.append(f"=== TXT에만 있고 게임 목록에 없는 Key ({len(only_in_txt)}개) ===")
        lines.extend(only_in_txt if only_in_txt else ["(없음)"])
        lines.append("")
        lines.append(f"=== 게임 목록에만 있고 TXT에 없는 Key ({len(only_in_game)}개) ===")
        lines.extend(only_in_game if only_in_game else ["(없음)"])

        result_text = "\n".join(lines)

        # diff_key.txt 저장 위치 = base_dir
        save_path = os.path.join(self.base_dir, "diff_key.txt")
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(result_text)
        except Exception as e:
            messagebox.showerror("오류", f"diff_key.txt 저장 중 오류가 발생했습니다.\n{e}", parent=self.root)
            return

        self.show_scrollable_info(
            f"Key 비교 결과 (차이: TXT전용 {len(only_in_txt)}개 / 게임전용 {len(only_in_game)}개)",
            result_text
        )
        messagebox.showinfo(
            "저장 완료",
            f"diff_key.txt 가 저장되었습니다.\n경로: {save_path}",
            parent=self.root
        )
