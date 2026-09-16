import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget
)
from PyQt6.QtCore import Qt

from ZipfileViewer import CombinedApp
from CheatTabWithBrowser import CheatTabWithBrowser


class SortedCheatTab(CheatTabWithBrowser):
    """치트 매칭이 끝나면 결과 상태별로 자동 정렬한다."""

    def match_all(self):
        super().match_all()
        self.sort_match_results()

    def sort_match_results(self):
        tree = self.archive_tree
        current_item = tree.currentItem()
        rows = []
        original_index = 0

        while tree.topLevelItemCount() > 0:
            item = tree.takeTopLevelItem(0)
            data = item.data(2, Qt.ItemDataRole.UserRole) or {}
            candidates = data.get("candidates", [])
            selected_index = data.get("selected_index")

            if not candidates:
                # 3순위: 매칭 안 됨
                priority = 2
            elif len(candidates) == 1:
                # 1순위: 정확히 일치 / 이름 매칭 / 수동 지정
                priority = 0
            elif (
                isinstance(selected_index, int)
                and 0 <= selected_index < len(candidates)
            ):
                # 1순위: 여러 후보 중 사용자가 이미 선택 완료
                priority = 0
            else:
                # 2순위: 후보는 있으나 아직 선택 필요
                priority = 1

            rows.append((priority, original_index, item))
            original_index += 1

        # 같은 상태 그룹 안에서는 원래 순서를 유지한다.
        rows.sort(key=lambda row: (row[0], row[1]))

        for _, _, item in rows:
            tree.addTopLevelItem(item)

        if current_item is not None:
            tree.setCurrentItem(current_item)

        header = tree.header()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(2, Qt.SortOrder.AscendingOrder)


class ZipfileViewerPlus(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("압축파일 썸네일 & 치트 매칭 매니저")
        self.resize(1380, 900)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        self.thumbnail_tab = CombinedApp()
        self.cheat_tab = SortedCheatTab()

        self._adjust_cheat_layout()

        # 긴 치트 파일명이 잘리지 않도록 후보 선택 칸과 펼침 목록을 넓힌다.
        self.cheat_tab.cmb_candidates.setMinimumWidth(520)
        self.cheat_tab.cmb_candidates.view().setMinimumWidth(800)

        # 필요하면 '치트 매칭' 헤더를 눌러 같은 정렬을 다시 적용할 수 있다.
        self.cheat_tab.archive_tree.header().sectionClicked.connect(
            lambda section: (
                self.cheat_tab.sort_match_results()
                if section == 2 else None
            )
        )

        tabs.addTab(self.thumbnail_tab, "썸네일")
        tabs.addTab(self.cheat_tab, "치트")
        layout.addWidget(tabs)

    def _adjust_cheat_layout(self):
        """기능은 그대로 두고 치트 탭의 배치와 폭만 조정한다."""
        cheat_list = self.cheat_tab.cheat_list
        system_tree = self.cheat_tab.system_tree
        archive_tree = self.cheat_tab.archive_tree

        # '하위 경로'는 치트 파일명과 같은 경우가 많아 화면에서는 숨긴다.
        # 데이터 자체는 남아 있으므로 기존 검색 로직은 그대로 동작한다.
        cheat_list.setColumnHidden(1, True)

        # 기존 아래쪽 splitter에서 시스템 폴더 목록을 빼서
        # 위쪽 치트 파일 목록의 왼편으로 이동한다.
        bottom_splitter = system_tree.parentWidget()
        browser_group = cheat_list.parentWidget()
        browser_layout = browser_group.layout()

        cheat_list_index = browser_layout.indexOf(cheat_list)
        browser_layout.removeWidget(cheat_list)

        system_tree.setParent(browser_group)
        system_tree.setMinimumWidth(240)
        system_tree.setMaximumWidth(310)

        browser_row = QHBoxLayout()
        browser_row.addWidget(system_tree, 0)
        browser_row.addWidget(cheat_list, 1)
        browser_layout.insertLayout(cheat_list_index, browser_row, 1)

        # 시스템 폴더가 빠진 만큼 아래쪽 압축파일 목록을 넓힌다.
        if bottom_splitter is not None:
            bottom_splitter.setStretchFactor(0, 3)
            bottom_splitter.setStretchFactor(1, 2)
            bottom_splitter.setSizes([820, 520])

        archive_tree.setMinimumWidth(760)
        archive_tree.setColumnWidth(0, 230)
        archive_tree.setColumnWidth(1, 430)
        archive_tree.setColumnWidth(2, 150)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZipfileViewerPlus()
    window.show()
    sys.exit(app.exec())
