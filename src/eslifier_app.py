import sys
import images_qr #do not remove, used for icons, it is a PyQt6 resource file
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPalette, QColor, QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QMenuBar, QStackedLayout, QMessageBox

from settings_page import settings
from main_page import main
from patch_new_page import patch_new
from log_stream import log_stream
class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        #TODO: refine patching of files in compact_form_ids.py
        #TODO: Fix existing ESLifier plugin
        self.setWindowTitle("ESLifier")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.log_stream = log_stream(self)
        self.setWindowIcon(QIcon(":/images/ESLifier.png"))
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
        main_menu_action.setToolTip(
            "This is the Main Page, scan your skyrim folder and select plugins to flag or compress.")
        setting_menu_action = QAction("Settings", self)
        setting_menu_action.triggered.connect(self.settings_selected)
        setting_menu_action.setToolTip(
            "This is the settings page. Certain settings will effect what plugins will display after scanning.")
        patch_new_menu_action = QAction("Patch New Plugins/Files", self)
        patch_new_menu_action.triggered.connect(self.patch_new_selected)
        patch_new_menu_action.setToolTip(
            "This is the Patch New Files Page, scan for new files that were not present when you\n"+
            "initially compressed plugins and patched dependent plugins and files, then select the\n"+
            "master of the new files you want to patch.")
        help_menu_action = QAction("Help?", self)
        help_menu_action.triggered.connect(self.help_selected)
        help_menu_action.setToolTip("Help Button, displays help message.")

        top_menu = QMenuBar()
        top_menu.addAction(main_menu_action)
        top_menu.addAction(patch_new_menu_action)
        top_menu.addAction(setting_menu_action)
        top_menu.addAction(help_menu_action)
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
            QMenuBar::item::pressed{
                background-color: rgb(50,50,50);
            }
            """)
        top_menu.setToolTip(
            "Main Page: Scan your skyrim folder and select plugins to flag or compress.\n" +
            "Patch New Files Page: Scan for new files and dependents that were not present when you\n"+
                "\tinitially compressed plugins and patched dependent files/plugins.\n"+
                "\tSelect the master of the new files you want to patch.\n" +
            "Settings Page: Certain settings will effect what plugins will display after scanning.")
            
        self.settings_widget = settings()
        self.main_widget = main()
        self.patch_new_widget = patch_new()
        self.main_widget.setMinimumWidth(1000)
        self.main_widget.setMinimumHeight(500)
        self.update_settings()
        self.tabs = QStackedLayout()
        self.tabs.addWidget(self.main_widget)
        self.tabs.addWidget(self.patch_new_widget)
        self.tabs.addWidget(self.settings_widget)
        self.tabs.setCurrentIndex(0)
        if self.settings_widget.settings['output_folder_path'] == '' or self.settings_widget.settings['skyrim_folder_path'] == '':
            self.tabs.setCurrentIndex(2)
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
        if (self.settings_widget.settings['output_folder_path'] == '' or self.settings_widget.settings['skyrim_folder_path'] == '' or 
            (self.settings_widget.settings['mo2_mode'] and self.settings_widget.settings['mo2_modlist_txt_path'] == '')):
            self.tabs.setCurrentIndex(2)
            self.no_path_set()

    def patch_new_selected(self):
        self.tabs.setCurrentIndex(1)
        if (self.settings_widget.settings['output_folder_path'] == '' or self.settings_widget.settings['skyrim_folder_path'] == '' or 
            (self.settings_widget.settings['mo2_mode'] and self.settings_widget.settings['mo2_modlist_txt_path'] == '')):
            self.tabs.setCurrentIndex(2)
            self.no_path_set()

    def settings_selected(self):
        self.tabs.setCurrentIndex(2)

    def help_selected(self):
        help = QMessageBox()
        help.setIcon(QMessageBox.Icon.Information)
        help.setWindowTitle("Help")
        help.setWindowIcon(QIcon(":/images/ESLifier.png"))
        help.setText(
            "Almost every element in the program has a tool tip that explains it.\n"+
            "Tool tips can be seen by hovering over elements with the mouse.\n"+
            "It is advised to read what everything does before doing anything.\n")
        help.addButton(QMessageBox.StandardButton.Ok)
        def close():
            help.close()
        help.accepted.connect(close)
        help.show()

    def no_path_set(self):
        message = QMessageBox()
        message.setWindowTitle("Missing Paths Error")
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowIcon(QIcon(":/images/ESLifier.png"))
        message.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        message.setText(
            "Both the Skyrim Folder Path and Output Folder Path\n"+
            "must be set to leave the settings page!")
        if self.settings_widget.settings['mo2_mode']:
            message.setText(
            "The Skyrim Folder Path, Output Folder Path, and the Modlist.txt Path\n"+
            "must be set to leave the settings page!")
        message.addButton(QMessageBox.StandardButton.Ok)
        def close():
            message.close()
        message.accepted.connect(close)
        message.show()

    def update_settings(self):
        self.settings_widget.update_settings()
        self.main_widget.skyrim_folder_path = self.settings_widget.settings['skyrim_folder_path']
        self.main_widget.output_folder_path = self.settings_widget.settings['output_folder_path']
        self.main_widget.mo2_mode = self.settings_widget.settings['mo2_mode']
        self.main_widget.modlist_txt_path = self.settings_widget.settings['mo2_modlist_txt_path']
        self.main_widget.update_header = self.settings_widget.settings['update_header']
        self.main_widget.scan_esms = self.settings_widget.settings['scan_esms']
        self.main_widget.show_cells = self.settings_widget.settings['show_cells']
        self.main_widget.list_compact.filter_changed_cells = self.settings_widget.settings['enable_cell_changed_filter']
        self.main_widget.list_eslify.filter_changed_cells = self.settings_widget.settings['enable_cell_changed_filter']
        self.patch_new_widget.skyrim_folder_path = self.settings_widget.settings['skyrim_folder_path']
        self.patch_new_widget.output_folder_path = self.settings_widget.settings['output_folder_path']
        self.patch_new_widget.modlist_txt_path = self.settings_widget.settings['mo2_modlist_txt_path']
        self.patch_new_widget.mo2_mode = self.settings_widget.settings['mo2_mode']
        self.patch_new_widget.update_header = self.settings_widget.settings['update_header']
        self.patch_new_widget.scan_esms = self.settings_widget.settings['scan_esms']
        self.update_shown()

    def update_shown(self):
        self.main_widget.list_compact.create()
        self.main_widget.list_eslify.create()
        show_cells = self.settings_widget.settings['show_cells']
        show_bsa = self.settings_widget.settings['show_bsas']
        self.main_widget.list_compact.setColumnHidden(1, not show_cells)
        self.main_widget.list_compact.setColumnHidden(2, not show_bsa)
        self.main_widget.list_eslify.setColumnHidden(1, not show_cells)
        for i in range(self.main_widget.list_compact.rowCount()):
            if self.main_widget.list_compact.item(i,1) and not show_cells:
                self.main_widget.list_compact.setRowHidden(i, True)
            elif self.main_widget.list_compact.item(i,2) and not show_bsa:
                self.main_widget.list_compact.setRowHidden(i, True)
            else:
                self.main_widget.list_compact.setRowHidden(i, False)

        for i in range(self.main_widget.list_eslify.rowCount()):
            if self.main_widget.list_eslify.item(i,1):
                self.main_widget.list_eslify.setRowHidden(i, not show_cells)

    def closeEvent(self, a0):
        sys.stdout = sys.__stdout__
        for window in QApplication.topLevelWidgets():
            window.close()

app = QApplication(sys.argv)
w = main_window()
w.show()
app.exec()