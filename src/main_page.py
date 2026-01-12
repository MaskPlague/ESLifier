import os
import json
import shutil
import threading
import timeit
import hashlib

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QRunnable, QThreadPool
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, 
                             QSplitter, QFrame, QTextEdit, QListWidget, QListWidgetItem, QDialog, QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QIcon

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from create_cell_master import create_new_cell_plugin
from patch_new import patch_new
from log_stream import log_stream as l_s
from file_defined_patcher_conditions import user_and_master_conditions_class

class main(QWidget):
    def __init__(self, log_stream, eslifier, COLOR_MODE):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.modlist_txt_path = ''
        self.plugins_txt_path = ''
        self.overwrite_path = ''
        self.scanned = False
        self.cell_master_warned = False
        self.mo2_mode = False
        self.update_header = True
        self.dependency_dictionary: dict[str, list[str]] = {}
        self.redoing_output = False
        self.patch_new_running = False
        self.patch_new_only_remove = False
        self.generate_cell_master = False
        self.hash_output = True
        self.log_stream: l_s = log_stream
        self.eslifier = eslifier
        self.COLOR_MODE = COLOR_MODE
        self.start_time = timeit.default_timer()
        self.settings = {}
        self.flag_worker = None
        self.compact_worker = None
        self.patch_and_flag_worker = None
        self.scanner_worker = None
        self.files_to_not_hash = []
        self.create()

    def create(self):
        self.eslify = QLabel("ESLify")
        self.eslify.setToolTip("List of plugins that meet ESL conditions.")
        self.compact = QLabel("Compact + ESLify")
        self.compact.setToolTip(
            "List of plugins that can be compacted to fit ESL conditions.\n" +
            "The \'Compact/ESLify Selected\' button will also ESL the selected plugin(s).")

        self.patch_new = patch_new()

        self.list_eslify = list_eslable()
        self.list_compact = list_compactable()

        self.button_eslify = QPushButton("ESLify Selected")
        self.button_eslify.setToolTip(
            "This button will ESL flag all selected files. If the update plugin headers setting\n"+
            "is on then it will also update the plugin headers to 1.71.")
        self.button_eslify.clicked.connect(self.set_false_redoing_output)
        self.button_eslify.clicked.connect(self.eslify_selected_clicked)

        self.button_compact = QPushButton("Compact/ESLify Selected")
        self.button_compact.setToolTip(
            "This button will first compact a selected file, patch the plugins that have it as a\n"+
            "master, then patch and rename loose files that are dependent on the compacted plugin.\n"+
            "If the update plugin headers setting is enabled then it will also update the plugin\n"+
            "headers of the compacted and dependent plugins to 1.71.")
        self.button_compact.clicked.connect(self.set_false_redoing_output)
        self.button_compact.clicked.connect(self.compact_selected_clicked)

        self.button_scan = self.create_button(
            " Scan Mod Files ",
            "This will scan the entire Skyrim Special Edition folder.\n"+
            "Depending on the cell and header settings, what is displayed\n" +
            "in the below lists will change.",
            self.scan
        )
        self.button_scan.clicked.connect(self.set_false_redoing_output)

        self.rebuild_output_button = self.create_button(
            " Scan and Rebuild \n ESLifier's Output ",
            "This will delete the existing output folder's contents\n"\
            "then scan and re-patch all curently ESLified mods\n"\
            "that fit the current filters in the settings.\n"\
            "It will also confirm if any files that are in the output\n"\
            "have been changed since ESLifier patched them and give\n"\
            "an option to keep or remove them.",
            self.rebuild_output
        )

        self.scan_and_patch_new_button = self.create_button(
            " Scan and Patch New \n or Changed Files ",
            "Scan for new plugins and files that were not\n"\
            "present during intial compacting and patching\n"\
            "and then patch those new plugins and files.\n"\
            "If in MO2 mode, it will also detect file\n"\
            "conflict changes but requires the output mod\n"\
            "in MO2 to match the exact same name as the\n"\
            "output folder in the settings.\n"\
            "This cannot detect changes in BSA and will NOT\n"\
            "check if the files in the output have been\n"\
            "changed since ESLifier patched them.",
            self.scan_and_patch_new
        )

        self.reset_output_button = self.create_button(
            " Reset ESLifier's Output ",
            "This will delete the existing output folder's contents and\n"\
            "the data used to patch new files.\n"\
            "It will also confirm if any files that are in the output\n"\
            "have been changed since ESLifier patched them and give\n"\
            "an option to keep or remove them.",
            self.reset_output
        )

        self.reset_bsa_button = self.create_button(
            ' Delete extracted BSA files  \n Rescan BSA on next Scan ',
            'ESLifier only extracts seq and script files from a BSA once so as not to\n'\
            'go through the tedious process of extracting the releveant files in BSAs\n'\
            'each time it scans (others are extracted during patching). Use this button\n'\
            'if a BSA has new files or you have deleted a mod that had a BSA.',
            self.reset_bsa
        )

        self.open_output_button = self.create_button(
            " Open Output",
            "Opens the Output Folder",
            self.open_output
        )

        self.open_log_button = self.create_button(
            " Open Log ",
            "Opens ESLifier.log",
            self.open_log
        )

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

        self.v_layout0 = QVBoxLayout()
        self.v_layout1 = QVBoxLayout()
        self.v_layout2 = QVBoxLayout()
        
        splitter = QSplitter()
        column_widget_0 = QWidget()
        column_widget_1 = QWidget()
        column_widget_2 = QWidget()
        column_widget_0.setLayout(self.v_layout0)
        column_widget_1.setLayout(self.v_layout1)
        column_widget_2.setLayout(self.v_layout2)
        splitter.addWidget(column_widget_0)
        splitter.addWidget(column_widget_1)
        splitter.addWidget(column_widget_2)
        splitter.setHandleWidth(26)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; border: none; }")

        #Bottom of center Column
        self.h_layout3 = QHBoxLayout()
        self.h_layout3.addWidget(self.button_eslify)
        self.h_layout3.addWidget(self.filter_eslify)

        #Bottom of right Column
        self.h_layout5 = QHBoxLayout()
        self.h_layout5.addWidget(self.button_compact)
        self.h_layout5.addWidget(self.filter_compact)

        line = QFrame()
        line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        line1 = QFrame()
        line1.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        line2 = QFrame()
        line2.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        if self.COLOR_MODE == 'Light':
            line.setStyleSheet('QFrame{background-color: lightgrey;}')
            line1.setStyleSheet('QFrame{background-color: lightgrey;}')
            line2.setStyleSheet('QFrame{background-color: lightgrey;}')
        
        self.stats = QTextEdit()
        self.stats.setReadOnly(True)
        self.stats.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.stats.setFixedHeight(200)

        #Left Column
        self.v_layout0.addSpacing(55)
        self.v_layout0.addWidget(self.button_scan)
        self.v_layout0.addWidget(line)
        self.v_layout0.addSpacing(25)
        self.v_layout0.addWidget(self.rebuild_output_button)
        #self.v_layout0.addSpacing(10)
        self.scan_and_patch_new_button_spacer = QSpacerItem(10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.v_layout0.addItem(self.scan_and_patch_new_button_spacer)
        self.v_layout0.addWidget(self.scan_and_patch_new_button)
        self.v_layout0.addWidget(line1)
        self.v_layout0.addSpacing(25)
        self.v_layout0.addWidget(self.reset_output_button)
        self.v_layout0.addSpacing(10)
        self.v_layout0.addWidget(self.reset_bsa_button)
        self.v_layout0.addWidget(line2)
        self.v_layout0.addSpacing(25)
        self.v_layout0.addWidget(self.open_output_button)
        self.v_layout0.addSpacing(10)
        self.v_layout0.addWidget(self.open_log_button)
        self.v_layout0.addStretch()
        self.v_layout0.addWidget(self.stats)
        self.v_layout0.addSpacing(29)
        self.v_layout0.setAlignment(Qt.AlignmentFlag.AlignTop)

        #Center Column
        self.v_layout1.addWidget(self.eslify)
        self.v_layout1.addWidget(self.list_eslify)
        self.v_layout1.addLayout(self.h_layout3)
        
        #Right Column
        self.v_layout2.addWidget(self.compact)
        self.v_layout2.addWidget(self.list_compact)
        self.v_layout2.addLayout(self.h_layout5)

        #self.main_layout.addWidget(self.button_scan)
        self.main_layout.addWidget(splitter)

        self.v_layout1.setContentsMargins(0,11,0,11)
        self.v_layout2.setContentsMargins(0,11,0,11)

        self.main_layout.setContentsMargins(21,11,21,11)
        
        self.setLayout(self.main_layout)
        splitter.setSizes([300,1200,1200])
    
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

    def set_false_redoing_output(self):
        self.redoing_output = False
        self.patch_new_only_remove = False
        self.patch_new_running = False

    def compact_selected_clicked(self):
        self.setEnabled(False)
        checked = []
        self.list_compact.clearSelection()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row, self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked and not self.list_compact.item(row, self.list_compact.HIDER_COL):
                checked.append(self.list_compact.item(row, self.list_compact.MOD_COL).toolTip())
        if checked != []:
            file_masters = self.get_from_file('ESLifier_Data/file_masters.json')
            self.confirm = QMessageBox()
            self.confirm.setIcon(QMessageBox.Icon.Information)
            self.confirm.setWindowTitle("Getting estimated disk usage...")
            self.confirm.setText('Getting estimated disk usage...')
            self.confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.confirm.addButton(QMessageBox.StandardButton.Yes)
            self.confirm.addButton(QMessageBox.StandardButton.Cancel)
            self.confirm.accepted.connect(lambda x = checked: self.compact_confirmed(x))
            if not self.redoing_output:
                self.confirm.show()
            else:
                self.confirm.accept()
                return
            self.confirm.setEnabled(False)
            
            size = 0
            counted = set()

            for mod in checked:
                mod_lower = mod.lower()
                if mod_lower not in counted and os.path.exists(mod):
                    size += os.path.getsize(mod)
                    counted.add(mod_lower)
                mod_basename = os.path.basename(mod_lower)
                if mod_basename in self.dependency_dictionary:
                    for dependent_mod in self.dependency_dictionary[mod_basename]:
                        dep_lower = dependent_mod.lower()
                        if dep_lower not in counted and os.path.exists(dependent_mod):
                            size += os.path.getsize(dependent_mod)
                            counted.add(dep_lower)
                if mod_basename in file_masters:
                    for file in file_masters[mod_basename]:
                        file_lower = file.lower()
                        if file_lower not in counted and os.path.exists(file):
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
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.setEnabled(True)
        elif self.patch_new_running and checked == []:
            self.finished_button_action('compact', checked)
        else:
            self.setEnabled(True)

    def compact_confirmed(self, checked):
        self.log_stream.log_file.write('Compacting Plugins\n')
        self.confirm.hide()
        self.start_time = timeit.default_timer()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row,self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.list_compact.item(row,self.list_compact.MOD_COL).setCheckState(Qt.CheckState.PartiallyChecked)
                self.list_compact.item(row,self.list_compact.MOD_COL).setFlags(self.list_compact.item(row,self.list_compact.MOD_COL).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.log_stream.show()
        self.compact_thread = QThread()
        self.compact_worker = CompactorWorker(checked, self.dependency_dictionary, self.files_to_not_hash, self.settings)
        self.compact_worker.moveToThread(self.compact_thread)
        self.compact_thread.started.connect(self.compact_worker.run)
        self.compact_worker.finished_signal.connect(
            lambda sender = 'compact', 
            checked_list = checked:
            self.finished_button_action(sender, checked_list,))
        self.compact_worker.finished_signal.connect(self.compact_thread.quit)
        self.compact_thread.start()
        
    def eslify_selected_clicked(self):
        self.setEnabled(False)
        checked: list[str] = []
        self.list_eslify.clearSelection()
        for row in range(self.list_eslify.rowCount()):
            if self.list_eslify.item(row, self.list_eslify.MOD_COL).checkState() == Qt.CheckState.Checked and not self.list_eslify.item(row, self.list_eslify.HIDER_COL):
                checked.append(self.list_eslify.item(row, self.list_eslify.MOD_COL).toolTip())
        if checked != []:
            file_masters: dict[str, list[str]] = self.get_from_file('ESLifier_Data/file_masters.json')
            self.confirm = QMessageBox()
            self.confirm.setIcon(QMessageBox.Icon.Information)
            self.confirm.setWindowTitle("Getting estimated disk usage...")
            self.confirm.setText('Getting estimated disk usage...')
            self.confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.confirm.addButton(QMessageBox.StandardButton.Yes)
            self.confirm.addButton(QMessageBox.StandardButton.Cancel)
            self.confirm.accepted.connect(lambda x = checked: self.eslify_confirmed(x))
            if not self.redoing_output:
                self.confirm.show()
            else:
                self.confirm.accept()
                return
            self.confirm.setEnabled(False)

            size = 0
            counted = set()

            for mod in checked:
                mod_lower = mod.lower()
                if mod_lower not in counted and os.path.exists(mod):
                    size += os.path.getsize(mod)
                    counted.add(mod_lower)
                if not 'new_interior_cell' in self.list_eslify.flag_dict[mod]:
                    continue
                mod_basename = os.path.basename(mod_lower)
                if mod_basename in self.dependency_dictionary:
                    for dependent_mod in self.dependency_dictionary[mod_basename]:
                        dep_lower = dependent_mod.lower()
                        if dep_lower not in counted and os.path.exists(dependent_mod):
                            size += os.path.getsize(dependent_mod)
                            counted.add(dep_lower)
                if mod_basename in file_masters:
                    for file in file_masters[mod_basename]:
                        file_lower = file.lower()
                        if file_lower not in counted and os.path.exists(file):
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
            self.confirm.setWindowTitle(f"Confirmation: ESL Flagging {len(checked)} Mod(s)")
            self.confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.setEnabled(True)
        elif self.patch_new_running and checked == []:
            self.finished_button_action('eslify', checked)
        else:
            self.setEnabled(True)

    def eslify_confirmed(self, checked):
        self.log_stream.log_file.write('ESL Flagging Plugins\n')
        self.confirm.hide()
        for row in range(self.list_eslify.rowCount()):
            if self.list_eslify.item(row, self.list_eslify.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.list_eslify.item(row, self.list_eslify.MOD_COL).setCheckState(Qt.CheckState.PartiallyChecked)
                self.list_eslify.item(row, self.list_eslify.MOD_COL).setFlags(self.list_eslify.item(row, self.list_eslify.MOD_COL).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.log_stream.show()
        if self.generate_cell_master:
            flag_only = []
            patch_and_flag = []
            for file in checked:
                if 'new_cell' in self.list_eslify.flag_dict[file] and not 'maxed_masters' in self.list_eslify.flag_dict[file]:
                    patch_and_flag.append(file)
                else:
                    flag_only.append(file) 
            self.create_flag_worker(flag_only, patch_and_flag)
        else:
            self.create_flag_worker(checked)
        try:
            with open('ESLifier_Data/esl_flagged.json', 'r', encoding='utf-8') as f:
                esl_flagged_data = json.load(f)
        except:
            esl_flagged_data = []
        for file in checked:
            basename = os.path.basename(file)
            if basename not in esl_flagged_data:
                esl_flagged_data.append(basename)
        try:
            with open('ESLifier_Data/esl_flagged.json', 'w', encoding='utf-8') as f:
                json.dump(esl_flagged_data, f, ensure_ascii=False, indent=4)
                f.close()
        except Exception as e:
            print('!Error: failed to save esl_flagged.json')
            print(e)

    def create_patch_and_flag_worker(self, files: list[str], patch_and_flag: list[str]):
        if len(patch_and_flag) > 0:
            full_list = files.copy()
            full_list.extend(patch_and_flag)
            self.flag_and_patch_thread = QThread()
            self.patch_and_flag_worker = CompactorWorker(patch_and_flag, self.dependency_dictionary, 
                                                         self.files_to_not_hash, self.settings)
            self.patch_and_flag_worker.moveToThread(self.flag_and_patch_thread)
            self.flag_and_patch_thread.started.connect(self.patch_and_flag_worker.run)
            self.patch_and_flag_worker.finished_signal.connect(self.flag_and_patch_thread.quit)
            self.patch_and_flag_worker.finished_signal.connect(
                lambda sender = 'eslify', 
                checked_list = full_list:
                self.finished_button_action(sender, checked_list,))
            self.flag_and_patch_thread.start()
        else:
            self.finished_button_action('eslify', files,)
            print("File(s) ESL Flagged")
            if self.redoing_output:
                print("CLEAR ALT")
            else:
                print("CLEAR")

    def create_flag_worker(self, files, patch_and_flag = []):
        self.flag_thread = QThread()
        self.flag_worker = FlagWorker(files, self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.overwrite_path, self.mo2_mode)
        self.flag_worker.moveToThread(self.flag_thread)
        self.flag_thread.started.connect(self.flag_worker.flag_files)
        self.flag_worker.finished_signal.connect(self.flag_thread.quit)
        self.flag_worker.finished_signal.connect(
            lambda files_copy = files,
            patch_and_flag_copy = patch_and_flag:
            self.create_patch_and_flag_worker(files_copy, patch_and_flag_copy)
        )
        self.flag_thread.start()

    def finished_button_action(self, sender, checked_list):
        if not self.redoing_output:
            message = QMessageBox()
            message.setWindowTitle("Finished")
            message.setWindowIcon(QIcon(":/images/ESLifier.png"))
            message.setText("If you're using MO2 or Vortex then make sure the ESLifier Output is installed as a mod and let it win any file conflicts. "+
                            "For MO2 users: If you generate the output folder in your mods folder for the first time, then make sure to hit "+
                            "refresh in MO2.\n"+
                            "For Vortex users: Make sure to redeploy before using this program again.")
            def shown():
                message.hide()
                if self.generate_cell_master and not self.cell_master_warned:
                    cell_master_message = QMessageBox()
                    cell_master_message.setWindowTitle("Activate ESLifier_Cell_Master.esm and Sort Your Plugins")
                    cell_master_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
                    cell_master_message.setText("Do not forget to activate ESLifier_Cell_Master.esm and re-sort\n"+
                                                "your plugins to put the ESM above all of it's dependents. You\n"+
                                                "likely can put it at the top of your plugins list.")
                    def hide_message():
                        cell_master_message.hide()
                    cell_master_message.accepted.connect(hide_message)
                    cell_master_message.show()
                    self.cell_master_warned = True
            message.accepted.connect(shown)
            message.show()
        if sender == 'compact':
            if len(checked_list) > 0:
                for mod in checked_list:
                    self.list_compact.flag_dict.pop(mod)
                self.list_compact.create()
            if not self.patch_new_running:
                print(f"Total Elapsed Time: {timeit.default_timer() - self.start_time:.2f} Seconds")
                print("CLEAR")
                self.setEnabled(True)
                self.calculate_stats()
            else:
                self.patch_new_running = False
                self.patch_new_only_remove = False
                self.redoing_output = False
                self.patch_new.finished_rebuilding()
        elif sender == 'eslify':
            if len(checked_list) > 0:
                for mod in checked_list:
                    self.list_eslify.flag_dict.pop(mod)
                self.list_eslify.create()
            if not self.redoing_output:
                print("CLEAR")
            elif self.redoing_output and os.path.exists('ESLifier_Data/previously_compacted.json'):
                print("CLEAR ALT")
                self.list_compact.check_previously_compacted()
                checked = 0
                for i in range(self.list_compact.rowCount()):
                    if self.list_compact.item(i, self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked:
                        checked += 1
                if checked > 0:
                    self.compact_selected_clicked()
                elif checked == 0 and self.patch_new_running:
                    self.patch_new_running = False
                    self.patch_new_only_remove = False
                    self.redoing_output = False
                    self.patch_new.finished_rebuilding()
                else:
                    print("CLEAR")
                    self.setEnabled(True)
            else:
                print("CLEAR")
                self.setEnabled(True)
        
        if not self.redoing_output:
            self.setEnabled(True)
            self.calculate_stats()
        
    def scan(self):
        self.setEnabled(False)
        self.scan_thread = QThread()
        def run_scan():
            self.log_stream.log_file.write('Running Scan\n')
            self.log_stream.show()
            self.scanner_worker = ScannerWorker()
            self.scanner_worker.moveToThread(self.scan_thread)
            self.scan_thread.started.connect(self.scanner_worker.scan_run)
            self.scanner_worker.finished_signal.connect(self.completed_scan)
            self.scanner_worker.finished_signal.connect(self.scan_thread.quit)
            self.scan_thread.start()
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
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            if self.redoing_output:
                self.confirm.accept()
            else:
                self.confirm.show()
    
    def completed_scan(self, eslifiy_flag_dict, compact_flag_dict, dependency_dictionary):
        self.list_eslify.flag_dict = eslifiy_flag_dict
        self.list_compact.flag_dict = compact_flag_dict
        self.dependency_dictionary = dependency_dictionary
        print('Populating Tables')
        try:
            self.list_eslify.create()
        except Exception as e:
            print('!Error: Failed to create "ESLify" list')
            print(e)
        try:
            self.list_compact.create()
        except Exception as e:
            print('!Error: Failed to create "Compact + ESLify" list')
            print(e)
        print('Done Scanning')
        if self.redoing_output and not self.patch_new_only_remove:
            if os.path.exists('ESLifier_Data/esl_flagged.json'):
                print('CLEAR ALT')
                self.list_eslify.check_previously_esl_flagged()
                if not self.patch_new_running:
                    os.remove('ESLifier_Data/esl_flagged.json')
                self.eslify_selected_clicked()
            elif os.path.exists('ESLifier_Data/previously_compacted.json'):
                self.list_compact.check_previously_compacted()
                self.compact_selected_clicked()
        elif self.redoing_output and self.patch_new_only_remove:
            self.redoing_output = False
            self.patch_new_running = False
            self.patch_new_only_remove = False
            self.patch_new.finished_rebuilding()
        else:
            print('CLEAR')
            self.calculate_stats()
            self.setEnabled(True)

    def get_from_file(self, file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    
    def update_changed_rel_paths_in_new_files_hashes(self, changed_rel_paths_to_switch):
        try:
            with open('ESLifier_Data/new_file_hashes.json', 'r+', encoding='utf-8') as f:
                try:
                    new_file_hashes:dict = json.load(f)
                except:
                    new_file_hashes = {}
                for rel_path in changed_rel_paths_to_switch:
                    tup = new_file_hashes.get(rel_path, (None, False))
                    if tup[0] != None:
                        new_file_hashes[rel_path] = (tup[0], False)
                f.seek(0)
                f.truncate(0)
                json.dump(new_file_hashes, f, ensure_ascii=False, indent=4)
                f.close()
        except Exception as e:
            print("!Error: Failed to open new_file_hashes.json")
            print(e)
    
    def reset_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.skyrim_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            print('!Error: Issue occured getting the output folder during output reset.')
            return

        if self.hash_output:
            self.calculate_existing_output_threaded('reset_output')
        else:
            files_to_remove, size, file_count = self.calculate_existing_output()
            self.reset_output_next(files_to_remove, size, file_count, [])
    
    def reset_output_next(self, files_to_remove, size, file_count, changed_rel_paths_to_switch):
        confirm = self.create_confirmation('lightcoral')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            f"Are you sure you want to delete the output folder {self.output_folder_name}'s contents and all data used to patch new files?\n" \
            f"This action will delete {file_count} files and {calculated_size} MBs of data from the output."
            )
        def accepted():
            self.log_stream.log_file.write('Resetting Output\n')
            confirm.hide()
            if os.path.exists('ESLifier_Data/compacted_and_patched.json'):
                try:
                    compacted_and_patched_dict = {}
                    with open('ESLifier_Data/compacted_and_patched.json', 'r', encoding='utf-8') as fcp:
                        compacted_and_patched_dict = json.load(fcp)
                        with open('ESLifier_Data/previously_compacted.json', 'w', encoding='utf-8') as fpc:
                            previously_compacted = [key for key in compacted_and_patched_dict.keys()]
                            json.dump(previously_compacted, fpc, ensure_ascii=False, indent=4)
                            fpc.close()
                        fcp.close()
                    os.remove('ESLifier_Data/compacted_and_patched.json')
                except Exception as e:
                    print("!Error: Failed in Compacted and Patched deletion process.")
                    print(e)
            if os.path.exists('ESLifier_Data/esl_flagged.json'):
                os.remove('ESLifier_Data/esl_flagged.json')
            if os.path.exists('ESLifier_Data/original_files.json'):
                os.remove('ESLifier_Data/original_files.json')
            if os.path.exists('ESLifier_Data/master_byte_data.json'):
                os.remove('ESLifier_Data/master_byte_data.json')
            self.delete_output(self.output_folder_full, files_to_remove)
            self.list_compact.flag_dict = {}
            self.list_eslify.flag_dict = {}
            self.list_compact.create()
            self.list_eslify.create()
            if os.path.exists('ESLifier_Data/new_file_hashes.json') and self.hash_output:
                self.update_changed_rel_paths_in_new_files_hashes(changed_rel_paths_to_switch)
                def accepted2():
                    if os.path.exists('ESLifier_Data/new_file_hashes.json'):
                        os.remove('ESLifier_Data/new_file_hashes.json')
                    confirm2.hide()
                confirm2 = self.create_confirmation('tomato')
                confirm2.setText("Would you like to remove the ESLifier Output hash info?\n"\
                                "This is how ESLifier can tell if a file in the output\n"\
                                "has been changed after ESLifier patched it.\n"\
                                "This is NOT recommended, especially if you kept any\n"\
                                "changed files.")
                yes_button = QPushButton("3 Yes")
                confirm2.addButton(yes_button, QMessageBox.ButtonRole.YesRole)
                confirm2.setStandardButtons(QMessageBox.StandardButton.No)
                confirm2.setDefaultButton(QMessageBox.StandardButton.No)
                yes_button.setEnabled(False)
                confirm2.accepted.connect(accepted2)
                QTimer.singleShot(1000, lambda: yes_button.setText("2 Yes"))
                QTimer.singleShot(2000, lambda: yes_button.setText("1 Yes"))
                def enable_and_set_text():
                    yes_button.setEnabled(True)
                    yes_button.setText("Yes")
                QTimer.singleShot(3000, enable_and_set_text)
                confirm2.show()
            self.calculate_stats()

        confirm.accepted.connect(accepted)
        confirm.show()

    def rebuild_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.skyrim_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            print('!Error: Issue occured getting the output folder during output rebuild.')
            return
        if self.hash_output:
            self.calculate_existing_output_threaded('rebuild_output')
        else:
            files_to_remove, size, file_count = self.calculate_existing_output()
            self.rebuild_output_next(files_to_remove, size, file_count, [])
        
    def rebuild_output_next(self, files_to_remove, size, file_count, changed_rel_paths_to_switch):

        confirm = self.create_confirmation('skyblue')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            f"Are you sure you want to recreate the output folder {self.output_folder_name}?\n" \
            f"This action will delete {file_count} files and {calculated_size} MBs of data from the output and\n" \
            "re-scan, flag, compact, and patch all previously output files that fit the current filters."
            )
        def accepted():
            self.log_stream.log_file.write('Starting Output Rebuild\n')
            confirm.hide()
            previously_compacted = []
            previously_esl_flagged = []
            if os.path.exists('ESLifier_Data/new_file_hashes.json'):
                self.update_changed_rel_paths_in_new_files_hashes(changed_rel_paths_to_switch)
            if os.path.exists('ESLifier_Data/compacted_and_patched.json'):
                with open('ESLifier_Data/compacted_and_patched.json', 'r', encoding='utf-8') as fcp:
                    compacted_and_patched_dict = json.load(fcp)
                    with open('ESLifier_Data/previously_compacted.json', 'w', encoding='utf-8') as fpc:
                        previously_compacted = [key for key in compacted_and_patched_dict.keys()]
                        json.dump(previously_compacted, fpc, ensure_ascii=False, indent=4)
                        fpc.close()
                    fcp.close()
                os.remove('ESLifier_Data/compacted_and_patched.json')
            if os.path.exists('ESLifier_Data/esl_flagged.json'):
                with open('ESLifier_Data/esl_flagged.json', 'r', encoding='utf-8') as fef:
                    previously_esl_flagged = json.load(fef)
                    fef.close()
            if os.path.exists('ESLifier_Data/original_files.json'):
                os.remove('ESLifier_Data/original_files.json')
            if os.path.exists("ESLifier_Data/winning_file_history_dict.json"):
                os.remove("ESLifier_Data/winning_file_history_dict.json")
            if os.path.exists("ESLifier_Data/winning_files_dict.json"):
                os.remove("ESLifier_Data/winning_files_dict.json")
            if os.path.exists('ESLifier_Data/master_byte_data.json'):
                os.remove('ESLifier_Data/master_byte_data.json')
            if len(previously_compacted) == 0 and len(previously_esl_flagged) == 0:
                QMessageBox.warning(None, "No Existing Output Data", f"There is no existing output data for ESLifier to use.")
                return
            self.delete_output(self.output_folder_full, files_to_remove, remove_maps=False)
            self.calculate_stats()
            self.redoing_output = True
            self.scan()

        confirm.accepted.connect(accepted)
        confirm.show()

    def reset_bsa(self):
        confirm = self.create_confirmation('lightcoral')
        confirm.setText(
            "Are you sure you want to reset the Extracted BSA List?\n" +
            "This will cause the next scan to take significantly longer as the BSA files will\n"+ 
            "need to be extracted again and irrelevant script files will need to be filtered.\n\n"+
            "This can take a short bit and will freeze the UI\n"+
            "or you can manually delete the \"bsa_extracted/\" folder\n"+
            "and then click this button.")
        def accepted():
            self.log_stream.log_file.write('Resetting BSA\n')
            confirm.hide()
            if os.path.exists('ESLifier_Data/extracted_bsa.json'):
                os.remove('ESLifier_Data/extracted_bsa.json')
            if os.path.exists('bsa_extracted/'):
                def delete_directory(dir_path):
                    try:
                        shutil.rmtree(dir_path)
                    except Exception as e:
                        pass

                def delete_subdirectories_threaded(parent_dir):
                    threads = []
                    for item in os.listdir(parent_dir):
                        item_path = os.path.join(parent_dir, item)
                        if os.path.isdir(item_path):
                            thread = threading.Thread(target=delete_directory, args=(item_path,))
                            threads.append(thread)
                            thread.start()

                    for thread in threads:
                        thread.join()
                delete_subdirectories_threaded('bsa_extracted/')
            self.list_compact.flag_dict = {}
            self.list_eslify.flag_dict = {}
            self.list_compact.create()
            self.list_eslify.create()
        confirm.accepted.connect(accepted)
        confirm.show()

    def open_output(self):
        output_folder = os.path.join(self.output_folder_path, self.output_folder_name)
        if os.path.exists(output_folder):
            try:
                if os.name == 'nt':
                    os.startfile(output_folder)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', os.path.dirname(output_folder)])
                else:
                    subprocess.Popen(['open', os.path.dirname(output_folder)])
            except Exception as e:
                print(f"Error opening folder: {e}")

    def open_log(self):
        log_file = os.path.join(os.getcwd(), "ESLifier_Data/ESLifier.log")
        if os.path.exists(log_file):
            try:
                if os.name == 'nt':
                    os.startfile(log_file)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', os.path.dirname(log_file)])
                else:
                    subprocess.Popen(['open', os.path.dirname(log_file)])
            except Exception as e:
                print(f"Error opening file: {e}")

    def create_button(self, button_text, tooltip, click_function):
        button = QPushButton(button_text)
        button.clicked.connect(click_function)
        button.setToolTip(tooltip)
        return button
    
    def create_confirmation(self, color: str = ''):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        if color != '':
            confirm.setStyleSheet("""
                QMessageBox {
                    background-color: """+color+""";
                }""")
        confirm.setWindowTitle("Confirmation")
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        return confirm
    
    def get_rel_path(self, file: str) -> str:
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
                parts = os.path.normpath(os.path.relpath(file, self.skyrim_folder_path)).split(os.sep)
                if len(parts) != 1:
                    parts = parts[1:]
                rel_path = os.path.join(*parts)
            else:
                rel_path = os.path.normpath(os.path.relpath(file, self.skyrim_folder_path))
        return rel_path
    
    def calculate_existing_output(self):
        size = 0
        file_count = 0
        files_to_remove = []
        for root, _, files in os.walk(self.output_folder_full):
            file_count += len(files)
            for file in files:
                full_path = os.path.join(root, file)
                files_to_remove.append(full_path)
                size += os.path.getsize(full_path)
        return files_to_remove, size, file_count
    
    def calculate_existing_output_threaded(self, requester):
        self.setEnabled(False)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(os.cpu_count())
        self.calculate_requester = requester
        self.total_size = 0
        self.total_file_count = 0
        self.total_progress = 0
        self.files_to_remove = []
        self.changed_hashes = []
        self.new_file_hashes = self.get_from_file('ESLifier_Data/new_file_hashes.json')

        files_to_hash = []
        for root, _, files in os.walk(self.output_folder_full):
            for f in files:
                files_to_hash.append(os.path.join(root, f))
        print("CLEAR ALT")
        self.log_stream.show()
        print("Hashing output for changes...\n\n")
        self.hasher_thread = QThread()
        self.hasher_worker = HashWorker(files_to_hash, self.new_file_hashes, self.get_rel_path)
        self.hasher_worker.moveToThread(self.hasher_thread)
        self.hasher_thread.started.connect(self.hasher_worker.run)
        self.hasher_worker.finished.connect(self.on_hashing_finished)
        self.hasher_worker.finished.connect(self.hasher_thread.quit)
        self.hasher_thread.start()

    def on_hashing_finished(self, result):
        total_size: int = result["size"]
        total_file_count: int = result["file_count"]
        files_to_remove:list[str] = result["files_to_remove"]
        changed_hashes:list = result["changed_hashes"]
        self.setEnabled(True)

        print("Hashing for changes complete.")
        print(f"Found {len(changed_hashes)} changed files.")
        print("CLEAR")
        changed_rel_paths_to_switch = []

        if changed_hashes:
            with open('ESLifier_Data/new_file_hashes.json', 'w', encoding='utf-8') as f:
                json.dump(self.new_file_hashes, f, ensure_ascii=False, indent=4)
                f.close()
            dialog = QDialog()
            dialog.setWindowIcon(QIcon(":/images/ESLifier.png"))
            dialog.setWindowTitle("Select files to remove.")
            dialog.setStyleSheet("QDialog {background-color: tomato;}")
            dialog.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
            listWidget = QListWidget()
            listWidget.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
            listWidget.setAutoScroll(False)
            layout = QVBoxLayout()
            buttons_widget = QWidget()
            buttons_layout = QHBoxLayout()
            buttons_widget.setLayout(buttons_layout)
            
            self.hash_changed_option = 'keep_all'
            def delete_selected():
                self.hash_changed_option = 'delete_selected'
                dialog.close()
            delete_selected_button = self.create_button("3 Delete Selected", "Deletes only the selected files.", delete_selected)
            delete_selected_button.setStyleSheet("QPushButton {background-color: red;}")
            delete_selected_button.setEnabled(False)
            
            def delete_all():
                self.hash_changed_option = 'delete_all'
                dialog.close()
            delete_all_button = self.create_button("3 Delete All", "Deletes all files regardless of selection.", delete_all)
            delete_all_button.setStyleSheet("QPushButton {background-color: red;}")
            delete_all_button.setEnabled(False)

            def keep_all():
                self.hash_changed_option = 'keep_all'
                dialog.close()
            keep_all_button = self.create_button("Keep All", "Keeps all files regardless of selection.", keep_all)
            keep_all_button.setStyleSheet("QPushButton {background-color: lime;}")

            buttons_layout.addWidget(delete_all_button)
            buttons_layout.addWidget(delete_selected_button)
            buttons_layout.addWidget(keep_all_button)
            dialog.setLayout(layout)
            label = QLabel("The following files have had their hashes change since they were patched by ESLifier.\n"\
                            "These files could be config or data storage files that you may want to keep.\n"\
                            "Select the files you would like to remove and select \"Delete Selected\",\n"\
                            "select \"Delete All\" to delete all files regardless of selection,\n"\
                            "or select \"Keep All\" to not delete any files.")
            layout.addWidget(label)
            layout.addWidget(listWidget)
            layout.addWidget(buttons_widget)
            
            for file, rel_path in changed_hashes:
                item = QListWidgetItem(rel_path)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(os.path.normpath(file))
                item.setData(0, rel_path)
                listWidget.addItem(item)
            
            def rename_2():
                delete_selected_button.setText("2 Delete Selected")
                delete_all_button.setText("2 Delete All")

            def rename_1():
                delete_selected_button.setText("1 Delete Selected")
                delete_all_button.setText("1 Delete All")
            
            def rename_and_enable():
                delete_selected_button.setText("Delete Selected")
                delete_selected_button.setEnabled(True)
                delete_all_button.setText("Delete All")
                delete_all_button.setEnabled(True)

            QTimer.singleShot(1000, rename_2)
            QTimer.singleShot(2000, rename_1)
            QTimer.singleShot(3000, rename_and_enable)
            keep_all_button.setFocus()
            dialog.exec()
            self.files_to_not_hash.clear()

            if self.hash_changed_option == 'delete_all':
                for file, rel_path in changed_hashes:
                    files_to_remove.append(file)
                    changed_rel_paths_to_switch.append(rel_path)
                    total_size += os.path.getsize(file)
                    total_file_count += 1
            elif self.hash_changed_option == 'delete_selected':
                for index in range(0, listWidget.count()):
                    item = listWidget.item(index)
                    if item.checkState() == Qt.CheckState.Checked:
                        files_to_remove.append(item.toolTip())
                        changed_rel_paths_to_switch.append(item.data(0))
                        total_size += os.path.getsize(item.toolTip())
                        total_file_count += 1
                    else:
                        self.files_to_not_hash.append(item.toolTip().lower())
            elif self.hash_changed_option == 'keep_all':
                for file, rel_path in self.changed_hashes:
                    self.files_to_not_hash.append(os.path.normpath(file).lower())
        if self.calculate_requester == 'reset_output':
            self.reset_output_next(files_to_remove, total_size, total_file_count, changed_rel_paths_to_switch)
        elif self.calculate_requester == 'rebuild_output':
            self.rebuild_output_next(files_to_remove, total_size, total_file_count, changed_rel_paths_to_switch)
    
    def prune_empty_dirs_recursive(self, path, output_folder):
        if not os.path.isdir(path):
            return

        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                self.prune_empty_dirs_recursive(full_path, output_folder)

        if not os.listdir(path) and path != output_folder:
            try:
                os.rmdir(path)
            except OSError as e:
                print(f"~Warn: Could not remove {path}: {e}")
        
    def delete_output(self, output_folder: str, files_to_remove: list[str], remove_maps=True):
        if remove_maps and os.path.exists('ESLifier_Data/Form_ID_Maps'):
            shutil.rmtree('ESLifier_Data/Form_ID_Maps')
        if os.path.exists('ESLifier_Data/EDIDs'):
            shutil.rmtree('ESLifier_Data/EDIDs')
        if os.path.exists('ESLifier_Data/Cell_IDs'):
            shutil.rmtree('ESLifier_Data/Cell_IDs')
        if os.path.exists('ESLifier_Data/cell_master_info.json'):
            os.remove('ESLifier_Data/cell_master_info.json')
        if os.path.exists("ESLifier_Data/winning_file_history_dict.json"):
            os.remove("ESLifier_Data/winning_file_history_dict.json")
        if os.path.exists("ESLifier_Data/winning_files_dict.json"):
            os.remove("ESLifier_Data/winning_files_dict.json")
        if os.path.exists(output_folder) and 'eslifier' in output_folder.lower():
            for file in files_to_remove:
                if os.path.exists(file):
                    os.remove(file)
            self.prune_empty_dirs_recursive(output_folder, output_folder)

    def calculate_stats(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        _1, size, file_count =  self.calculate_existing_output()
        if size > 1024 ** 3:
            calculated_size = str(round(size / (1024 ** 3), 3)) + ' GBs'
        elif size > 1048576:
            calculated_size = str(round(size / 1048576, 2)) + ' MBs'
        else:
            calculated_size = str(round(size / 1024, 2)) + ' KBs'
        flaggable_count = 0
        row_count = self.list_eslify.rowCount()
        for row in range(0, row_count):
            if not self.list_eslify.isRowHidden(row):
                flaggable_count += 1
        compactible_count = 0
        row_count = self.list_compact.rowCount()
        for row in range(0, row_count):
            if not self.list_compact.isRowHidden(row):
                compactible_count += 1

        stats_text = "Output Stats:\n"\
                    "  Size:\n"\
                    f"    > {calculated_size}\n"\
                    "  File Count:\n"\
                    f"    > {file_count}"
        if self.scanned:
            stats_text += "\n\n"\
                    "Scanned Stats:\n"\
                    "  Flaggable:\n"\
                    f"    > {flaggable_count}\n"\
                    "  Compactible:\n"\
                    f"    > {compactible_count}"
        self.stats.setText(stats_text)

    def scan_and_patch_new(self):
        self.setEnabled(False)
        confirm = self.create_confirmation()
        confirm.setText("Are you sure you want to scan and patch new/changed files?")
        def accepted():
            self.log_stream.log_file.write('Starting Patch New Process\n')
            confirm.hide()
            self.log_stream.show()
            self.patch_new.scan_and_find(self.settings.copy(), self)
        confirm.accepted.connect(accepted)
        confirm.rejected.connect(lambda: self.setEnabled(True))
        confirm.show()

class ScannerWorker(QObject):
    finished_signal = pyqtSignal(dict, dict, dict)
    def __init__(self):
        super().__init__()

    def scan_run(self):
        print('Scanning All Files:')
        flag_dict, dependency_dictionary = scanner.scan(True)
        print('Checking if New CELLs are Changed')
        plugins_with_cells = [plugin for plugin, flags in flag_dict.items() if 'new_cell' in flags]
        cell_scanner.scan(plugins_with_cells)
        eslify_flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' not in f}
        compact_flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' in f}
        self.finished_signal.emit(eslify_flag_dict, compact_flag_dict, dependency_dictionary)
        return

class CompactorWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, files_to_not_hash, settings: dict):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.skyrim_folder_path: str = settings.get('skyrim_folder_path', '')
        self.output_folder_path = settings.get('output_folder_path', '')
        self.output_folder_name = settings.get('output_folder_name', 'ESLifier Compactor Output')
        self.overwrite_path: str = os.path.normpath(settings.get('overwrite_path', ''))
        self.mo2_mode: bool = settings.get('mo2_mode', False)
        self.update_header: bool = settings.get('update_header', False)
        self.create_new_cell_plugin = create_new_cell_plugin()
        self.generate_cell_master = settings.get('generate_cell_master', True)
        self.persistent_ids = settings.get('persistent_ids', True)
        self.free_non_existent = settings.get('free_non_existent', False)
        self.files_to_not_hash = files_to_not_hash
        self.hash_output = settings.get('hash_output', True)
        
    def run(self):
        total = len(self.checked)
        count = 0
        if self.update_header:
            try:
                with open("ESLifier_Data/missing_skyrim_as_master.json", 'r', encoding='utf-8') as f:
                    missing_skyrim_esm = json.load(f)
            except:
                missing_skyrim_esm = {}
        with open("ESLifier_Data/flag_dictionary.json", 'r', encoding='utf-8') as f:
            flag_dict = json.load(f)
        if self.generate_cell_master:
            self.create_new_cell_plugin.generate(os.path.join(self.output_folder_path, self.output_folder_name))
        finalize = False
        original_files: dict = self.get_from_file('ESLifier_Data/original_files.json')
        winning_files_dict: dict = self.get_from_file('ESLifier_Data/winning_files_dict.json')
        master_byte_data: dict = self.get_from_file('ESLifier_Data/master_byte_data.json')
        files_to_patch: dict = self.get_from_file('ESLifier_Data/file_masters.json')
        bsa_dict: dict = self.get_from_file('ESLifier_Data/bsa_dict.json')
        bsa_masters = []
        for value in bsa_dict.values():
            bsa_masters.extend(value)

        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.overwrite_path, self.update_header, self.mo2_mode,
                      self.create_new_cell_plugin, original_files, winning_files_dict, {}, {}, master_byte_data, bsa_masters, bsa_dict,
                      self.persistent_ids, self.free_non_existent, additional_file_patcher_conditions)
        if self.hash_output:
            print("Hashing any existing files for changes...")
            cfids.hash_output_files([], True)
        print("CLEAR ALT")
        for file in self.checked:
            count +=1
            percent = round((count/total)*100,1)
            print(f'{percent}% Patching: {count}/{total}')
            dependents = self.dependency_dictionary[os.path.basename(file).lower()]
            all_dependents_have_skyrim_esm_as_master = True
            if self.update_header:
                for plugin_without_skyrim_as_master, master_0 in missing_skyrim_esm.items():
                    if plugin_without_skyrim_as_master in dependents and os.path.basename(file) == master_0:
                        all_dependents_have_skyrim_esm_as_master = False
                        break
            else:
                all_dependents_have_skyrim_esm_as_master = True
            if self.generate_cell_master:
                flags = flag_dict[file]
                generate_cell_master = False
                if 'new_cell' in flags and not 'maxed_masters' in flags:
                    generate_cell_master = True
                    finalize = True
            else:
                generate_cell_master = False
            cfids.compact_and_patch(
                            file, dependents, all_dependents_have_skyrim_esm_as_master, 
                            generate_cell_master, files_to_patch)

        if finalize:
            print('Creating/Updating ESLifier_Cell_Master.esm...')
            self.create_new_cell_plugin.finalize_plugin()
        print('Saving Data...')
        cfids.save_data()
        if self.hash_output:
            print('Hashing output files for checking later changes...')
            cfids.hash_output_files(self.files_to_not_hash)
        print("Patching Complete")
        self.finished_signal.emit()
        return
    
    def get_from_file(self, file: str) -> dict:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    
class FlagWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, files, skyrim_folder_path, output_folder_path, output_folder_name, overwrite_path, mo2_mode):
        self.files = files
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.output_folder_name = output_folder_name
        self.overwrite_path = overwrite_path
        self.mo2_mode = mo2_mode
        super().__init__()
    
    def flag_files(self):
        original_files = self.get_from_file('ESLifier_Data/original_files.json')
        winning_files_dict = self.get_from_file('ESLifier_Data/winning_files_dict.json')
        winning_file_history_dict = {}
        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.overwrite_path, True, self.mo2_mode, 
                      None, original_files, winning_files_dict, winning_file_history_dict, None, None, None, None, None, None, additional_file_patcher_conditions)
        for file in self.files:
            original_files, winning_file_history_dict = cfids.set_flag(file)
        self.dump_dictionary('ESLifier_Data/original_files.json', original_files)
        self.dump_dictionary('ESLifier_Data/winning_file_history_dict.json', winning_file_history_dict)
        self.finished_signal.emit()

    def dump_dictionary(self, file, dictionary: dict):
        data = self.get_from_file(file)
        for key, values in dictionary.items():
            data[key] = values
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to {file}')
            print(e)
    
    def get_from_file(self, file: str) -> dict:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    

class HashWorker(QObject):
    finished = pyqtSignal(dict)
    def __init__(self, files, new_file_hashes, get_rel_path):
        super().__init__()
        self.files = files
        self.new_file_hashes:dict = new_file_hashes
        self.get_rel_path = get_rel_path

    def run(self):
        size = 0
        file_count = 0
        files_to_remove = []
        changed_hashes = []
        to_hash_len = len(self.files)

        progress = 1
        for file in self.files:
            progress += 1
            percentage = (progress / to_hash_len) * 100
            factor = round(to_hash_len * 0.01)
            if factor == 0:
                factor = 1
            if (progress % factor) >= (factor-1):
                print('\033[F\033[K-    Processed: ' + str(round(percentage, 1)) + '%' + 
                    '\n-    Files: ' + str(progress) + '/' + str(to_hash_len), end='\r')
            with open(file, 'rb') as f: 
                sha256_hash = hashlib.sha256(f.read()).hexdigest()
                f.close()
            rel_path = self.get_rel_path(file).lower()
            old_hash, changed = self.new_file_hashes.get(rel_path, (None, False))
            if old_hash == None or (old_hash == sha256_hash and not changed): 
                files_to_remove.append(file) 
                size += os.path.getsize(file)
                file_count += 1
            else: 
                self.new_file_hashes[rel_path] = (old_hash, True) 
                changed_hashes.append((file, rel_path))
        print('\033[F\033[K-    Processed: 100.0%' + 
                    '\n-    Files: ' + str(to_hash_len) + '/' + str(to_hash_len), end='\r')
        self.finished.emit({
            "size": size,
            "file_count": file_count,
            "files_to_remove": files_to_remove,
            "changed_hashes": changed_hashes
        })