
import os
import json
import shutil
import threading
import hashlib

from PyQt6.QtCore import QObject, pyqtSignal

from scanners.scanner import scanner
from compact_form_ids import CFIDs
from scanners.cell_changed_scanner import cell_scanner
from create_cell_master import create_new_cell_plugin
from main.utils import estimate_output_size
from data_holder import (_global, GAME_MODE, FILE_MASTERS_JSON, FLAG_DICTIONARY_JSON, MASTER_BYTE_DATA_JSON, MISSING_GAME_AS_MASTER_JSON,
                         ORIGINAL_FILES_JSON, WINNING_FILE_HISTORY_DICT_JSON, WINNING_FILES_DICT_JSON)

from log_stream import write_error, write_normal, write_patching, write_progress, clear_and_leave_log_open, write_main_progress
from patchers.file_defined_patcher_conditions import user_and_master_conditions_class

class SizeEstimateWorker(QObject):
    finished_signal = pyqtSignal(object, object) #(estimated bytes, free bytes) - object because they can exceed 2 GB

    def __init__(self, mods, has_others, dependency_dictionary, file_masters, game_archive_masters, output_folder_path):
        super().__init__()
        self.mods = mods
        self.has_others = has_others
        self.dependency_dictionary = dependency_dictionary
        self.file_masters = file_masters
        self.game_archive_masters = game_archive_masters
        self.output_folder_path = output_folder_path

    def run(self):
        size = estimate_output_size(self.mods, self.dependency_dictionary, self.file_masters,
                                    self.game_archive_masters, self.has_others)
        self.finished_signal.emit(size, shutil.disk_usage(self.output_folder_path).free)

class ScannerWorker(QObject):
    finished_signal = pyqtSignal(dict, dict, dict)
    def __init__(self):
        super().__init__()

    def scan_run(self):
        write_main_progress(5, -1, self.tr('Scanning All Files:'))
        flag_dict, dependency_dictionary = scanner.scan(True)
        if _global.vortex_error != None or _global.mo2_error != None:
            self.finished_signal.emit({}, {}, {})
            return
        flag_dict = {p: set(f) for p, f in flag_dict.items()}
        if GAME_MODE == "SSE":
            write_main_progress(95, 0, self.tr('Checking if New CELLs are Changed'))
        elif GAME_MODE == "FO4":
            write_main_progress(95, 0, self.tr('Checking if New CELLs have PreVis/PreCombined'))
        plugins_with_cells = [plugin for plugin, flags in flag_dict.items() if 'new_cell' in flags]
        cell_scanner.scan(plugins_with_cells)
        eslify_flag_dict = {p: f for p, f in flag_dict.items() if 'esl_flaggable' in f}
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
                with open(MISSING_GAME_AS_MASTER_JSON, 'r', encoding='utf-8') as f:
                    missing_game_esm = json.load(f)
            except:
                missing_game_esm = {}
        with open(FLAG_DICTIONARY_JSON, 'r', encoding='utf-8') as f:
            flag_dict = json.load(f)
        if self.generate_cell_master:
            self.create_new_cell_plugin.generate(_global.output_folder_joined_path)
        finalize = False
        original_files: dict = self.get_from_file(ORIGINAL_FILES_JSON)
        winning_files_dict: dict = self.get_from_file(WINNING_FILES_DICT_JSON)
        master_byte_data: dict = self.get_from_file(MASTER_BYTE_DATA_JSON)
        files_to_patch: dict = self.get_from_file(FILE_MASTERS_JSON)
        game_archive_masters = []
        for value in _global.game_archive_dict.values():
            game_archive_masters.extend(value)

        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(self.create_new_cell_plugin, original_files, winning_files_dict, {}, {}, master_byte_data, game_archive_masters,
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
            all_dependents_have_game_esm_as_master = True
            if self.update_header:
                for plugin_without_game_esm_as_master, master_0 in missing_game_esm.items():
                    if plugin_without_game_esm_as_master in dependents and os.path.basename(file) == master_0:
                        all_dependents_have_game_esm_as_master = False
                        break
            else:
                all_dependents_have_game_esm_as_master = True
            if self.generate_cell_master:
                flags = flag_dict[file]
                generate_cell_master = False
                if 'new_cell' in flags and not 'maxed_masters' in flags:
                    generate_cell_master = True
                    finalize = True
            else:
                generate_cell_master = False
            cfids.compact_and_patch(
                            file, dependents, all_dependents_have_game_esm_as_master, 
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
        super().__init__()
        self.files = files
        self.files_to_not_hash = files_to_not_hash
    
    def flag_files(self):
        original_files = self.get_from_file(ORIGINAL_FILES_JSON)
        winning_files_dict = self.get_from_file(WINNING_FILES_DICT_JSON)
        winning_file_history_dict = {}
        additional_file_patcher_conditions = user_and_master_conditions_class()
        cfids = CFIDs(None, original_files, winning_files_dict, winning_file_history_dict, {}, {}, [], additional_file_patcher_conditions)
        if _global.hash_output:
            write_main_progress(5, 0, self.tr("Hashing any existing files for changes..."))
            cfids.hash_output_files(set(), True)
        for file in self.files:
            original_files, winning_file_history_dict = cfids.set_flag(file)
        if _global.hash_output:
            write_main_progress(85, 0, self.tr('Hashing output files for checking later changes...'))
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
        chunk_size = max(1, -(-self.to_hash_len // thread_count)) #ceiling division so there are never more than thread_count chunks

        chunks = [self.files[i:i + chunk_size] for i in range(0, self.to_hash_len, chunk_size)]
        
        self.results = []
        self.errors: list[Exception] = []
        self.hash_progress = 0
        
        threads: list[threading.Thread] = []
        for chunk in chunks:
            thread = threading.Thread(target=self.hash_chunk, args=(chunk,))
            threads.append(thread)
            thread.start()
            
        for thread in threads: thread.join()

        if self.errors:
            self.finished.emit({
                "size": 0,
                "file_count": 0,
                "files_to_remove": [],
                "changed_hashes": [],
                "error": str(self.errors[0])
            })
            return
            
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

    def hash_chunk(self, files):
        try:
            self.hash_files(files)
        except Exception as e:
            write_error(self.tr("Failed while hashing output files."))
            write_error(e, True)
            with self.lock:
                self.errors.append(e)

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
                local_files_to_remove.append(file)
                try:
                    local_size += os.path.getsize(file)
                except OSError: pass
                local_file_count += 1
                continue
                
            try:
                sha256 = hashlib.sha256()
                file_size = 0
                with open(file, 'rb') as f:
                    while block := f.read(1048576):
                        sha256.update(block)
                        file_size += len(block)
                sha256_hash = sha256.hexdigest()
            except Exception:
                local_progress_batch += 1
                continue
                
            rel_path = get_rel_path(file).lower()
            old_hash, changed = self.new_file_hashes.get(rel_path, (None, False))
            
            if old_hash is None or (old_hash == sha256_hash and not changed):
                local_files_to_remove.append(file)
                local_size += file_size
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