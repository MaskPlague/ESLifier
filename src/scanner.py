import os
import regex as re
import threading
import timeit
import json
import subprocess
import mmap
import psutil
import struct

from plugin_qualification_checker import qualification_checker
from dependency_getter import dependecy_getter

class scanner():
    def scan(path, mo2_mode, modlist_txt_path, scan_esms, plugins_txt_path, bsab, update_header, full_scan):
        scanner.bsa_blacklist = ['skyrim - misc.bsa', 'skyrim - shaders.bsa', 'skyrim - interface.bsa', 'skyrim - animations.bsa', 'skyrim - meshes0.bsa', 'skyrim - meshes1.bsa',
                    'skyrim - sounds.bsa', 'skyrim - voices_en0.bsa', 'skyrim - textures0.bsa', 'skyrim - textures1.bsa', 'skyrim - textures2.bsa', 'skyrim - textures3.bsa',
                    'skyrim - textures4.bsa', 'skyrim - textures5.bsa', 'skyrim - textures6.bsa', 'skyrim - textures7.bsa', 'skyrim - textures8.bsa', 'skyrim - patch.bsa']
        start_time = timeit.default_timer()
        scanner.file_count = 0
        scanner.all_files = []
        scanner.plugins = []
        scanner.file_dict = {}
        scanner.bsa_dict = {}
        scanner.dll_dict = {}
        scanner.bsa_files = []
        scanner.threads = []
        scanner.seq_files = []
        scanner.pex_files = []
        scanner.dll_files = []
        scanner.kreate_files = []
        scanner.bsab = bsab
        scanner.lock = threading.Lock()
        total_ram = psutil.virtual_memory().total
        usable_ram = total_ram * 0.75
        thread_memory_usage = 10 * 1024 * 1024
        scanner.max_threads_by_ram = int(usable_ram / thread_memory_usage)
        thread_memory_usage = 2.5 * (1024**3)
        scanner.bsa_threads_by_ram = int(usable_ram / thread_memory_usage) * 7

        scanner.extracted = scanner.get_from_file('ESLifier_Data/extracted_bsa.json')
        print('\n')
        plugins_list = scanner.get_plugins_list(plugins_txt_path)
        if mo2_mode:
            load_order, enabled_mods = scanner.get_modlist(modlist_txt_path)
            scanner.all_files, scanner.plugins = scanner.get_winning_files(path, load_order, enabled_mods, scan_esms, plugins_list)
            scanner.file_count = len(scanner.all_files)
        else:
            scanner.get_files_from_skyrim_folder(path, scan_esms, plugins_list)

        scanner.plugin_basename_list = [os.path.basename(plugin).lower() for plugin in scanner.plugins]

        scanner.dump_to_file(file="ESLifier_Data/extracted_bsa.json", data=scanner.extracted)
        scanner.dump_to_file(file="ESLifier_Data/plugin_list.json", data=scanner.plugins)

        print('\033[F\033[K-  Gathered ' + str(len(scanner.all_files)) +' total files.', end='\r')

        if full_scan:
            print('Gettings Dependencies')
            dependency_dictionary = dependecy_getter.scan(path)
            print('Scanning Plugins')
            flag_dict = qualification_checker.scan(path, update_header, scan_esms)

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
    
    def sort_bsa_files(bsa_dict, plugins):
        def get_base_name(bsa_path):
            bsa_name = bsa_path.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
            bsa_name = bsa_name.lower().removesuffix('.bsa')
            bsa_name = re.sub(r' - textures\d*$', '', bsa_name)
            return bsa_name
        
        plugin_index = {plugin: idx for idx, plugin in enumerate(plugins)}
        filtered_bsa_items = {k: v for k, v in bsa_dict.items() if get_base_name(k) in plugin_index}
        sorted_bsa_items = sorted(filtered_bsa_items.items(),key=lambda item: plugin_index.get(get_base_name(item[0]), float('inf')))
        
        return dict(sorted_bsa_items)

    def get_files_from_skyrim_folder(path, scan_esms, plugins_list):
        path = os.path.normpath(path)
        path_level = len(path.split(os.sep))
        loop = 0
        if scan_esms:
            plugin_extensions = ('.esp', '.esm', '.esl')
        else:
            plugin_extensions = ('.esp', '.esl')
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
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path).lower()
                scanner.all_files.append(full_path)
                temp_rel_paths.append(rel_path)
                if path_level == root_level and file.lower().endswith(plugin_extensions):
                    scanner.plugins.append(full_path)
                if file.lower().endswith('.bsa') and file.lower() not in scanner.bsa_blacklist:
                    file = file[:-4]
                    if ' - textures' in file.lower():
                        index = file.lower().index(' - textures')
                        file = file[:index]
                    bsa_list.append([file.lower(), full_path])

        order_map = {plugin: index for index, plugin in enumerate(plugins_list)}
        filtered_bsa_list = [item for item in bsa_list if item[0] in order_map]
        filtered_bsa_list.sort(key=lambda x: order_map.get(x[0], float('inf')))
        bsa_length = len(filtered_bsa_list)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        last = 0
        update_time = 0.1
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            if file not in scanner.extracted:
                print(f'\033[F\033[K-  Extracting {i}/{bsa_length} BSA files\n-', end='\r')
                try:
                    try:
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf7", "-f", ".pex", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        print(f'\033[F\033[K{line}', end='\r')
                                        raise EncodingWarning(f'~utf-7 failed switching to utf-8 for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf7", "-f", ".seq", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        print(f'\033[F\033[K{line}', end='\r')
                                        raise EncodingWarning(f'~utf-7 failed switching to utf-8 for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        
                        scanner.extracted.append(file)
                    except Exception as e:
                        print(e)
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf8", "-f", ".pex", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-8 failed for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf8", "-f", ".seq", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-8 failed for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        
                        scanner.extracted.append(file)
                except Exception as e:
                    print(f'!Error Reading BSA: {file}')
                    print(e)
                print(f'\033[F\033[K')
        
        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted')

        for root, dirs, files in os.walk('bsa_extracted/'):
            scanner.file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {scanner.file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder).lower()
                if relative_path not in temp_rel_paths:
                    scanner.all_files.append(full_path)

    def get_files_from_mods(mods_folder, enabled_mods, scan_esms, plugins_list):
        if not os.path.exists('bsa_extracted/'):
            os.makedirs('bsa_extracted/')
        mod_files = {}
        cases_of_files = {}
        bsa_list = []
        if scan_esms:
            plugin_extensions = ('.esp', '.esl', '.esm')
        else:
            plugin_extensions = ('.esp', '.esl')
        plugin_names = []
        loop = 0
        file_count = 0
        #Get file from MO2's mods folder
        for mod_folder in os.listdir(mods_folder):
            mod_path = os.path.join(mods_folder, mod_folder)
            if os.path.isdir(mod_path) and mod_folder in enabled_mods:
                for root, dirs, files in os.walk(mod_path):
                    file_count += len(files)
                    if loop == 50: #prevent spamming stdout and slowing down the program
                        loop = 0
                        print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
                    else:
                        loop += 1
                    for file in files:
                        if file != 'meta.ini':
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
                            if file.lower().endswith(plugin_extensions):
                                plugin_names.append(file)
                            if file.lower().endswith('.bsa') and file.lower() not in scanner.bsa_blacklist:
                                file = file[:-4]
                                if ' - textures' in file.lower():
                                    index = file.lower().index(' - textures')
                                    file = file[:index]
                                bsa_list.append([file.lower(), full_path])

        #Get files from MO2's overwrite folder
        overwrite_path = os.path.join(os.path.split(mods_folder)[0], 'overwrite')
        for root, dirs, files in os.walk(overwrite_path):
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                full_path = os.path.join(root, file)
                cased = os.path.relpath(full_path, overwrite_path)
                relative_path = cased.lower()
                if '.mohidden' in relative_path:
                    continue
                if relative_path not in mod_files:
                    mod_files[relative_path] = []
                    cases_of_files[relative_path] = cased
                mod_files[relative_path].append('overwrite_eslifier_scan')
                if file.lower().endswith(plugin_extensions):
                    plugin_names.append(file)
                if file.lower().endswith('.bsa') and file.lower() not in scanner.bsa_blacklist:
                    file = file[:-4]
                    if ' - textures' in file.lower():
                        index = file.lower().index(' - textures')
                        file = file[:index]
                    bsa_list.append([file.lower(), full_path])


        order_map = {plugin: index for index, plugin in enumerate(plugins_list)}
        filtered_bsa_list = [item for item in bsa_list if item[0] in order_map]
        filtered_bsa_list.sort(key=lambda x: order_map.get(x[0], float('inf')))
        bsa_length = len(filtered_bsa_list)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        last = 0
        update_time = 0.1
        #Extract Files from BSA
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            if file not in scanner.extracted:
                print(f'\033[F\033[K-  Extracting {i}/{bsa_length} BSA files ({os.path.basename(file)})\n\n', end='\r')
                try:
                    try:
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf7", "-f", ".pex", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-7 failed switching to utf-8 for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf7", "-f", ".seq", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-7 failed switching to utf-8 for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        
                        scanner.extracted.append(file)
                    except Exception as e:
                        print(e)
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf8", "-f", ".pex", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-8 failed for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        with subprocess.Popen(
                            [scanner.bsab, file, "--encoding", "utf8", "-f", ".seq", "-e", "-o", "bsa_extracted"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            text=True
                            ) as p:
                                for line in p.stdout:
                                    if line.startswith('An error'):
                                        raise EncodingWarning(f'~utf-8 failed for {file}')
                                    if timeit.default_timer() - last > update_time:
                                        last = timeit.default_timer()
                                        print(f'\033[F\033[K{line}', end='\r')
                        
                        scanner.extracted.append(file)
                except Exception as e:
                    print(f'!Error Reading BSA: {file}')
                    print(e)
                print(f'\033[F\033[K')

        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')
        #Get files from overwrite
        for root, dirs, files in os.walk('bsa_extracted/'):
            file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                # Get the relative file path
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder)
                # Track the file paths by mod
                if relative_path not in mod_files:
                    mod_files[relative_path] = []
                    cases_of_files[relative_path] = relative_path
                mod_files[relative_path].append('bsa_extracted_eslifier_scan')

        return mod_files, plugin_names, cases_of_files

    def get_modlist(path):
        load_order = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                load_order = f.readlines()
        except Exception as e:
            print(f"!Error: failed to get modlist at {path}")
            print(e)

        enabled_mods = []
        for line in load_order:
            if line.startswith(('+','*')) and not line.endswith('_separator'):
                enabled_mods.append(line[1:].strip())
        
        enabled_mods.append('bsa_extracted_eslifier_scan')
        enabled_mods.reverse()
        enabled_mods.append('overwrite_eslifier_scan')

        to_remove = []
        for i in range(len(load_order)):
            load_order[i] = load_order[i][1:].strip()
            if '_separator' in load_order[i]:
                to_remove.append(load_order[i])
        
        for mod in to_remove:
            load_order.remove(mod)
        load_order.pop(0)
        load_order.append('bsa_extracted_eslifier_scan')
        load_order.reverse()
        load_order.append('overwrite_eslifier_scan')
        return load_order, enabled_mods
    
    def get_plugins_list(path):
        lines = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            active_plugins = []
            for line in lines:
                if line.startswith('*'):
                    active_plugins.append(line.strip()[1:-4].lower())
        except Exception as e:
            print(f'!Error: failed to get plugins list at: {path}')
            print(e)
            return []
        return active_plugins

    def get_winning_files(mods_folder, load_order, enabled_mods, scan_esms, plugins_list):
        mods_folder = os.path.normpath(mods_folder)
        mod_folder_level = len(mods_folder.split(os.sep))
        mod_files, plugin_names, cases = scanner.get_files_from_mods(mods_folder, enabled_mods, scan_esms, plugins_list)
        winning_files = []
        file_count = 0
        loop = 0
        cwd = os.getcwd()
        overwrite_path = os.path.join(os.path.split(mods_folder)[0], 'overwrite')
        for file, mods in mod_files.items():
            file_count += 1
            if loop == 500:
                loop = 0
                print(f'\033[F\033[K-  Winning Files Processed: {file_count}\n-', end='\r')
            else:
                loop += 1
            if len(mods) == 1:
                if mods[0] == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[file])
                elif mods[0] == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                else:
                    file_path = os.path.join(mods_folder, mods[0], cases[file])
                winning_files.append(file_path)
            else:
                mods_sorted = sorted(mods, key=lambda mod: load_order.index(mod))
                if mods_sorted[-1] == 'bsa_extracted_eslifier_scan':
                    file_path = os.path.join(cwd, 'bsa_extracted', cases[file])
                elif mods_sorted[-1] == 'overwrite_eslifier_scan':
                    file_path = os.path.join(overwrite_path, cases[file])
                else:
                    file_path = os.path.join(mods_folder, mods_sorted[-1], cases[file])
                winning_files.append(file_path)
        if scan_esms:
            plugin_extensions = ('.esp', '.esl', '.esm')
        else:
            plugin_extensions = ('.esp', '.esl')
        plugins = []
        plugin_names_lowered = [plugin.lower() for plugin in plugin_names]
        for file in winning_files:
            file_level = len(file.split(os.sep))
            if file_level == mod_folder_level + 2 and file.lower().endswith(plugin_extensions):
                plugin = os.path.join(os.path.dirname(file), plugin_names[plugin_names_lowered.index(os.path.basename(file.lower()))])
                plugins.append(plugin)

        return winning_files, plugins

    def dump_to_file(file, data):
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to: {file}')
            print(e)
    
    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
        return data

    def get_file_masters():
        plugin_names = []
        for plugin in scanner.plugins: plugin_names.append(os.path.basename(plugin).lower())
        #pattern = re.compile(r'(?:~|:\s*|\||=|,|-|")\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\)?)\s*(?:\||,|"|$)')
        pattern = re.compile(r'(?:~|:\s*|\||=|,|-|"|\*)\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\)?)\s*(?:\||,|"|$|\n)')
        pattern2 = re.compile(rb'\x00.([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\x00', flags=re.DOTALL)
        pattern3 = re.compile(r'\\facegeom\\([a-zA-Z0-9_\-\'\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        pattern4 = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        pattern5 = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\\')
        scanner.file_dict = {plugin: [] for plugin in plugin_names}
        scanner.count = 0
        
        if len(scanner.all_files) > 500000:
            split = scanner.max_threads_by_ram // 2
        elif len(scanner.all_files) > 50000:
            split = 50
        else:
            split = 5

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
        plugin_edid_dict = {}
        if os.path.exists('ESLifier_Data\\EDIDs'):
            for file in os.scandir('ESLifier_Data\\EDIDs'):
                basename = os.path.basename(file)
                plugin_name = basename.removesuffix('_EDIDs.txt').lower()
                plugin_edid_dict[plugin_name] = []
                with open(file, 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        plugin_edid_dict[plugin_name].append(line.strip())

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
            #print('\033[F\033[K-    Processed: ' + str(round(scanner.percentage, 1)) + '%' + '\n-    Files: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
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

    def file_processor(files, pattern, pattern3, pattern4, pattern5):
        local_dict = {}
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count / scanner.file_count) * 100
            file_lower = file.lower()
            factor = round(scanner.file_count * 0.01)
            if factor == 0:
                factor = 1
            if (scanner.count % factor) >= (factor-1):
                print('\033[F\033[K-    Processed: ' + str(round(scanner.percentage, 1)) + '%' + '\n-    Files: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
            if ((file_lower.endswith(('.ini', '.json', '.psc', '.jslot', '.toml', '_conditions.txt', '_srd.yaml'))
                or (file_lower.endswith('config.txt') and 'plugins\\customskill' in file_lower))
                    and not ('modex\\user\\kits' in file_lower
                            or 'nemesis_engine' in file_lower
                            or 'quickarmorrebalance\\config\\' in file_lower
                            or 'equipmenttoggle\\slotdata\\' in file_lower
                            or file_lower.endswith('revealingarmo_tng.ini')
                            or file_lower.endswith('enginefixes_snct.toml')
                            )
                ):
                if 'kreate\\presets\\' in file_lower:
                    scanner.kreate_files.append(file)
                    continue
                thread = threading.Thread(target=scanner.file_reader,args=(pattern, file, 'r'))
                scanner.threads.append(thread)
                thread.start()
            elif file_lower.endswith('.bsa'):
                if os.path.basename(file_lower) not in scanner.bsa_blacklist:
                    scanner.bsa_files.append(file)
            elif file_lower.endswith('.pex'):
                scanner.pex_files.append(file)
            elif file_lower.endswith('.dll'):
                scanner.dll_files.append(file)
            elif file_lower.endswith('.seq'):
                plugin = os.path.splitext(os.path.basename(file))[0]
                scanner.seq_files.append([plugin.lower(), file])
            elif ('\\facegeom\\' in file_lower and '.nif' in file_lower):
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern3, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif '\\facetint\\' in file_lower and '.dds' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern4, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif '\\sound\\' in file_lower and '\\voice\\' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern5, file_lower).group(1)
                        if plugin not in local_dict: 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
                        
        for key, values_list in local_dict.items():
            with scanner.lock:
                if key not in scanner.file_dict: scanner.file_dict.update({key: []})
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

    def file_reader(pattern, file, reader_type):
        try:
            file_lower = file.lower()
            if reader_type == 'r':
                if file_lower.endswith('.jslot'):
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        data = json.load(f)
                        f.close()
                    plugins = []
                    if 'actor' in data and 'headTexture' in data['actor']:
                        plugin_and_fid = data['actor']['headTexture']
                        plugins.append(plugin_and_fid[:-7].lower())
                    
                    if 'headParts' in data:
                        for part in data['headParts']:
                            if 'formIdentifier' in part:
                                formIdentifier = part['formIdentifier']
                                plugins.append(formIdentifier[:-7].lower())
                    for plugin in plugins:
                        with scanner.lock:
                            if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                            if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
                elif file_lower.endswith('.psc'):
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        data = f.read().lower()
                        f.close()
                    if 'getformfromfile' in data:
                        r = re.findall(pattern, data)
                        if r != []:
                            for plugin in r:
                                with scanner.lock:
                                    if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                                    if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
                    elif 'bsa_extracted\\' in file:
                        os.remove(file)
                else:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = [line.lower() for line in f.readlines()]
                    found_plugins = set()
                    for line in lines:
                        if '.es' in line:
                            for plugin in scanner.plugin_basename_list:
                                if plugin in line:
                                    found_plugins.add(plugin)
                                        
                    for plugin in found_plugins:
                        with scanner.lock:
                            if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                            if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
                    #    r = re.findall(pattern,f.read().lower())
                    #    f.close()
                    #if r != []:
                    #    for plugin in r:
                    #        if 'NOT Is' not in plugin:
                    #            with scanner.lock:
                    #                if plugin not in scanner.file_dict: scanner.file_dict.update({plugin: []})
                    #                if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)

            elif reader_type == 'pex':
                with open(file, 'rb') as f:
                    data = f.read()
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
                    f.close()
                if 'getformfromfile' in strings:
                    for string in strings:
                        if string.endswith(('.esp', '.esl', '.esm')) and not ':' in string and not '/' in string and not '\\' in string:
                            with scanner.lock:
                                if string not in scanner.file_dict: scanner.file_dict.update({string: []})
                                if file not in scanner.file_dict[string]: scanner.file_dict[string].append(file)
                elif 'bsa_extracted\\' in file:
                    os.remove(file)
            elif reader_type == 'dll':
                with open(file, 'rb') as f:
                    r = re.findall(pattern,f.read().lower())
                    f.close()
                if r != []:
                    for plugin in r:
                        plugin = plugin.decode('utf-8')
                        with scanner.lock:
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
            with open(bsa_file, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
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
                        raise ValueError('Exceeded max processing time')

            if plugins != []:
                with scanner.lock:
                    scanner.bsa_dict[bsa_file] = plugins
        except Exception as e:
            print(f'!Error Reading BSA: {bsa_file}')
            print(e)
