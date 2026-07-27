from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
import os
from typing import TYPE_CHECKING
from data_holder import _global
if TYPE_CHECKING:
    from scanner import scanner 

class NoManager():
    scanner: scanner = None
    def get_files_from_skyrim_folder(path: str, plugins_list: list):
        if not os.path.exists('bsa_extracted/'):
            os.makedirs('bsa_extracted/')
        path = os.path.normpath(path)
        path_level = len(path.split(os.sep))
        loop = 0
        plugin_extensions = ('.esp', '.esm', '.esl')
        bsa_list = []
        temp_rel_paths = set()
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        for root, _, files in os.walk(path):
            root_level = len(root.split(os.sep))
            NoManager.scanner.file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                write_remove(1, gathered_str + str(NoManager.scanner.file_count))
            else:
                loop += 1
            for file in files:
                file_lower = file.lower()
                if file_lower in NoManager.scanner.ignored_files:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path).lower()
                NoManager.scanner.all_files.append(full_path)
                temp_rel_paths.add(rel_path)
                if path_level == root_level and file_lower.endswith(plugin_extensions):
                    _global.plugins.append(full_path)
                if path_level == root_level and file_lower.endswith('.bsa') and file_lower not in NoManager.scanner.bsa_blacklist:
                    file = file[:-4]
                    if ' - textures' in file_lower:
                        index = file_lower.index(' - textures')
                        file = file[:index]
                    bsa_list.append([file.lower(), full_path])

        NoManager.scanner.extract_scripts_and_seq_from_bsa(bsa_list, plugins_list)
        
        cwd = os.getcwd()
        mod_folder = os.path.join(cwd, 'bsa_extracted/')
        loop = 0
        for root, _, files in os.walk('bsa_extracted/'):
            for file in files:
                NoManager.scanner.file_count += 1
                if loop == 75: #prevent spamming stdout and slowing down the program
                    loop = 0
                    write_remove(1, gathered_str + str(NoManager.scanner.file_count))
                else:
                    loop += 1
                if file.lower() in NoManager.scanner.ignored_files:
                    continue
                full_path = os.path.normpath(os.path.join(cwd, root, file))
                relative_path = os.path.relpath(full_path, mod_folder).lower()
                if relative_path not in temp_rel_paths:
                    NoManager.scanner.all_files.append(full_path)
                else:
                    if os.path.exists(full_path):
                        os.remove(full_path)