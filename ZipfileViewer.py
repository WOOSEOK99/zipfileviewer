import os
import sys
import tempfile
import zipfile
import tarfile
import re
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTreeWidget, QTreeWidgetItem, QFileDialog, 
    QLabel, QMessageBox, QHeaderView, QLineEdit, QSplitter,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

# --- Worker Threads ---

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)

    def __init__(self, download_list, parent=None):
        super().__init__(parent)
        self.download_list = download_list
        self.is_cancelled = False

    def run(self):
        try:
            total = len(self.download_list)
            success_count = 0
            for i, (url, filepath) in enumerate(self.download_list):
                if self.is_cancelled:
                    break
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    success_count += 1
                self.progress_signal.emit(i + 1, total)
            self.finished_signal.emit(success_count)
        except Exception as e:
            self.error_signal.emit(str(e))
            
    def cancel_download(self):
        self.is_cancelled = True

class ArchiveWorker(QThread):
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            results = list_final_files(self.file_path)
            self.finished_signal.emit(results)
        except Exception as e:
            self.error_signal.emit(str(e))

class WebLoadWorker(QThread):
    finished_signal = pyqtSignal(list, str)
    error_signal = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            items = []

            for a_tag in soup.find_all('a'):
                href = a_tag.get('href')
                text = unquote(a_tag.text.strip())

                if not href or href.startswith('?') or href.startswith('/') or href in ['../', 'Parent Directory']:
                    continue

                full_url = urljoin(self.url, href)
                is_dir = href.endswith('/')
                display_name = text.rstrip('/') if text else href.rstrip('/')
                items.append((display_name, is_dir, full_url))
            
            self.finished_signal.emit(items, self.url)
        except Exception as e:
            self.error_signal.emit(str(e))

class ImageLoadWorker(QThread):
    finished_signal = pyqtSignal(QPixmap)
    error_signal = pyqtSignal(str)
    
    def __init__(self, img_url, parent=None):
        super().__init__(parent)
        self.img_url = img_url

    def run(self):
        try:
            response = requests.get(self.img_url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self.finished_signal.emit(pixmap)
            else:
                self.error_signal.emit(f"HTTP Status: {response.status_code}")
        except Exception as e:
            self.error_signal.emit(str(e))

# --- Customs Widgets ---

class FixedImageLabel(QLabel):
    """지정된 고정 창 크기로 이미지를 작게 축소하여 보여주는 라벨입니다."""
    def __init__(self, text=""):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.setFixedSize(300, 300)

    def setPixmap(self, pixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled)
        
    def clear_image(self, reset_text=""):
        super().clear()
        if reset_text:
            self.setText(reset_text)

# --- Utility Functions ---

ARCHIVE_EXTENSIONS = ('.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz')

def is_archive(filename):
    return filename.lower().endswith(ARCHIVE_EXTENSIONS)

def remove_archive_extension(filename):
    lower_name = filename.lower()
    for ext in ('.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz'):
        if lower_name.endswith(ext):
            return filename[:-len(ext)]
    return os.path.splitext(filename)[0]

def clean_game_title(filename):
    base_name = os.path.splitext(filename)[0]
    cleaned = re.sub(r'\(.*?\)|\[.*?\]', '', base_name)
    cleaned = ' '.join(cleaned.split()).lower()
    return cleaned

def list_final_files(target_path, current_archive_name=""):
    """재귀적으로 압축 파일을 탐색합니다. (비압축 파일은 불필요하게 해제하지 않도록 최적화)"""
    results = []
    if os.path.isfile(target_path) and is_archive(target_path):
        archive_clean_name = remove_archive_extension(os.path.basename(target_path))
        
        try:
            lower_path = target_path.lower()
            if lower_path.endswith('.zip'):
                with zipfile.ZipFile(target_path, 'r') as zip_ref:
                    for name in zip_ref.namelist():
                        if is_archive(name):
                            with tempfile.TemporaryDirectory() as temp_dir:
                                zip_ref.extract(name, temp_dir)
                                extracted_path = os.path.join(temp_dir, name)
                                results.extend(list_final_files(extracted_path, archive_clean_name))
                        elif not name.endswith('/'):
                            results.append((archive_clean_name, os.path.basename(name)))
                            
            elif any(lower_path.endswith(ext) for ext in ('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz')):
                with tarfile.open(target_path, 'r:*') as tar_ref:
                    for member in tar_ref.getmembers():
                        name = member.name
                        if is_archive(name):
                            with tempfile.TemporaryDirectory() as temp_dir:
                                tar_ref.extract(member, temp_dir)
                                extracted_path = os.path.join(temp_dir, name)
                                results.extend(list_final_files(extracted_path, archive_clean_name))
                        elif member.isfile():
                            results.append((archive_clean_name, os.path.basename(name)))
        except Exception as e:
            print(f"압축 읽기 오류 ({target_path}): {e}")
            
    elif os.path.isdir(target_path):
        for entry in os.listdir(target_path):
            full_path = os.path.join(target_path, entry)
            if is_archive(entry) or os.path.isdir(full_path):
                results.extend(list_final_files(full_path, current_archive_name))
            else:
                results.append((current_archive_name, entry))
                
    elif os.path.isfile(target_path):
        results.append((current_archive_name, os.path.basename(target_path)))
        
    return results


class CombinedApp(QWidget):
    def __init__(self):
        super().__init__()
        self.base_url = "https://thumbnails.libretro.com/"
        self.web_images_map = {}
        self.current_preview_item = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("압축파일 목록 & 웹 썸네일 매칭 매니저 (최적화 버전)")
        self.resize(1300, 700)

        main_layout = QVBoxLayout()

        top_layout = QHBoxLayout()

        self.btn_open_archive = QPushButton("1. 로컬 압축파일 선택")
        self.btn_open_archive.clicked.connect(self.select_archive_file)
        
        self.lbl_url = QLabel("웹 서버 URL:")
        self.txt_url = QLineEdit(self.base_url)
        self.btn_load_web = QPushButton("웹 서버 불러오기")
        self.btn_load_web.clicked.connect(self.load_web_root)

        self.btn_batch_download = QPushButton("2. 일괄 다운로드")
        self.btn_batch_download.setEnabled(False)
        self.btn_batch_download.clicked.connect(self.batch_download_images)

        top_layout.addWidget(self.btn_open_archive)
        top_layout.addWidget(self.lbl_url)
        top_layout.addWidget(self.txt_url)
        top_layout.addWidget(self.btn_load_web)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_batch_download)

        main_layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.web_tree = QTreeWidget()
        self.web_tree.setHeaderLabels(["웹 디렉터리 폴더"])
        self.web_tree.itemExpanded.connect(self.on_web_folder_expanded)
        self.web_tree.itemClicked.connect(self.on_web_folder_clicked)

        self.archive_tree = QTreeWidget()
        self.archive_tree.setHeaderLabels(["압축파일 이름", "내부 파일 이름", "이미지 여부"])
        
        header = self.archive_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.archive_tree.setColumnWidth(0, 220)
        self.archive_tree.setColumnWidth(1, 280)
        self.archive_tree.setColumnWidth(2, 100)

        self.archive_tree.itemClicked.connect(self.on_archive_item_clicked)

        self.preview_container = QWidget()
        preview_layout = QVBoxLayout()
        
        # 이름 표시 영역 (복사 가능)
        info_layout = QVBoxLayout()
        
        arch_layout = QHBoxLayout()
        arch_layout.addWidget(QLabel("압축 파일:"))
        self.txt_preview_archive = QLineEdit()
        self.txt_preview_archive.setReadOnly(True)
        arch_layout.addWidget(self.txt_preview_archive)
        
        inner_layout = QHBoxLayout()
        inner_layout.addWidget(QLabel("내부 파일:"))
        self.txt_preview_inner = QLineEdit()
        self.txt_preview_inner.setReadOnly(True)
        inner_layout.addWidget(self.txt_preview_inner)
        
        info_layout.addLayout(arch_layout)
        info_layout.addLayout(inner_layout)

        self.btn_single_download = QPushButton("개별 다운로드")
        self.btn_single_download.setEnabled(False)
        self.btn_single_download.clicked.connect(self.single_download_image)
        info_layout.addWidget(self.btn_single_download)

        self.lbl_image = FixedImageLabel("목록에서 이미지가 있는 항목을\n클릭하면 여기에 표시됩니다.")
        
        preview_layout.addLayout(info_layout)
        preview_layout.addStretch()
        preview_layout.addWidget(self.lbl_image, alignment=Qt.AlignmentFlag.AlignCenter)
        preview_layout.addStretch()

        self.preview_container.setLayout(preview_layout)

        splitter.addWidget(self.web_tree)
        splitter.addWidget(self.archive_tree)
        splitter.addWidget(self.preview_container)
        
        splitter.setSizes([250, 450, 350])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        self.load_web_root()

    def select_archive_file(self):
        file_filter = "압축 파일 (*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz2 *.tar.xz *.txz)"
        file_path, _ = QFileDialog.getOpenFileName(self, "압축파일 선택", "", file_filter)
        
        if file_path:
            self.archive_tree.clear()
            self.btn_open_archive.setEnabled(False)
            self.btn_open_archive.setText("압축 탐색 중...")
            self.btn_batch_download.setEnabled(False)
            
            worker = ArchiveWorker(file_path, self)
            worker.finished_signal.connect(self.on_archive_finished)
            worker.error_signal.connect(lambda e: self.on_worker_error(e, "압축 탐색 오류"))
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def on_archive_finished(self, results):
        self.btn_open_archive.setEnabled(True)
        self.btn_open_archive.setText("1. 로컬 압축파일 선택")
        if results:
            for archive_name, inner_file in results:
                item = QTreeWidgetItem([archive_name, inner_file, ""])
                self.archive_tree.addTopLevelItem(item)

            QMessageBox.information(self, "완료", f"총 {len(results)}개의 파일을 로드했습니다.\n웹 폴더를 선택하여 이미지를 매칭하세요.")
            self.match_images_with_archive()
        else:
            QMessageBox.warning(self, "알림", "파일을 찾을 수 없습니다.")

    def load_web_root(self):
        target_url = self.txt_url.text().strip()
        if not target_url.endswith('/'):
            target_url += '/'

        self.web_tree.clear()
        self.btn_load_web.setEnabled(False)
        self.btn_load_web.setText("불러오는 중...")
        
        worker = WebLoadWorker(target_url, self)
        worker.finished_signal.connect(self.on_web_root_loaded)
        worker.error_signal.connect(lambda e: self.on_worker_error(e, "웹 서버 오류"))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def on_web_root_loaded(self, items, url):
        self.btn_load_web.setEnabled(True)
        self.btn_load_web.setText("웹 서버 불러오기")
        
        for name, is_dir, full_url in items:
            if is_dir:
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.ItemDataRole.UserRole, full_url)
                item.addChild(QTreeWidgetItem(["Loading..."]))
                self.web_tree.addTopLevelItem(item)

    def on_web_folder_expanded(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            folder_url = item.data(0, Qt.ItemDataRole.UserRole)
            if not folder_url: return
            
            worker = WebLoadWorker(folder_url, self)
            worker.finished_signal.connect(lambda items, u, itm=item: self.on_web_folder_loaded(itm, items))
            worker.error_signal.connect(lambda e: self.on_worker_error(e, "하위 폴더 오류"))
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def on_web_folder_loaded(self, parent_item, items):
        parent_item.takeChildren()
        for name, is_dir, full_url in items:
            if is_dir:
                child_item = QTreeWidgetItem([name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, full_url)
                child_item.addChild(QTreeWidgetItem(["Loading..."]))
                parent_item.addChild(child_item)

    def on_web_folder_clicked(self, item, column):
        folder_url = item.data(0, Qt.ItemDataRole.UserRole)
        if not folder_url:
            return

        worker = WebLoadWorker(folder_url, self)
        worker.finished_signal.connect(self.on_web_match_loaded)
        worker.error_signal.connect(lambda e: self.on_worker_error(e, "웹 서버 상호작용 오류"))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def on_web_match_loaded(self, items, url):
        self.web_images_map.clear()
        for name, is_dir, full_url in items:
            if not is_dir and name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                clean_title = clean_game_title(name)
                if clean_title:
                    self.web_images_map[clean_title] = full_url

        self.match_images_with_archive()

    def match_images_with_archive(self):
        root = self.archive_tree.invisibleRootItem()
        matched_count = 0

        for i in range(root.childCount()):
            item = root.child(i)
            inner_file_name = item.text(1)
            clean_inner_title = clean_game_title(inner_file_name)

            if clean_inner_title and clean_inner_title in self.web_images_map:
                img_url = self.web_images_map[clean_inner_title]
                item.setText(2, "🖼️ 이미지")
                item.setData(2, Qt.ItemDataRole.UserRole, img_url)
                matched_count += 1
            else:
                item.setText(2, "")
                item.setData(2, Qt.ItemDataRole.UserRole, None)

        if self.web_images_map:
            print(f"선택한 웹 폴더에서 {matched_count}개의 이미지 매칭 완료")
            self.btn_batch_download.setEnabled(matched_count > 0)
        else:
            self.btn_batch_download.setEnabled(False)

    def on_archive_item_clicked(self, item, column):
        self.current_preview_item = item
        self.txt_preview_archive.setText(item.text(0))
        self.txt_preview_inner.setText(item.text(1))

        img_url = item.data(2, Qt.ItemDataRole.UserRole)
        
        if img_url:
            self.btn_single_download.setEnabled(True)
            self.lbl_image.clear_image("이미지 불러오는 중...")
            
            worker = ImageLoadWorker(img_url, self)
            worker.finished_signal.connect(self.on_image_loaded)
            worker.error_signal.connect(lambda e: self.on_worker_error(e, "이미지 로드 오류"))
            worker.finished.connect(worker.deleteLater)
            worker.start()
        else:
            self.btn_single_download.setEnabled(False)
            self.lbl_image.clear_image("선택한 항목에 매칭된 이미지가 없습니다.")

    def on_image_loaded(self, pixmap):
        self.lbl_image.setPixmap(pixmap)

    def batch_download_images(self):
        root = self.archive_tree.invisibleRootItem()
        download_list = []

        save_dir = QFileDialog.getExistingDirectory(self, "일괄 다운로드 폴더 선택")
        if not save_dir: return

        for i in range(root.childCount()):
            item = root.child(i)
            img_url = item.data(2, Qt.ItemDataRole.UserRole)
            if img_url:
                archive_name = item.text(0)
                # Ensure valid filename and extract extension
                ext = os.path.splitext(img_url)[1]
                if not ext: ext = ".png"
                
                safe_name = re.sub(r'[\\/*?:"<>|]', "", archive_name)
                filepath = os.path.join(save_dir, f"{safe_name}{ext}")
                download_list.append((img_url, filepath))

        if not download_list:
            QMessageBox.information(self, "알림", "다운로드할 수 있는 매칭된 이미지가 없습니다.")
            return

        self.start_download(download_list)

    def single_download_image(self):
        item = self.current_preview_item
        if not item: return
        img_url = item.data(2, Qt.ItemDataRole.UserRole)
        if not img_url: return

        archive_name = item.text(0)
        ext = os.path.splitext(img_url)[1]
        if not ext: ext = ".png"
        
        safe_name = re.sub(r'[\\/*?:"<>|]', "", archive_name)
        default_path = os.path.join(os.path.expanduser("~"), "Downloads", f"{safe_name}{ext}")
        
        file_path, _ = QFileDialog.getSaveFileName(self, "이미지 저장", default_path, f"Image (*{ext})")
        if file_path:
            self.start_download([(img_url, file_path)])

    def start_download(self, download_list):
        self.progress_dialog = QProgressDialog("다운로드 중...", "취소", 0, len(download_list), self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.show()

        self.download_worker = DownloadWorker(download_list, self)
        self.download_worker.progress_signal.connect(self.progress_dialog.setValue)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.error_signal.connect(lambda e: self.on_worker_error(e, "다운로드 오류"))
        self.progress_dialog.canceled.connect(self.download_worker.cancel_download) 
        self.download_worker.finished.connect(self.download_worker.deleteLater)
        self.download_worker.start()

    def on_download_finished(self, success_count):
        self.progress_dialog.close()
        QMessageBox.information(self, "완료", f"총 {success_count}개의 이미지를 성공적으로 다운로드했습니다.")

    def on_worker_error(self, err, title):
        QMessageBox.warning(self, title, f"오류 발생:\n{err}")
        if title == "압축 탐색 오류":
            self.btn_open_archive.setEnabled(True)
            self.btn_open_archive.setText("1. 로컬 압축파일 선택")
        elif title == "웹 서버 오류":
            self.btn_load_web.setEnabled(True)
            self.btn_load_web.setText("웹 서버 불러오기")
        elif title == "이미지 로드 오류":
            self.lbl_image.clear_image(f"이미지 로드 오류:\n{err}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = CombinedApp()
    ex.show()
    sys.exit(app.exec())