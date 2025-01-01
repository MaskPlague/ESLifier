import sys
import dependency_getter as dGetter


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QMenuBar, QStackedLayout,)

from settings_page import settings
from main_page import main

class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        #TODO: Make a scanner Page
        #TODO: Make exclusions window/page
        #TODO: list_compact and list_eslify need to get actual data from scanner
        #TODO: hook up scanner
        #TODO: create scanner dialog
        self.setWindowTitle("ESLifier")

        main_menu_action = QAction("Main", self)
        main_menu_action.triggered.connect(self.main_selected)

        setting_menu_action = QAction("Settings", self)
        setting_menu_action.triggered.connect(self.settings_selected)

        top_menu = QMenuBar()
        top_menu.addAction(main_menu_action)
        top_menu.addAction(setting_menu_action)
        top_menu.setStyleSheet("""
            QMenuBar {
                background-color: rgb(70,70,70);
                color: rgb(255,255,255);
                border-bottom: 1px solid rgb(255,255,255)
            }
            QMenuBar::item {
                background-color: rgb(70,70,70);
                color: rgb(255,255,255);
            }
            QMenuBar::item::selected {
                background-color: rgb(100,100,100);
            }
            """)
        
        self.main_widget = main()
        self.settings_widget = settings()
        self.tabs = QStackedLayout()
        self.tabs.addWidget(self.main_widget)
        self.tabs.addWidget(self.settings_widget)
        self.tabs.setCurrentIndex(0)

        display_widget = QWidget()
        display_widget.setLayout(self.tabs)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("Gray"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("Black"))
        palette.setColor(QPalette.ColorRole.Button, QColor("Light Grey"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("White"))
        self.setPalette(palette)

        self.setCentralWidget(display_widget)
        self.setMenuBar(top_menu)

    def main_selected(self):
        self.settings_widget.update_settings()
        self.tabs.setCurrentIndex(0)

    def settings_selected(self):
        self.tabs.setCurrentIndex(1)


app = QApplication(sys.argv)
w = main_window()
w.show()
app.exec()