import os
import regex as re
import threading
import timeit
import json
import subprocess

class scanner():
    def __init__(self, path, mo2_mode, modlist_txt_path, scan_esms, plugins_txt_path, bsab):
        scanner.bsa_blacklist = ['skyrim - misc.bsa', 'skyrim - shaders.bsa', 'skyrim - interface.bsa', 'skyrim - animations.bsa', 'skyrim - meshes0.bsa', 'skyrim - meshes1.bsa',
                    'skyrim - sounds.bsa', 'skyrim - voices_en0.bsa', 'skyrim - textures0.bsa', 'skyrim - textures1.bsa', 'skyrim - textures2.bsa', 'skyrim - textures3.bsa',
                    'skyrim - textures4.bsa', 'skyrim - textures5.bsa', 'skyrim - textures6.bsa', 'skyrim - textures7.bsa', 'skyrim - textures8.bsa', 'skyrim - patch.bsa']
        start_time = timeit.default_timer()
        scanner.file_count = 0
        scanner.all_files = []
        scanner.plugins = []
        scanner.bsab = bsab
        scanner.lock = threading.Lock()
        scanner.extracted = scanner.get_from_file('ESLifier_Data/extracted_bsa.json')
        print('-  Gathering Files...\n\n')
        plugins_list = scanner.get_plugins_list(plugins_txt_path)
        if mo2_mode:
            load_order, enabled_mods = scanner.get_modlist(modlist_txt_path)
            scanner.all_files, scanner.plugins = scanner.get_winning_files(path, load_order, enabled_mods, scan_esms, plugins_list)
            scanner.file_count = len(scanner.all_files)
        else:
            scanner.get_files_from_skyrim_folder(path, scan_esms, plugins_list)

        scanner.dump_to_file(file="ESLifier_Data/extracted_bsa.json", data=scanner.extracted)
        scanner.dump_to_file(file="ESLifier_Data/plugin_list.json", data=scanner.plugins)

        print('\033[F\033[K-  Gathered ' + str(len(scanner.all_files)) +' total files.', end='\r')
        
        scanner.get_file_masters()

        bsa_dict = scanner.sort_bsa_files(scanner.bsa_dict, plugins_list)

        scanner.dump_to_file(file="ESLifier_Data/file_masters.json", data=scanner.file_dict)
        scanner.dump_to_file(file="ESLifier_Data/bsa_dict.json", data=bsa_dict)
        scanner.dump_to_file(file="ESLifier_Data/dll_dict.json", data=scanner.dll_dict)
        

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print(f'\033[F\033[K-  Time taken: ' + str(round(time_taken,2)) + ' seconds')

    
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
        path_level = len(path.split(os.sep))
        loop = 0
        if scan_esms:
            plugin_extensions = ('.esp', '.esm', '.esl')
        else:
            plugin_extensions = ('.esp', '.esl')
        bsa_list = []
        temp_rel_paths = []
        for root, _, files in os.walk(path):
            if 'eslifier' not in root.lower():
                root_level = len(root.split(os.sep))
                scanner.file_count += len(files)
                if loop == 50: #prevent spamming stdout and slowing down the program
                    loop = 0
                    print(f'\033[F\033[K-  Gathered: {scanner.file_count}\n-', end='\r')
                else:
                    loop += 1
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, path)
                    scanner.all_files.append(full_path)
                    temp_rel_paths.append(rel_path)
                    if path_level == root_level and file.lower().endswith(plugin_extensions) :
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
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            if file not in scanner.extracted:
                print(f'\033[F\033[K-  Extracting {i}/{bsa_length} BSA files\n-', end='\r')
                subprocess.run([scanner.bsab, file, "-f", ".pex", "-e", "-o", "bsa_extracted"], creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run([scanner.bsab, file, "-f", ".seq", "-e", "-o", "bsa_extracted"], creationflags=subprocess.CREATE_NO_WINDOW)
                scanner.extracted.append(file)
        
        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')

        for root, dirs, files in os.walk('bsa_extracted/'):
            scanner.file_count += len(files)
            if loop == 50: #prevent spamming stdout and slowing down the program
                loop = 0
                print(f'\033[F\033[K-  Gathered: {scanner.file_count}\n-', end='\r')
            else:
                loop += 1
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, mod_folder)
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
                            part = relative_path.split('\\')
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
                print(f'\033[F\033[K-  Extracting {i}/{bsa_length} BSA files\n\n', end='\r')
                with subprocess.Popen(
                    [scanner.bsab, file, "-f", ".pex", "-e", "-o", "bsa_extracted"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    text=True
                    ) as p:
                        for line in p.stdout:
                            if timeit.default_timer() - last > update_time:
                                last = timeit.default_timer()
                                print(f'\033[F\033[K{line}', end='\r')
                with subprocess.Popen(
                    [scanner.bsab, file, "-f", ".seq", "-e", "-o", "bsa_extracted"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    text=True
                    ) as p:
                        for line in p.stdout:
                            if timeit.default_timer() - last > update_time:
                                last = timeit.default_timer()
                                print(f'\033[F\033[K{line}', end='\r')
                print(f'\033[F\033[K')
                scanner.extracted.append(file)

        mod_folder = os.path.join(os.getcwd(), 'bsa_extracted/')

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
                mod_files[relative_path].append('bsa_extracted')

        return mod_files, plugin_names, cases_of_files

    def get_modlist(path):
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        enabled_mods = []
        for line in lines:
            if line.startswith(('+','*')) and not line.endswith('_separator'):
                enabled_mods.append(line[1:].strip())
        
        enabled_mods.append('bsa_extracted')
        enabled_mods.reverse()

        to_remove = []
        for i in range(len(lines)):
            lines[i] = lines[i][1:].strip()
            if '_separator' in lines[i]:
                to_remove.append(lines[i])
        
        for mod in to_remove:
            lines.remove(mod)
        lines.pop(0)
        lines.append('bsa_extracted')
        lines.reverse()
        return lines, enabled_mods
    
    def get_plugins_list(path):
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        active_plugins = []
        for line in lines:
            if line.startswith('*'):
                active_plugins.append(line.strip()[1:-4].lower())
        return active_plugins

    def get_winning_files(mods_folder, load_order, enabled_mods, scan_esms, plugins_list):
        mod_folder_level = len(mods_folder.split(os.sep))
        mod_files, plugin_names, cases = scanner.get_files_from_mods(mods_folder, enabled_mods, scan_esms, plugins_list)
        winning_files = []
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
                if mods[0] == 'bsa_extracted':
                    file_path = os.path.join(cwd, mods[0], cases[file])
                else:
                    file_path = os.path.join(mods_folder, mods[0], cases[file])
                winning_files.append(file_path)
            else:
                mods_sorted = sorted(mods, key=lambda mod: load_order.index(mod))
                if mods_sorted[-1] == 'bsa_extracted':
                    file_path = os.path.join(cwd, mods_sorted[-1], cases[file])
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
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
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
        pattern = re.compile(r'(?:~|: *|\||=|,|-|")\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\)?)(?:\||,|"|$)')
        pattern2 = re.compile(rb'\x00.([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\x00', flags=re.DOTALL)
        pattern3 = re.compile(r'\\facegeom\\([a-zA-Z0-9_\-\'\?\!\(\)\[\]\, ]+\.es[pml])\\')
        pattern4 = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\\')
        pattern5 = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\\')
        scanner.file_dict = {plugin: [] for plugin in plugin_names}
        scanner.bsa_dict = {}
        scanner.dll_dict = {}
        scanner.bsa_files = []
        scanner.threads = []
        scanner.seq_files = []
        scanner.pex_files = []
        scanner.dll_files = []
        scanner.count = 0
        
        if len(scanner.all_files) > 500000:
            split = 500
        elif len(scanner.all_files) > 50000:
            split = 50
        else:
            split = 5

        chunk_size = len(scanner.all_files) // split
        chunks = [scanner.all_files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(scanner.all_files[(split) * chunk_size:])

        print('-  Getting masters of loose files...\n\n')
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
            thread = threading.Thread(target=scanner.file_reader,args=(pattern2, file, 'rb'))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        print("-  Scanning .bsa files\n\n")
        scanner.file_count = len(scanner.bsa_files)
        scanner.count = 0
        if len(scanner.bsa_files) > 10:
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


    def bsa_processor(files):
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count/scanner.file_count) * 100
            print('\033[F\033[K-    Processed: ' + str(round(scanner.percentage, 1)) + '%' + '\n-    Files: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
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
            scanner.file_reader(pattern2, file, 'rb')

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
            if (file_lower.endswith(('.ini', '.json', '.psc', '.jslot', '.toml', '_conditions.txt')) or '_srd.' in file_lower):
                if 'modex\\user\\kits' in file_lower or 'nemesis_engine' in file_lower:
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
                plugin, _ = os.path.splitext(os.path.basename(file))
                scanner.seq_files.append([plugin.lower(), file])
            elif ('\\facegeom\\' in file_lower and '.nif' in file_lower):
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern3, file_lower).group(1)
                        if plugin not in local_dict.keys(): 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif '\\facetint\\' in file_lower and '.dds' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern4, file_lower).group(1)
                        if plugin not in local_dict.keys(): 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
            elif '\\sound\\' in file_lower and '\\voice\\' in file_lower:
                if '.esp' in file_lower or '.esm' in file_lower or '.esl' in file_lower:
                    try: 
                        plugin = re.search(pattern5, file_lower).group(1)
                        if plugin not in local_dict.keys(): 
                            local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: 
                            local_dict[plugin].append(file)
                    except Exception as e:
                        pass
                        
        for key, values_list in local_dict.items():
            with scanner.lock:
                if key not in scanner.file_dict: scanner.file_dict.update({key: []})
                scanner.file_dict[key].extend(values_list)

    def file_name_without_ext_processor(files):
        for file in files:
            esp, esl, esm = file[0] + '.esp', file[0] + '.esl', file[0] + '.esm'
            if esp in scanner.file_dict.keys():
                if file[1] not in scanner.file_dict[esp]: scanner.file_dict[esp].append(file[1])
            elif esl in scanner.file_dict.keys():
                if file[1] not in scanner.file_dict[esl]: scanner.file_dict[esl].append(file[1])
            elif esm in scanner.file_dict.keys():
                if file[1] not in scanner.file_dict[esm]: scanner.file_dict[esm].append(file[1])

    def file_reader(pattern, file, reader_type):
        if reader_type == 'r':
            if file.lower().endswith('.jslot'):
                with open(file, 'r', errors='ignore') as f:
                    data = json.load(f)
                    f.close()
                plugins = []
                if 'actor' in data.keys() and 'headTexture' in data['actor'].keys():
                    plugin_and_fid = data['actor']['headTexture']
                    plugins.append(plugin_and_fid[:-7].lower())
                
                if 'headParts' in data.keys():
                    for part in data['headParts']:
                        formIdentifier = part['formIdentifier']
                        plugins.append(formIdentifier[:-7].lower())
                for plugin in plugins:
                    with scanner.lock:
                        if plugin not in scanner.file_dict.keys(): scanner.file_dict.update({plugin: []})
                        if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
            else:
                with open(file, 'r', errors='ignore') as f:
                    r = re.findall(pattern,f.read().lower())
                    f.close()
                if r != []:
                    for plugin in r:
                        if 'NOT Is' not in plugin:
                            with scanner.lock:
                                if plugin not in scanner.file_dict.keys(): scanner.file_dict.update({plugin: []})
                                if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)
                elif 'bsa_extracted\\' in file and file.endswith('.psc'):
                    os.remove(file)

        if reader_type == 'rb':
            with open(file, 'rb') as f:
                r = re.findall(pattern,f.read().lower())
                f.close()
            if r != []:
                for plugin in r:
                    plugin = plugin.decode('utf-8')
                    if file.lower().endswith('.dll'):
                        with scanner.lock:
                            if plugin not in scanner.dll_dict.keys(): scanner.dll_dict.update({plugin: []})
                            if file not in scanner.dll_dict[plugin]: scanner.dll_dict[plugin].append(file)
                    else:
                        with scanner.lock:
                            if plugin not in scanner.file_dict.keys(): scanner.file_dict.update({plugin: []})
                            if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)

            elif 'bsa_extracted\\' in file and file.endswith('.pex'):
                os.remove(file)

    def bsa_reader(bsa_file):
        plugins = []
        with open(bsa_file, 'rb') as f:
            f.seek(16)
            folder_count = int.from_bytes(f.read(4)[::-1])
            f.seek(8,1)
            total_file_name_length = int.from_bytes(f.read(4)[::-1])
            f.seek(0)
            data = f.read()

        end_of_folder_records = (folder_count * 24) + 36
        offset = 36
        pattern_1 = re.compile(r'([^\\]+\.es[pml])')

        while offset < end_of_folder_records:
            location = int.from_bytes(data[offset+16:offset+20][::-1]) - total_file_name_length
            folder_length = int.from_bytes(data[location:location+1])
            folder_path = data[location+1:location+folder_length].decode(errors='ignore')
            if ('facegeom\\' in folder_path or 'facetint\\' in folder_path or 'sound\\voice' in folder_path) and ('.esp' in folder_path or '.esl' in folder_path or '.esm' in folder_path):
                plugin = re.search(pattern_1, folder_path).group(0)
                if plugin not in plugins:
                    plugins.append(plugin)

            offset += 24

        if plugins != []:
            scanner.bsa_dict[bsa_file] = plugins