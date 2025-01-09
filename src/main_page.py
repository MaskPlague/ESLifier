import os
import multiprocessing

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit)

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from plugin_qualification_checker import qualification_checker
from dependency_getter import dependecy_getter
from compact_form_ids import CFIDs
from output_steam import output_stream

class main(QWidget):
    def __init__(self):
        super().__init__()
        self.create()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.update_header = True
        self.show_cells = True
        self.eslify_dictionary = {}
        self.dependency_dictionary = {}
        self.output_stream = output_stream()

    def create(self):
        self.eslify = QLabel("ESLify")
        self.eslify.setToolTip("List of plugins that meet ESL conditions.")
        self.compact = QLabel("Compact + ESLify")
        self.compact.setToolTip("List of plugins that can be compacted to fit ESL conditions." +
                         "\nThe \'Compact Selected\' button will also ESL the selected plugin(s).")

        self.list_eslify = list_eslable()
        self.list_compact = list_compactable()

        self.button_eslify = QPushButton("ESLify Selected")
        self.button_eslify.clicked.connect(self.eslify_selected_clicked)

        self.button_compact = QPushButton("Compact/ESLify Selected")
        self.button_compact.clicked.connect(self.compact_selected_clicked)

        self.button_scan = QPushButton("Scan Mod Files")
        self.button_scan.setToolTip("This will scan the entire Skyrim Special Edition folder.\nThe time taken depends on how many files are present.\nScanning 800k files takes approximately a minute.")
        self.button_scan.clicked.connect(self.scan)
        
        self.filter_eslify = QLineEdit()
        self.filter_eslify.setPlaceholderText("Filter")
        self.filter_eslify.setToolTip("Search Bar")
        self.filter_eslify.setMinimumWidth(50)
        self.filter_eslify.setMaximumWidth(150)
        self.filter_eslify.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_eslify.setClearButtonEnabled(True)
        self.filter_eslify.textChanged.connect(self.searchE)

        self.filter_compact = QLineEdit()
        self.filter_compact.setPlaceholderText("Filter")
        self.filter_compact.setMinimumWidth(50)
        self.filter_compact.setMaximumWidth(150)
        self.filter_compact.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_compact.setClearButtonEnabled(True)
        self.filter_compact.textChanged.connect(self.searchC)

        self.main_layout = QVBoxLayout()
        self.settings_layout = QVBoxLayout()

        self.v_layout1 =  QVBoxLayout()
        self.v_layout2 =  QVBoxLayout()
        
        self.h_layout1 = QHBoxLayout()

        #Bottom of left Column
        self.h_layout3 = QHBoxLayout()
        self.h_layout3.addWidget(self.button_eslify)
        self.h_layout3.addWidget(self.filter_eslify)

        #Bottom of right Column
        self.h_layout5 = QHBoxLayout()
        self.h_layout5.addWidget(self.button_compact)
        self.h_layout5.addWidget(self.filter_compact)

        #Left Column
        self.h_layout1.addLayout(self.v_layout1)
        self.v_layout1.addWidget(self.eslify)
        self.v_layout1.addWidget(self.list_eslify)
        self.v_layout1.addLayout(self.h_layout3)

        self.h_layout1.addSpacing(20)

        #Right Column
        self.h_layout1.addLayout(self.v_layout2)
        self.v_layout2.addWidget(self.compact)
        self.v_layout2.addWidget(self.list_compact)
        self.v_layout2.addLayout(self.h_layout5)

        self.main_layout.addWidget(self.button_scan)
        self.main_layout.addLayout(self.h_layout1)

        self.h_layout1.setContentsMargins(0,20,0,20)
        self.v_layout1.setContentsMargins(10,0,10,0)
        self.v_layout2.setContentsMargins(10,0,10,0)

        self.setLayout(self.main_layout)

    def searchE(self):
        if len(self.filter_eslify.text()) > 0:
            items = self.list_eslify.findItems(self.filter_eslify.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_eslify.rowCount()):
                    self.list_eslify.setRowHidden(i, False if (self.list_eslify.item(i,0) in items) else True)
        else:
            for i in range(self.list_eslify.rowCount()):
                self.list_eslify.setRowHidden(i, False)

    def searchC(self):
        if len(self.filter_compact.text()) > 0:
            items = self.list_compact.findItems(self.filter_compact.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_compact.rowCount()):
                    self.list_compact.setRowHidden(i, False if (self.list_compact.item(i,0) in items) else True)
        else:
            for i in range(self.list_compact.rowCount()):
                self.list_compact.setRowHidden(i, False)

    def compact_selected_clicked(self):
        checked = []
        self.output_stream.show()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row,0).checkState() == Qt.CheckState.Checked:
                self.list_compact.hideRow(row)
                checked.append(self.list_compact.item(row,0).toolTip())
        #self.setEnabled(False)
        self.thread_new = QThread()
        self.worker = Worker2(checked, self.dependency_dictionary, self.skyrim_folder_path, self.output_folder_path, self.update_header)
        self.worker.moveToThread(self.thread_new)
        self.thread_new.started.connect(self.worker.run)
        self.worker.finished_signal.connect(self.thread_new.quit)
        self.worker.finished_signal.connect(self.thread_new.deleteLater)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker.finished_signal.connect(lambda x = True: self.setEnabled(x))
        self.thread_new.start()
        #for file in checked:
        #    CFIDs.compact_and_patch(file, self.dependency_dictionary[os.path.basename(file).lower()], self.skyrim_folder_path, self.output_folder_path, self.update_header)
        
    
    def eslify_selected_clicked(self):
        checked = []
        for row in range(self.list_eslify.rowCount()):
            if self.list_eslify.item(row,0).checkState() == Qt.CheckState.Checked:
                self.list_eslify.hideRow(row)
                checked.append(self.list_eslify.item(row,0).toolTip())
        for file in checked:
            CFIDs.set_flag(file)
        print("Flag(s) Changed")

    def scan(self):
        self.button_scan.setEnabled(False)
        self.output_stream.show()
        self.thread_new = QThread()
        self.worker = Worker(self.skyrim_folder_path, self.update_header, self.show_cells)
        self.worker.moveToThread(self.thread_new)
        self.thread_new.started.connect(self.worker.scan_run)
        self.worker.finished_signal.connect(self.completed_scan)
        self.worker.finished_signal.connect(self.thread_new.quit)
        self.worker.finished_signal.connect(self.thread_new.deleteLater)
        self.thread_new.start()
        
    def completed_scan(self, list_eslify_mod_list, list_eslify_cell_flags, list_compact_mod_list, list_compact_cell_flags, dependency_dictionary):
        self.list_eslify.mod_list = list_eslify_mod_list
        self.list_eslify.cell_flags = list_eslify_cell_flags
        self.list_compact.mod_list = list_compact_mod_list
        self.list_compact.cell_flags = list_compact_cell_flags
        self.dependency_dictionary = dependency_dictionary
        print('Populating Tables')
        self.list_eslify.create()
        self.list_compact.create()
        self.button_scan.setEnabled(True)
        print('Done Scanning')
        print('CLEAR')


class Worker(QObject):
    finished_signal = pyqtSignal(list, list , list, list, dict)
    def __init__(self, path, update, cell):
        super().__init__()
        self.skyrim_folder_path = path
        self.update_header = update
        self.show_cells = cell
        self.list_eslify_mod_list = []
        self.list_eslify_cell_flags = []
        self.list_compact_mod_list = []
        self.list_compact_cell_flags = []

    def scan_run(self):
        print('Scanning All Files:')
        scanner(self.skyrim_folder_path)
        print('\nGettings Dependencies')
        dependency_dictionary = dependecy_getter.scan(self.skyrim_folder_path)
        print('\nScanning Plugins:')
        list_eslify_mod_list, list_eslify_cell_flags, list_compact_mod_list, list_compact_cell_flags = qualification_checker.scan(self.skyrim_folder_path, self.update_header, self.show_cells)
        self.finished_signal.emit(list_eslify_mod_list, list_eslify_cell_flags, list_compact_mod_list, list_compact_cell_flags, dependency_dictionary)

class Worker2(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, skyrim_folder_path, output_folder_path, update_header):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.update_header = update_header
        
    def run(self):
        for file in self.checked:
            CFIDs.compact_and_patch(file, self.dependency_dictionary[os.path.basename(file).lower()], self.skyrim_folder_path, self.output_folder_path, self.update_header)
        print("Compacted and Patched")
        print('')
        print('CLEAR')
        self.finished_signal.emit()
