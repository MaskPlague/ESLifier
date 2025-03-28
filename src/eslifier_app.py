import sys
import os
import images_qr #do not remove, used for icons, it is a PyQt6 resource file
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QMessageBox, QTabWidget, QVBoxLayout

from settings_page import settings
from main_page import main
from patch_new_page import patch_new
from log_stream import log_stream
class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        #TODO: Research into making a save patcher
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))

        self.setWindowTitle("ESLifier")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.resize(1300, 500)
        self.move(100,50)
        self.log_stream = log_stream(self)
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
            
        self.settings_widget = settings()
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
        
        if self.settings_widget.settings['output_folder_path'] == '' or self.settings_widget.settings['skyrim_folder_path'] == '':
            self.tabs.setCurrentIndex(2)
            self.previous_tab = 2
        else:
            self.tabs.setCurrentIndex(0)
            self.previous_tab = 0
        self.tabs.currentChanged.connect(self.tab_changed)
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
        if (self.settings_widget.settings['output_folder_path'] == '' or self.settings_widget.settings['skyrim_folder_path'] == '' or 
            self.settings_widget.settings['plugins_txt_path'] == '' or self.settings_widget.settings['bsab_path'] == '' or
            (self.settings_widget.settings['mo2_mode'] and self.settings_widget.settings['mo2_modlist_txt_path'] == '')):
            self.tabs.setCurrentIndex(2)
            self.no_path_set()
            self.tabs.blockSignals(False)
            return
        
        output_path = self.settings_widget.settings['output_folder_path']
        data_path = self.settings_widget.settings['skyrim_folder_path']
        plugins_txt = self.settings_widget.settings['plugins_txt_path']
        bsab = self.settings_widget.settings['bsab_path']
        mo2_mode = self.settings_widget.settings['mo2_mode']
        if mo2_mode:
            mo2_path = self.settings_widget.settings['mo2_modlist_txt_path']

        error_message = ''
        if not os.path.exists(output_path):
            error_message += "Invalid Output Directory, it does not exist.\n"
        if not os.path.exists(data_path):
            if mo2_mode:
                error_message += "Invalid MO2 Mods Directory, it does not exist.\n"
            else:
                error_message += "Invalid Skyrim Data Directory, it does not exist.\n"
        if not plugins_txt.lower().endswith('.txt'):
            error_message += "Invalid plugins.txt, the path should be to the file not directory.\n"
        if not os.path.exists(plugins_txt):
            error_message += "Invalid plugins.txt, the file does not exist.\n"
        if not bsab.lower().endswith('bsab.exe'):
            error_message += "Invalid bsab.exe, the path should be to the file not directory\n"
        if not os.path.exists(bsab):
            error_message += "Invalid bsab.exe, the file does not exist.\n"
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
            "All three paths must be set to leave the settings page!")
        if self.settings_widget.settings['mo2_mode']:
            message.setText(
            "All four paths must be set to leave the settings page!")
        message.addButton(QMessageBox.StandardButton.Ok)
        def close():
            message.close()
        message.accepted.connect(close)
        message.show()

    def update_settings(self):
        self.settings_widget.update_settings()
        self.main_widget.skyrim_folder_path =                   self.settings_widget.settings['skyrim_folder_path']
        self.main_widget.output_folder_path =                   self.settings_widget.settings['output_folder_path']
        self.main_widget.mo2_mode =                             self.settings_widget.settings['mo2_mode']
        self.main_widget.modlist_txt_path =                     self.settings_widget.settings['mo2_modlist_txt_path']
        self.main_widget.plugins_txt_path =                     self.settings_widget.settings['plugins_txt_path']
        self.main_widget.bsab =                                 self.settings_widget.settings['bsab_path']
        self.main_widget.update_header =                        self.settings_widget.settings['update_header']
        self.main_widget.scan_esms =                            self.settings_widget.settings['scan_esms']
        self.main_widget.list_compact.filter_changed_cells =    self.settings_widget.settings['enable_cell_changed_filter']
        self.main_widget.list_compact.filter_interior_cells =   self.settings_widget.settings['enable_interior_cell_filter']
        self.main_widget.list_compact.show_cells =              self.settings_widget.settings['show_cells']
        self.main_widget.list_compact.show_dlls =               self.settings_widget.settings['show_dlls']
        self.main_widget.list_compact.filter_worldspaces =      self.settings_widget.settings['filter_worldspaces']
        self.main_widget.list_eslify.filter_changed_cells =     self.settings_widget.settings['enable_cell_changed_filter']
        self.main_widget.list_eslify.filter_interior_cells =    self.settings_widget.settings['enable_interior_cell_filter']
        self.main_widget.list_eslify.show_cells =               self.settings_widget.settings['show_cells']
        self.main_widget.list_eslify.filter_worldspaces =       self.settings_widget.settings['filter_worldspaces']
        self.patch_new_widget.skyrim_folder_path =              self.settings_widget.settings['skyrim_folder_path']
        self.patch_new_widget.output_folder_path =              self.settings_widget.settings['output_folder_path']
        self.patch_new_widget.plugins_txt_path =                self.settings_widget.settings['plugins_txt_path']
        self.patch_new_widget.bsab =                            self.settings_widget.settings['bsab_path']
        self.patch_new_widget.modlist_txt_path =                self.settings_widget.settings['mo2_modlist_txt_path']
        self.patch_new_widget.mo2_mode =                        self.settings_widget.settings['mo2_mode']
        self.patch_new_widget.update_header =                   self.settings_widget.settings['update_header']
        self.patch_new_widget.scan_esms =                       self.settings_widget.settings['scan_esms']
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
if background_color.lightness() < 128:  # Darker backgrounds mean dark mode
    COLOR_MODE = "Dark"
else:
    COLOR_MODE = "Light"
w = main_window()
w.show()
app.exec()