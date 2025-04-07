import os
import json
import shutil

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QApplication, QSplitter
from PyQt6.QtGui import QIcon

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from full_form_processor import form_processor

class main(QWidget):
    def __init__(self):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.modlist_txt_path = ''
        self.plugins_txt_path = ''
        self.bsab = ''
        self.scanned = False
        self.mo2_mode = False
        self.update_header = True
        self.scan_esms = False
        self.eslify_dictionary = {}
        self.dependency_dictionary = {}
        for window in QApplication.allWidgets():
            if window.windowTitle() == 'Log Stream':
                self.log_stream = window
            if window.windowTitle() == 'ESLifier':
                self.eslifier = window
        self.create()

    def create(self):
        self.eslify = QLabel("ESLify")
        self.eslify.setToolTip("List of plugins that meet ESL conditions.")
        self.compact = QLabel("Compact + ESLify")
        self.compact.setToolTip(
            "List of plugins that can be compacted to fit ESL conditions.\n" +
            "The \'Compact/ESLify Selected\' button will also ESL the selected plugin(s).")

        self.list_eslify = list_eslable()
        self.list_compact = list_compactable()

        self.button_eslify = QPushButton("ESLify Selected")
        self.button_eslify.setToolTip(
            "This button will ESL flag all selected files. If the update plugin headers setting\n"+
            "is on then it will also update the plugin headers to 1.71.")
        self.button_eslify.clicked.connect(self.eslify_selected_clicked)

        self.button_compact = QPushButton("Compact/ESLify Selected")
        self.button_compact.setToolTip(
            "This button will first compact a selected file, patch the plugins that have it as a\n"+
            "master, then patch and rename loose files that are dependent on the compacted plugin.\n"+
            "If the update plugin headers setting is enabled then it will also update the plugin\n"+
            "headers of the compacted and dependent plugins to 1.71.")
        self.button_compact.clicked.connect(self.compact_selected_clicked)

        self.button_scan = QPushButton("Scan Mod Files")
        self.button_scan.setToolTip(
            "This will scan the entire Skyrim Special Edition folder.\n"+
            "Depending on the cell and header settings, what is displayed\n" +
            "in the below lists will change.")
        self.button_scan.clicked.connect(self.scan)
        
        self.filter_eslify = QLineEdit()
        self.filter_eslify.setPlaceholderText("Filter ")
        self.filter_eslify.setToolTip("Search Bar")
        self.filter_eslify.setMinimumWidth(50)
        self.filter_eslify.setMaximumWidth(150)
        self.filter_eslify.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_eslify.setClearButtonEnabled(True)
        self.filter_eslify.textChanged.connect(self.search_eslify)

        self.filter_compact = QLineEdit()
        self.filter_compact.setPlaceholderText("Filter ")
        self.filter_compact.setToolTip("Search Bar")
        self.filter_compact.setMinimumWidth(50)
        self.filter_compact.setMaximumWidth(150)
        self.filter_compact.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_compact.setClearButtonEnabled(True)
        self.filter_compact.textChanged.connect(self.search_compact)

        self.main_layout = QVBoxLayout()
        self.settings_layout = QVBoxLayout()

        self.v_layout1 =  QVBoxLayout()
        self.v_layout2 =  QVBoxLayout()
        
        splitter = QSplitter()
        column_widget_1 = QWidget()
        column_widget_2 = QWidget()
        column_widget_1.setLayout(self.v_layout1)
        column_widget_2.setLayout(self.v_layout2)
        splitter.addWidget(column_widget_1)
        splitter.addWidget(column_widget_2)
        splitter.setHandleWidth(26)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; border: none; }")
        splitter.setSizes([1,1])

        #Bottom of left Column
        self.h_layout3 = QHBoxLayout()
        self.h_layout3.addWidget(self.button_eslify)
        self.h_layout3.addWidget(self.filter_eslify)

        #Bottom of right Column
        self.h_layout5 = QHBoxLayout()
        self.h_layout5.addWidget(self.button_compact)
        self.h_layout5.addWidget(self.filter_compact)

        #Left Column
        self.v_layout1.addWidget(self.eslify)
        self.v_layout1.addWidget(self.list_eslify)
        self.v_layout1.addLayout(self.h_layout3)
        
        #Right Column
        self.v_layout2.addWidget(self.compact)
        self.v_layout2.addWidget(self.list_compact)
        self.v_layout2.addLayout(self.h_layout5)

        self.main_layout.addWidget(self.button_scan)
        self.main_layout.addWidget(splitter)
        
        self.v_layout1.setContentsMargins(0,11,0,11)
        self.v_layout2.setContentsMargins(0,11,0,11)

        self.main_layout.setContentsMargins(21,11,21,11)
        
        self.setLayout(self.main_layout)
        
    def search_eslify(self):
        if len(self.filter_eslify.text()) > 0:
            items = self.list_eslify.findItems(self.filter_eslify.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_eslify.rowCount()):
                    self.list_eslify.setRowHidden(i, False if (self.list_eslify.item(i,self.list_eslify.MOD_COL) in items and not self.list_eslify.item(i, self.list_eslify.HIDER_COL)) else True)
        else:
            for i in range(self.list_eslify.rowCount()):
                self.list_eslify.setRowHidden(i, True if self.list_eslify.item(i, self.list_eslify.HIDER_COL) else False)

    def search_compact(self):
        if len(self.filter_compact.text()) > 0:
            items = self.list_compact.findItems(self.filter_compact.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_compact.rowCount()):
                    self.list_compact.setRowHidden(i, False if (self.list_compact.item(i, self.list_compact.MOD_COL) in items and not self.list_compact.item(i, self.list_compact.HIDER_COL)) else True)
        else:
            for i in range(self.list_compact.rowCount()):
                self.list_compact.setRowHidden(i, True if self.list_compact.item(i, self.list_compact.HIDER_COL) else False)

    def compact_selected_clicked(self):
        self.setEnabled(False)
        checked = []
        self.list_compact.clearSelection()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row, self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked and not self.list_compact.item(row, self.list_compact.HIDER_COL):
                checked.append(self.list_compact.item(row, self.list_compact.MOD_COL).toolTip())
        if checked != []:
            file_masters = main.get_from_file('ESLifier_Data/file_masters.json')
            self.confirm = QMessageBox()
            self.confirm.setIcon(QMessageBox.Icon.Information)
            self.confirm.setWindowTitle("Getting estimated disk usage...")
            self.confirm.setText('Getting estimated disk usage...')
            self.confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.confirm.addButton(QMessageBox.StandardButton.Yes)
            self.confirm.addButton(QMessageBox.StandardButton.Cancel)
            self.confirm.setEnabled(False)
            self.confirm.show()
            size = 0
            counted = set()

            for mod in checked:
                mod_lower = mod.lower()
                if mod_lower not in counted:
                    size += os.path.getsize(mod)
                    counted.add(mod_lower)
                mod_basename = os.path.basename(mod_lower)
                if mod_basename in self.dependency_dictionary:
                    for dependent_mod in self.dependency_dictionary[mod_basename]:
                        dep_lower = dependent_mod.lower()
                        if dep_lower not in counted:
                            size += os.path.getsize(dependent_mod)
                            counted.add(dep_lower)
                if mod_basename in file_masters:
                    for file in file_masters[mod_basename]:
                        file_lower = file.lower()
                        if file_lower not in counted:
                            size += os.path.getsize(file)
                            counted.add(file_lower)
            total, used, free = shutil.disk_usage(self.output_folder_path)
            free_space = round(free / (1024**3), 3)
            if size > 1024 ** 3:
                calculated_size = round(size / (1024 ** 3), 3)
                self.confirm.setText(f"This may generate up to {calculated_size} GBs of new files\nand you have {free_space} GBs of space left.\nAre you sure you want to continue?")
            elif size > 1048576:
                calculated_size = round(size / 1048576, 2)
                self.confirm.setText(f"This may generate up to {calculated_size} MBs of new files\nand you have {free_space} GBs of space left.\nAre you sure you want to continue?")
            else:
                calculated_size = round(size / 1024, 2)
                self.confirm.setText(f"This may generate up to {calculated_size} KBs of new files\nand you have {free_space} GBs of space left.\nAre you sure you want to continue?")
            if size >= free:
                self.confirm.setText(f'Not enough space!\nNeeded space: {round(size / (1024**3),3)}\nSpace left: {free_space} GBs')
                self.confirm.removeButton(QMessageBox.StandardButton.Yes)
            self.confirm.setWindowTitle(f"Confirmation: Patching {len(checked)} Mod(s)")
            self.confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
            self.confirm.accepted.connect(lambda x = checked: self.compact_confirmed(x))
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.setEnabled(True)
        else:
            self.setEnabled(True)

    def compact_confirmed(self, checked):
            self.confirm.hide()
            self.confirm.deleteLater()
            for row in range(self.list_compact.rowCount()):
                if self.list_compact.item(row,self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked:
                    self.list_compact.item(row,self.list_compact.MOD_COL).setCheckState(Qt.CheckState.PartiallyChecked)
                    self.list_compact.item(row,self.list_compact.MOD_COL).setFlags(self.list_compact.item(row,self.list_compact.MOD_COL).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = Worker2(checked, self.dependency_dictionary, self.skyrim_folder_path, self.output_folder_path, 
                                  self.output_folder_name, self.update_header, self.mo2_mode, self.bsab)
            self.worker.moveToThread(self.thread_new)
            self.thread_new.started.connect(self.worker.run)
            self.worker.finished_signal.connect(self.thread_new.quit)
            self.worker.finished_signal.connect(self.thread_new.deleteLater)
            self.worker.finished_signal.connect(self.worker.deleteLater)
            self.worker.finished_signal.connect(lambda sender = 'compact', checked_list = checked: self.finished_button_action(sender, checked_list))
            self.thread_new.start()
        
    def eslify_selected_clicked(self):
        self.setEnabled(False)
        checked = []
        self.list_eslify.clearSelection()
        for row in range(self.list_eslify.rowCount()):
            if self.list_eslify.item(row, self.list_eslify.MOD_COL).checkState() == Qt.CheckState.Checked and not self.list_eslify.item(row, self.list_eslify.HIDER_COL):
                checked.append(self.list_eslify.item(row, self.list_eslify.MOD_COL).toolTip())
        if checked != []:
            self.confirm = QMessageBox()
            self.confirm.setIcon(QMessageBox.Icon.Information)
            size = 0
            counted = []
            for mod in checked:
                if mod not in counted:
                    size += os.path.getsize(mod)
                    counted.append(mod)
            if size > 1048576:
                calculated_size = round(size / 1048576, 2)
                self.confirm.setText(f"This may generate up to {calculated_size} MBs of new files.\nAre you sure you want to continue?")
            else:
                calculated_size = round(size / 1024,2)
                self.confirm.setText(f"This may generate up to {calculated_size} KBs of new files.\nAre you sure you want to continue?")
            self.confirm.setWindowTitle(f"Confirmation: ESL Flagging {len(checked)} Mod(s)")
            self.confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.confirm.addButton(QMessageBox.StandardButton.Yes)
            self.confirm.addButton(QMessageBox.StandardButton.Cancel)
            self.confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
            self.confirm.accepted.connect(lambda x = checked: self.eslify_confirmed(x))
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.show()
        else:
            self.setEnabled(True)

    def eslify_confirmed(self, checked):
        self.confirm.hide()
        self.confirm.deleteLater()
        for row in range(self.list_eslify.rowCount()):
            if self.list_eslify.item(row, self.list_eslify.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.list_eslify.item(row, self.list_eslify.MOD_COL).setCheckState(Qt.CheckState.PartiallyChecked)
                self.list_eslify.item(row, self.list_eslify.MOD_COL).setFlags(self.list_eslify.item(row, self.list_eslify.MOD_COL).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.log_stream.show()
        for file in checked:
            CFIDs.set_flag(file, self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.mo2_mode)
        print("Flag(s) Changed")
        print("CLEAR")
        self.finished_button_action('eslify', checked)

    def finished_button_action(self, sender, checked_list):
        message = QMessageBox()
        message.setWindowTitle("Finished")
        message.setWindowIcon(QIcon(":/images/ESLifier.png"))
        message.setText("If you're using MO2 or Vortex then make sure the ESLifier Output is installed as a mod and let it win any file conflicts. "+
                        "For MO2 users: If you generate the output folder in your mods folder for the first time, then make sure to hit "+
                        "refresh in MO2.\n"+
                        "For Vortex users: Make sure to redeploy before using this program again.")
        def shown():
            message.hide()
        message.accepted.connect(shown)
        message.show()
        if sender == 'compact':
            for mod in checked_list:
                self.list_compact.flag_dict.pop(mod)
            self.list_compact.create()
        elif sender == 'eslify':
            for mod in checked_list:
                self.list_eslify.flag_dict.pop(mod)
            self.list_eslify.create()
        self.eslifier.update_settings()
        self.setEnabled(True)
        
    def scan(self):
        self.button_scan.setEnabled(False)
        def run_scan():
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = Worker(self.skyrim_folder_path, self.update_header, self.scan_esms, self.mo2_mode,
                                  self.modlist_txt_path, self.plugins_txt_path, self.bsab)
            self.worker.moveToThread(self.thread_new)
            self.thread_new.started.connect(self.worker.scan_run)
            self.worker.finished_signal.connect(self.completed_scan)
            self.worker.finished_signal.connect(self.thread_new.quit)
            self.worker.finished_signal.connect(self.thread_new.deleteLater)
            self.thread_new.start()
        if not self.scanned:
            self.scanned = True
            run_scan()
        else:
            self.confirm = QMessageBox()
            self.confirm.setIcon(QMessageBox.Icon.Question)
            self.confirm.setWindowTitle("Confirmation")
            self.confirm.setText("You have already scanned this session.\nWould you like to scan again?")
            self.confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.confirm.addButton(QMessageBox.StandardButton.Yes)
            self.confirm.addButton(QMessageBox.StandardButton.Cancel)
            self.confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
            self.confirm.accepted.connect(run_scan)
            self.confirm.rejected.connect(lambda:self.button_scan.setEnabled(True))
            self.confirm.show()
        
    def completed_scan(self, flag_dict, dependency_dictionary):
        self.list_eslify.flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' not in f}
        self.list_compact.flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' in f}
        self.dependency_dictionary = dependency_dictionary
        print('Populating Tables')
        self.eslifier.update_settings()
        self.button_scan.setEnabled(True)
        print('Done Scanning')
        print('CLEAR')

    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data


class Worker(QObject):
    finished_signal = pyqtSignal(dict, dict)
    def __init__(self, path, update, scan_esms, mo2_mode, modlist_txt_path, plugins_txt_path, bsab):
        super().__init__()
        self.skyrim_folder_path = path
        self.update_header = update
        self.scan_esms = scan_esms
        self.mo2_mode = mo2_mode
        self.modlist_txt_path = modlist_txt_path
        self.plugins_txt_path = plugins_txt_path
        self.bsab = bsab

    def scan_run(self):
        print('Scanning All Files:')
        flag_dict, dependency_dictionary = scanner.scan(self.skyrim_folder_path, self.mo2_mode, self.modlist_txt_path, 
                                                   self.scan_esms, self.plugins_txt_path, self.bsab, self.update_header, True)
        print('Checking if New CELLs are Changed')
        plugins_with_cells = [plugin for plugin, flags in flag_dict.items() if 'new_cell' in flags]
        cell_scanner.scan(plugins_with_cells)
        self.finished_signal.emit(flag_dict, dependency_dictionary)

class Worker2(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, skyrim_folder_path, output_folder_path, output_folder_name, update_header, mo2_mode, bsab):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.output_folder_name = output_folder_name
        self.update_header = update_header
        self.mo2_mode = mo2_mode
        self.bsab = bsab
        
    def run(self):
        fp = form_processor()
        total = len(self.checked)
        count = 0
        for file in self.checked:
            count +=1
            percent = round((count/total)*100,1)
            print(f'{percent}% Patching: {count}/{total}')
            CFIDs.compact_and_patch(fp, file, self.dependency_dictionary[os.path.basename(file).lower()], self.skyrim_folder_path,
                                     self.output_folder_path, self.output_folder_name, self.update_header, self.mo2_mode, self.bsab)
        print("Compacted and Patched")
        print('CLEAR')
        self.finished_signal.emit()
