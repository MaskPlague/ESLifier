import os
import json
import threading
import hashlib

from .ESLifier_qualification_checker import qualification_checker as light_check

class check_files():    
    def scan_files(self, scan_esms, eslifier_folder, new_header, compare_hashes, detect_conflict_changes, only_plugins, plugin_files_list, eslifier) -> tuple[bool, dict, dict, list, list]:
        self.flag_dict = {}
        self.hash_mismatches = []
        self._problems = [0]
        self._finished = False
        self.any_esl = False
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(500)
        self.flag_dict.clear()
        self.hash_mismatches.clear()
        self.any_esl = False
        self.eslifier = eslifier

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
            thread = threading.Thread(target=self.plugin_scanner, args=(chunk, new_header, scan_esms))
            threads.append(thread)
            thread.start()

        original_plugins_hash_map = []
        if compare_hashes:
            original_plugins_path = os.path.join(eslifier_folder, 'ESLifier_Data/original_files.json')
            if os.path.exists(original_plugins_path):
                with self.semaphore:
                    with open(original_plugins_path, 'r', encoding='utf-8') as f:
                        original_plugins_dict: dict = json.load(f)
                if only_plugins:
                    original_plugins_hash_map = [values for key, values in original_plugins_dict.items() if key.lower().endswith(('.esp', '.esl', '.esm'))]
                else:
                    original_plugins_hash_map = [values for key, values in original_plugins_dict.items()]

        self.conflict_changes = []
        if detect_conflict_changes:
            winning_file_history_dict_path = os.path.join(eslifier_folder, "ESLifier_Data/winning_file_history_dict.json")
            if os.path.exists(winning_file_history_dict_path):
                with self.semaphore:
                    with open(winning_file_history_dict_path, 'r', encoding='utf-8') as f:
                        winning_file_history_dict: dict[str, list[str]] = json.load(f)
                for file, old_winner in winning_file_history_dict.items():
                    if not 'bsa_extracted_eslifier_scan' == old_winner:
                        thread = threading.Thread(target=self.detect_conflict_change, args=(old_winner, file))
                        threads.append(thread)
                        thread.start()

        for thread in threads:
            thread.join()

        threads.clear()

        if compare_hashes and os.path.exists(original_plugins_path):
            for plugin, original_hash in original_plugins_hash_map:
                thread = threading.Thread(target=self.compare_previous_hash_to_current, args=(plugin, original_hash))
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()

        needs_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' not in f}
        needs_compacting_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' in f}
        return ((self.any_esl or len(self.hash_mismatches) > 0 or len(self.conflict_changes) > 0), 
                needs_flag_dict, needs_compacting_flag_dict, self.hash_mismatches, self.conflict_changes)
    
    def compare_previous_hash_to_current(self, file, original_hash):
        if os.path.exists(file):
            with self.semaphore:
                with open(file, 'rb') as f:
                    data = f.read()
            if hashlib.sha256(data).hexdigest() != original_hash:
                with self.lock:
                    self.hash_mismatches.append("Hash Mismatch: " + file)
        else:
            with self.lock:
                self.hash_mismatches.append("Missing: " + file)
    
    def detect_conflict_change(self, old_winner, file):
        origins: list = self.eslifier._organizer.getFileOrigins(file)
        if len(origins) == 1:
            if old_winner != origins[0]:
                self.conflict_changes.append(file)
        else:
            if origins[-1] != old_winner:
                self.conflict_changes.append(file)

    def plugin_scanner(self, plugins, new_header, scan_esms):
        flag_dict = {}
        for plugin in plugins:
            esl_allowed, need_compacting, new_cell, interior_cell, new_wrld = self.qualification_check(plugin, new_header, scan_esms)
            if esl_allowed == True:
                self.any_esl = True
                basename = os.path.basename(plugin)
                with self.lock:
                    if esl_allowed:
                        flag_dict[basename] = []
                        if need_compacting:
                            flag_dict[basename].append('need_compacting')
                        if new_cell:
                            flag_dict[basename].append('new_cell')
                            if interior_cell:
                                flag_dict[basename].append('new_interior_cell')
                        if new_wrld:
                            flag_dict[basename].append('new_wrld')
        with self.lock:
            for key, value in flag_dict.items():
                if key not in self.flag_dict:
                    self.flag_dict[key] = value
    
    @staticmethod
    def qualification_check(plugin, new_header, scan_esms):
        return light_check().qualification_check(plugin, new_header, scan_esms)
