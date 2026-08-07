from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
from data_holder import _global
import os
import configparser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scanner import scanner 

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
        
        enabled_mods.append('bsa_extracted_eslifier_scan')
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
        load_order.append('bsa_extracted_eslifier_scan')
        load_order.reverse()
        load_order.append('overwrite_eslifier_scan')
        return load_order, set(enabled_mods)

    def get_winning_files(plugins_list: list) -> tuple[list, list]:
        load_order:list[str]
        load_order, enabled_mods = MO2.get_modlist()
        mods_folder = os.path.normpath(_global.mo2_mods_folder)
        overwrite_path = os.path.normpath(_global.mo2_overwrite_path)
        mod_folder_level = len(mods_folder.split(os.sep))
        overwrite_level = len(overwrite_path.split(os.sep)) - 1
        mod_files: dict[str, list[str]]
        plugin_names: list[str]
        cases: dict[str, str]
        mod_files, plugin_names, cases = MO2.get_files_from_mods(mods_folder, enabled_mods, plugins_list, overwrite_path)
        winning_files: list[list[str, str]] = []
        file_count = 0
        loop = 0
        cwd = os.getcwd()
        winning_files_processed_str = QCoreApplication.translate("scanner", "Winning Files Processed: ")
        write_remove(1, winning_files_processed_str)
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
                if mod == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[file])
                elif mod == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                    overwrite = True
                else:
                    file_path = os.path.join(mods_folder, mod, cases[file])
                winning_files.append([file_path, overwrite])
                if mod != MO2.scanner.output_file_name:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mod, file_path)
            else:
                mods_sorted = sorted(mods, key=lambda mod: load_order.index(mod))
                overwrite = False
                if mods_sorted[-1] == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[file])
                elif mods_sorted[-1] == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                    overwrite = True
                else:
                    file_path = os.path.join(mods_folder, mods_sorted[-1], cases[file])
                winning_files.append([file_path, overwrite])
                if mods_sorted[-1] != MO2.scanner.output_file_name:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-1], file_path)
                else:
                    MO2.scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-2], os.path.join(mods_folder, mods_sorted[-2], cases[file]))
        plugin_extensions = ('.esp', '.esl', '.esm')
        plugins = []
        plugin_names_lowered = [plugin.lower() for plugin in plugin_names]
        for file, overwrite in winning_files:
            file_level = len(file.split(os.sep))
            if overwrite:
                level = overwrite_level
            else:
                level = mod_folder_level
            if file_level == level + 2 and file.lower().endswith(plugin_extensions) and not file.endswith("ESLifier_Cell_Master.esm"):
                plugin = os.path.join(os.path.dirname(file), plugin_names[plugin_names_lowered.index(os.path.basename(file.lower()))])
                plugins.append(plugin)
        return_list = [winning_file for winning_file, _ in winning_files]
        return return_list, plugins

    def get_files_from_mods(mods_folder: str, enabled_mods: set, plugins_list: list, overwrite_path: str) -> tuple[dict, list, dict]:
        if not os.path.exists('bsa_extracted/'):
            os.makedirs('bsa_extracted/')
        mod_files: dict[str, list[str]] = {}
        cases_of_files: dict[str, str] = {}
        bsa_list = []
        plugin_extensions = ('.esp', '.esl', '.esm')
        plugin_names = []
        loop = 0
        file_count = 0
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        #Get file from MO2's mods folder
        for mod_folder in os.listdir(mods_folder):
            mod_path = os.path.join(mods_folder, mod_folder)
            mod_folder_level = len(mod_path.split(os.sep))
            if os.path.isdir(mod_path) and mod_folder in enabled_mods:
                for root, dirs, files in os.walk(mod_path):
                    file_count += len(files)
                    root_level = len(root.split(os.sep))
                    if loop == 50: #prevent spamming stdout and slowing down the program
                        loop = 0
                        write_remove(1, gathered_str + str(file_count))
                    else:
                        loop += 1
                    for file in files:
                        if file != 'meta.ini':
                            file_lower = file.lower()
                            if file_lower in MO2.scanner.ignored_files:
                                continue
                            # Get the relative file path
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, mods_folder)
                            part = relative_path.split(os.sep)
                            cased = os.path.join(*part[1:])
                            relative_path = cased.lower()
                            if '.mohidden' in relative_path: #if the file or containing folder is mod organizer hidden, skip it
                                continue
                            # Track the file paths by mod
                            if relative_path not in mod_files:
                                mod_files[relative_path] = []
                                cases_of_files[relative_path] = cased
                            mod_files[relative_path].append(mod_folder)
                            if file_lower.endswith(plugin_extensions):
                                plugin_names.append(file)
                            elif root_level == mod_folder_level and file_lower.endswith('.bsa') and file_lower not in MO2.scanner.bsa_blacklist:
                                file = file[:-4]
                                if ' - textures' in file_lower:
                                    index = file.lower().index(' - textures')
                                    file = file[:index]
                                bsa_list.append([file.lower(), full_path])

        #Get files from MO2's overwrite folder
        if os.path.exists(overwrite_path):
            for root, dirs, files in os.walk(overwrite_path):
                file_count += len(files)
                if loop == 50: #prevent spamming stdout and slowing down the program
                    loop = 0
                    write_remove(1, gathered_str + str(file_count))
                else:
                    loop += 1
                for file in files:
                    file_lower = file.lower()
                    if file_lower in MO2.scanner.ignored_files:
                        continue
                    full_path = os.path.join(root, file)
                    cased = os.path.relpath(full_path, overwrite_path)
                    relative_path = cased.lower()
                    if '.mohidden' in relative_path:
                        continue
                    if relative_path not in mod_files:
                        mod_files[relative_path] = []
                        cases_of_files[relative_path] = cased
                    mod_files[relative_path].append('overwrite_eslifier_scan')
                    if file_lower.endswith(plugin_extensions):
                        plugin_names.append(file)
                    elif file_lower.endswith('.bsa') and file_lower not in MO2.scanner.bsa_blacklist:
                        file = file[:-4]
                        if ' - textures' in file_lower:
                            index = file_lower.index(' - textures')
                            file = file[:index]
                        bsa_list.append([file.lower(), full_path])
        else:
            write_to_file('Overwrite folder not found.\n')

        MO2.scanner.extract_scripts_and_seq_from_bsa(bsa_list, plugins_list)

        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')
        #Get files that were extracted from BSA
        for root, dirs, files in os.walk('bsa_extracted/'):
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                write_remove(1, gathered_str + str(file_count))
            else:
                loop += 1
            for file in files:
                if file.lower() in MO2.scanner.ignored_files:
                    continue
                # Get the relative file path
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder)
                # Track the file paths by mod
                if relative_path not in mod_files:
                    mod_files[relative_path] = []
                    cases_of_files[relative_path] = relative_path
                mod_files[relative_path].append('bsa_extracted_eslifier_scan')

        return mod_files, plugin_names, cases_of_files

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

            mods_folder_drive, _ = os.path.splitdrive(_global.mo2_mods_folder)
            output_folder_drive, _ = os.path.splitdrive(_global.output_folder_path)
            #Output and mo2 mods folder must be on same drive
            if mods_folder_drive != output_folder_drive:
                _global.mo2_error = 0
                return

            if ini.has_option('Settings', 'overwrite_directory'):
                _global.mo2_overwrite_path = os.path.normpath(ini.get('Settings', 'overwrite_directory'))
                if _global.mo2_overwrite_path.startswith("%BASE_DIR%"):
                    _global.mo2_overwrite_path = os.path.normpath(_global.mo2_overwrite_path.replace("%BASE_DIR%", mo2_base_dir))
            else:
                _global.mo2_overwrite_path = os.path.normpath(os.path.join(mo2_base_dir, 'overwrite'))

            overwrite_folder_drive, _ = os.path.splitdrive(_global.mo2_overwrite_path)
            #Output and mo2 overwrite folder must be on same drive
            if overwrite_folder_drive != output_folder_drive:
                _global.mo2_error = 1
                return

            profile = os.path.join(_global.mo2_profiles_dir, _global.mo2_profile)
            _global.plugins_txt_path = os.path.normpath(os.path.join(profile, 'plugins.txt'))
            _global.mo2_modlist_txt_path = os.path.normpath(os.path.join(profile, 'modlist.txt'))
        except Exception as e:
            _global.mo2_error = e

