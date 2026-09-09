import json
import json5
import os

import configparser
import io
from log_stream import write_to_file, write_ineligible

class shared_patchers():
    def find_prev_non_alphanumeric(text: str, start_index: int, tokens: set[str] = {}):
            """Use this with care, do not use this to find the start of a plugin name as plugins are files and can contain non-alphanumeric characters"""
            for i in range(start_index, -1, -1): #this was range(start_index, 0, -1) I have changed it to -1 as 0 was not 0 inclusive, I hope I didn't just break a bunch of stuff...
                if (not text[i].isalnum() and text[i] != ' ') or text[i] in tokens:
                    return i
            return -1
    
    def find_next_non_alphanumeric(text: str, start_index: int, tokens: set[str] = {}):
        for i in range(start_index, len(text)):
            if not text[i].isalnum() or text[i] in tokens:
                return i
        return len(text)

    def ini_formid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, 
                                      sep: str = '~', tkns: set[str] = {" "}, fid_start: str = '0x', to_id_key: str = "hex_no_0",
                                      encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if sep+basename in line.lower() and not line.startswith(';'):
                    count = line.lower().count(sep)
                    start = 0
                    final_index = line.index(';') if ';' in line else None
                    for _ in range(count):
                        line = lines[i]
                        middle_index = line.index(sep, start)
                        start_index = shared_patchers.find_prev_non_alphanumeric(line, middle_index-2, tokens=tkns)
                        if final_index is not None and start_index > final_index:
                            continue
                        end_index = line.index('.es', middle_index) + 4
                        plugin = line.lower()[middle_index+len(sep):end_index].strip()
                        start_of_line = line[:start_index+1]
                        end_of_line = line[middle_index:]
                        form_id = line[start_index+1:middle_index].strip()
                        start = middle_index+len(sep)
                        if not form_id.lower().startswith('0x'):
                            continue
                        if len(form_id) > 8: # 0x accounts for 2
                            if form_id[2:4] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        if basename == plugin: 
                            form_id_int = int(form_id, 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + fid_start + to_id_data[to_id_key] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = start_of_line + fid_start + to_id_data[to_id_key] + sep + "ESLifier_Cell_Master.esm" + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))            

    def ini_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict,
                                        sep: str = '~', tkns: set[str] = {" "}, fid_start: str = '0x', to_id_key: str = "hex_no_0",
                                        encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename+sep in line.lower() and not line.startswith(';'):
                    count = line.lower().count(basename+sep)
                    start = 0
                    final_index = line.index(';') if ';' in line else None
                    for _ in range(count):
                        line = lines[i]
                        start_index = line.lower().index(basename+sep, start)
                        if final_index is not None and start_index > final_index:
                            continue
                        middle_index = start_index + len(basename+sep)
                        end_index = shared_patchers.find_next_non_alphanumeric(line, middle_index+1, tokens=tkns)
                        plugin = line.lower()[start_index:middle_index-len(sep)].strip()
                        start_of_line = line[:start_index]
                        end_of_line = line[end_index:]
                        form_id = line[middle_index:end_index].strip()
                        start = middle_index+1
                        if not form_id.lower().startswith('0x'):
                            continue
                        if len(form_id) > 8: # 0x accounts for 2
                            if form_id[2:4] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        if basename == plugin: 
                            form_id_int = int(form_id, 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = line[:middle_index] + fid_start + to_id_data[to_id_key] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = start_of_line + "ESLifier_Cell_Master.esm" + sep + fid_start + to_id_data[to_id_key] + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))

    def ini_eq_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict, sep: str ='|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and sep in line and '=' in line and not line.strip().startswith(';'):
                    ox = False
                    middle_index = line.index(sep)
                    plugin_index = line.index('=') + 1
                    plugin = line[plugin_index:middle_index].lower().strip()
                    if plugin == basename:
                        end_index = shared_patchers.find_next_non_alphanumeric(line, middle_index+1)
                        start_of_line = line[:middle_index+1]
                        end_of_line = line[end_index:]
                        form_id = line[middle_index+1:end_index].lower().strip()
                        if form_id.startswith('0x'):
                            ox = True
                        form_id_int = int(form_id, 16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if ox:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False   
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "0x" + to_id_data["hex_no_0"] + end_of_line
                            else:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '00' + to_id_data["hex"] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "00" + to_id_data["hex"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))


        #IDK why I read it into a string for json5, probably was part of debugging way back when I first started, not going to touch it though.
    def safe_load_json(file_handle) -> dict:
        try:
            data = json.load(file_handle)
        except:
            file_handle.seek(0)
            string = file_handle.read()
            data = json5.loads(string)
        return data 

    def extract_values_and_keys(json_data, path=[]):
        results = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if path:
                    new_path = path.copy()
                    new_path.append(key)
                else:
                    new_path = [key]
                results.extend(shared_patchers.extract_values_and_keys(value, new_path))
        elif isinstance(json_data, list):
            for index, item in enumerate(json_data):
                if path:
                    new_path = path.copy()
                    new_path.append(index)
                else:
                    new_path = [index]
                results.extend(shared_patchers.extract_values_and_keys(item, new_path))
        else:
            results.append((path, json_data))

        return results

    def change_json_element(data, path, new_value):
        if not path:
            return new_value
        
        key = path[0]
        if isinstance(data, dict):
            data[key] = shared_patchers.change_json_element(data[key], path[1:], new_value)
        elif isinstance(data, list):
            index = int(key)
            data[index] = shared_patchers.change_json_element(data[index], path[1:], new_value)
        return data

    def change_json_key(data, old_key, new_key):
        if isinstance(data, dict):
            if old_key in data:
                data[new_key] = data.pop(old_key)
            for key, value in data.items():
                shared_patchers.change_json_key(value, old_key, new_key)
        elif isinstance(data, list):
            for item in data:
                shared_patchers.change_json_key(item, old_key, new_key)
        return data
    
    def json_generic_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict, sep: str = '|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            ox = False
            print_replace = True
            for path, value in json_dict:
                if isinstance(value, str) and sep in value:
                    index = value.index(sep)
                    plugin = value[:index]
                    if plugin.lower() == basename:
                        form_id = value[index+len(sep):]
                        form_id_int = int(form_id, 16)
                        if not ox and '0x' in form_id.lower():
                            ox = True
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if not ox:
                                    data = shared_patchers.change_json_element(data, path, plugin + sep + to_id_data["hex_no_0"])
                                else:
                                    data = shared_patchers.change_json_element(data, path, plugin + sep + '0x' + to_id_data["hex_no_0"])
                            else:
                                if print_replace:
                                    write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox:
                                    data = shared_patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + sep + to_id_data["hex_no_0"])
                                else:
                                    data = shared_patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + sep + '0x' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            

    def json_generic_formid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = '|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if isinstance(value, str) and sep in value:
                    ox = False
                    int_type_actual = int_type
                    index = value.index(sep)
                    plugin = value[index+len(sep):]
                    if plugin.lower() == basename:
                        form_id = value[:index]
                        if '0x' in form_id.lower():
                            ox = True
                        if ox or not int_type:
                            form_id_int = int(form_id, 16)
                        else:
                            try:
                                form_id_int = int(form_id)
                            except:
                                form_id_int = int(form_id, 16)
                                int_type_actual = False
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if not ox and not int_type_actual:
                                    data = shared_patchers.change_json_element(data, path, to_id_data["hex_no_0"] + sep + plugin)
                                elif ox:
                                    data = shared_patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + sep + plugin)
                                else: # not ox and int_type
                                    data = shared_patchers.change_json_element(data, path, str(to_id_data["int"]) + sep + plugin)
                            else:
                                if print_replace:
                                    write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox and not int_type_actual:
                                    data = shared_patchers.change_json_element(data, path, to_id_data["hex_no_0"] + sep + "ESLifier_Cell_Master.esm")
                                elif ox:
                                    data = shared_patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + sep + "ESLifier_Cell_Master.esm")
                                else: # not ox and int_type
                                    data = shared_patchers.change_json_element(data, path, str(to_id_data["int"]) + sep + "ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            
    
    def json_generic_key_fid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = ":", encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            patched_keys = []
            for path, value in json_dict:
                for i, part in enumerate(path):
                    if isinstance(part, str) and part.lower().endswith(sep + basename) and path[:i+1] not in patched_keys:
                        index = part.find(sep)
                        to_id_data = form_id_map.get(int(part[:index])) if int_type else form_id_map.get(int(part[:index],16))
                        if to_id_data is not None:
                            new_id = '0x' + to_id_data['hex'] if part.startswith('0x') else str(to_id_data['int']) if int_type else to_id_data['hex']
                            plugin = sep + 'ESLifier_Cell_Master.esm' if to_id_data['update_name'] else part[index:]
                            data = shared_patchers.change_json_key(data, part, new_id + plugin)
                            patched_keys.append(path[:i+1])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)

    def json_generic_key_plugin_sep_fid_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = ":", encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            patched_keys = []
            for path, value in json_dict:
                for i, part in enumerate(path):
                    if isinstance(part, str) and part.lower().startswith(basename+sep) and not path[:i+1] in patched_keys:
                        index = part.find(sep)
                        id_part = part[index+len(sep):]
                        to_id_data = form_id_map.get(int(id_part)) if int_type else form_id_map.get(int(id_part ,16))
                        if to_id_data is not None:
                            new_id = '0x' + to_id_data['hex'] if id_part.startswith('0x') else str(to_id_data['int']) if int_type else to_id_data['hex']
                            plugin = 'ESLifier_Cell_Master.esm' + sep if to_id_data['update_name'] else part[:index+len(sep)]
                            data = shared_patchers.change_json_key(data, part, plugin + new_id)
                            patched_keys.append(path[:i+1])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
