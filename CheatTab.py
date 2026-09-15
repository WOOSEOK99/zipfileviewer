import os
import re
import requests
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QFileDialog, QLabel, QMessageBox, QHeaderView,
    QLineEdit, QSplitter, QProgressDialog, QPlainTextEdit, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ZipfileViewer import ArchiveWorker, clean_game_title


CHEAT_ROOT_API = (
    "https://api.github.com/repos/libretro/libretro-database/"
    "contents/cht?ref=master"
)


def github_get(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "ZipfileViewer-Cheat/1.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20,
    )
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise RuntimeError(
            "GitHub API 요청 한도에 도달했습니다. 잠시 뒤 다시 시도하세요."
        )
    response.raise_for_status()
    return response


def normalize_full_title(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.replace("_", " ")
    return " ".join(stem.split()).casefold()


def safe_filename(name):
    result = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return result or "cheat"


def unique_filepath(directory, filename, used):
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    n = 2
    while candidate.casefold() in used or os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_{n}{ext}")
        n += 1
    used.add(candidate.casefold())
    return candidate


class CheatRootWorker(QThread):
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            data = github_get(CHEAT_ROOT_API).json()
            systems = []
            for entry in data:
                if entry.get("type") == "dir" and entry.get("git_url"):
                    systems.append((entry["name"], entry["git_url"]))
            systems.sort(key=lambda x: x[0].casefold())
            self.finished_signal.emit(systems)
        except Exception as e:
            self.error_signal.emit(str(e))


class CheatFolderWorker(QThread):
    finished_signal = pyqtSignal(list, str)
    error_signal = pyqtSignal(str)

    def __init__(self, system_name, git_url, parent=None):
        super().__init__(parent)
        self.system_name = system_name
        self.git_url = git_url

    def run(self):
        try:
            sep = "&" if "?" in self.git_url else "?"
            tree_url = self.git_url
            if "recursive=" not in tree_url:
                tree_url = f"{tree_url}{sep}recursive=1"

            data = github_get(tree_url).json()
            entries = []
            for node in data.get("tree", []):
                path = node.get("path", "")
                if node.get("type") != "blob" or not path.lower().endswith(".cht"):
                    continue

                raw_path = quote(f"cht/{self.system_name}/{path}", safe="/")
                entries.append(
                    {
                        "name": os.path.basename(path),
                        "path": path,
                        "url": (
                            "https://raw.githubusercontent.com/"
                            f"libretro/libretro-database/master/{raw_path}"
                        ),
                    }
                )

            entries.sort(key=lambda x: x["name"].casefold())
            self.finished_signal.emit(entries, self.system_name)
        except Exception as e:
            self.error_signal.emit(str(e))


class CheatTextWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            response = requests.get(
                self.url,
                headers={"User-Agent": "ZipfileViewer-Cheat/1.0"},
                timeout=15,
            )
            response.raise_for_status()
            self.finished_signal.emit(
                response.content.decode("utf-8", errors="replace")
            )
        except Exception as e:
            self.error_signal.emit(str(e))


class CheatDownloadWorker(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)

    def __init__(self, download_list, parent=None):
        super().__init__(parent)
        self.download_list = download_list
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            success = 0
            for index, (url, filepath) in enumerate(self.download_list, start=1):
                if self.cancelled:
                    break

                response = requests.get(
                    url,
                    headers={"User-Agent": "ZipfileViewer-Cheat/1.0"},
                    timeout=20,
                )
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    success += 1

                self.progress_signal.emit(index)

            self.finished_signal.emit(success)
        except Exception as e:
            self.error_signal.emit(str(e))


class CheatTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cheat_entries = []
        self.exact_map = {}
        self.clean_map = {}
        self.current_item = None
        self.current_system = ""
        self.download_note = ""
        self.init_ui()
        self.load_systems()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.btn_archive = QPushButton("1. 로컬 압축파일 선택")
        self.btn_archive.clicked.connect(self.select_archive)

        self.btn_reload = QPushButton("시스템 목록 새로고침")
        self.btn_reload.clicked.connect(self.load_systems)

        self.btn_batch = QPushButton("2. 일괄 치트 다운로드")
        self.btn_batch.setEnabled(False)
        self.btn_batch.clicked.connect(self.batch_download)

        top.addWidget(self.btn_archive)
        top.addWidget(QLabel("치트 데이터: libretro/libretro-database/cht"))
        top.addWidget(self.btn_reload)
        top.addStretch()
        top.addWidget(self.btn_batch)
        layout.addLayout(top)

        self.lbl_status = QLabel("치트 시스템 목록을 불러오는 중...")
        layout.addWidget(self.lbl_status)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.system_tree = QTreeWidget()
        self.system_tree.setHeaderLabels(["치트 시스템 폴더"])
        self.system_tree.itemClicked.connect(self.system_clicked)

        self.archive_tree = QTreeWidget()
        self.archive_tree.setHeaderLabels(
            ["압축파일 이름", "내부 파일 이름", "치트 매칭"]
        )
        header = self.archive_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.archive_tree.setColumnWidth(0, 210)
        self.archive_tree.setColumnWidth(1, 300)
        self.archive_tree.setColumnWidth(2, 140)
        self.archive_tree.itemClicked.connect(self.archive_item_clicked)

        preview = QWidget()
        preview_layout = QVBoxLayout(preview)

        row = QHBoxLayout()
        row.addWidget(QLabel("압축 파일:"))
        self.txt_archive = QLineEdit()
        self.txt_archive.setReadOnly(True)
        row.addWidget(self.txt_archive)
        preview_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("내부 파일:"))
        self.txt_inner = QLineEdit()
        self.txt_inner.setReadOnly(True)
        row.addWidget(self.txt_inner)
        preview_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("치트 후보:"))
        self.cmb_candidates = QComboBox()
        self.cmb_candidates.setEnabled(False)
        self.cmb_candidates.currentIndexChanged.connect(
            self.candidate_changed
        )
        row.addWidget(self.cmb_candidates)
        preview_layout.addLayout(row)

        self.btn_single = QPushButton("선택 치트 다운로드")
        self.btn_single.setEnabled(False)
        self.btn_single.clicked.connect(self.single_download)
        preview_layout.addWidget(self.btn_single)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText(
            "매칭된 치트를 선택하면 .cht 내용이 표시됩니다."
        )
        preview_layout.addWidget(self.txt_preview)

        splitter.addWidget(self.system_tree)
        splitter.addWidget(self.archive_tree)
        splitter.addWidget(preview)
        splitter.setSizes([270, 560, 470])
        layout.addWidget(splitter)

    def select_archive(self):
        filters = (
            "압축 파일 "
            "(*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz2 *.tar.xz *.txz)"
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "압축파일 선택", "", filters
        )
        if not path:
            return

        self.archive_tree.clear()
        self.btn_archive.setEnabled(False)
        self.btn_archive.setText("압축 탐색 중...")
        self.btn_batch.setEnabled(False)

        worker = ArchiveWorker(path, self)
        worker.finished_signal.connect(self.archive_loaded)
        worker.error_signal.connect(
            lambda e: self.show_error("압축 탐색 오류", e)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def archive_loaded(self, results):
        self.btn_archive.setEnabled(True)
        self.btn_archive.setText("1. 로컬 압축파일 선택")

        for archive_name, inner_name in results:
            self.archive_tree.addTopLevelItem(
                QTreeWidgetItem([archive_name, inner_name, ""])
            )

        if not results:
            QMessageBox.warning(self, "알림", "압축파일 안에서 파일을 찾지 못했습니다.")
            return

        self.match_all()
        QMessageBox.information(
            self,
            "완료",
            f"총 {len(results)}개의 파일을 읽었습니다.\n"
            "왼쪽에서 게임 시스템을 선택하면 치트를 매칭합니다.",
        )

    def load_systems(self):
        self.system_tree.clear()
        self.btn_reload.setEnabled(False)
        self.btn_reload.setText("불러오는 중...")
        self.lbl_status.setText("libretro 치트 시스템 목록을 불러오는 중...")

        worker = CheatRootWorker(self)
        worker.finished_signal.connect(self.systems_loaded)
        worker.error_signal.connect(
            lambda e: self.show_error("치트 목록 오류", e)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def systems_loaded(self, systems):
        self.btn_reload.setEnabled(True)
        self.btn_reload.setText("시스템 목록 새로고침")

        for name, git_url in systems:
            item = QTreeWidgetItem([name])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"name": name, "git_url": git_url},
            )
            self.system_tree.addTopLevelItem(item)

        self.lbl_status.setText(
            f"치트 시스템 {len(systems)}개를 불러왔습니다. "
            "게임에 맞는 시스템을 선택하세요."
        )

    def system_clicked(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        name = data.get("name")
        git_url = data.get("git_url")
        if not name or not git_url:
            return

        self.current_system = name
        self.cheat_entries = []
        self.exact_map = {}
        self.clean_map = {}
        self.btn_batch.setEnabled(False)
        self.lbl_status.setText(f"{name} 치트 파일 목록을 불러오는 중...")

        worker = CheatFolderWorker(name, git_url, self)
        worker.finished_signal.connect(self.cheats_loaded)
        worker.error_signal.connect(
            lambda e: self.show_error("치트 파일 목록 오류", e)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def cheats_loaded(self, entries, system_name):
        self.cheat_entries = entries
        self.exact_map = {}
        self.clean_map = {}

        for entry in entries:
            exact = normalize_full_title(entry["name"])
            clean = clean_game_title(entry["name"])
            self.exact_map.setdefault(exact, []).append(entry)
            self.clean_map.setdefault(clean, []).append(entry)

        self.lbl_status.setText(
            f"{system_name}: {len(entries)}개의 .cht 파일을 불러왔습니다."
        )
        self.match_all()

    def find_matches(self, inner_name):
        exact = normalize_full_title(inner_name)
        exact_matches = self.exact_map.get(exact, [])
        if exact_matches:
            return list(exact_matches), "exact"

        clean = clean_game_title(inner_name)
        loose_matches = self.clean_map.get(clean, [])
        if loose_matches:
            return list(loose_matches), "loose"

        return [], "none"

    def match_all(self):
        root = self.archive_tree.invisibleRootItem()
        unique_count = 0
        ambiguous_count = 0
        matched_count = 0

        for i in range(root.childCount()):
            item = root.child(i)
            candidates, match_type = self.find_matches(item.text(1))
            item.setData(
                2,
                Qt.ItemDataRole.UserRole,
                {"candidates": candidates, "match_type": match_type},
            )

            if not candidates:
                item.setText(2, "")
            elif len(candidates) == 1:
                matched_count += 1
                unique_count += 1
                item.setText(
                    2,
                    "✅ 정확히 일치" if match_type == "exact" else "✅ 이름 매칭",
                )
            else:
                matched_count += 1
                ambiguous_count += 1
                item.setText(2, f"⚠ 후보 {len(candidates)}개")

        self.btn_batch.setEnabled(unique_count > 0)

        if self.cheat_entries:
            extra = (
                f" 후보가 여러 개인 게임 {ambiguous_count}개는 직접 선택하세요."
                if ambiguous_count else ""
            )
            self.lbl_status.setText(
                f"{self.current_system}: 게임 {matched_count}개에 치트 후보가 있습니다. "
                f"단일 매칭 {unique_count}개는 일괄 다운로드할 수 있습니다."
                f"{extra}"
            )

    def archive_item_clicked(self, item, column):
        self.current_item = item
        self.txt_archive.setText(item.text(0))
        self.txt_inner.setText(item.text(1))

        data = item.data(2, Qt.ItemDataRole.UserRole) or {}
        candidates = data.get("candidates", [])

        self.cmb_candidates.blockSignals(True)
        self.cmb_candidates.clear()
        for candidate in candidates:
            self.cmb_candidates.addItem(candidate["name"])
        self.cmb_candidates.blockSignals(False)

        enabled = bool(candidates)
        self.cmb_candidates.setEnabled(enabled)
        self.btn_single.setEnabled(enabled)

        if not candidates:
            self.txt_preview.setPlainText("매칭된 치트 파일이 없습니다.")
            return

        self.cmb_candidates.setCurrentIndex(0)
        self.load_preview()

    def candidate_changed(self, index):
        if index >= 0:
            self.load_preview()

    def selected_candidate(self):
        if not self.current_item:
            return None

        data = self.current_item.data(2, Qt.ItemDataRole.UserRole) or {}
        candidates = data.get("candidates", [])
        index = self.cmb_candidates.currentIndex()

        if 0 <= index < len(candidates):
            return candidates[index]
        return None

    def load_preview(self):
        candidate = self.selected_candidate()
        if not candidate:
            return

        self.txt_preview.setPlainText(
            f"{candidate['name']}\n\n불러오는 중..."
        )

        worker = CheatTextWorker(candidate["url"], self)
        worker.finished_signal.connect(self.preview_loaded)
        worker.error_signal.connect(
            lambda e: self.show_error("치트 미리보기 오류", e)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def preview_loaded(self, text):
        candidate = self.selected_candidate()
        title = candidate["name"] if candidate else "치트"
        self.txt_preview.setPlainText(f"# {title}\n\n{text}")

    def single_download(self):
        candidate = self.selected_candidate()
        if not candidate or not self.current_item:
            return

        inner_name = self.current_item.text(1)
        default_name = (
            f"{safe_filename(os.path.splitext(inner_name)[0])}.cht"
        )
        default_path = os.path.join(
            os.path.expanduser("~"), "Downloads", default_name
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "치트 파일 저장",
            default_path,
            "RetroArch Cheat (*.cht)",
        )
        if not path:
            return
        if not path.lower().endswith(".cht"):
            path += ".cht"

        self.start_download([(candidate["url"], path)])

    def batch_download(self):
        save_dir = QFileDialog.getExistingDirectory(
            self, "일괄 치트 다운로드 폴더 선택"
        )
        if not save_dir:
            return

        root = self.archive_tree.invisibleRootItem()
        download_list = []
        skipped = 0
        used = set()

        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(2, Qt.ItemDataRole.UserRole) or {}
            candidates = data.get("candidates", [])

            if len(candidates) > 1:
                skipped += 1
                continue
            if len(candidates) != 1:
                continue

            inner_name = item.text(1)
            filename = (
                f"{safe_filename(os.path.splitext(inner_name)[0])}.cht"
            )
            filepath = unique_filepath(save_dir, filename, used)
            download_list.append((candidates[0]["url"], filepath))

        if not download_list:
            QMessageBox.information(
                self,
                "알림",
                "일괄 다운로드할 단일 매칭 치트가 없습니다.\n"
                "후보가 여러 개인 항목은 직접 선택해 다운로드하세요.",
            )
            return

        self.download_note = (
            f"\n후보가 여러 개인 게임 {skipped}개는 건너뛰었습니다."
            if skipped else ""
        )
        self.start_download(download_list)

    def start_download(self, download_list):
        self.progress = QProgressDialog(
            "치트 다운로드 중...",
            "취소",
            0,
            len(download_list),
            self,
        )
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setAutoClose(False)
        self.progress.setAutoReset(False)
        self.progress.show()

        self.downloader = CheatDownloadWorker(download_list, self)
        self.downloader.progress_signal.connect(self.progress.setValue)
        self.downloader.finished_signal.connect(self.download_finished)
        self.downloader.error_signal.connect(
            lambda e: self.show_error("다운로드 오류", e)
        )
        self.progress.canceled.connect(self.downloader.cancel)
        self.downloader.finished.connect(self.downloader.deleteLater)
        self.downloader.start()

    def download_finished(self, count):
        self.progress.close()
        QMessageBox.information(
            self,
            "완료",
            f"총 {count}개의 치트 파일을 다운로드했습니다."
            f"{self.download_note}",
        )
        self.download_note = ""

    def show_error(self, title, message):
        if title == "압축 탐색 오류":
            self.btn_archive.setEnabled(True)
            self.btn_archive.setText("1. 로컬 압축파일 선택")
        elif title == "치트 목록 오류":
            self.btn_reload.setEnabled(True)
            self.btn_reload.setText("시스템 목록 새로고침")
        elif title == "치트 미리보기 오류":
            self.txt_preview.setPlainText(f"미리보기 오류:\n{message}")

        QMessageBox.warning(self, title, f"오류 발생:\n{message}")
