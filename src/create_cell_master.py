import os
import struct
import json
from intervaltree import IntervalTree

class create_new_cell_plugin():
    def generate(self, output_folder, update_header = True):
        self.output_file = os.path.join(output_folder, 'ESLifier_Cell_Master.esm')
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
        if os.path.exists(self.output_file) and os.path.exists('ESLifier_Data/cell_master_info.json'):
            with open('ESLifier_Data/cell_master_info.json', 'r', encoding='utf-8')as f:
                str_new_grup_struct = json.load(f)
            # Convert strings back to bytes
            for grup_block in str_new_grup_struct:
                str_grup_dict = str_new_grup_struct[grup_block]
                self.new_grup_struct[bytes.fromhex(grup_block)] = {"data": bytes.fromhex(str_grup_dict["data"]),
                                                                   "sub_blocks": {}}
                byte_grup_block = bytes.fromhex(grup_block)
                for sub_block in str_grup_dict["sub_blocks"]:
                    str_sub_dict = str_grup_dict["sub_blocks"][sub_block]
                    byte_sub_block = bytes.fromhex(sub_block)
                    self.new_grup_struct[byte_grup_block]["sub_blocks"][byte_sub_block]= {"data": bytes.fromhex(str_sub_dict["data"]),
                                                                                          "cells": []}
                    for cell in str_sub_dict["cells"]:
                        self.new_grup_struct[byte_grup_block]["sub_blocks"][byte_sub_block]["cells"].append(bytes.fromhex(cell))

        self.form_ids = [i.to_bytes(3, 'little') for i in range(2048, 4096)]

    def add_cells(self, data_list, grup_struct, master_count):
        form_id_map = []
        for i, form in enumerate(data_list):
            if form[:4] == b'CELL' and form[15] >= master_count:
                sub_block = False
                prev_grup_block = b''
                for grup_index in grup_struct[i][1:]:
                    new_grup = b'GRUP\x00\x00\x00\x00' + data_list[grup_index][8:]
                    grup_block = data_list[grup_index][8:12]
                    if not sub_block and grup_block not in self.new_grup_struct:
                        prev_grup_block = grup_block
                        self.new_grup_struct[grup_block] = {
                            "data": new_grup,
                            "sub_blocks": {}
                            }
                        sub_block = True
                    elif sub_block:
                        current_index = len(self.new_grup_struct)
                        form_id_map.append([form[12:16], self.form_ids[current_index]])
                        cell_data = (b'CELL\x12\x00\x00\x00\x00\x00\x00\x00' + 
                                     self.form_ids[current_index] +
                                     b'\x01'+ data_list[i][16:24] +
                                     b'\x44\x41\x54\x41\x02\x00'+
                                     b'\x01\x00\x4C\x54\x4D\x50'+
                                     b'\x04\x00\x00\x00\x00\x00')
                        if grup_block not in self.new_grup_struct[prev_grup_block]["sub_blocks"]:
                            self.new_grup_struct[prev_grup_block]["sub_blocks"][grup_block] = {
                                "data": new_grup,
                                "cells": [cell_data]}
                        else:
                            self.new_grup_struct[prev_grup_block]["sub_blocks"][grup_block]["cells"].append(cell_data)
        return form_id_map

    def finalize_plugin(self):
        # Calculate size of top level CELL GRUP
        grup_count = 1 # start at 1 as the top grup is not in the dict
        cell_count = 0
        for grup_block in self.new_grup_struct:
            grup_dict = self.new_grup_struct[grup_block]
            grup_count += 1
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = self.new_grup_struct[grup_block]["sub_blocks"][sub_block]
                grup_count += 1
                for cell in sub_dict["cells"]:
                    cell_count += 1
                
        record_count = grup_count + cell_count
        self.new_data_list[0] = self.new_data_list[0][:34] + record_count.to_bytes(4, 'little') + self.new_data_list[0][38:]
        size = ((grup_count * 24) + (cell_count * (18 + 24))).to_bytes(4, 'little')
        self.new_data_list[1] = b'GRUP' + size + self.new_data_list[1][8:]

        # Calculate sizes of block GRUPs and sub-block GRUPs
        for grup_block in self.new_grup_struct:
            grup_count = 1
            cell_count = 0
            for sub_block in self.new_grup_struct[grup_block]["sub_blocks"]:
                grup_count += 1
                sub_block_cell_count = 0
                for cell in self.new_grup_struct[grup_block]["sub_blocks"][sub_block]["cells"]:
                    cell_count += 1
                    sub_block_cell_count += 1
                size = ((sub_block_cell_count * (18+24)) + 24).to_bytes(4, 'little')
                self.new_grup_struct[grup_block]["sub_blocks"][sub_block]["size"] = size
            size = (grup_count * 24 + cell_count * (18 + 24)).to_bytes(4, 'little')
            self.new_grup_struct[grup_block]["size"] = size

        # Create new data list
        for grup_block in self.new_grup_struct:
            grup_dict = self.new_grup_struct[grup_block]
            self.new_data_list.append(b'GRUP' + grup_dict["size"] + grup_dict["data"][8:]) 
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = grup_dict["sub_blocks"][sub_block]
                self.new_data_list.append(b'GRUP' + sub_dict["size"] + sub_dict["data"][8:])
                for cell in sub_dict["cells"]:
                    self.new_data_list.append(cell)

        # Convert keys to strings from byte strings
        str_new_grup_struct = {}
        for grup_block in self.new_grup_struct:
            grup_dict = self.new_grup_struct[grup_block]
            str_grup_block = grup_block.hex()
            str_new_grup_struct[str_grup_block] = {"data": grup_dict["data"].hex(),
                                                     "size": int.from_bytes(grup_dict["size"], 'little'),
                                                     "sub_blocks": {}}
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = grup_dict["sub_blocks"][sub_block]
                str_sub_block = sub_block.hex()
                str_new_grup_struct[str_grup_block]["sub_blocks"][str_sub_block] = {"data": sub_dict["data"].hex(),
                                                                                    "size": int.from_bytes(sub_dict["size"],'little'),
                                                                                    "cells": []}
                for cell in sub_dict["cells"]:
                    str_new_grup_struct[str_grup_block]["sub_blocks"][str_sub_block]["cells"].append(cell.hex())

        with open('ESLifier_Data/cell_master_info.json', 'w', encoding='utf-8')as f:
            json.dump(str_new_grup_struct, f , ensure_ascii=False, indent=4)
        with open(self.output_file, 'wb') as f:
            f.write(b''.join(self.new_data_list))
            f.close()