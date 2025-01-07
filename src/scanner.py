import os
import re
import threading
import dependency_getter as dep_getter
import timeit #TODO: Remove
import json


class scanner():
    def __init__(self, path):
        scanner.path = path
        start_time = timeit.default_timer()
        scanner.file_count = 0
        scanner.all_files = []
        scanner.lock = threading.Lock()
        print('Gathering Files...')
        for root, _, files in os.walk(scanner.path):
            scanner.file_count += len(files)
            for file in files:
                scanner.all_files.append(os.path.join(root, file))

        scanner.get_file_masters()

        scanner.dump_to_file(file="ESLifier_Data/file_masters.json")

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print('\nTime taken: ' + str(round(time_taken,2)) + ' seconds')

    def dump_to_file(file):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(scanner.file_dict, f, ensure_ascii=False, indent=4)
    
    def get_from_file(file):
        data = {} #TODO: Some form of verification?
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def get_file_masters():
        plugins = dep_getter.dependecy_getter.get_list_of_plugins(scanner.path)
        plugin_names = []
        for plugin in plugins: plugin_names.append(os.path.basename(plugin).lower())
        pattern = re.compile(r'(?:~|: *|\||=|,|-|")\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\)?)(?:\||,|"|$)')
        pattern2 = re.compile(rb'\x00.([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\x00')
        pattern3 = re.compile(r'\\facegeom\\([a-zA-Z0-9_\-\'\?\!\(\)\[\]\, \u0080-\uffff]+\.es[pml])\\')
        pattern4 = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\, \u0080-\uffff]+\.es[pml])\\')
        pattern5 = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\, \u0080-\uffff]+\.es[pml])\\')
        scanner.file_dict = {plugin: [] for plugin in plugin_names}
        scanner.threads = []
        scanner.seq_files = []
        scanner.pex_files = []
        scanner.bsa_list = []
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
        
        for chunk in chunks:
            thread = threading.Thread(target=scanner.file_processor, args=(chunk, pattern, pattern3, pattern4, pattern5))
            scanner.threads.append(thread)
            thread.start()
        
        for thread in scanner.threads: thread.join()

        scanner.file_name_without_ext_processor(scanner.seq_files)
        
        scanner.threads = []

        for file in scanner.pex_files:
            thread = threading.Thread(target=scanner.file_reader,args=(pattern2, file, 'rb'))
            scanner.threads.append(thread)
            thread.start()

        for thread in scanner.threads: thread.join()

    def file_processor(files, pattern, pattern3, pattern4, pattern5):
        local_dict = {}
        for file in files:
            scanner.count += 1
            scanner.percentage = (scanner.count / scanner.file_count) * 100
            print("\033[F\033[K", end="")
            print('Processed: ' + str(round(scanner.percentage, 1)) + '%' + '\nFiles: ' + str(scanner.count) + '/' + str(scanner.file_count), end='\r')
            if '.bsa' in file:
                scanner.bsa_list.append(file)
            elif (not 'meta.ini' in file) and ('.ini' in file or '.json' in file or '_conditions.txt' in file or '_srd.' in file or '.psc' in file):
                thread = threading.Thread(target=scanner.file_reader,args=(pattern, file, 'r'))
                scanner.threads.append(thread)
                thread.start()
            elif '.pex' in file:
                scanner.pex_files.append(file)
            elif '.seq' in file:
                plugin, _ = os.path.splitext(os.path.basename(file))
                scanner.seq_files.append([plugin, file])
            elif ('\\facegeom\\' in file and '.nif' in file):
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern3, file).group(1)
                        if plugin.lower() not in local_dict.keys(): 
                            local_dict.update({plugin.lower(): []})
                        if file not in local_dict[plugin.lower()]: 
                            local_dict[plugin.lower()].append(file)
                    except Exception as e:
                        print(e)
                        print(file)
                        print('\n')
            elif '\\facetint\\' in file and '.dds' in file:
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern4, file).group(1)
                        if plugin.lower() not in local_dict.keys(): 
                            local_dict.update({plugin.lower(): []})
                        if file not in local_dict[plugin.lower()]: 
                            local_dict[plugin.lower()].append(file)
                    except Exception as e:
                        print(e)
                        print(file)
                        print('\n')
            elif '\\sound\\' in file and '\\voice\\' in file:
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern5, file).group(1)
                        if plugin.lower() not in local_dict.keys(): 
                            local_dict.update({plugin.lower(): []})
                        if file not in local_dict[plugin.lower()]: 
                            local_dict[plugin.lower()].append(file)
                    except Exception as e:
                        print(e)
                        print(file)
                        print('\n')
                        
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
            with open(file, 'r', errors='ignore') as f:
                r = re.findall(pattern,f.read().lower())
                if r != []:
                    for plugin in r:
                        if 'NOT Is' not in plugin:
                            with scanner.lock:
                                if plugin not in scanner.file_dict.keys(): scanner.file_dict.update({plugin: []})
                                if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)

        if reader_type == 'rb':
            with open(file, 'rb') as f:
                r = re.findall(pattern,f.read().lower())
                if r != []:
                    for plugin in r:
                        plugin = plugin.decode('utf-8')
                        with scanner.lock:
                            if plugin not in scanner.file_dict.keys(): scanner.file_dict.update({plugin: []})
                            if file not in scanner.file_dict[plugin]: scanner.file_dict[plugin].append(file)

    def get_all_files():
        for root, dirs, files in os.walk(scanner.path):
            for file in files:
                yield os.path.join(root,file)

#s = scanner()
