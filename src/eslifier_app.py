import sys
import os
import images_qr #do not remove, used for icons, it is a PyQt6 resource file
import json
import requests
import traceback
from datetime import datetime

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget, QMessageBox, QTabWidget, QVBoxLayout, QSizePolicy

from settings_page import settings
from main_page import main
from log_stream import log_stream

CURRENT_VERSION = '0.14.7'
MAJOR, MINOR, PATCH = [int(x, 10) for x in CURRENT_VERSION.split('.')] 
VERSION_TUPLE = (MAJOR, MINOR, PATCH)

def verify_luhn_checksum(filename: str):
    try:
        with open(filename, "rb") as f:
            data = f.read()
        original_data, stored_checksum = data[:-1], data[-1]
        computed_checksum = luhn_checksum(original_data)
    except:
        computed_checksum = stored_checksum

    if computed_checksum != stored_checksum:
        QMessageBox.critical(None, "File likely Corrupt", "The file is likely corrupt! Checksum mismatch. Redownload the file, if the issue persists then report this to the GitHub.")
        raise RuntimeError("The file is likely corrupt! Checksum mismatch. Redownload the file, if the issue persists then report this to the GitHub.")
    else:
        settings_path = os.path.normpath('ESLifier_Data/settings.json')
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r+', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    settings_data['version'] = CURRENT_VERSION
                    f.seek(0)
                    f.truncate(0)
                    json.dump(settings_data, f, ensure_ascii=False, indent=4)
            except:
                QMessageBox.warning(None, 'Access Error', 'Cannot access ESLifier_Data/settings.json')
        else:
            os.makedirs(os.path.dirname(settings_path))
            settings_data = {"version": CURRENT_VERSION}
            try:
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, ensure_ascii=False, indent=4)
            except:
                QMessageBox.warning(None, 'Access Error', 'Cannot access/create ESLifier_Data/settings.json')

def luhn_checksum(data: bytes) -> int:
    total = 0
    for i, digit in enumerate(reversed(data)):
        if i % 2 == 0:
            digit *= 2
            if digit > 255:
                digit -= 256
        total += digit
    return (256 - (total % 256)) % 256

def connection_result(is_latest: bool, latest_version: str):
    if not is_latest:
        QMessageBox.warning(None, 'ESLifier Outdated', f"There exists a new version of ESLifier (v{latest_version}).\n"\
                                                        "It is recommended to update as it could contain critical changes,\n"\
                                                        "bug fixes, or additional file patchers.")
        
class github_connect(QObject):
    finished_signal = pyqtSignal(bool, str)
    def check_version(self):
        is_latest, latest_version = self.connect_to_github()
        self.finished_signal.emit(is_latest, latest_version)
            
    def connect_to_github(self) -> tuple[bool, str]:
        try:
            api_url = f"https://api.github.com/repos/MaskPlague/ESLifier/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            latest_release_info: dict[str, str] = response.json()
            latest_version = latest_release_info["tag_name"]
            latest_version = latest_version.removeprefix('v')
            major, minor, patch = [int(x, 10) for x in latest_version.split('.')]
            latest_version_tuple = (major, minor, patch)
            if latest_version_tuple > VERSION_TUPLE:
                return False, latest_version
            else:
                return True, latest_version
        except:
            return True, '0'
        
def conditions_connection_result(conditions_success: bool , ignored_success: bool):
    if not conditions_success:
        QMessageBox.warning(None, 'Master Patcher Conditions Update Failed', 'Failed to download latest patcher conditions from GitHub.\n'\
                                                                     'Ensure you have an active internet connection.\n'\
                                                                     'Using outdated patcher conditions may cause certain files to not be patched.')
    elif not ignored_success:
        QMessageBox.warning(None, 'Master Ignored Files Update Failed', 'Failed to download latest ignored files list from GitHub.\n'\
                                                                     'Ensure you have an active internet connection.')

class get_latest_patcher_conditions(QObject):
    finished_signal = pyqtSignal(bool, bool)
    def fetch_conditions(self):
        conditions_success = self.download_conditions()
        ignored_success = self.download_ignored_files()
        self.finished_signal.emit(conditions_success, ignored_success)
            
    def download_conditions(self) -> bool:
        try:
            url = "https://raw.githubusercontent.com/MaskPlague/ESLifier/refs/heads/main/src/master_patch_conditions.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            conditions_data: dict[str] = json.loads(response.text)
            github_conditions_version = conditions_data.get("version", -1)
            filename = os.path.normpath("ESLifier_Data/master_patch_conditions.json")
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        local_conditions_data: dict[str] = json.load(f)
                        f.close()
                except:
                    local_conditions_data = {}
                local_conditions_version = local_conditions_data.get("version", -1)
            else:
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                local_conditions_version = -1
            if github_conditions_version <= local_conditions_version:
                print(f"~Local master_patcher_conditions.json is version {local_conditions_version} which is up to date.")
                return True
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(conditions_data, f, ensure_ascii=False, indent=4)
            print(f"~Updated to master_patcher_conditions.json version {github_conditions_version} from GitHub.")
            return True
        except Exception as e:
            print("~Failed to update master_patcher_conditions.json; no connection?")
            print(e)
            return False
        
    def download_ignored_files(self) -> bool:
        try:
            url = "https://raw.githubusercontent.com/MaskPlague/ESLifier/refs/heads/main/src/master_ignored_files.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            conditions_data: dict[str] = json.loads(response.text)
            github_conditions_version = conditions_data.get("version", -1)
            filename = os.path.normpath("ESLifier_Data/master_ignored_files.json")
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        local_conditions_data: dict[str] = json.load(f)
                        f.close()
                except:
                    local_conditions_data = {}
                local_conditions_version = local_conditions_data.get("version", -1)
            else:
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                local_conditions_version = -1
            if github_conditions_version <= local_conditions_version:
                print(f"~Local master_ignored_files.json is version {local_conditions_version} which is up to date.")
                return True
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(conditions_data, f, ensure_ascii=False, indent=4)
            print(f"~Updated to master_ignored_files.json version {github_conditions_version} from GitHub.")
            return True
        except Exception as e:
            print("~Failed to update master_ignored_files.json; no connection?")
            print(e)
            return False
        
def curdirIsWritable() -> bool:
    try:
        test_file = os.path.join(os.getcwd(), 'eslifierTestFile.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('Testing if ESLifier is in a non-protected folder')
            f.close()
        os.remove(test_file)
        return True
    except:
        return False

class main_window(QMainWindow):
    def __init__(self):
        super().__init__()
        if getattr(sys, 'frozen', False):
            try:
                os.chdir(os.path.dirname(sys.executable))
            except Exception as e:
                raise RuntimeError(f"ESLifier cannot change working directory: {e}")
            settings_path = os.path.normpath('ESLifier_Data/settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings_data: dict[str, str|bool] = json.load(f)
                version = settings_data.get('version', '0.0.0')
                major, minor, patch = [int(x, 10) for x in version.split('.')] 
                version_tuple = (major, minor, patch)
                if VERSION_TUPLE > version_tuple:
                    verify_luhn_checksum('ESLifier.exe')
            elif not curdirIsWritable():
                QMessageBox.critical(None, "EXE is in a Protected Folder!", "ESLifier is in a protected folder, please move its exe outside of any C:/User/USERNAME/ folder or program files folder.")
                return 
            else:
                verify_luhn_checksum('ESLifier.exe')
        
        self.setWindowTitle("ESLifier v" + CURRENT_VERSION)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.resize(1300, 500)
        self.move(100,50)
        self.log_stream = log_stream(self, CURRENT_VERSION)
        self.setWindowIcon(QIcon(":/images/ESLifier.png"))
        self.setFocus()
        self.rebuild_lists = False
        self.settings_widget = settings(COLOR_MODE, self)
        check_for_update = self.settings_widget.settings.get('check_for_updates', True)
        if check_for_update:
            self.github_thread = QThread()
            self.github_connection = github_connect()
            self.github_connection.moveToThread(self.github_thread)
            self.github_thread.started.connect(self.github_connection.check_version)
            self.github_connection.finished_signal.connect(connection_result)
            self.github_connection.finished_signal.connect(self.github_thread.quit)
            self.github_thread.start()

            self.conditions_thread = QThread()
            self.conditions_connection = get_latest_patcher_conditions()
            self.conditions_connection.moveToThread(self.conditions_thread)
            self.conditions_thread.started.connect(self.conditions_connection.fetch_conditions)
            self.conditions_connection.finished_signal.connect(self.conditions_thread.quit)
            self.conditions_connection.finished_signal.connect(conditions_connection_result)
            self.conditions_thread.start()
        else:
            print("~GitHub connection is disabled via user's settings.")

        if COLOR_MODE == 'Light':
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("Gray"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("Black"))
            palette.setColor(QPalette.ColorRole.Button, QColor("Light Grey"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("White"))
            self.setPalette(palette)

        self.main_widget = main(self.log_stream, self, COLOR_MODE)
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
        else:
            self.tabs.setStyleSheet("""
                QTabWidget::pane { /* The tab widget frame */
                    border-top: 1px solid rgb(255,255,255);
                }""")

        self.MAIN_TAB = 0
        self.SETTINGS_TAB = 1
        self.HELP_TAB = 2

        self.tabs.addTab(self.main_widget, "  Main  ")
        self.tabs.setTabToolTip(self.MAIN_TAB, "This is the Main Page, scan your skyrim folder and select plugins to flag or compress.")
        self.tabs.addTab(self.settings_widget, "  Settings  ")
        self.tabs.setTabToolTip(self.SETTINGS_TAB, "This is the settings page. Certain settings will effect what plugins will display after scanning.")
        self.tabs.addTab(QWidget(), "  Help?  ")
        self.initial = True
        self.tabs.currentChanged.connect(self.tab_changed)
        self.previous_tab = self.MAIN_TAB
        self.tab_changed(self.MAIN_TAB)
        self.layout().setAlignment(Qt.AlignmentFlag.AlignHCenter)

        display_widget = QWidget()
        tabs_layout = QVBoxLayout()
        tabs_layout.addWidget(self.tabs)
        display_widget.setLayout(tabs_layout)
        self.setCentralWidget(display_widget)
        self.main_widget.calculate_stats()

    def tab_changed(self, index: int):
        self.update_settings()
        if self.rebuild_lists:
            self.rebuild_lists = False
            self.main_widget.list_compact.create()
            self.main_widget.list_eslify.create()
        if index == self.HELP_TAB:
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
            or (self.settings_widget.settings['mo2_mode'] 
                and (self.settings_widget.settings['mo2_modlist_txt_path'] == '' 
                     or self.settings_widget.settings['overwrite_path'] == ''))):
            self.tabs.setCurrentIndex(self.SETTINGS_TAB)
            self.tabs.blockSignals(False)
            if not self.initial:
                self.no_path_set()
            else:
                self.initial = False
            return
        self.initial = False
        if not self.settings_widget.output_folder_name_valid or not 'eslifier' in self.settings_widget.settings['output_folder_name'].lower():
            self.tabs.setCurrentIndex(self.SETTINGS_TAB)
            QMessageBox.warning(None, "Invalid Folder Name", f"Enter a valid output folder name.")
            self.tabs.blockSignals(False)
            return
        
        output_path = self.settings_widget.settings['output_folder_path']
        data_path = self.settings_widget.settings['skyrim_folder_path']
        plugins_txt = self.settings_widget.settings['plugins_txt_path']
        mo2_mode = self.settings_widget.settings['mo2_mode']
        if mo2_mode:
            mo2_path = self.settings_widget.settings['mo2_modlist_txt_path']
            overwrite_path = self.settings_widget.settings['overwrite_path']

        error_message = ''
        output_path_exists = False
        data_path_exists = False
        if not os.path.exists('bsarch/bsarch.exe'):
            error_message += ("The included BSArch.exe must be present in a folder\nnamed bsarch adjactent to ESLifier:\n\n"+
                              f"{os.path.split(os.getcwd())[1]}/\n"+
                              "├─── bsarch/\n"
                              "│        └── BSArch.exe\n"
                              "└─── ESLifier.exe\n\n")
                              
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
        if mo2_mode and not os.path.exists(overwrite_path):
            error_message += "Invalid Overwrite Directory, it does not exist.\n'"
        if mo2_mode and not mo2_path.lower().endswith('modlist.txt'):
            error_message += "Invalid MO2 modlist.txt, the path should be to the file not directory.\n"
        if mo2_mode and not os.path.exists(mo2_path):
            error_message += "Invalid MO2 modlist.txt, the file does not exist.\n"

        if len(error_message) > 10:
            self.tabs.setCurrentIndex(self.SETTINGS_TAB)
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
        self.set_colors()
        self.main_widget.skyrim_folder_path =                   self.settings_widget.settings.get('skyrim_folder_path', '')
        self.main_widget.output_folder_path =                   self.settings_widget.settings.get('output_folder_path', '')
        self.main_widget.output_folder_name =                   self.settings_widget.settings.get('output_folder_name', "ESLifier Output")
        self.main_widget.mo2_mode =                             self.settings_widget.settings.get('mo2_mode', False)
        self.main_widget.modlist_txt_path =                     self.settings_widget.settings.get('mo2_modlist_txt_path', '')
        self.main_widget.plugins_txt_path =                     self.settings_widget.settings.get('plugins_txt_path', '')
        self.main_widget.overwrite_path =                       self.settings_widget.settings.get('overwrite_path', '')
        self.main_widget.update_header =                        self.settings_widget.settings.get('update_header', True)
        self.main_widget.generate_cell_master =                 self.settings_widget.settings.get('generate_cell_master', True)
        self.main_widget.list_compact.filter_changed_cells =    self.settings_widget.settings.get('enable_cell_changed_filter', True)
        self.main_widget.list_compact.filter_interior_cells =   self.settings_widget.settings.get('enable_interior_cell_filter', False)
        self.main_widget.list_compact.show_cells =              self.settings_widget.settings.get('show_cells', True)
        self.main_widget.list_compact.show_esms =               self.settings_widget.settings.get('show_esms', True)
        self.main_widget.list_compact.show_dlls =               self.settings_widget.settings.get('show_dlls', False)
        self.main_widget.list_compact.filter_worldspaces =      self.settings_widget.settings.get('filter_worldspaces', True)
        self.main_widget.list_compact.filter_weather =          self.settings_widget.settings.get('filter_weathers', False)
        self.main_widget.list_compact.cell_master =             self.settings_widget.settings.get('generate_cell_master', True)
        self.main_widget.list_eslify.hidden_columns =           self.settings_widget.settings.get('left_hidden_columns', '')
        self.main_widget.list_compact.hidden_columns =          self.settings_widget.settings.get('right_hidden_columns', '')
        self.main_widget.list_eslify.filter_changed_cells =     self.settings_widget.settings.get('enable_cell_changed_filter', True)
        self.main_widget.list_eslify.filter_interior_cells =    self.settings_widget.settings.get('enable_interior_cell_filter', False)
        self.main_widget.list_eslify.show_cells =               self.settings_widget.settings.get('show_cells', True)
        self.main_widget.list_eslify.show_esms =                self.settings_widget.settings.get('show_esms', True)
        self.main_widget.list_eslify.filter_worldspaces =       self.settings_widget.settings.get('filter_worldspaces', True)
        self.main_widget.list_eslify.cell_master =              self.settings_widget.settings.get('generate_cell_master', True)
        self.main_widget.settings =                             self.settings_widget.settings.copy()
        self.main_widget.hash_output =                          self.settings_widget.settings.get('hash_output', True)

        if self.settings_widget.settings.get('enable_patch_new', False):
            self.main_widget.scan_and_patch_new_button_spacer.changeSize(10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.main_widget.scan_and_patch_new_button.setHidden(False)
        else:
            self.main_widget.scan_and_patch_new_button_spacer.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.main_widget.scan_and_patch_new_button.setHidden(True)
            
    def set_colors(self):
        inner_color = self.settings_widget.settings['inner_color']
        outer_color = self.settings_widget.settings['outer_color']
        if COLOR_MODE == 'Light':
            self.setStyleSheet("""
                QMainWindow{           
                    background-color: qradialgradient(
                                cx: 0.5, cy: 0.5, radius: 0.8,
                                fx: 0.5, fy: 0.5,
                                stop: 0 """+ inner_color +""", stop: 1 """+ outer_color +"""
                                );
                }
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
        else:
            self.setStyleSheet("""
                QMainWindow{           
                    background-color: qradialgradient(
                                cx: 0.5, cy: 0.5, radius: 0.8,
                                fx: 0.5, fy: 0.5,
                                stop: 0 """+ inner_color +""", stop: 1 """+ outer_color +"""
                                );
                }""")
        
    def closeEvent(self, a0):
        try:
            self.log_stream.running = False
            self.log_stream.flush()
            self.log_stream.close()
        except:
            pass
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.excepthook = sys.__excepthook__
        for window in QApplication.topLevelWidgets():
            window.close()
        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        self.log_stream.center_on_parent()
        return super().resizeEvent(a0)
    
    def moveEvent(self, a0):
        self.log_stream.center_on_parent()
        return super().moveEvent(a0)

try:
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
except Exception as e:
    timestamp = datetime.now().isoformat(timespec='minutes').replace(':', '-')
    crash_log = f'crash-{timestamp}.log'
    try:
        sys.stderr = sys.__stderr__
        if os.path.exists('ESLifier_Data') and not os.path.exists('ESlifier_Data/Crash Logs'):
            os.makedirs(os.path.normpath('ESLifier_Data/Crash Logs/'))
        with open(os.path.normpath(os.path.join('ESLifier_Data/Crash Logs/', crash_log)), 'w+', encoding='utf-8') as f:
            traceback.print_exc(file=f)
        QMessageBox.critical(None, 'ESLifier Error', 'Check latest crash log in ESLifier_Data/Crash Logs')
    except Exception as e1:
        crash_log_file = os.path.normpath(os.path.join(os.getcwd(), crash_log))
        try:
            with open(crash_log_file, 'w+', encoding='utf-8') as f:
                traceback.print_exc(file=f)
                f.write(f'Failed to open crash log directory: \n')
                f.write(e1)
            QMessageBox.critical(None, 'ESLifier Error', f'Failed to open crash log directory, creating crash log at: {crash_log_file}')
        except Exception as e2:
            QMessageBox.critical(None, 'ESLifier Error', f'Failed to create crash log, error: {e2}\ncrash cause: {e}')
