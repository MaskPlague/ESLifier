import os
import json
import shutil
import threading
import timeit
import hashlib
import subprocess

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QThreadPool
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QApplication,
                             QSplitter, QFrame, QTextEdit, QListWidget, QListWidgetItem, QDialog, QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QIcon, QCursor

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from create_cell_master import create_new_cell_plugin
from patch_new import patch_new
from data_holder import _global
from vortex_database_reader import VortexDBParser
from log_stream import log_stream, write_error, write_normal, write_patching, write_progress, write_remove, write_to_file, clear_and_close_log, clear_and_leave_log_open
from file_defined_patcher_conditions import user_and_master_conditions_class

import platform
import psutil
if platform.system() == 'Windows':
    from win32 import win32file
    win32file._setmaxstdio(8192)

total_ram = psutil.virtual_memory().available
usable_ram = total_ram * 0.90
thread_memory_usage = 30 * 1024 * 1024
max_threads = max(1, int(usable_ram / thread_memory_usage))
if max_threads > 8192:
    MAX_THREADS = 8192
else:
    MAX_THREADS = max_threads

ESLIFIER_DATA_FOLDER = "ESLifier_Data/"

CELL_IDS_FOLDER =                   ESLIFIER_DATA_FOLDER + "Cell_IDs"

ESLIFIER_LOG_FILE =                 ESLIFIER_DATA_FOLDER + "ESLifier.log"

PREVIOUSLY_COMPACTED_JSON =         ESLIFIER_DATA_FOLDER + "previously_compacted.json" 
ESL_FLAGGED_JSON =                  ESLIFIER_DATA_FOLDER + "esl_flagged.json"
PREVIOUSLY_ESL_FLAGGED_JSON =       ESLIFIER_DATA_FOLDER + "previously_esl_flagged.json"
ORIGINAL_FILES_JSON =               ESLIFIER_DATA_FOLDER + "original_files.json"
FILE_MASTERS_JSON =                 ESLIFIER_DATA_FOLDER + "file_masters.json"
NEW_FILE_HASHES_JSON =              ESLIFIER_DATA_FOLDER + "new_file_hashes.json"
WINNING_FILE_HISTORY_DICT_JSON =    ESLIFIER_DATA_FOLDER + "winning_file_history_dict.json"
WINNING_FILES_DICT_JSON =           ESLIFIER_DATA_FOLDER + "winning_files_dict.json"
COMPACTED_AND_PATCHED_JSON =        ESLIFIER_DATA_FOLDER + "compacted_and_patched.json"
MASTER_BYTE_DATA_JSON =             ESLIFIER_DATA_FOLDER + "master_byte_data.json"
EXTRACTED_BSA_JSON =                ESLIFIER_DATA_FOLDER + "extracted_bsa.json"
FORM_ID_MAPS_JSON =                 ESLIFIER_DATA_FOLDER + "Form_ID_Maps"
CELL_MASTER_INFO_JSON =             ESLIFIER_DATA_FOLDER + "cell_master_info.json"
FLAG_DICTIONARY_JSON =              ESLIFIER_DATA_FOLDER + "flag_dictionary.json"
MISSING_SKYRIM_AS_MASTER_JSON =     ESLIFIER_DATA_FOLDER + "missing_skyrim_as_master.json"

class main(QWidget):
    def __init__(self, COLOR_MODE):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.scanned = False
        self.cell_master_warned = False
        self.dependency_dictionary: dict[str, list[str]] = {}
        self.redoing_output = False
        self.patch_new_running = False
        self.patch_new_only_remove = False
        self.generate_cell_master = False
        self.log_stream: log_stream = log_stream()
        self.COLOR_MODE = COLOR_MODE
        self.start_time = timeit.default_timer()
        self.flag_worker = None
        self.compact_worker = None
        self.patch_and_flag_worker = None
        self.scanner_worker = None
        self.files_to_not_hash = set()
        self.create_widget()

    def create_top_lables(self):
        self.eslify_label = QLabel(self.tr("ESLify"))
        self.eslify_label.setToolTip(self.tr("List of plugins that meet ESL conditions."))
        self.compact_label = QLabel(self.tr("Compact + ESLify"))
        self.compact_label.setToolTip(
            self.tr("List of plugins that can be compacted to fit ESL conditions.\n"\
            "The \'Compact/ESLify Selected\' button will also ESL the selected plugin(s)."))

    def create_mains_buttons(self):
        self.button_eslify = QPushButton(self.tr("ESLify Selected"))
        self.button_eslify.setToolTip(
            self.tr("This button will ESL flag all selected files. If the update plugin headers setting\n"\
            "is on then it will also update the plugin headers to 1.71."))
        self.button_eslify.clicked.connect(self.set_false_redoing_output)
        self.button_eslify.clicked.connect(self.eslify_selected_clicked)

        self.button_compact = QPushButton(self.tr("Compact/ESLify Selected"))
        self.button_compact.setToolTip(
            self.tr("This button will first compact a selected file, patch the plugins that have it as a\n"\
            "master, then patch and rename loose files that are dependent on the compacted plugin.\n"\
            "If the update plugin headers setting is enabled then it will also update the plugin\n"\
            "headers of the compacted and dependent plugins to 1.71."))
        self.button_compact.clicked.connect(self.set_false_redoing_output)
        self.button_compact.clicked.connect(self.compact_selected_clicked)

        self.button_scan = self.create_button(
            self.tr(" Scan Mod Files "),
            self.tr("This will scan the entire Skyrim Special Edition folder.\n"\
            "Depending on the cell and header settings, what is displayed\n"\
            "in the below lists will change."),
            self.scan
        )
        self.button_scan.clicked.connect(self.set_false_redoing_output)

        self.rebuild_output_button = self.create_button(
            self.tr(" Scan and Rebuild \n ESLifier's Output "),
            self.tr("This will delete the existing output folder's contents\n"\
            "then scan and re-patch all curently ESLified mods\n"\
            "that fit the current filters in the settings.\n"\
            "It will also confirm if any files that are in the output\n"\
            "have been changed since ESLifier patched them and give\n"\
            "an option to keep or remove them."),
            self.rebuild_output
        )

        self.scan_and_patch_new_button = self.create_button(
            self.tr(" Scan and Patch New \n or Changed Files "),
            self.tr("Scan for new plugins and files that were not\n"\
            "present during intial compacting and patching\n"\
            "and then patch those new plugins and files.\n"\
            "If in MO2/Vortex mode, it will also detect file\n"\
            "conflict changes but requires the output mod\n"\
            "in MO2/Vortex to match the exact same name as the\n"\
            "output folder in the settings.\n"\
            "This cannot detect changes in BSA and will NOT\n"\
            "check if the files in the output have been\n"\
            "changed since ESLifier patched them."),
            self.scan_and_patch_new
        )

        self.reset_output_button = self.create_button(
            self.tr(" Reset ESLifier's Output "),
            self.tr("This will delete the existing output folder's contents and\n"\
            "the data used to patch new files.\n"\
            "It will also confirm if any files that are in the output\n"\
            "have been changed since ESLifier patched them and give\n"\
            "an option to keep or remove them."),
            self.reset_output
        )

        self.reset_bsa_button = self.create_button(
            self.tr(' Delete extracted BSA files  \n Rescan BSA on next Scan '),
            self.tr('ESLifier only extracts seq and script files from a BSA once so as not to\n'\
            'go through the tedious process of extracting the releveant files in BSAs\n'\
            'each time it scans (others are extracted during patching). Use this button\n'\
            'if a BSA has new files or you have deleted a mod that had a BSA.'),
            self.reset_bsa
        )

        self.open_output_button = self.create_button(
            self.tr(" Open Output "),
            self.tr("Opens the Output Folder"),
            self.open_output
        )

        self.open_log_button = self.create_button(
            self.tr(" Open Log "),
            self.tr("Opens ESLifier.log"),
            self.open_log
        )

    def create_filters(self):
        self.filter_eslify = QLineEdit()
        self.filter_eslify.setPlaceholderText(self.tr("Filter "))
        self.filter_eslify.setToolTip(self.tr("Search Bar"))
        self.filter_eslify.setMinimumWidth(50)
        self.filter_eslify.setMaximumWidth(150)
        self.filter_eslify.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_eslify.setClearButtonEnabled(True)
        self.list_eslify.filter = self.filter_eslify
        self.filter_eslify.textChanged.connect(self.list_eslify.filter_search)
        self.list_eslify.list_created_signal.connect(self.list_eslify.filter_search)

        self.filter_compact = QLineEdit()
        self.filter_compact.setPlaceholderText(self.tr("Filter "))
        self.filter_compact.setToolTip(self.tr("Search Bar"))
        self.filter_compact.setMinimumWidth(50)
        self.filter_compact.setMaximumWidth(150)
        self.filter_compact.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_compact.setClearButtonEnabled(True)
        self.list_compact.filter = self.filter_compact
        self.filter_compact.textChanged.connect(self.list_compact.filter_search)
        self.list_compact.list_created_signal.connect(self.list_compact.filter_search)

    def create_widget(self):
        self.create_top_lables()

        self.patch_new = patch_new()

        self.list_eslify = list_eslable()
        self.list_compact = list_compactable()

        self.create_mains_buttons()

        self.create_filters()

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
        self.h_bottom_layout1 = QHBoxLayout()
        self.h_bottom_layout1.addWidget(self.button_eslify)
        self.h_bottom_layout1.addWidget(self.filter_eslify)

        #Bottom of right Column
        self.h_bottom_layout2 = QHBoxLayout()
        self.h_bottom_layout2.addWidget(self.button_compact)
        self.h_bottom_layout2.addWidget(self.filter_compact)

        def create_line():
            widget = QFrame()
            widget.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
            if self.COLOR_MODE == 'Light':
                widget.setStyleSheet('QFrame{background-color: lightgrey;}')
            return widget

        line = create_line()
        line1 = create_line()
        line2 = create_line()
        
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
        self.v_layout1.addWidget(self.eslify_label)
        self.v_layout1.addWidget(self.list_eslify)
        self.v_layout1.addLayout(self.h_bottom_layout1)

        
        #Right Column
        self.v_layout2.addWidget(self.compact_label)
        self.v_layout2.addWidget(self.list_compact)
        self.v_layout2.addLayout(self.h_bottom_layout2)

        #self.main_layout.addWidget(self.button_scan)
        self.main_layout.addWidget(splitter)

        self.v_layout1.setContentsMargins(0,11,0,11)
        self.v_layout2.setContentsMargins(0,11,0,11)

        self.main_layout.setContentsMargins(21,11,21,11)
        
        self.setLayout(self.main_layout)
        splitter.setSizes([300,1200,1200])

    def update_data(self):
        self.skyrim_folder_path =   _global.skyrim_folder_path
        self.output_folder_path =   _global.output_folder_path
        self.output_folder_name =   _global.output_folder_name
        self.generate_cell_master = _global.generate_cell_master

        self.list_compact.filter_changed_cells =    _global._settings.get('enable_cell_changed_filter', True)
        self.list_compact.filter_interior_cells =   _global._settings.get('enable_interior_cell_filter', False)
        self.list_compact.show_cells =              _global._settings.get('show_cells', True)
        self.list_compact.show_esms =               _global._settings.get('show_esms', True)
        self.list_compact.show_dlls =               _global._settings.get('show_dlls', False)
        self.list_compact.filter_seq =              _global._settings.get('filter_seq', False)
        self.list_compact.filter_pex =              _global._settings.get('filter_pex', False)
        self.list_compact.filter_worldspaces =      _global._settings.get('filter_worldspaces', True)
        self.list_compact.filter_weather =          _global._settings.get('filter_weathers', False)
        self.list_compact.cell_master =             _global._settings.get('generate_cell_master', True)
        self.list_compact.hidden_columns =          _global._settings.get('right_hidden_columns', '')

        self.list_eslify.filter_seq =               _global._settings.get('filter_seq', False)
        self.list_eslify.filter_pex =               _global._settings.get('filter_pex', False)
        self.list_eslify.filter_changed_cells =     _global._settings.get('enable_cell_changed_filter', True)
        self.list_eslify.filter_interior_cells =    _global._settings.get('enable_interior_cell_filter', False)
        self.list_eslify.show_cells =               _global._settings.get('show_cells', True)
        self.list_eslify.show_esms =                _global._settings.get('show_esms', True)
        self.list_eslify.filter_worldspaces =       _global._settings.get('filter_worldspaces', True)
        self.list_eslify.cell_master =              _global.generate_cell_master
        self.list_eslify.hidden_columns =           _global._settings.get('left_hidden_columns', '')

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
            file_masters = self.get_from_file(FILE_MASTERS_JSON)
            bsa_masters = {}
            for key, items in _global.bsa_dict.items():
                for item in items:
                    if item in bsa_masters:
                        bsa_masters[item].append(key)
                    else:
                        bsa_masters[item] = [key]
            self.confirm = self.create_confirmation(icon=QMessageBox.Icon.Information)
            self.confirm.setWindowTitle(self.tr("Getting estimated disk usage..."))
            self.confirm.setText(self.tr('Getting estimated disk usage...'))
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
                if mod_basename in bsa_masters:
                    for file in bsa_masters[mod_basename]:
                        file_lower = file.lower()
                        if file_lower not in counted and os.path.exists(file):
                            size += os.path.getsize(file)
                            counted.add(file_lower)
            total, used, free = shutil.disk_usage(self.output_folder_path)
            free_space = round(free / (1024**3), 3)
            free_space_continuation_message = self.tr(
                    "This may generate up to %1 %2 of new files\n"\
                    "(this may be inaccurate due to unpacking compressed BSA)\n"\
                    "and you have %3 GBs of space left.\n"\
                    "Are you sure you want to continue?")
            if size > 1024 ** 3:
                calculated_size = round(size / (1024 ** 3), 3)
                self.confirm.setText(free_space_continuation_message.replace("%1", str(calculated_size)).replace("%2", self.tr("GBs")).replace("%3", str(free_space)))
            elif size > 1048576:
                calculated_size = round(size / 1048576, 2)
                self.confirm.setText(free_space_continuation_message.replace("%1", str(calculated_size)).replace("%2", self.tr("MBs")).replace("%3", str(free_space)))
            else:
                calculated_size = round(size / 1024, 2)
                self.confirm.setText(free_space_continuation_message.replace("%1", str(calculated_size)).replace("%2", self.tr("KBs")).replace("%3", str(free_space)))
            if size >= free:
                self.confirm.setText(self.tr('Not enough space!\nNeeded space: %1\nSpace left: %2 GBs').replace("%1", str((round(size / 1024**3,3)))).replace("%2", str(free_space)))
                self.confirm.removeButton(QMessageBox.StandardButton.Yes)
            self.confirm.setWindowTitle(self.tr("Confirmation: Patching %1 Mod(s)").replace("%1", str(len(checked))))
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.setEnabled(True)
        elif (self.redoing_output or self.patch_new_running) and checked == []:
            self.finished_button_action('compact', checked)
        else:
            self.setEnabled(True)

    def compact_confirmed(self, checked):
        write_to_file(f'Compacting Plugins [Mod Manager Mode = {_global.mod_manager_mode}]')
        self.confirm.hide()
        self.start_time = timeit.default_timer()
        for row in range(self.list_compact.rowCount()):
            if self.list_compact.item(row,self.list_compact.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.list_compact.item(row,self.list_compact.MOD_COL).setCheckState(Qt.CheckState.PartiallyChecked)
                self.list_compact.item(row,self.list_compact.MOD_COL).setFlags(self.list_compact.item(row,self.list_compact.MOD_COL).flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.log_stream.show()
        self.compact_thread = QThread()
        self.compact_worker = CompactorWorker(checked, self.dependency_dictionary, self.files_to_not_hash)
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
            file_masters: dict[str, list[str]] = self.get_from_file(FILE_MASTERS_JSON)
            self.confirm = self.create_confirmation(icon=QMessageBox.Icon.Information)
            self.confirm.setWindowTitle(self.tr("Getting estimated disk usage..."))
            self.confirm.setText(self.tr('Getting estimated disk usage...'))
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
                # if not new_interior_cell then the mod's dependents don't need patching for ESLifier_Cell_Master and thus shouldn't be counted
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
                self.confirm.setText(self.tr("This may generate up to %1 GBs of new files\nand you have %2 GBs of space left.\nAre you sure you want to continue?").replace("%1", str(calculated_size)).replace("%2", str(free_space)))
            elif size > 1048576:
                calculated_size = round(size / 1048576, 2)
                self.confirm.setText(self.tr("This may generate up to %1 MBs of new files\nand you have %2 GBs of space left.\nAre you sure you want to continue?").replace("%1", str(calculated_size)).replace("%2", str(free_space)))
            else:
                calculated_size = round(size / 1024, 2)
                self.confirm.setText(self.tr("This may generate up to %1 KBs of new files\nand you have %2 GBs of space left.\nAre you sure you want to continue?").replace("%1", str(calculated_size)).replace("%2", str(free_space)))
            if size >= free:
                self.confirm.setText(self.tr('Not enough space!\nNeeded space: %1\nSpace left: %2 GBs').replace("%1", str((round(size / 1024**3,3)))).replace("%2", str(free_space)))
                self.confirm.removeButton(QMessageBox.StandardButton.Yes)
            self.confirm.setWindowTitle(self.tr("Confirmation: ESL Flagging %1 Mod(s)").replace("%1", str(len(checked))))
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            self.confirm.setEnabled(True)
        elif (self.redoing_output or self.patch_new_running) and checked == []:
            self.finished_button_action('eslify', checked)
        else:
            self.setEnabled(True)

    def eslify_confirmed(self, checked):
        write_to_file(f'ESL Flagging Plugins [Mod Manager Mode = {_global.mod_manager_mode}]')
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
            with open(ESL_FLAGGED_JSON, 'r', encoding='utf-8') as f:
                esl_flagged_data = json.load(f)
        except:
            esl_flagged_data = []
        for file in checked:
            basename = os.path.basename(file)
            if basename not in esl_flagged_data:
                esl_flagged_data.append(basename)
        try:
            with open(ESL_FLAGGED_JSON, 'w', encoding='utf-8') as f:
                json.dump(esl_flagged_data, f, ensure_ascii=False, indent=4)
                f.close()
        except Exception as e:
            write_error(self.tr('Failed to save esl_flagged.json'))
            write_error(e, True)

    def create_patch_and_flag_worker(self, files: list[str], patch_and_flag: list[str]):
        if len(patch_and_flag) > 0:
            full_list = files.copy()
            full_list.extend(patch_and_flag)
            self.flag_and_patch_thread = QThread()
            self.patch_and_flag_worker = CompactorWorker(patch_and_flag, self.dependency_dictionary, self.files_to_not_hash)
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
            write_normal(self.tr("File(s) ESL Flagged"))
            if self.redoing_output:
                clear_and_leave_log_open()
            else:
                clear_and_close_log()

    def create_flag_worker(self, files, patch_and_flag = []):
        self.flag_thread = QThread()
        self.flag_worker = FlagWorker(files, self.files_to_not_hash)
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
            message.setWindowTitle(self.tr("Finished"))
            message.setWindowIcon(QIcon(":/images/ESLifier.png"))
            if _global.mod_manager_mode == 0: #Manutal?
                message.setText(self.tr("ESLifier has finished. The altered files are in your ESLifier Output."))
            elif _global.mod_manager_mode == 1: #Vortex
                message.setText(self.tr("Make sure the ESLifier Output is installed as a mod and let it win any file conflicts by making the "\
                                        "output go 'After All' conflicts. Make sure to re-deploy your mods. " \
                                        "If you generate the output folder in your mod staging folder for the first time, then make sure "\
                                        "to restart Vortex to install the output. Make sure that all of your plugins are still enabled."))
            elif _global.mod_manager_mode == 2: #MO2
                message.setText(self.tr("Make sure the ESLifier Output is installed as a mod and let it win any file conflicts. "\
                                        "If you generate the output folder in your mods folder for the first time, then make sure to hit "\
                                        "refresh in MO2."))
            message.addButton(QMessageBox.StandardButton.Ok).setText(self.tr("Ok"))
            def shown():
                message.hide()
                if self.generate_cell_master and not self.cell_master_warned:
                    cell_master_message = QMessageBox()
                    cell_master_message.setWindowTitle(self.tr("Activate ESLifier_Cell_Master.esm and Sort Your Plugins"))
                    cell_master_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
                    cell_master_message.setText(self.tr("Do not forget to activate ESLifier_Cell_Master.esm and re-sort\n"\
                                                "your plugins to put the ESM above all of it's dependents. You\n"\
                                                "likely can put it at the top of your plugins list."))
                    cell_master_message.addButton(QMessageBox.StandardButton.Ok).setText(self.tr("Ok"))
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
                self.list_compact.create_list()
            if not self.patch_new_running:
                write_normal(self.tr("Total Elapsed Time: %1 Seconds").replace("%1", f"{timeit.default_timer() - self.start_time:.2f}"))
                clear_and_close_log()
                self.redoing_output = False
                self.setEnabled(True)
                self.calculate_stats()
                return
            else:
                self.patch_new_running = False
                self.patch_new_only_remove = False
                self.redoing_output = False
                self.patch_new.finished_rebuilding()
        elif sender == 'eslify':
            if len(checked_list) > 0:
                for mod in checked_list:
                    self.list_eslify.flag_dict.pop(mod)
                self.list_eslify.create_list()
            if not self.redoing_output:
                clear_and_close_log()
            elif self.redoing_output and os.path.exists(PREVIOUSLY_COMPACTED_JSON):
                clear_and_leave_log_open()
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
                    clear_and_close_log()
                    self.redoing_output = False
                    #self.setEnabled(True)
            else:
                clear_and_close_log()
                self.setEnabled(True)
        
        if not self.redoing_output:
            self.setEnabled(True)
            self.calculate_stats()

    def check_if_vortex_db_is_readable_and_warn_if_it_is_not(self):
        return_val = VortexDBParser.is_readable()
        #If not readable (1)
        if return_val != 1:
            confirm = self.create_confirmation('lightcoral')
            # 0 means locked by vortex
            if return_val == 0:
                confirm.setText(self.tr("Please close Vortex, ESLifier cannot accesss Vortex's database while it is open."))
            elif isinstance(_global.vortex_error, Exception):
                confirm.setText(self.tr(f"ESLifier has come across an error while scanning Vortex data: %0").replace('%0', str(return_val)))
            self.scanned = False
            def accept():
                confirm.hide()
            confirm.setStandardButtons(QMessageBox.StandardButton.Ok)
            confirm.accepted.connect(accept)
            confirm.show()
            return True
        return False
        
    def scan(self):
        if _global.mod_manager_mode == 1:
            if self.check_if_vortex_db_is_readable_and_warn_if_it_is_not():
                return
        self.setEnabled(False)
        self.scan_thread = QThread()
        def run_scan():
            write_to_file(f'Running Scan [Mode Manager Mode = {_global.mod_manager_mode}]')
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
            self.confirm = self.create_confirmation(icon=QMessageBox.Icon.Question)
            self.confirm.setText(self.tr("You have already scanned this session.\nWould you like to scan again?"))
            self.confirm.accepted.connect(run_scan)
            self.confirm.rejected.connect(lambda:self.setEnabled(True))
            if self.redoing_output:
                self.confirm.accept()
            else:
                self.confirm.show()

    def vortex_error(self):
        clear_and_close_log()
        confirm = self.create_confirmation('lightcoral')
        if _global.vortex_error == 0:
            confirm.setText(self.tr("Please close Vortex, ESLifier cannot accesss Vortex's database while it is open."))
        elif _global.vortex_error == 2:
            confirm.setText(self.tr("ESLifier detected that a cyclic rule is set in Vortex, please correct it first."))
        elif _global.vortex_error == 3:
            confirm.setText(self.tr("Vortex's Mod Staging Folder and ESLifier's Output Folder must be on the same drive."))
        elif isinstance(_global.vortex_error, Exception):
            confirm.setText(self.tr(f"ESLifier has come across an error while scanning Vortex data: %0").replace("%0", str(_global.vortex_error)))
        _global.vortex_error = -1
        self.scanned = False
        def accept():
            confirm.hide()
        confirm.setStandardButtons(QMessageBox.StandardButton.Ok)
        confirm.accepted.connect(accept)
        confirm.show()
        self.setEnabled(True)

    def mo2_error(self):
        clear_and_close_log()
        confirm = self.create_confirmation('lightcoral')
        if _global.mo2_error == 0:
            confirm.setText(self.tr("The MO2 instance's Mods folder and the Output Folder Path must be on the same drive."))
        elif _global.mo2_error == 1:
            confirm.setText(self.tr("The MO2 instance's Overwrite folder and the Output Folder Path must be on the same drive."))
        elif isinstance(_global.mo2_error, Exception):
            confirm.setText(self.tr(f"ESLifier has come across an error while reading MO2's ini: %0").replace("%0", str(_global.mo2_error)))
        _global.mo2_error = -1
        self.scanned = False
        def accept():
            confirm.hide()
        confirm.setStandardButtons(QMessageBox.StandardButton.Ok)
        confirm.accepted.connect(accept)
        confirm.show()
        self.setEnabled(True)
    
    def completed_scan(self, eslifiy_flag_dict, compact_flag_dict, dependency_dictionary):
        if _global.vortex_error != -1:
            self.vortex_error()
            return
        if _global.mo2_error != -1:
            self.mo2_error()
            return
        self.list_eslify.flag_dict = eslifiy_flag_dict
        self.list_compact.flag_dict = compact_flag_dict
        self.dependency_dictionary = dependency_dictionary
        write_normal(self.tr('Populating Tables'))
        try:
            self.list_eslify.create_list()
        except Exception as e:
            write_error(self.tr('Failed to create "ESLify" list'))
            write_error(e, True)
        try:
            self.list_compact.create_list()
        except Exception as e:
            write_error(self.tr('Failed to create "Compact + ESLify" list'))
            write_error(e, True)
        write_normal(self.tr('Done Scanning'))
        if self.redoing_output and not self.patch_new_only_remove:
            if os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
                clear_and_leave_log_open()
                self.list_eslify.check_previously_esl_flagged()
                #if not self.patch_new_running:
                #    os.remove(ESL_FLAGGED_JSON)
                self.eslify_selected_clicked()
            elif os.path.exists(PREVIOUSLY_COMPACTED_JSON):
                self.list_compact.check_previously_compacted()
                self.compact_selected_clicked()
        elif self.redoing_output and self.patch_new_only_remove:
            self.redoing_output = False
            self.patch_new_running = False
            self.patch_new_only_remove = False
            self.patch_new.finished_rebuilding()
        else:
            clear_and_close_log()
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
            with open(NEW_FILE_HASHES_JSON, 'r+', encoding='utf-8') as f:
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
            write_error(self.tr("Failed to open new_file_hashes.json"))
            write_error(e, True)

    def reset_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.skyrim_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            write_error(self.tr('Issue occured getting the output folder during output reset.'))
            return

        if _global.mod_manager_mode == 1:
            if self.check_if_vortex_db_is_readable_and_warn_if_it_is_not():
                return

        if _global.hash_output:
            self.calculate_existing_output_threaded('reset_output')
        else:
            files_to_remove, size, file_count = self.calculate_existing_output()
            self.reset_output_next(files_to_remove, size, file_count, [])

    def create_removal_confirmation(self, text:str, function, next_function = None):
        confirm = self.create_confirmation('tomato')
        confirm.setText(text)
        yes_button = QPushButton("3 " + self.tr("Yes"))
        confirm.addButton(yes_button, QMessageBox.ButtonRole.YesRole)
        confirm.setStandardButtons(QMessageBox.StandardButton.No)
        confirm.button(QMessageBox.StandardButton.No).setText(self.tr("No"))
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button.setEnabled(False)
        def close_confirm():
            confirm.close()
        confirm.accepted.connect(close_confirm)
        confirm.accepted.connect(function)
        if next_function is not None:
            confirm.accepted.connect(next_function)
            confirm.rejected.connect(next_function)
        def update_text(text):
            try:
                yes_button.setText(text)
            except:
                pass
        QTimer.singleShot(1000, lambda: update_text("2 " + self.tr("Yes")))
        QTimer.singleShot(2000, lambda: update_text("1 " + self.tr("Yes")))
        def enable_and_set_text():
            try:
                yes_button.setEnabled(True)
                yes_button.setText(self.tr("Yes"))
            except:
                pass
        QTimer.singleShot(3000, enable_and_set_text)
        return confirm
    
    def reset_output_next(self, files_to_remove, size, file_count, changed_rel_paths_to_switch):
        confirm = self.create_confirmation('lightcoral')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            self.tr(
                "Are you sure you want to delete the output folder %1's contents and all data used to patch new files?\n" \
                "This action will delete %2 files and %3 MBs of data from the output."
            ).replace("%1", self.output_folder_name).replace("%2", str(file_count)).replace("%3", str(calculated_size)))
        def accepted():
            write_to_file(f'Resetting Output [Mode Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            if os.path.exists(COMPACTED_AND_PATCHED_JSON):
                try:
                    compacted_and_patched_dict = {}
                    with open(COMPACTED_AND_PATCHED_JSON, 'r', encoding='utf-8') as f:
                        compacted_and_patched_dict = json.load(f)
                        f.close()
                    previously_compacted = [key for key in compacted_and_patched_dict.keys()]
                    with open(PREVIOUSLY_COMPACTED_JSON, 'w', encoding='utf-8') as f:
                        json.dump(previously_compacted, f, ensure_ascii=False, indent=4)
                        f.close()
                    os.remove(COMPACTED_AND_PATCHED_JSON)
                except Exception as e:
                    write_error(self.tr("Failed in Compacted and Patched deletion process."))
                    write_error(e, True)
            if os.path.exists(ESL_FLAGGED_JSON):
                if os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
                    os.remove(PREVIOUSLY_ESL_FLAGGED_JSON)
                shutil.copy(ESL_FLAGGED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON)
                os.remove(ESL_FLAGGED_JSON)
            if os.path.exists(ORIGINAL_FILES_JSON):
                os.remove(ORIGINAL_FILES_JSON)
            if os.path.exists(MASTER_BYTE_DATA_JSON):
                os.remove(MASTER_BYTE_DATA_JSON)
            self.delete_output(self.output_folder_full, files_to_remove)
            self.list_compact.flag_dict = {}
            self.list_eslify.flag_dict = {}
            self.list_compact.create_list()
            self.list_eslify.create_list()
            def previous_removal_confirmation():
                def accepted3():
                    if os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
                        os.remove(PREVIOUSLY_ESL_FLAGGED_JSON)
                    if os.path.exists(PREVIOUSLY_COMPACTED_JSON):
                        os.remove(PREVIOUSLY_COMPACTED_JSON)
                confirm3 = self.create_removal_confirmation(
                    self.tr("Would you like to remove the ESLifier Data that stores\n"\
                            "info used to reselect your previously ESL flagged/compacted\n"\
                            "mods? Do this only if you are performing a full reset."),
                    accepted3
                )
                confirm3.show()
            if os.path.exists(NEW_FILE_HASHES_JSON) and _global.hash_output:
                self.update_changed_rel_paths_in_new_files_hashes(changed_rel_paths_to_switch)
                def accepted2():
                    if os.path.exists(NEW_FILE_HASHES_JSON):
                        os.remove(NEW_FILE_HASHES_JSON)
                confirm2 = self.create_removal_confirmation(
                    self.tr("Would you like to remove the ESLifier Output hash info?\n"\
                            "This is how ESLifier can tell if a file in the output\n"\
                            "has been changed after ESLifier patched it.\n"\
                            "This is NOT recommended, especially if you kept any\n"\
                            "changed files."),
                    accepted2,
                    previous_removal_confirmation
                )
                confirm2.show()
            else:
                previous_removal_confirmation()

            self.calculate_stats()
            clear_and_close_log()

        confirm.accepted.connect(accepted)
        confirm.rejected.connect(clear_and_close_log)
        confirm.show()

    def rebuild_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.skyrim_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            write_error(self.tr('Issue occured getting the output folder during output rebuild.'))
            return

        if _global.mod_manager_mode == 1:
            if self.check_if_vortex_db_is_readable_and_warn_if_it_is_not():
                return

        if _global.hash_output:
            self.calculate_existing_output_threaded('rebuild_output')
        else:
            files_to_remove, size, file_count = self.calculate_existing_output()
            self.rebuild_output_next(files_to_remove, size, file_count, [])
        
    def rebuild_output_next(self, files_to_remove, size, file_count, changed_rel_paths_to_switch):
        confirm = self.create_confirmation('skyblue')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            self.tr(
                "Are you sure you want to recreate the output folder %1?\n" \
                "This action will delete %2 files and %3 MBs of data from the output and\n" \
                "re-scan, flag, compact, and patch all previously output files that fit the current filters.\n" \
                "If deletion of the output folder takes more than 5 seconds, blame your anti-virus\n"\
                "and maybe move your output/game install to a non-protected folder."
            ).replace("%1", self.output_folder_name).replace("%2", str(file_count)).replace("%3", str(calculated_size)))
        def accepted():
            write_to_file(f'Starting Output Rebuild [Mode Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            previously_compacted = []
            previously_esl_flagged = []
            if os.path.exists(NEW_FILE_HASHES_JSON):
                self.update_changed_rel_paths_in_new_files_hashes(changed_rel_paths_to_switch)
            if os.path.exists(COMPACTED_AND_PATCHED_JSON):
                compacted_and_patched_dict = {}
                with open(COMPACTED_AND_PATCHED_JSON, 'r', encoding='utf-8') as f:
                    compacted_and_patched_dict = json.load(f)
                    f.close()
                previously_compacted = [key for key in compacted_and_patched_dict.keys()]
                with open(PREVIOUSLY_COMPACTED_JSON, 'w', encoding='utf-8') as f:
                    json.dump(previously_compacted, f, ensure_ascii=False, indent=4)
                    f.close()
                os.remove(COMPACTED_AND_PATCHED_JSON)
            elif os.path.exists(PREVIOUSLY_COMPACTED_JSON):
                previously_compacted = self.get_from_file(PREVIOUSLY_COMPACTED_JSON)
            if os.path.exists(ESL_FLAGGED_JSON):
                previously_esl_flagged = self.get_from_file(ESL_FLAGGED_JSON)
                if os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
                    os.remove(PREVIOUSLY_ESL_FLAGGED_JSON)
                shutil.copy(ESL_FLAGGED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON)
                os.remove(ESL_FLAGGED_JSON)
            elif os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
                previously_esl_flagged = self.get_from_file(PREVIOUSLY_ESL_FLAGGED_JSON)
            if os.path.exists(ORIGINAL_FILES_JSON):
                os.remove(ORIGINAL_FILES_JSON)
            if os.path.exists(WINNING_FILE_HISTORY_DICT_JSON):
                os.remove(WINNING_FILE_HISTORY_DICT_JSON)
            if os.path.exists(WINNING_FILES_DICT_JSON):
                os.remove(WINNING_FILES_DICT_JSON)
            if os.path.exists(MASTER_BYTE_DATA_JSON):
                os.remove(MASTER_BYTE_DATA_JSON)
            if len(previously_compacted) == 0 and len(previously_esl_flagged) == 0:
                QMessageBox.warning(None, self.tr("No Existing Output Data"), self.tr("There is no existing output data for ESLifier to use."))
                clear_and_close_log()
                return
            self.delete_output(self.output_folder_full, files_to_remove, remove_maps=False)
            self.calculate_stats()
            self.redoing_output = True
            self.scan()

        confirm.accepted.connect(accepted)
        confirm.rejected.connect(clear_and_close_log)
        confirm.show()

    def reset_bsa(self):
        confirm = self.create_confirmation('lightcoral')
        confirm_text = self.tr(
                "Are you sure you want to reset the Extracted BSA List?\n"\
                "This will cause the next scan to take significantly longer as the BSA files will\n"\
                "need to be extracted again and irrelevant script files will need to be filtered.\n\n"\
                "This can take a short bit and may freeze the UI\n"\
                "or you can manually delete the \"bsa_extracted/\" folder\n"\
                "and then click this button.")
        confirm.setText(confirm_text)
        def accepted():
            write_to_file(f'Resetting BSA [Mode Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            if os.path.exists(EXTRACTED_BSA_JSON):
                os.remove(EXTRACTED_BSA_JSON)
            if os.path.exists('bsa_extracted/'):
                def delete_directory(dir_path):
                    try:
                        shutil.rmtree(dir_path)
                    except Exception:
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
            self.list_compact.create_list()
            self.list_eslify.create_list()
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
                write_error(self.tr("Error opening folder: ") + str(e))

    def open_log(self):
        log_file = os.path.join(os.getcwd(), ESLIFIER_LOG_FILE)
        if os.path.exists(log_file):
            try:
                if os.name == 'nt':
                    os.startfile(log_file)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', log_file])
                else:
                    subprocess.Popen(['open', log_file])
            except Exception as e:
                write_error(self.tr("Error opening file:: ") + str(e))

    def create_button(self, button_text, tooltip, click_function):
        button = QPushButton(button_text)
        button.clicked.connect(click_function)
        button.setToolTip(tooltip)
        return button
    
    def create_confirmation(self, color:str = '', icon:QMessageBox.Icon = QMessageBox.Icon.Warning):
        confirm = QMessageBox()
        confirm.setIcon(icon)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        if color != '':
            confirm.setStyleSheet("""
                QMessageBox {
                    background-color: """+color+""";
                }""")
        confirm.setWindowTitle(self.tr("Confirmation"))
        confirm.addButton(QMessageBox.StandardButton.Yes).setText(self.tr("Yes"))
        confirm.addButton(QMessageBox.StandardButton.Cancel).setText(self.tr("Cancel"))
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirm._savedSetEnabled = confirm.setEnabled
        def newSetEnabled(a0:bool):
            confirm._savedSetEnabled(a0)
            confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
            confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirm.setEnabled = newSetEnabled
        return confirm
    
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
        self.new_file_hashes = self.get_from_file(NEW_FILE_HASHES_JSON)

        files_to_hash = []
        for root, _, files in os.walk(self.output_folder_full):
            for f in files:
                files_to_hash.append(os.path.join(root, f))
        clear_and_leave_log_open()
        self.log_stream.show()
        write_normal(self.tr("Hashing output for changes..."))
        write_normal("", False)
        self.hasher_thread = QThread()
        self.hasher_worker = HashWorker(files_to_hash, self.new_file_hashes)
        self.hasher_worker.moveToThread(self.hasher_thread)
        self.hasher_thread.started.connect(self.hasher_worker.run)
        self.hasher_worker.finished.connect(self.on_hashing_finished)
        self.hasher_worker.finished.connect(self.hasher_thread.quit)
        self.hasher_thread.start()

    def create_changed_hash_list_widget(self):
        def somethingChanged(item_changed:QListWidgetItem):
            listWidget.blockSignals(True)
            if item_changed in listWidget.selectedItems():
                if item_changed.checkState() == Qt.CheckState.Checked:
                    for x in listWidget.selectedItems():
                        x.setCheckState(Qt.CheckState.Checked)
                else:
                    for x in listWidget.selectedItems():
                        x.setCheckState(Qt.CheckState.Unchecked)
            listWidget.blockSignals(False)

        listWidget = QListWidget()
        listWidget.itemChanged.connect(somethingChanged)
        listWidget.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        listWidget.setSelectionBehavior(QListWidget.SelectionBehavior.SelectRows)
        listWidget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        listWidget.setAutoScroll(True)

        return listWidget

    def on_hashing_finished(self, result):
        total_size: int = result["size"]
        total_file_count: int = result["file_count"]
        files_to_remove:list[str] = result["files_to_remove"]
        changed_hashes:list = result["changed_hashes"]
        self.setEnabled(True)

        write_normal(self.tr("Hashing for changes complete."))
        write_normal(self.tr("Found %1 changed files.").replace("%1", str(len(changed_hashes))))
        changed_rel_paths_to_switch = []

        if changed_hashes:
            with open(NEW_FILE_HASHES_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.new_file_hashes, f, ensure_ascii=False, indent=4)
                f.close()
            dialog = QDialog()
            dialog.setWindowIcon(QIcon(":/images/ESLifier.png"))
            dialog.setWindowTitle(self.tr("Select files to remove."))
            dialog.setStyleSheet("QDialog {background-color: tomato;}")
            dialog.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

            layout = QVBoxLayout()
            buttons_widget = QWidget()
            buttons_layout = QHBoxLayout()
            buttons_widget.setLayout(buttons_layout)
            
            filter = QLineEdit()
            filter.setPlaceholderText(self.tr("Filter"))
            filter.setToolTip(self.tr("Search bar"))
            filter.setMinimumWidth(50)
            filter.setMaximumWidth(150)
            filter.setAlignment(Qt.AlignmentFlag.AlignRight)
            filter.setClearButtonEnabled(True)

            plugin_files = []
            other_files = []
            for file, rel_path in changed_hashes:
                if rel_path.endswith(('.esp', '.es', '.esm')):
                    plugin_files.append((file, rel_path))
                else:
                    other_files.append((file, rel_path))

            plugins_listWidget = self.create_changed_hash_list_widget()
            other_listWidget = self.create_changed_hash_list_widget()
    
            def filtered():
                if len(filter.text()) > 0:
                    items = plugins_listWidget.findItems(filter.text(), Qt.MatchFlag.MatchContains)
                    for i in range(plugins_listWidget.count()):
                        plugins_listWidget.setRowHidden(i, False if plugins_listWidget.item(i) in items else True)
                    items = other_listWidget.findItems(filter.text(), Qt.MatchFlag.MatchContains)
                    for i in range(other_listWidget.count()):
                        other_listWidget.setRowHidden(i, False if other_listWidget.item(i) in items else True)
                else:
                    for i in range(plugins_listWidget.count()):
                        plugins_listWidget.setRowHidden(i, False)
                    for i in range(other_listWidget.count()):
                        other_listWidget.setRowHidden(i, False)
    
            filter.textEdited.connect(filtered)
            buttons_layout.addWidget(filter)
            
            self.hash_changed_option = 'keep_all'
            def delete_selected():
                self.hash_changed_option = 'delete_selected'
                dialog.close()
            delete_selected_button = self.create_button("3 " + self.tr("Delete Selected"), self.tr("Deletes only the selected files."), delete_selected)
            delete_selected_button.setStyleSheet("QPushButton {background-color: red;}")
            delete_selected_button.setEnabled(False)
            
            def delete_all():
                self.hash_changed_option = 'delete_all'
                dialog.close()
            delete_all_button = self.create_button("3 " + self.tr("Delete All"), self.tr("Deletes all files regardless of selection."), delete_all)
            delete_all_button.setStyleSheet("QPushButton {background-color: red;}")
            delete_all_button.setEnabled(False)

            def keep_all():
                self.hash_changed_option = 'keep_all'
                dialog.close()
            keep_all_button = self.create_button(self.tr("Keep All"), self.tr("Keeps all files regardless of selection."), keep_all)
            keep_all_button.setStyleSheet("QPushButton {background-color: lime;}")

            buttons_layout.addWidget(delete_all_button)
            buttons_layout.addWidget(delete_selected_button)
            buttons_layout.addWidget(keep_all_button)
            dialog.setLayout(layout)

            for file, rel_path in plugin_files:
                item = QListWidgetItem(rel_path)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(os.path.normpath(file))
                item.setData(0, rel_path)
                plugins_listWidget.addItem(item)

            for file, rel_path in other_files:
                item = QListWidgetItem(rel_path)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(os.path.normpath(file))
                item.setData(0, rel_path)
                other_listWidget.addItem(item)

            if plugin_files:
                label_plugins = QLabel(self.tr("The following plugins have had their hashes change since they were patched by ESLifier.\n"\
                                               "This could be because you or another program changed them. Be VERY careful as deleting\n"\
                                                "or not deleting these could have consequences."))
                layout.addWidget(label_plugins)
                layout.addWidget(plugins_listWidget)
            if other_files:
                other_label = QLabel(self.tr("The following files have had their hashes change since they were patched by ESLifier.\n"\
                                "These files could be config or data storage files that you may want to keep."))
                layout.addWidget(other_label)
                layout.addWidget(other_listWidget)
            choices_label = QLabel(self.tr("Select the files you would like to remove and select \"Delete Selected\",\n"\
                                            "select \"Delete All\" to delete all files regardless of selection,\n"\
                                            "or select \"Keep All\" to not delete any files."))
            layout.addWidget(choices_label)
            layout.addWidget(buttons_widget)

            
            def rename_2():
                delete_selected_button.setText("2 " + self.tr("Delete Selected"))
                delete_all_button.setText("2 " + self.tr("Delete All"))

            def rename_1():
                delete_selected_button.setText("1 " + self.tr("Delete Selected"))
                delete_all_button.setText("1 " + self.tr("Delete All"))
            
            def rename_and_enable():
                delete_selected_button.setText(self.tr("Delete Selected"))
                delete_selected_button.setEnabled(True)
                delete_all_button.setText(self.tr("Delete All"))
                delete_all_button.setEnabled(True)

            QTimer.singleShot(1000, rename_2)
            QTimer.singleShot(2000, rename_1)
            QTimer.singleShot(3000, rename_and_enable)
            keep_all_button.setFocus()
            dialog.exec()
            self.files_to_not_hash.clear()

            def get_files_to_remove(listWidget: QListWidget):
                nonlocal total_size
                nonlocal total_file_count
                nonlocal files_to_remove
                nonlocal changed_rel_paths_to_switch
                for index in range(0, listWidget.count()):
                    item = listWidget.item(index)
                    if item.checkState() == Qt.CheckState.Checked:
                        files_to_remove.append(item.toolTip())
                        changed_rel_paths_to_switch.append(item.data(0))
                        total_size += os.path.getsize(item.toolTip())
                        total_file_count += 1
                    else:
                        self.files_to_not_hash.add(item.toolTip().lower())                

            if self.hash_changed_option == 'delete_all':
                for file, rel_path in changed_hashes:
                    files_to_remove.append(file)
                    changed_rel_paths_to_switch.append(rel_path)
                    total_size += os.path.getsize(file)
                    total_file_count += 1
            elif self.hash_changed_option == 'delete_selected':
                if plugin_files:
                    get_files_to_remove(plugins_listWidget)
                if other_files:
                    get_files_to_remove(other_listWidget)

            elif self.hash_changed_option == 'keep_all':
                for file, rel_path in self.changed_hashes:
                    self.files_to_not_hash.add(os.path.normpath(file).lower())
        if self.calculate_requester == 'reset_output':
            self.reset_output_next(files_to_remove, total_size, total_file_count, changed_rel_paths_to_switch)
        elif self.calculate_requester == 'rebuild_output':
            self.rebuild_output_next(files_to_remove, total_size, total_file_count, changed_rel_paths_to_switch)
    
    def prune_empty_dirs_recursive(self, path, output_folder):
        #in this use case os.listdir and os.scandir are the same speed
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
                write_to_file(f"Warn: Could not remove {path}: {e}")
        
    def delete_output(self, output_folder: str, files_to_remove: list[str], remove_maps=True):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))   
        if remove_maps:
            shutil.rmtree(FORM_ID_MAPS_JSON, ignore_errors=True)
        shutil.rmtree(CELL_IDS_FOLDER, ignore_errors=True)
        def silent_remove(file_path):
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                write_to_file(f"Warn: Could not remove {file_path}: {e}")
        silent_remove(CELL_MASTER_INFO_JSON)
        silent_remove(WINNING_FILE_HISTORY_DICT_JSON)
        silent_remove(WINNING_FILES_DICT_JSON)
        if os.path.exists(output_folder) and 'eslifier' in output_folder.lower():
            #if vortex then we need to restore any .vortex_backup
            if _global.mod_manager_mode == 1 and _global.vortex_restore_backups:
                gamedata = VortexDBParser.get_section("settings###gameMode###discovered###skyrimse")
                skyrim_folder_path = os.path.normpath(os.path.join(gamedata.get('path'), "Data"))

                for file in files_to_remove:
                    rel_path = os.path.relpath(file, output_folder)
                    data_folder_file_path = os.path.join(skyrim_folder_path, rel_path)
                    vortex_backup_path = data_folder_file_path + '.vortex_backup'
                    if os.path.exists(vortex_backup_path) and os.path.samefile(file, data_folder_file_path):
                        silent_remove(data_folder_file_path)
                        shutil.copy(vortex_backup_path, data_folder_file_path)
                    silent_remove(file)
            else:
                for file in files_to_remove:
                    silent_remove(file)
            self.prune_empty_dirs_recursive(output_folder, output_folder)
        QApplication.restoreOverrideCursor()

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

        stats_text = (self.tr(
                    "Output Stats:\n"\
                    "  Size:\n"\
                    "    > %1\n"\
                    "  File Count:\n"\
                    "    > %2"
                    ).replace("%1", str(calculated_size)).replace("%2", str(file_count)))
        if self.scanned:
            stats_text += ("\n\n" + self.tr(
                    "Scanned Stats:\n"\
                    "  Flaggable:\n"\
                    "    > %1\n"\
                    "  Compactible:\n"\
                    "    > %2"
                    ).replace("%1", str(flaggable_count)).replace("%2", str(compactible_count)))
        self.stats.setText(stats_text)

    def scan_and_patch_new(self):
        if _global.mod_manager_mode == 1:
            if self.check_if_vortex_db_is_readable_and_warn_if_it_is_not():
                return
        self.setEnabled(False)
        confirm = self.create_confirmation()
        confirm.setText(self.tr("Are you sure you want to scan and patch new/changed files?"))
        def accepted():
            write_to_file(f'Starting Patch New Process [Mode Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            self.log_stream.show()
            self.patch_new.scan_and_find(self)
        confirm.accepted.connect(accepted)
        confirm.rejected.connect(lambda: self.setEnabled(True))
        confirm.show()

class ScannerWorker(QObject):
    finished_signal = pyqtSignal(dict, dict, dict)
    def __init__(self):
        super().__init__()

    def scan_run(self):
        write_remove(-1, self.tr('Scanning All Files:'), True)
        flag_dict, dependency_dictionary = scanner.scan(True)
        if _global.vortex_error != -1:
            self.finished_signal.emit({}, {}, {})
            return
        write_normal(self.tr('Checking if New CELLs are Changed'))
        plugins_with_cells = [plugin for plugin, flags in flag_dict.items() if 'new_cell' in flags]
        cell_scanner.scan(plugins_with_cells)
        eslify_flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' not in f and 'adhseam_problem' not in f}
        compact_flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' in f}
        self.finished_signal.emit(eslify_flag_dict, compact_flag_dict, dependency_dictionary)
        return

class CompactorWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, files_to_not_hash: set):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.update_header: bool = _global.update_header
        self.create_new_cell_plugin = create_new_cell_plugin()
        self.generate_cell_master = _global.generate_cell_master
        self.files_to_not_hash: set = files_to_not_hash
        
    def run(self):
        total = len(self.checked)
        count = 0
        if self.update_header:
            try:
                with open(MISSING_SKYRIM_AS_MASTER_JSON, 'r', encoding='utf-8') as f:
                    missing_skyrim_esm = json.load(f)
            except:
                missing_skyrim_esm = {}
        with open(FLAG_DICTIONARY_JSON, 'r', encoding='utf-8') as f:
            flag_dict = json.load(f)
        if self.generate_cell_master:
            self.create_new_cell_plugin.generate(_global.output_folder_joined_path)
        finalize = False
        original_files: dict = self.get_from_file(ORIGINAL_FILES_JSON)
        winning_files_dict: dict = self.get_from_file(WINNING_FILES_DICT_JSON)
        master_byte_data: dict = self.get_from_file(MASTER_BYTE_DATA_JSON)
        files_to_patch: dict = self.get_from_file(FILE_MASTERS_JSON)
        bsa_masters = []
        for value in _global.bsa_dict.values():
            bsa_masters.extend(value)

        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(self.create_new_cell_plugin, original_files, winning_files_dict, {}, {}, master_byte_data, bsa_masters,
                       additional_file_patcher_conditions)
        if _global.hash_output:
            write_normal(self.tr("Hashing any existing files for changes..."))
            cfids.hash_output_files(set(), True)
        clear_and_leave_log_open()
        patching_str = self.tr("%0% Patching: %1/%2").replace("%0", "{0}").replace("%1", "{1}").replace("%2", "{2}")
        for file in self.checked:
            count +=1
            percent = round((count/total)*100,1)
            write_patching(round(percent), patching_str.format(percent, count, total))
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
            write_normal(self.tr('Creating/Updating ESLifier_Cell_Master.esm...'))
            self.create_new_cell_plugin.finalize_plugin()
        write_normal(self.tr('Saving Data...'))
        cfids.save_data()
        if _global.hash_output:
            write_normal(self.tr('Hashing output files for checking later changes...'))
            cfids.hash_output_files(self.files_to_not_hash)
        write_normal(self.tr("Patching Complete"))
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
    def __init__(self, files, files_to_not_hash):
        self.files = files
        self.files_to_not_hash = files_to_not_hash
        super().__init__()
    
    def flag_files(self):
        original_files = self.get_from_file(ORIGINAL_FILES_JSON)
        winning_files_dict = self.get_from_file(WINNING_FILES_DICT_JSON)
        winning_file_history_dict = {}
        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(None, original_files, winning_files_dict, winning_file_history_dict, {}, {}, [], additional_file_patcher_conditions)
        if _global.hash_output:
            write_normal(self.tr("Hashing any existing files for changes..."))
            cfids.hash_output_files(set(), True)
        for file in self.files:
            original_files, winning_file_history_dict = cfids.set_flag(file)
        if _global.hash_output:
            write_normal(self.tr('Hashing output files for checking later changes...'))
            cfids.hash_output_files(self.files_to_not_hash)
        self.dump_dictionary(ORIGINAL_FILES_JSON, original_files)
        self.dump_dictionary(WINNING_FILE_HISTORY_DICT_JSON, winning_file_history_dict)
        self.finished_signal.emit()

    def dump_dictionary(self, file, dictionary: dict):
        data = self.get_from_file(file)
        for key, values in dictionary.items():
            data[key] = values
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            write_error(self.tr("Failed to dump data to ") + file)
            write_error(e, True)
    
    def get_from_file(self, file: str) -> dict:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    

class HashWorker(QObject):
    finished = pyqtSignal(dict)
    def __init__(self, files, new_file_hashes):
        super().__init__()
        self.files = files
        self.new_file_hashes:dict = new_file_hashes
        self.lock = threading.Lock()

    def run(self):
        self.to_hash_len = len(self.files)
        
        thread_count = min(16, (os.cpu_count() or 4))
        chunk_size = max(1, self.to_hash_len // thread_count)

        chunks = [self.files[i:i + chunk_size] for i in range(0, self.to_hash_len, chunk_size)]
        
        self.results = []
        self.hash_progress = 0
        
        threads: list[threading.Thread] = []
        for chunk in chunks:
            thread = threading.Thread(target=self.hash_files, args=(chunk,))
            threads.append(thread)
            thread.start()
            
        for thread in threads: thread.join()
            
        size = 0
        file_count = 0
        files_to_remove = []
        changed_hashes = []
        
        for local_size, local_count, local_remove, local_changed, local_new in self.results:
            size += local_size
            file_count += local_count
            files_to_remove.extend(local_remove)
            changed_hashes.extend(local_changed)
            self.new_file_hashes.update(local_new)
            
        processed_str = ('-    ' + self.tr("Processed: %1%") + 
                       '\n-    ' + self.tr("Files: %2/%3")).replace("%1", "{0}").replace("%2", "{1}").replace("%3", "{2}")
        
        write_progress(100, 1, processed_str.format(100.0, self.to_hash_len, self.to_hash_len))
        self.finished.emit({
            "size": size,
            "file_count": file_count,
            "files_to_remove": files_to_remove,
            "changed_hashes": changed_hashes
        })

    def hash_files(self, files):
        local_size = 0
        local_file_count = 0
        local_files_to_remove = []
        local_changed_hashes = []
        local_new_file_hashes = {}
        processed_str = ('-    ' + self.tr("Processed: %1%") + 
                       '\n-    ' + self.tr("Files: %2/%3")).replace("%1", "{0}").replace("%2", "{1}").replace("%3", "{2}")
        update_factor = max(1, round(self.to_hash_len * 0.001))
        local_progress_batch = 0

        get_rel_path = _global.get_rel_path
        warn = _global.hash_plugins_warn

        for file in files:
            if not warn and file.lower().endswith(('.esp', '.esl', '.esm')):
                local_progress_batch += 1
                continue
                
            try:
                with open(file, 'rb') as f:
                    sha256_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                local_progress_batch += 1
                continue
                
            rel_path = get_rel_path(file).lower()
            old_hash, changed = self.new_file_hashes.get(rel_path, (None, False))
            
            if old_hash is None or (old_hash == sha256_hash and not changed):
                local_files_to_remove.append(file)
                try:
                    local_size += os.path.getsize(file)
                except OSError: pass
                local_file_count += 1
            else:
                local_new_file_hashes[rel_path] = (old_hash, True)
                local_changed_hashes.append((file, rel_path))
                
            local_progress_batch += 1
            if local_progress_batch >= update_factor:
                with self.lock:
                    self.hash_progress += local_progress_batch
                    current_prog = self.hash_progress
                local_progress_batch = 0
                
                percentage = round((current_prog / self.to_hash_len) * 100, 1)
                write_progress(round(percentage), 1, processed_str.format(percentage, current_prog, self.to_hash_len))
                
        # Add any remaining progress for this batch
        if local_progress_batch > 0:
            with self.lock:
                self.hash_progress += local_progress_batch

        with self.lock:
            self.results.append((local_size, local_file_count, local_files_to_remove, local_changed_hashes, local_new_file_hashes))