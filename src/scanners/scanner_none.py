from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
import os
import re
from typing import TYPE_CHECKING
from data_holder import _global, GAME_ARCHIVE_EXTENSION, ARCHIVE_EXTRACTED_FOLDER
if TYPE_CHECKING:
    from scanners.scanner import scanner 

class NoManager():
    scanner: scanner = None
    def get_files_from_game_folder(path: str, plugins_list: list):
        if not os.path.exists(f'{ARCHIVE_EXTRACTED_FOLDER}/'):
            os.makedirs(f'{ARCHIVE_EXTRACTED_FOLDER}/')
        os_sep = os.sep
        path = os.path.normpath(path)
        path_len = len(path)
        loop = 0
        plugin_extensions = ('.esp', '.esm', '.esl')
        game_archive_extension = GAME_ARCHIVE_EXTENSION
        game_archive_list = []
        temp_rel_paths = set()
        ignored_files: set[str] = NoManager.scanner.ignored_files
        game_archive_blacklist: set[str] = NoManager.scanner.game_archive_blacklist
        all_files: list[str] = NoManager.scanner.all_files
        plugins: list[str] = _global.plugins
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        for root, _, files in os.walk(path):
            #string manipulation for relative paths instead of os.path.relpath per file
            rel_root_lower = root[path_len:].lstrip(os_sep).lower()
            is_root_level = root == path
            NoManager.scanner.file_count += len(files)
            if loop == 50: #prevent spamming logger and slowing down the program
                loop = 0
                write_remove(1, gathered_str + str(NoManager.scanner.file_count))
            else:
                loop += 1
            for file in files:
                file_lower = file.lower()
                if file_lower in ignored_files:
                    continue
                all_files.append(os.path.join(root, file))
                temp_rel_paths.add(os.path.join(rel_root_lower, file_lower))
                if is_root_level:
                    if file_lower.endswith(plugin_extensions):
                        plugins.append(os.path.join(root, file))
                    elif file_lower.endswith(game_archive_extension) and file_lower not in game_archive_blacklist:
                        # remove " - Main.ext", " - Textures#.ext", ".ext" + lower()
                        game_archive_lower = re.sub(r' - (main\.|textures\d*\.).*$', '', file_lower).removesuffix(game_archive_extension)
                        game_archive_list.append([game_archive_lower, os.path.join(root, file)])

        NoManager.scanner.extract_scripts_and_seq_from_game_archive(game_archive_list, plugins_list)
        
        #Get files that were extracted from archives
        loop = 0
        mod_folder = os.path.normpath(os.path.join(os.getcwd(), ARCHIVE_EXTRACTED_FOLDER))
        mod_folder_len = len(mod_folder)
        for root, _, files in os.walk(mod_folder):
            rel_root_lower = root[mod_folder_len:].lstrip(os_sep).lower()
            for file in files:
                NoManager.scanner.file_count += 1
                if loop == 75: #prevent spamming logger and slowing down the program
                    loop = 0
                    write_remove(1, gathered_str + str(NoManager.scanner.file_count))
                else:
                    loop += 1
                file_lower = file.lower()
                if file_lower in ignored_files:
                    continue
                full_path = os.path.join(root, file)
                # a loose file in the game folder overrides the one extracted from an archive
                if os.path.join(rel_root_lower, file_lower) not in temp_rel_paths:
                    all_files.append(full_path)
                elif os.path.exists(full_path):
                    os.remove(full_path)
