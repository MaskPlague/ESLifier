import os
import json
import threading
import zlib
import struct

class qualification_checker():
    def scan(path, update_header, scan_esms):
        qualification_checker.lock = threading.Lock()
        all_plugins = qualification_checker.get_from_file("ESLifier_Data/plugin_list.json")
        plugins = [plugin for plugin in all_plugins if not plugin.lower().endswith('.esl')]
        qualification_checker.flag_dict = {}
        qualification_checker.max_record_number = 4096
        qualification_checker.scan_esms = scan_esms
        if update_header:
            qualification_checker.num_max_records = 4096
        else:
            qualification_checker.num_max_records = 2048

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
        return qualification_checker.flag_dict

    def plugin_scanner(plugins):
        flag_dict = {}
        for plugin in plugins:
            if not qualification_checker.already_esl(plugin):
                esl_allowed, need_compacting, new_cell, interior_cell, new_wrld = qualification_checker.file_reader(plugin)
                if esl_allowed:
                    flag_dict[plugin] = []
                    if need_compacting:
                        flag_dict[plugin].append('need_compacting')
                    if new_cell:
                        flag_dict[plugin].append('new_cell')
                        if interior_cell:
                            flag_dict[plugin].append('new_interior_cell')
                    if new_wrld:
                        flag_dict[plugin].append('new_wrld')
        with qualification_checker.lock:
            for key, value in flag_dict.items():
                if key not in qualification_checker.flag_dict:
                    qualification_checker.flag_dict[key] = value

    def create_data_list(data):
        data_list = []
        offset = 0
        while offset < len(data):
            if data[offset:offset+4] == b'GRUP':
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = struct.unpack("<I", data[offset+4:offset+8])[0]
                offset_end = offset + 24 + form_length
                data_list.append(data[offset:offset_end])
                offset = offset_end
        return data_list      

    def file_reader(file):
        data_list = []
        new_cell = False
        interior_cell_flag = False
        need_compacting = False
        new_wrld = False
        with open(file, 'rb') as f:
            data = f.read()
        data_list = qualification_checker.create_data_list(data)
        master_count = qualification_checker.get_master_count(data_list)
        if master_count == 0:
            num_max_records = 2048
        else:
            num_max_records = qualification_checker.num_max_records
        count = 0
        cell_form_ids = []
        for form in data_list:
            record_type = form[:4]
            if record_type not in (b'GRUP', b'TES4') and form[15] >= master_count:
                count += 1
                if count > num_max_records:
                    return False, False, False, False, False
                if int.from_bytes(form[12:15][::-1]) > qualification_checker.max_record_number:
                    need_compacting = True
                if record_type == b'CELL':
                    new_cell = True
                    if not interior_cell_flag:
                        flag_byte = form[10]
                        compressed_flag = (flag_byte & 0x04) != 0
                        offset = 24
                        form_to_check = form
                        if compressed_flag:
                            form_to_check = zlib.decompress(form[28:])
                            offset = 0
                        form_size = len(form_to_check)
                        while offset < form_size:
                            field = form_to_check[offset:offset+4]
                            field_size = struct.unpack("<H", form_to_check[offset+4:offset+6])[0]
                            if field == b'DATA':
                                flags = form_to_check[offset+6]
                                interior_cell_flag = (flags & 0x01) != 0
                            offset += field_size + 6
                if record_type == b'WRLD':
                    new_wrld = True
                    
            if record_type == b'CELL' and form[15] >= master_count and str(form[12:15].hex()) not in cell_form_ids:
                cell_form_ids.append(str(form[12:15].hex()))

        cell_form_ids.sort()
        if cell_form_ids != []:
            cell_form_id_file = 'ESLifier_Data/Cell_IDs/' + os.path.basename(file) + '_CellFormIDs.txt'
            with qualification_checker.lock:
                if not os.path.exists(os.path.dirname(cell_form_id_file)):
                    os.makedirs(os.path.dirname(cell_form_id_file))
            with open(cell_form_id_file, 'w', encoding='utf-8') as f:
                for form_id in cell_form_ids:
                    f.write(form_id + '\n')

        return True, need_compacting, new_cell, interior_cell_flag, new_wrld

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
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
        return data
    
    def get_master_count(data_list):
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_count = 0
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master_count += 1
            offset += field_size + 6
        return master_count