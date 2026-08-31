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
import pefile

from data_holder import _global
from scanner_mo2 import MO2
from scanner_none import NoManager
from scanner_vortex import Vortex

if platform.system() == 'Windows':
    from win32 import win32file
    win32file._setmaxstdio(8192)
    WINDOWS = True
else:
    WINDOWS = False

from plugin_qualification_checker import qualification_checker
from dependency_getter import dependecy_getter
from log_stream import write_error, write_normal, write_progress, write_remove, write_to_file, write_warning

from PyQt6.QtCore import QCoreApplication

class scanner():    
    def scan(full_scan: bool) -> tuple[dict, dict] | None:
        scanner.bsa_blacklist = set(['skyrim - misc.bsa', 'skyrim - shaders.bsa', 'skyrim - interface.bsa', 'skyrim - animations.bsa', 'skyrim - meshes0.bsa', 'skyrim - meshes1.bsa',
                    'skyrim - sounds.bsa', 'skyrim - voices_en0.bsa', 'skyrim - textures0.bsa', 'skyrim - textures1.bsa', 'skyrim - textures2.bsa', 'skyrim - textures3.bsa',
                    'skyrim - textures4.bsa', 'skyrim - textures5.bsa', 'skyrim - textures6.bsa', 'skyrim - textures7.bsa', 'skyrim - textures8.bsa', 'skyrim - patch.bsa'])
        start_time = timeit.default_timer()
        scanner.mod_manager_mode: int = _global.mod_manager_mode
        scanner.output_file_name = _global.output_folder_name
        scanner.all_patcher_experimental: bool = _global.all_patcher_experimental
        if scanner.all_patcher_experimental:
            write_to_file("Experimental all patcher mode enabled.")
        if not os.path.exists('bsa_extracted'):
            os.makedirs('bsa_extracted')
        scanner.file_count: int = 0
        scanner.all_files: list[str] = []
        _global.plugins.clear()
        _global.mods_with_seq.clear()
        scanner.file_dict: dict[str, set[str]] = {}
        scanner.bsa_dict: dict[str, list[str]] = {}
        scanner.dll_dict: dict[str, list[str]] = {}
        scanner.bsa_files: list[str] = []
        scanner.winning_files_dict: dict[str, list[str]] = {}
        scanner.threads: list[threading.Thread] = []
        scanner.seq_files: list[str] = []
        scanner.pex_files: list[str] = []
        scanner.dll_files: list[str] = []
        scanner.lock = threading.Lock()
        if not os.path.exists("ESLifier_Data/ignored_files.json"):
            with open("ESLifier_data/ignored_files.json", "w+", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=3)
        master_ignored_file_data = scanner.get_from_file("ESLifier_Data/master_ignored_files.json", dict)
        master_ignored_files = [item.lower() for item in master_ignored_file_data.get("ignored_files", [])]
        user_ignored_files = [item.lower() for item in scanner.get_from_file("ESLifier_Data/ignored_files.json", list)]
        master_ignored_files.extend(user_ignored_files)

        scanner.ignored_files = set(master_ignored_files)
        scanner.file_extensions = tuple([item.lower() for item in ('.ini', '.json', '.jslot', '.toml', '_conditions.txt', '.yaml', '.yml')])

        exclude_contains = [item.lower() for item in (
            'modex\\user\\kits',
            'nemesis_engine',
            'quickarmorrebalance\\config\\',
            'equipmenttoggle\\slotdata\\',
            '\\headpartwhitelist\\',
            '\\interface\\quests\\'
            )]
        exclude_contains.extend([os.path.normpath(item).lower() for item in master_ignored_file_data.get("ignored_contains", [])])
        scanner.exclude_contains = tuple(exclude_contains)

        exclude_endswith = [item.lower() for item in (
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
            )]
        exclude_endswith.extend([os.path.normpath(item).lower() for item in master_ignored_file_data.get("ignored_endswith", [])])
        scanner.exclude_endswith = tuple(exclude_endswith)

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

        scanner.extracted: set[str] = set(scanner.get_from_file('ESLifier_Data/extracted_bsa.json', list))
        
        if scanner.mod_manager_mode == 2: # MO2
            MO2.scanner = scanner
            _global.get_paths()
            if _global.mo2_error != None:
                return {}, {}
            plugins_list = scanner.get_plugins_list(_global.plugins_txt_path)
            scanner.all_files, _global.plugins = MO2.get_winning_files(plugins_list)
            scanner.file_count = len(scanner.all_files)
        elif scanner.mod_manager_mode == 1: # Vortex
            #likely do the get files from skyrim folder at the same time as scanning vortex mod staging folder, if not exists in mod staging then add to dict
            Vortex.scanner = scanner
            scanner.all_files, _global.plugins, plugins_list = Vortex.get_winning_files()
            scanner.file_count = len(scanner.all_files)
            if _global.vortex_error != None:
                return {}, {}
        else: #Manually modding?
            NoManager.scanner = scanner
            plugins_list = scanner.get_plugins_list(_global.plugins_txt_path)
            NoManager.get_files_from_skyrim_folder(_global.skyrim_folder_path, plugins_list)

        scanner.plugin_basename_set: set[str] = set([os.path.basename(plugin).lower() for plugin in _global.plugins])
        scanner.max_plugin_len = max((len(p) for p in scanner.plugin_basename_set), default=0)

        scanner.dump_to_file(file="ESLifier_Data/extracted_bsa.json", data=scanner.extracted)
        scanner.dump_to_file(file="ESLifier_Data/winning_files_dict.json", data=scanner.winning_files_dict)

        write_remove(1, "-  " + QCoreApplication.translate("scanner", "Gathered %0 total files.").replace("%0", str(len(scanner.all_files))), True)
        if full_scan:
            write_normal(QCoreApplication.translate("scanner", 'Getting Dependencies'))
            dependency_dictionary = dependecy_getter.scan()
            write_normal(QCoreApplication.translate("scanner", 'Scanning Plugins'))
            flag_dict = qualification_checker.scan()

        scanner.get_file_masters()

        _global.bsa_dict = scanner.sort_bsa_files(scanner.bsa_dict, plugins_list)

        scanner.dump_to_file(file="ESLifier_Data/file_masters.json", data=scanner.file_dict)
        #scanner.dump_to_file(file="ESLifier_Data/bsa_dict.json", data=bsa_dict)
        scanner.dump_to_file(file="ESLifier_Data/dll_dict.json", data=scanner.dll_dict)

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        write_normal('-  ' + QCoreApplication.translate("scanner", 'Time taken: %1 seconds').replace("%1", str(round(time_taken,2))))
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

    def extract_bsa(file: str, startupinfo: subprocess.STARTUPINFO, update_time: float, filter: str):
        last = 0
        extracting_str = "-  " + QCoreApplication.translate("scanner", "Extracting: ")
        with subprocess.Popen(
            ["bsarch/bsarch.exe", "unpack", file, "bsa_extracted", filter],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            text=True
            ) as p:
                for line in p.stdout:
                    if line.startswith('Unpacking error'):
                        write_remove(1, line, True)
                        raise Exception("Occured during unpacking via modified BSArch.exe")
                    if timeit.default_timer() - last > update_time:
                        last = timeit.default_timer()
                        write_remove(1, extracting_str + line)

    def extract_scripts_and_seq_from_bsa(bsa_list, plugins_list):
        order_map = {plugin: index for index, plugin in enumerate(plugins_list)}
        filtered_bsa_list = [item for item in bsa_list if item[0] in order_map]
        filtered_bsa_list.sort(key=lambda x: order_map.get(x[0], float('inf')))
        scanner.bsa_files = [file for _, file in filtered_bsa_list]
        bsa_length = len(filtered_bsa_list)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        update_time = 0.1
        extracting_str = QCoreApplication.translate("scanner", "Extracting %0/%1 BSA files (%2)").replace("%0", "{0}").replace("%1", "{1}").replace("%2", "{2}")
        #Extract Files from BSA
        for i, tup in enumerate(filtered_bsa_list):
            file = tup[1]
            if file not in scanner.extracted:
                write_remove(1, extracting_str.format(i+1, bsa_length, os.path.basename(file)), True)
                write_normal("",False)
                try:
                    scanner.extract_bsa(file, startupinfo, update_time, ".pex")
                    scanner.extract_bsa(file, startupinfo, update_time, ".seq")
                    scanner.extracted.add(file)
                except Exception as e:
                    write_error(QCoreApplication.translate("scanner", "Error Reading BSA: ") + file)
                    write_error(e, True)
                write_remove(2, "")
    
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
            write_error(QCoreApplication.translate("scanner", "Failed to get plugins list at: ") + path)
            write_error(e, True)
            return []
        return active_plugins

    def dump_to_file(file: str, data: list | dict | set):
        if isinstance(data, dict):
            to_dump = {}
            for key, value in data.items():
                if isinstance(value, set):
                    to_dump.update({key: list(value)})
                else:
                    to_dump.update({key: value})
        else:
            to_dump = list(data)
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(to_dump, f, ensure_ascii=False, indent=4)
        except Exception as e:
            write_error(QCoreApplication.translate("Global", "Failed to dump data to: ") + file)
            write_error(e, True)
    
    def get_from_file(file: str, type: dict | list) -> list[str] | dict[str]:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data: list[str] | dict[str] = json.load(f)
        except:
            data: list[str] | dict[str] = type()
        return data

    def get_file_masters():
        #Regex is slow so this is unused. I'm leaving it here in case I have a future use for it as these are fairly robust patterns
        #unused_plugin_pattern = re.compile(r'(?:~|:\s*|\||=|,|-|"|\*)\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\,\s]+\.es[pml])\)?)\s*(?:\||,|"|$|\n)')
        #facegeom_pattern = re.compile(r'\\facegeom\\([a-zA-Z0-9_\-\'\?\!\(\)\[\]\,\s\.]+\.es[pml])\\')
        #facetint_pattern = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s\.]+\.es[pml])\\')
        #voice_pattern = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\,\s\.]+\.es[pml])\\')
        dll_byte_pattern = re.compile(rb'\x00([a-z0-9\_\'\-\?\!\(\)\[\]\,\s\.]+\.es[pml])\x00', flags=re.DOTALL)
        scanner.file_dict = {plugin: set() for plugin in scanner.plugin_basename_set}
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

        write_normal(QCoreApplication.translate("scanner", 'Getting masters of loose files...'))
        write_normal("", False)
        for chunk in chunks:
            thread = threading.Thread(target=scanner.file_processor, args=(chunk,))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        write_remove(1, "-  " + QCoreApplication.translate("scanner", "Scanning .pex files"), True)
        write_normal("", False)
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
            thread = threading.Thread(target=scanner.pex_processor, args=(dll_byte_pattern, chunk,))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        write_remove(1, "-  " + QCoreApplication.translate("scanner", "Scanning .dll SKSE plugins"), True)
        for file in scanner.dll_files:
            thread = threading.Thread(target=scanner.file_reader,args=(dll_byte_pattern, file, 'dll'))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()
        scanner.threads.clear()

        write_normal("-  " + QCoreApplication.translate("scanner", "Sorting .seq files"))
        scanner.seq_plugin_extension_processor(scanner.seq_files)

        write_normal("-  " + QCoreApplication.translate("scanner", "Scanning .bsa files"))

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
        
    def bsa_processor(files):
        for file in files:
            scanner.bsa_reader(file)

    def pex_processor(pattern2, files):
        processed_string = ('-  ' + QCoreApplication.translate("scanner", "Processed: %0 %") +
                            '\n-  ' + QCoreApplication.translate("scanner", "Files: %1/%2")).replace("%0", "{0}").replace("%1", "{1}").replace("%2", "{2}")
        for file in files:
            scanner.count += 1
            factor = round(scanner.file_count * 0.01)
            if factor == 0:
                factor = 1
            if (scanner.count % factor) >= (factor-1):
                scanner.percentage = round((scanner.count / scanner.file_count) * 100, 1)
                write_progress(round(scanner.percentage), 1, processed_string.format(scanner.percentage, scanner.count, scanner.file_count))
            scanner.file_reader(pattern2, file, 'pex')

    def file_processor(files: list[str]):
        local_dict: dict[str, set[str]] = {}
        local_pex: list[str] = []
        local_dll: list[str] = []
        local_seq: list[str] = []
        processed_string = ('-  ' + QCoreApplication.translate("scanner", "Processed: %0 %") +
                            '\n-  ' + QCoreApplication.translate("scanner", "Files: %1/%2")).replace("%0", "{0}").replace("%1", "{1}").replace("%2", "{2}")
        for file in files:
            scanner.count += 1
            file_lower = file.lower()
            factor = round(scanner.file_count * 0.01)
            if factor == 0:
                factor = 1
            if (scanner.count % factor) >= (factor-1):
                scanner.percentage = round((scanner.count / scanner.file_count) * 100, 1)
                write_progress(round(scanner.percentage), 1, processed_string.format(scanner.percentage, scanner.count, scanner.file_count))
            if ((file_lower.endswith(scanner.file_extensions) 
                 or (file_lower.endswith('config.txt') and 'plugins\\customskill' in file_lower))
                 and not (any(exclusion in file_lower for exclusion in scanner.exclude_contains) 
                          or file_lower.endswith(scanner.exclude_endswith))
                ):
                scanner.file_reader(None, file, 'r')
            elif file_lower.endswith('.pex'):
                local_pex.append(file)
            elif file_lower.endswith('.dll') and '\\skse\\plugins' in file_lower:
                local_dll.append(file)
            elif file_lower.endswith('.seq'):
                plugin = os.path.splitext(os.path.basename(file))[0]
                local_seq.append([plugin.lower(), file])
            elif file_lower.endswith('.nif') and '\\facegeom\\' in file_lower and '.es' in file_lower:
                plugin = file_lower.split('\\facegeom\\')[1].split(os.sep)[0]
                if plugin.endswith(('.esp', '.esl', '.esm')):
                    if plugin not in local_dict:
                        local_dict[plugin] = set()
                    local_dict[plugin].add(file)
            elif file_lower.endswith('.dds') and '\\facetint\\' in file_lower and '.es' in file_lower:
                plugin = file_lower.split('\\facetint\\')[1].split(os.sep)[0]
                if plugin.endswith(('.esp', '.esl', '.esm')):
                    if plugin not in local_dict:
                        local_dict[plugin] = set()
                    local_dict[plugin].add(file)
            elif '\\sound\\voice\\' in file_lower and '.es' in file_lower:
                plugin = file_lower.split('\\sound\\voice\\')[1].split(os.sep)[0]
                if plugin.endswith(('.esp', '.esl', '.esm')):
                    if plugin not in local_dict:
                        local_dict[plugin] = set()
                    local_dict[plugin].add(file)
            elif (scanner.all_patcher_experimental 
                  and not file_lower.endswith(
                      ('.psc', '.tri', '.nif', '.dds', '.osd', '.osp', '.hkx', '.pdb', '.dll', '.esp', '.esl', '.esm',
                       '.swf', '.wav', '.ttf', '.bin', '.bsa', '.exe', '.modgroups', '.jpg', '.png', '.lua', '.refcache',
                       '.fla', '.bsl', '.html', '.bak', '.psd', '.log', '.cdf'))
                  and not (any(excl in file_lower for excl in ['dialogueviews', '\\calientetools\\bodyslide']))
                  and not (any(exclusion in file_lower for exclusion in scanner.exclude_contains) 
                          or file_lower.endswith(scanner.exclude_endswith))
                 ):
                thread = threading.Thread(target=scanner.file_reader,args=(None, file, 'r'))
                scanner.threads.append(thread)
                thread.start()
                scanner.file_reader(None, file, 'r')
        with scanner.lock:     
            scanner.pex_files.extend(local_pex)
            scanner.seq_files.extend(local_seq)
            scanner.dll_files.extend(local_dll)      
            for key, values_list in local_dict.items():
                if key in scanner.plugin_basename_set:
                    if key not in scanner.file_dict:
                        scanner.file_dict.update({key: set()})
                    scanner.file_dict[key].update(values_list)

    def seq_plugin_extension_processor(files):
        for file in files:
            esp, esl, esm = file[0] + '.esp', file[0] + '.esl', file[0] + '.esm'
            if esp in scanner.file_dict:
                _global.mods_with_seq[esp] = file[1]
                scanner.file_dict[esp].add(file[1])
            elif esl in scanner.file_dict:
                _global.mods_with_seq[esl] = file[1]
                scanner.file_dict[esl].add(file[1])
            elif esm in scanner.file_dict:
                _global.mods_with_seq[esm] = file[1]
                scanner.file_dict[esm].add(file[1])

    def check_if_modbyname_uses_plugin_names(data: bytes, plugins: set[str], file: str, offset: int, strings: list[bytes]):
        plugin_bytes = []
        plugins_indexes = {}
        for plugin in plugins:
            plugin_bytes.append([plugin.encode(), plugin])
        for plugin_name_bytes, plugin_name in plugin_bytes:
            if plugin_name_bytes in strings:
                plugins_indexes[strings.index(plugin_name_bytes).to_bytes(2)] = plugin_name
        getmodbyname_index = strings.index(b'getmodbyname').to_bytes(2)
        data_size = len(data)
        while offset < data_size:
            if data[offset:offset+2] == getmodbyname_index and data[offset+10:offset+11] == b'\x02':
                plugin_name = plugins_indexes.get(data[offset+11:offset+13])
                if plugin_name:
                    if plugin_name not in _global.pex_with_getmodbyname:
                        _global.pex_with_getmodbyname[plugin_name] = set()
                    _global.pex_with_getmodbyname[plugin_name].add(file)
            offset += 1

    def file_reader(pattern, file: str, reader_type):
        try:
            file_lower = file.lower()
            if reader_type == 'r':
                if file_lower.endswith('.jslot'):
                    with scanner.file_semaphore:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            read_string = f.read()
                            #while read_string[-1] != '}':
                            #    read_string = read_string.removesuffix(read_string[-1])
                            index = read_string.rfind('}')
                            if index != -1: 
                                read_string = read_string[:index+1]
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
                            if plugin in scanner.plugin_basename_set:
                                if plugin not in scanner.file_dict: 
                                    scanner.file_dict.update({plugin: set()})
                                scanner.file_dict[plugin].add(file)
                else:
                    with scanner.file_semaphore:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            data = f.read().lower()
                            f.close()
                    lines = data.splitlines()
                    max_len = scanner.max_plugin_len
                    plugin_basename_set = scanner.plugin_basename_set

                    found_plugins = set()
                    for line in lines:
                        if '.es' in line:
                            index = 0
                            while True:
                                index = line.find('.es', index)
                                if index == -1:
                                    break
                                
                                ext = line[index:index+4]
                                if ext in ('.esp', '.esm', '.esl'):
                                    end_idx = index + 4
                                    search_start = max(0, end_idx - max_len)
                                    
                                    for start_idx in range(search_start, index):
                                        possible_plugin = line[start_idx:end_idx]
                                        if possible_plugin in plugin_basename_set:
                                            found_plugins.add(possible_plugin)
                                            break  
                                index += 3
                    file_lower = file.lower()
                    if file_lower.endswith('.json') and '\\luma\\' in file_lower:
                        found_plugins.add(file.split(os.sep)[-2].lower())
                    with scanner.lock:                  
                        for plugin in found_plugins:
                            if plugin not in scanner.file_dict: 
                                scanner.file_dict.update({plugin: set()})
                            scanner.file_dict[plugin].add(file)

            elif reader_type == 'pex':
                with scanner.file_semaphore:
                    with open(file, 'rb') as f:
                        data = f.read()
                offset = 18 + struct.unpack('>H', data[16:18])[0]
                offset += 2 + struct.unpack('>H', data[offset:offset+2])[0]
                offset += 2 + struct.unpack('>H', data[offset:offset+2])[0]
                string_count = struct.unpack('>H', data[offset:offset+2])[0]
                offset += 2
                strings = set()
                strings_lowered_bytes = []
                for _ in range(string_count):
                    string_length = struct.unpack('>H', data[offset:offset+2])[0]
                    string_lowered = data[offset+2:offset+2+string_length].lower()
                    strings_lowered_bytes.append(string_lowered)
                    strings.add(string_lowered.decode())
                    offset += 2 + string_length
                gfff = 'getformfromfile' in strings
                gmbn = 'getmodbyname' in strings
                if gfff or gmbn: #'getformfromfile' in strings: #or 'getmodbyname' in strings:
                    plugins = set()
                    for string in strings:
                        if string.endswith(('.esp', '.esl', '.esm')) and string in scanner.plugin_basename_set:#not ':' in string and not '/' in string and not '\\' in string:
                            with scanner.lock:
                                if gfff:
                                    if string not in scanner.file_dict: 
                                        scanner.file_dict[string] = set()
                                    scanner.file_dict[string].add(file)
                                if gmbn:
                                    plugins.add(string)
                    if gmbn:
                        scanner.check_if_modbyname_uses_plugin_names(data, plugins, file, offset, strings_lowered_bytes)

                elif 'bsa_extracted\\' in file:
                    os.remove(file)
            elif reader_type == 'dll':
                with scanner.file_semaphore:
                    if file.endswith('EngineFixes.dll'):
                        pe = pefile.PE(file)
                        if hasattr(pe, "VS_FIXEDFILEINFO"):
                            verinfo = pe.VS_FIXEDFILEINFO[0]
                            _global.engine_fixes_v7_or_newer =  verinfo.FileVersionMS >> 16 >= 7,
                    with open(file, 'rb') as f:
                        r = re.findall(pattern,f.read().lower())
                        f.close()
                if r != []:
                    with scanner.lock:
                        for plugin in r:
                            plugin = plugin.decode('utf-8')
                            if plugin in scanner.plugin_basename_set:
                                if plugin not in scanner.dll_dict: scanner.dll_dict.update({plugin: []})
                                if file not in scanner.dll_dict[plugin]: scanner.dll_dict[plugin].append(file)
            else:
                write_warning(QCoreApplication.translate("scanner", "Missing file scan type for ") + file)
        except Exception as e:
            write_error(QCoreApplication.translate("scanner", "Error reading file ") + file)
            if reader_type == 'pex':
                write_error(QCoreApplication.translate("scanner",'!pex file is likely corrupt.'))
            write_error(e, True)

    def bsa_reader(bsa_file):
        plugins = set()
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

                            #TODO: consider splitting this if statement into multiple and using split('thing')[1].split(sep)[0]
                            if ('facegeom\\' in folder_path or 'facetint\\' in folder_path or 'sound\\voice' in folder_path) and ('.esp' in folder_path or '.esl' in folder_path or '.esm' in folder_path):
                                match = re.search(pattern_1, folder_path.encode())
                                if match:
                                    plugin = match.group(0).decode()
                                    if plugin not in plugins:
                                        plugins.add(plugin)
                            time = timeit.default_timer() - start_time
                            offset += folder_record_size
                        if time > max_time:
                            raise ValueError(f'Exceeded max processing time for {bsa_file}')
                        mm.close()
                    f.close()

            if plugins:
                with scanner.lock:
                    scanner.bsa_dict[bsa_file] = list(plugins)
        except Exception as e:
            write_error(QCoreApplication.translate("scanner", "Error Reading BSA: ") + bsa_file)
            write_error(e, True)
