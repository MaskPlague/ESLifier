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
        self.dialog = QDialog()
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
    
    def displayName(self):
        return self.tr("ESLifier")
    
    def tooltip(self):
        return self.tr("")
    
    def icon(self):
        return QIcon(self.icon_path + '\\ESLifier.ico')

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
        f, f_c, f_i_c, c, c_c, c_i_c, = self.notifier.return_eslable()
        full_list = f.copy()
        full_list.extend(c)
        self.blacklist_add.blacklist.blacklist = full_list
        self.blacklist_add.blacklist.needs_flag_new_cell_list = f_c
        self.blacklist_add.blacklist.needs_flag_interior_cell_list = f_i_c
        self.blacklist_add.blacklist.needs_compacting_list = c
        self.blacklist_add.blacklist.needs_compacting_new_cell_list = c_c
        self.blacklist_add.blacklist.needs_compacting_interior_cell_list = c_i_c
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

    def button_maker(self, name, function, hide=False):
        button = QPushButton(name)
        if hide:
            button.clicked.connect(self.dialog.hide)
        if function:
            button.clicked.connect(function)
        return button

    def display(self):
        self.dialog.raise_()
        self.dialog.show()
        return