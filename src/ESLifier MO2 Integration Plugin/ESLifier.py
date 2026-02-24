import mobase
import subprocess
import os
import json

from .ESLifier_notifier import check_files as notifier
from .ESLifier_blacklist import blacklist_window
from .ESLifier_notification_display import notification_display_dialog

try:
    from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal, QThread, QTimer
    from PyQt6.QtGui import QIcon, QColor
    from PyQt6.QtWidgets import (QDialog, QMessageBox, QPushButton, QVBoxLayout, QFileDialog, QToolButton,
                                  QToolBar, QCheckBox, QLabel, QGridLayout, QWidget, QApplication)
except ImportError:
    from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal, QThread, QTimer
    from PyQt5.QtGui import QIcon, QColor
    from PyQt5.QtWidgets import (QDialog, QMessageBox, QPushButton, QVBoxLayout, QFileDialog, QToolButton,
                                  QToolBar, QCheckBox, QLabel, QGridLayout, QWidget, QApplication)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal, QThread, QTimer
    from PyQt6.QtGui import QIcon, QColor
    from PyQt6.QtWidgets import (QDialog, QMessageBox, QPushButton, QVBoxLayout, QFileDialog, QToolButton,
                                  QToolBar, QCheckBox, QLabel, QGridLayout, QWidget, QApplication)
            
class ESLifier(mobase.IPluginTool):
    def __init__(self):
        super(ESLifier, self).__init__()
    
    def name(self) -> str:
        return "ESLifier"
    
    def localizedName(self) -> str:
        return self.tr("ESLifier")
    
    def author(self) -> str:
        return "MaskPlague"

    def description(self):
        return self.tr("ESLifier's MO2 Plugin Integration")
    
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 5, 1, mobase.ReleaseType.FINAL)
    
    def requirements(self):
        return [mobase.PluginRequirementFactory.gameDependency({
                "Skyrim Special Edition",
                "Skyrim VR"
            })]
    
    def settings(self):
        return [
            mobase.PluginSetting("Enable Notifications", self.tr("Enable ESLifier's notifications"), True),
            mobase.PluginSetting("Scan ESMs", self.tr("Scan plugins that are flagged as ESM."), False),
            mobase.PluginSetting("Use 1.71 Header Range", self.tr("Use the new 1.71 Header range when scanning for plugins that can be light."), True),
            mobase.PluginSetting("ESLifier Folder", self.tr("Set this to the folder that holds ESLifier.exe."), ""),
            mobase.PluginSetting("Compare File Hashes", self.tr("Compare current file hashes to last ESLifier run."), True),
            mobase.PluginSetting("Compare Only Game Plugins", self.tr("If 'Compare File Hashes' and this are enabled:\nonly check game plugins (faster),\nelse compare all file hashes (slower)."), False),
            mobase.PluginSetting("Detect Conflict Changes", self.tr("Detect if a file conflict change has occured since ESLifier last ran."), True)
        ]
    
    def displayName(self):
        return self.tr("ESLifier")
    
    def tooltip(self):
        return self.tr("")
    
    def icon(self):
        return self.eslifier_icon

    def getFiles(self):
        return

    def tr(self, str):
        return QCoreApplication.translate("ESLifier", str)
    
    def display(self):
        self.main_dialog.raise_()
        self.main_dialog.show()
        return

    def init(self, organiser = mobase.IOrganizer):
        self._organizer = organiser
        icon_path = os.path.join(os.path.dirname(self._organizer.getPluginDataPath()), 'ESLifier MO2 Integration')

        self._init_state(icon_path)
        self._create_icons(icon_path)
        self._create_throbber(icon_path)

        self._create_eslifier_button()
        
        self._hook_up_callbacks()

        QApplication.instance().aboutToQuit.connect(self._stop_worker_if_running)

        return True

    
    def _init_state(self, icon_path):
        self.validGame = True
        self.main_dialog = QDialog()
        self.settings_dialog = QDialog()
        self.thread = QThread()
        self.needs_flag_dict = {}
        self.needs_compacting_flag_dict = {}
        self.hash_mismatches = []
        self.conflict_changes = []
        self.lost_to_overwrite = []
        self.master_not_enabled = False
        self.throbber_iterator = 0

        self.notifcation_display = notification_display_dialog(icon_path)
        self.blacklist_add = blacklist_window(False, self.scan_files)
        self.blacklist_remove = blacklist_window(True, self.scan_files)
    
    def _create_icons(self, icon_path):
        self.eslifier_icon_default = QIcon(icon_path + '\\ESLifier.ico')
        self.eslifier_icon = self.eslifier_icon_default
        self.main_dialog.setWindowIcon(self.eslifier_icon)
        self.eslifier_icon_notif = QIcon(icon_path + '\\ESLifier_with_notif_badge.ico')
        self.eslifier_icon_greyed_out = QIcon(icon_path + '\\ESLifier_greyed_out.ico')
    
    def _create_throbber(self, icon_path):
        throbber_top_icon = QIcon(icon_path + '\\ESLifier_throbber_top.ico')
        throbber_right_icon = QIcon(icon_path + '\\ESLifier_throbber_right.ico')
        throbber_bottom_icon = QIcon(icon_path + '\\ESLifier_throbber_bottom.ico')
        throbber_left_icon = QIcon(icon_path + '\\ESLifier_throbber_left.ico')
        self.eslifier_thobber = [throbber_top_icon, throbber_right_icon, throbber_bottom_icon, throbber_left_icon]
        self.throbber_timer = QTimer()
        self.throbber_timer.timeout.connect(self._throbber_iterate)
        self.throbber_timer.setInterval(250)
    
    def _create_eslifier_button(self):
        self.eslifier_button = QToolButton()
        self.eslifier_button.setIcon(self.eslifier_icon_greyed_out)
        self.eslifier_button.clicked.connect(self.display)

    def _hook_up_callbacks(self):
        self._organizer.onUserInterfaceInitialized(self.create)
        self._organizer.onUserInterfaceInitialized(self._create_settings_dialog)
        self._organizer.pluginList().onRefreshed(self.scan_files)
        self._organizer.pluginList().onPluginStateChanged(self.scan_if_cell_master_state_changed)
    
    def _throbber_iterate(self):
        if self.throbber_iterator > 3:
            self.throbber_iterator = 0
        self.eslifier_button.setIcon(self.eslifier_thobber[self.throbber_iterator])
        self.throbber_iterator += 1
    
    def scan_if_cell_master_state_changed(self, state_changes):
        if not self.validGame:
            return
        for mod in state_changes:
            if mod == 'ESLifier_Cell_Master.esm':
                self.scan_files()
                break

    def _stop_worker_if_running(self):
        if hasattr(self, 'worker') and self.worker and self.worker.running:
            self.worker.stop()
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            self.thread.quit()

    def scan_files(self):
        if not self.validGame:
            return
        notifications_enabled = self._organizer.pluginSetting(self.name(), "Enable Notifications")
        self._stop_worker_if_running()

        if notifications_enabled:
            self.throbber_timer.start()
            scan_esms = self._organizer.pluginSetting(self.name(), "Scan ESMs")
            eslifier_folder = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
            new_header = self._organizer.pluginSetting(self.name(), "Use 1.71 Header Range")
            blacklist_path = os.path.join(eslifier_folder, 'ESLifier_Data/blacklist.json')
            compare_hashes = self._organizer.pluginSetting(self.name(), "Compare File Hashes")
            detect_conflict_changes = self._organizer.pluginSetting(self.name(), "Detect Conflict Changes")
            only_plugins = self._organizer.pluginSetting(self.name(), "Compare Only Game Plugins")
            if os.path.exists(blacklist_path):
                try:
                    with open(blacklist_path, 'r', encoding='utf-8') as f:
                        ignore_list: list[str] = json.load(f)
                        ignore_list.append("ESLifier_Cell_Master.esm")
                except Exception as e:
                    ignore_list = ["ESLifier_Cell_Master.esm"]
            else:
                ignore_list = ["ESLifier_Cell_Master.esm"]

            if scan_esms:
                filter = "*.es[pm]"
            else:
                filter = "*.esp"

            self.worker = CheckWorker(self._organizer, scan_esms, eslifier_folder, new_header, compare_hashes, 
                                      detect_conflict_changes, only_plugins, ignore_list, filter)
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.check_files)
            self.worker.finished_signal.connect(self.update_icon)
            self.worker.finished_signal.connect(self.thread.quit)
            self.worker.finished_signal.connect(self.worker.deleteLater)
            self.thread.start()
        else:
            self._grey_out_icon()
        return

    def update_icon(self, any_eslable_or_issue, needs_flag_dict, needs_compacting_flag_dict, hash_mismatches, conflict_changes, lost_to_overwrite, master_enabled, early_exit):
        if not early_exit:
            self.throbber_timer.stop()
        else:
            self.scan_files()
        if any_eslable_or_issue:
            self.eslifier_button.setIcon(self.eslifier_icon_notif)
            self.eslifier_icon = self.eslifier_icon_notif
            self.needs_flag_dict = needs_flag_dict
            self.needs_compacting_flag_dict = needs_compacting_flag_dict
            self.hash_mismatches = hash_mismatches
            self.lost_to_overwrite = lost_to_overwrite
            self.conflict_changes = conflict_changes
            self.master_not_enabled = master_enabled
            self.notification_button.show()
        else:
            self._grey_out_icon()
        return
    
    def _grey_out_icon(self):
        self.eslifier_button.setIcon(self.eslifier_icon_greyed_out)
        self.eslifier_icon = self.eslifier_icon_default
        self.needs_flag_dict.clear()
        self.needs_compacting_flag_dict.clear()
        self.hash_mismatches.clear()
        self.conflict_changes.clear()
        self.master_not_enabled = False
        self.notification_button.hide()
    
    def _create_label_check_box_setting_pair(self, layout: QGridLayout, text: str, row: int, tool_tip = None) -> QCheckBox:
        label = QLabel(text)
        check_box = QCheckBox()
        if tool_tip:
            label.setToolTip(tool_tip)
            check_box.setToolTip(tool_tip)
        def changed():
            self._organizer.setPluginSetting(self.name(), text, check_box.isChecked())
        check_box.stateChanged.connect(changed)
        layout.addWidget(label, row, 0)
        layout.addWidget(check_box, row, 1)
        return check_box
    
    def _create_settings_dialog(self, _):
        self.settings_dialog = QDialog()
        layout = QGridLayout()
        self.settings_dialog.setLayout(layout)

        self.notifications_check_box = self._create_label_check_box_setting_pair(layout, "Enable Notifications", 0)
        self.esms_check_box = self._create_label_check_box_setting_pair(layout, "Scan ESMs", 1)
        self.header_check_box = self._create_label_check_box_setting_pair(layout, "Use 1.71 Header Range", 2)
        self.compare_file_hashes_check_box = self._create_label_check_box_setting_pair(layout, "Compare File Hashes", 3, "Compare current file hashes to the hashes of the last ESLifier run.")
        self.compare_only_game_plugins_check_box = self._create_label_check_box_setting_pair(layout, "Compare Only Game Plugins", 4, "If 'Compare File Hashes' and this are enabled:\nonly check game plugins (faster),\nelse compare all file hashes (slower).")
        self.detect_file_conflict_changes_check_box = self._create_label_check_box_setting_pair(layout, "Detect Conflict Changes", 5, "Detect if a file conflict change has occured since ESLifier last ran.")

        folder = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
        if len(folder) > 30:
            self.folder_path = QLabel(f"...{folder[-30:]}")
        else:
            self.folder_path = QLabel(folder)
        self.folder_path.setToolTip("Set this to the folder that holds ESLifier.exe")
        layout.addWidget(self.folder_path, 6, 0)
        path_button = self._button_maker("Explore", self.set_eslifier_path)
        path_button.setToolTip("Set this to the folder that holds ESLifier.exe")
        layout.addWidget(path_button, 6, 1)

        done_button = QPushButton("Done")
        def done():
            self.settings_dialog.hide()
            self._organizer.refresh()
        done_button.clicked.connect(done)
        layout.addWidget(done_button, 7, 0)
    
    def start_eslifier(self):
        eslifier_folder = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
        eslifier_exe = os.path.join(eslifier_folder, 'ESLifier.exe')
        if os.path.exists(eslifier_exe):
            try:
                if os.name == 'nt':
                    os.startfile(eslifier_exe)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', eslifier_exe])
                else:
                    subprocess.Popen(['open', eslifier_exe])
            except Exception as e:
                print(f"Error starting ESLifier: {e}")
        else:
            self.no_path_set()

    def no_path_set(self):
        error_message = QMessageBox(parent=self._parentWidget())
        error_message.setIcon(QMessageBox.Icon.Warning)
        error_message.setWindowTitle("ESLifier Folder Not Set")
        error_message.setText('Please set the ESLifier Folder setting of the ESLifier plugin in MO2\'s plugin settings or via the button.')
        error_message.addButton(QMessageBox.StandardButton.Ok)
        error_message.show()

    def add_to_blacklist(self):
        eslifier_folder = self._organizer.pluginSetting("ESLifier", "ESLifier Folder")
        if not os.path.exists(eslifier_folder):
            self.no_path_set()
            return
        blacklist_path = os.path.join(eslifier_folder, 'ESLifier_Data/blacklist.json')
        full_dict = self.needs_compacting_flag_dict.copy()
        for key, value in self.needs_flag_dict.items():
            if key not in full_dict:
                full_dict[key] = value
        self.blacklist_add.blacklist.blacklist = full_dict
        self.blacklist_add.blacklist.blacklist_path = blacklist_path
        self.blacklist_add.blacklist.create(False)
        self.blacklist_add.show()

    def remove_from_blacklist(self):
        eslifier_folder = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
        if not os.path.exists(eslifier_folder):
            self.no_path_set()
            return
        blacklist_path = os.path.join(eslifier_folder, 'ESLifier_Data/blacklist.json')
        self.blacklist_remove.blacklist.blacklist_path = blacklist_path
        self.blacklist_remove.blacklist.create(True)
        self.blacklist_remove.show()

    def set_eslifier_path(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        path = dialog.getExistingDirectory(None, "Select the folder that holds ESLifier.exe.", self._organizer.pluginSetting("ESLifier", "ESLifier Folder"))
        if path:
            self._organizer.setPluginSetting(self.name(), "ESLifier Folder", path)
            if len(path) > 30:
                self.folder_path.setText(f"...{path[-30:]}")
            else:
                self.folder_path.setText(path)

    def create(self, _):
        game = self._organizer.managedGame()
        if not game.gameName() in ("Skyrim Special Edition", "Skyrim VR"):
            self.validGame = False
            return
        v_layout = QVBoxLayout()
        self.main_dialog.setLayout(v_layout)
        self.main_dialog.setWindowTitle('ESLifier MO2 Integration')
        self.notification_button = self._button_maker("Show Notifications", self.display_notifications)
        self.notification_button.hide()
        p = self.notification_button.palette()
        p.setColor(p.ColorRole.ButtonText, QColor('Red'))
        self.notification_button.setPalette(p)
        v_layout.addWidget(self._button_maker("Start ESLifier", self.start_eslifier, True))
        v_layout.addWidget(self._button_maker("Add Plugins to Blacklist", self.add_to_blacklist))
        v_layout.addWidget(self._button_maker("Remove Plugins from Blacklist", self.remove_from_blacklist))
        v_layout.addWidget(self._button_maker("Change Plugin Settings", self.display_settings))
        v_layout.addWidget(self.notification_button)
        v_layout.addWidget(self._button_maker("Exit", None, True))
        
        #Install notification button to MO2 tool bar
        tool_bar = self._parentWidget().findChild(QToolBar, 'toolBar')
        if tool_bar:
            try:
                next_install = False
                installed = False
                passed_one = False
                for child in tool_bar.children():
                    if type(child) == QWidget:
                        next_install = True
                    elif isinstance(child, QToolButton) and next_install and not passed_one:
                        passed_one = True
                    elif isinstance(child, QToolButton) and next_install and not installed and passed_one:
                        installed = True
                        child_action = child.actions()[0]
                        tool_bar.insertWidget(child_action, self.eslifier_button)
            except:
                try:
                    installed = False
                    for child in tool_bar.children():
                        if isinstance(child, QToolButton) and child.text() == 'Notifications':
                            installed = True
                            tool_bar.insertWidget(child_action, self.eslifier_button)
                            break
                    if not installed:
                        raise NameError("Notifications not found")
                except:
                    action = tool_bar.children()[-9].actions()[0]
                    tool_bar.insertWidget(action, self.eslifier_button)

    def _button_maker(self, name, function, hide=False):
        button = QPushButton(name)
        if hide:
            button.clicked.connect(self.main_dialog.hide)
        if function:
            button.clicked.connect(function)
        return button
    
    def display_settings(self):
        notifications = self._organizer.pluginSetting(self.name(), "Enable Notifications")
        self.notifications_check_box.setChecked(notifications)

        esms = self._organizer.pluginSetting(self.name(), "Scan ESMs")
        self.esms_check_box.setChecked(esms)

        header = self._organizer.pluginSetting(self.name(), "Use 1.71 Header Range")
        self.header_check_box.setChecked(header)

        hashes = self._organizer.pluginSetting(self.name(), "Compare File Hashes")
        self.compare_file_hashes_check_box.setChecked(hashes)
        
        only_plugins = self._organizer.pluginSetting(self.name(), "Compare Only Game Plugins")
        self.compare_only_game_plugins_check_box.setChecked(only_plugins)

        conflicts = self._organizer.pluginSetting(self.name(), "Detect Conflict Changes")
        self.detect_file_conflict_changes_check_box.setChecked(conflicts)

        path = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
        if len(path) > 30:
            self.folder_path.setText(f"...{path[-30:]}")
        else:
            self.folder_path.setText(path)

        self.settings_dialog.raise_()
        self.settings_dialog.show()
        return
    
    def display_notifications(self):
        self.notifcation_display.create(self.hash_mismatches, self.conflict_changes, self.lost_to_overwrite, self.needs_flag_dict, self.needs_compacting_flag_dict, self.master_not_enabled)


class CheckWorker(QObject):
    finished_signal = pyqtSignal(bool, dict, dict, list, list, list, bool, bool)
    def __init__(self, organizer: mobase.IOrganizer, scan_esms, eslifier_folder, new_header, 
                 compare_hashes, detect_conflict_changes, only_plugins, ignore_list, filter):
        super().__init__()
        self._organizer = organizer
        self.file_checker: notifier = notifier()
        self.scan_esms = scan_esms
        self.eslifier_folder = eslifier_folder
        self.new_header = new_header
        self.compare_hashes = compare_hashes
        self.detect_conflict_changes = detect_conflict_changes
        self.only_plugins = only_plugins
        self.ignore_list = ignore_list
        self.filter = filter
        self.running = True

    def check_files(self):
        mods_path = os.path.normpath(self._organizer.modsPath())
        master_not_enabled = True if self._organizer.pluginList().state("ESLifier_Cell_Master.esm") == 1 else False
        try:
            plugin_files_list = [plugin for plugin in self._organizer.findFiles('', self.filter) if os.path.basename(plugin) not in self.ignore_list and os.path.normpath(plugin).startswith(mods_path)]
        except Exception as e:
            self.finished_signal.emit(False, {}, {}, [], [], [], False, True)
            return
        flag, needs_flag_dict, needs_compacting_flag_dict, hash_mismatches, conflict_changes, lost_to_overwrite = self.file_checker.scan_files(
                                    self.scan_esms, self.eslifier_folder, self.new_header, self.compare_hashes, 
                                    self.detect_conflict_changes, self.only_plugins, plugin_files_list, self._organizer)
        if master_not_enabled:
            flag = True
        if self.running:
            self.finished_signal.emit(flag, needs_flag_dict, needs_compacting_flag_dict, hash_mismatches, conflict_changes, lost_to_overwrite, master_not_enabled, False)
        else:
            self.finished_signal.emit(False, {}, {}, [], [], [], False, True)

    def stop(self):
        self.file_checker.stop()
        self.running = False
