import os
import json
import shutil
import threading

from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QSplitter, QFrame, QTextEdit
from PyQt6.QtGui import QIcon

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from create_cell_master import create_new_cell_plugin

class main(QWidget):
    def __init__(self, log_stream, eslifier, COLOR_MODE):
        super().__init__()
        self.skyrim_folder_path = ''
        self.output_folder_path = ''
        self.output_folder_name = ''
        self.modlist_txt_path = ''
        self.plugins_txt_path = ''
        self.overwrite_path = ''
        self.bsab = ''
        self.scanned = False
        self.mo2_mode = False
        self.update_header = True
        self.dependency_dictionary = {}
        self.redoing_output = False
        self.generate_cell_master = False
        self.log_stream = log_stream
        self.eslifier = eslifier
        self.COLOR_MODE = COLOR_MODE
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

        self.button_scan = self.create_button(
            " Scan Mod Files ",
            "This will scan the entire Skyrim Special Edition folder.\n"+
            "Depending on the cell and header settings, what is displayed\n" +
            "in the below lists will change.",
            self.scan
        )

        self.rebuild_output_button = self.create_button(
            " Scan and Rebuild \n ESLifier's Output ",
            "This will delete the existing output folder's contents\n"\
            "then scan and re-patch all curently ESLified mods\n"\
            "that fit the current filters in the settings.",
            self.rebuild_output
        )

        self.reset_output_button = self.create_button(
            " Reset ESLifier's Output ",
            "This will delete the existing output folder's contents and\n"\
            "the data used to patch new files.",
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
        self.compact_thread = QThread()
        self.worker = CompactorWorker(checked, self.dependency_dictionary, self.skyrim_folder_path, self.output_folder_path, 
                                self.output_folder_name, self.overwrite_path, self.update_header, self.mo2_mode, self.bsab, self.generate_cell_master)
        self.worker.moveToThread(self.compact_thread)
        self.compact_thread.started.connect(self.worker.run)
        self.worker.finished_signal.connect(self.compact_thread.quit)
        self.worker.finished_signal.connect(self.compact_thread.deleteLater)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker.finished_signal.connect(
            lambda sender = 'compact', 
            checked_list = checked:
            self.finished_button_action(sender, checked_list,))
        self.compact_thread.start()
        
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
            if not self.redoing_output:
                self.confirm.show()
            else:
                self.confirm.accept()
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
            CFIDs.set_flag(file, self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.overwrite_path, self.mo2_mode)
        print("Flag(s) Changed")
        if not self.redoing_output:
            print("CLEAR")
        self.finished_button_action('eslify', checked)

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
                if self.generate_cell_master:
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
        self.calculate_stats()
        if not self.redoing_output:
            self.setEnabled(True)
        
    def scan(self):
        self.setEnabled(False)
        def run_scan():
            self.log_stream.show()
            self.scan_thread = QThread()
            self.worker = ScannerWorker(self.skyrim_folder_path, self.update_header, self.mo2_mode, self.modlist_txt_path,
                                 self.plugins_txt_path, self.overwrite_path, self.bsab)
            self.worker.moveToThread(self.scan_thread)
            self.scan_thread.started.connect(self.worker.scan_run)
            self.worker.finished_signal.connect(self.completed_scan)
            self.worker.finished_signal.connect(self.scan_thread.quit)
            self.worker.finished_signal.connect(self.scan_thread.deleteLater)
            self.worker.finished_signal.connect(self.worker.deleteLater)
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
        
    def completed_scan(self, flag_dict, dependency_dictionary):
        self.list_eslify.flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' not in f}
        self.list_compact.flag_dict = {p: f for p, f in flag_dict.items() if 'need_compacting' in f}
        self.dependency_dictionary = dependency_dictionary
        print('Populating Tables')
        self.eslifier.update_settings()
        print('Done Scanning')
        if self.redoing_output:
            if os.path.exists('ESLifier_Data/esl_flagged.json'):
                self.list_eslify.check_previously_esl_flagged()
                os.remove('ESLifier_Data/esl_flagged.json')
                self.eslify_selected_clicked()
            if os.path.exists('ESLifier_Data/previously_compacted.json'):
                self.list_compact.check_previously_compacted()
                self.compact_selected_clicked()
            self.redoing_output = False
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
    
    def reset_output(self):
        output_folder = os.path.join(self.output_folder_path, self.output_folder_name)
        if output_folder.lower() == self.skyrim_folder_path.lower() or output_folder.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            print('!Error: Issue occured getting the output folder during output reset.')
            return
        files_to_remove, size, file_count = self.calculate_existing_output(output_folder)
        confirm = self.create_confirmation('lightcoral')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            f"Are you sure you want to delete the output folder {self.output_folder_name}'s contents and all data used to patch new files?\n" \
            f"This action will delete {file_count} files and {calculated_size} MBs of data from the output."
            )
        def accepted():
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
            self.delete_output(output_folder, files_to_remove)
            self.list_compact.flag_dict = {}
            self.list_eslify.flag_dict = {}
            self.list_compact.create()
            self.list_eslify.create()
            self.calculate_stats()

        confirm.accepted.connect(accepted)
        confirm.show()

    def rebuild_output(self):
        output_folder = os.path.join(self.output_folder_path, self.output_folder_name)
        if output_folder.lower() == self.skyrim_folder_path.lower() or output_folder.lower() == self.output_folder_path.lower():
            self.log_stream.show()
            print('!Error: Issue occured getting the output folder during output rebuild.')
            return
        files_to_remove, size, file_count = self.calculate_existing_output(output_folder)
        confirm = self.create_confirmation('skyblue')
        calculated_size = round(size / 1048576, 2)
        confirm.setText(
            f"Are you sure you want to recreate the output folder {self.output_folder_name}?\n" \
            f"This action will delete {file_count} files and {calculated_size} MBs of data from the output and\n" \
            "re-scan, flag, compact, and patch all previously output files that fit the current filters."
            )
        def accepted():
            confirm.hide()
            previously_compacted = []
            previously_esl_flagged = []
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
            if len(previously_compacted) == 0 and len(previously_esl_flagged) == 0:
                QMessageBox.warning(None, "No Existing Output Data", f"There is no existing output data for ESLifier to use.")
                return
            self.delete_output(output_folder, files_to_remove)
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
    
    def create_confirmation(self, color):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))

        confirm.setStyleSheet("""
            QMessageBox {
                background-color: """+color+""";
            }""")
        confirm.setWindowTitle("Confirmation")
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        return confirm

    def calculate_existing_output(self, output_folder):
        size = 0
        file_count = 0
        files_to_remove = []
        for root, _, files in os.walk(output_folder):
            file_count += len(files)
            for file in files:
                full_path = os.path.join(root, file)
                files_to_remove.append(full_path)
                size += os.path.getsize(full_path)
        return files_to_remove, size, file_count
    
    def delete_output(self, output_folder, files_to_remove):
        if os.path.exists('ESLifier_Data/Form_ID_Maps'):
            shutil.rmtree('ESLifier_Data/Form_ID_Maps')
        if os.path.exists('ESLifier_Data/EDIDs'):
            shutil.rmtree('ESLifier_Data/EDIDs')
        if os.path.exists('ESLifier_Data/Cell_IDs'):
            shutil.rmtree('ESLifier_Data/Cell_IDs')
        if os.path.exists('ESLifier_Data/cell_master_info.json'):
            os.remove('ESLifier_Data/cell_master_info.json')
        if os.path.exists(output_folder) and 'eslifier' in output_folder.lower():
            for file in files_to_remove:
                if os.path.exists(file):
                    os.remove(file)
            for item in os.listdir(output_folder):
                item_path = os.path.join(output_folder, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
        self.calculate_stats()

    def calculate_stats(self):
        _, size, file_count=  self.calculate_existing_output(os.path.join(self.output_folder_path, self.output_folder_name))
        if size > 1024 ** 3:
            calculated_size = str(round(size / (1024 ** 3), 3)) + ' GBs'
        elif size > 1048576:
            calculated_size = str(round(size / 1048576, 2)) + ' MBs'
        else:
            calculated_size = str(round(size / 1024, 2)) + ' KBs'
        flaggable_count = 0
        row_count = self.list_eslify.rowCount()
        for row in range(0,row_count):
            if not self.list_eslify.isRowHidden(row):
                flaggable_count += 1
        compactible_count = 0
        row_count = self.list_compact.rowCount()
        for row in range(0, row_count):
            if not self.list_eslify.isRowHidden(row):
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

class ScannerWorker(QObject):
    finished_signal = pyqtSignal(dict, dict)
    def __init__(self, path, update, mo2_mode, modlist_txt_path, plugins_txt_path, overwrite_path, bsab):
        super().__init__()
        self.skyrim_folder_path = path
        self.update_header = update
        self.mo2_mode = mo2_mode
        self.modlist_txt_path = modlist_txt_path
        self.plugins_txt_path = plugins_txt_path
        self.overwrite_path = overwrite_path
        self.bsab = bsab

    def scan_run(self):
        print('Scanning All Files:')
        flag_dict, dependency_dictionary = scanner.scan(self.skyrim_folder_path, self.mo2_mode, self.modlist_txt_path, self.plugins_txt_path,
                                                        self.overwrite_path, self.bsab, self.update_header, True)
        print('Checking if New CELLs are Changed')
        plugins_with_cells = [plugin for plugin, flags in flag_dict.items() if 'new_cell' in flags]
        cell_scanner.scan(plugins_with_cells)
        self.finished_signal.emit(flag_dict, dependency_dictionary)

class CompactorWorker(QObject):
    finished_signal = pyqtSignal()
    def __init__(self, checked, dependency_dictionary, skyrim_folder_path, output_folder_path, output_folder_name, overwrite_path,
                  update_header, mo2_mode, bsab, generate_cell_master):
        super().__init__()
        self.checked = checked
        self.dependency_dictionary = dependency_dictionary
        self.skyrim_folder_path = skyrim_folder_path
        self.output_folder_path = output_folder_path
        self.output_folder_name = output_folder_name
        self.overwrite_path = overwrite_path
        self.update_header = update_header
        self.mo2_mode = mo2_mode
        self.bsab = bsab
        self.create_new_cell_plugin = create_new_cell_plugin()
        self.generate_cell_master = generate_cell_master
        
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
                if 'new_interior_cell' in flags: #'new_cell' in flags:
                    generate_cell_master = True
                    finalize = True
            else:
                generate_cell_master = False
            CFIDs.compact_and_patch(file, dependents, self.skyrim_folder_path, self.output_folder_path, self.output_folder_name,
                                     self.overwrite_path, self.update_header, self.mo2_mode, self.bsab, all_dependents_have_skyrim_esm_as_master, 
                                     self.create_new_cell_plugin, generate_cell_master)
        if finalize:
            self.create_new_cell_plugin.finalize_plugin()
        print("Compacted and Patched")
        print('CLEAR')
        self.finished_signal.emit()
