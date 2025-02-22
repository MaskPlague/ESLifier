import timeit
import os
import json
import threading


class qualification_checker():
    def scan(path, update_header, show_cells, scan_esms):
        qualification_checker.lock = threading.Lock()
        start_time = timeit.default_timer()
        all_plugins = qualification_checker.get_from_file("ESLifier_Data/plugin_list.json")
        plugins = [plugin for plugin in all_plugins if not plugin.lower().endswith('.esl')]
        qualification_checker.need_flag_list = []
        qualification_checker.need_flag_cell_flag_list = []
        qualification_checker.need_compacting_list = []
        qualification_checker.need_compacting_cell_flag_list = []
        qualification_checker.max_record_number = 4096
        qualification_checker.show_cells = show_cells
        qualification_checker.scan_esms = scan_esms
        if update_header:
            qualification_checker.num_max_records = 4096
        else:
            qualification_checker.num_max_records = 2048

        print('\n')
        qualification_checker.count = 0
        qualification_checker.plugin_count = len(plugins)

        if len(plugins) > 1000:
            split = 5
        elif len(plugins) > 500:
            split = 2
        else:
            split = 1

        chunk_size = len(plugins) // split
        chunks = [plugins[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(plugins[(split) * chunk_size:])

        threads = []
        for chunk in chunks:
            thread = threading.Thread(target=qualification_checker.plugin_scanner, args=(chunk,))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()

        end_time = timeit.default_timer()
        time_taken = end_time - start_time
        print('-  Time taken: ' + str(round(time_taken,2)) + ' seconds')
        return qualification_checker.need_flag_list, qualification_checker.need_flag_cell_flag_list, qualification_checker.need_compacting_list, qualification_checker.need_compacting_cell_flag_list

    def plugin_scanner(plugins):
        need_flag_list = []
        need_flag_cell_flag_list = []
        need_compacting_list = []
        need_compacting_cell_flag_list = []
        for plugin in plugins:
            if not qualification_checker.already_esl(plugin):
                esl_allowed, need_compacting, new_cell = qualification_checker.file_reader(plugin)
                if esl_allowed:
                    if not need_compacting:
                        need_flag_list.append(plugin)
                        if new_cell:
                            need_flag_cell_flag_list.append(os.path.basename(plugin))
                    else:
                        need_compacting_list.append(plugin)
                        if new_cell:
                            need_compacting_cell_flag_list.append(os.path.basename(plugin))
            qualification_checker.count += 1
            percentage = (qualification_checker.count / qualification_checker.plugin_count) * 100
            print('\033[F\033[K-  Processed: ' + str(round(percentage, 1)) + '%' + '\n-  Plugins: ' + str(qualification_checker.count) + '/' + str(qualification_checker.plugin_count), end='\r')

        with qualification_checker.lock:
            qualification_checker.need_flag_list.extend(need_flag_list)
            qualification_checker.need_flag_cell_flag_list.extend(need_flag_cell_flag_list)
            qualification_checker.need_compacting_list.extend(need_compacting_list)
            qualification_checker.need_compacting_cell_flag_list.extend(need_compacting_cell_flag_list)

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

    def file_reader(file):
        data_list = []
        new_cell = False
        need_compacting = False
        with open(file, 'rb') as f:
            data = f.read()
            data_list = qualification_checker.create_data_list(data)
        master_count = data_list[0].count(b'MAST')
        count = 0
        cell_form_ids = []
        for form in data_list:
            if form[:4] != 'TES4' and len(form) > 24 and form[15] == master_count:
                count += 1
                if count > qualification_checker.num_max_records:
                    return False, False, False
                if int.from_bytes(form[12:15][::-1]) > qualification_checker.max_record_number:
                    need_compacting = True
                if form[:4] == b'CELL':
                    if not qualification_checker.show_cells:
                        return False, False, True
                    new_cell = True
            if len(form) >= 24 and form[:4] == b'CELL' and form[15] == master_count and str(form[12:15].hex()) not in cell_form_ids:
                cell_form_ids.append(str(form[12:15].hex()))
        cell_form_ids.sort()
        if cell_form_ids != []:
            cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(file) + '_CellFormIDs.txt'
            with qualification_checker.lock:
                if not os.path.exists(os.path.dirname(cell_form_id_file)):
                    os.makedirs(os.path.dirname(cell_form_id_file))
            with open(cell_form_id_file, 'w') as f:
                for form_id in cell_form_ids:
                    f.write(form_id + '\n')

        return True, need_compacting, new_cell

    def already_esl(file):
        with open(file, 'rb') as f:
            f.seek(8)
            esm_flag = f.read(1)
            if esm_flag in (b'\x81', b'\x01') and not qualification_checker.scan_esms:
                return True #return that the file does not qualify
            esl_flag = f.read(1)
            if esl_flag == b'\x02':
                return True
            else:
                return False #not esl, so it does qualify for processing
            
    def get_from_file(file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = []
        return data