import os
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
        try:
            with open(file, 'w+', encoding='utf-8') as f:
                json.dump(dependecy_getter.dependency_dictionary, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"!Error: Failed to dump data to {file}")
    
    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
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
                    if master.lower() not in dependecy_getter.dependency_dictionary:
                        dependecy_getter.dependency_dictionary[master.lower()] = []
                    if plugin not in dependecy_getter.dependency_dictionary[master.lower()]:
                        dependecy_getter.dependency_dictionary[master.lower()].append(plugin)

    def get_masters(file):
        master_list = []
        try:
            with open(file, 'rb') as f:
                f.seek(4)
                tes4_size = int.from_bytes(f.read(4)[::-1]) + 24
                f.seek(0)
                tes4_record = f.read(tes4_size)
        except Exception as e:
            print(f"!Error: Failed to get master list of {file}")
            print(e)
            return []
        offset = 24
        while offset < tes4_size:
            field = tes4_record[offset:offset+4]
            field_size = int.from_bytes(tes4_record[offset+4:offset+6][::-1])
            if field == b'MAST':
                master_list.append(tes4_record[offset+6:offset+field_size+5].decode('utf-8'))
            offset += field_size + 6
        return master_list
