
from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning
from PyQt6.QtCore import QCoreApplication
import os
import re
import fnmatch
from vortex_database_reader import VortexDBParser
from vortex_database_reader import ReadState
from collections import deque, defaultdict
from data_holder import _global
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from scanner import scanner 

class VortexErrors(Enum):
    HAS_CYCLES = 0
    INVALID_MSF = 1
    DIFFERENT_MSF_AND_OF_DRIVEs = 2
    NO_LAST_SSE_PROFILE = 3

class Vortex():
    scanner: scanner = None
    def get_load_order(profile_id: str, installed_mods: dict[str, dict]) -> list[str]:
        profiles: dict[str, dict] = VortexDBParser.get_section("persistent###profiles###") or {}
        mod_state_data: dict[str, dict[str, bool|str]] = profiles.get(profile_id, {}).get("modState", {})
        
        enabled_mods: set[str] = set()
        enabled_lfn: dict[str] = {}
        for mod_id, state in mod_state_data.items():
            if state.get("enabled", False):
                enabled_mods.add(mod_id)
                enabled_lfn[mod_id] = state.get("logicalFileName")

        # pair_rules[frozenset({modA, modB})] = {(u, v): priority} 
        # where for (u, v), 'u' loads before 'v'
        pair_rules = defaultdict(lambda: defaultdict(int))

        for mod_id in enabled_mods:
            mod_data: dict[str, list[dict[str, dict]]] = installed_mods.get(mod_id, {})
            rules: list[dict[str, str]] = mod_data.get("rules", [])
            
            for rule in rules:
                ref = rule.get("reference", {})
                rule_type = rule.get("type")
                
                if rule_type not in ("before", "after"):
                    continue

                ref_id = ref.get("id")
                ref_fe = ref.get("fileExpression")
                ref_lfn = ref.get("logicalFileName")

                rule_targets = {}
                
                # High priority, 2, exact match for id
                if ref_id and ref_id in enabled_mods:
                    rule_targets[ref_id] = 2

                    
                # Low priority, 1, match for logicalFileName/fileExpression
                if ref_lfn or ref_fe:
                    for target_id in enabled_mods:
                        if target_id in rule_targets:
                            continue # Skip if already captured by Priority 2 match
                        
                        matched = False
                        target_lfn = enabled_lfn.get(target_id)
                        
                        # Match logicalFileName
                        if ref_lfn and target_lfn and ref_lfn == target_lfn:
                            matched = True
                        # Match fileExpression (exact, wildcard glob, or regex)
                        elif ref_fe:
                            if ref_fe == target_id:
                                matched = True
                            elif '*' in ref_fe or '?' in ref_fe:
                                if fnmatch.fnmatch(target_id.lower(), ref_fe.lower()):
                                    matched = True
                            else:
                                try:
                                    if re.search(ref_fe, target_id, re.IGNORECASE):
                                        matched = True
                                except re.error:
                                    pass
                                    
                        if matched:
                            rule_targets[target_id] = 1

                for target_id, priority in rule_targets.items():
                    if target_id == mod_id:
                        continue
                        
                    if rule_type == "before":
                        # mod_id loads before target_id
                        direction = (mod_id, target_id)
                    else:
                        # mod_id loads after target_id
                        direction = (target_id, mod_id)
                        
                    pair = frozenset({mod_id, target_id})
                    # Only keep the highest priority observed for this specific direction
                    pair_rules[pair][direction] = max(pair_rules[pair][direction], priority)

        adjacency_list = {mod: set() for mod in enabled_mods}
        in_degree = {mod: 0 for mod in enabled_mods}

        for pair, directions in pair_rules.items():
            if len(directions) == 1:
                u, v = list(directions.keys())[0]
                if v not in adjacency_list[u]:
                    adjacency_list[u].add(v)
                    in_degree[v] += 1
            else: # A conflict between rules exists: A before B and B before A 
                # Compare priorities
                dirs = list(directions.keys())
                dir1, dir2 = dirs[0], dirs[1]
                p1, p2 = directions[dir1], directions[dir2]

                winning_dirs = []
                if p1 > p2:
                    winning_dirs.append(dir1)
                elif p2 > p1:
                    winning_dirs.append(dir2)
                else:
                    # Same priority, leave both so Kahn's algo detects it as cycle.
                    winning_dirs.extend([dir1, dir2])
                    
                for u, v in winning_dirs:
                    if v not in adjacency_list[u]:
                        adjacency_list[u].add(v)
                        in_degree[v] += 1

        # Perform Topological Sort, Kahn's Algorithm
        queue = deque([mod for mod in enabled_mods if in_degree[mod] == 0])
        load_order = []

        while queue:
            current_mod = queue.popleft()
            load_order.append(current_mod)
            
            for dependent_mod in adjacency_list[current_mod]:
                in_degree[dependent_mod] -= 1
                if in_degree[dependent_mod] == 0:
                    queue.append(dependent_mod)

        # Handle cycles
        if len(load_order) != len(enabled_mods):
            unresolved = enabled_mods - set(load_order)
            load_order.extend(list(unresolved))
            write_to_file(f"Cyclic rules? {len(unresolved)} unresolved mods: {list(unresolved)}")
            Vortex.find_exact_cycles(adjacency_list, unresolved)
            _global.vortex_error = VortexErrors.HAS_CYCLES
            
        return load_order, installed_mods

    def find_exact_cycles(adj_list, unresolved_nodes):
        visited = {node: 0 for node in unresolved_nodes}
        path = []
        cycles = []
        
        def dfs(node):
            visited[node] = 1
            path.append(node)
            
            for neighbor in adj_list[node]:
                if neighbor in unresolved_nodes:
                    if visited[neighbor] == 0:
                        dfs(neighbor)
                    elif visited[neighbor] == 1:
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])
            
            path.pop()
            visited[node] = 2

        for node in unresolved_nodes:
            if visited[node] == 0:
                dfs(node)

        # De-duplicate permutations (A->B->C->A vs B->C->A->B)
        unique_cycles = set()
        for c in cycles:
            c_base = c[:-1]
            min_idx = c_base.index(min(c_base))
            normalized = tuple(c_base[min_idx:] + c_base[:min_idx])
            unique_cycles.add(normalized)
            
        for i, c in enumerate(unique_cycles, 1):
            cycle_list = list(c) + [c[0]]
            write_to_file(f"\n--- Cycle {i} ---" + "\n -> ".join(cycle_list) + "\n")

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
        ordered_mod_ids.insert(0, 'data_folder_file_eslifier_scan')

        load_order_index = {mod_id: i for i, mod_id in enumerate(ordered_mod_ids)}

        file_resolution = {}
        
        for file_path, providing_mods in mod_files.items():
            norm_file_path = file_path.replace("\\", "/")
            
            def sort_key(mod_id: str):
                is_actual_mod = 0 if mod_id in (
                    'data_folder_file_eslifier_scan', 
                    'bsa_extracted_eslifier_scan'
                ) else 1
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
                return (is_actual_mod, is_not_yielded, order_idx)

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
        if profile_id == None:
            write_to_file("No last used skyrimse profile. Aborting.")
            _global.vortex_error = VortexErrors.NO_LAST_SSE_PROFILE
            return [], [], [], '', ''

        plugins_list: list[str] = Vortex.get_plugins_list(profile_id)

        installed_mods: dict[str, dict] = VortexDBParser.get_section("persistent###mods###skyrimse###") or {}
        ordered_mod_ids, installed_mods = Vortex.get_load_order(profile_id, installed_mods)
        mod_staging_folder = VortexDBParser.get_key_value("settings###mods###installPath###skyrimse###")
        if mod_staging_folder != None:
            mod_staging_folder:str = os.path.normpath(mod_staging_folder.removeprefix('"').removesuffix('"'))
        if mod_staging_folder == None or mod_staging_folder == '' or not os.path.exists(mod_staging_folder):
            write_to_file("No skyrimse in installPath for Mod Staging Folder, assuming default at INSTANCE/skyrimse/mods/")
            mod_staging_folder = os.path.normpath(os.path.join(_global.vortex_data_path,"skyrimse/mods/"))
        
        if not os.path.exists(mod_staging_folder):
            write_to_file("Couldn't get an actual mod staging folder. Aborting.")
            write_to_file(f"Non-existent MSF at: {mod_staging_folder}")
            _global.vortex_error = VortexErrors.INVALID_MSF
            return [], [], [], '', ''
        gamedata = VortexDBParser.get_section("settings###gameMode###discovered###skyrimse")
        skyrim_folder_path = os.path.normpath(os.path.join(gamedata.get('path'), "Data"))

        mod_staging_folder_drive = os.path.splitdrive(mod_staging_folder)[0].lower()
        output_folder_drive = os.path.splitdrive(_global.output_folder_path)[0].lower()
        #Output and mod staging folder must be on same drive
        if mod_staging_folder_drive != output_folder_drive:
            write_to_file("Mod Staging Folder and Output Folder are not on the same Drive")
            write_to_file(f"MSF Drive: {mod_staging_folder_drive}, OF Drive: {output_folder_drive}")
            write_to_file(f"MSF: {mod_staging_folder}, OF: {_global.output_folder_path}")
            _global.vortex_error = VortexErrors.DIFFERENT_MSF_AND_OF_DRIVEs
            return [], [], [], '', ''
        mod_files:dict[str, list[str]] = {}
        cases: dict[str, str] = {}
        plugin_extensions = ('.esp', '.esl', '.esm')
        loop = 0
        plugin_names = set()
        bsa_list = []
        bsa_dict_temp:dict[str, list[str]] = {}
        bsa_file_name_dict:dict[str, str] = {}
        file_count = 0
        gathered_str = '-  ' + QCoreApplication.translate("scanner", "Gathered: ")
        write_normal(gathered_str, False)
        mod_folder_level = len(mod_staging_folder.split(os.sep)) + 1
        skyrim_data_level = len(skyrim_folder_path.split(os.sep))
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
                        if file != '__folder_managed_by_vortex':
                            file_lower = file.lower()
                            if file_lower in Vortex.scanner.ignored_files:
                                continue
                            is_mod_root_level = root_level == mod_folder_level
                            if is_mod_root_level and (file_lower == "collection.json" or file_lower == "meta.ini"):
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
                            if is_mod_root_level and file_lower.endswith(plugin_extensions):
                                plugin_names.add(file)
                            elif is_mod_root_level and file_lower.endswith('.bsa') and file_lower not in Vortex.scanner.bsa_blacklist:
                                bsa_file = file[:-4]
                                if ' - textures' in file_lower:
                                    index = bsa_file.lower().index(' - textures')
                                    bsa_file = bsa_file[:index]
                                if not file_lower in bsa_dict_temp:
                                    bsa_dict_temp[file_lower] = []
                                    bsa_file_name_dict[file_lower] = bsa_file.lower()
                                bsa_dict_temp[file_lower].append(mod_folder)

        #Get files from Skyrim's Data folder
        if os.path.exists(skyrim_folder_path):
            for root, dirs, files in os.walk(skyrim_folder_path):
                file_count += len(files)
                root_level = len(root.split(os.sep))
                if loop == 50: #prevent spamming stdout and slowing down the program
                    loop = 0
                    write_remove(1, gathered_str + str(file_count))
                else:
                    loop += 1
                for file in files:
                    if file != '__folder_managed_by_vortex':
                        file_lower = file.lower()
                        if file_lower in Vortex.scanner.ignored_files:
                            continue
                        is_file_root_level = root_level == skyrim_data_level
                        if is_file_root_level and (file_lower == "collection.json" or file_lower == "meta.ini"):
                            continue
                        full_path = os.path.join(root, file)
                        cased = os.path.relpath(full_path, skyrim_folder_path)
                        relative_path = cased.lower()
                        if relative_path not in mod_files:
                            mod_files[relative_path] = []
                            cases[relative_path] = cased
                        mod_files[relative_path].append('data_folder_file_eslifier_scan')
                        if is_file_root_level and file_lower.endswith(plugin_extensions):
                            if file not in plugin_names:
                                plugin_names.add(file)
                        elif is_file_root_level and file_lower.endswith('.bsa') and file_lower not in Vortex.scanner.bsa_blacklist:
                            bsa_file = file[:-4]
                            bsa_lower = bsa_file.lower()
                            if ' - textures' in bsa_lower:
                                index = bsa_lower.lower().index(' - textures')
                                bsa_lower = bsa_lower[:index]
                            if not file_lower in bsa_dict_temp:
                                bsa_dict_temp[file_lower] = []
                                bsa_file_name_dict[file_lower] = bsa_lower
                            bsa_dict_temp[file_lower].append('data_folder_file_eslifier_scan')
        bsa_conflict_map: dict[str, list[str]] = Vortex.get_file_conflict_resolution(
            ordered_mod_ids,
            bsa_dict_temp,
            installed_mods
        )
        #BSA list is expacted to be like: [[mod_name, full_path], [mod_name2, full_path2]] where mod_name is (mod_name).esp without ext 
        # for sorting by plugin during extraction. mod_name is obtained from (mod_name).bsa
        bsa_list = []
        for relative_path, providing_mods in bsa_conflict_map.items():
            if len(providing_mods) == 1:
                mod = providing_mods[0]
                if mod == 'data_folder_file_eslifier_scan':
                    file_path = os.path.join(skyrim_folder_path, relative_path)
                else:
                    file_path = os.path.join(mod_staging_folder, mod, relative_path)
                bsa_list.append([bsa_file_name_dict[relative_path], file_path])
            else:
                if providing_mods[-1] == 'data_folder_file_eslifier_scan':
                    file_path = os.path.join(skyrim_folder_path, relative_path)
                else:
                    file_path = os.path.join(mod_staging_folder, providing_mods[-1], relative_path)
                bsa_list.append([bsa_file_name_dict[relative_path], file_path])
        #bsa_list = [[bsa_file, full_path] for bsa_file, full_path in bsa_dict_temp.values()]

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
                data_folder_file = False
                mod = providing_mods[0]
                if mod == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[relative_path])
                elif mod == 'data_folder_file_eslifier_scan':
                    file_path = os.path.join(skyrim_folder_path, cases[relative_path])
                    data_folder_file = True
                else:
                    file_path = os.path.join(mod_staging_folder, mod, cases[relative_path])
                winning_files.append([file_path, data_folder_file])
                #winning_files.append(file_path)
                if mod != Vortex.scanner.output_file_name:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (mod, file_path)
            else:
                data_folder_file = False
                if providing_mods[-1] == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[relative_path])
                elif providing_mods[-1] == 'data_folder_file_eslifier_scan':
                    file_path = os.path.join(skyrim_folder_path, cases[relative_path])
                    data_folder_file = True
                else:
                    file_path = os.path.join(mod_staging_folder, providing_mods[-1], cases[relative_path])
                winning_files.append([file_path, data_folder_file])
                #winning_files.append(file_path)
                if providing_mods[-1] != Vortex.scanner.output_file_name:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (providing_mods[-1], file_path)
                else:
                    Vortex.scanner.winning_files_dict[cases[relative_path].lower()] = (providing_mods[-2], 
                                                                                       os.path.join(mod_staging_folder, providing_mods[-2], cases[relative_path]))

        plugins = []
        plugin_names = list(plugin_names)
        plugin_names_lowered = [plugin.lower() for plugin in plugin_names]
        for file, data_folder_file in winning_files:
            file_level = len(file.split(os.sep))
            if data_folder_file:
                level = skyrim_data_level
            else:
                level = mod_folder_level
            if file_level == level + 1 and file.lower().endswith(plugin_extensions) and not file.endswith("ESLifier_Cell_Master.esm"):
                plugin = os.path.join(os.path.dirname(file), plugin_names[plugin_names_lowered.index(os.path.basename(file.lower()))])
                plugins.append(plugin)
        return_list = [winning_file for winning_file, _ in winning_files]
        return return_list, plugins, plugins_list, mod_staging_folder, skyrim_folder_path

    def get_winning_files() -> tuple[list, list, list, str, str]:
        readibility_flag = VortexDBParser.is_readable()
        if readibility_flag in (ReadState.SUCCESS_DB, ReadState.SUCCESS_STATE):
            return Vortex.get_winning_file_conflicts()
        else:
            _global.vortex_error = readibility_flag
            return [], [], [], '', ''
        
        
