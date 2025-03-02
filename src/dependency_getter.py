import os
import regex as re
import json

class dependecy_getter():
    bsa_list = []
    def scan(path):
        dependecy_getter.dependency_dictionary = {}
        dependecy_getter.plugins = dependecy_getter.get_from_file("ESLifier_Data/plugin_list.json")
        dependecy_getter.create_dependency_dictionary()
        dependecy_getter.dump_to_file("ESLifier_Data/dependency_dictionary.json")
        return dependecy_getter.dependency_dictionary
    
    def dump_to_file(file):
        with open(file, 'w+', encoding='utf-8') as f:
            json.dump(dependecy_getter.dependency_dictionary, f, ensure_ascii=False, indent=4)
    
    def get_from_file(file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = []
        return data
    
    def create_dependency_dictionary():
        plugin_names = []
        for plugin in dependecy_getter.plugins:
            plugin_names.append(os.path.basename(plugin).lower())

        dependecy_getter.dependency_dictionary = {plugin: [] for plugin in plugin_names}
        for plugin in dependecy_getter.plugins:
            masters = dependecy_getter.get_masters(plugin)
            if len(masters) > 0:
                for master in masters:
                    if master.lower() not in dependecy_getter.dependency_dictionary.keys():
                        dependecy_getter.dependency_dictionary[master.lower()] = []
                    if plugin not in dependecy_getter.dependency_dictionary[master.lower()]:
                        dependecy_getter.dependency_dictionary[master.lower()].append(plugin)

    def get_masters(file):
        master_list = []
        with open(file, 'rb') as f:
            f.seek(4)
            size = int.from_bytes(f.read(4)[::-1])
            f.seek(0)
            tes4_header = f.read(size + 24)
            data_list = re.split(b'MAST..',tes4_header)
            data_list.remove(data_list[0])
            for master in data_list:
                master_list.append(re.sub(b'.DATA.*', b'', master, flags=re.DOTALL).decode('utf-8'))

        return master_list
