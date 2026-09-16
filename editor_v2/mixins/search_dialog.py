import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


class SearchDialogMixin:
    def open_cheat_search(self):
        self._open_dat_search("cheat.dat 검색", "cheat_cache", self._parse_cheat_dat)

    def open_command_search(self):
        self._open_dat_search("command.dat 검색", "command_cache", self._parse_command_dat)

    def _open_dat_search(self, title, cache_attr, parse_method):
        cache = getattr(self, cache_attr)
        if cache is None:
            parse_method()
            cache = getattr(self, cache_attr)

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x400")
        
        self.root.update_idletasks()
        width = 600
        height = 400
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        dialog.transient(self.root)
        
        top_frame = tk.Frame(dialog)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(top_frame, text="Key 검색:").pack(side=tk.LEFT)
        search_entry = tk.Entry(top_frame, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.focus()
        
        text_frame = tk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        result_text = tk.Text(text_frame, font=("Consolas", 9), wrap=tk.NONE, undo=True)
        yscroll = tk.Scrollbar(text_frame, command=result_text.yview)
        xscroll = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=result_text.xview)
        result_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        result_text.pack(fill=tk.BOTH, expand=True)
        
        current_search_key = {"key": None}
        
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
                
        search_entry.bind("<Return>", do_search)
        tk.Button(top_frame, text="검색", command=do_search).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="저장", command=do_save, bg="#fff9c4", font=("Malgun Gothic", 9, "bold")).pack(side=tk.LEFT, padx=5)

