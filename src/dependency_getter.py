import os
import re
import json

class dependecy_getter():    
    def __init__(self, path):
        self.plugins = self.get_list_of_plugins(path)
        self.create_dependecy_dictionary()
        self.dump_to_file("ESLifier_Data/dependency_dictionary.json")

    def get_list_of_plugins(path):
        plugins = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if re.search(r'\.es[pml]$', file):
                    plugins.append(os.path.join(root,file).lower())
        return plugins
    
    def dump_to_file(self, file):
        with open(file, 'w+', encoding='utf-8') as f:
            json.dump(self.dictionary, f, ensure_ascii=False, indent=4)
    
    def get_from_file(self, file):
        data = {}
        with open(file, 'r') as f:
            data = json.load(f)
        return data
    
    def create_dependecy_dictionary(self):
        plugin_names = []
        for plugin in self.plugins:
            plugin_names.append(os.path.basename(plugin))
            plugin_names.append(os.path.basename(plugin) + '_path')

        self.dependency_dictionary = {plugin: [] for plugin in plugin_names}
        for plugin in self.plugins:
            self.dependency_dictionary[os.path.basename(plugin) + '_path'] = plugin
            masters = self.getMasters(plugin)
            if len(masters) > 0:
                for master in masters:
                    if plugin not in self.dependency_dictionary[master]:
                        self.dependency_dictionary[master].append(plugin)

    def getMasters(self, file):
        masterList = []
        with open(file, 'rb') as f:
            f.seek(4)
            size = int.from_bytes(f.read(4)[::-1])
            f.seek(0)
            tes4Header = f.read(size + 24)
            dataList = re.split(b'MAST..',tes4Header)
            dataList.remove(dataList[0])
            for master in dataList:
                masterList.append(re.sub(b'.DATA.*', b'', master, flags=re.DOTALL).decode('utf-8'))

        return masterList
