import os
import re

from PyQt6.QtWidgets import (
    QApplication, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt

from CheatTab import CheatTab, CheatTextWorker, safe_filename


def cleaned_search_title(filename):
    """웹 검색용으로 확장자와 (태그), [태그]를 제거하되 원래 대소문자는 유지한다."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    title = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', stem)
    return ' '.join(title.split()).strip()


class CheatTabWithBrowser(CheatTab):
    """기존 자동 매칭 기능에 시스템 전체 치트 검색/수동 지정 기능을 추가한다."""

    def __init__(self, parent=None):
        self.manual_selected_entry = None
        super().__init__(parent)
        self._add_manual_browser()
        self._add_copy_title_button()

    def _add_copy_title_button(self):
        """오른쪽 '내부 파일' 입력칸 옆에 웹 검색용 제목 복사 버튼을 붙인다."""
        self.btn_copy_game_title = QPushButton("제목 복사")
        self.btn_copy_game_title.setEnabled(False)
        self.btn_copy_game_title.setToolTip(
            "확장자와 (지역/버전), [태그]를 제거한 게임 제목만 복사합니다."
        )
        self.btn_copy_game_title.clicked.connect(self.copy_game_title)

        preview_layout = self.txt_inner.parentWidget().layout()
        inner_row = self._find_layout_containing_widget(preview_layout, self.txt_inner)
        if inner_row is not None:
            inner_row.addWidget(self.btn_copy_game_title)

    def _find_layout_containing_widget(self, layout, target_widget):
        if layout is None:
            return None

        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is target_widget:
                return layout

            child_layout = item.layout()
            if child_layout is not None:
                found = self._find_layout_containing_widget(
                    child_layout, target_widget
                )
                if found is not None:
                    return found
        return None

    def copy_game_title(self):
        if not self.current_item:
            return

        title = cleaned_search_title(self.current_item.text(1))
        if not title:
            return

        QApplication.clipboard().setText(title)
        self.btn_copy_game_title.setText("복사됨")
        self.btn_copy_game_title.setToolTip(f"클립보드: {title}")

    def _add_manual_browser(self):
        # 자동 매칭 결과 문구는 한 줄만 차지하도록 고정한다.
        self.lbl_status.setWordWrap(False)
        self.lbl_status.setFixedHeight(24)
        self.lbl_status.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        group = QGroupBox("치트 파일 직접 찾기 (선택한 시스템 폴더)")
        group_layout = QVBoxLayout(group)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("검색:"))

        self.txt_cheat_search = QLineEdit()
        self.txt_cheat_search.setPlaceholderText(
            "영문 제목 또는 치트 파일명 일부를 입력하세요. 예: mario, zelda"
        )
        self.txt_cheat_search.textChanged.connect(self.filter_cheat_list)
        search_row.addWidget(self.txt_cheat_search)

        self.btn_use_game_name = QPushButton("선택 게임명 넣기")
        self.btn_use_game_name.setEnabled(False)
        self.btn_use_game_name.clicked.connect(self.use_current_game_name_for_search)
        search_row.addWidget(self.btn_use_game_name)

        self.btn_clear_search = QPushButton("검색 지우기")
        self.btn_clear_search.clicked.connect(self.txt_cheat_search.clear)
        search_row.addWidget(self.btn_clear_search)
        group_layout.addLayout(search_row)

        self.lbl_manual_count = QLabel(
            "왼쪽에서 시스템 폴더를 선택하면 전체 .cht 목록을 검색할 수 있습니다."
        )
        self.lbl_manual_count.setFixedHeight(20)
        group_layout.addWidget(self.lbl_manual_count)

        self.cheat_list = QTreeWidget()
        self.cheat_list.setHeaderLabels(["치트 파일", "하위 경로"])
        header = self.cheat_list.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cheat_list.itemClicked.connect(self.manual_cheat_clicked)
        self.cheat_list.itemDoubleClicked.connect(self.manual_cheat_double_clicked)
        self.cheat_list.setMinimumHeight(220)
        group_layout.addWidget(self.cheat_list, 1)

        button_row = QHBoxLayout()

        self.btn_manual_assign = QPushButton("현재 게임에 지정")
        self.btn_manual_assign.setEnabled(False)
        self.btn_manual_assign.clicked.connect(self.assign_manual_cheat)
        button_row.addWidget(self.btn_manual_assign)

        self.btn_manual_download = QPushButton("목록에서 선택한 치트 다운로드")
        self.btn_manual_download.setEnabled(False)
        self.btn_manual_download.clicked.connect(self.manual_download)
        button_row.addWidget(self.btn_manual_download)

        button_row.addStretch()
        group_layout.addLayout(button_row)

        # 상태 문구에서 확보한 공간을 직접 찾기 목록에 사용한다.
        group.setMinimumHeight(300)
        group.setMaximumHeight(380)
        self.layout().insertWidget(2, group)

    def systems_loaded(self, systems):
        super().systems_loaded(systems)
        if hasattr(self, "lbl_manual_count"):
            self.lbl_manual_count.setText(
                "왼쪽에서 시스템 폴더를 선택하면 전체 .cht 목록을 검색할 수 있습니다."
            )

    def system_clicked(self, item, column):
        if hasattr(self, "cheat_list"):
            self.cheat_list.clear()
            self.txt_cheat_search.clear()
            self.manual_selected_entry = None
            self.btn_manual_download.setEnabled(False)
            self.btn_manual_assign.setEnabled(False)
            self.lbl_manual_count.setText("치트 파일 목록을 불러오는 중...")
        super().system_clicked(item, column)

    def cheats_loaded(self, entries, system_name):
        super().cheats_loaded(entries, system_name)
        self.populate_cheat_list()

    def populate_cheat_list(self):
        self.cheat_list.setUpdatesEnabled(False)
        self.cheat_list.clear()

        for entry in self.cheat_entries:
            item = QTreeWidgetItem([entry["name"], entry["path"]])
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            self.cheat_list.addTopLevelItem(item)

        self.cheat_list.setUpdatesEnabled(True)
        self.filter_cheat_list(self.txt_cheat_search.text())

    def filter_cheat_list(self, text):
        if not hasattr(self, "cheat_list"):
            return

        query = " ".join(text.split()).casefold()
        terms = [term for term in query.split(" ") if term]
        total = self.cheat_list.topLevelItemCount()
        visible = 0

        self.cheat_list.setUpdatesEnabled(False)
        for i in range(total):
            item = self.cheat_list.topLevelItem(i)
            haystack = f"{item.text(0)} {item.text(1)}".casefold()
            matched = all(term in haystack for term in terms)
            item.setHidden(not matched)
            if matched:
                visible += 1
        self.cheat_list.setUpdatesEnabled(True)

        if not self.cheat_entries:
            self.lbl_manual_count.setText(
                "시스템을 선택하면 이곳에 .cht 목록이 표시됩니다."
            )
        elif terms:
            self.lbl_manual_count.setText(
                f"검색 결과 {visible}개 / 전체 {len(self.cheat_entries)}개"
            )
        else:
            self.lbl_manual_count.setText(
                f"{self.current_system}: 전체 {len(self.cheat_entries)}개"
            )

    def archive_item_clicked(self, item, column):
        super().archive_item_clicked(item, column)
        self.btn_use_game_name.setEnabled(True)
        self.btn_manual_assign.setEnabled(self.manual_selected_entry is not None)
        self.btn_copy_game_title.setEnabled(True)
        self.btn_copy_game_title.setText("제목 복사")
        self.btn_copy_game_title.setToolTip(
            "확장자와 (지역/버전), [태그]를 제거한 게임 제목만 복사합니다."
        )

        data = item.data(2, Qt.ItemDataRole.UserRole) or {}
        if not data.get("candidates"):
            self.txt_preview.setPlainText(
                "자동으로 매칭된 치트 파일이 없습니다.\n\n"
                "위의 '치트 파일 직접 찾기'에서 영문 게임명을 검색한 뒤 "
                "치트 내용을 확인하고 '현재 게임에 지정'을 사용할 수 있습니다."
            )

    def use_current_game_name_for_search(self):
        if not self.current_item:
            return

        title = cleaned_search_title(self.current_item.text(1))
        self.txt_cheat_search.setText(title)
        self.txt_cheat_search.setFocus()
        self.txt_cheat_search.selectAll()

    def manual_cheat_clicked(self, item, column):
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry:
            return

        self.manual_selected_entry = entry
        self.btn_manual_download.setEnabled(True)
        self.btn_manual_assign.setEnabled(self.current_item is not None)
        self.preview_manual_entry(entry)

    def manual_cheat_double_clicked(self, item, column):
        self.manual_cheat_clicked(item, column)
        if self.current_item:
            self.assign_manual_cheat()

    def preview_manual_entry(self, entry):
        self.txt_preview.setPlainText(f"{entry['name']}\n\n불러오는 중...")

        worker = CheatTextWorker(entry["url"], self)
        worker.finished_signal.connect(
            lambda text, e=entry: self.txt_preview.setPlainText(
                f"# {e['name']}\n\n{text}"
            )
        )
        worker.error_signal.connect(
            lambda e: self.show_error("치트 미리보기 오류", e)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def assign_manual_cheat(self):
        if not self.current_item or not self.manual_selected_entry:
            return

        entry = self.manual_selected_entry
        self.current_item.setData(
            2,
            Qt.ItemDataRole.UserRole,
            {"candidates": [entry], "match_type": "manual"},
        )
        self.current_item.setText(2, "🛠 수동 지정")
        self.btn_batch.setEnabled(True)

        # 기존 후보 선택/개별 다운로드 UI도 수동 지정된 파일을 가리키도록 갱신한다.
        super().archive_item_clicked(self.current_item, 2)
        self.btn_use_game_name.setEnabled(True)
        self.btn_manual_assign.setEnabled(True)
        self.btn_copy_game_title.setEnabled(True)
        self.lbl_status.setText(
            f"{self.current_system}: '{entry['name']}'을(를) 현재 게임에 수동 지정했습니다."
        )

    def manual_download(self):
        entry = self.manual_selected_entry
        if not entry:
            return

        if self.current_item:
            inner_name = self.current_item.text(1)
            default_name = f"{safe_filename(os.path.splitext(inner_name)[0])}.cht"
        else:
            default_name = safe_filename(entry["name"])
            if not default_name.lower().endswith(".cht"):
                default_name += ".cht"

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

        self.start_download([(entry["url"], path)])
