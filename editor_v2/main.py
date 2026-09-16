import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk


from mixins.ui_setup import UiSetupMixin
from mixins.data_ops import DataOpsMixin
from mixins.list_ops import ListOpsMixin
from mixins.cheat_ops import CheatOpsMixin
from mixins.command_ops import CommandOpsMixin
from mixins.search_dialog import SearchDialogMixin
from mixins.misc_ops import MiscOpsMixin

class GameJsonEditor(
    UiSetupMixin, DataOpsMixin, ListOpsMixin, CheatOpsMixin, CommandOpsMixin, SearchDialogMixin, MiscOpsMixin
):
    def __init__(self, root):
        self.root = root
        self.root.title("EK Launcher - Advanced Editor")
        self.data = {}
        self.file_path = ""
        self.base_dir = self.get_base_dir()
        self.default_base = "https://github.com/WOOSEOK99/my-repo/blob/main/files/"
        self.img_base = "https://raw.githubusercontent.com/WOOSEOK99/my-Images/main/"
        self.marquee_base = "https://wooseok99.github.io/my-mrq/marquee/"
        
        # 자동 완성을 위한 사전 정의 데이터
        self.default_genres = ["슈팅", "액션", "벨트스크롤 액션", "격투", "퍼즐", "스포츠", "레이싱"]
        self.default_devs = ["캡콤", "나즈카", "SNK", "세가", "타이토", "코나미", "데이터 이스트"]
        self.genre_list = list(self.default_genres)
        self.genre_en_list = []
        self.dev_list = list(self.default_devs)
        self.series_list = []
        self.parent_list = []
        self.category_list = ["arcade", "console"]
        self.version_var = tk.StringVar(value="Version: -")
        
        # 검색 관련 상태
        self.search_results = []
        self.current_search_index = -1
        self.search_info_var = tk.StringVar(value="0/0")

        # cheat.dat 관련 상태
        self.cheat_dat_path = os.path.join(self.get_base_dir(), "support", "cheat.dat")
        self.cheat_cache = None  # {romkey: [line, ...]} 캐시 (최초 1회 파싱)

        # command.dat 관련 상태
        self.command_dat_path = os.path.join(self.get_base_dir(), "support", "command.dat")
        self.command_cache = None  # {romkey: str} 캐시 (최초 1회 파싱)
        
        self.newly_added_keys = set()

        self.setup_ui()
        self.bind_paste_cleaning()
        self.auto_load_default()

    def get_base_dir(self):
        import sys
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1450x700")
    app = GameJsonEditor(root)
    root.mainloop()
