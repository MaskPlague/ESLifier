import os
import json

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QApplication
from PyQt6.QtGui import QIcon

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from plugin_qualification_checker import qualification_checker
from dependency_getter import dependecy_getter
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from full_form_processor import form_processor

class main(QWidget):
    def __init__(self):
        super().__init__()
        self.create()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.modlist_txt_path = ''
        self.scanned = False
        self.mo2_mode = False
        self.update_header = True
        self.scan_esms = False
        self.show_cells = True
        self.eslify_dictionary = {}
        self.dependency_dictionary = {}
        for window in QApplication.allWidgets():
            if window.windowTitle() == 'Log Stream':
                self.log_stream = window
            if window.windowTitle() == 'ESLifier':
                self.eslifier = window

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
        self.filter_eslify.textChanged.connect(self.searchE)

        self.filter_compact = QLineEdit()
        self.filter_compact.setPlaceholderText("Filter ")
        self.filter_compact.setToolTip("Search Bar")
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
        
        self.v_layout1.setContentsMargins(0,11,0,11)
        self.v_layout2.setContentsMargins(0,11,0,11)

        self.main_layout.setContentsMargins(21,11,21,11)

        self.setLayout(self.main_layout)
        
    def searchE(self):
        if len(self.filter_eslify.text()) > 0:
            items = self.list_eslify.findItems(self.filter_eslify.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_eslify.rowCount()):
                    self.list_eslify.setRowHidden(i, False if (self.list_eslify.item(i,0) in items and not self.list_eslify.item(i, 3)) else True)
        else:
            for i in range(self.list_eslify.rowCount()):
                self.list_eslify.setRowHidden(i, False)

    def searchC(self):
        if len(self.filter_compact.text()) > 0:
            items = self.list_compact.findItems(self.filter_compact.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_compact.rowCount()):
                    self.list_compact.setRowHidden(i, False if (self.list_compact.item(i,0) in items and not self.list_compact.item(i, 5)) else True)
        else:
            for i in range(self.list_compact.rowCount()):
                self.list_compact.setRowHidden(i, False)

    def compact_selected_clicked(self):
        self.setEnabled(False)
        checked = []
        self.list_compact.clearSelection()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row,0).checkState() == Qt.CheckState.Checked and not self.list_compact.item(row, 6):
                checked.append(self.list_compact.item(row,0).toolTip())
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
            counted = []
            for mod in checked:
                if mod not in counted:
                    size += os.path.getsize(mod)
                    counted.append(mod)
                if os.path.basename(mod.lower()) in self.dependency_dictionary.keys():
                    for dependent_mod in self.dependency_dictionary[os.path.basename(mod.lower())]:
                        if dependent_mod not in counted:
                            size += os.path.getsize(dependent_mod)
                            counted.append(dependent_mod)
                if os.path.basename(mod.lower()) in file_masters.keys():
                    for file in file_masters[os.path.basename(mod.lower())]:
                        if file not in counted:
                            size += os.path.getsize(file)
                            counted.append(file)
            if size > 1024 ** 3:
                calculated_size = round(size / (1024 ** 3),3)
                self.confirm.setText(f"This may generate up to {calculated_size} GBs of new files.\nAre you sure you want to continue?")
            elif size > 1048576:
                calculated_size = round(size / 1048576,2)
                self.confirm.setText(f"This may generate up to {calculated_size} MBs of new files.\nAre you sure you want to continue?")
            else:
                calculated_size = round(size / 1024,2)
                self.confirm.setText(f"This may generate up to {calculated_size} KBs of new files.\nAre you sure you want to continue?")
            self.confirm.setWindowTitle("Confirmation")
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
                if self.list_compact.item(row,0).checkState() == Qt.CheckState.Checked:
                    self.list_compact.item(row,0).setCheckState(Qt.CheckState.PartiallyChecked)
                    self.list_compact.item(row,0).setFlags(self.list_compact.item(row,0).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = Worker2(checked, self.dependency_dictionary, self.skyrim_folder_path, self.output_folder_path, self.update_header, self.mo2_mode)
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
            if self.list_eslify.item(row,0).checkState() == Qt.CheckState.Checked and not self.list_eslify.item(row, 3):
                checked.append(self.list_eslify.item(row,0).toolTip())
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
                calculated_size = round(size / 1048576,2)
                self.confirm.setText(f"This may generate up to {calculated_size} MiBs of new files.\nAre you sure you want to continue?")
            else:
                calculated_size = round(size / 1024,2)
                self.confirm.setText(f"This may generate up to {calculated_size} KiBs of new files.\nAre you sure you want to continue?")
            self.confirm.setWindowTitle("Confirmation")
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
            if self.list_eslify.item(row,0).checkState() == Qt.CheckState.Checked:
                self.list_eslify.item(row,0).setCheckState(Qt.CheckState.PartiallyChecked)
                self.list_eslify.item(row,0).setFlags(self.list_eslify.item(row,0).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.log_stream.show()
        for file in checked:
            CFIDs.set_flag(file, self.skyrim_folder_path, self.output_folder_path)
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
                self.list_compact.mod_list.remove(mod)
            self.list_compact.create()
        elif sender == 'eslify':
            for mod in checked_list:
                self.list_eslify.mod_list.remove(mod)
            self.list_eslify.create()
        self.eslifier.update_shown()
        self.setEnabled(True)
        
    def scan(self):
        self.button_scan.setEnabled(False)
        def run_scan():
            self.log_stream.show()
            self.thread_new = QThread()
            self.worker = Worker(self.skyrim_folder_path, self.update_header, self.scan_esms, self.show_cells, self.mo2_mode, self.modlist_txt_path)
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

        
        
    def completed_scan(self, list_eslify_mod_list, list_eslify_has_new_cells, list_compact_mod_list, list_compact_has_new_cells, dependency_dictionary):
        self.list_eslify.mod_list = list_eslify_mod_list
        self.list_eslify.has_new_cells = list_eslify_has_new_cells
        self.list_compact.mod_list = list_compact_mod_list
        self.list_compact.has_new_cells = list_compact_has_new_cells
        self.dependency_dictionary = dependency_dictionary
        print('Populating Tables')
        self.eslifier.update_shown()
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
    finished_signal = pyqtSignal(list, list , list, list, dict)
    def __init__(self, path, update, scan_esms, cell, mo2_mode, modlist_txt_path):
        super().__init__()
        self.skyrim_folder_path = path
        self.update_header = update
        self.scan_esms = scan_esms
        self.show_cells = cell
        self.mo2_mode = mo2_mode
        self.modlist_txt_path = modlist_txt_path

    def scan_run(self):
        print('Scanning All Files:')
        scanner(self.skyrim_folder_path, self.mo2_mode, self.modlist_txt_path, self.scan_esms)
        print('\nGettings Dependencies')
        dependency_dictionary = dependecy_getter.scan(self.skyrim_folder_path)
        print('\nScanning Plugins:')
        list_eslify_mod_list, list_eslify_has_new_cells, list_compact_mod_list, list_compact_has_new_cells = qualification_checker.scan(self.skyrim_folder_path, self.update_header, self.show_cells, self.scan_esms)
        print('\nChecking if New CELLs are Changed:')
        combined_list = [mod for mod in list_compact_mod_list if os.path.basename(mod) in list_compact_has_new_cells]
        combined_list.extend([mod for mod in list_eslify_mod_list if os.path.basename(mod) in list_eslify_has_new_cells])
        cell_scanner.scan(combined_list)
        self.finished_signal.emit(list_eslify_mod_list, list_eslify_has_new_cells, list_compact_mod_list, list_compact_has_new_cells, dependency_dictionary)

class Worker2(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.update_header = update_header
        self.mo2_mode = mo2_mode
        
    def run(self):
        fp = form_processor()
        total = len(self.checked)
        count = 0
        for file in self.checked:
            count +=1
            percent = round((count/total)*100,1)
            print(f'{percent}% Patching: {count}/{total}')
            CFIDs.compact_and_patch(fp, file, self.dependency_dictionary[os.path.basename(file).lower()], self.skyrim_folder_path, self.output_folder_path, self.update_header, self.mo2_mode)
        print("Compacted and Patched")
        print('CLEAR')
        self.finished_signal.emit()
