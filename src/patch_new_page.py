import json

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QApplication)

from scanner import scanner
from dependency_getter import dependecy_getter
from list_compacted_unpatched import list_compacted_unpatched
from list_unpatched_files import list_unpatched
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner

#patched dict - hold key patched name, values patched files do a scan and compare old dict to new dict
class patch_new(QWidget):
    def __init__(self):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.update_header = True
        self.create()

    def create(self):
        find_button = QPushButton("Find Unpatched Files")
        find_button.clicked.connect(self.scan_and_find)
        find_button.setToolTip("Scan for new plugins and files that were not\n"+
                               "present during intial compacting and patching.")
        patch_button = QPushButton("Patch Selected")
        patch_button.clicked.connect(self.patch_new_plugins_and_files)
        patch_button.setToolTip("Patch the files that are dependent on the selected plugin(s).")

        eslifier_compacted_label = QLabel("ESLifier Compacted With Unpatched Files")
        unpatched_files_label = QLabel("Unpatched Files")

        self.list_compacted_unpatched = list_compacted_unpatched()
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

        for window in QApplication.topLevelWidgets():
            if window.windowTitle() == 'Log Stream':
                self.log_stream = window

    def scan_and_find(self):
        self.setEnabled(False)
        self.log_stream.show()
        self.thread_new = QThread()
        self.worker = Worker(self.skyrim_folder_path)
        self.worker.moveToThread(self.thread_new)
        self.thread_new.started.connect(self.worker.scan_run)
        self.worker.finished_signal.connect(self.completed_scan)
        self.worker.finished_signal.connect(self.thread_new.quit)
        self.worker.finished_signal.connect(self.thread_new.deleteLater)
        self.thread_new.start()
    
    def completed_scan(self):
        print('Getting New Dependencies and Files')
        self.find()
        print('Checking if New Dependencies Modify Any Compacted Light Plugin\'s New CELLs')
        cell_scanner.scan_new_dependents(self.list_compacted_unpatched.mod_list, self.list_unpatched_files.dependencies_dictionary)
        print('CLEAR')
        self.list_unpatched_files.create()
        self.list_compacted_unpatched.create()
        self.setEnabled(True)

    def find(self):
        try:
            with open("ESLifier_Data/compacted_and_patched.json", 'r', encoding='utf-8') as f:
                compacted_and_patched = json.load(f)
            with open("ESLifier_Data/file_masters.json", 'r', encoding='utf-8') as f:
                file_masters = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json", 'r', encoding='utf-8') as f: 
                dependencies = json.load(f)
        except Exception as e:
            return {}
        
        new_files = {}
        new_dependencies = {}

        for key, values in compacted_and_patched.items():
            file_masters_list = []
            dependencies_list = []
            if key.lower() in file_masters.keys(): 
                file_masters_list = file_masters[key.lower()]
            if key.lower() in dependencies.keys(): 
                dependencies_list = dependencies[key.lower()]
            
            for value in file_masters_list: 
                if value not in values: 
                    if key not in new_files.keys():
                        new_files[key] = []
                    new_files[key].append(value)

            for value in dependencies_list: 
                if value not in values: 
                    if key not in new_dependencies.keys():
                        new_dependencies[key] = []
                    new_dependencies[key].append(value)

        mod_list = [key for key in new_dependencies.keys()]
        mod_list.extend([key for key in new_files.keys() if key not in mod_list])
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
                checked.append(self.list_compacted_unpatched.item(row,0).toolTip())
        if checked != []:
            self.setEnabled(False)
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = Worker2(checked, self.list_unpatched_files.dependencies_dictionary, self.list_unpatched_files.file_dictionary ,self.skyrim_folder_path, self.output_folder_path, self.update_header)
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


class Worker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, path):
        super().__init__()
        self.skyrim_folder_path = path

    def scan_run(self):
        print('Scanning All Files:')
        scanner(self.skyrim_folder_path)
        print('Getting Dependencies')
        dependecy_getter.scan(self.skyrim_folder_path)
        self.finished_signal.emit()

class Worker2(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, files, dependencies_dictionary, file_dictionary, skyrim_folder_path, output_folder_path, update_header):
        super().__init__()
        self.files = files
        self.dependencies_dictionary = dependencies_dictionary
        self.file_dictionary = file_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.update_header = update_header

    def patch(self):
        for file in self.files:
            dependents = []
            if file in self.dependencies_dictionary.keys():
                dependents = self.dependencies_dictionary[file]
            CFIDs.patch_new(file, dependents, self.file_dictionary, self.skyrim_folder_path, self.output_folder_path, self.update_header)
        self.finished_signal.emit()


        

        

        