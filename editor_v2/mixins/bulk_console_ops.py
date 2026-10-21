"""콘솔 ZIP 일괄 등록. 원본을 건드리지 않고 미리보기 후 선택 항목만 복사한다."""
import os
import posixpath
import queue
import random
import re
import shutil
import string
import threading
import unicodedata
import webbrowser
import zipfile
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from mixins.genre_lookup import GENRES, GENRE_EN, lookup_genre
from mixins.libretro_genre import lookup_libretro

CONSOLES = ("snes", "nes", "genesis", "gba")
ROM_EXTENSIONS = {
    "snes": (".sfc", ".smc", ".fig", ".swc"),
    "nes": (".nes", ".fds"),
    "genesis": (".bin", ".gen", ".md", ".smd"),
    "gba": (".gba",),
}
CHEAT_DIRS = {
    "snes": "snescheats",
    "nes": "nescheats",
    "genesis": "genesischeats",
    "gba": "gbacheats",
}
SNAP_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")


def _without_regions(name):
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)|\[[^]]*\]", " ", name)).strip(" _-")


def _match_key(name):
    name = unicodedata.normalize("NFKC", _without_regions(name)).casefold()
    return re.sub(r"[\W_]+", "", name, flags=re.UNICODE)


def _slug(title):
    return re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")[:55]


def _files_in(folder, extensions):
    if not folder:
        return []
    return sorted(
        (os.path.join(folder, name) for name in os.listdir(folder)
         if os.path.isfile(os.path.join(folder, name))
         and os.path.splitext(name)[1].casefold() in extensions),
        key=lambda s: s.casefold(),
    )


def _find_asset(files, aliases):
    """Exact stem first; then allow region-free match only when unique."""
    for alias in aliases:
        if not alias:
            continue
        found = [p for p in files if os.path.splitext(os.path.basename(p))[0].casefold() == alias.casefold()]
        if len(found) == 1:
            return found[0], ""
        if len(found) > 1:
            return None, "동일한 이름의 파일이 여러 개입니다."
    for alias in aliases:
        if not alias:
            continue
        found = [p for p in files if _match_key(os.path.splitext(os.path.basename(p))[0]) == _match_key(alias)]
        if len(found) == 1:
            return found[0], ""
        if len(found) > 1:
            return None, "지역명 제외 후 여러 파일이 일치합니다."
    return None, ""


def _english_from_zip(path, system):
    with zipfile.ZipFile(path) as archive:
        candidates = [
            item for item in archive.infolist()
            if not item.is_dir()
            and not item.filename.startswith("__MACOSX/")
            and posixpath.splitext(item.filename)[1].casefold() in ROM_EXTENSIONS[system]
        ]
        if not candidates:
            return "", "ZIP 내부에 해당 기종의 ROM이 없습니다."
        chosen = max(candidates, key=lambda item: item.file_size)
        stem = posixpath.splitext(posixpath.basename(chosen.filename))[0]
        return _without_regions(stem), ("ZIP에 ROM 파일이 여러 개 있습니다." if len(candidates) > 1 else ""), chosen.CRC


def _copy_exclusive(source, target):
    """Never overwrite an existing destination; remove partial copies on error."""
    created = False
    try:
        with open(source, "rb") as src, open(target, "xb") as dst:
            created = True
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    except Exception:
        if created:
            try:
                os.remove(target)
            except OSError:
                pass
        raise


class BulkConsoleMixin:
    def setup_ui(self):
        super().setup_ui()
        menu = self.root.nametowidget(self.root.cget("menu"))
        menu.add_separator()
        menu.add_command(label="콘솔 일괄 등록", command=self.open_bulk_console)

    def open_bulk_console(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("콘솔 일괄 등록 (미리보기 후 등록)")
        dialog.geometry("1250x690")
        dialog.transient(self.root)
        dialog.grab_set()

        system_var = tk.StringVar(value="snes")
        rom_var = tk.StringVar()
        snap_var = tk.StringVar()
        cheat_var = tk.StringVar()
        progress_var = tk.StringVar(value="폴더를 지정한 뒤 '분석 / 장르 조회'를 누르세요.")
        tasks = queue.Queue()
        cancelled = threading.Event()
        rows = []
        scanning = [False]

        def close():
            cancelled.set()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", close)
        top = ttk.Frame(dialog, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="기종:").grid(row=0, column=0, sticky="w")
        system_cb = ttk.Combobox(top, textvariable=system_var, values=CONSOLES, state="readonly", width=14)
        system_cb.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(top, text="category = console (자동 적용)").grid(row=0, column=2, sticky="w", padx=10)
        top.columnconfigure(1, weight=1)

        for position, (caption, variable) in enumerate(
            (("ROM ZIP 폴더 (필수)", rom_var),
             ("스냅샷 폴더 (선택)", snap_var),
             ("치트 .cht 폴더 (선택)", cheat_var)), start=1
        ):
            ttk.Label(top, text=caption).grid(row=position, column=0, sticky="w", pady=3)
            ttk.Entry(top, textvariable=variable).grid(
                row=position, column=1, columnspan=2, sticky="ew", padx=5
            )

            def choose(v=variable):
                directory = filedialog.askdirectory(parent=dialog, title="폴더 선택")
                if directory:
                    v.set(directory)

            ttk.Button(top, text="폴더 선택", command=choose).grid(row=position, column=3, padx=4)

        ttk.Label(top, text="ROM ZIP 내부 파일명 → 영문 제목 | ROM ZIP 파일명에서 괄호 제거 → 한글 제목").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=5
        )

        table_frame = ttk.Frame(dialog, padding=(8, 0, 8, 0))
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("use", "key", "title", "english", "genre", "snap", "cheat", "status")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in (
            ("use", "등록", 50), ("key", "Key(ID)", 135), ("title", "한글 제목", 180),
            ("english", "영문 제목", 185), ("genre", "장르", 95),
            ("snap", "스냅샷", 75), ("cheat", "치트", 60), ("status", "상태", 300),
        ):
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=45, stretch=(col in ("title", "english", "status")))
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll = ttk.Scrollbar(table_frame, command=tree.yview)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=vscroll.set)

        ttk.Label(dialog, textvariable=progress_var, padding=(8, 6)).pack(fill=tk.X)
        footer = ttk.Frame(dialog, padding=8)
        footer.pack(fill=tk.X)

        def errors(row):
            problems = list(row["problems"])
            if not re.fullmatch(r"[a-z0-9]{15}", row["key"]):
                problems.append("Key는 영문 소문자·숫자 15자리여야 합니다.")
            if not row["title"]:
                problems.append("한글 제목 확인 필요")
            if not row["english"]:
                problems.append("영문 제목 확인 필요")
            if not row["genre"]:
                problems.append("장르 확인 필요")
            if row["key"] in self.data:
                problems.append("JSON에 동일 Key 존재")
            if sum(r["key"] == row["key"] for r in rows) > 1:
                problems.append("현재 목록의 Key 중복")
            return problems

        def status(row):
            bad = errors(row)
            warnings = []
            if not row["snapshot"]:
                warnings.append("스냅샷 없음")
            if not row["cheat"]:
                warnings.append("치트 없음")
            warnings.extend(row.get("notes", []))
            if row["genre_reason"] and (not row["genre"] or "확인 권장" in row["genre_reason"]):
                warnings.append(row["genre_reason"])
            return ", ".join(bad + warnings) or "등록 가능"

        def redraw():
            for item in tree.get_children():
                tree.delete(item)
            for i, row in enumerate(rows):
                tree.insert("", tk.END, iid=str(i), values=(
                    "✓" if row["selected"] else "—",
                    row["key"], row["title"], row["english"], row["genre"],
                    "있음" if row["snapshot"] else "없음",
                    "있음" if row["cheat"] else "없음",
                    status(row),
                ))
            good = sum(r["selected"] and not errors(r) for r in rows)
            progress_var.set(f"검색 {len(rows)}개 / 등록 선택 {good}개 | 행 더블클릭: 제목·Key·장르 편집")

        def worker(system, rom_dir, snap_dir, cheat_dir, existing):
            try:
                roms = _files_in(rom_dir, (".zip",))
                snaps = _files_in(snap_dir, SNAP_EXTENSIONS)
                cheats = _files_in(cheat_dir, (".cht",))
                pending = []
                keys = set(existing)
                for i, path in enumerate(roms, 1):
                    if cancelled.is_set():
                        break
                    file_stem = os.path.splitext(os.path.basename(path))[0]
                    english, zip_issue, rom_crc = "", "", None
                    try:
                        english, zip_issue, rom_crc = _english_from_zip(path, system)
                    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                        zip_issue = "ZIP 읽기 실패: " + str(exc)[:80]
                    english = english.strip()
                    title = _without_regions(file_stem)
                    aliases = (file_stem, title, english)
                    snapshot, snap_issue = _find_asset(snaps, aliases)
                    cheat, cheat_issue = _find_asset(cheats, aliases)
                    # JSON Key = ROM .bin 이름 = 스냅샷 이름 = 치트 이름
                    # 기존 데이터와 로컬 파일에 없는 무작위 15자리 값을 미리 결정한다.
                    for _ in range(100):
                        key = "".join(random.choices(string.ascii_lowercase + string.digits, k=15))
                        rom_target = os.path.join(self.base_dir, "konfiles", system, key + ".bin")
                        snapshot_target = (
                            os.path.join(os.path.dirname(snapshot),
                                         key + os.path.splitext(snapshot)[1].lower())
                            if snapshot else None
                        )
                        cheat_target = os.path.join(
                            self.base_dir, "support", CHEAT_DIRS[system], key + ".cht"
                        )
                        if (key not in keys and not os.path.exists(rom_target)
                                and not os.path.exists(cheat_target)
                                and (not snapshot_target or not os.path.exists(snapshot_target))):
                            break
                    else:
                        raise RuntimeError("중복되지 않는 15자리 Key를 생성하지 못했습니다.")
                    keys.add(key)
                    genre, libretro_title, reason, source = lookup_libretro(
                        english, system, rom_crc,
                        os.path.join(self.base_dir, "support", "libretro_genre_cache"),
                    )
                    if not genre and english:
                        web_genre, web_reason, web_source = lookup_genre(english, system)
                        if web_genre:
                            genre, reason, source = web_genre, web_reason, web_source
                        else:
                            reason = reason + " / " + web_reason
                    if not genre and not english:
                        reason = "ZIP에서 영문 제목을 추출하지 못했습니다. " + reason
                    if not english and libretro_title:
                        english = libretro_title
                    # 여러 ROM이 든 ZIP은 최대 파일의 제목을 후보로 표시하고 수동 확인한다.
                    notes = [zip_issue] if zip_issue.startswith("ZIP에 ROM 파일이 여러 개") else []
                    problems = [x for x in (zip_issue, snap_issue, cheat_issue) if x and x not in notes]
                    row = {
                        "rom": path, "system": system, "key": key, "title": title,
                        "english": english, "genre": genre, "genre_reason": reason,
                        "source": source, "snapshot": snapshot, "cheat": cheat,
                        "problems": problems, "notes": notes, "selected": bool(
                            key and title and english and genre and not problems and not notes
                            and key not in existing
                        ),
                    }
                    pending.append(row)
                    tasks.put(("progress", f"ROM 분석 / 인터넷 조회 중: {i}/{len(roms)}"))
                tasks.put(("done", pending))
            except Exception as exc:
                tasks.put(("error", str(exc)))

        def poll():
            if not dialog.winfo_exists():
                return
            try:
                while True:
                    kind, value = tasks.get_nowait()
                    if kind == "progress":
                        progress_var.set(value)
                    elif kind == "done":
                        rows[:] = value
                        scanning[0] = False
                        analyze_btn.configure(state="normal")
                        redraw()
                    elif kind == "error":
                        scanning[0] = False
                        analyze_btn.configure(state="normal")
                        progress_var.set("분석 실패: " + value)
                        messagebox.showerror("분석 오류", value, parent=dialog)
            except queue.Empty:
                pass
            dialog.after(150, poll)

        def analyze():
            if scanning[0]:
                return
            rom_dir = rom_var.get().strip()
            snap_dir = snap_var.get().strip()
            cheat_dir = cheat_var.get().strip()
            if not os.path.isdir(rom_dir):
                messagebox.showwarning("폴더 확인", "유효한 ROM ZIP 폴더를 선택하세요.", parent=dialog)
                return
            if any(folder and not os.path.isdir(folder) for folder in (snap_dir, cheat_dir)):
                messagebox.showwarning("폴더 확인", "스냅샷/치트 폴더 경로를 확인하세요.", parent=dialog)
                return
            scanning[0] = True
            rows.clear()
            redraw()
            analyze_btn.configure(state="disabled")
            progress_var.set("ROM 분석 시작...")
            threading.Thread(
                target=worker,
                args=(system_var.get(), rom_dir, snap_dir, cheat_dir, set(self.data)),
                daemon=True,
            ).start()

        def chosen_row():
            selected = tree.selection()
            return rows[int(selected[0])] if selected else None

        def edit():
            row = chosen_row()
            if not row:
                return
            editor = tk.Toplevel(dialog)
            editor.title("일괄 등록 항목 편집")
            editor.transient(dialog)
            editor.grab_set()
            vars_ = {}
            for i, (field, label) in enumerate((
                ("key", "Key(ID)"), ("title", "한글 제목"),
                ("english", "영문 제목"), ("genre", "장르"),
            )):
                ttk.Label(editor, text=label).grid(row=i, column=0, padx=8, pady=6)
                variable = tk.StringVar(value=row[field])
                vars_[field] = variable
                if field == "genre":
                    entry = ttk.Combobox(editor, textvariable=variable, values=GENRES, state="readonly", width=43)
                else:
                    entry = ttk.Entry(editor, textvariable=variable, width=45)
                entry.grid(row=i, column=1, padx=8, pady=6)
            ttk.Label(editor, text="조회 결과: " + row["genre_reason"], wraplength=440).grid(
                row=4, column=0, columnspan=2, padx=8, sticky="w"
            )

            def open_source():
                if row["source"]:
                    webbrowser.open(row["source"])

            if row["source"]:
                ttk.Button(editor, text="장르 출처 열기", command=open_source).grid(row=5, column=0, columnspan=2)

            def save():
                for field, variable in vars_.items():
                    row[field] = variable.get().strip()
                row["selected"] = not bool(errors(row))
                editor.destroy()
                redraw()

            ttk.Button(editor, text="적용", command=save).grid(row=6, column=0, columnspan=2, pady=10)

        def toggle():
            row = chosen_row()
            if not row:
                return
            if errors(row):
                messagebox.showwarning("등록 불가", ", ".join(errors(row)), parent=dialog)
                return
            row["selected"] = not row["selected"]
            redraw()

        def register():
            if scanning[0]:
                messagebox.showwarning("대기", "분석이 완료된 후 등록하세요.", parent=dialog)
                return
            if not self.file_path:
                messagebox.showwarning("JSON 필요", "먼저 메인 메뉴에서 JSON 파일을 열어주세요.", parent=dialog)
                return
            pending = [r for r in rows if r["selected"] and not errors(r)]
            if not pending:
                messagebox.showinfo("안내", "등록할 항목이 없습니다. 장르 또는 제목을 먼저 확인하세요.", parent=dialog)
                return
            if not messagebox.askyesno(
                "일괄 등록 확인",
                f"{len(pending)}개 게임을 로컬 폴더로 복사하고 현재 JSON 목록에 추가합니다.\n"
                "원본 파일은 유지됩니다. JSON 디스크 저장과 GitHub 업로드는 별도입니다.\n진행할까요?",
                parent=dialog,
            ):
                return
            done, failed = 0, []
            for row in pending:
                key = row["key"]
                if key in self.data:
                    failed.append(key + ": 중복 Key")
                    continue
                rom_dir = os.path.join(self.base_dir, "konfiles", row["system"])
                cheat_dir = os.path.join(self.base_dir, "support", CHEAT_DIRS[row["system"]])
                os.makedirs(rom_dir, exist_ok=True)
                if row["cheat"]:
                    os.makedirs(cheat_dir, exist_ok=True)
                cheat_dest = os.path.join(cheat_dir, key + ".cht") if row["cheat"] else None
                if cheat_dest and os.path.exists(cheat_dest) and (
                    os.path.abspath(cheat_dest) != os.path.abspath(row["cheat"])
                ):
                    failed.append(key + ": 같은 이름의 치트 파일이 이미 존재함")
                    continue
                created = []
                try:
                    # 미리보기에서 정한 Key를 그대로 .bin 및 스냅샷 파일명에 사용
                    basename = key
                    rom_dest = os.path.join(rom_dir, basename + ".bin")
                    snap_dest = (
                        os.path.join(os.path.dirname(row["snapshot"]),
                                     basename + os.path.splitext(row["snapshot"])[1].lower())
                        if row["snapshot"] else None
                    )
                    if os.path.exists(rom_dest) or (snap_dest and os.path.exists(snap_dest)):
                        raise FileExistsError("같은 Key의 ROM 또는 스냅샷 파일이 이미 존재합니다.")
                    _copy_exclusive(row["rom"], rom_dest)
                    created.append(rom_dest)
                    if snap_dest:
                        _copy_exclusive(row["snapshot"], snap_dest)
                        created.append(snap_dest)
                    if cheat_dest and not os.path.exists(cheat_dest):
                        _copy_exclusive(row["cheat"], cheat_dest)
                        created.append(cheat_dest)
                    self.data[key] = {
                        "url": f"https://github.com/WOOSEOK99/my-repo/blob/main/konfiles/{row['system']}/{basename}.bin",
                        "title": row["title"], "title_en": row["english"],
                        "desc": "", "category": "console", "genre": row["genre"],
                        "genre_en": GENRE_EN[row["genre"]], "series": "", "series_en": "",
                        "parent": "", "year": 0, "developer": "", "portrait": False,
                        "buttons": 0, "system": row["system"], "LRbuttons": False,
                    }
                    self.newly_added_keys.add(key)
                    row["selected"] = False
                    done += 1
                except (OSError, KeyError, ValueError) as exc:
                    for dest in reversed(created):
                        try:
                            os.remove(dest)
                        except OSError:
                            pass
                    failed.append(key + ": " + str(exc))
            self.refresh_all_lists()
            self.update_listbox()
            redraw()
            result_text = (
                f"메모리에 등록: {done}개 / 실패: {len(failed)}개\n\n"
                "JSON 저장은 기존 '저장하기' 버튼을 눌러야 반영됩니다.\n"
                "ROM/스냅샷/치트의 GitHub 업로드는 별도로 진행해야 합니다."
            )
            if failed:
                result_text += "\n\n실패 목록:\n" + "\n".join(failed[:30])
            messagebox.showinfo("콘솔 일괄 등록 결과", result_text, parent=dialog)

        analyze_btn = ttk.Button(footer, text="1. 분석 / 인터넷 장르 조회", command=analyze)
        analyze_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="행 편집", command=edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="등록 포함/제외", command=toggle).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="2. 선택 항목 일괄 등록", command=register).pack(side=tk.RIGHT, padx=5)
        ttk.Button(footer, text="닫기", command=close).pack(side=tk.RIGHT, padx=5)
        tree.bind("<Double-1>", lambda event: edit())
        dialog.after(150, poll)
