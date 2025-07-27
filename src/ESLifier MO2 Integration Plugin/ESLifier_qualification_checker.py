import zlib
import struct

class qualification_checker():
    def qualification_check(self, plugin, new_header, scan_esms):
        qualification_checker.max_record_number = 4096
        qualification_checker.scan_esms = scan_esms

        if new_header:
            qualification_checker.num_max_records = 4096
        else:
            qualification_checker.num_max_records = 2048
        
        if not qualification_checker.already_esl(plugin):
            esl_allowed, need_comapcting, new_cell, interior_cell, new_wrld = qualification_checker.file_reader(plugin)
        else:
            return False, False, False, False, False
        return esl_allowed, need_comapcting, new_cell, interior_cell, new_wrld
    
    def file_reader(file):
        data_list = []
        new_cell = False
        interior_cell_flag = False
        need_compacting = False
        new_wrld = False
        try:
            with open(file, 'rb') as f:
                data = f.read()
        except:
            return False, False, False, False, False
        data_list = qualification_checker.create_data_list(data)
        master_count = qualification_checker.get_master_count(data_list)
        if master_count == 0:
            num_max_records = 2048
        else:
            num_max_records = qualification_checker.num_max_records
        count = 0
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
        
        return True, need_compacting, new_cell, interior_cell_flag, new_wrld
    
    def already_esl(file): # return true if already esl or ESM but not scanning 
        try:
            with open(file, 'rb') as f:
                f.seek(8)
                esm_flag = f.read(1)
                if esm_flag in (b'\x81', b'\x01') and not qualification_checker.scan_esms:
                    return True
                esl_flag = f.read(1)
                if esl_flag == b'\x02':
                    return True
                else:
                    return 
        except:
            return True
            
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