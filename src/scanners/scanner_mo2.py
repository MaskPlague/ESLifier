from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
from data_holder import _global, GAME_ARCHIVE_EXTENSION, ARCHIVE_EXTRACTED_FOLDER
import os
import configparser
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from scanners.scanner import scanner 

class MO2Errors(Enum):
    DIFFERENT_MF_AND_OF_DRIVES = 0
    DIFFERENT_OWF_AND_OF_DRIVES = 1

class MO2():
    scanner: scanner = None
    def get_modlist() -> tuple[list[str], set[str]]:
        load_order = []
        try:
            with open(_global.mo2_modlist_txt_path, 'r', encoding='utf-8') as f:
                load_order = f.readlines()
                f.close()
        except Exception as e:
            write_error(QCoreApplication.translate("scanner", "Failed to get modlist at ") + _global.mo2_modlist_txt_path)
            write_error(e, True)

        enabled_mods = []
        for line in load_order:
            if line.startswith(('+','*')) and not line.strip().endswith('_separator'):
                enabled_mods.append(line[1:].strip())
        
        enabled_mods.append('archive_extracted_eslifier_scan')
        enabled_mods.reverse()
        enabled_mods.append('overwrite_eslifier_scan')

        to_remove = []
        for i in range(len(load_order)):
            load_order[i] = load_order[i][1:].strip()
            if load_order[i].endswith('_separator'):
                to_remove.append(load_order[i])
        
        for mod in to_remove:
            load_order.remove(mod)
        if load_order[0].startswith('# This file was'):
            load_order.pop(0)
        load_order.append('archive_extracted_eslifier_scan')
        load_order.reverse()
        load_order.append('overwrite_eslifier_scan')
        return load_order, set(enabled_mods)

    def get_winning_files(plugins_list: list) -> tuple[list, list]:
        os_sep = os.sep
        load_order:list[str]
        load_order, enabled_mods = MO2.get_modlist()
        mods_folder = os.path.normpath(_global.mo2_mods_folder)
        overwrite_path = os.path.normpath(_global.mo2_overwrite_path)
        mod_folder_level = len(mods_folder.split(os_sep))
        overwrite_level = len(overwrite_path.split(os_sep)) - 1
        mod_files: dict[str, list[str]]
        plugin_names: list[str]
        cases: dict[str, str]
        mod_files, plugin_names, cases = MO2.get_files_from_mods(mods_folder, enabled_mods, plugins_list, overwrite_path, load_order)
        winning_files: list[list[str, str]] = []
        file_count = 0
        loop = 0
        cwd = os.getcwd()
        winning_files_processed_str = QCoreApplication.translate("scanner", "Winning Files Processed: ")
        write_remove(1, winning_files_processed_str)
        output_file_name = MO2.scanner.output_file_name
        for file, mods in mod_files.items():
            file_count += 1
            if loop == 500:
                loop = 0
                write_remove(1, winning_files_processed_str + str(file_count))
            else:
                loop += 1
            if len(mods) == 1:
                overwrite = False
                mod = mods[0]
                if mod == 'archive_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, ARCHIVE_EXTRACTED_FOLDER, cases[file])
                elif mod == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                    overwrite = True
                else:
                    file_path = os.path.join(mods_folder, mod, cases[file])
                winning_files.append([file_path, overwrite])
                if mod != output_file_name:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mod, file_path)
            else:
                mods_sorted = sorted(mods, key=lambda mod: load_order.index(mod))
                overwrite = False
                if mods_sorted[-1] == 'archive_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, ARCHIVE_EXTRACTED_FOLDER, cases[file])
                elif mods_sorted[-1] == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                    overwrite = True
                else:
                    file_path = os.path.join(mods_folder, mods_sorted[-1], cases[file])
                winning_files.append([file_path, overwrite])
                if mods_sorted[-1] != output_file_name:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-1], file_path)
                else:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-2], os.path.join(mods_folder, mods_sorted[-2], cases[file]))
        plugin_extensions = ('.esp', '.esl', '.esm')
        plugins = []
        plugin_names_lowered = [plugin.lower() for plugin in plugin_names]
        for file, overwrite in winning_files:
            file_level = len(file.split(os_sep))
            if overwrite:
                level = overwrite_level
            else:
                level = mod_folder_level
            if file_level == level + 2 and file.lower().endswith(plugin_extensions) and not file.endswith("ESLifier_Cell_Master.esm"):
                plugin = os.path.join(os.path.dirname(file), plugin_names[plugin_names_lowered.index(os.path.basename(file.lower()))])
                plugins.append(plugin)
        return_list = [winning_file for winning_file, _ in winning_files]
        return return_list, plugins

    def get_files_from_mods(mods_folder: str, enabled_mods: set, plugins_list: list, overwrite_path: str, load_order:list[str]) -> tuple[dict, list, dict]:
        if not os.path.exists(f'{ARCHIVE_EXTRACTED_FOLDER}/'):
            os.makedirs(f'{ARCHIVE_EXTRACTED_FOLDER}/')
        os_sep = os.sep
        mod_files: dict[str, list[str]] = {}
        cases: dict[str, str] = {}
        game_archive_list = []
        game_archive_dict_temp: dict[str, list[str]] = {}
        game_archive_file_name_dict: dict[str, str] = {}
        game_archive_extension = GAME_ARCHIVE_EXTENSION
        plugin_extensions = ('.esp', '.esl', '.esm')
        game_archive_blacklist: set[str] = MO2.scanner.game_archive_blacklist
        ignored_files: set[str] = MO2.scanner.ignored_files
        plugin_names = set()
        loop = 0
        file_count = 0
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        #Get file from MO2's mods folder
        for mod_folder in os.listdir(mods_folder):
            mod_path = os.path.join(mods_folder, mod_folder)
            if mod_folder in enabled_mods and os.path.isdir(mod_path):
                mod_path_len = len(mod_path)
                for root, dirs, files in os.walk(mod_path):
                    #prune directories that are mod organizer hidden
                    dirs[:] = [d for d in dirs if '.mohidden' not in d]

                    #string manipulation for relative paths instead of os.path.relpath per file
                    rel_root = root[mod_path_len:].lstrip(os_sep)
                    
                    file_count += len(files)
                    if loop == 50: #prevent spamming logger and slowing down the program
                        loop = 0
                        write_remove(1, gathered_str + str(file_count))
                    else:
                        loop += 1
                    # is root level
                    if root == mod_path:
                        for file in files:
                            file_lower = file.lower()
                            if file_lower in ignored_files or file_lower == 'meta.ini' or file_lower.endswith('.mohidden'):
                                continue
                            # Get the relative file path
                            cased = os.path.join(rel_root, file)
                            relative_path = cased.lower()
                            # Track the file paths by mod
                            existing_mod_files = mod_files.get(relative_path)
                            if not existing_mod_files:
                                mod_files[relative_path] = [mod_folder]
                                cases[relative_path] = cased
                            else:
                                existing_mod_files.append(mod_folder)
                            if file_lower.endswith(plugin_extensions):
                                plugin_names.add(file)
                            elif file_lower.endswith(game_archive_extension) and file_lower not in game_archive_blacklist:
                                game_archive_file = file[:-4]
                                game_archive_lower = game_archive_file.lower().partition(' - textures')[0]
                                game_archive_lower = game_archive_lower.partition(' - main')[0]
                                if not file_lower in game_archive_dict_temp:
                                    game_archive_dict_temp[file_lower] = []
                                    game_archive_file_name_dict[file_lower] = game_archive_lower
                                game_archive_dict_temp[file_lower].append(mod_folder)
                    else: #not root level
                        for file in files:
                            file_lower = file.lower()
                            if file_lower in ignored_files or file_lower.endswith('.mohidden'):
                                continue
                            # Get the relative file path
                            cased = os.path.join(rel_root, file)
                            relative_path = cased.lower()
                            # Track the file paths by mod
                            existing_mod_files = mod_files.get(relative_path)
                            if not existing_mod_files:
                                mod_files[relative_path] = [mod_folder]
                                cases[relative_path] = cased
                            else:
                                existing_mod_files.append(mod_folder)

        #Get files from MO2's overwrite folder
        if os.path.exists(overwrite_path) and not overwrite_path == '.':
            overwrite_path = os.path.normpath(overwrite_path)
            overwrite_path_len = len(overwrite_path)
            for root, dirs, files in os.walk(overwrite_path):
                #prune directories that are mod organizer hidden
                dirs[:] = [d for d in dirs if '.mohidden' not in d]

                rel_root = root[overwrite_path_len:].lstrip(os_sep)

                file_count += len(files)
                if loop == 50: #prevent spamming stdout and slowing down the program
                    loop = 0
                    write_remove(1, gathered_str + str(file_count))
                else:
                    loop += 1
                if root == overwrite_path:
                    for file in files:
                        file_lower = file.lower()
                        if file_lower in ignored_files or file_lower.endswith('.mohidden'):
                            continue
                        cased = os.path.join(rel_root, file)
                        relative_path = cased.lower()
                        # Track the file paths by mod
                        existing_mod_files = mod_files.get(relative_path)
                        if not existing_mod_files:
                            mod_files[relative_path] = ['overwrite_eslifier_scan']
                            cases[relative_path] = cased
                        else:
                            existing_mod_files.append('overwrite_eslifier_scan')
                        if file_lower.endswith(plugin_extensions):
                            if file not in plugin_names:
                                plugin_names.add(file)
                        elif file_lower.endswith(game_archive_extension) and file_lower not in game_archive_blacklist:
                            game_archive_file = file[:-4]
                            game_archive_lower = game_archive_file.lower().partition(' - textures')[0]
                            game_archive_lower = game_archive_lower.partition(' - main')[0]
                            if not file_lower in game_archive_dict_temp:
                                game_archive_dict_temp[file_lower] = []
                                game_archive_file_name_dict[file_lower] = game_archive_lower
                            game_archive_dict_temp[file_lower].append('overwrite_eslifier_scan')
                else:
                    for file in files:
                        file_lower = file.lower()
                        if file_lower in ignored_files or file_lower.endswith('.mohidden'):
                            continue
                        cased = os.path.join(rel_root, file)
                        relative_path = cased.lower()
                        # Track the file paths by mod
                        existing_mod_files = mod_files.get(relative_path)
                        if not existing_mod_files:
                            mod_files[relative_path] = ['overwrite_eslifier_scan']
                            cases[relative_path] = cased
                        else:
                            existing_mod_files.append('overwrite_eslifier_scan')
        else:
            write_to_file('Overwrite folder not found.\n')
        #BSA list is expacted to be like: [[mod_name, full_path], [mod_name2, full_path2]] where mod_name is (mod_name).esp without ext 
        # for sorting by plugin during extraction. mod_name is obtained from (mod_name).bsa
        game_archive_list = []
        for relative_path, mods in game_archive_dict_temp.items():
            if len(mods) == 1:
                mod = mods[0]
                if mod == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, relative_path)
                else:
                    file_path = os.path.join(mods_folder, mod, relative_path)
                game_archive_list.append([game_archive_file_name_dict[relative_path], file_path])
            else:
                mods_sorted = sorted(mods, key=lambda mod: load_order.index(mod))
                if mods_sorted[-1] == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, relative_path)
                else:
                    file_path = os.path.join(mods_folder, mods_sorted[-1], relative_path)
                game_archive_list.append([game_archive_file_name_dict[relative_path], file_path])
        
        MO2.scanner.extract_scripts_and_seq_from_game_archive(game_archive_list, plugins_list)

        mod_folder = os.path.join(os.getcwd(), f'{ARCHIVE_EXTRACTED_FOLDER}/')
        #Get files that were extracted from archives
        archive_extracted_folder_len = len(mod_folder)
        for root, dirs, files in os.walk(mod_folder):
            rel_root = root[archive_extracted_folder_len:].lstrip(os_sep)
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                write_remove(1, gathered_str + str(file_count))
            else:
                loop += 1
            for file in files:
                if file.lower() in ignored_files:
                    continue
                # Get the relative file path
                cased = os.path.join(rel_root, file)
                relative_path = cased.lower()
                # Track the file paths by mod
                existing_mod_files = mod_files.get(relative_path)
                if not existing_mod_files:
                    mod_files[relative_path] = ['archive_extracted_eslifier_scan']
                    cases[relative_path] = cased
                else:
                    existing_mod_files.append('archive_extracted_eslifier_scan')

        return mod_files, list(plugin_names), cases

    def get_instance_paths():
        try:
            mo2_base_dir = os.path.normpath(_global.mo2_base_path)
            file = os.path.join(mo2_base_dir, "ModOrganizer.ini")

            ini = configparser.ConfigParser(interpolation=None)
            
            ini.read(file, encoding='utf-8')

            if ini.has_option('Settings', 'base_directory'):
                mo2_base_dir = os.path.normpath(ini.get('Settings', 'base_directory'))

            if ini.has_option('Settings', 'mod_directory'):
                _global.mo2_mods_folder = os.path.normpath(ini.get('Settings', 'mod_directory'))
                if _global.mo2_mods_folder.startswith("%BASE_DIR%"):
                    _global.mo2_mods_folder = os.path.normpath(_global.mo2_mods_folder.replace("%BASE_DIR%", mo2_base_dir))
            else:
                _global.mo2_mods_folder = os.path.normpath(os.path.join(mo2_base_dir, 'mods'))

            mods_folder_drive = os.path.splitdrive(_global.mo2_mods_folder)[0].lower()
            output_folder_drive = os.path.splitdrive(_global.output_folder_path)[0].lower()
            #Output and mo2 mods folder must be on same drive
            if mods_folder_drive != output_folder_drive:
                write_to_file("Mods Folder and Output folder must be on the same drive.")
                write_to_file(f"MFD: {mods_folder_drive}, OFD: {output_folder_drive}")
                write_to_file(f"MF: {_global.mo2_mods_folder}, OF: {_global.output_folder_path}")
                _global.mo2_error = MO2Errors.DIFFERENT_MF_AND_OF_DRIVES
                return False

            if ini.has_option('Settings', 'overwrite_directory'):
                _global.mo2_overwrite_path = os.path.normpath(ini.get('Settings', 'overwrite_directory'))
                if _global.mo2_overwrite_path.startswith("%BASE_DIR%"):
                    _global.mo2_overwrite_path = os.path.normpath(_global.mo2_overwrite_path.replace("%BASE_DIR%", mo2_base_dir))
            else:
                _global.mo2_overwrite_path = os.path.normpath(os.path.join(mo2_base_dir, 'overwrite'))

            overwrite_folder_drive = os.path.splitdrive(_global.mo2_overwrite_path)[0].lower()
            #Output and mo2 overwrite folder must be on same drive
            if overwrite_folder_drive != output_folder_drive:
                write_to_file("Overwrite Folder and Output folder must be on the same drive.")
                write_to_file(f"OVFD: {overwrite_folder_drive}, OFD: {output_folder_drive}")
                write_to_file(f"OVF: {_global.mo2_overwrite_path}, OF: {_global.output_folder_path}")
                _global.mo2_error = MO2Errors.DIFFERENT_OWF_AND_OF_DRIVES
                return False

            profile = os.path.join(_global.mo2_profiles_dir, _global.mo2_profile)
            _global.plugins_txt_path = os.path.normpath(os.path.join(profile, 'plugins.txt'))
            _global.mo2_modlist_txt_path = os.path.normpath(os.path.join(profile, 'modlist.txt'))
            _global.update_mo2_vars()
            return True
        except Exception as e:
            _global.mo2_error = e
            return False

