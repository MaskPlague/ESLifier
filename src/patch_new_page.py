import json
import os

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QApplication, QMessageBox)
from PyQt6.QtGui import QIcon

from scanner import scanner
from dependency_getter import dependecy_getter
from list_compacted_unpatched import list_compacted_unpatched
from list_unpatched_files import list_unpatched
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner

class patch_new(QWidget):
    def __init__(self):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.modlist_txt_path = ''
        self.plugins_txt_path = ''
        self.overwrite_path = ''
        self.mo2_mode = False
        self.update_header = True
        self.scanned = False
        self.generate_cell_master = False
        self.create()

    def create(self):
        find_button = QPushButton("Find Unpatched Files")
        find_button.clicked.connect(self.scan_and_find)
        find_button.setToolTip("Scan for new plugins and files that were not\n"+
                               "present during intial compacting and patching.\n"+
                               "This currently does not detect new facegen files present in BSA.")
        patch_button = QPushButton("Patch Selected")
        patch_button.clicked.connect(self.patch_new_plugins_and_files)
        patch_button.setToolTip("Patch the files that are dependent on the selected plugin(s).")

        eslifier_compacted_label = QLabel("ESLifier Compacted With Unpatched Files")
        unpatched_files_label = QLabel("Unpatched Files")

        self.list_compacted_unpatched = list_compacted_unpatched()
        self.list_compacted_unpatched.cell_master = self.generate_cell_master
        self.list_unpatched_files = list_unpatched()

        h_layout = QHBoxLayout()
        h_widget = QWidget()
        h_widget.setLayout(h_layout)

        v_layout_1 = QVBoxLayout()
        self.setLayout(v_layout_1)

        v_layout_1.addWidget(find_button)
        v_layout_1.addWidget(h_widget)
        v_layout_1.addWidget(patch_button)
        v_layout_1.addSpacing(22)

        v_layout_2 = QVBoxLayout()
        v_widget_2 = QWidget()
        v_widget_2.setLayout(v_layout_2)
        v_layout_2.addWidget(eslifier_compacted_label)
        v_layout_2.addWidget(self.list_compacted_unpatched)
        
        v_layout_3 = QVBoxLayout()
        v_widget_3 = QWidget()
        v_widget_3.setLayout(v_layout_3)
        v_layout_3.addWidget(unpatched_files_label)
        v_layout_3.addWidget(self.list_unpatched_files)

        h_layout.addWidget(v_widget_2)
        h_layout.addSpacing(20)
        h_layout.addWidget(v_widget_3)

        h_layout.setContentsMargins(0,0,0,0)
        v_layout_2.setContentsMargins(0,11,0,1)
        v_layout_3.setContentsMargins(0,11,0,1)

        v_layout_1.setContentsMargins(21,11,21,1)

        for window in QApplication.allWidgets():
            if window.windowTitle() == 'Log Stream':
                self.log_stream = window

    def scan_and_find(self):
        self.setEnabled(False)
        def run_scan():
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = ScannerWorker(self.skyrim_folder_path, self.mo2_mode, self.modlist_txt_path, self.plugins_txt_path, self.overwrite_path, self.update_header)
            self.worker.moveToThread(self.thread_new)
            self.thread_new.started.connect(self.worker.scan_run)
            self.worker.finished_signal.connect(self.completed_scan)
            self.worker.finished_signal.connect(self.thread_new.quit)
            self.worker.finished_signal.connect(self.thread_new.deleteLater)
            self.thread_new.start()
        if not os.path.exists('ESLifier_Data/compacted_and_patched.json'):
            self.no_data_warning = QMessageBox()
            self.no_data_warning.setIcon(QMessageBox.Icon.Information)
            self.no_data_warning.setWindowTitle("No Compacted/Patched Mods")
            self.no_data_warning.setText("There are no existing compacted/patched mods for\n"+
                                         "ESLifier to check for new files that need patching.\n"+
                                         "Compact a mod on the Main page first. This page is for\n"+
                                         "when you install a new mod and don't feel like rebuilding\n"+
                                         "the entire output.")
            self.no_data_warning.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.no_data_warning.addButton(QMessageBox.StandardButton.Ok)
            self.no_data_warning.show()
            self.setEnabled(True)
            return
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
            self.confirm.rejected.connect(lambda:self.setEnabled(False))
            self.confirm.show()
    
    def completed_scan(self):
        print('\nGetting New Dependencies and Files')
        self.find()
        if self.list_compacted_unpatched.mod_list != [] and self.list_unpatched_files.dependencies_dictionary != {}:
            print('\nChecking if New CELLs are Changed:')
            cell_scanner.scan_new_dependents(self.list_compacted_unpatched.mod_list, self.list_unpatched_files.dependencies_dictionary)
        print('CLEAR')
        self.list_unpatched_files.create()
        self.list_compacted_unpatched.create()
        if self.list_compacted_unpatched.mod_list == []:
            self.no_new_files_message = QMessageBox()
            self.no_new_files_message.setWindowTitle("No New Files Found")
            self.no_new_files_message.setIcon(QMessageBox.Icon.Information)
            self.no_new_files_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.no_new_files_message.setText('No new files that need patching have been found.')
            self.no_new_files_message.addButton(QMessageBox.StandardButton.Ok)
            self.no_new_files_message.accepted.connect(self.no_new_files_message.hide)
            self.no_new_files_message.show()
        self.setEnabled(True)

    def get_rel_path(self, file, skyrim_folder_path):
        if 'bsa_extracted' in file:
            if 'bsa_extracted_temp' in file:
                start = os.path.join(os.getcwd(), 'bsa_extracted_temp/')
            else:
                start = os.path.join(os.getcwd(), 'bsa_extracted/')
            rel_path = os.path.normpath(os.path.relpath(file, start))
        elif self.mo2_mode and file.lower().startswith(self.overwrite_path.lower()):
            rel_path = os.path.normpath(os.path.relpath(file, self.overwrite_path))
        else:
            if self.mo2_mode:
                rel_path = os.path.join(*os.path.normpath(os.path.relpath(file, skyrim_folder_path)).split(os.sep)[1:])
            else:
                rel_path = os.path.normpath(os.path.relpath(file, skyrim_folder_path))
        return rel_path
    
    def find(self):
        try:
            with open("ESLifier_Data/compacted_and_patched.json", 'r', encoding='utf-8') as f:
                compacted_and_patched = json.load(f)
            with open("ESLifier_Data/file_masters.json", 'r', encoding='utf-8') as f:
                file_masters = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json", 'r', encoding='utf-8') as f: 
                dependencies = json.load(f)
            with open("ESLifier_Data/dll_dict.json", 'r', encoding='utf-8') as f:
                dll_dict = json.load(f)
        except Exception as e:
            print(f'!Error: Failed to find a required dictionary.')
            print(e)
            return {}
        
        new_files = {}
        new_dependencies = {}

        for master, patched_files in compacted_and_patched.items():
            file_masters_list = []
            dependencies_list = []
            if master.lower() in file_masters: 
                file_masters_list = file_masters[master.lower()]
            if master.lower() in dependencies: 
                dependencies_list = dependencies[master.lower()]
            
            for file in file_masters_list:
                rel_path = self.get_rel_path(file, self.skyrim_folder_path)
                if rel_path.lower() not in patched_files: 
                    if master not in new_files:
                        new_files[master] = []
                    new_files[master].append(file)

            for file in dependencies_list:
                rel_path = self.get_rel_path(file, self.skyrim_folder_path)
                if rel_path.lower() not in patched_files: 
                    if master not in new_dependencies:
                        new_dependencies[master] = []
                    new_dependencies[master].append(file)

        mod_list = [master for master in new_dependencies]
        mod_list.extend([file for file in new_files if file not in mod_list])

        compacted_lowered = [key.lower() for key in compacted_and_patched]
        mod_list_lowered = [mod.lower() for mod in mod_list]
        for mod in dll_dict:
            if mod in compacted_lowered and mod not in mod_list_lowered:
                mod_list.append('SKSE WARN - ' + mod)

        self.list_compacted_unpatched.mod_list = mod_list
        self.list_unpatched_files.dependencies_dictionary = new_dependencies
        self.list_unpatched_files.file_dictionary = new_files

    def patch_new_plugins_and_files(self):
        checked  = []
        self.list_compacted_unpatched.clearSelection()
        for row in range(self.list_compacted_unpatched.rowCount()):
            if self.list_compacted_unpatched.item(row,0).checkState() == Qt.CheckState.Checked:
                self.list_compacted_unpatched.item(row,0).setCheckState(Qt.CheckState.Unchecked)
                self.list_compacted_unpatched.item(row,0).setFlags(self.list_compacted_unpatched.item(row,0).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                if not self.list_compacted_unpatched.item(row,0).text().startswith('SKSE WARN - '):
                    checked.append(self.list_compacted_unpatched.item(row,0).toolTip())
        if checked != []:
            self.setEnabled(False)
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = PatchNewWorker(checked, self.list_unpatched_files.dependencies_dictionary, self.list_unpatched_files.file_dictionary, self.skyrim_folder_path,
                                  self.output_folder_path, self.output_folder_name, self.overwrite_path, self.update_header, self.mo2_mode, self.generate_cell_master)
            self.worker.moveToThread(self.thread_new)
            self.thread_new.started.connect(self.worker.patch)
            self.worker.finished_signal.connect(lambda x = checked: self.finished_patching(x))
            self.worker.finished_signal.connect(self.thread_new.quit)
            self.worker.finished_signal.connect(self.thread_new.deleteLater)
            self.thread_new.start()
    
    def finished_patching(self, checked):
        print('Finished Patching New Dependencies and Files')
        mod_list = self.list_compacted_unpatched.mod_list
        for mod in checked:
            mod_list.remove(mod)
        self.list_compacted_unpatched.mod_list = mod_list
        self.list_compacted_unpatched.create()
        print('CLEAR')
        self.setEnabled(True)


class ScannerWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, path, mo2_mode, modlist_txt_path, plugins_txt_path, overwrite_path, update):
        super().__init__()
        self.skyrim_folder_path = path
        self.mo2_mode = mo2_mode
        self.modlist_txt_path = modlist_txt_path
        self.plugins_txt_path = plugins_txt_path
        self.overwrite_path = overwrite_path
        self.update_header = update

    def scan_run(self):
        print('Scanning All Files:')
        scanner.scan(self.skyrim_folder_path, self.mo2_mode, self.modlist_txt_path, self.plugins_txt_path, 
                     self.overwrite_path, self.update_header, False)
        print('Getting Dependencies')
        dependecy_getter.scan(self.skyrim_folder_path)
        self.finished_signal.emit()

class PatchNewWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, files, dependencies_dictionary, file_dictionary, skyrim_folder_path, output_folder_path, 
                 output_folder_name, overwrite_path, update_header, mo2_mode, generate_cell_master):
        super().__init__()
        self.files = files
        self.dependencies_dictionary = dependencies_dictionary
        self.file_dictionary = file_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.output_folder_name = output_folder_name
        self.overwrite_path = overwrite_path
        self.update_header = update_header
        self.mo2_mode = mo2_mode
        self.generate_cell_master = generate_cell_master

    def patch(self):
        total = len(self.files)
        count = 0
        for file in self.files:
            count +=1
            percent = round((count/total)*100,1)
            print(f'{percent}% Patching: {count}/{total}')
            dependents = []
            if file in self.dependencies_dictionary:
                dependents = self.dependencies_dictionary[file]
            CFIDs.patch_new(file, dependents, self.file_dictionary, self.skyrim_folder_path, self.output_folder_path,
                            self.output_folder_name, self.overwrite_path, self.update_header, self.mo2_mode, self.generate_cell_master)
        self.finished_signal.emit()


        

        

        