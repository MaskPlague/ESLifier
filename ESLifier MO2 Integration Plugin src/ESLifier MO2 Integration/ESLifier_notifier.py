import os
import json
import threading
import hashlib

try:
    from PyQt6.QtCore import QCoreApplication
except ImportError:
    from PyQt5.QtCore import QCoreApplication #type: ignore

from .ESLifier_qualification_checker import qualification_checker as light_check
from .ESLifier_cell_changed_scanner import cell_scanner

class check_files():    
    def scan_files(self, scan_esms, eslifier_data_folder, new_header, compare_hashes, detect_conflict_changes,
                   only_plugins, plugin_files_list, organizer, game_mode="SSE", all_plugin_files=None):
        self.flag_dict = {}
        self.hash_mismatches = []
        self.lost_to_overwrite = []
        self._problems = [0]
        self._finished = False
        self.any_esl = False
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(500)
        self.flag_dict.clear()
        self.hash_mismatches.clear()
        self.any_esl = False
        self._organizer = organizer
        self.running = True
        self.game_mode = game_mode
        light_check.configure(game_mode, plugin_files_list if all_plugin_files is None else all_plugin_files)

        if len(plugin_files_list) > 1000:
            split = 5
        elif len(plugin_files_list) > 500:
            split = 2
        else:
            split = 1

        chunk_size = len(plugin_files_list) // split
        chunks = [plugin_files_list[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(plugin_files_list[(split) * chunk_size:])

        threads: list[threading.Thread] = []
        for chunk in chunks:
            if not self.running:
                break
            thread = threading.Thread(target=self.plugin_scanner, args=(chunk, new_header, scan_esms))
            threads.append(thread)
            thread.start()

        original_plugins_hash_map = []
        if compare_hashes and self.running:
            original_plugins_path = os.path.join(eslifier_data_folder, 'original_files.json')
            if os.path.exists(original_plugins_path):
                with self.semaphore:
                    try:
                        with open(original_plugins_path, 'r', encoding='utf-8') as f:
                            original_plugins_dict: dict = json.load(f)
                    except Exception as e:
                        return False, {}, {}, [], [], []
                if only_plugins:
                    original_plugins_hash_map = [values for key, values in original_plugins_dict.items() if key.lower().endswith(('.esp', '.esl', '.esm'))]
                else:
                    original_plugins_hash_map = [values for key, values in original_plugins_dict.items()]

        self.conflict_changes = []
        if detect_conflict_changes and self.running:
            winning_file_history_dict_path = os.path.join(eslifier_data_folder, "winning_file_history_dict.json")
            mod_list: list[str] = self._organizer.modList().allModsByProfilePriority()
            mod_list.append('overwrite_eslifier_scan')
            if os.path.exists(winning_file_history_dict_path):
                with self.semaphore:
                    try:
                        with open(winning_file_history_dict_path, 'r', encoding='utf-8') as f:
                            winning_file_history_dict: dict[str, list[str]] = json.load(f)
                    except Exception as e:
                        return False, {}, {}, [], [], []
                for file, old_winner in winning_file_history_dict.items():
                    if self.running:
                        if not 'bsa_extracted_eslifier_scan' == old_winner:
                            self.detect_conflict_change(old_winner, file, mod_list)
                    else:
                        break

        if compare_hashes and self.running and os.path.exists(original_plugins_path) :
            for plugin, original_hash in original_plugins_hash_map:
                if self.running:
                    self.compare_previous_hash_to_current(plugin, original_hash)
                else:
                    break

        for thread in threads:
            thread.join()

        if self.running:
            self.flag_new_cells_changed_by_dependents()

        needs_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' not in f}
        needs_compacting_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' in f}
        if self.running:
            return ((self.any_esl or len(self.hash_mismatches) > 0 or len(self.conflict_changes) > 0), 
                needs_flag_dict, needs_compacting_flag_dict, self.hash_mismatches, self.conflict_changes, self.lost_to_overwrite)
        else:
            return False, {}, {}, [], [], []

    def flag_new_cells_changed_by_dependents(self):
        plugins_with_cells = [plugin for plugin, flags in self.flag_dict.items() if 'new_cell' in flags]
        changed = cell_scanner.scan(plugins_with_cells, light_check.new_cell_ids, light_check.dependent_dict,
                                    self.game_mode, lambda: self.running)
        for plugin in changed:
            if plugin in self.flag_dict:
                self.flag_dict[plugin].append('cell_changed')

    def stop(self):
        self.running = False
    
    def compare_previous_hash_to_current(self, file, original_hash):
        if os.path.exists(file):
            with self.semaphore:
                if self.running:
                    with open(file, 'rb') as f:
                        data = f.read()
            if self.running and hashlib.sha256(data).hexdigest() != original_hash:
                self.hash_mismatches.append(QCoreApplication.translate("ESLifier", "Hash Mismatch: ") + file)
        else:
            self.hash_mismatches.append(QCoreApplication.translate("ESLifier", "Missing: ") + file)
    
    def detect_conflict_change(self, old_winner, file, mod_list: list):
        try:
            origins_unformated: list = self._organizer.getFileOrigins(file)
        except:
            return
        origins = [origin if origin != 'Overwrite' else 'overwrite_eslifier_scan' for origin in origins_unformated]
        if len(origins) == 1:
            if old_winner != origins[0]:
                self.conflict_changes.append(file)
        elif len(origins) > 0:
            sorted_origins = sorted(origins, key=lambda x: mod_list.index(x))
            if 'eslifier' in sorted_origins[-1].lower():
                if sorted_origins[-1] == 'overwrite_eslifier_scan':
                    self.lost_to_overwrite.append(file)
                elif sorted_origins[-2] != old_winner:
                    self.conflict_changes.append(file)
            else:
                if sorted_origins[-1] != old_winner:
                    self.conflict_changes.append(file)

    def plugin_scanner(self, plugins, new_header, scan_esms):
        flag_dict = {}
        is_sse_mode = self.game_mode == "SSE"
        for plugin in plugins:
            ret_val = self.qualification_check(plugin, new_header, scan_esms)
            if ret_val[0] == True:
                self.any_esl = True
                need_compacting, new_cell = ret_val[1], ret_val[2]
                basename = os.path.basename(plugin)
                with self.lock:
                    flag_dict[basename] = []
                    if need_compacting:
                        flag_dict[basename].append('need_compacting')
                    if new_cell:
                        flag_dict[basename].append('new_cell')
                        if is_sse_mode and ret_val[3]:
                            flag_dict[basename].append('new_interior_cell')
                        if self.is_maxed_masters(plugin, basename):
                            flag_dict[basename].append('maxed_masters')
                    if is_sse_mode:
                        if ret_val[4]:
                            flag_dict[basename].append('new_wrld')
                        if ret_val[5]:
                            flag_dict[basename].append('new_wthr')
                    elif ret_val[3]:
                        flag_dict[basename].append('has_previs_precombines')
        with self.lock:
            for key, value in flag_dict.items():
                if key not in self.flag_dict:
                    self.flag_dict[key] = value
    
    @staticmethod
    def is_maxed_masters(plugin, basename) -> bool:
        maxed = light_check.maxed_masters
        if plugin in maxed:
            return True
        return any(dependent in maxed for dependent in light_check.dependent_dict.get(basename.lower(), ()))

    @staticmethod
    def qualification_check(plugin, new_header, scan_esms):
        return light_check().qualification_check(plugin, new_header, scan_esms)
