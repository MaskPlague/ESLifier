import sys
import dependency_getter as dGetter


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QMenuBar, QStackedLayout, QHBoxLayout)

from settings_page import settings
from main_page import main
from patch_new_page import patch_new

class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        #TODO: Make a patch files page which will only use the esp name and pull the form id map to patch dependent files
        #TODO: Make exclusions window/page
        #TODO: create scanner dialog
        self.setWindowTitle("ESLifier")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setFocus()
        self.setStyleSheet("""
            QLineEdit {
                border: 1px solid grey;
                border-radius: 5px;
            }
            QLineEdit::focus {
                border: 1px solid black;
                border-radius: 5px;
            }
            QPushButton {
                border: 1px solid LightGrey;
                border-radius: 5px;
                background-color: LightGrey;
            }
            QPushButton::hover{
                border: 1px solid ghostwhite;
                border-radius: 5px;
                background-color: ghostwhite;
            }
            QLabel{
                color: White
            }
            """)

        main_menu_action = QAction("Main", self)
        main_menu_action.triggered.connect(self.main_selected)
        setting_menu_action = QAction("Settings", self)
        setting_menu_action.triggered.connect(self.settings_selected)
        patch_new_menu_action = QAction("Patch New Plugins/Files", self)
        patch_new_menu_action.triggered.connect(self.patch_new_selected)

        top_menu = QMenuBar()
        top_menu.addAction(main_menu_action)
        top_menu.addAction(patch_new_menu_action)
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
        self.settings_widget = settings()
        self.main_widget = main()
        self.patch_new_widget = patch_new()
        self.main_widget.setMinimumWidth(1000)
        self.main_widget.setMinimumHeight(500)
        self.update_settings()
        self.update_shown()
        self.tabs = QStackedLayout()
        self.tabs.addWidget(self.main_widget)
        self.tabs.addWidget(self.patch_new_widget)
        self.tabs.addWidget(self.settings_widget)
        self.tabs.setCurrentIndex(0)
        self.layout().setAlignment(Qt.AlignmentFlag.AlignHCenter)

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
        self.update_settings()
        self.tabs.setCurrentIndex(0)

    def patch_new_selected(self):
        self.tabs.setCurrentIndex(1)

    def settings_selected(self):
        self.tabs.setCurrentIndex(2)

    def update_settings(self):
        self.settings_widget.update_settings()
        self.main_widget.skyrim_folder_path = self.settings_widget.settings['skyrim_folder_path']
        self.main_widget.output_folder_path = self.settings_widget.settings['output_folder_path']
        self.main_widget.update_header = self.settings_widget.settings['update_header']
        self.main_widget.show_cells = self.settings_widget.settings['show_cells']
        self.patch_new_widget.skyrim_folder_path = self.settings_widget.settings['skyrim_folder_path']
        self.update_shown()

    def update_shown(self):
        show_cells = self.settings_widget.settings['show_cells']
        self.main_widget.list_compact.setColumnHidden(1, not show_cells)
        self.main_widget.list_eslify.setColumnHidden(1, not show_cells)
        for i in range(self.main_widget.list_compact.rowCount()):
            if self.main_widget.list_compact.item(i,1):
                self.main_widget.list_compact.setRowHidden(i, not show_cells)

        for i in range(self.main_widget.list_eslify.rowCount()):
            if self.main_widget.list_eslify.item(i,1):
                self.main_widget.list_eslify.setRowHidden(i, not show_cells)


app = QApplication(sys.argv)
w = main_window()
w.show()
app.exec()