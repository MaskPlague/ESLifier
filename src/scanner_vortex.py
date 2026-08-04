
from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
import os
from vortex_database_reader import VortexDBParser
from collections import deque
from data_holder import _global
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scanner import scanner 


class Vortex():
    scanner: scanner = None
    def get_load_order(profile_id: str, installed_mods: dict[str, dict]) -> list[str]:
        profiles: dict[str, dict] = VortexDBParser.get_section("persistent###profiles###") or {}
        mod_state_data: dict[str, dict[str, bool|str]] = profiles.get(profile_id, {}).get("modState", {})
        
        enabled_mods: set[str] = set()
        for mod_id, state in mod_state_data.items():
            if state.get("enabled", False):
                enabled_mods.add(mod_id)

        # Build Adjacency List (Graph) and In-Degree counts for Topological Sort
        # An edge from A -> B means B must load AFTER A (B overwrites A / B wins)
        adjacency_list = {mod: set() for mod in enabled_mods}
        in_degree = {mod: 0 for mod in enabled_mods}

        for mod_id in enabled_mods:
            mod_data: dict[str, list[dict[str, dict]]] = installed_mods.get(mod_id, {})
            rules: list[dict[str, str]] = mod_data.get("rules", [])
            
            for rule in rules:
                ref = rule.get("reference", {})
                ref_id = ref.get("id") or ref.get("fileExpression")
                # Ignore rules referencing mods that aren't enabled/installed
                if not ref_id or ref_id not in enabled_mods:
                    continue
                rule_type = rule.get("type")

                if rule_type == "before":
                    # mod_id loads before ref_id
                    if ref_id not in adjacency_list[mod_id]:
                        adjacency_list[mod_id].add(ref_id)
                        in_degree[ref_id] += 1
                elif rule_type == "after":
                    # mod_id loads after ref_id
                    if mod_id not in adjacency_list[ref_id]:
                        adjacency_list[ref_id].add(mod_id)
                        in_degree[mod_id] += 1

        # Perform Topological Sort (Kahn's Algorithm)
        queue = deque([mod for mod in enabled_mods if in_degree[mod] == 0])
        load_order = []

        while queue:
            current_mod = queue.popleft()
            load_order.append(current_mod)
            
            for dependent_mod in adjacency_list[current_mod]:
                in_degree[dependent_mod] -= 1
                if in_degree[dependent_mod] == 0:
                    queue.append(dependent_mod)

        # Handle cycles (fallback)
        # If the lengths don't match, the user created a cyclic rule in Vortex (A -> B -> A)
        if len(load_order) != len(enabled_mods):
            unresolved = enabled_mods - set(load_order)
            # append unresolved mods to the end to prevent data loss
            load_order.extend(list(unresolved))
            _global.vortex_error = 2
        return load_order, installed_mods

    def get_file_conflict_resolution(
        ordered_mod_ids: list[str], 
        mod_files: dict[str, list[str]],
        installed_mods: dict[str, list]
    ) -> dict[str, list[str]]:
        # Extract specific file exceptions/yields per mod
        yielded_files_per_mod = {}
        for mod_id in ordered_mod_ids:
            mod_data = installed_mods.get(mod_id, {})
            raw_overrides = mod_data.get("fileOverrides", [])
            
            # Normalize DB yields to forward slashes and lowercase
            normalized_yields = set(p.lower().replace("\\", "/") for p in raw_overrides)

            yielded_files_per_mod[mod_id] = normalized_yields

        ordered_mod_ids.insert(0, 'bsa_extracted_eslifier_scan')
        load_order_index = {mod_id: i for i, mod_id in enumerate(ordered_mod_ids)}

        file_resolution = {}
        
        for file_path, providing_mods in mod_files.items():
            norm_file_path = file_path.replace("\\", "/")
            
            def sort_key(mod_id: str):
                yields_for_this_mod: set[str] = yielded_files_per_mod.get(mod_id, set())
                
                # Check if this mod specifically yielded this file in Vortex
                is_yielded = any(
                    norm_file_path.endswith(y) or y.endswith(norm_file_path) 
                    for y in yields_for_this_mod
                )
                
                # We want mods that DID NOT yield to sort higher 1 than mods that yielded 0
                is_not_yielded = int(not is_yielded)
                
                order_idx = load_order_index.get(mod_id, -1)
                
                # Yielded mods 0 come before Non-yielded mods 1, within these groups sort by normal load order
                return (is_not_yielded, order_idx)

            sorted_mods = sorted(providing_mods, key=sort_key)
            
            if sorted_mods:
                file_resolution[file_path] = sorted_mods

        return file_resolution

    def get_last_used_skyrim_profile():
        profile_data = VortexDBParser.get_section("settings###profiles###")
        return profile_data.get('lastActiveProfile',{}).get("skyrimse", None)

    def get_plugins_list(profile_id) -> list[str]:
        return Vortex.scanner.get_plugins_list(os.path.join(_global.vortex_data_path, "skyrimse", "profiles", profile_id, "plugins.txt"))
        
    def get_winning_file_conflicts():
        profile_id = Vortex.get_last_used_skyrim_profile()
        
        plugins_list: list[str] = Vortex.get_plugins_list(profile_id)

        installed_mods: dict[str, dict] = VortexDBParser.get_section("persistent###mods###skyrimse###") or {}
        ordered_mod_ids, installed_mods = Vortex.get_load_order(profile_id, installed_mods)
        mod_staging_folder = os.path.normpath(VortexDBParser.get_key_value("settings###mods###installPath###").removeprefix('"').removesuffix('"'))
        mod_staging_folder_drive, _ = os.path.splitdrive(mod_staging_folder)
        output_folder_drive, _ = os.path.splitdrive(_global.output_folder_path)
        #Output and mod staging folder must be on same drive
        if mod_staging_folder_drive != output_folder_drive:
            _global.vortex_error = 3
            return [], [], [], ''
        mod_files = {}
        cases: dict[str, str] = {}
        plugin_extensions = ('.esp', '.esl', '.esm')
        loop = 0
        plugin_names = []
        bsa_list = []
        file_count = 0
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        mod_folder_level = len(mod_staging_folder.split(os.sep)) + 1
        for mod_folder in os.listdir(mod_staging_folder):
            mod_path = os.path.join(mod_staging_folder, mod_folder)
            if os.path.isdir(mod_path) and mod_folder in ordered_mod_ids:
                for root, dirs, files in os.walk(mod_path):
                    file_count += len(files)
                    root_level = len(root.split(os.sep))
                    if loop == 50: #prevent spamming stdout and slowing down the program
                        loop = 0
                        write_remove(1, gathered_str + str(file_count))
                    else:
                        loop += 1
                    for file in files:
                        if file != 'meta.ini' and file != '__folder_managed_by_vortex':
                            file_lower = file.lower()
                            if file_lower in Vortex.scanner.ignored_files:
                                continue
                            # Get the relative file path
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, mod_staging_folder)
                            part = relative_path.split(os.sep)
                            cased = os.path.join(*part[1:])
                            relative_path = cased.lower()
                            # Track the file paths by mod
                            if relative_path not in mod_files:
                                mod_files[relative_path] = []
                                cases[relative_path] = cased
                            mod_files[relative_path].append(mod_folder)
                            if file_lower.endswith(plugin_extensions):
                                plugin_names.append(file)
                            if root_level == mod_folder_level and file_lower.endswith('.bsa') and file_lower not in Vortex.scanner.bsa_blacklist:
                                file = file[:-4]
                                if ' - textures' in file_lower:
                                    index = file.lower().index(' - textures')
                                    file = file[:index]
                                bsa_list.append([file.lower(), full_path])
        
        Vortex.scanner.extract_scripts_and_seq_from_bsa(bsa_list, plugins_list)
        cwd = os.getcwd()
        mod_folder = os.path.join(cwd, 'bsa_extracted/')
        #Get files that were extracted from BSA
        for root, dirs, files in os.walk('bsa_extracted/'):
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                write_remove(1, gathered_str + str(file_count))
            else:
                loop += 1
            for file in files:
                if file.lower() in Vortex.scanner.ignored_files:
                    continue
                # Get the relative file path
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder)
                # Track the file paths by mod
                if relative_path not in mod_files:
                    mod_files[relative_path] = []
                    cases[relative_path] = relative_path
                mod_files[relative_path].append('bsa_extracted_eslifier_scan')

        conflict_map: dict[str, list[str]] = Vortex.get_file_conflict_resolution(
            ordered_mod_ids,
            mod_files,
            installed_mods
        )
        
        #TODO: probably going to ignore the skyrim_data_folder as all files that suddenly appear/are generated should not need patching...
        winning_files = []
        file_count = 0
        loop = 0
        winning_files_processed_str = QCoreApplication.translate("scanner", "Winning Files Processed: ")
        write_remove(1, winning_files_processed_str)
        for relative_path, providing_mods in conflict_map.items():
            file_count += 1
            if loop == 500:
                loop = 0
                write_remove(1, winning_files_processed_str + str(file_count))
            else:
                loop += 1
            if len(providing_mods) == 1:
                #data_folder_file = False
                mod = providing_mods[0]
                if mod == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[relative_path])
                #elif mod == 'data_folder_file_eslifier_scan':
                #    file_path = os.path.join(skyrim_data_folder, cases[file])
                #    data_folder_file = True
                else:
                    file_path = os.path.join(mod_staging_folder, mod, cases[relative_path])
                #winning_files.append([file_path, data_folder_file])
                winning_files.append(file_path)
                if mod != Vortex.scanner.output_file_name:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (mod, file_path)
            else:
                #data_folder_file = False
                if providing_mods[-1] == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[relative_path])
                #elif providing_mods[-1] == 'data_folder_file_eslifier_scan':
                #    file_path = os.path.join(skyrim_data_folder, cases[file])
                #    data_folder_file = True
                else:
                    file_path = os.path.join(mod_staging_folder, providing_mods[-1], cases[relative_path])
                #winning_files.append([file_path, data_folder_file])
                winning_files.append(file_path)
                if providing_mods[-1] != Vortex.scanner.output_file_name:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (providing_mods[-1], file_path)
                else:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (providing_mods[-2], 
                                                                                       os.path.join(mod_staging_folder, providing_mods[-2], cases[relative_path]))

        plugins = []
        plugin_names_lowered = [plugin.lower() for plugin in plugin_names]
        for file in winning_files:
            file_level = len(file.split(os.sep))
            if file_level == mod_folder_level + 1 and file.lower().endswith(plugin_extensions) and not file.endswith("ESLifier_Cell_Master.esm"):
                plugin = os.path.join(os.path.dirname(file), plugin_names[plugin_names_lowered.index(os.path.basename(file.lower()))])
                plugins.append(plugin)
        return winning_files, plugins, plugins_list, mod_staging_folder

    def get_winning_files() -> tuple[list, list, list, str]:
        readibility_flag = VortexDBParser.is_readable()
        # 1: ok, 0: locked, e: E
        if readibility_flag == 1:
            return Vortex.get_winning_file_conflicts()
        else:
            _global.vortex_error = readibility_flag
            return [], [], [], ''
        
        
