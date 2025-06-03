import os
import struct
import json

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
            bytes([ # CELL top GRUP
                0x47, 0x52, 0x55, 0x50, 0x72, 0x00, 0x00, 0x00, 0x43, 0x45, 0x4C, 0x4C, 
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
            ]),
            bytes([ # WRLD top GRUP
                0x47, 0x52, 0x55, 0x50, 0x2D, 0x74, 0x02, 0x00, 0x57, 0x52, 0x4C, 0x44,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
            ])
            ]
        if update_header:
            self.new_data_list[0] = self.new_data_list[0][:30] + b'\x48\xE1\xDA\x3F' + self.new_data_list[0][34:]
        self.new_interior_cell_dict = {}
        self.wrld_dict = {}
        self.counter = 1
        if os.path.exists(self.output_file) and os.path.exists('ESLifier_Data/cell_master_info.json'):
            with open('ESLifier_Data/cell_master_info.json', 'r', encoding='utf-8')as f:
                dict = json.load(f)
            # Convert strings back to 
            str_new_interior_cell_dict = dict["interior_cells_dict"]
            self.counter = dict["counter"]
            for grup_block in str_new_interior_cell_dict:
                str_grup_dict = str_new_interior_cell_dict[grup_block]
                byte_grup_block = bytes.fromhex(grup_block)
                self.new_interior_cell_dict[byte_grup_block] = {"data": bytes.fromhex(str_grup_dict["data"]),
                                                                   "source_plugin": str_grup_dict["source_plugin"],
                                                                   "sub_blocks": {}}
                for sub_block in str_grup_dict["sub_blocks"]:
                    str_sub_dict = str_grup_dict["sub_blocks"][sub_block]
                    byte_sub_block = bytes.fromhex(sub_block)
                    self.new_interior_cell_dict[byte_grup_block]["sub_blocks"][byte_sub_block]= {"data": bytes.fromhex(str_sub_dict["data"]),
                                                                                          "source_plugin": str_sub_dict["source_plugin"],
                                                                                          "cells": []}
                    for cell in str_sub_dict["cells"]:
                        self.new_interior_cell_dict[byte_grup_block]["sub_blocks"][byte_sub_block]["cells"].append(bytes.fromhex(cell))
            
            str_hex_wrld_dict = dict["wrld_dict"]
            for world_id in str_hex_wrld_dict:
                str_wrld_dict = str_hex_wrld_dict[world_id]
                byte_wrld_id = bytes.fromhex(world_id)
                self.wrld_dict[byte_wrld_id] = {"data": bytes.fromhex(str_wrld_dict["data"]),
                                                "grup_data": bytes.fromhex(str_wrld_dict["grup_data"]),
                                                "persistent_cell_data": bytes.fromhex(str_wrld_dict["persistent_cell_data"]),
                                                "source_plugin": str_wrld_dict["source_plugin"],
                                                "blocks": {}}
                for grup_block in str_wrld_dict['blocks']:
                    str_grup_dict = str_wrld_dict['blocks'][grup_block]
                    byte_grup_block = bytes.fromhex(grup_block)
                    self.wrld_dict[byte_wrld_id]['blocks'][byte_grup_block] = {"data": bytes.fromhex(str_grup_dict["data"]),
                                                                               "source_plugin": str_grup_dict["source_plugin"],
                                                                               "sub_blocks": {}}
                    
                    for sub_block in str_grup_dict["sub_blocks"]:
                        str_sub_dict = str_grup_dict["sub_blocks"][sub_block]
                        byte_sub_block = bytes.fromhex(sub_block)
                        self.wrld_dict[byte_wrld_id]['blocks'][byte_grup_block]["sub_blocks"][byte_sub_block]= {"data": bytes.fromhex(str_sub_dict["data"]),
                                                                                                                "source_plugin": str_sub_dict["source_plugin"],
                                                                                                                "cells": []}
                        for cell in str_sub_dict["cells"]:
                            self.wrld_dict[byte_wrld_id]['blocks'][byte_grup_block]["sub_blocks"][byte_sub_block]["cells"].append(bytes.fromhex(cell))

    def add_cells(self, data_list, grup_struct, master_count, name):
        form_id_map = []
        first_exterior_cell_in_world = True
        current_wrld_id = b''
        for i, form in enumerate(data_list):
            interior_cell_flag = False
            if form[:4] == b'CELL' and form[15] >= master_count:
                offset = 24
                form_size = len(form)
                while offset < form_size:
                    field = form[offset:offset+4]
                    field_size = struct.unpack("<H", form[offset+4:offset+6])[0]
                    if field == b'DATA':
                        flags = form[offset+6]
                        interior_cell_flag = (flags & 0x01) != 0
                        break
                    offset += field_size + 6
                if interior_cell_flag:
                    sub_block = False
                    prev_grup_block = b''
                    for grup_index in grup_struct[i][1:]:
                        new_grup = b'GRUP\x00\x00\x00\x00' + data_list[grup_index][8:]
                        grup_block = data_list[grup_index][8:12]
                        if not sub_block and grup_block not in self.new_interior_cell_dict:  
                            self.new_interior_cell_dict[grup_block] = {
                                "data": new_grup,
                                "source_plugin": name,
                                "sub_blocks": {}
                                }
                        if sub_block:
                            new_form_id = (self.counter + 2048).to_bytes(3, 'little')
                            self.counter += 1
                            form_id_map.append([form[12:16], new_form_id])
                            cell_data = (b'CELL\x12\x00\x00\x00\x00\x00\x00\x00' + new_form_id +
                                        b'\x01'+ data_list[i][16:24] + b'\x44\x41\x54\x41\x02\x00' +
                                        b'\x01\x00\x4C\x54\x4D\x50\x04\x00\x00\x00\x00\x00')
                            if grup_block not in self.new_interior_cell_dict[prev_grup_block]["sub_blocks"]:
                                self.new_interior_cell_dict[prev_grup_block]["sub_blocks"][grup_block] = {
                                    "data": new_grup,
                                    "source_plugin": name,
                                    "cells": []}
                            self.new_interior_cell_dict[prev_grup_block]["sub_blocks"][grup_block]["cells"].append(cell_data)
                        if not sub_block:
                            sub_block = True
                            prev_grup_block = grup_block

            if form[:4] == b'CELL' and form[15] >= master_count and not interior_cell_flag and not current_wrld_id == b'':
                if first_exterior_cell_in_world:
                    first_exterior_cell_in_world = False
                    new_form_id = (self.counter + 2048).to_bytes(3, 'little')
                    self.counter += 1
                    form_id_map.append([form[12:16], new_form_id])
                    cell_data = (b'CELL\x24\x00\x00\x00\x00\x00\x00\x00' + new_form_id +
                                b'\x01'+ data_list[i][16:24] + b'\x44\x41\x54\x41\x02\x00'+
                                b'\x00\x00\x58\x43\x4C\x43\x0C\x00\x00\x00\x00\x00\x00\x00\x00'+
                                b'\x00\x00\x00\x00\x00\x4C\x54\x4D\x50\x04\x00\x00\x00\x00\x00')
                    self.wrld_dict[current_wrld_id]["persistent_cell_data"] = cell_data
                else:
                    sub_block = False
                    prev_grup_block = b''
                    for grup_index in grup_struct[i][2:]:
                        new_grup = b'GRUP\x00\x00\x00\x00' + data_list[grup_index][8:]
                        grup_block = data_list[grup_index][8:12]
                        if not sub_block and grup_block not in self.wrld_dict[current_wrld_id]['blocks']:  
                            self.wrld_dict[current_wrld_id]['blocks'][grup_block] = {
                                "data": new_grup,
                                "source_plugin": name,
                                "sub_blocks": {}
                                }
                        if sub_block:
                            new_form_id = (self.counter + 2048).to_bytes(3, 'little')
                            self.counter += 1
                            form_id_map.append([form[12:16], new_form_id])
                            cell_data = (b'CELL\x24\x00\x00\x00\x00\x00\x00\x00' + new_form_id +
                                        b'\x01'+ data_list[i][16:24] + b'\x44\x41\x54\x41\x02\x00'+
                                        b'\x00\x00\x58\x43\x4C\x43\x0C\x00\x00\x00\x00\x00\x00\x00\x00'+
                                        b'\x00\x00\x00\x00\x00\x4C\x54\x4D\x50\x04\x00\x00\x00\x00\x00')
                            if grup_block not in self.wrld_dict[current_wrld_id]['blocks'][prev_grup_block]["sub_blocks"]:
                                self.wrld_dict[current_wrld_id]['blocks'][prev_grup_block]["sub_blocks"][grup_block] = {
                                    "data": new_grup,
                                    "source_plugin": name,
                                    "cells": []}
                            self.wrld_dict[current_wrld_id]['blocks'][prev_grup_block]["sub_blocks"][grup_block]["cells"].append(cell_data)
                        if not sub_block:
                            sub_block = True
                            prev_grup_block = grup_block
            elif form[:4] == b'WRLD' and form[15] >= master_count:
                current_wrld_id = form[12:16]
                if form[15] >= master_count:
                    new_form_id = (self.counter + 2048).to_bytes(3, 'little')
                    self.counter += 1
                    form_id_map.append([form[12:16], new_form_id])
                    new_form_id += b'\01'
                else:
                    new_form_id = current_wrld_id
                first_exterior_cell_in_world = True
                self.wrld_dict[current_wrld_id] = {
                    "data": (b'WRLD\x9B\x00\x00\x00\x00\x00\x00\x00' + new_form_id +
                            b'\x00\x00\x00\x00\x2C\x00\x00\x00'+
                            b'\x43\x4E\x41\x4D\x04\x00\x5F\x01\x00\x00\x4E\x41'+
                            b'\x4D\x32\x04\x00\x18\x00\x00\x00\x4E\x41\x4D\x33'+
                            b'\x04\x00\x18\x00\x00\x00\x4E\x41\x4D\x34\x04\x00'+
                            b'\x00\x00\x00\x00\x44\x4E\x41\x4D\x08\x00\x00\x00'+
                            b'\x00\xC5\x00\x00\x00\x00\x4D\x4E\x41\x4D\x1C\x00'+
                            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'+
                            b'\x00\x00\x00\x00\x00\x50\x43\x47\x00\x40\x9C\x47'+
                            b'\x00\x00\x48\x42\x4F\x4E\x41\x4D\x10\x00\x00\x00'+
                            b'\x80\x3F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'+
                            b'\x00\x00\x4E\x41\x4D\x41\x04\x00\x00\x00\x80\x3F'+
                            b'\x44\x41\x54\x41\x01\x00\x01\x4E\x41\x4D\x30\x08'+
                            b'\x00\xFF\xFF\x7F\x7F\xFF\xFF\x7F\x7F\x4E\x41\x4D'+
                            b'\x39\x08\x00\xFF\xFF\x7F\xFF\xFF\xFF\x7F\xFF'),
                    "source_plugin": name,
                    "grup_data": (b'GRUP\x00\x00\x00\x00'+ new_form_id +
                            b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'),
                    "persistent_cell_data": b'',
                    "blocks": {}
                }
        return form_id_map

    def finalize_plugin(self):
        # Calculate size of top level CELL GRUP
        cell_grup_count = 1 # start at 1 as the top grup is not in the dict
        cell_grup_cell_count = 0
        for grup_block in self.new_interior_cell_dict:
            grup_dict = self.new_interior_cell_dict[grup_block]
            cell_grup_count += 1
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = grup_dict["sub_blocks"][sub_block]
                cell_grup_count += 1
                for cell in sub_dict["cells"]:
                    cell_grup_cell_count += 1
                
        record_count = cell_grup_count + cell_grup_cell_count
        #self.new_data_list[0] = self.new_data_list[0][:34] + record_count.to_bytes(4, 'little') + self.new_data_list[0][38:]
        size = ((cell_grup_count * 24) + (cell_grup_cell_count * (18 + 24))).to_bytes(4, 'little')
        self.new_data_list[1] = b'GRUP' + size + self.new_data_list[1][8:]

        # Calculate size of top level WRLD GRUP
        wrld_grup_count = 1 # start at 1 as the top grup is not in the dict
        wrld_grup_cell_count = 1 # start at 1 for the one cell outside of the blocks
        wrld_count = 0
        for wrld_id in self.wrld_dict:
            wrld_dict = self.wrld_dict[wrld_id]['blocks']
            wrld_grup_count += 1
            wrld_count += 1
            for grup_block in wrld_dict:
                grup_dict = wrld_dict[grup_block]
                wrld_grup_count += 1
                for sub_block in grup_dict["sub_blocks"]:
                    sub_dict = grup_dict["sub_blocks"][sub_block]
                    wrld_grup_count += 1
                    for cell in sub_dict["cells"]:
                        wrld_grup_cell_count += 1
                
        record_count = wrld_grup_count + wrld_grup_cell_count + cell_grup_count + cell_grup_cell_count
        self.new_data_list[0] = self.new_data_list[0][:34] + record_count.to_bytes(4, 'little') + self.new_data_list[0][38:]
        size = ((wrld_count * (24 + 155)) + (wrld_grup_count * 24) + (wrld_grup_cell_count * (36 + 24))).to_bytes(4, 'little')
        self.new_data_list[2] = b'GRUP' + size + self.new_data_list[2][8:]

        # Calculate sizes of CELL block GRUPs and sub-block GRUPs, grups are 24 bytes and cells are 18 bytes + 24 for header
        for grup_block in self.new_interior_cell_dict:
            grup_count = 1
            cell_count = 0
            for sub_block in self.new_interior_cell_dict[grup_block]["sub_blocks"]:
                grup_count += 1
                sub_block_cell_count = 0
                for cell in self.new_interior_cell_dict[grup_block]["sub_blocks"][sub_block]["cells"]:
                    cell_count += 1
                    sub_block_cell_count += 1
                size = ((sub_block_cell_count * (18+24)) + 24).to_bytes(4, 'little')
                self.new_interior_cell_dict[grup_block]["sub_blocks"][sub_block]["size"] = size
            size = (grup_count * 24 + cell_count * (18 + 24)).to_bytes(4, 'little')
            self.new_interior_cell_dict[grup_block]["size"] = size

        # Calculate sizes of WRLD block GRUPs and sub-block GRUPs, grups are 24 bytes and cells are 36 bytes + 24 for header
        for wrld_id in self.wrld_dict:
            wrld_grup_count = 1
            wrld_cell_count = 0
            for grup_block in self.wrld_dict[wrld_id]['blocks']:
                grup_count = 1
                cell_count = 0
                wrld_grup_count += 1
                for sub_block in self.wrld_dict[wrld_id]['blocks'][grup_block]["sub_blocks"]:
                    grup_count += 1
                    sub_block_cell_count = 0
                    wrld_grup_count += 1
                    for cell in self.wrld_dict[wrld_id]['blocks'][grup_block]["sub_blocks"][sub_block]["cells"]:
                        cell_count += 1
                        sub_block_cell_count += 1
                        wrld_cell_count += 1
                    size = ((sub_block_cell_count * (36+24)) + 24).to_bytes(4, 'little')
                    self.wrld_dict[wrld_id]['blocks'][grup_block]["sub_blocks"][sub_block]["size"] = size
                size = (grup_count * 24 + cell_count * (36 + 24)).to_bytes(4, 'little')
                self.wrld_dict[wrld_id]['blocks'][grup_block]["size"] = size
            size = ((36 + 24) + wrld_grup_count * 24 + wrld_cell_count * (36 + 24)).to_bytes(4, 'little')
            self.wrld_dict[wrld_id]['size'] = size

        # Add CELL grups, blocks, sub-blocks, and cells to data list
        for grup_block in self.new_interior_cell_dict:
            grup_dict = self.new_interior_cell_dict[grup_block]
            self.new_data_list.insert(len(self.new_data_list) - 1, b'GRUP' + grup_dict["size"] + grup_dict["data"][8:]) 
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = grup_dict["sub_blocks"][sub_block]
                self.new_data_list.insert(len(self.new_data_list) - 1, b'GRUP' + sub_dict["size"] + sub_dict["data"][8:])
                for cell in sub_dict["cells"]:
                    self.new_data_list.insert(len(self.new_data_list) - 1, cell)

        if len(self.new_interior_cell_dict) == 0:
            self.new_data_list.pop(1)

        # Add WRLD grups, wrlds, persistent cell, blocks, sub-blocks, and cells to data list
        for wrld_id in self.wrld_dict:
            wrld_dict = self.wrld_dict[wrld_id]
            self.new_data_list.append(wrld_dict['data'])
            self.new_data_list.append(b'GRUP' + wrld_dict['size'] + wrld_dict["grup_data"][8:])
            self.new_data_list.append(wrld_dict['persistent_cell_data'])
            for grup_block in wrld_dict['blocks']:
                grup_dict = wrld_dict['blocks'][grup_block]
                self.new_data_list.append(b'GRUP' + grup_dict["size"] + grup_dict["data"][8:]) 
                for sub_block in grup_dict["sub_blocks"]:
                    sub_dict = grup_dict["sub_blocks"][sub_block]
                    self.new_data_list.append(b'GRUP' + sub_dict["size"] + sub_dict["data"][8:])
                    for cell in sub_dict["cells"]:
                        self.new_data_list.append(cell)
        if len(self.wrld_dict) == 0:
            self.new_data_list.pop()

        # Convert keys to strings from byte strings for interior cell dict
        str_new_interior_dict = {}
        for grup_block in self.new_interior_cell_dict:
            grup_dict = self.new_interior_cell_dict[grup_block]
            str_grup_block = grup_block.hex()
            str_new_interior_dict[str_grup_block] = {"data": grup_dict["data"].hex(),
                                                     "size": int.from_bytes(grup_dict["size"], 'little'),
                                                     "source_plugin": grup_dict["source_plugin"],
                                                     "sub_blocks": {}}
            for sub_block in grup_dict["sub_blocks"]:
                sub_dict = grup_dict["sub_blocks"][sub_block]
                str_sub_block = sub_block.hex()
                str_new_interior_dict[str_grup_block]["sub_blocks"][str_sub_block] = {"data": sub_dict["data"].hex(),
                                                                                    "size": int.from_bytes(sub_dict["size"],'little'),
                                                                                    "source_plugin": sub_dict["source_plugin"],
                                                                                    "cells": []}
                for cell in sub_dict["cells"]:
                    str_new_interior_dict[str_grup_block]["sub_blocks"][str_sub_block]["cells"].append(cell.hex())

        # Convert keys to strings from byte strings for wrld cell dict
        str_wrld_dict = {}
        for wrld_id in self.wrld_dict:
            wrld_dict = self.wrld_dict[wrld_id]
            str_wrld_id = wrld_id.hex()
            str_wrld_dict[str_wrld_id] = {"data": wrld_dict["data"].hex(),
                                          "size": int.from_bytes(wrld_dict["size"], "little"),
                                          "grup_data": wrld_dict["grup_data"].hex(),
                                          "persistent_cell_data": wrld_dict["persistent_cell_data"].hex(),
                                          "source_plugin": wrld_dict["source_plugin"],
                                          "blocks": {}}
            for grup_block in wrld_dict["blocks"]:
                grup_dict = wrld_dict["blocks"][grup_block]
                str_grup_block = grup_block.hex()
                str_wrld_dict[str_wrld_id]["blocks"][str_grup_block] = {"data": grup_dict["data"].hex(),
                                                                        "size": int.from_bytes(grup_dict["size"], 'little'),
                                                                        "source_plugin": grup_dict["source_plugin"],
                                                                        "sub_blocks": {}}
                for sub_block in grup_dict["sub_blocks"]:
                    sub_dict = grup_dict["sub_blocks"][sub_block]
                    str_sub_block = sub_block.hex()
                    str_wrld_dict[str_wrld_id]["blocks"][str_grup_block]["sub_blocks"][str_sub_block] = {"data": sub_dict["data"].hex(),
                                                                                        "size": int.from_bytes(sub_dict["size"],'little'),
                                                                                        "source_plugin": sub_dict["source_plugin"],
                                                                                        "cells": []}
                    for cell in sub_dict["cells"]:
                        str_wrld_dict[str_wrld_id]["blocks"][str_grup_block]["sub_blocks"][str_sub_block]["cells"].append(cell.hex())
        
        dump_dict = {
            "counter": self.counter,
            "interior_cells_dict": str_new_interior_dict,
            "wrld_dict": str_wrld_dict
        }
        with open('ESLifier_Data/cell_master_info.json', 'w', encoding='utf-8')as f:
            json.dump(dump_dict, f , ensure_ascii=False, indent=4)
        with open(self.output_file, 'wb') as f:
            f.write(b''.join(self.new_data_list))
            f.close()