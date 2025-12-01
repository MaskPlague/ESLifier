import os
import regex as re
import threading
import timeit
import json
import subprocess
import mmap
import psutil
import struct
import platform

if platform.system() == 'Windows':
    from win32 import win32file
    win32file._setmaxstdio(8192)
    WINDOWS = True
else:
    WINDOWS = False

from plugin_qualification_checker import qualification_checker
from dependency_getter import dependecy_getter

class scanner():
    def scan(full_scan: bool) -> tuple[dict, dict] | None:
        scanner.bsa_blacklist = ['skyrim - misc.bsa', 'skyrim - shaders.bsa', 'skyrim - interface.bsa', 'skyrim - animations.bsa', 'skyrim - meshes0.bsa', 'skyrim - meshes1.bsa',
                    'skyrim - sounds.bsa', 'skyrim - voices_en0.bsa', 'skyrim - textures0.bsa', 'skyrim - textures1.bsa', 'skyrim - textures2.bsa', 'skyrim - textures3.bsa',
                    'skyrim - textures4.bsa', 'skyrim - textures5.bsa', 'skyrim - textures6.bsa', 'skyrim - textures7.bsa', 'skyrim - textures8.bsa', 'skyrim - patch.bsa']
        start_time = timeit.default_timer()
        settings: dict = scanner.get_from_file('ESLifier_Data/settings.json', dict)
        path: str = settings.get('skyrim_folder_path', '')
        scanner.mo2_mode: bool = settings.get('mo2_mode', False)
        scanner.output_file_name = settings.get('output_folder_name', 'ESLifier Compactor Output')
        modlist_txt_path: str = settings.get('mo2_modlist_txt_path', '')
        plugins_txt_path: str = settings.get('plugins_txt_path', '')
        scanner.overwrite_path: str = settings.get('overwrite_path', '')
        update_header: bool = settings.get('update_header', False)
        scanner.file_count: int = 0
        scanner.all_files: list[str] = []
        scanner.plugins: list[str] = []
        scanner.file_dict: dict[str, list[str]] = {}
        scanner.bsa_dict: dict[str, list[str]] = {}
        scanner.dll_dict: dict[str, list[str]] = {}
        scanner.bsa_files: list[str] = []
        scanner.winning_files_dict: dict[str, list[str]] = {}
        scanner.threads: list[threading.Thread] = []
        scanner.seq_files: list[str] = []
        scanner.pex_files: list[str] = []
        scanner.dll_files: list[str] = []
        scanner.kreate_files: list[str] = []
        scanner.lock = threading.Lock()
        if not os.path.exists("ESLifier_Data/ignored_files.json"):
            with open("ESLifier_data/ignored_files.json", "w+", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=3)
        master_ignored_file_data = scanner.get_from_file("ESLifier_Data/master_ignored_files.json", dict)
        master_ignored_files = [item.lower() for item in master_ignored_file_data.get("ignored_files", [])]
        user_ignored_files = [item.lower() for item in scanner.get_from_file("ESLifier_Data/ignored_files.json", list)]
        master_ignored_files.extend(user_ignored_files)

        scanner.ignored_files = tuple(master_ignored_files)
        scanner.file_extensions = tuple([item.lower() for item in ('.ini', '.json', '.jslot', '.toml', '_conditions.txt', '.yaml', '.yml')])
        scanner.exclude_contains = tuple([item.lower() for item in (
            'modex\\user\\kits',
            'nemesis_engine',
            'quickarmorrebalance\\config\\',
            'equipmenttoggle\\slotdata\\',
            '\\headpartwhitelist\\',
            '\\interface\\quests\\'
            )])
        scanner.exclude_endswith = tuple([item.lower() for item in (
            '\\revealingarmo_tng.ini',
            '\\enginefixes_snct.toml', 
            '\\enginefixes_snct.ini',
            '\\vortex.deployment.json', 
            '\\aiprocessfixmodpatch.ini', 
            '\\grasscontrol.ini',
            '\\gearspreader.ini',
            '\\merge.json', '\\map.json', '\\fidcache.json', #zMerge
            '\\parallaxgen_diff.json',
            '\\console_cheatsheet.json'
            )])
        total_ram = psutil.virtual_memory().available
        usable_ram = total_ram * 0.90
        thread_memory_usage = 10 * 1024 * 1024 # assume each file is about 10 MB
        max_threads = max(100, int(usable_ram / thread_memory_usage))
        if max_threads > 8192 and WINDOWS:
            scanner.max_threads_by_ram = 8192
        elif max_threads > 1024 and not WINDOWS:
            scanner.max_threads_by_ram = 1024
        else:
            scanner.max_threads_by_ram = max_threads

        scanner.file_semaphore = threading.Semaphore(scanner.max_threads_by_ram)
        thread_memory_usage = 2.5 * (1024**3)
        scanner.bsa_threads_by_ram = max(1, int(usable_ram / thread_memory_usage) * 7)

        scanner.extracted: list[str] = scanner.get_from_file('ESLifier_Data/extracted_bsa.json', list)
        print('\n')
        plugins_list = scanner.get_plugins_list(plugins_txt_path)
        if scanner.mo2_mode:
            load_order, enabled_mods = scanner.get_modlist(modlist_txt_path)
            scanner.all_files, scanner.plugins = scanner.get_winning_files(path, load_order, enabled_mods, plugins_list)
            scanner.file_count = len(scanner.all_files)
        else:
            scanner.get_files_from_skyrim_folder(path, plugins_list)

        scanner.plugin_basename_list = [os.path.basename(plugin).lower() for plugin in scanner.plugins]

        scanner.dump_to_file(file="ESLifier_Data/extracted_bsa.json", data=scanner.extracted)
        scanner.dump_to_file(file="ESLifier_Data/plugin_list.json", data=scanner.plugins)
        scanner.dump_to_file(file="ESLifier_Data/winning_files_dict.json", data=scanner.winning_files_dict)

        print('\033[F\033[K-  Gathered ' + str(len(scanner.all_files)) +' total files.', end='\r')

        if full_scan:
            print('Getting Dependencies')
            dependency_dictionary = dependecy_getter.scan()
            print('Scanning Plugins')
            flag_dict = qualification_checker.scan(path, update_header)

        scanner.get_file_masters()

        bsa_dict = scanner.sort_bsa_files(scanner.bsa_dict, plugins_list)

        scanner.dump_to_file(file="ESLifier_Data/file_masters.json", data=scanner.file_dict)
        scanner.dump_to_file(file="ESLifier_Data/bsa_dict.json", data=bsa_dict)
        scanner.dump_to_file(file="ESLifier_Data/dll_dict.json", data=scanner.dll_dict)

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print(f'\033[F\033[K-  Time taken: ' + str(round(time_taken,2)) + ' seconds')
        if full_scan:
            return flag_dict, dependency_dictionary
    
    def sort_bsa_files(bsa_dict: dict, plugins: list) -> dict:
        def get_base_name(bsa_path: str) -> str:
            bsa_name = bsa_path.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
            bsa_name = bsa_name.lower().removesuffix('.bsa')
            bsa_name = re.sub(r' - textures\d*$', '', bsa_name)
            return bsa_name
        
        plugin_index = {plugin: idx for idx, plugin in enumerate(plugins)}
        filtered_bsa_items = {k: v for k, v in bsa_dict.items() if get_base_name(k) in plugin_index}
        sorted_bsa_items = sorted(filtered_bsa_items.items(),key=lambda item: plugin_index.get(get_base_name(item[0]), float('inf')))
        
        return dict(sorted_bsa_items)

    def get_files_from_skyrim_folder(path: str, plugins_list: list):
        if not os.path.exists('bsa_extracted/'):
            os.makedirs('bsa_extracted/')
        path = os.path.normpath(path)
        path_level = len(path.split(os.sep))
        loop = 0
        plugin_extensions = ('.esp', '.esm', '.esl')
        bsa_list = []
        temp_rel_paths = []
        for root, _, files in os.walk(path):
            root_level = len(root.split(os.sep))
            scanner.file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {scanner.file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                file_lower = file.lower()
                if file_lower in scanner.ignored_files:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path).lower()
                scanner.all_files.append(full_path)
                temp_rel_paths.append(rel_path)
                if path_level == root_level and file_lower.endswith(plugin_extensions):
                    scanner.plugins.append(full_path)
                if path_level == root_level and file_lower.endswith('.bsa') and file_lower not in scanner.bsa_blacklist:
                    file = file[:-4]
                    if ' - textures' in file_lower:
                        index = file_lower.index(' - textures')
                        file = file[:index]
                    bsa_list.append([file.lower(), full_path])

        order_map = {plugin: index for index, plugin in enumerate(plugins_list)}
        filtered_bsa_list = [item for item in bsa_list if item[0] in order_map]
        filtered_bsa_list.sort(key=lambda x: order_map.get(x[0], float('inf')))
        scanner.bsa_files = [file for _, file in filtered_bsa_list]
        bsa_length = len(filtered_bsa_list)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        update_time = 0.1
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            print(f'\033[F\033[K-  Extracting {i}/{bsa_length} BSA files ({os.path.basename(file)})\n\n', end='\r')
            if file not in scanner.extracted:
                try:
                    scanner.extract_bsa(file, startupinfo, update_time, ".pex")
                    scanner.extract_bsa(file, startupinfo, update_time, ".seq")
                    scanner.extracted.append(file)
                except Exception as e:
                    print(f'!Error Reading BSA: {file}')
                    print(e)
            print(f'\033[F\033[K')

        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')

        for root, dirs, files in os.walk('bsa_extracted/'):
            scanner.file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {scanner.file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                if file.lower() in scanner.ignored_files:
                    continue
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder).lower()
                if relative_path not in temp_rel_paths:
                    scanner.all_files.append(full_path)
                else:
                    if os.path.exists(full_path):
                        os.remove(full_path)

    def extract_bsa(file: str, startupinfo: subprocess.STARTUPINFO, update_time: float, filter: str):
        last = 0
        with subprocess.Popen(
            ["bsarch/bsarch.exe", "unpack", file, "bsa_extracted", filter],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            text=True
            ) as p:
                for line in p.stdout:
                    if line.startswith('Unpacking error'):
                        print(f'\033[F\033[K{line}', end='\r')
                        raise Exception(f"Occured during unpacking via modified BSArch.exe")
                    if timeit.default_timer() - last > update_time:
                        last = timeit.default_timer()
                        print(f'\033[F\033[K-  Extracting: {line}', end='\n')

    def get_files_from_mods(mods_folder: str, enabled_mods: list, plugins_list: list, overwrite_path: str) -> tuple[dict, list, dict]:
        if not os.path.exists('bsa_extracted/'):
            os.makedirs('bsa_extracted/')
        mod_files: dict[str, list[str]] = {}
        cases_of_files: dict[str, str] = {}
        bsa_list = []
        plugin_extensions = ('.esp', '.esl', '.esm')
        plugin_names = []
        loop = 0
        file_count = 0
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
                        print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
                    else:
                        loop += 1
                    for file in files:
                        if file != 'meta.ini':
                            file_lower = file.lower()
                            if file_lower in scanner.ignored_files:
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
                            if root_level == mod_folder_level and file_lower.endswith('.bsa') and file_lower not in scanner.bsa_blacklist:
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
                    print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
                else:
                    loop += 1
                for file in files:
                    file_lower = file.lower()
                    if file_lower in scanner.ignored_files:
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
                    if file_lower.endswith('.bsa') and file_lower not in scanner.bsa_blacklist:
                        file = file[:-4]
                        if ' - textures' in file_lower:
                            index = file_lower.index(' - textures')
                            file = file[:index]
                        bsa_list.append([file.lower(), full_path])
        else:
            print('Overwrite folder not found.\n')

        order_map = {plugin: index for index, plugin in enumerate(plugins_list)}
        filtered_bsa_list = [item for item in bsa_list if item[0] in order_map]
        filtered_bsa_list.sort(key=lambda x: order_map.get(x[0], float('inf')))
        scanner.bsa_files = [file for _, file in filtered_bsa_list]
        bsa_length = len(filtered_bsa_list)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        update_time = 0.1
        #Extract Files from BSA
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            if file not in scanner.extracted:
                print(f'\033[F\033[K-  Extracting {i+1}/{bsa_length} BSA files ({os.path.basename(file)})\n\n', end='\r')
                try:
                    scanner.extract_bsa(file, startupinfo, update_time, ".pex")
                    scanner.extract_bsa(file, startupinfo, update_time, ".seq")
                    scanner.extracted.append(file)
                except Exception as e:
                    print(f'!Error Reading BSA: {file}')
                    print(e)
                print(f'\033[F\033[K')

        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')
        #Get files that were extracted from BSA
        for root, dirs, files in os.walk('bsa_extracted/'):
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                if file.lower() in scanner.ignored_files:
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

    def get_modlist(path: str) -> tuple[list[str], list[str]]:
        load_order = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                load_order = f.readlines()
                f.close()
        except Exception as e:
            print(f"!Error: failed to get modlist at {path}")
            print(e)

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
        load_order.pop(0)
        load_order.append('bsa_extracted_eslifier_scan')
        load_order.reverse()
        load_order.append('overwrite_eslifier_scan')
        return load_order, enabled_mods
    
    def get_plugins_list(path: str) -> list:
        lines = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                f.close()
            active_plugins = []
            for line in lines:
                if line.startswith('*'):
                    active_plugins.append(line.strip()[1:-4].lower())
        except Exception as e:
            print(f'!Error: failed to get plugins list at: {path}')
            print(e)
            return []
        return active_plugins

    def get_winning_files(mods_folder: str, load_order: list, enabled_mods: list, plugins_list: list) -> tuple[list, list]:
        mods_folder = os.path.normpath(mods_folder)
        overwrite_path = os.path.normpath(scanner.overwrite_path)
        mod_folder_level = len(mods_folder.split(os.sep))
        overwrite_level = len(overwrite_path.split(os.sep)) - 1
        mod_files: dict[str, list[str]]
        plugin_names: list[str]
        cases: dict[str, str]
        mod_files, plugin_names, cases = scanner.get_files_from_mods(mods_folder, enabled_mods, plugins_list, overwrite_path)
        winning_files: list[list[str, str]] = []
        file_count = 0
        loop = 0
        cwd = os.getcwd()
        for file, mods in mod_files.items():
            file_count += 1
            if loop == 500:
                loop = 0
                print(f'\033[F\033[K-  Winning Files Processed: {file_count}\n-', end='\r')
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
                if mod != scanner.output_file_name:
                    scanner.winning_files_dict[cases[file].lower()] = (mod, file_path)
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
                if mods_sorted[-1] != scanner.output_file_name:
                    scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-1], file_path)
                else:
                    scanner.winning_files_dict[cases[file].lower()] = (mods_sorted[-2], os.path.join(mods_folder, mods_sorted[-2], cases[file]))
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

    def dump_to_file(file: str, data: list | dict):
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to: {file}')
            print(e)
    
    def get_from_file(file: str, type: dict | list) -> list[str] | dict[str]:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data: list[str] | dict[str] = json.load(f)
        except:
            data: list[str] | dict[str] = type()
        return data

    def get_file_masters():
        plugin_names = []
        for plugin in scanner.plugins: plugin_names.append(os.path.basename(plugin).lower())
        #pattern = re.compile(r'(?:~|:\s*|\||=|,|-|")\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\)?)\s*(?:\||,|"|$)')
        pattern = re.compile(r'(?:~|:\s*|\||=|,|-|"|\*)\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\)?)\s*(?:\||,|"|$|\n)')
        pattern2 = re.compile(rb'\x00([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\x00', flags=re.DOTALL)
        pattern3 = re.compile(r'\\facegeom\\([a-zA-Z0-9_\-\'\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        pattern4 = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        pattern5 = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        scanner.file_dict = {plugin: [] for plugin in plugin_names}
        scanner.count = 0
        if len(scanner.all_files) > 500000:
            split = max(1, scanner.max_threads_by_ram)
        elif len(scanner.all_files) > 50000:
            split = 50
        else:
            split = 5
        scanner.file_semaphore = threading.Semaphore(1000)
        chunk_size = len(scanner.all_files) // split
        chunks = [scanner.all_files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(scanner.all_files[(split) * chunk_size:])

        print('Getting masters of loose files...\n\n')
        for chunk in chunks:
            thread = threading.Thread(target=scanner.file_processor, args=(chunk, pattern, pattern3, pattern4, pattern5))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        print(f"\033[F\033[K-  Scanning .pex files\n\n")
        scanner.file_count = len(scanner.pex_files)
        scanner.count = 0
        if len(scanner.pex_files) > 8192 :
            split = 500 
        elif len(scanner.pex_files) > 2048:
            split = 200
        elif len(scanner.pex_files) > 512:
            split = 50
        else:
            split = 1
        chunk_size = len(scanner.pex_files) // split
        chunks = [scanner.pex_files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(scanner.pex_files[(split) * chunk_size:])
        for chunk in chunks:
            thread = threading.Thread(target=scanner.pex_processor, args=(pattern2, chunk,))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        print(f"\033[F\033[K-  Scanning .dll SKSE plugins")
        for file in scanner.dll_files:
            thread = threading.Thread(target=scanner.file_reader,args=(pattern2, file, 'dll'))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        print("-  Sorting .seq files")
        scanner.seq_plugin_extension_processor(scanner.seq_files)

        print("-  Scanning .bsa files")
        scanner.file_count = len(scanner.bsa_files)
        scanner.count = 0
        if len(scanner.bsa_files) > 100:
            split = scanner.bsa_threads_by_ram
        elif len(scanner.bsa_files) > 10:
            split = 10
        else:
            split = 1
        chunk_size = len(scanner.bsa_files) // split
        chunks = [scanner.bsa_files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(scanner.bsa_files[(split) * chunk_size:])
        for chunk in chunks:
            thread = threading.Thread(target=scanner.bsa_processor, args=(chunk,))
            scanner.threads.append(thread)
            thread.start()
        
        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        print("-  Scanning Other files\n\n")
        scanner.kreate_processor()

    def kreate_processor():
        plugin_edid_dict: dict[str, list[str]] = {}
        if os.path.exists('ESLifier_Data\\EDIDs'):
            for file in os.scandir('ESLifier_Data\\EDIDs'):
                basename = os.path.basename(file)
                plugin_name = basename.removesuffix('_EDIDs.txt').lower()
                plugin_edid_dict[plugin_name] = []
                with open(file, 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        plugin_edid_dict[plugin_name].append(line.strip())
                    f.close()

        for plugin, edids in plugin_edid_dict.items():
            for kreate_file in scanner.kreate_files:
                file_edid = os.path.basename(kreate_file).removesuffix('.ini')
                # only works if KreatE preset has at least one EDID ini file from a weather mod
                if file_edid in edids:
                    # assume everything in a preset is meant for one weather mod or does not share ANY Form IDs with other weather mods
                    if plugin not in scanner.file_dict: 
                        scanner.file_dict.update({plugin: []})
                    split = kreate_file.split(os.sep)[:-2]
                    level = len(split)
                    directory = os.sep.join(split)
                    for root, _, files in os.walk(directory):
                        split = root.split(os.sep)
                        root_level = len(split)
                        if root_level == level + 1:
                            for file_name in files:
                                file = os.path.join(root, file_name)
                                if file not in scanner.file_dict[plugin]: 
                                    scanner.file_dict[plugin].append(file)
                    break
        
    def bsa_processor(files):
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count/scanner.file_count) * 100
            scanner.bsa_reader(file)

    def pex_processor(pattern2, files):
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count / scanner.file_count) * 100
            factor = round(scanner.file_count * 0.01)
            if factor == 0:
                factor = 1
            if (scanner.count % factor) >= (factor-1):
                print('\033[F\033[K-    Processed: ' + str(round(scanner.percentage, 1)) + '%' + '\n-    Files: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
            scanner.file_reader(pattern2, file, 'pex')

    def file_processor(files: list[str], pattern, pattern3, pattern4, pattern5):
        local_dict: dict[str, list[str]] = {}
        local_pex: list[str] = []
        local_dll: list[str] = []
        local_seq: list[str] = []
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count / scanner.file_count) * 100
            file_lower = file.lower()
            factor = round(scanner.file_count * 0.01)
            if factor == 0:
                factor = 1
            if (scanner.count % factor) >= (factor-1):
                print('\033[F\033[K-    Processed: ' + str(round(scanner.percentage, 1)) + '%' + 
                      '\n-    Files: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
            if ((file_lower.endswith(scanner.file_extensions) or (file_lower.endswith('config.txt') and 'plugins\\customskill' in file_lower))
                and not (any(exclusion in file_lower for exclusion in scanner.exclude_contains) or file_lower.endswith(scanner.exclude_endswith))
                ):
                if 'kreate\\presets\\' in file_lower and file_lower.endswith('.ini'):
                    scanner.kreate_files.append(file)
                    continue
                thread = threading.Thread(target=scanner.file_reader,args=(pattern, file, 'r'))
                scanner.threads.append(thread)
                thread.start()
            elif file_lower.endswith('.pex'):
                local_pex.append(file)
            elif file_lower.endswith('.dll') and '\\skse\\plugins' in file_lower:
                local_dll.append(file)
            elif file_lower.endswith('.seq'):
                plugin = os.path.splitext(os.path.basename(file))[0]
                local_seq.append([plugin.lower(), file])
            elif file_lower.endswith('.nif') and '\\facegeom\\' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern3, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif file_lower.endswith('.dds') and '\\facetint\\' in file_lower :
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern4, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif '\\sound\\voice\\' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern5, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
        with scanner.lock:     
            scanner.pex_files.extend(local_pex)
            scanner.seq_files.extend(local_seq)
            scanner.dll_files.extend(local_dll)      
            for key, values_list in local_dict.items():
                if key in scanner.plugin_basename_list:
                    if key not in scanner.file_dict:
                        scanner.file_dict.update({key: []})
                    scanner.file_dict[key].extend(values_list)

    def seq_plugin_extension_processor(files):
        for file in files:
            esp, esl, esm = file[0] + '.esp', file[0] + '.esl', file[0] + '.esm'
            if esp in scanner.file_dict:
                if file[1] not in scanner.file_dict[esp]: scanner.file_dict[esp].append(file[1])
            elif esl in scanner.file_dict:
                if file[1] not in scanner.file_dict[esl]: scanner.file_dict[esl].append(file[1])
            elif esm in scanner.file_dict:
                if file[1] not in scanner.file_dict[esm]: scanner.file_dict[esm].append(file[1])

    def file_reader(pattern, file: str, reader_type):
        try:
            file_lower = file.lower()
            if reader_type == 'r':
                if file_lower.endswith('.jslot'):
                    with scanner.file_semaphore:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            read_string = f.read()
                            while read_string[-1] != '}':
                                read_string = read_string.removesuffix(read_string[-1])
                            data = json.loads(read_string)
                            f.close()
                    plugins = []
                    if 'actor' in data and 'headTexture' in data['actor']:
                        plugin_and_fid = data['actor']['headTexture']
                        plugins.append(plugin_and_fid[:-7].lower())
                    
                    if 'headParts' in data:
                        for part in data['headParts']:
                            if 'formIdentifier' in part:
                                formIdentifier: str = part['formIdentifier']
                                plugins.append(formIdentifier[:-7].lower())
                    with scanner.lock:
                        for plugin in plugins:
                            if plugin in scanner.plugin_basename_list:
                                if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                                if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
                else:
                    with scanner.file_semaphore:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            normal_lines = f.readlines()
                            f.close()
                    lines = [line.lower() for line in normal_lines]
                    found_plugins = set()
                    for line in lines:
                        if '.es' in line:
                            plugins_in_line = []
                            for plugin in scanner.plugin_basename_list:
                                if plugin in line:
                                    index = line.index(plugin)
                                    plugins_in_line.append([plugin, index, index+len(plugin)])
                            for plugin, start, end in plugins_in_line:
                                if not any(plugin_start < start < plugin_end for _, plugin_start, plugin_end in plugins_in_line):
                                    found_plugins.add(plugin)
                    with scanner.lock:                  
                        for plugin in found_plugins:
                            if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                            if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)

            elif reader_type == 'pex':
                with scanner.file_semaphore:
                    with open(file, 'rb') as f:
                        data = f.read()
                        f.close()
                offset = 18 + struct.unpack('>H', data[16:18])[0]
                offset += 2 + struct.unpack('>H', data[offset:offset+2])[0]
                offset += 2 + struct.unpack('>H', data[offset:offset+2])[0]
                string_count = struct.unpack('>H', data[offset:offset+2])[0]
                offset += 2
                strings = []
                for _ in range(string_count):
                    string_length = struct.unpack('>H', data[offset:offset+2])[0]
                    strings.append(data[offset+2:offset+2+string_length].lower().decode())
                    offset += 2 + string_length
                if 'getformfromfile' in strings: #or 'getmodbyname' in strings:
                    for string in strings:
                        if string.endswith(('.esp', '.esl', '.esm')) and string in scanner.plugin_basename_list:#not ':' in string and not '/' in string and not '\\' in string:
                            with scanner.lock:
                                if string not in scanner.file_dict: scanner.file_dict.update({string: []})
                                if file not in scanner.file_dict[string]: scanner.file_dict[string].append(file)
                elif 'bsa_extracted\\' in file:
                    os.remove(file)
            elif reader_type == 'dll':
                with scanner.file_semaphore:
                    with open(file, 'rb') as f:
                        r = re.findall(pattern,f.read().lower())
                        f.close()
                if r != []:
                    with scanner.lock:
                        for plugin in r:
                            plugin = plugin.decode('utf-8')
                            if plugin in scanner.plugin_basename_list:
                                if plugin not in scanner.dll_dict: scanner.dll_dict.update({plugin: []})
                                if file not in scanner.dll_dict[plugin]: scanner.dll_dict[plugin].append(file)
            else:
                print(f'!Warn: Missing file scan type for {file}')

        except Exception as e:
            print(f"!Error reading file {file}")
            if reader_type == 'pex':
                print('!pex file is likely corrupt.')
            print(e)

    def bsa_reader(bsa_file):
        plugins = []
        pattern_1 = re.compile(rb'([^\\]+\.es[pml])')
        try:
            with scanner.file_semaphore:
                with open(bsa_file, 'rb') as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        if mm[:3] != b'BSA': # Confirm .BSA file is actually a BSA and not something renamed
                            mm.close()
                            f.close()
                            return
                        folder_count = struct.unpack('<I', mm[16:20])[0]
                        version = struct.unpack('<I', mm[4:8])[0]
                        if version == 105:
                            folder_record_size = 24
                            file_record_offset = 16
                        else:
                            folder_record_size = 16
                            file_record_offset = 12
                        total_file_name_length = struct.unpack('<I', mm[28:32])[0]

                        end_of_folder_records = (folder_count * folder_record_size) + 36
                        offset = 36
                        max_time = 5
                        time = 0
                        start_time = timeit.default_timer()
                        if end_of_folder_records > len(mm) + 1:
                            raise ValueError('Possibly Corrupt BSA')
                        while offset < end_of_folder_records and time < max_time:
                            location = int.from_bytes(mm[offset+file_record_offset:offset+file_record_offset+4][::-1]) - total_file_name_length
                            folder_length = int.from_bytes(mm[location:location+1])
                            folder_path = mm[location+1:location+folder_length].decode(errors='ignore')

                            if ('facegeom\\' in folder_path or 'facetint\\' in folder_path or 'sound\\voice' in folder_path) and ('.esp' in folder_path or '.esl' in folder_path or '.esm' in folder_path):
                                match = re.search(pattern_1, folder_path.encode())
                                if match:
                                    plugin = match.group(0).decode()
                                    if plugin not in plugins:
                                        plugins.append(plugin)
                            time = timeit.default_timer() - start_time
                            offset += folder_record_size
                        if time > max_time:
                            raise ValueError(f'Exceeded max processing time for {bsa_file}')
                        mm.close()
                    f.close()

            if plugins != []:
                with scanner.lock:
                    scanner.bsa_dict[bsa_file] = plugins
        except Exception as e:
            print(f'!Error Reading BSA: {bsa_file}')
            print(e)
