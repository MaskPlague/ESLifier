import os
import re
import binascii
import shutil
import fileinput
import zlib
import json
import threading
import timeit

#TODO: change list compact and list eslify to use new cell_changed
#TODO: save cell_changed to cell_changed.json
#TODO: change this so that it stores the cell form ids and can use them later to compare new dependents.
#TODO: Add setting to use cell_scanner() and put the relevant change in main_page worker.
#TODO: change patch_new to reflect above

class cell_scanner():
    def scan(mods_with_new_cells):
        cell_scanner.dependency_dict = cell_scanner.get_from_file('ESLifier_Data/dependency_dictionary.json')
        cell_scanner.cell_changed_list = []
        threads = []
        for mod in mods_with_new_cells:
            thread = threading.Thread(target=cell_scanner.check_if_new_cell_is_changed_by_dependent, args=[mod])
            threads.append(thread)
            thread.start()

        for thread in threads: thread.join()

    def check_if_new_cell_is_changed_by_dependent(mod):
        data_list = []
        with open(mod, 'rb') as f:
            data = f.read()
            data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2c|\x2b]\x00.\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]
        
        cell_form_ids = []

        for chunk in data_list:
            if len(chunk) >= 24 and chunk[:4] == b'CELL':
                cell_form_ids.append(chunk[12:15])
        
        for dependent in cell_scanner.dependency_dict[os.path.basename(mod).lower()]:
            dependent_data_list = []
            with open(dependent, 'rb') as f:
                dependent_data = f.read()
                dependent_data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2c|\x2b]\x00.\x00)|(?=GRUP....................)', dependent_data, flags=re.DOTALL) if x]
            for chunk in dependent_data_list:
                if len(chunk) >= 24 and chunk[:4] == b'CELL' and chunk[12:15] in cell_form_ids:
                    print(f'mod {os.path.basename(mod)}\'s new cell(s) are changed by dependent {os.path.basename(dependent)}')
                    cell_scanner.cell_changed_list.append(mod)
                    return

    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data