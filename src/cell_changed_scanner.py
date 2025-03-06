import os
import json

class cell_scanner():
    def scan(mods_with_new_cells):
        cell_scanner.cell_changed_list = []
        cell_scanner.dependency_dict = cell_scanner.get_from_file('ESLifier_Data/dependency_dictionary.json')
        cell_scanner.plugin_count = 0
        cell_scanner.count = 0
        for mod in mods_with_new_cells:
            cell_scanner.plugin_count += len(cell_scanner.dependency_dict[os.path.basename(mod).lower()])
        print('\n')
        for mod in mods_with_new_cells:
            cell_scanner.check_if_dependents_modify_new_cells(mod)

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def scan_new_dependents(mods, dependency_dict):
        cell_scanner.dependency_dict = {}
        cell_scanner.cell_changed_list = []
        cell_scanner.plugin_count = 0
        cell_scanner.count = 0
        
        for key, value in dependency_dict.items():
            cell_scanner.dependency_dict[key.lower()] = value
        for mod in mods:
            if mod in cell_scanner.dependency_dict:
                cell_scanner.plugin_count += len(cell_scanner.dependency_dict[os.path.basename(mod).lower()])
        for mod in mods:
            if mod in cell_scanner.dependency_dict:
                cell_scanner.check_if_dependents_modify_new_cells(mod)

        cell_scanner.dump_to_file('ESLifier_Data/cell_changed.json')

    def check_if_dependents_modify_new_cells(mod):
        cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(mod) + '_CellFormIDs.txt'
        if not os.path.exists(cell_form_id_file) or not os.path.basename(mod).lower() in cell_scanner.dependency_dict:
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
        data_list = cell_scanner.create_data_list(dependent_data)
        master_index = cell_scanner.get_master_index(mod, data_list)
        for form in data_list:
            if form[:4] == b'CELL' and form[15] == master_index and str(form[12:15].hex()) in cell_form_ids:
                if os.path.basename(mod) not in cell_scanner.cell_changed_list:
                    cell_scanner.cell_changed_list.append(os.path.basename(mod))
                return
                    
    def get_master_index(file, data_list):
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_list = []
        master_index = 0
        name = os.path.basename(file).lower()
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = int.from_bytes(tes4[offset+4:offset+6][::-1])
            if field == b'MAST':
                master_list.append(tes4[offset+6:offset+field_size+5].decode('utf-8'))
            offset += field_size + 6
        for master in master_list:
            if name == master.lower():
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

    def create_data_list(data):
        data_list = []
        offset = 0
        while offset < len(data):
            if data[offset:offset+4] == b'GRUP':
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = int.from_bytes(data[offset+4:offset+8][::-1])
                data_list.append(data[offset:offset+24+form_length])
                offset += 24 + form_length
        return data_list