import os
import re
import json

class dependecy_getter():
    bsa_list = []
    def scan(path):
        dependecy_getter.bsa_list = []
        dependecy_getter.dependency_dictionary = {}
        dependecy_getter.plugins = dependecy_getter.get_list_of_plugins(path)
        dependecy_getter.create_dependency_dictionary()
        dependecy_getter.dependency_dictionary['BSA_list'] = dependecy_getter.bsa_list
        dependecy_getter.dump_to_file("ESLifier_Data/dependency_dictionary.json")
        return dependecy_getter.dependency_dictionary

    def get_list_of_plugins(path):
        plugins = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if re.search(r'\.es[pml]$', file) and not '\\optional' in root.lower():
                    plugins.append(os.path.join(root,file))
                elif '.bsa' in file.lower():
                    dependecy_getter.bsa_list.append(file.lower())
        return plugins
    
    def dump_to_file(file):
        with open(file, 'w+', encoding='utf-8') as f:
            json.dump(dependecy_getter.dependency_dictionary, f, ensure_ascii=False, indent=4)
    
    def get_from_file(file):
        data = {}
        with open(file, 'r') as f:
            data = json.load(f)
        return data
    
    def create_dependency_dictionary():
        plugin_names = []
        for plugin in dependecy_getter.plugins:
            plugin_names.append(os.path.basename(plugin).lower())
            #plugin_names.append(os.path.basename(plugin).lower() + '_path')

        dependecy_getter.dependency_dictionary = {plugin: [] for plugin in plugin_names}
        for plugin in dependecy_getter.plugins:
            #dependecy_getter.dependency_dictionary[os.path.basename(plugin).lower() + '_path'] = plugin
            masters = dependecy_getter.getMasters(plugin)
            if len(masters) > 0:
                for master in masters:
                    if master.lower() not in dependecy_getter.dependency_dictionary.keys():
                        dependecy_getter.dependency_dictionary[master.lower()] = []
                    if plugin not in dependecy_getter.dependency_dictionary[master.lower()]:
                        dependecy_getter.dependency_dictionary[master.lower()].append(plugin.lower())

    def getMasters(file):
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
