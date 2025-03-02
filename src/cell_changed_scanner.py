import os
import regex as re
import json
import timeit

class cell_scanner():
    def scan(mods_with_new_cells):
        start_time = timeit.default_timer()
        cell_scanner.cell_changed_list = []
        cell_scanner.dependency_dict = cell_scanner.get_from_file('ESLifier_Data/dependency_dictionary.json')
        cell_scanner.plugin_count = 0
        cell_scanner.count = 0
        for mod in mods_with_new_cells:
            cell_scanner.plugin_count += len(cell_scanner.dependency_dict[os.path.basename(mod).lower()])

        print('\n')
        for mod in mods_with_new_cells:
            cell_scanner.check_if_dependents_modify_new_cells(mod)

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print('-  Time taken: ' + str(round(time_taken,2)) + ' seconds')

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def scan_new_dependents(mods, dependency_dict):
        cell_scanner.dependency_dict = {}
        cell_scanner.cell_changed_list = []
        cell_scanner.plugin_count = 0
        cell_scanner.count = 0
        
        for key, value in dependency_dict.items():
            cell_scanner.dependency_dict[key.lower()] = value
        for mod in mods:
            if mod in cell_scanner.dependency_dict.keys():
                cell_scanner.plugin_count += len(cell_scanner.dependency_dict[os.path.basename(mod).lower()])
        for mod in mods:
            if mod in cell_scanner.dependency_dict.keys():
                cell_scanner.check_if_dependents_modify_new_cells(mod)

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def check_if_dependents_modify_new_cells(mod):
        cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(mod) + '_CellFormIDs.txt'
        if not os.path.exists(cell_form_id_file) or not os.path.basename(mod).lower() in cell_scanner.dependency_dict.keys():
            return
        with open(cell_form_id_file, 'r') as f:
            cell_form_ids = [line.strip() for line in f.readlines()]
        if cell_form_ids:
            dependents = cell_scanner.dependency_dict[os.path.basename(mod).lower()]
            for dependent in dependents:
                cell_scanner.scan_dependent(mod, dependent, cell_form_ids)

    def scan_dependent(mod, dependent, cell_form_ids):
        cell_scanner.count += 1
        cell_scanner.percentage = (cell_scanner.count / cell_scanner.plugin_count) * 100
        factor = round(cell_scanner.plugin_count * 0.01)
        if factor == 0:
            factor = 1
        if (cell_scanner.count % factor) >= (factor-1) or cell_scanner.count >= cell_scanner.plugin_count:
            print('\033[F\033[K-  Processed: ' + str(round(cell_scanner.percentage, 1)) + '%' + '\n-  Plugins: ' + str(cell_scanner.count) + '/' + str(cell_scanner.plugin_count), end='\r')
        
        dependent_data = b''
        with open(dependent, 'rb') as f:
            dependent_data = f.read()
        
        master_index = cell_scanner.get_master_index(mod, dependent_data)
        previous_offset = 0
        count = dependent_data.count(b'CELL')
        for i in range(count):
            offset = dependent_data.index(b'CELL', previous_offset)
            if dependent_data[offset+15] == master_index and str(dependent_data[offset+12:offset+15].hex()) in cell_form_ids:
                if os.path.basename(mod) not in cell_scanner.cell_changed_list:
                    cell_scanner.cell_changed_list.append(os.path.basename(mod))
                return
            previous_offset = offset+4
            
                    
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