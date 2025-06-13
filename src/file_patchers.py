try:
    import regex as re
except ImportError:
    import re
import json
import json5
import os

class patchers():    
    def find_prev_non_alphanumeric(text, start_index):
        for i in range(start_index, 0, -1):
            if not text[i].isalnum() and text[i] != ' ':
                return i
        return -1

    def find_next_non_alphanumeric(text, start_index):
        for i in range(start_index, len(text)):
            if not text[i].isalnum():
                return i
        return len(text)
    
    def facegeom_mesh_patcher(basename, new_file, form_id_map):
        with open(new_file, 'rb+') as f:
            data = f.readlines()
            bytes_basename = bytes(basename, 'utf-8')
            for i in range(len(data)):
                if bytes_basename in data[i].lower(): #check for plugin name, in file path, in line of nif file.
                    for form_ids in form_id_map:
                        data[i] = data[i].replace(form_ids[0].encode(), form_ids[1].encode()).replace(form_ids[0].encode().lower(), form_ids[1].encode().lower())
            f.seek(0)
            f.writelines(data)
    
    def seq_patcher(new_file, form_id_map, dependent=False):
        with open(new_file, 'rb+') as f:
            data = f.read()
            seq_form_id_list = [data[i:i+4] for i in range(0, len(data), 4)]
            if not dependent:
                form_id_dict = form_id_map
            else:
                form_id_dict = {old_id: new_id for old_id, new_id in form_id_map}
            new_seq_form_id_list = [form_id_dict.get(fid, fid) for fid in seq_form_id_list]
            f.seek(0)
            f.truncate(0)
            f.write(b''.join(new_seq_form_id_list))
            f.close()
        
    def pex_patcher(basename, new_file, form_id_map):
        with open(new_file,'rb+') as f:
            data = f.read()
            data = bytearray(data)
            src_name_length = int.from_bytes(data[16:18])
            offset = 18 + src_name_length
            username_length = int.from_bytes(data[offset:offset+2])
            offset += 2 + username_length
            machine_name_length = int.from_bytes(data[offset:offset+2])
            offset += 2 + machine_name_length
            string_count = int.from_bytes(data[offset:offset+2])
            offset += 2
            strings = []
            for _ in range(string_count):
                string_length = int.from_bytes(data[offset:offset+2])
                strings.append(data[offset+2:offset+2+string_length].lower())
                offset += 2 + string_length
            start_offset = offset
            master_name_bytes = basename.encode()
            index = strings.index(master_name_bytes)
            getformfromfile_index = strings.index(b'getformfromfile').to_bytes(2)
            data_size = len(data)
            arrays = []
            patch_arrays = False
            while offset < data_size:
                if data[offset:offset+1] == b'\x03' and data[offset+5:offset+6] == b'\x02' and int.from_bytes(data[offset+6:offset+8]) == index:
                    integer_variable = data[offset+2:offset+5]
                    to_id_data = form_id_map.get(int.from_bytes(integer_variable))
                    if to_id_data is not None:
                        data[offset+2:offset+5] = to_id_data["bytes"][::-1][1:]
                        offset += 6
                        if to_id_data["update_name"]:
                            print(f'~Ineligible: {basename} -> ESLifier_Cell_Master.esm | 0x{integer_variable.hex()} -> 0x{to_id_data["hex_no_0"]} | {new_file}')
                elif not patch_arrays and data[offset:offset+2] == b'\x1E\x01':
                    patch_arrays = True
                offset += 1
            if patch_arrays:
                offset = start_offset
                last_offset = 0
                while offset < data_size:
                    if data[offset:offset+2] == b'\x1E\x01' and data[offset+4:offset+5] == b'\x03':
                        last_offset = offset + 16
                        array = {'id': data[offset+10:offset+13], 'integers': [], 'patch': False}
                        offset += 16
                        temp_var = data[offset+1:offset+4]
                        while offset < data_size:
                            if data[offset:offset+1] == b'\x0D' and data[offset+1:offset+4] == temp_var:
                                offset +=4
                                array['integers'].append([offset+2, data[offset+2:offset+5]])
                                offset +=17
                            else:
                                break
                        while offset < data_size:
                            if data[offset:offset+3] == array['id']:
                                if data[offset+6:offset+7] == b'\x19':
                                    offset += 10
                                    if data[offset:offset+1] == b'\x01' and data[offset+1:offset+3] == getformfromfile_index:
                                        offset += 14
                                        if data[offset:offset+1] == b'\x02' and data[offset+1: offset+3] == index.to_bytes(2):
                                            array['patch'] = True
                                break
                            offset += 1
                        arrays.append(array)
                        offset = last_offset
                    offset +=1
                for array in arrays:
                    if array['patch'] == True:
                        for int_offset, integer in array['integers']:
                            to_id_data = form_id_map.get(integer)
                            if to_id_data is not None:
                                data[int_offset:int_offset+3] = to_id_data["bytes"][::-1][1:]
                                if to_id_data["update_name"]:
                                    print(f'~Ineligible: {basename} -> ESLifier_Cell_Master.esm | 0x{integer.to_bytes(4).hex()} -> 0x{to_id_data["hex_no_0"]} | {new_file}')
            data = bytes(data)
            f.seek(0)
            f.truncate(0)
            f.write(data)
            f.close()

    def ini_season_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if not ';' in line and basename in line.lower():
                    index_1 = line.find('~')
                    index_2 = line.find('|', index_1)
                    index_3 = line.find('~', index_2)
                    plugin_1 = line[index_1+1:index_2]
                    plugin_2 = line[index_3+1:]
                    form_id_1 = line[:index_1]
                    form_id_2 = line[index_2+1:index_3]
                    replace_1 = False
                    replace_2 = False
                    if basename == plugin_1.lower().strip():
                        form_id_int_1 = int(form_id_1, 16)
                        to_id_data = form_id_map.get(form_id_int_1)
                        if to_id_data is not None:
                            form_id_1 = '0x' + to_id_data['hex_no_0']
                            replace_1 = to_id_data["update_name"]
                    if basename == plugin_2.lower().strip():
                        form_id_int_2 = int(form_id_2, 16)
                        to_id_data = form_id_map.get(form_id_int_2)
                        if to_id_data is not None:
                            form_id_2 = '0x' + to_id_data['hex_no_0']
                            replace_2 = to_id_data["update_name"]

                    if not replace_1 and not replace_2:
                        lines[i] = form_id_1 + '~' + plugin_1 + '|' + form_id_2 + '~' + plugin_2
                    elif replace_1 and not replace_2:
                        lines[i] = form_id_1 + '~' + "ESLifier_Cell_Master.esm" + "|" + form_id_2 + '~' + plugin_2
                    elif not replace_1 and replace_2:
                        lines[i] = form_id_1 + '~' + plugin_1 + '|' + form_id_2 + "~" + "ESLifier_Cell_Master.esm" + '\n'
                    else:
                        lines[i] = form_id_1 + '~' + "ESLifier_Cell_Master.esm" + "|" + form_id_2 + "~" + "ESLifier_Cell_Master.esm" + '\n'
                    if replace_1 or replace_2 and print_replace:
                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                        print_replace = False
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def ini_pi_dtry_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and '|' in line and not line.startswith(';'):
                    end_index = line.rfind('|', 0, line.lower().index(basename))
                    start_index = line.rfind('|', 0, end_index)
                    start_of_line = line[:start_index+1]
                    end_of_line = line[end_index:]
                    form_id_int = int(line[start_index+1:end_index],16)
                    plugin = line[end_index+1:].strip().lower()
                    if '|' in plugin:
                        split_string = plugin.split('|', 1)
                        plugin = split_string[0].strip()
                        end = '|' + split_string[1]
                    else:
                        end = ''
                    if line.endswith('\n'):
                        end += '\n'
                    if plugin == basename:
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False
                                lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + "|ESLifier_Cell_Master.esm" + end
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and '~' in line and not line.startswith(';'):
                    count = line.lower().count('~')
                    start = 0
                    for _ in range(count):
                        line = lines[i]
                        middle_index = line.index('~', start)
                        start_index = patchers.find_prev_non_alphanumeric(line, middle_index-2)
                        end_index = line.index('.es', middle_index) + 3
                        plugin = line.lower()[middle_index+1:end_index+1].strip()
                        start_of_line = line[:start_index+1]
                        end_of_line = line[middle_index:]
                        form_id = line[start_index+1:middle_index].strip()
                        if len(form_id) > 8: # 0x accounts for 2
                            if form_id[2:4] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        form_id_int = int(form_id, 16)
                        start = middle_index+1
                        if basename == plugin:
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                                else:
                                    if print_replace:
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + "~ESLifier_Cell_Master.esm" + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()
       
    def ini_mu_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and '|' in line and not line.startswith(';'):
                    count = line.lower().count('|')
                    start = 0
                    for _ in range(count):
                        line = lines[i]
                        start_index = line.lower().index(basename, start)
                        middle_index = line.index('|', start_index)
                        end_index = patchers.find_next_non_alphanumeric(line, middle_index+1)
                        plugin = line.lower()[start_index:middle_index].strip()
                        start_of_line = line[:middle_index+1]
                        end_of_line = line[end_index:]
                        form_id_int = int(line[middle_index+1:end_index], 16)
                        start = start_index + 1
                        if plugin == basename:
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                                else:
                                    if print_replace:
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = line[:start_index] + "ESLifier_Cell_Master.esm|" + '0x' + to_id_data["hex_no_0"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()
        
    def ini_sp_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and '|' in line and not line.startswith(';'):
                    count = line.lower().count('|')
                    start = 0
                    for _ in range(count):
                        line = lines[i]
                        start_index = line.lower().index('.es', start)
                        middle_index = line.index('|', start_index)
                        plugin_start_index = -1
                        for j in range(start_index-1, 0, -1):
                            if line[j] in ('=', ','):
                                plugin_start_index = j + 1
                                break
                        end_index = patchers.find_next_non_alphanumeric(line, middle_index+1)
                        plugin = line[plugin_start_index:middle_index]
                        start_of_line = line[:plugin_start_index]
                        end_of_line = line[end_index:]
                        form_id = line[middle_index+1:end_index]
                        if len(form_id) > 6:
                            if form_id[:2] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        try:
                            form_id_int = int(form_id, 16)
                            start = start_index+3
                            if plugin.lower().strip() == basename:
                                to_id_data = form_id_map.get(form_id_int)
                                if to_id_data is not None:
                                    if not to_id_data["update_name"]:
                                        lines[i] = start_of_line + plugin + '|' + to_id_data["hex_no_0"] + end_of_line
                                    else:
                                        if print_replace:
                                            print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                            print_replace = False
                                        lines[i] = start_of_line + "ESLifier_Cell_Master.esm|" + to_id_data["hex_no_0"] + end_of_line
                                        start += len('ESLifier_Cell_Master.esm') - len(plugin)
                        except:
                            start = start_index+3
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def ini_eq_plugin_sep_fid_patcher(basename, new_file, form_id_map, sep='|', encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and sep in line and '=' in line and not line.startswith(';'):
                    ox = False
                    middle_index = line.index(sep)
                    plugin_index = line.index('=') + 1
                    plugin = line[plugin_index:middle_index].lower().strip()
                    if plugin == basename:
                        end_index = patchers.find_next_non_alphanumeric(line, middle_index+1)
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
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False   
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "0x" + to_id_data["hex_no_0"] + end_of_line
                            else:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '00' + to_id_data["hex"] + end_of_line
                                else:
                                    if print_replace:
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "00" + to_id_data["hex"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def ini_ab_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.lower().startswith(basename) and '|' in line and not line.startswith(';'):
                    middle_index = line.index('|')
                    end_index = patchers.find_next_non_alphanumeric(line, middle_index+1)
                    start_of_line = line[:middle_index+1]
                    end_of_line = line[end_index:]
                    form_id_int = int(line[middle_index+1:end_index], 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        lines[i] = start_of_line + to_id_data["hex_no_0"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()
            
    # No Cell Form IDs possible
    def ini_rla_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            required_perk = ''
            rpi = 0
            for i, line in enumerate(lines):
                if line.startswith('requiredPerk'):
                    required_perk = line.removeprefix('requiredPerk =').strip()
                    rpi = i
                if line.startswith('modName'):
                    mod_name = line.removeprefix('modName =').strip().lower()
                    if mod_name == basename:
                        form_id_int = int(required_perk, 16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            lines[rpi] = 'requiredPerk = ' + to_id_data["hex_no_0"] + '\n'
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def ini_exp_knt_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            patch_following = False
            for i, line in enumerate(lines):
                if line.startswith('[') and '['+basename+']' in line.lower():
                    patch_following = True
                elif line.startswith('['):
                    patch_following = False
                if patch_following and line.startswith('00') or line.lower().startswith('0x'):
                    index = line.index('=')
                    form_id_int = int(line[:index], 16)
                    if line.lower().startswith('0x'):
                        ox = True
                    else:
                        ox = False
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        if not ox:
                            lines[i] = '00' + to_id_data["hex"] + line[index-1:]
                        else:
                            lines[i] = '0x' + to_id_data["hex"] + line[index-1:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()
    
    # No Cell Form IDs possible
    def ini_nup_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if ','+basename+'>' in line.lower() and not line.startswith(';'):
                    count = line.count('<')
                    start = 0
                    for _ in range(count):
                        line = lines[i]
                        start_index = line.index('<', start) + 1
                        stop_index = line.index('>', start_index)
                        end_index = line.find(',', start_index, stop_index)
                        start = start_index+2
                        if end_index != -1 and line[end_index+1:].lower().startswith(basename):
                            form_id_int = int(line[start_index:end_index], 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                lines[i] = line[:start_index] + to_id_data["hex_no_0"] + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    comp_print_replace = True
    def ini_completionist_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            start_patching = False
            plugin_to_patch = ''
            global_replace = False
            in_form_ids = False
            end_tag = 'ENDTAG'
            for i, line in enumerate(lines):
                if not start_patching and line.startswith('PluginFileName'):
                    index = line.index('=')+1
                    plugin_to_patch = line[index:].strip().lower()
                    if plugin_to_patch == basename:
                        global_replace = True
                if not in_form_ids and line.startswith('FormIDs'):
                    if '<<<' in line:
                        in_form_ids = True
                        index = line.index('<<<')+3
                        end_tag = line[index:].strip()
                        continue
                    else:
                        lines[i] = patchers.comp_layout_3_processor(global_replace, basename, line, form_id_map)
                if in_form_ids and line.strip() == end_tag:
                    in_form_ids = False
                
                if in_form_ids:
                    lines[i] = patchers.comp_form_id_processor(line, basename, global_replace, form_id_map, True)

                if not in_form_ids and line.startswith('0x') and '=' in line:
                    lines[i] = patchers.comp_variable_from_id(line, basename, global_replace, form_id_map)

            if not patchers.comp_print_replace:
                print(f'~Plugin Name Replaced: {basename} | {new_file}')
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def comp_form_id_replacer(form_id, form_id_map):
        if '0x' in form_id.lower():
            form_id_int = int(form_id, 16)
            to_id_data = form_id_map.get(form_id_int)
            if to_id_data is not None:
                if to_id_data["update_name"] and patchers.comp_print_replace:
                    patchers.comp_print_replace = False
                return '0x' + to_id_data["hex"], to_id_data["update_name"]
            return form_id, False
        else:
            return form_id, False

    def comp_variable_from_id(line, basename, global_replace, form_id_map):
        equal_index = line.index('=')
        variable = line[:equal_index]
        var_end = False
        if '_' in variable:
            index = variable.index('_')
            form_id = variable[:index]
            var_end = True
            variable_end = variable[index:]
        else:
            form_id = variable
        if global_replace:
            form_id, replace_name_ignored = patchers.comp_form_id_replacer(form_id, form_id_map)
            variable = form_id
            if var_end:
                variable += variable_end
            else:
                variable += ' '
        line = variable + line[equal_index:]
        line = patchers.comp_layout_3_processor(global_replace, basename, line, form_id_map)
        return line

    def comp_layout_3_processor(global_replace, basename, line, form_id_map):
        # This assumes that no plugin name has a comma. If one does then it probably breaks completionist anyways.
        start_index = line.index('=')+1
        parts = [part for part in line[start_index:].split(',') if part]
        append_newline = False
        if parts[-1] == '\n':
            append_newline = True
            parts.pop()
        for i, form_id_string in enumerate(parts):
            parts[i] = patchers.comp_form_id_processor(form_id_string, basename, global_replace, form_id_map, False)
        return_string = line[:start_index] + ' ' + ', '.join(parts) + ','
        if append_newline:
            return_string += '\n'
        return return_string

    def comp_form_id_processor(form_id_string, basename, global_replace, form_id_map, has_comma):
        if has_comma:
            index = form_id_string.index(',')
            end_of_line = form_id_string[index:]
            form_id_string = form_id_string[:index]
        if '*' in form_id_string:
            index = form_id_string.index('*')
            if '<' in form_id_string:
                add_end = True
                end_index = form_id_string.index('<')
            else:
                add_end = False
                end_index = len(form_id_string)
            plugin = form_id_string[index+1:end_index].strip()
            if plugin.lower() == basename:
                form_id = form_id_string[:index]
                form_id, replace_name = patchers.comp_form_id_replacer(form_id, form_id_map)
                if add_end:
                    end = form_id_string[end_index:]
                    if not replace_name:
                        form_id_string = form_id + '*' + plugin + end
                    else:
                        form_id_string = form_id + '*' + "ESLifier_Cell_Master.esm" + end
                else:
                    if not replace_name:
                        form_id_string = form_id + '*' + plugin
                    else:
                        form_id_string = form_id + '*' + "ESLifier_Cell_Master.esm"

        elif '<' in form_id_string:
            end_index = form_id_string.index('<')
            form_id = form_id_string[:end_index]
            end = form_id_string[end_index:]
            form_id, replace_name = patchers.comp_form_id_replacer(form_id, form_id_map)
            if replace_name:
                form_id += "*" + "ESLifier_Cell_Master.esm"
            form_id_string = form_id + end
            
        elif global_replace:
            form_id, replace_name = patchers.comp_form_id_replacer(form_id_string, form_id_map)
            form_id_string = form_id
            if replace_name:
                form_id_string += "*" + "ESLifier_Cell_Master.esm"
            
        if has_comma:
            form_id_string += end_of_line
        return form_id_string

    def ini_kreate_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        edid_file = 'ESLifier_Data\\EDIDs\\' + basename + '_EDIDs.txt'
        edids = []
        with open(edid_file, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                edids.append(line.strip())
        edid_name = os.path.basename(new_file).removesuffix('.ini')
        # assume everything in a preset is meant for one weather mod or does not share ANY Form IDs with other weather mods
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith('ID =') and edid_name in edids:
                    index = line.index('=')
                    form_id_int = int(line[index+1:],16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        lines[i] = 'ID = 0xFE' + to_id_data["hex"] + '\n'
                elif 'ID' in line and '= 0x' in line:
                    index = line.index('=')
                    form_id_int = int(line[index+1:], 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        lines[i] = line[:index+1] + ' 0xFE' + to_id_data["hex"] + '\n'
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def toml_dac_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            dac_toml_type = 'new'
            events = []
            for i, line in enumerate(lines):
                if 'espname' in line.lower():
                    dac_toml_type = 'old'
                elif '[[event]]' in line.lower():
                    events.append(i)
                    
            if dac_toml_type == 'new':
                for i, line, in enumerate(lines):
                    if basename in line.lower() and '|' in line:
                        count = line.lower().count('|')
                        start = 0
                        for _ in range(count):
                            line = lines[i]
                            start_index = line.lower().index('.', start)
                            middle_index = line.index('|', start_index)
                            plugin_start_index = -1
                            for j in range(start_index-1, 0, -1):
                                if line[j] == '"':
                                    plugin_start_index = j + 1
                                    break
                            plugin = line.lower()[plugin_start_index:middle_index].strip()
                            start = start_index + 1
                            if plugin == basename:
                                end_index = patchers.find_next_non_alphanumeric(line, middle_index+1)
                                start_of_line = line[:middle_index+1]
                                end_of_line = line[end_index:]
                                form_id_int = int(line[middle_index+1:end_index], 16)
                                to_id_data = form_id_map.get(form_id_int)
                                if to_id_data is not None:
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
            else:
                plugin_offsets = [3, 5, 9, 11, 13, 15]
                for event in events:
                    for offset in plugin_offsets:
                        if basename in lines[event + offset].lower():
                            if offset == 9:
                                form_id_offsets = [6,7]
                            else:
                                form_id_offsets = [event + offset - 1]
                            if offset != 15:
                                for form_id_offset in form_id_offsets:
                                    line = lines[form_id_offset]
                                    index = line.index('=')
                                    start_of_line = line[:index+1]
                                    end_index = patchers.find_next_non_alphanumeric(line, index + 3)
                                    end_of_line = line[end_index:]
                                    form_id_int = int(line[index+1:], 16)
                                    to_id_data = form_id_map.get(form_id_int)
                                    if to_id_data is not None:
                                        lines[form_id_offset] = start_of_line + ' 0x' + to_id_data["hex_no_0"] + end_of_line
                            else:
                                form_id_offset = form_id_offsets[0]
                                count = lines[form_id_offset].count(',') + 1
                                start_index = lines[form_id_offset].index('[')
                                for _ in range(count):
                                    line = lines[form_id_offset]
                                    end_index = patchers.find_next_non_alphanumeric(line,start_index+1)
                                    start_of_line = line[:start_index+1]
                                    end_of_line = line[end_index:]
                                    id = line[start_index+1:end_index]
                                    form_id_int = int(id, 16)
                                    to_id_data = form_id_map.get(form_id_int)
                                    if to_id_data is not None:
                                        lines[form_id_offset] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                                    start_index = patchers.find_next_non_alphanumeric(lines[form_id_offset], start_index+1) + 1
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def toml_precision_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if basename in line.lower() and 'formid' in line.lower():
                    count = line.count('{')
                    start = 0
                    for _ in range(count):
                        line = lines[i]
                        formid_index = line.lower().index('0x', start)
                        plugin_index = line.index('"', formid_index)
                        plugin_end_index = line.index('"', plugin_index+1)
                        plugin = line.lower()[plugin_index+1:plugin_end_index].strip()
                        if plugin == basename:
                            formid_end_index = patchers.find_next_non_alphanumeric(line, formid_index)
                            form_id_int = int(line[formid_index:formid_end_index], 16)
                            start_of_line = line[:formid_index]
                            end_of_line = line[formid_end_index:]
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                        start = formid_index + 1
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def toml_loki_tdm_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if '"'+basename+'"' in line.lower() and line.lower().startswith('plugin'):
                    i = i - 1
                    line = lines[i]
                    index = line.lower().index('0x')
                    end_index = patchers.find_next_non_alphanumeric(line, index)
                    start_of_line = line[:index]
                    end_of_line = line[end_index:]
                    form_id_int = int(line[index:end_index],16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def toml_avg_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if basename in line.lower() and 'object:' in line.lower() and '::' in line.lower():
                    index = line.lower().index('::0x') + 2
                    object_index = line.lower().index("object: ") + 7
                    end_index = patchers.find_next_non_alphanumeric(line, index)
                    form_id = line[index:end_index]
                    plugin = line[object_index:index-2].lower().strip()
                    if plugin == basename:
                        if form_id != '0x':
                            start_of_line = line[:index]
                            end_of_line = line[end_index:]
                            form_id_int = int(form_id,16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map, symbol = '|', encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            ox = False
            print_replace = True
            for path, value in json_dict:
                if type(value) is str and symbol in value:
                    index = value.index(symbol)
                    plugin = value[:index]
                    if plugin.lower() == basename:
                        form_id = value[index+1:]
                        form_id_int = int(form_id, 16)
                        if not ox and '0x' in form_id.lower():
                            ox = True
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if not ox:
                                    data = patchers.change_json_element(data, path, plugin + symbol + to_id_data["hex_no_0"])
                                else:
                                    data = patchers.change_json_element(data, path, plugin + symbol + '0x' + to_id_data["hex_no_0"])
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox:
                                    data = patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + symbol + to_id_data["hex_no_0"])
                                else:
                                    data = patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + symbol + '0x' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_generic_formid_sep_plugin_patcher(basename, new_file, form_id_map, int_type=False, symbol = '|', encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if type(value) is str and symbol in value:
                    ox = False
                    int_type_actual = int_type
                    index = value.index(symbol)
                    plugin = value[index+1:]
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
                                    data = patchers.change_json_element(data, path, to_id_data["hex_no_0"] + symbol + plugin)
                                elif ox:
                                    data = patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + symbol + plugin)
                                else: # not ox and int_type
                                    data = patchers.change_json_element(data, path, str(int(to_id_data["hex_no_0"], 16)) + symbol + plugin)
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox and not int_type_actual:
                                    data = patchers.change_json_element(data, path, to_id_data["hex_no_0"] + symbol + "ESLifier_Cell_Master.esm")
                                elif ox:
                                    data = patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + symbol + "ESLifier_Cell_Master.esm")
                                else: # not ox and int_type
                                    data = patchers.change_json_element(data, path, str(int(to_id_data["hex_no_0"], 16)) + symbol +"ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()
    
    def json_oar_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            plugin = False
            plugin_name_path = []
            print_replace = True
            for path, value in json_dict:
                if type(path[-1]) is str and 'pluginname' == path[-1].lower() and value.lower() == basename:
                    plugin = True
                    plugin_name_path = path
                elif plugin and type(path[-1]) is str and 'formid' == path[-1].lower():
                    form_id_int = int(value, 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_element(data, path, to_id_data["hex_no_0"])
                        if to_id_data["update_name"]:
                            if print_replace:
                                print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                print_replace = False  
                            data = patchers.change_json_element(data, plugin_name_path, "ESLifier_Cell_Master.esm")
                else:
                    plugin = False
                    plugin_name_path = []
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_sud_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if type(value) is str and '|' in value:
                    index = value.index('|')
                    plugin = value[index+1:]
                    if plugin.lower() == basename:
                        form_id = value[:index]
                        if '0x' in form_id:
                            ox = True
                            form_id_int = int(value[:index],16)
                        else:
                            ox = False
                            form_id_int = int(value[:index])
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if ox:
                                    data = patchers.change_json_element(data, path, '0x'+ to_id_data["hex_no_0"] + '|' + plugin)
                                else:
                                    data = patchers.change_json_element(data, path, str(to_id_data["int"]) + '|' + plugin)
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if ox:
                                    data = patchers.change_json_element(data, path, '0x'+ to_id_data["hex_no_0"] + '|' + "ESLifier_Cell_Master.esm")
                                else:
                                    data = patchers.change_json_element(data, path, str(to_id_data["int"]) + '|' + "ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    # No Cell Form IDs possible
    def json_obody_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            for path, value in json_dict:
                if len(path) > 2 and type(path[-3]) is str and basename == path[-3].lower():
                    if len(path[-2]) > 6:
                        form_id = path[-2][-6:]
                        if len(path[-2]) == 7: fid_start = path[-2][:1]
                        else: fid_start = path[-2][:2]
                    else:
                        fid_start = ''
                        form_id = path[-2]
                    form_id_int = int(form_id, 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_key(data, fid_start + form_id, fid_start + to_id_data["hex"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_sum_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if type(value) is str and '|' + basename in value.lower():
                    count = value.lower().count('|'+basename)
                    start_index = 0
                    changed = False
                    for _ in range(count):
                        plugin_index = value.lower().index('|'+basename, start_index)
                        plugin = value[plugin_index+1:plugin_index+len(basename)+1]
                        start_index = plugin_index + 4
                        if plugin.lower() == basename:
                            form_id_index = patchers.find_prev_non_alphanumeric(value,plugin_index-1) + 1
                            start = value[:form_id_index]
                            end = value[plugin_index:]
                            form_id = value[form_id_index:plugin_index]
                            form_id_int = int(form_id, 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    value = start + '0x' + to_id_data["hex"] + end
                                else:
                                    if print_replace:
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False  
                                    value = start + '0x' + to_id_data["hex"] + '|ESLifier_Cell_Master.esm' + value[plugin_index+len(basename)+1:]
                                changed = True
                    if changed:
                        data = patchers.change_json_element(data, path, value)
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def dar_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if '"'+basename+'"' in line.lower() and '|' in line:
                    index = line.index('|')
                    end_index = patchers.find_next_non_alphanumeric(line, index+2)
                    plugin_index = line.lower().index(basename)
                    if end_index != -1:
                        form_id_int = int(line[index+1:end_index], 16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                lines[i] = line[:index+1] + '0x' + to_id_data["hex"] + line[end_index:]
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False
                                lines[i] = line[:plugin_index] + 'ESLifier_Cell_Master.esm' + '" | 0x' + to_id_data["hex"] + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    def srd_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and '|' in line and not line.startswith('#'):
                    if '#' in line:
                        comment_index = line.index('#')
                        comment = True
                    else:
                        comment = False
                    index = line.index('|')
                    end_index = patchers.find_next_non_alphanumeric(line, index+1)
                    if comment and (index > comment_index or end_index > comment_index):
                        continue
                    end_of_line = line[end_index:]
                    form_id_int = int(line[index+1:], 16)
                    plugin_index = line.index(':')+1
                    plugin = line[plugin_index:index].lower().strip()
                    if plugin == basename:
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                lines[i] = line[:index+1] + to_id_data["hex"] + end_of_line
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False
                                lines[i] = line[:plugin_index] + " ESLifier_Cell_Master.esm" + '|' + to_id_data["hex"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()

    # No Cell Form IDs possible
    def jslot_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            read_string = f.read()
            while read_string[-1] != '}':
                read_string = read_string.removesuffix(read_string[-1])
            data = json.loads(read_string)
            if 'actor' in data and 'headTexture' in data['actor']:
                plugin_and_fid = data['actor']['headTexture']
                if plugin_and_fid[:-7].lower() == basename:
                    form_id_int = int(plugin_and_fid[-6:],16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        if not to_id_data["update_name"]:
                            data['actor']['headTexture'] = plugin_and_fid[:-6] + to_id_data["hex"]

            if 'headParts' in data:
                for i, part in enumerate(data['headParts']):
                    if 'formIdentifier' in part:
                        formIdentifier = part['formIdentifier']
                        if formIdentifier[:-7].lower() == basename:
                            formId = part['formId'].to_bytes(4)
                            form_id_int = int(formIdentifier[-6:],16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                new_form_id = formId[:1] + to_id_data["bytes"][::-1][1:]
                                data['headParts'][i]['formId'] = int.from_bytes(new_form_id)
                                data['headParts'][i]['formIdentifier'] = formIdentifier[:-6] + to_id_data["hex"]
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3, separators=(',', ' : '))
            f.close()

    def json_shse_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            plugin = False
            print_replace = True
            plugin_path = []
            for path, value in json_dict:
                if path[-1] == 'plugin' and basename == value.lower():
                    plugin = True
                    plugin_path = path
                elif plugin == True and path[-2] == 'form':
                    form_id_int = int(value,16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_element(data, path, '00' + to_id_data["hex"])
                        if to_id_data["update_name"]:
                            if print_replace:
                                print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                print_replace = False  
                            data = patchers.change_json_element(data, plugin_path, "ESLifier_Cell_Master.esm")
                else:
                    plugin = False
                    plugin_path = []
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dsd_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if path[-1] == 'form_id' and '|' in value:
                    index = value.index('|')
                    form_id = value[:index]
                    plugin = value[index+1:]
                    if plugin.lower() == basename:
                        form_id_int = int(form_id,16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                data = patchers.change_json_element(data, path, to_id_data["hex"] + '|' + plugin)
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                data = patchers.change_json_element(data, path, to_id_data["hex"] + '|' + "ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dkaf_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if type(value) is str and '|' in value:
                    index = value.find('|')
                    plugin = value[:index]
                    form_id_int = int(value[index+1:], 16)
                    if plugin.lower() == basename:
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                data = patchers.change_json_element(data, path, plugin + '|0x' + to_id_data["hex_no_0"])
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                data = patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + '|0x' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dav_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if len(path) > 2 and type(path[-2]) is str and 'replace' in path[-2]:
                    if path[-2] == 'replaceByForm':
                        index = path[-1].index('|')
                        plugin = path[-1][:index]
                        form_id_int = int(path[-1][index+1:], 16)
                        if plugin.lower() == basename:
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    data = patchers.change_json_key(data, path[-1], plugin + '|' + to_id_data["hex_no_0"])
                                else:
                                    if print_replace:
                                        print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    data = patchers.change_json_key(data, path[-1], "ESLifier_Cell_Master.esm" + '|' + to_id_data["hex_no_0"])
                    index = value.index('|')
                    plugin = value[:index]
                    form_id_int = int(value[index+1:], 16)
                    if plugin.lower() == basename:
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                data = patchers.change_json_element(data, path, plugin + '|' + to_id_data["hex_no_0"])
                            else:
                                if print_replace:
                                    print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False
                                data = patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + '|' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    # No Cell Form IDs possible
    def json_jcontainer_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            for path, value in json_dict:
                if type(value) is str and '__formdata' in value.lower():
                    formData_index = value.index('|')
                    index = value.index('|', formData_index+1)
                    plugin = value[formData_index+1:index]
                    if plugin.lower() == basename:
                        form_id_int = int(value[index+1:],16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            data = patchers.change_json_element(data, path, value[:index+1] + '0x' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_ied_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            form_id_int = 0
            form_id_path = []
            print_replace = True
            for path, value in json_dict:
                if path[-1] == 'id':
                    form_id_int = value
                    form_id_path = path
                if path[-1].lower() == 'plugin' and value.lower() == basename:
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_element(data, form_id_path, to_id_data["int"])
                        if to_id_data["update_name"]:
                            if print_replace:
                                print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                print_replace = False
                            data = patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False)
            f.close()

    def json_ostim_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            plugin = False
            print_replace = True
            plugin_path = []
            for path, value in json_dict:
                if type(path[-1]) is str and 'mod' == path[-1].lower() and value.lower() == basename:
                    plugin = True
                    plugin_path = path
                elif plugin and type(path[-1]) is str and 'formid' == path[-1].lower():
                    form_id_int = int(value, 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_element(data, path, "0x" + to_id_data["hex_no_0"])
                        if to_id_data["update_name"]:
                            if print_replace:
                                print(f'~Plugin Name Replaced: {basename} | {new_file}')
                                print_replace = False
                            data = patchers.change_json_element(data, plugin_path, "ESLifier_Cell_Master.esm")
                else:
                    plugin = False
                    plugin_path = []
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    # No Cell Form IDs possible
    def json_dressuplovers_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = patchers.use_json5(string)
            json_dict = patchers.extract_values_and_keys(data)
            patch_next_index = False
            for path, value in json_dict:
                if patch_next_index:
                    patch_next_index = False
                    form_id_int = int(value, 16)
                    to_id_data = form_id_map.get(form_id_int)
                    if to_id_data is not None:
                        data = patchers.change_json_element(data, path, to_id_data["hex"])
                if type(path[-1]) is int and path[-1] == 0 and value.lower() == basename:
                    patch_next_index = True
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def use_json5(json_string):
        return json5.loads(json_string)

    def extract_values_and_keys(json_data, path=[]):
        results = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if path:
                    new_path = path.copy()
                    new_path.append(key)
                else:
                    new_path = [key]
                results.extend(patchers.extract_values_and_keys(value, new_path))
        elif isinstance(json_data, list):
            for index, item in enumerate(json_data):
                if path:
                    new_path = path.copy()
                    new_path.append(index)
                else:
                    new_path = [index]
                results.extend(patchers.extract_values_and_keys(item, new_path))
        else:
            results.append((path, json_data))

        return results

    def change_json_element(data, path, new_value):
        if not path:
            return new_value
        
        key = path[0]
        if isinstance(data, dict):
            data[key] = patchers.change_json_element(data[key], path[1:], new_value)
        elif isinstance(data, list):
            index = int(key)
            data[index] = patchers.change_json_element(data[index], path[1:], new_value)
        return data

    def change_json_key(data, old_key, new_key):
        if isinstance(data, dict):
            if old_key in data:
                data[new_key] = data.pop(old_key)
            for key, value in data.items():
                patchers.change_json_key(value, old_key, new_key)
        elif isinstance(data, list):
            for item in data:
                patchers.change_json_key(item, old_key, new_key)
        return data
    
    def old_customskill_patcher(basename, new_file, form_id_map, encoding_method='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            patch_next_line = False
            for i, line in enumerate(lines):
                if patch_next_line and 'Id' in line:
                    index = line.index('=') + 1
                    start_of_line = line[:index]
                    end_index = patchers.find_next_non_alphanumeric(line, index + 1)
                    end_of_line = line[end_index:]
                    form_id = line[index:end_index]
                    if form_id.strip() != '':
                        form_id_int = int(form_id, 16)
                        if form_id_int != 0:
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                lines[i] = start_of_line + ' 0x' + to_id_data["hex_no_0"] + end_of_line
                            
                if 'File' in line and basename in line.lower():
                    patch_next_line = True
                else:
                    patch_next_line = False
                
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))
            f.close()
