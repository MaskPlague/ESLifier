import os
import struct
import json
from intervaltree import IntervalTree

class create_new_cell_plugin():
    def generate(self, output_folder, update_header = True):
        self.output_file = os.path.join(output_folder, 'ESLifier_Cell_Master.esm')
        if not os.path.exists(self.output_file):
            self.new_data_list = [
                bytes([
                    0x54, 0x45, 0x53, 0x34, 0x9B, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0x00,
                    0x48, 0x45, 0x44, 0x52, 0x0C, 0x00, 0x9A, 0x99, 0xD9, 0x3F, 0x04, 0x00,
                    0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x43, 0x4E, 0x41, 0x4D, 0x16, 0x00,
                    0x4D, 0x61, 0x73, 0x6B, 0x50, 0x6C, 0x61, 0x67, 0x75, 0x65, 0x27, 0x73,
                    0x20, 0x45, 0x53, 0x4C, 0x69, 0x66, 0x69, 0x65, 0x72, 0x00, 0x53, 0x4E,
                    0x41, 0x4D, 0x3E, 0x00, 0x45, 0x53, 0x4C, 0x69, 0x66, 0x69, 0x65, 0x72,
                    0x27, 0x73, 0x20, 0x63, 0x65, 0x6C, 0x6C, 0x20, 0x6D, 0x61, 0x73, 0x74,
                    0x65, 0x72, 0x20, 0x70, 0x6C, 0x75, 0x67, 0x69, 0x6E, 0x20, 0x74, 0x6F,
                    0x20, 0x63, 0x69, 0x72, 0x63, 0x75, 0x6D, 0x76, 0x65, 0x6E, 0x74, 0x20,
                    0x74, 0x68, 0x65, 0x20, 0x65, 0x73, 0x6C, 0x20, 0x63, 0x65, 0x6C, 0x6C,
                    0x20, 0x62, 0x75, 0x67, 0x2E, 0x00, 0x4D, 0x41, 0x53, 0x54, 0x0B, 0x00,
                    0x53, 0x6B, 0x79, 0x72, 0x69, 0x6D, 0x2E, 0x65, 0x73, 0x6D, 0x00, 0x44,
                    0x41, 0x54, 0x41, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x49, 0x4E, 0x43, 0x43, 0x04, 0x00, 0x01, 0x00, 0x00, 0x00
                ]),
                bytes([ 
                    0x47, 0x52, 0x55, 0x50, 0x72, 0x00, 0x00, 0x00, 0x43, 0x45, 0x4C, 0x4C, 
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
                ])
            ]
            if update_header:
                self.new_data_list[0] = self.new_data_list[0][:30] + b'\x48\xE1\xDA\x3F' + self.new_data_list[0][34:]
            self.new_grup_struct = {}
            self.grups = []
            self.grup_blocks = {}
            self.sub_blocks = {}

        else:
            with open(self.output_file, 'rb') as f:
                data = f.read()
            self.new_data_list, self.new_grup_struct = self.create_data_list(data)
            with open('ESLifier_Data/cell_master_info.json', 'r', encoding='utf-8')as f:
                dict = json.load(f)
            self.new_grup_struct = dict['new_grup_struct']
            self.grups = dict['grups']

            str_grup_blocks = dict['grup_blocks']
            self.grup_blocks = {}
            for key, values in str_grup_blocks.items():
                self.grup_blocks[bytes.fromhex(key)] = values

            str_sub_blocks = dict['sub_blocks']
            self.sub_blocks = {}            
            for key, values in str_sub_blocks.items():
                self.sub_blocks[bytes.fromhex(key)] = values

        self.grup_master = 0
        self.form_ids = [i.to_bytes(3, 'little') for i in range(2048, 4096)]

    def add_cells(self, data_list, grup_struct, master_count):
        form_id_map = []
        for i, form in enumerate(data_list):
            if form[:4] == b'CELL' and form[15] >= master_count:
                grup_masters = []
                self.grup_master = len(self.new_data_list)
                grup_block = b''
                sub_block = False
                for grup_index in grup_struct[i][1:]:
                    new_grup = b'GRUP\x00\x00\x00\x00' + data_list[grup_index][8:]
                    grup_block = data_list[grup_index][8:12]
                    if grup_block not in self.grup_blocks and not sub_block:
                        self.grup_blocks[grup_block] = self.grup_master
                        self.new_data_list.append(new_grup)
                    elif sub_block and grup_block not in self.sub_blocks:
                        self.sub_blocks[grup_block] = self.grup_master
                        self.new_data_list.append(new_grup)
                    if not sub_block:
                        grup_masters.append(self.grup_blocks[grup_block])
                    else:
                        grup_masters.append(self.sub_blocks[grup_block])
                    self.grup_master += 1
                    sub_block = True
                current_index = len(self.new_data_list)
                form_id_map.append([form[12:16], self.form_ids[current_index]])
                cell_data = (b'CELL\x12\x00\x00\x00\x00\x00\x00\x00' + 
                             self.form_ids[current_index] +
                             b'\x01'+ data_list[i][16:24] +
                             b'\x44\x41\x54\x41\x02\x00\x01\x00\x4C\x54\x4D\x50\x04\x00\x00\x00\x00\x00')
                grup_masters = self.insert_cell(self.sub_blocks[grup_block]+1, cell_data, grup_masters)
                try:
                    self.new_grup_struct[self.sub_blocks[grup_block]+1] = grup_masters
                except:
                    self.new_grup_struct[self.grup_blocks[grup_block]+1] = grup_masters
                for grup in grup_masters:
                    if grup not in self.grups:
                        self.grups.append(grup)
        return form_id_map

    def insert_cell(self, index, cell_data, grup_masters):
        if index == len(self.new_data_list):
            self.new_data_list.append(cell_data)
            return grup_masters
        else:
            self.new_data_list.insert(index, cell_data)

        for key in self.new_grup_struct.copy():
            values = self.new_grup_struct.pop(key)
            if key >= index:
                key += 1
            for i, value in enumerate(values):
                if value >= index:
                    values[i] = value + 1
            self.new_grup_struct[key] = values
        for key in self.grup_blocks.copy():
            value = self.grup_blocks.pop(key)
            if value >= index:
                value += 1
            self.grup_blocks[key] = value
        for key in self.sub_blocks.copy():
            value = self.sub_blocks.pop(key)
            if value >= index:
                value += 1
            self.sub_blocks[key] = value
        for i, grup in enumerate(grup_masters):
            if grup >= index:
                grup += 1
            grup_masters[i] = grup
        for i, grup in enumerate(self.grups):
            if grup >= index:
                grup += 1
            self.grups[i] = grup
        return grup_masters

    def finalize_plugin(self):
        grup_count = 1
        cell_count = 0
        grups_counted = []
        for key, values in self.new_grup_struct.items():
            for value in values:
                if value not in grups_counted:
                    grups_counted.append(value)
                    grup_count += 1
            cell_count += 1
        record_count = grup_count + cell_count
        self.new_data_list[0] = self.new_data_list[0][:34] + record_count.to_bytes(4, 'little') + self.new_data_list[0][38:]
        size = (grup_count * 24 + cell_count * (18 + 24)).to_bytes(4, 'little')
        self.new_data_list[1] = b'GRUP' + size + self.new_data_list[1][8:]
        for grup in self.grups:
            grup_count = 0
            cell_count = 0
            grups_counted = []
            for key, values in self.new_grup_struct.items():
                copy = values.copy()
                if grup in copy:
                    cell_count += 1
                for x in grups_counted:
                    if x in copy:
                        copy.remove(x)
                if grup in copy:
                    grups_counted.append(grup)
                    copy.reverse()
                    grup_count += copy.index(grup) + 1
            size = (grup_count * 24 + cell_count * (18 + 24)).to_bytes(4, 'little')
            self.new_data_list[grup] = b'GRUP' + size + self.new_data_list[grup][8:]
        str_grup_blocks = {}
        for key, values in self.grup_blocks.items():
            str_grup_blocks[key.hex()] = values
        str_sub_blocks = {}
        for key, values in self.sub_blocks.items():
            str_sub_blocks[key.hex()] = values
        cell_master_info = {
            'new_grup_struct': self.new_grup_struct,
            'grups': self.grups,
            'grup_blocks': str_grup_blocks,
            'sub_blocks': str_sub_blocks,
            }
        with open('ESLifier_Data/cell_master_info.json', 'w', encoding='utf-8')as f:
            json.dump(cell_master_info, f , ensure_ascii=False, indent=4)
        with open(self.output_file, 'wb') as f:
            f.write(b''.join(self.new_data_list))
            f.close()

    def create_data_list(self, data):
        data_list = []
        data_list_offsets = []
        offset = 0
        index = 0
        grup_list = []
        while offset < len(data):
            data_list_offsets.append(offset)
            if data[offset:offset+4] == b'GRUP':
                grup_length = struct.unpack("<I", data[offset+4:offset+8])[0]
                grup_list.append([index, offset, offset + grup_length])
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = struct.unpack("<I", data[offset+4:offset+8])[0]
                offset_end = offset + 24 + form_length
                data_list.append(data[offset:offset_end])
                offset = offset_end
            index += 1
            
        tree = IntervalTree()
        for i, (index, start, end) in enumerate(grup_list):
            tree[start:end] = index

        grup_struct = {}

        for i, data_offset in enumerate(data_list_offsets):
            is_inside_of = [interval.data for interval in tree[data_offset]]
            grup_struct[i] = sorted([index for index in is_inside_of if index != i])

        return data_list, grup_struct