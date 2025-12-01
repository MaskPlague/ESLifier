import json
import os
import hashlib
import threading

from PyQt6.QtCore import pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QIcon

from scanner import scanner
from dependency_getter import dependecy_getter
from compact_form_ids import CFIDs
from cell_changed_scanner import cell_scanner
from file_defined_patcher_conditions import user_and_master_conditions_class

class patch_new():
    def scan_and_find(self, settings: dict[str, str|bool], main_parent):
        self.main_parent = main_parent
        if (not os.path.exists(os.path.normpath('ESLifier_Data/compacted_and_patched.json')) 
            and not os.path.exists(os.path.normpath('ESLifier_Data/esl_flagged.json'))):
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
            self.main_parent.setEnabled(True)
            print('CLEAR')
            return
        if not os.path.exists(os.path.normpath('ESLifier_data/master_byte_data.json')):
            self.output_not_new_warning = QMessageBox()
            self.output_not_new_warning.setIcon(QMessageBox.Icon.Information)
            self.output_not_new_warning.setWindowTitle("Output is from outdated build.")
            self.output_not_new_warning.setText("ESLifier cannot find the file master_byte_data.json\n"+
                                                "in ESLifier_Data/, this is likely because the current\n"+
                                                "ESLifier output was made on a version older than v0.12.0.\n"+
                                                "This button needs an output made from v0.12.0+.")
            self.output_not_new_warning.setWindowIcon(QIcon(":/images/ESLifier.png"))
            self.output_not_new_warning.addButton(QMessageBox.StandardButton.Ok)
            self.output_not_new_warning.show()
            self.main_parent.setEnabled(True)
            print('CLEAR')
            return
        self.settings: dict = settings
        self.skyrim_folder_path: str = settings.get('skyrim_folder_path', '')
        self.output_folder_path = settings.get('output_folder_path', '')
        self.output_folder_name = settings.get('output_folder_name', 'ESLifier Compactor Output')
        self.modlist_txt_path: str = settings.get('mo2_modlist_txt_path', '')
        self.plugins_txt_path: str = settings.get('plugins_txt_path', '')
        self.overwrite_path: str = settings.get('overwrite_path', '')
        self.mo2_mode: bool = settings.get('mo2_mode', False)
        self.update_header: bool = settings.get('update_header', False)
        self.generate_cell_master = settings.get('generate_cell_master', True)

        self.patch_new_scan_thread = QThread()
        self.scanner_worker = PatchNewScannerWorker(settings.copy(), self.main_parent)
        self.scanner_worker.moveToThread(self.patch_new_scan_thread)
        self.patch_new_scan_thread.started.connect(self.scanner_worker.detect_changes)
        self.scanner_worker.finished_signal.connect(self.completed_scan)
        self.scanner_worker.finished_signal.connect(self.patch_new_scan_thread.quit)
        self.scanner_worker.delete_confirmation_signal.connect(self.create_delete_message)
        self.patch_new_scan_thread.start()

    def create_delete_message(self, text, files_to_delete, winning_file_history_dict, only_remove, compacted_and_patched):
        self.delete_message = QMessageBox()
        self.delete_message.setWindowTitle(f'Delete {len(files_to_delete)} files?')
        self.delete_message.setText(text)
        self.delete_message.addButton(QMessageBox.StandardButton.Abort)
        self.delete_message.addButton(QMessageBox.StandardButton.Ok)
        def accept():
            self.delete_message.hide()
            self.scanner_worker.delete_files(files_to_delete, winning_file_history_dict, only_remove, compacted_and_patched)
            return
        def reject():
            self.delete_message.hide()
            self.patch_new_scan_thread.quit()
            self.main_parent.setEnabled(True)
            self.main_parent.calculate_stats()
            print('User canceled Patch New file deletion, aborting.')
            print('CLEAR')
            return
        self.delete_message.accepted.connect(accept)
        self.delete_message.rejected.connect(reject)
        self.delete_message.show()
    
    def completed_scan(self, mod_list, new_dependencies, new_files, hash_mismatch_num, file_conflict_num, skse_warnings):
        self.mod_list = mod_list
        self.new_dependencies = new_dependencies
        self.new_files = new_files
        self.hash_mismatch_num = hash_mismatch_num
        self.file_conflict_num = file_conflict_num
        if len(skse_warnings) > 0:
            text = ('The following mods have been compacted by ESLifier and have a dll that references their name.'+
                    'These mods are likely referenced by a Form ID look up which means if the Form ID has been changed'+
                    'by ESLifier, the SKSE dll may not function correctly. Mods:')
            for mod, dlls in skse_warnings:
                text += '\nMod: ' + mod
                text += '\n    DLLs: '
                for i, dll in enumerate(dlls):
                    text += dll
                    if i < len(dlls) - 1:
                        text += '\n\t'
            QMessageBox.warning(None, "Compacted mod referenced in SKSE dll.", text)
        if len(self.mod_list) > 0 and len(self.new_dependencies) > 0 :
            print('\nChecking if New CELLs are Changed...')
            cell_scanner.scan_new_dependents(self.mod_list, self.new_dependencies)
        if len(self.mod_list) == 0:
            print("CLEAR")
            self.create_completion_message(0)
            self.main_parent.setEnabled(True)
        else:
            self.patch_new_plugins_and_files()

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

    def patch_new_plugins_and_files(self):
        self.patch_new_thread = QThread()
        self.patch_worker = PatchNewWorker(self.mod_list, self.new_dependencies, self.new_files, self.settings.copy())
        self.patch_worker.moveToThread(self.patch_new_thread)
        self.patch_new_thread.started.connect(self.patch_worker.patch_new_files)
        self.patch_worker.finished_signal.connect(self.finished_patching)
        self.patch_worker.finished_signal.connect(self.patch_new_thread.quit)
        self.patch_new_thread.start()

    def finished_patching(self, new_file_num):
        print('Finished Patching New or Changed Dependencies and Files')
        print('CLEAR')
        self.create_completion_message(new_file_num)
        self.main_parent.setEnabled(True)

    def create_completion_message(self, new_file_num):
        self.patch_new_complete_message = QMessageBox()
        self.patch_new_complete_message.setWindowTitle("Patch New Done")
        self.patch_new_complete_message.setIcon(QMessageBox.Icon.Information)
        self.patch_new_complete_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
        if new_file_num > 0:
            text = f'{new_file_num} new files that needed patching have been patched.'
        else:
            text = 'No new files that need patching have been found.'
            if self.mo2_mode and self.file_conflict_num > 0:
                text += '\n   (or they were patched due to a conflict change)'
        if self.hash_mismatch_num > 0:
            text += f'\n{self.hash_mismatch_num} files had hash mismatches and were corrected.'
        else:
            text += '\nNo files with a hash mismatched were found.'
        if self.mo2_mode:
            if self.file_conflict_num > 0:
                text += f'\n{self.file_conflict_num} files had winning conflicts change and were corrected.'
            else:
                text += '\nNo files with a winning conflict change were found.'
        self.patch_new_complete_message.setText(text)
        self.patch_new_complete_message.addButton(QMessageBox.StandardButton.Ok)
        self.patch_new_complete_message.accepted.connect(self.patch_new_complete_message.hide)
        self.patch_new_complete_message.show()
        self.main_parent.calculate_stats()

    def finished_rebuilding(self):
        self.scanner_worker.detect_new_files()

class PatchNewScannerWorker(QObject):
    finished_signal = pyqtSignal(list, dict, dict, int, int, list)
    delete_confirmation_signal = pyqtSignal(str, list, dict, bool, dict)
    def __init__(self, settings:dict[str, str|bool], main_parent):
        super().__init__()
        self.skyrim_folder_path: str = settings.get('skyrim_folder_path', '')
        self.overwrite_path: str = settings.get('overwrite_path', '')
        self.output_folder: str = settings.get('output_folder_name', 'ESLifier Compactor Output')
        self.output_path: str = os.path.join(settings.get('output_folder_path', ''), self.output_folder)
        self.mo2_mode: bool = settings.get('mo2_mode', False)
        self.hash_mismatches = []
        self.conflict_changes = []
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(1000)
        self.main_parent = main_parent

    def detect_changes(self):
        print('Scanning All Files:')
        scanner.scan(False)
        print('Getting Dependencies')
        dependecy_getter.scan()
        try:
            if os.path.exists('ESLifier_Data/compacted_and_patched.json'):
                with open("ESLifier_Data/compacted_and_patched.json", 'r', encoding='utf-8') as f:
                    compacted_and_patched: dict[str, list[str]] = json.load(f)
            else:
                compacted_and_patched: dict[str, list[str]] = {}
            if os.path.exists('ESLifier_Data/esl_flagged.json'):
                with open("ESLifier_Data/esl_flagged.json", 'r', encoding='utf-8') as f:
                    esl_flagged: list[str] = json.load(f)
            else:
                esl_flagged: list[str] = {}
            with open("ESLifier_Data/file_masters.json", 'r', encoding='utf-8') as f:
                file_masters: dict[str, list[str]] = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json", 'r', encoding='utf-8') as f: 
                dependencies: dict[str, list[str]] = json.load(f)
            if os.path.exists("ESLifier_Data/winning_file_history_dict.json"):
                with open("ESLifier_Data/winning_file_history_dict.json", 'r', encoding='utf-8') as f:
                    winning_file_history_dict: dict[str, list[str]] = json.load(f)
            else:
                winning_file_history_dict: dict[str, list[str]] = {}
            if os.path.exists("ESLifier_Data/winning_files_dict.json"):
                with open("ESLifier_Data/winning_files_dict.json", 'r', encoding='utf-8') as f:
                    winning_files_dict: dict[str, (str, list[str])] = json.load(f)
            else:
                winning_files_dict: dict[str, (str, list[str])] = {}
        except Exception as e:
            print("!Error: Issue reading an ESLifier_Data file.")
            print(e)
            self.finished_signal.emit({},{},{},0,0,[])

        self.hash_mismatches.clear()
        print('Detecting Hash Changes...')
        if os.path.exists('ESLifier_Data/original_files.json'):
            threads: list[threading.Thread] = []
            with open('ESLifier_Data/original_files.json', 'r', encoding='utf-8') as f:
                original_plugins_dict: dict = json.load(f)
                original_plugins_hash_map = [values for key, values in original_plugins_dict.items()]
            for file, original_hash in original_plugins_hash_map:
                thread = threading.Thread(target=self.compare_previous_hash_to_current, args=(file, original_hash))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

        print(f'Found {len(self.hash_mismatches)} Hash changes.')

        self.conflict_changes.clear()
        if self.mo2_mode:
            print('Detecting Conflict Changes...')
            if len(winning_file_history_dict) > 0:
                for rel_path, prev_mod in winning_file_history_dict.copy().items():
                    (mod_name, full_path) = winning_files_dict.get(rel_path, (None, None))
                    if mod_name != None and mod_name != prev_mod:
                        self.conflict_changes.append((rel_path, full_path, 'c'))
                    elif mod_name == None:
                        self.conflict_changes.append((rel_path, os.path.join(self.output_path, rel_path), 'c'))
            
            print(f'Found {len(self.conflict_changes)} Conflict Changes.')

        if len(self.hash_mismatches) > 0 or len(self.conflict_changes) > 0:
            actual_cases_output_files = {}
            for files in file_masters.values():
                for file in files:
                    rel_path = self.get_rel_path(file, self.skyrim_folder_path)
                    if rel_path.lower() not in actual_cases_output_files:
                        actual_cases_output_files[rel_path.lower()] = os.path.join(self.output_path, rel_path)

            for deps in dependencies.values():
                for dep in deps:
                    rel_path = self.get_rel_path(dep, self.skyrim_folder_path)
                    if rel_path.lower() not in actual_cases_output_files:
                        actual_cases_output_files[rel_path.lower()] = os.path.join(self.output_path, rel_path)
        
        with open('ESLifier_Data/previously_compacted.json', 'w', encoding='utf-8') as f:
            previously_compacted = [key for key in compacted_and_patched.keys()]
            json.dump(previously_compacted, f, ensure_ascii=False, indent=4)

        files_to_remove = []
        temp_list = self.conflict_changes.copy()
        if len(self.hash_mismatches) > 0:
            temp_rel_paths = [rel_path for rel_path, x, y in self.conflict_changes]
            for rel_path, full_path in self.hash_mismatches:
                if rel_path not in temp_rel_paths:
                    temp_rel_paths.append(rel_path)
                    temp_list.append((rel_path.lower(), full_path, 'h'))
        only_remove = True
        if len(temp_list) > 0:
            for rel_path, full_path, source in temp_list:
                added_to_list = False
                for compacted, patched in compacted_and_patched.copy().items():
                    if rel_path == compacted.lower():
                        output_cased = actual_cases_output_files.get(rel_path, None)
                        if output_cased != None and output_cased not in files_to_remove:
                            files_to_remove.append(output_cased)
                            added_to_list = True
                            if source == 'h':
                                only_remove = False
                            for patched_rel_path in patched:
                                patched_output_cased = actual_cases_output_files.get(patched_rel_path, None)
                                if patched_output_cased != None and patched_output_cased not in files_to_remove:
                                    files_to_remove.append(patched_output_cased)
                                    only_remove = False
                        elif output_cased == None and full_path not in files_to_remove and full_path.startswith(self.output_path):
                            files_to_remove.append(full_path)
                            added_to_list = True
                            if source == 'h':
                                only_remove = False
                            for patched_rel_path in patched:
                                patched_output_cased = actual_cases_output_files.get(patched_rel_path, None)
                                if patched_output_cased != None and patched_output_cased not in files_to_remove:
                                    files_to_remove.append(patched_output_cased)
                                    only_remove = False
                        compacted_and_patched.pop(compacted)

                    if rel_path in patched:
                        output_cased = actual_cases_output_files.get(rel_path, None)
                        if output_cased != None and output_cased not in files_to_remove:
                            files_to_remove.append(output_cased)
                            only_remove = False
                            added_to_list = True
                        elif output_cased == None and full_path not in files_to_remove and full_path.startswith(self.output_path):
                            files_to_remove.append(full_path)
                            added_to_list = True
                        compacted_and_patched[compacted].remove(rel_path)
                
                for flagged in esl_flagged:
                    if rel_path == flagged.lower():
                        output_cased = actual_cases_output_files.get(rel_path, None)
                        if output_cased != None and output_cased not in files_to_remove:
                            files_to_remove.append(output_cased)
                            added_to_list = True
                
                if not added_to_list and full_path.startswith(self.output_path):
                    files_to_remove.append(full_path)
        if len(files_to_remove) > 0:
            print("CLEAR ALT")
            self.delete_and_patch_changed(files_to_remove, only_remove, winning_file_history_dict, compacted_and_patched)
        else:
            self.detect_new_files()
    
    def delete_and_patch_changed(self, files_to_remove: list[str], only_remove: bool,
                                  winning_file_history_dict: dict[str, list[str]], compacted_and_patched: dict):
        print(f"Confirming files that need deleting...")
        output_folder_lowered = self.output_folder.lower()
        counter = 0
        plugins_to_delete = []
        files_that_exist_to_delete = []
        for file in files_to_remove:
            if os.path.exists(file) and output_folder_lowered in file.lower():
                counter += 1
                files_that_exist_to_delete.append(file)
                if file.lower().endswith(('.esp','.esm','.esl')):
                    plugins_to_delete.append(os.path.basename(file))

        if counter > 0:
            number_of_plugins_to_delete = len(plugins_to_delete)
            text = f"Continuing will delete {counter} files from ESLifier's output"
            if number_of_plugins_to_delete > 0:
                text +=  f" of which {number_of_plugins_to_delete} are game plugins. "
            else:
                text += ". "
            text += ("This action is destructive and cannot be undone. If you have made any edits to files in the ESLifier "\
                    "Output it is not advised to do so nor to continue.\nAre you sure you want to continue?")

            if number_of_plugins_to_delete > 0:
                if number_of_plugins_to_delete > 10:
                    text += '\nSome plugins that will be deleted include:'
                else:
                    text += '\nThe plugins that will be deleted are:'
                count = 0
                for plugin in plugins_to_delete:
                    if count < 10:
                        text += f'\n - {plugin}'
                        count += 1
                    else:
                        break
                if number_of_plugins_to_delete > 10:
                    text += f"\nand {number_of_plugins_to_delete - count} more..."
            self.delete_confirmation_signal.emit(text, files_that_exist_to_delete, winning_file_history_dict, only_remove, compacted_and_patched)
        else:
            self.delete_files(files_that_exist_to_delete, winning_file_history_dict, only_remove, compacted_and_patched)

    def delete_files(self, files_to_remove: list[str], winning_file_history_dict: dict[str, list[str]], only_remove: bool, compacted_and_patched: dict):
        with open('ESLifier_Data/compacted_and_patched.json', 'w', encoding='utf-8') as f:
            json.dump(compacted_and_patched, f, ensure_ascii=False, indent=4)
        with open("ESLifier_Data/original_files.json", 'r', encoding='utf-8') as f:
            original_files: dict[str, list[str]] = json.load(f)
        deleted_count = 0
        for file in files_to_remove:
            if os.path.exists(file):
                os.remove(file)
                deleted_count += 1
            cased_rel_path = self.get_rel_path(file, self.skyrim_folder_path)
            if cased_rel_path.lower() in winning_file_history_dict:
                winning_file_history_dict.pop(cased_rel_path.lower())
            if cased_rel_path.lower() in original_files:
                original_files.pop(cased_rel_path.lower())
        with open("ESLifier_Data/winning_file_history_dict.json", 'w', encoding='utf-8') as f:
            json.dump(winning_file_history_dict, f, ensure_ascii=False, indent=4)
        with open("ESLifier_Data/original_files.json", 'w', encoding='utf-8') as f:
            json.dump(original_files, f, ensure_ascii=False, indent=4)
        print('CLEAR ALT')
        self.main_parent.redoing_output = True
        self.main_parent.patch_new_running = True
        self.main_parent.patch_new_only_remove = only_remove
        self.main_parent.scan()

    def detect_new_files(self):
        if not os.path.exists("ESLifier_Data/compacted_and_patched.json"):
            self.finished_signal.emit({},{},{},0,0,[])
            return
        print('\nGetting New Dependencies and Files')
        try:
            with open("ESLifier_Data/compacted_and_patched.json", 'r', encoding='utf-8') as f:
                compacted_and_patched: dict[str, list[str]] = json.load(f)
            with open("ESLifier_Data/file_masters.json", 'r', encoding='utf-8') as f:
                file_masters: dict[str, list[str]] = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json", 'r', encoding='utf-8') as f: 
                dependencies: dict[str, list[str]] = json.load(f)
            with open("ESLifier_Data/dll_dict.json", 'r', encoding='utf-8') as f:
                dll_dict: dict[str, list[str]] = json.load(f)
        except Exception as e:
            print(f'!Error: Failed to find a required dictionary.')
            print(e)
            self.finished_signal.emit([],{},{},0,0,[])
            return

        new_files: dict[str, list[str]] = {}
        new_dependencies: dict[str, list[str]] = {}
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
        skse_warnings = []
        for mod, dlls in dll_dict.items():
            if mod in compacted_lowered and mod not in mod_list_lowered:
                skse_warnings.append((mod, [os.path.basename(dll) for dll in dlls]))
        self.finished_signal.emit(mod_list, new_dependencies, new_files, len(self.hash_mismatches), len(self.conflict_changes), skse_warnings)
        return

    def compare_previous_hash_to_current(self, file, original_hash):
        if os.path.exists(file):
            with self.semaphore:
                with open(file, 'rb') as f:
                    data = f.read()
            if hashlib.sha256(data).hexdigest() != original_hash:
                with self.lock:
                    self.hash_mismatches.append((self.get_rel_path(file, self.skyrim_folder_path), file))

    def get_rel_path(self, file: str, skyrim_folder_path: str):
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

class PatchNewWorker(QObject):
    finished_signal = pyqtSignal(int)
    def __init__(self, files: list, dependencies_dictionary: dict, file_dictionary: dict, settings: dict):
        super().__init__()
        self.files = files
        self.dependencies_dictionary = dependencies_dictionary
        self.file_dictionary = file_dictionary
        self.skyrim_folder_path: str = settings.get('skyrim_folder_path', '')
        self.output_folder_path = settings.get('output_folder_path', '')
        self.output_folder_name = settings.get('output_folder_name', 'ESLifier Compactor Output')
        self.overwrite_path: str = os.path.normpath(settings.get('overwrite_path', ''))
        self.mo2_mode: bool = settings.get('mo2_mode', False)
        self.update_header: bool = settings.get('update_header', False)
        self.generate_cell_master = settings.get('generate_cell_master', True)
        self.persistent_ids = settings.get('persistent_ids', True)
        self.free_non_existent = settings.get('free_non_existent', False)

    def patch_new_files(self):
        total = len(self.files)
        count = 0
        print("CLEAR ALT")
        original_files: dict = self.get_from_file('ESLifier_Data/original_files.json')
        winning_files_dict: dict = self.get_from_file('ESLifier_Data/winning_files_dict.json')
        master_byte_data: dict = self.get_from_file('ESLifier_Data/master_byte_data.json')
        winning_file_history_dict = {}
        compacted_and_patched = {}
        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(self.skyrim_folder_path, self.output_folder_path, self.output_folder_name, self.overwrite_path, 
                      self.update_header, self.mo2_mode, None, original_files, winning_files_dict, winning_file_history_dict, 
                      compacted_and_patched, master_byte_data, None, None, self.persistent_ids, self.free_non_existent, additional_file_patcher_conditions)
        for file in self.files:
            count +=1
            percent = round((count/total)*100,1)
            print(f'{percent}% Patching: {count}/{total}')
            dependents = []
            if file in self.dependencies_dictionary:
                dependents = self.dependencies_dictionary[file]
            cfids.patch_new(file, dependents, self.file_dictionary, self.generate_cell_master)
        all_patched = []
        for files in self.dependencies_dictionary.values():
            for file in files:
                if file not in all_patched:
                    all_patched.append(file)
        for files in self.file_dictionary.values():
            for file in files:
                if file not in all_patched:
                    all_patched.append(file)
        cfids.save_data()
        self.finished_signal.emit(len(all_patched))
        return
    
    def dump_compacted_and_patched(self, file, dictionary: dict[str, list[str]]):
        data: dict[str, list[str]] = self.get_from_file(file)
        for key, value in dictionary.items():
            if key not in data:
                data[key] = []
            for item in value:
                if item.lower() not in data[key]:
                    data[key].append(item.lower())
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to {file}')
            print(e)
    
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

    


        

        

        