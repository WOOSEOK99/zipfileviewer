import sys

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import Qt

from ZipfileViewer import CombinedApp
from CheatTabWithBrowser import CheatTabWithBrowser


class ZipfileViewerPlus(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("압축파일 썸네일 & 치트 매칭 매니저")
        self.resize(1380, 900)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        self.thumbnail_tab = CombinedApp()
        self.cheat_tab = CheatTabWithBrowser()

        # 긴 치트 파일명이 잘리지 않도록 후보 선택 칸과 펼침 목록을 넓힌다.
        self.cheat_tab.cmb_candidates.setMinimumWidth(520)
        self.cheat_tab.cmb_candidates.view().setMinimumWidth(800)

        # '치트 매칭' 헤더 클릭 시 사용자 지정 우선순위로 정렬한다.
        self.cheat_tab.archive_tree.header().sectionClicked.connect(
            self._sort_cheat_rows_by_match_status
        )

        tabs.addTab(self.thumbnail_tab, "썸네일")
        tabs.addTab(self.cheat_tab, "치트")
        layout.addWidget(tabs)

    def _sort_cheat_rows_by_match_status(self, section):
        if section != 2:
            return

        tree = self.cheat_tab.archive_tree
        current_item = tree.currentItem()
        rows = []
        original_index = 0

        while tree.topLevelItemCount() > 0:
            item = tree.takeTopLevelItem(0)
            data = item.data(2, Qt.ItemDataRole.UserRole) or {}
            candidates = data.get("candidates", [])
            selected_index = data.get("selected_index")

            if not candidates:
                # 매칭 안 됨
                priority = 2
            elif len(candidates) == 1:
                # 정확히 일치 / 이름 매칭 / 수동 지정
                priority = 0
            elif (
                isinstance(selected_index, int)
                and 0 <= selected_index < len(candidates)
            ):
                # 여러 후보 중 사용자가 이미 선택 완료
                priority = 0
            else:
                # 후보는 있으나 아직 선택 필요
                priority = 1

            rows.append((priority, original_index, item))
            original_index += 1

        # 같은 그룹 안에서는 기존 순서를 유지한다.
        rows.sort(key=lambda row: (row[0], row[1]))

        for _, _, item in rows:
            tree.addTopLevelItem(item)

        if current_item is not None:
            tree.setCurrentItem(current_item)

        header = tree.header()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(2, Qt.SortOrder.AscendingOrder)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZipfileViewerPlus()
    window.show()
    sys.exit(app.exec())
