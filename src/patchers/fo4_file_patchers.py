import json
import json5
import os

import configparser
import io
import struct
try:
    from patchers.shared_file_patchers import shared_patchers
    from log_stream import write_to_file, write_ineligible
except ImportError:
    from shared_file_patchers import shared_patchers
    def write_to_file(txt):
        print(str(f"write_to_file: {str(txt)}"))
    def write_ineligible(txt):
        print(str(f"write_ineligible: {str(txt)}"))

class patchers(shared_patchers):    
    @staticmethod
    def json_transfer_settlements_patcher(basename: str, new_file: str, form_id_map: dict, encoding_method: str ='utf-8'):
        def patch_hex_and_decimal(itm:dict, hex_key:str):
            form_id_hex = itm.get(hex_key)
            if form_id_hex:
                to_id_data = form_id_map.get(int(form_id_hex, 16))
                if to_id_data:
                    itm[hex_key] = to_id_data["hex"]
            int_key = f"{hex_key}_dec"
            form_id_int = itm.get(int_key)
            if form_id_int:
                to_id_data = form_id_map.get(int(form_id_int))
                if to_id_data:
                    itm[int_key] = to_id_data["int"]
        
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            header:dict = data.get("header")
            if header:
                header_keys = ("cell", "worldspace")
                for key in header_keys:
                    plugin:str = header.get(f"{key}_plugin")
                    if plugin and plugin.lower() == basename:
                        patch_hex_and_decimal(header, f"{key}_id")
            items:list[dict] = data.get("items")
            if items:
                for item in items:
                    plugin:str = item.get("plugin_name")
                    if plugin and plugin.lower() == basename:
                        patch_hex_and_decimal(item, f"FormID")

            f.seek(0)
            f.truncate(0)
            json.dump(data, f, indent="\t")

#if __name__ == '__main__':
#    import os
#    basename = "thing.esl".lower()
#    form_id_map = {int('8D8',16): {'hex_no_0': 'A0A', 'hex': '000A0A', 'int': 10, 'bytes': b'\x00\x0A\x0A', 'update_name': False}, 
#                   int('c00c',16): {'hex_no_0': 'B0B', 'hex': '000B0B', "int": 10101, 'bytes': b'\x00\x0B\x0B', 'update_name': True}}
#    new_file = os.path.normpath(r)
#    patchers.json_transfer_settlements_patcher(basename, new_file, form_id_map, encoding_method='utf-8')