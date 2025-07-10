import mobase
import subprocess
import os

from .ESLifier_notifier import ESLifier_Notifier
from .ESLifier_blacklist import blacklist_window

try:
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton, QVBoxLayout, QFileDialog
except ImportError:
    from PyQt5.QtCore import QCoreApplication
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QDialog, QMessageBox, QPushButton, QVBoxLayout, QFileDialog
            
class ESLifier(mobase.IPluginTool):
    def __init__(self):
        super(ESLifier, self).__init__()
    
    def init(self, organiser = mobase.IOrganizer):
        self._organizer = organiser
        self.main_dialog = QDialog()
        self.settings_dialog = QDialog()
        self.thread = QThread()
        self.check_again = False
        self.needs_flag_dict = {}
        self.needs_compacting_flag_dict = {}
        self.hash_mismatches = []

        icon_path = os.path.join(os.path.split(self._organizer.getPluginDataPath())[0], 'ESLifier MO2 Integration')
        self.eslifier_icon = QIcon(icon_path + '\\ESLifier.ico')
        self.main_dialog.setWindowIcon(self.eslifier_icon)
        self.eslifier_icon_notif = QIcon(icon_path + '\\ESLifier_with_notif_badge.ico')
        self.eslifier_icon_greyed_out = QIcon(icon_path + '\\ESLifier_greyed_out.ico')

        self.eslifier_button = QToolButton()
        self.eslifier_button.setIcon(self.eslifier_icon_greyed_out)
        self.eslifier_button.clicked.connect(self.display)

        self._organizer.onUserInterfaceInitialized(self.create)
        self.icon_path = os.path.join(os.path.split(self._organizer.getPluginDataPath())[0], 'ESLifier MO2 Integration')
        self.notifier = ESLifier_Notifier()
        self.notifier.init(self._organizer)
        self.blacklist_add = blacklist_window(False)
        self.blacklist_remove = blacklist_window(True)
        return True
        
    def name(self) -> str:
        return "ESLifier"
    
    def localizedName(self) -> str:
        return self.tr("ESLifier")
    
    def author(self) -> str:
        return "MaskPlague"

    def description(self):
        return self.tr("ESLifier's MO2 Plugin Integration")
    
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(2, 0, 0, mobase.ReleaseType.BETA)
    
    def requirements(self):
        return[]
    
    def settings(self):
        return [
            mobase.PluginSetting("Display Plugins With Cells", self.tr("Display plugins that can be light with Cells."), True),
            mobase.PluginSetting("Scan ESMs", self.tr("Scan plugins that are flagged as ESM."), False),
            mobase.PluginSetting("Use 1.71 Header Range", self.tr("Use the new 1.71 Header range when scanning for plugins that can be light."), True),
            mobase.PluginSetting("ESLifier Folder", self.tr("Set this to the folder that holds ESLifier.exe."), ""),
        ]
    
    def create_label_check_box_setting_pair(self, layout: QGridLayout, text: str, row: int) -> QCheckBox:
        label = QLabel(text)
        check_box = QCheckBox()
        def changed():
            self._organizer.setPluginSetting(self.name(), text, check_box.isChecked())
        check_box.checkStateChanged.connect(changed)
        layout.addWidget(label, row, 0)
        layout.addWidget(check_box, row, 1)
        return check_box
    
    def create_settings_dialog(self, _):
        self.settings_dialog = QDialog()
        layout = QGridLayout()
        self.settings_dialog.setLayout(layout)

        self.notifications_check_box = self.create_label_check_box_setting_pair(layout, "Enable Notifications", 0)
        self.esms_check_box = self.create_label_check_box_setting_pair(layout, "scan_esms", 1)
        self.header_check_box = self.create_label_check_box_setting_pair(layout, "Use 1.71 Header Range", 2)

        folder = self._organizer.pluginSetting(self.name(), "ESLifier Folder")
        if len(folder) > 30:
            self.folder_path = QLabel(f"...{folder[-30:]}")
        else:
            self.folder_path = QLabel(folder)
        self.folder_path.setToolTip("Set this to the folder that holds ESLifier.exe")
        layout.addWidget(self.folder_path, 3, 0)
        path_button = self.button_maker("Explore", self.set_eslifier_path)
        path_button.setToolTip("Set this to the folder that holds ESLifier.exe")
        layout.addWidget(path_button, 3, 1)

        done_button = QPushButton("Done")
        def done():
            self.settings_dialog.hide()
            self._organizer.refresh()
        done_button.clicked.connect(done)
        layout.addWidget(done_button, 4, 0)

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
    
    def start_eslifier(self):
        eslifier_folder = self._organizer.pluginSetting("ESLifier", "ESLifier Folder")
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
        self.notifier.scan_for_eslable()
        self.blacklist_add.blacklist.blacklist = self.notifier.flag_dict
        self.blacklist_add.blacklist.blacklist_path = blacklist_path
        self.blacklist_add.blacklist.create(False)
        self.blacklist_add.show()

    def remove_from_blacklist(self):
        eslifier_folder = self._organizer.pluginSetting("ESLifier", "ESLifier Folder")
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
            self._organizer.setPluginSetting("ESLifier", "ESLifier Folder", path)

    def create(self, _):
        v_layout = QVBoxLayout()
        self.dialog.setLayout(v_layout)
        self.dialog.setWindowTitle('ESLifier MO2 Integration')

        v_layout.addWidget(self.button_maker("Start ESLifier", self.start_eslifier, True))
        v_layout.addWidget(self.button_maker("Add Plugins to Blacklist", self.add_to_blacklist))
        v_layout.addWidget(self.button_maker("Remove Plugins from Blacklist", self.remove_from_blacklist))
        v_layout.addWidget(self.button_maker("Set ESLifier Path", self.set_eslifier_path))
        v_layout.addWidget(self.button_maker("Exit", None, True))
        
        #Install notification button to MO2 tool bar
        tool_bar = self._parentWidget().findChild(QToolBar, 'toolBar')
        if tool_bar:
            try:
                action = tool_bar.children()[-9].actions()[0]
                tool_bar.insertWidget(action, self.eslifier_button)
            except:
                try:
                    installed = False
                    for child in tool_bar.children():
                        if isinstance(check_plugins, QToolButton) and child.text() == 'Notifications':
                            installed = True
                            tool_bar.insertWidget(child_action, self.eslifier_button)
                            break
                    if not installed:
                        raise NameError("Notifications not found")
                except:
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


    def button_maker(self, name, function, hide=False):
        button = QPushButton(name)
        if hide:
            button.clicked.connect(self.main_dialog.hide)
        if function:
            button.clicked.connect(function)
        return button

    def display(self):
        self.main_dialog.raise_()
        self.main_dialog.show()
        return
    
    def display_settings(self):
        notifications = self._organizer.pluginSetting(self.name(), "Enable Notifications")
        self.notifications_check_box.setChecked(notifications)

        esms = self._organizer.pluginSetting(self.name(), "Scan ESMs")
        self.esms_check_box.setChecked(esms)

        header = self._organizer.pluginSetting(self.name(), "Use 1.71 Header Range")
        self.header_check_box.setChecked(header)

        self.settings_dialog.raise_()
        self.settings_dialog.show()
        return
    
    def display_notifications(self):
        self.notifcation_display.create(self.hash_mismatches, self.needs_flag_dict, self.needs_compacting_flag_dict)


class CheckWorker(QObject):
    finished_signal = pyqtSignal(bool, dict, dict, list)
    def __init__(self, eslifier: ESLifier, plugin_checker: check_plugins, scan_esms, eslifier_folder, new_header, compare_hashes, ignore_list, filter):
        super().__init__()
        self.eslifier = eslifier
        self.plugin_checker = plugin_checker
        self.scan_esms = scan_esms
        self.eslifier_folder = eslifier_folder
        self.new_header = new_header
        self.compare_hashes = compare_hashes
        self.ignore_list = ignore_list
        self.filter = filter

    def check_for_esl(self):
        plugin_files_list = [plugin for plugin in self.eslifier._organizer.findFiles('', self.filter) if os.path.basename(plugin) not in self.ignore_list]
        flag, needs_flag_dict, needs_compacting_flag_dict, hash_mismatches = self.plugin_checker.scan_for_eslable(self.scan_esms, self.eslifier_folder, self.new_header, 
                                                                                                 self.compare_hashes, plugin_files_list)
        self.finished_signal.emit(flag, needs_flag_dict, needs_compacting_flag_dict, hash_mismatches)