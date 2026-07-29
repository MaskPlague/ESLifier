import os
import json
from log_stream import write_error
from data_holder import _global
from PyQt6.QtCore import QCoreApplication

class dependecy_getter():
    bsa_list = []
    def scan(_=None):
        dependecy_getter.dependency_dictionary: dict[str, set] = {}
        dependecy_getter.missing_skyrim_as_master = {}
        dependecy_getter.maxed_masters = []
        dependecy_getter.create_dependency_dictionary()
        dependecy_getter.dump_to_file("ESLifier_Data/dependency_dictionary.json", dependecy_getter.dependency_dictionary)
        dependecy_getter.dump_to_file("ESLifier_Data/missing_skyrim_as_master.json", dependecy_getter.missing_skyrim_as_master)
        dependecy_getter.dump_to_file("ESLifier_Data/maxed_masters.json", dependecy_getter.maxed_masters)
        return dependecy_getter.dependency_dictionary

    def dump_to_file(file: str, data: list | dict):
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
            write_error(QCoreApplication.translate("Global", "Failed to dump data to ") + file)
            write_error(e, True)
    
    def get_from_file(file: str):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
        return data
    
    def create_dependency_dictionary():
        dependecy_getter.dependency_dictionary = {os.path.basename(plugin).lower(): set() for plugin in _global.plugins}
        for plugin in _global.plugins:
            masters, has_records = dependecy_getter.get_masters(plugin)
            if len(masters) > 0:
                for master in masters:
                    master_lower = master.lower()
                    if master_lower not in dependecy_getter.dependency_dictionary:
                        dependecy_getter.dependency_dictionary[master_lower] = set()
                    dependecy_getter.dependency_dictionary[master_lower].add(plugin)
                if masters[0] != 'Skyrim.esm' and has_records:
                    dependecy_getter.missing_skyrim_as_master[plugin] = masters[0]
            if len(masters) >= 254 and 'ESLifier_Cell_Master.esm' not in masters:
                dependecy_getter.maxed_masters.append(plugin)

    def get_masters(file: str) -> tuple[list, bool]:
        master_list = []
        try:
            with open(file, 'rb') as f:
                f.seek(4)
                tes4_size = int.from_bytes(f.read(4)[::-1]) + 24
                f.seek(0)
                tes4_record = f.read(tes4_size)
                has_records = f.read(5) != b''
        except Exception as e:
            write_error(QCoreApplication.translate("Global", "Failed to get master list of " ) + file)
            write_error(e, True)
            return [], False
        offset = 24
        while offset < tes4_size:
            field = tes4_record[offset:offset+4]
            field_size = int.from_bytes(tes4_record[offset+4:offset+6][::-1])
            if field == b'MAST':
                master_list.append(tes4_record[offset+6:offset+field_size+5].decode('utf-8'))
            offset += field_size + 6
        return master_list, has_records
