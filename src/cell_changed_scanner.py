import os
import re
import json
import threading

class cell_scanner():
    def scan(mods_with_new_cells):
        cell_scanner.cell_changed_list = []
        cell_scanner.dependency_dict = cell_scanner.get_from_file('ESLifier_Data/dependency_dictionary.json')
        threads = []
        for mod in mods_with_new_cells:
            thread = threading.Thread(target=cell_scanner.get_new_cell_form_ids, args=(mod,))
            threads.append(thread)
            thread.start()

        for thread in threads: thread.join()

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def get_new_cell_form_ids(mod):
        data_list = []
        with open(mod, 'rb') as f:
            data = f.read()
            data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2c|\x2b]\x00.\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]

        master_count = data_list[0].count(b'MAST')
        cell_form_ids = []
        for chunk in data_list:
            if len(chunk) >= 24 and chunk[:4] == b'CELL' and chunk[15] == master_count and str(chunk[12:15].hex()) not in cell_form_ids:
                    cell_form_ids.append(str(chunk[12:15].hex()))
        
        cell_form_ids.sort()

        cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(mod) + '_CellFormIDs.txt'
        if not os.path.exists(os.path.dirname(cell_form_id_file)):
            os.makedirs(os.path.dirname(cell_form_id_file))

        with open(cell_form_id_file, 'w') as f:
            for form_id in cell_form_ids:
                f.write(form_id + '\n')
        
        cell_scanner.check_if_dependents_modify_new_cells(mod)

    def scan_new_dependents(mods, dependency_dict):
        cell_scanner.dependency_dict = {}
        for key, value in dependency_dict.items():
            cell_scanner.dependency_dict[key.lower()] = value
        cell_scanner.cell_changed_list = []
        threads = []
        for mod in mods:
            thread = threading.Thread(target=cell_scanner.check_if_dependents_modify_new_cells, args=(mod,))
            threads.append(thread)
            thread.start()

        for thread in threads: thread.join()

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def check_if_dependents_modify_new_cells(mod):
        cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(mod) + '_CellFormIDs.txt'
        if not os.path.exists(cell_form_id_file) or not os.path.basename(mod).lower() in cell_scanner.dependency_dict.keys():
            return
        with open(cell_form_id_file, 'r') as f:
            cell_form_ids = [line.strip() for line in f.readlines()]
        if cell_form_ids:
            for dependent in cell_scanner.dependency_dict[os.path.basename(mod).lower()]:
                dependent_data_list = []
                dependent_data = b''
                with open(dependent, 'rb') as f:
                    dependent_data = f.read()
                    dependent_data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2c|\x2b]\x00.\x00)|(?=GRUP....................)', dependent_data, flags=re.DOTALL) if x]
                master_index = cell_scanner.get_master_index(mod, dependent_data)
                for chunk in dependent_data_list:
                    if len(chunk) >= 24 and chunk[:4] == b'CELL' and chunk[15] == master_index and str(chunk[12:15].hex()) in cell_form_ids:
                        #print(f'Mod: {os.path.basename(mod)}\'s new cell(s) are changed by dependent: {os.path.basename(dependent)}')
                        cell_scanner.cell_changed_list.append(os.path.basename(mod))
                        return
                    
    def get_master_index(file, data):
        master_pattern = re.compile(b'MAST..(.*?).DATA')
        matches = re.findall(master_pattern, data)
        master_index = 0
        for match in matches:
            if os.path.basename(file).lower() in str(match).lower():
                return master_index
            else:
                master_index += 1

    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    
    def dump_to_file(file):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(cell_scanner.cell_changed_list, f, ensure_ascii=False, indent=4)