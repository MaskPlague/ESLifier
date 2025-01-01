import os
import re
import threading
import dependency_getter as dep_getter
import timeit #TODO: Remove
import json


class scanner():
    def __init__(self, path):
        #TODO: for each compacted file, make a file with a list of patched files. Compare patched vs unpatched to get new files.
        #TODO: maybe convert to PyQt threading if necessary? plz no.
        start_time = timeit.default_timer()
        self.path = path
        #self.path = 'fakemodsfolder/'
        self.path = 'D:/Modding/MO2/mods'
        self.file_count = 0
        self.all_files = []
        self.lock = threading.Lock()
        for root, _, files in os.walk(self.path):
            self.file_count += len(files)
            for file in files:
                self.all_files.append(os.path.join(root, file).lower())

        print('')
        self.get_file_masters()

        self.dump_to_file(file="C:/Users/s34ke/Desktop/qual checker/dict.json")

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print('\nTime taken: ' + str(round(time_taken,2)) + ' seconds')

    def dump_to_file(self, file):
        with open(file, 'w+', encoding='utf-8') as f:
            json.dump(self.file_dict, f, ensure_ascii=False, indent=4)
    
    def get_from_file(self,file):
        data = {} #TODO: Some form of verification?
        with open(file, 'r') as f:
            data = json.load(f)
        return data

    def get_file_masters(self):
        #dg = dep_getter.dependecy_getter(self.path)
        #plugins = dg.plugins
        plugins = dep_getter.dependecy_getter.get_list_of_plugins(self.path)
        plugin_names = []
        for plugin in plugins: plugin_names.append(os.path.basename(plugin).lower())
        pattern = re.compile(r'(?:~|: *|\||=|,|-)\s*(?:\(?([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\)?)(?:\||,|$)')
        pattern2 = re.compile(rb'\x00.([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\x00')
        pattern3 = re.compile(r'\\facegeom\\([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\\')
        pattern4 = re.compile(r'\\facetint\\([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\\')
        pattern5 = re.compile(r'\\sound\\voice\\([a-z0-9\_\'\-\?\!\(\)\[\]\, ]+\.es[pml])\\')
        self.file_dict = {plugin: [] for plugin in plugin_names}
        self.threads = []
        self.seq_files = []
        self.pex_files = []
        self.bsa_list = []
        self.count = 0
        
        if len(self.all_files) > 500000:
            split = 500
        elif len(self.all_files) > 50000:
            split = 50
        else:
            split = 5

        chunk_size = len(self.all_files) // split
        chunks = [self.all_files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(self.all_files[(split) * chunk_size:])
        
        for chunk in chunks:
            thread = threading.Thread(target=self.file_processor, args=(chunk, pattern, pattern3, pattern4, pattern5))
            self.threads.append(thread)
            thread.start()
        
        for thread in self.threads: thread.join()

        self.file_name_without_ext_processor(self.seq_files)
        
        self.threads = []

        for file in self.pex_files:
            thread = threading.Thread(target=self.file_reader,args=(pattern2, file, 'rb'))
            self.threads.append(thread)
            thread.start()

        for thread in self.threads: thread.join()

    def file_processor(self, files, pattern, pattern3, pattern4, pattern5):
        local_dict = {}
        for file in files:
            self.count += 1
            self.percentage = (self.count / self.file_count) * 100
            print("\033[F\033[K", end="")
            print('Processed: ' + str(round(self.percentage, 1)) + '%' + '\nFiles: ' + str(self.count) + '/' + str(self.file_count), end='\r')
            if '.bsa' in file:
                self.bsa_list.append(file)
            elif (not 'meta.ini' in file) and ('.ini' in file or '.json' in file or '_conditions.txt' in file or '_srd.' in file or '.psc' in file):
                thread = threading.Thread(target=self.file_reader,args=(pattern, file, 'r'))
                self.threads.append(thread)
                thread.start()
            elif '.pex' in file:
                self.pex_files.append(file)
            elif '.seq' in file:
                plugin, _ = os.path.splitext(os.path.basename(file))
                self.seq_files.append([plugin, file])
            elif ('\\facegeom\\' in file and '.nif' in file):
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern3, file).group(1)
                        if plugin not in local_dict.keys(): local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: local_dict[plugin].append(file)
                    except:
                        print(file)
            elif '\\facetint\\' in file and '.dds' in file:
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern4, file).group(1)
                        if plugin not in local_dict.keys(): local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: local_dict[plugin].append(file)
                    except:
                        print(file)
            elif '\\sound\\' in file and '\\voice\\' in file:
                if '.esp' in file or '.esm' in file or '.esl' in file:
                    try: 
                        plugin = re.search(pattern5, file).group(1)
                        if plugin not in local_dict.keys(): local_dict.update({plugin: []})
                        if file not in local_dict[plugin]: local_dict[plugin].append(file)
                    except:
                        print(file)
                        
        for key, values_list in local_dict.items():
            with self.lock:
                if key not in self.file_dict: self.file_dict.update({key: []})
                self.file_dict[key].extend(values_list)
    
    def search_file_name(self, file, pattern):
        try: 
            plugin = re.search(pattern, file).group()
            with self.lock:
                if plugin not in self.file_dict.keys(): self.file_dict.update({plugin: []})
                if file not in self.file_dict[plugin]: self.file_dict[plugin].append(file)
        except:
            print(file)

    def file_name_without_ext_processor(self, files):
        for file in files:
            esp, esl, esm = file[0] + '.esp', file[0] + '.esl', file[0] + '.esm'
            if esp in self.file_dict.keys():
                if file[1] not in self.file_dict[esp]: self.file_dict[esp].append(file[1])
            elif esl in self.file_dict.keys():
                if file[1] not in self.file_dict[esl]: self.file_dict[esl].append(file[1])
            elif esm in self.file_dict.keys():
                if file[1] not in self.file_dict[esm]: self.file_dict[esm].append(file[1])

    def file_reader(self, pattern, file, reader_type):
        if reader_type == 'r':
            with open(file, 'r', errors='ignore') as f:
                r = re.findall(pattern,f.read().lower())
                if r != []:
                    for plugin in r:
                        if 'NOT Is' not in plugin:
                            with self.lock:
                                if plugin not in self.file_dict.keys(): self.file_dict.update({plugin: []})
                                if file not in self.file_dict[plugin]: self.file_dict[plugin].append(file)

        if reader_type == 'rb':
            with open(file, 'rb') as f:
                r = re.findall(pattern,f.read().lower())
                if r != []:
                    for plugin in r:
                        plugin = plugin.decode('utf-8')
                        with self.lock:
                            if plugin not in self.file_dict.keys(): self.file_dict.update({plugin: []})
                            if file not in self.file_dict[plugin]: self.file_dict[plugin].append(file)

    def get_all_files(self):
        for root, dirs, files in os.walk(self.path):
            for file in files:
                yield os.path.join(root,file)

s = scanner('')
