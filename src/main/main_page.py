import os
import json
import shutil
import threading
import timeit
import subprocess

from PyQt6.QtCore import Qt, QThread, QObject, QTimer, pyqtBoundSignal
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QApplication,
                             QSplitter, QFrame, QTextEdit, QListWidget, QListWidgetItem, QDialog, QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QIcon, QCursor

from lists.list_eslify import list_eslable
from lists.list_compact import list_compactable
from lists.list_parent import list_parent_class
from patch_new import patch_new
from main.flow import Flow
from main.utils import size_in_units, ListObjBase
import main.workers as Workers
from data_holder import (_global, VERBOSE_GAME_NAME, VORTEX_GAME_NAME, GAME_MODE, ARCHIVE_EXTRACTED_FOLDER, ESLIFIER_PNG_ICON_PATH,
                         CELL_IDS_FOLDER, COMPACTED_AND_PATCHED_JSON, ESL_FLAGGED_JSON, ESLIFIER_LOG_FILE, CELL_MASTER_INFO_JSON, 
                         EXTRACTED_GAME_ARCHIVE_JSON, FILE_MASTERS_JSON, FORM_ID_MAPS_FOLDER, MASTER_BYTE_DATA_JSON, 
                         NEW_FILE_HASHES_JSON, ORIGINAL_FILES_JSON, WINNING_FILE_HISTORY_DICT_JSON, WINNING_FILES_DICT_JSON,
                         PREVIOUSLY_COMPACTED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON, GAME_ARCHIVE_TYPE)

from scanners.vortex_database_reader import VortexDBParser
from log_stream import log_stream, write_error, write_normal, write_to_file, clear_and_close_log, clear_and_leave_log_open
from scanners.vortex_database_reader import ReadState
from scanners.scanner_vortex import VortexErrors
from scanners.scanner_mo2 import MO2Errors

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

class main(QWidget):
    def __init__(self, COLOR_MODE):
        super().__init__()
        self.game_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.scanned = False
        self.cell_master_warned = False
        self.dependency_dictionary: dict[str, list[str]] = {}
        self.flow = Flow.NONE
        self.generate_cell_master = False
        self.log_stream: log_stream = log_stream()
        self.COLOR_MODE = COLOR_MODE
        self.start_time = timeit.default_timer()
        self.flag_worker = None
        self.compact_worker = None
        self.patch_and_flag_worker = None
        self.scanner_worker = None
        self.running_workers:list[tuple[QThread,QObject]] = []
        self.files_to_not_hash = set()
        self.skip_confirmations = set()
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
            "is on then it will also update the plugin headers to %0.").replace("%0", "1.71" if GAME_MODE == "SSE" else "1.0"))
        self.button_eslify.clicked.connect(self.set_false_redoing_output)
        self.button_eslify.clicked.connect(self.eslify_selected_clicked)

        self.button_compact = QPushButton(self.tr("Compact/ESLify Selected"))
        self.button_compact.setToolTip(
            self.tr("This button will first compact a selected file, patch the plugins that have it as a\n"\
            "master, then patch and rename loose files that are dependent on the compacted plugin.\n"\
            "If the update plugin headers setting is enabled then it will also update the plugin\n"\
            "headers of the compacted and dependent plugins to %0").replace("%0", "1.71" if GAME_MODE == "SSE" else "1.0"))
        self.button_compact.clicked.connect(self.set_false_redoing_output)
        self.button_compact.clicked.connect(self.compact_selected_clicked)

        self.button_scan = self.create_button(
            self.tr(" Scan Mod Files "),
            self.tr("This will scan the entire %0 folder.\n"\
            "Depending on the cell and header settings, what is displayed\n"\
            "in the below lists will change.").replace("%0", VERBOSE_GAME_NAME),
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
            f"This cannot detect changes in {GAME_ARCHIVE_TYPE} and will NOT\n"\
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

        self.reset_game_archive_button = self.create_button(
            self.tr(' Delete extracted %0 files  \n Rescan %0 on next Scan ').replace("%0", GAME_ARCHIVE_TYPE),
            self.tr('ESLifier only extracts seq and script files from a %0 once so as not to\n'\
            'go through the tedious process of extracting the releveant files in %0s\n'\
            'each time it scans (others are extracted during patching). Use this button\n'\
            'if a %0 has new files or you have deleted a mod that had a %0.').replace("%0", GAME_ARCHIVE_TYPE),
            self.reset_game_archive
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
        self.v_layout0.addWidget(self.reset_game_archive_button)
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
        self.game_folder_path =   _global.game_folder_path
        self.output_folder_path =   _global.output_folder_path
        self.output_folder_name =   _global.output_folder_name
        self.generate_cell_master = _global.generate_cell_master
        self.skip_confirmations = set([con.strip().upper() for con in _global._settings.get('skip_confirmations', '').split(',')])

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

        #FO4
        self.list_compact.filter_precombines =      _global._settings.get('filter_previs_precombine', True)
        self.list_eslify.filter_precombines =       _global._settings.get('filter_previs_precombine', True)

    @property
    def redoing_output(self) -> bool:
        return self.flow.redoing

    @property
    def patch_new_running(self) -> bool:
        return self.flow.patch_new

    @property
    def patch_new_only_remove(self) -> bool:
        return self.flow.only_remove

    def set_false_redoing_output(self):
        self.flow = Flow.NONE

    def compact_selected_clicked(self):
        self.selected_clicked('compact')

    def eslify_selected_clicked(self):
        self.selected_clicked('eslify')

    def make_list_obj(self, name) -> ListObjBase:
        if name == 'compact':
            return ListObjBase(name, self.list_compact, "COMPACT",
                               self.tr("Confirmation: Patching %1 Mod(s)"),
                               self.compact_confirm_text, self.compact_confirmed)
        else:
            return ListObjBase(name, self.list_eslify, "FLAG",
                               self.tr("Confirmation: ESL Flagging %1 Mod(s)"),
                               self.eslify_confirm_text, self.eslify_confirmed)

    def get_checked_mods(self, mod_list: list_parent_class):
        checked = []
        mod_list.clearSelection()
        for row in range(mod_list.rowCount()):
            item = mod_list.item(row, mod_list.MOD_COL)
            if item.checkState() == Qt.CheckState.Checked and not mod_list.item(row, mod_list.HIDER_COL):
                checked.append(item.toolTip())
        return checked

    def lock_checked_rows(self, mod_list:list_parent_class):
        for row in range(mod_list.rowCount()):
            item = mod_list.item(row, mod_list.MOD_COL)
            if item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.PartiallyChecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

    def game_archive_masters_by_file(self):
        game_archive_masters = {}
        for archive, masters in _global.game_archive_dict.items():
            for master in masters:
                game_archive_masters.setdefault(master, []).append(archive)
        return game_archive_masters

    def selected_clicked(self, name):
        list_obj = self.make_list_obj(name)
        self.setEnabled(False)
        checked = self.get_checked_mods(list_obj.mod_list)
        if not checked:
            if self.redoing_output or self.patch_new_running:
                self.finished_button_action(name, checked)
            else:
                self.setEnabled(True)
            return
        self.confirm = self.create_confirmation(icon=QMessageBox.Icon.Information)
        self.confirm.setWindowTitle(self.tr("Getting estimated disk usage..."))
        self.confirm.setText(self.tr('Getting estimated disk usage...'))
        self.confirm.accepted.connect(lambda: list_obj.confirmed(checked))
        if self.redoing_output or list_obj.skip_key in self.skip_confirmations:
            self.confirm.accept()
            return
        self.confirm.show()
        self.confirm.setEnabled(False)
        if name == 'compact':
            has_others = None
            game_archive_masters = self.game_archive_masters_by_file()
        else: #a plugin's dependents only need patching for ESLifier_Cell_Master if it has a new interior cell
            has_others = {mod for mod in checked if 'new_interior_cell' in list_obj.mod_list.flag_dict.get(mod, ())}
            game_archive_masters = None
        worker = Workers.SizeEstimateWorker(checked, has_others, self.dependency_dictionary, self.get_from_file(FILE_MASTERS_JSON),
                                    game_archive_masters, self.output_folder_path)
        self.start_worker(worker, worker.run, worker.finished_signal,
                          lambda size, free: self.show_estimate(list_obj, checked, size, free))

    def show_estimate(self, list_obj:ListObjBase, checked:list, size:int, free:int):
        free_space = round(free / (1024**3), 3)
        self.confirm.setText(list_obj.confirm_text(size, free_space))
        if size >= free:
            self.confirm.setText(self.tr('Not enough space!\nNeeded space: %1\nSpace left: %2 GBs').replace("%1", str((round(size / 1024**3,3)))).replace("%2", str(free_space)))
            self.confirm.removeButton(QMessageBox.StandardButton.Yes)
        self.confirm.setWindowTitle(list_obj.title.replace("%1", str(len(checked))))
        self.confirm.rejected.connect(lambda:self.setEnabled(True))
        self.confirm.setEnabled(True)

    def compact_confirm_text(self, size, free_space):
        value, unit = size_in_units(size)
        return self.tr(
                "This may generate up to %1 %2 of new files\n"\
                "(this may be inaccurate due to unpacking compressed %0)\n"\
                "and you have %3 GBs of space left.\n"\
                "Are you sure you want to continue?").replace("%0", GAME_ARCHIVE_TYPE
                ).replace("%1", str(value)).replace("%2", unit).replace("%3", str(free_space))

    def eslify_confirm_text(self, size, free_space):
        value, unit = size_in_units(size)
        return self.tr(
                "This may generate up to %0 %1 of new files\n"\
                "and you have %2 GBs of space left.\n"\
                "Are you sure you want to continue?").replace("%0", str(value)
                ).replace("%1", unit).replace("%2", str(free_space))
    
    def start_worker(self, worker:QObject, start_func, finished_signal:pyqtBoundSignal, *on_finished):
        thread = QThread()
        self.running_workers.append((thread, worker))
        worker.moveToThread(thread)
        thread.started.connect(start_func)
        thread.finished.connect(lambda t=thread, w=worker: self.running_workers.remove((t, w)))
        for callback in on_finished:
            finished_signal.connect(callback)
        finished_signal.connect(thread.quit)
        thread.start()

    def compact_confirmed(self, checked:list):
        write_to_file(f'Compacting Plugins [Mod Manager Mode = {_global.mod_manager_mode}]')
        self.confirm.hide()
        self.start_time = timeit.default_timer()
        self.lock_checked_rows(self.list_compact)
        self.log_stream.show()
        worker = Workers.CompactorWorker(checked, self.dependency_dictionary, self.files_to_not_hash)
        self.start_worker(worker, worker.run, worker.finished_signal,
                          lambda: self.finished_button_action('compact', checked))

    def eslify_confirmed(self, checked):
        write_to_file(f'ESL Flagging Plugins [Mod Manager Mode = {_global.mod_manager_mode}]')
        self.confirm.hide()
        self.lock_checked_rows(self.list_eslify)
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
                esl_flagged_data = set(json.load(f))
        except:
            esl_flagged_data = set()
        for file in checked:
            basename = os.path.basename(file)
            esl_flagged_data.add(basename)
        try:
            with open(ESL_FLAGGED_JSON, 'w', encoding='utf-8') as f:
                json.dump(list(esl_flagged_data), f, ensure_ascii=False, indent=4)
        except Exception as e:
            write_error(self.tr('Failed to save esl_flagged.json'))
            write_error(e, True)

    def create_flag_worker(self, files, patch_and_flag = []):
        worker = Workers.FlagWorker(files, self.files_to_not_hash)
        self.start_worker(worker, worker.flag_files, worker.finished_signal,
                          lambda: self.create_patch_and_flag_worker(files, patch_and_flag))

    def create_patch_and_flag_worker(self, files: list[str], patch_and_flag: list[str]):
        if len(patch_and_flag) > 0:
            full_list = files.copy()
            full_list.extend(patch_and_flag)
            worker = Workers.CompactorWorker(patch_and_flag, self.dependency_dictionary, self.files_to_not_hash)
            self.start_worker(worker, worker.run, worker.finished_signal,
                              lambda: self.finished_button_action('eslify', full_list))
        else:
            self.finished_button_action('eslify', files,)
            write_normal(self.tr("File(s) ESL Flagged"))
            if self.redoing_output:
                clear_and_leave_log_open()
            else:
                clear_and_close_log()

    def finished_button_action(self, sender, checked_list):
        if not self.redoing_output:
            self.show_finished_message()
        if sender == 'compact':
            self.remove_finished_mods(self.list_compact, checked_list)
            self.compact_finished()
        elif sender == 'eslify':
            self.remove_finished_mods(self.list_eslify, checked_list)
            self.eslify_finished()

    def show_finished_message(self):
        message = QMessageBox()
        message.setWindowTitle(self.tr("Finished"))
        message.setWindowIcon(QIcon(ESLIFIER_PNG_ICON_PATH))
        if _global.mod_manager_mode == 0: #Manual?
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
                cell_master_message.setWindowIcon(QIcon(ESLIFIER_PNG_ICON_PATH))
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

    def remove_finished_mods(self, mod_list:list_parent_class, checked_list:list[str]):
        if len(checked_list) > 0:
            for mod in checked_list:
                mod_list.flag_dict.pop(mod, None)
            mod_list.create_list()

    def compact_finished(self):
        if self.patch_new_running:
            self.end_flow(hand_back_to_patch_new=True)
            return
        write_normal(self.tr("Total Elapsed Time: %1 Seconds").replace("%1", f"{timeit.default_timer() - self.start_time:.2f}"))
        clear_and_close_log()
        self.end_flow()

    def eslify_finished(self):
        if self.redoing_output and os.path.exists(PREVIOUSLY_COMPACTED_JSON):
            #A rebuild or Patch New also compacts whatever was compacted before, once the ESL flagging is done.
            clear_and_leave_log_open()
            self.list_compact.check_previously_compacted()
            if self.count_checked_rows(self.list_compact) > 0:
                self.compact_selected_clicked()
                return
            if not self.patch_new_running:
                clear_and_close_log()
        else:
            clear_and_close_log()
        self.end_flow(hand_back_to_patch_new=True)

    def count_checked_rows(self, mod_list:list_parent_class):
        return sum(1 for row in range(mod_list.rowCount())
                   if mod_list.item(row, mod_list.MOD_COL).checkState() == Qt.CheckState.Checked)

    def end_flow(self, hand_back_to_patch_new=False):
        was_patch_new = self.patch_new_running
        self.set_false_redoing_output()
        if hand_back_to_patch_new and was_patch_new:
            self.patch_new.finished_rebuilding()
            return
        self.setEnabled(True)
        self.calculate_stats()

    def vortex_error_text(self, state:ReadState):
        if state == ReadState.ERROR_DB_LOCKED_EXTENSION_MISSING:
            return self.tr("Please close Vortex or install the Vortex extension from ESLifier's mod page. " \
                                    "ESLifier cannot read Vortex's database unless Vortex is closed or the extension is installed.")
        elif state == ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE:
            return self.tr("Vortex is open but the Vortex extension is unresponsive. Please close or restart Vortex.")
        elif state == ReadState.ERROR_DB_LOCKED_DEPLOYING:
            return self.tr("Vortex is in the process of deploying your modlist, please wait for it to complete and try again.")
        elif state == ReadState.ERROR_DB_LOCKED_PURGING:
            return self.tr("ESLifier has detected you are currently purging your modlist. You will need to redeploy before running ESLifier.")
        elif state == VortexErrors.HAS_CYCLES:
            return self.tr("ESLifier detected that a cyclic rule is set in Vortex, please correct it first.")
        elif state == VortexErrors.DIFFERENT_MSF_AND_OF_DRIVEs:
            return self.tr("Vortex's Mod Staging Folder and ESLifier's Output Folder must be on the same drive.")
        elif state == VortexErrors.INVALID_MSF:
            return self.tr("Failed to get the Vortex Mod Staging Folder.")
        elif state == VortexErrors.NO_LAST_SSE_PROFILE:
            return self.tr("No last used %0 profile detected.").replace("%0", VERBOSE_GAME_NAME)
        elif state == VortexErrors.NO_BASE_PATH:
            return self.tr("Failed to get the %0 Game folder.").replace("%0", VORTEX_GAME_NAME)
        elif isinstance(state, Exception):
            return self.tr("ESLifier has come across an error while scanning Vortex data: %0").replace("%0", str(state))
        return self.tr("ESLifier has run into an unknown error: %0").replace("%0", str(state))
    
    def check_if_vortex_db_is_readable_and_warn_if_it_is_not(self):
        return_val = VortexDBParser.is_readable()
        if return_val not in (ReadState.SUCCESS_DB, ReadState.SUCCESS_STATE):
            confirm = self.create_confirmation('lightcoral')
            self.scanned = False
            confirm.setText(self.vortex_error_text(return_val))
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
            write_to_file(f'Running Scan [Mod Manager Mode = {_global.mod_manager_mode}]')
            self.log_stream.show()
            self.scanner_worker = Workers.ScannerWorker()
            self.scanner_worker.moveToThread(self.scan_thread)
            self.scan_thread.started.connect(self.scanner_worker.scan_run)
            self.scanner_worker.finished_signal.connect(self.completed_scan)
            self.scanner_worker.finished_signal.connect(self.scan_thread.quit)
            self.scan_thread.start()
        if not self.scanned or "RE-SCAN" in self.skip_confirmations:
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
        confirm.setText(self.vortex_error_text(_global.vortex_error))
        _global.vortex_error = None
        self.scanned = False
        def accept():
            confirm.hide()
        confirm.setStandardButtons(QMessageBox.StandardButton.Ok)
        confirm.accepted.connect(accept)
        confirm.show()
        self.set_false_redoing_output()
        self.setEnabled(True)

    def mo2_error(self):
        clear_and_close_log()
        confirm = self.create_confirmation('lightcoral')
        if _global.mo2_error == MO2Errors.DIFFERENT_MF_AND_OF_DRIVES:
            confirm.setText(self.tr("The MO2 instance's Mods folder and the Output Folder Path must be on the same drive."))
        elif _global.mo2_error == MO2Errors.DIFFERENT_OWF_AND_OF_DRIVES:
            confirm.setText(self.tr("The MO2 instance's Overwrite folder and the Output Folder Path must be on the same drive."))
        elif isinstance(_global.mo2_error, Exception):
            confirm.setText(self.tr("ESLifier has come across an error while reading MO2's ini: %0").replace("%0", str(_global.mo2_error)))
        _global.mo2_error = None
        self.scanned = False
        def accept():
            confirm.hide()
        confirm.setStandardButtons(QMessageBox.StandardButton.Ok)
        confirm.accepted.connect(accept)
        confirm.show()
        self.set_false_redoing_output()
        self.setEnabled(True)
    
    def completed_scan(self, eslifiy_flag_dict, compact_flag_dict, dependency_dictionary):
        if _global.vortex_error != None:
            self.vortex_error()
            return
        if _global.mo2_error != None:
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
        if self.redoing_output:
            self.continue_redo_after_scan()
        else:
            clear_and_close_log()
            self.calculate_stats()
            self.setEnabled(True)

    def continue_redo_after_scan(self):
        if self.patch_new_only_remove:
            self.end_flow(hand_back_to_patch_new=True)
        elif os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON):
            clear_and_leave_log_open()
            self.list_eslify.check_previously_esl_flagged()
            self.eslify_selected_clicked()
        elif os.path.exists(PREVIOUSLY_COMPACTED_JSON):
            self.list_compact.check_previously_compacted()
            self.compact_selected_clicked()
        else:
            clear_and_close_log()
            self.end_flow(hand_back_to_patch_new=True)

    def safe_remove(self, path):
        """Remove a file, tolerating it being missing or locked (e.g. by anti-virus)."""
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            write_to_file(f"Warn: Could not remove {path}: {e}")

    def archive_compacted_and_patched(self):
        if not os.path.exists(COMPACTED_AND_PATCHED_JSON):
            return
        try:
            with open(COMPACTED_AND_PATCHED_JSON, 'r', encoding='utf-8') as f:
                previously_compacted = list(json.load(f).keys())
            with open(PREVIOUSLY_COMPACTED_JSON, 'w', encoding='utf-8') as f:
                json.dump(previously_compacted, f, ensure_ascii=False, indent=4)
            os.remove(COMPACTED_AND_PATCHED_JSON)
        except Exception as e:
            write_error(self.tr("Failed in Compacted and Patched deletion process."))
            write_error(e, True)

    def archive_esl_flagged(self):
        if not os.path.exists(ESL_FLAGGED_JSON):
            return
        try:
            os.replace(ESL_FLAGGED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON)
        except OSError as e:
            write_error(self.tr("Failed to archive the ESL flagged list."))
            write_error(e, True)

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
        except Exception as e:
            write_error(self.tr("Failed to open new_file_hashes.json"))
            write_error(e, True)

    def reset_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.game_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
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
        def enable_and_set_text():
            try:
                yes_button.setEnabled(True)
                yes_button.setText(self.tr("Yes"))
            except:
                pass
        if "TIMERS" in self.skip_confirmations:
            enable_and_set_text()
        else:
            QTimer.singleShot(1000, lambda: update_text("2 " + self.tr("Yes")))
            QTimer.singleShot(2000, lambda: update_text("1 " + self.tr("Yes")))
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
            write_to_file(f'Resetting Output [Mod Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            self.archive_compacted_and_patched()
            self.archive_esl_flagged()
            self.safe_remove(ORIGINAL_FILES_JSON)
            self.safe_remove(MASTER_BYTE_DATA_JSON)
            self.delete_output(self.output_folder_full, files_to_remove)
            self.list_compact.reset_list()
            self.list_eslify.reset_list()
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
        if "OUTPUT-RESET" in self.skip_confirmations:
            confirm.accept()
        else:
            confirm.show()

    def rebuild_output(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        if self.output_folder_full.lower() == self.game_folder_path.lower() or self.output_folder_full.lower() == self.output_folder_path.lower():
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
                "This action will delete %2 files and %3 MBs of data\n"\
                "from the output and re-scan, flag, compact, and patch\n"\
                "all previously output files that fit the current filters.\n"\
                "Anti-Virus can cause output deletion to take 5+ seconds."
            ).replace("%1", self.output_folder_name).replace("%2", str(file_count)).replace("%3", str(calculated_size)))
        def accepted():
            write_to_file(f'Starting Output Rebuild [Mod Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            # Work out what there is to rebuild from BEFORE touching any state files,
            # so that bailing out leaves everything exactly as it was.
            if os.path.exists(COMPACTED_AND_PATCHED_JSON):
                previously_compacted = list(self.get_from_file(COMPACTED_AND_PATCHED_JSON).keys())
            else:
                previously_compacted = self.get_from_file(PREVIOUSLY_COMPACTED_JSON)
            if os.path.exists(ESL_FLAGGED_JSON):
                previously_esl_flagged = self.get_from_file(ESL_FLAGGED_JSON)
            else:
                previously_esl_flagged = self.get_from_file(PREVIOUSLY_ESL_FLAGGED_JSON)
            if len(previously_compacted) == 0 and len(previously_esl_flagged) == 0:
                QMessageBox.warning(None, self.tr("No Existing Output Data"), self.tr("There is no existing output data for ESLifier to use."))
                clear_and_close_log()
                return
            if os.path.exists(NEW_FILE_HASHES_JSON):
                self.update_changed_rel_paths_in_new_files_hashes(changed_rel_paths_to_switch)
            self.archive_compacted_and_patched()
            self.archive_esl_flagged()
            for cache_file in (ORIGINAL_FILES_JSON, WINNING_FILE_HISTORY_DICT_JSON, WINNING_FILES_DICT_JSON, MASTER_BYTE_DATA_JSON):
                self.safe_remove(cache_file)
            self.delete_output(self.output_folder_full, files_to_remove, remove_maps=False)
            self.calculate_stats()
            self.flow = Flow.REBUILD
            self.scan()

        confirm.accepted.connect(accepted)
        confirm.rejected.connect(clear_and_close_log)
        if "OUTPUT-REBUILD" in self.skip_confirmations:
            confirm.accept()
        else:
            confirm.show()

    def reset_game_archive(self):
        confirm = self.create_confirmation('lightcoral')
        confirm_text = self.tr(
                "Are you sure you want to reset the Extracted %0 List?\n"\
                "This will cause the next scan to take significantly longer as the %0 files will\n"\
                "need to be extracted again and irrelevant script files will need to be filtered.\n\n"\
                "This can take a short bit and may freeze the UI\n"\
                "or you can manually delete the \"%1/\" folder\n"\
                "and then click this button.").replace("%0", GAME_ARCHIVE_TYPE).replace("%1", ARCHIVE_EXTRACTED_FOLDER)
        confirm.setText(confirm_text)
        def accepted():
            write_to_file(f'Resetting {GAME_ARCHIVE_TYPE} [Mod Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            if os.path.exists(EXTRACTED_GAME_ARCHIVE_JSON):
                os.remove(EXTRACTED_GAME_ARCHIVE_JSON)
            if os.path.exists(f'{ARCHIVE_EXTRACTED_FOLDER}/'):
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
                delete_subdirectories_threaded(f'{ARCHIVE_EXTRACTED_FOLDER}/')
            self.list_compact.reset_list()
            self.list_eslify.reset_list()
        confirm.accepted.connect(accepted)
        if f"{GAME_ARCHIVE_TYPE}-RESET" in self.skip_confirmations:
            confirm.accept()
        else:
            confirm.show()
        

    def open_output(self):
        output_folder = os.path.join(self.output_folder_path, self.output_folder_name)
        if os.path.exists(output_folder):
            try:
                if os.name == 'nt':
                    os.startfile(output_folder)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', output_folder])
                else:
                    subprocess.Popen(['open', output_folder])
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
        confirm.setWindowIcon(QIcon(ESLIFIER_PNG_ICON_PATH))
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
    
    @staticmethod
    def walk_output_files(folder):
        """Yields (path, size) for every file under folder.
        Uses scandir so that on Windows the size comes from the directory listing rather than one stat call per file.
        Directory symlinks are not followed and files that vanish mid-walk are skipped."""
        stack = [folder]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir():
                                if not entry.is_symlink():
                                    stack.append(entry.path)
                                continue
                            yield entry.path, entry.stat().st_size
                        except OSError:
                            continue
            except OSError:
                continue

    def calculate_existing_output(self):
        size = 0
        files_to_remove = []
        for path, file_size in self.walk_output_files(self.output_folder_full):
            files_to_remove.append(path)
            size += file_size
        return files_to_remove, size, len(files_to_remove)

    def calculate_existing_output_threaded(self, requester):
        self.setEnabled(False)
        self.calculate_requester = requester
        self.total_size = 0
        self.total_file_count = 0
        self.total_progress = 0
        self.files_to_remove = []
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
        self.hasher_worker = Workers.HashWorker(files_to_hash, self.new_file_hashes)
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

    def on_hashing_finished(self, result:dict):
        total_size: int = result["size"]
        total_file_count: int = result["file_count"]
        files_to_remove:list[str] = result["files_to_remove"]
        changed_hashes:list = result["changed_hashes"]
        self.setEnabled(True)
        if result.get("error"):
            write_error(self.tr("Hashing the output failed: %1").replace("%1", result["error"]))
            QMessageBox.warning(None, self.tr("Hashing Failed"),
                                self.tr("Hashing the output failed.\nSee the log for details."))
            return
        self.files_to_not_hash.clear()

        write_normal(self.tr("Hashing for changes complete."))
        write_normal(self.tr("Found %1 changed files.").replace("%1", str(len(changed_hashes))))
        changed_rel_paths_to_switch = []

        if changed_hashes:
            with open(NEW_FILE_HASHES_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.new_file_hashes, f, ensure_ascii=False, indent=4)
            dialog = QDialog()
            dialog.setWindowIcon(QIcon(ESLIFIER_PNG_ICON_PATH))
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
                if rel_path.endswith(('.esp', '.esl', '.esm')):
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
                for file, rel_path in changed_hashes:
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
            shutil.rmtree(FORM_ID_MAPS_FOLDER, ignore_errors=True)
        shutil.rmtree(CELL_IDS_FOLDER, ignore_errors=True)
        self.safe_remove(CELL_MASTER_INFO_JSON)
        self.safe_remove(WINNING_FILE_HISTORY_DICT_JSON)
        self.safe_remove(WINNING_FILES_DICT_JSON)
        try:
            if os.path.exists(output_folder) and 'eslifier' in output_folder.lower():
                #if vortex then we need to restore any .vortex_backup
                if _global.mod_manager_mode == 1 and _global.vortex_restore_backups:
                    gamedata = VortexDBParser.get_section(f"settings###gameMode###discovered###{VORTEX_GAME_NAME}")
                    game_folder_path = os.path.normpath(os.path.join(gamedata.get('path'), "Data"))

                    for file in files_to_remove:
                        rel_path = os.path.relpath(file, output_folder)
                        data_folder_file_path = os.path.join(game_folder_path, rel_path)
                        vortex_backup_path = data_folder_file_path + '.vortex_backup'
                        if os.path.exists(vortex_backup_path):
                            try:
                                if os.path.samefile(file, data_folder_file_path):
                                    self.safe_remove(data_folder_file_path)
                                    shutil.copy(vortex_backup_path, data_folder_file_path)
                            except:
                                pass
                        self.safe_remove(file)
                else:
                    for file in files_to_remove:
                        self.safe_remove(file)
                self.prune_empty_dirs_recursive(output_folder, output_folder)
        finally:
            QApplication.restoreOverrideCursor()

    def calculate_stats(self):
        self.output_folder_full = os.path.join(self.output_folder_path, self.output_folder_name)
        size = 0
        file_count = 0
        for _path, file_size in self.walk_output_files(self.output_folder_full):
            size += file_size
            file_count += 1
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
            write_to_file(f'Starting Patch New Process [Mod Manager Mode = {_global.mod_manager_mode}]')
            confirm.hide()
            self.log_stream.show()
            self.patch_new.scan_and_find(self)
        confirm.accepted.connect(accepted)
        confirm.rejected.connect(lambda: self.setEnabled(True))
        if "PATCHNEW" in self.skip_confirmations:
            confirm.accept()
        else:
            confirm.show()
