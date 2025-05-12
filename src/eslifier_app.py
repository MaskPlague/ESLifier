import sys
import os
import images_qr #do not remove, used for icons, it is a PyQt6 resource file
import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QMessageBox, QTabWidget, QVBoxLayout

from settings_page import settings
from main_page import main
from patch_new_page import patch_new
from log_stream import log_stream

CURRENT_VERSION = '0.8.16'
MAJOR, MINOR, PATCH = [int(x, 10) for x in CURRENT_VERSION.split('.')] 
VERSION_TUPLE = (MAJOR, MINOR, PATCH)

def verify_luhn_checksum(filename):
    with open(filename, "rb") as f:
        data = f.read()

    original_data, stored_checksum = data[:-1], data[-1]
    computed_checksum = luhn_checksum(original_data)

    if computed_checksum != stored_checksum:
        raise RuntimeError("File is corrupted! Checksum mismatch. Redownload the file, if the issue persists then report this to the GitHub.")
    else:
        if os.path.exists('ESLifier_Data/settings.json'):
            with open('ESLifier_Data/settings.json', 'r+', encoding='utf-8') as f:
                settings_data = json.load(f)
                settings_data['version'] = CURRENT_VERSION
                f.seek(0)
                f.truncate(0)
                json.dump(settings_data, f, ensure_ascii=False, indent=4)
        else:
            os.makedirs('ESLifier_Data/')
            settings_data = {"version": CURRENT_VERSION}
            with open('ESLifier_Data/settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=4)

def luhn_checksum(data: bytes) -> int:
    total = 0
    for i, digit in enumerate(reversed(data)):
        if i % 2 == 0:
            digit *= 2
            if digit > 255:
                digit -= 256
        total += digit
    return (256 - (total % 256)) % 256

class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
            if os.path.exists('ESLifier_Data/settings.json'):
                with open('ESLifier_Data/settings.json', 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                version = settings_data.get('version', '0.0.0')
                major, minor, patch = [int(x, 10) for x in version.split('.')] 
                version_tuple = (major, minor, patch)
                if VERSION_TUPLE > version_tuple:
                    verify_luhn_checksum('ESLifier.exe')
            else:
                verify_luhn_checksum('ESLifier.exe')
        self.setWindowTitle("ESLifier v" + CURRENT_VERSION)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.resize(1300, 500)
        self.move(100,50)
        self.log_stream = log_stream(self, CURRENT_VERSION)
        self.setWindowIcon(QIcon(":/images/ESLifier.png"))
        self.setFocus()
        if COLOR_MODE == 'Light':
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("Gray"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("Black"))
            palette.setColor(QPalette.ColorRole.Button, QColor("Light Grey"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("White"))
            self.setPalette(palette)
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
                    color: black
                }
                QLabel{
                    color: White
                }
                """)
            
        self.settings_widget = settings(COLOR_MODE=COLOR_MODE)
        self.main_widget = main()
        self.patch_new_widget = patch_new()
        self.update_settings()
        self.tabs = QTabWidget()
        if COLOR_MODE == 'Light':
            self.tabs.setStyleSheet("""
                QTabWidget::pane { /* The tab widget frame */
                    border-top: 1px solid rgb(255,255,255);
                }
                QTabWidget::tab-bar {
                    left: 20px
                }
                QTabBar::tab {
                    background-color: lightgrey;
                    border-top-left-radius: 1px;
                    border-top-right-radius: 1px;
                    border-right: 1px solid grey;
                    min-width: 8ex;
                    padding: 3px;
                }
                QTabBar::tab:selected, QTabBar::tab:hover {
                    background-color: ghostwhite
                }
                """)

        self.tabs.addTab(self.main_widget, "  Main  ")
        self.tabs.setTabToolTip(0, "This is the Main Page, scan your skyrim folder and select plugins to flag or compress.")
        self.tabs.addTab(self.patch_new_widget, "  Patch New Plugins/Files  ")
        self.tabs.setTabToolTip(1,
            "This is the Patch New Files Page, scan for new files that were not present when you\n"+
            "initially compressed plugins and patched dependent plugins and files, then select the\n"+
            "master of the new files you want to patch.")
        self.tabs.addTab(self.settings_widget, "  Settings  ")
        self.tabs.setTabToolTip(2, "This is the settings page. Certain settings will effect what plugins will display after scanning.")
        self.tabs.addTab(QWidget(), "  Help?  ")
        self.initial = True
        self.tabs.currentChanged.connect(self.tab_changed)
        self.previous_tab = 0
        self.tab_changed(0)
        self.layout().setAlignment(Qt.AlignmentFlag.AlignHCenter)

        display_widget = QWidget()
        tabs_layout = QVBoxLayout()
        tabs_layout.addWidget(self.tabs)
        display_widget.setLayout(tabs_layout)
        self.setCentralWidget(display_widget)

    def tab_changed(self, index):
        self.update_settings()
        if index == 3:
            self.tabs.setCurrentIndex(self.previous_tab)
            self.help_selected()
            index = self.previous_tab
        self.previous_tab = index
        self.path_validator()

    def path_validator(self):
        self.tabs.blockSignals(True)
        if (self.settings_widget.settings['output_folder_path'] == ''
            or self.settings_widget.settings['skyrim_folder_path'] == ''
            or self.settings_widget.settings['plugins_txt_path'] == ''
            or self.settings_widget.settings['bsab_path'] == ''
            or (self.settings_widget.settings['mo2_mode'] 
                and (self.settings_widget.settings['mo2_modlist_txt_path'] == '' 
                     or self.settings_widget.settings['overwrite_path'] == ''))):
            self.tabs.setCurrentIndex(2)
            self.tabs.blockSignals(False)
            if not self.initial:
                self.no_path_set()
            else:
                self.initial = False
            return
        self.initial = False
        if not self.settings_widget.output_folder_name_valid:
            self.tabs.setCurrentIndex(2)
            QMessageBox.warning(None, "Invalid Folder Name", f"Enter a valid output folder name.")
            self.tabs.blockSignals(False)
            return
        
        output_path = self.settings_widget.settings['output_folder_path']
        data_path = self.settings_widget.settings['skyrim_folder_path']
        plugins_txt = self.settings_widget.settings['plugins_txt_path']
        bsab = self.settings_widget.settings['bsab_path']
        mo2_mode = self.settings_widget.settings['mo2_mode']
        if mo2_mode:
            mo2_path = self.settings_widget.settings['mo2_modlist_txt_path']
            overwrite_path = self.settings_widget.settings['overwrite_path']

        error_message = ''
        output_path_exists = False
        data_path_exists = False
        if not os.path.exists(output_path):
            error_message += "Invalid Output Directory, it does not exist.\n"
        else:
            output_path_exists = True
        if not os.path.exists(data_path):
            if mo2_mode:
                error_message += "Invalid MO2 Mods Directory, it does not exist.\n"
            else:
                error_message += "Invalid Skyrim Data Directory, it does not exist.\n"
        else:
            data_path_exists = True
        if output_path_exists and data_path_exists:
            output_path_drive, _ = os.path.splitdrive(output_path)
            data_path_drive, _ = os.path.splitdrive(data_path)
            if output_path_drive != data_path_drive:
                error_message += "The Mods/Data Folder Path and the Output Folder Path must be on the same drive.\n"
        if not plugins_txt.lower().endswith('.txt'):
            error_message += "Invalid plugins.txt, the path should be to the file not directory.\n"
        if not os.path.exists(plugins_txt):
            error_message += "Invalid plugins.txt, the file does not exist.\n"
        if not bsab.lower().endswith('bsab.exe'):
            error_message += "Invalid bsab.exe, the path should be to the file not directory\n"
        if not os.path.exists(bsab):
            error_message += "Invalid bsab.exe, the file does not exist.\n"
        if mo2_mode and not os.path.exists(overwrite_path):
            error_message += "Invalid Overwrite Directory, it does not exist.\n'"
        if mo2_mode and not mo2_path.lower().endswith('modlist.txt'):
            error_message += "Invalid MO2 modlist.txt, the path should be to the file not directory.\n"
        if mo2_mode and not os.path.exists(mo2_path):
            error_message += "Invalid MO2 modlist.txt, the file does not exist.\n"

        if len(error_message) > 10:
            self.tabs.setCurrentIndex(2)
            message = QMessageBox()
            message.setWindowTitle("Path Validation Error")
            message.setIcon(QMessageBox.Icon.Warning)
            message.setWindowIcon(QIcon(":/images/ESLifier.png"))
            message.setStyleSheet("""
                QMessageBox {
                    background-color: lightcoral;
                }""")
            message.setText(error_message)
            message.addButton(QMessageBox.StandardButton.Ok)
            def close():
                message.close()
            message.accepted.connect(close)
            message.show()
        self.tabs.blockSignals(False)

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
            "All paths must be set to leave the settings page!")
        message.addButton(QMessageBox.StandardButton.Ok)
        def close():
            message.close()
        message.accepted.connect(close)
        message.show()

    def update_settings(self):
        self.settings_widget.update_settings()
        self.main_widget.skyrim_folder_path =                   self.settings_widget.settings['skyrim_folder_path']
        self.main_widget.output_folder_path =                   self.settings_widget.settings['output_folder_path']
        self.main_widget.output_folder_name =                   self.settings_widget.settings['output_folder_name']
        self.main_widget.mo2_mode =                             self.settings_widget.settings['mo2_mode']
        self.main_widget.modlist_txt_path =                     self.settings_widget.settings['mo2_modlist_txt_path']
        self.main_widget.plugins_txt_path =                     self.settings_widget.settings['plugins_txt_path']
        self.main_widget.overwrite_path =                       self.settings_widget.settings['overwrite_path']
        self.main_widget.bsab =                                 self.settings_widget.settings['bsab_path']
        self.main_widget.update_header =                        self.settings_widget.settings['update_header']
        self.main_widget.list_compact.filter_changed_cells =    self.settings_widget.settings['enable_cell_changed_filter']
        self.main_widget.list_compact.filter_interior_cells =   self.settings_widget.settings['enable_interior_cell_filter']
        self.main_widget.list_compact.show_cells =              self.settings_widget.settings['show_cells']
        self.main_widget.list_compact.show_esms =               self.settings_widget.settings['show_esms']
        self.main_widget.list_compact.show_dlls =               self.settings_widget.settings['show_dlls']
        self.main_widget.list_compact.filter_worldspaces =      self.settings_widget.settings['filter_worldspaces']
        self.main_widget.list_eslify.filter_changed_cells =     self.settings_widget.settings['enable_cell_changed_filter']
        self.main_widget.list_eslify.filter_interior_cells =    self.settings_widget.settings['enable_interior_cell_filter']
        self.main_widget.list_eslify.show_cells =               self.settings_widget.settings['show_cells']
        self.main_widget.list_eslify.show_esms =                self.settings_widget.settings['show_esms']
        self.main_widget.list_eslify.filter_worldspaces =       self.settings_widget.settings['filter_worldspaces']
        self.patch_new_widget.skyrim_folder_path =              self.settings_widget.settings['skyrim_folder_path']
        self.patch_new_widget.output_folder_path =              self.settings_widget.settings['output_folder_path']
        self.patch_new_widget.output_folder_name =              self.settings_widget.settings['output_folder_name']
        self.patch_new_widget.plugins_txt_path =                self.settings_widget.settings['plugins_txt_path']
        self.patch_new_widget.overwrite_path =                  self.settings_widget.settings['overwrite_path']
        self.patch_new_widget.bsab =                            self.settings_widget.settings['bsab_path']
        self.patch_new_widget.modlist_txt_path =                self.settings_widget.settings['mo2_modlist_txt_path']
        self.patch_new_widget.mo2_mode =                        self.settings_widget.settings['mo2_mode']
        self.patch_new_widget.update_header =                   self.settings_widget.settings['update_header']
        self.main_widget.list_compact.create()
        self.main_widget.list_eslify.create()
        
    def closeEvent(self, a0):
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.excepthook = sys.__excepthook__
        for window in QApplication.topLevelWidgets():
            window.close()

    def resizeEvent(self, a0):
        self.log_stream.center_on_parent()
        return super().resizeEvent(a0)
    
    def moveEvent(self, a0):
        self.log_stream.center_on_parent()
        return super().moveEvent(a0)

app = QApplication(sys.argv)
palette = app.palette()
background_color = palette.color(QPalette.ColorRole.Window)

# Determine if the mode is dark or light based on brightness
if background_color.lightness() < 128:
    COLOR_MODE = "Dark"
else:
    COLOR_MODE = "Light"
w = main_window()
w.show()
app.exec()