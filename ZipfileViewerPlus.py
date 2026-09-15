import sys

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget

from ZipfileViewer import CombinedApp
from CheatTab import CheatTab


class ZipfileViewerPlus(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("압축파일 썸네일 & 치트 매칭 매니저")
        self.resize(1380, 760)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        self.thumbnail_tab = CombinedApp()
        self.cheat_tab = CheatTab()

        tabs.addTab(self.thumbnail_tab, "썸네일")
        tabs.addTab(self.cheat_tab, "치트")
        layout.addWidget(tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZipfileViewerPlus()
    window.show()
    sys.exit(app.exec())
