import os
import regex as re
#import re
import binascii
import shutil
import fileinput
import zlib
import json
import threading

#TODO: Further refinement of file patching, additional research on files that need patching

class CFIDs():
    def compact_and_patch(form_processor, file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        CFIDs.lock = threading.Lock()
        CFIDs.compacted_and_patched = {}
        CFIDs.mo2_mode = mo2_mode
        CFIDs.form_processor = form_processor
        size = os.path.getsize(file_to_compact)
        mb_size = round(size / 1048576, 3)
        print(f"Compacting Plugin: {os.path.basename(file_to_compact)} ({mb_size} MB)...")
        CFIDs.compact_file(file_to_compact, skyrim_folder_path, output_folder_path, update_header)
        if dependents != []:
            print(f"-  Patching {len(dependents)} Dependent Plugins...")
            CFIDs.patch_dependent_plugins(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header)
        
        files_to_patch = CFIDs.get_from_file('ESLifier_Data/file_masters.json')
        if os.path.basename(file_to_compact).lower() in files_to_patch.keys():
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(file_to_compact, files_to_patch[os.path.basename(file_to_compact).lower()]) #function to get files that need to be edited in some way to function correctly.
            form_id_map = CFIDs.get_form_id_map(file_to_compact)
            if len(to_patch) > 0:
                print(f"-  Patching {len(to_patch)} Dependent Files...")
                if len(to_patch) > 20:
                    print('\n')
                CFIDs.patch_files_threader(file_to_compact, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
            if len(to_rename) > 0:
                print(f"-  Renaming/Patching {len(to_rename)} Dependent Files...")
                if len(to_rename) > 20:
                    print('\n')
                CFIDs.rename_files_threader(file_to_compact, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')
        print('CLEAR ALT')
        return
    
    def dump_to_file(file):
        try:
            data = CFIDs.get_from_file(file)
        except:
            data = {}
        for key, value in CFIDs.compacted_and_patched.items():
            if key not in data.keys():
                data[key] = []
            for item in value:
                if item.lower() not in data[key]:
                    data[key].append(item.lower())

        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    
    def set_flag(file, skyrim_folder, output_folder):
        print("-  Changing ESL flag in: " + os.path.basename(file))
        new_file = CFIDs.copy_file_to_output(file, skyrim_folder, output_folder)
        with open(new_file, 'rb+') as f:
            f.seek(9)
            f.write(b'\x02')

    def patch_new(form_processor, compacted_file, dependents, files_to_patch, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        CFIDs.lock = threading.Lock()
        CFIDs.form_processor = form_processor
        CFIDs.compacted_and_patched = {}
        CFIDs.mo2_mode = mo2_mode
        print('Patching new plugins and files for ' + compacted_file + '...')
        CFIDs.compacted_and_patched[compacted_file] = []
        if dependents != []:
            print("-  Patching New Dependent Plugins...")
            CFIDs.patch_dependent_plugins(compacted_file, dependents, skyrim_folder_path, output_folder_path, update_header)
        if os.path.basename(compacted_file) in files_to_patch.keys():
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(compacted_file, files_to_patch[os.path.basename(compacted_file)])
            form_id_map = CFIDs.get_form_id_map(compacted_file)
            if len(to_rename) > 0:
                print(f"-  Patching {len(to_patch)} New Dependent Files...")
                if len(to_patch) > 20:
                    print('\n')
                CFIDs.patch_files_threader(compacted_file, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
            if len(to_rename) > 0:
                print(f"-  Renaming/Patching {len(to_rename)} New Dependent Files...")
                if len(to_rename) > 20:
                    print('\n')
                CFIDs.rename_files_threader(compacted_file, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')
        print('CLEAR ALT')

    #Create a copy of the mod plugin we're compacting
    def copy_file_to_output(file, skyrim_folder_path, output_folder):
        if CFIDs.mo2_mode:
            end_path = os.path.relpath(file, skyrim_folder_path)
            #part = relative_path.split('\\')
            #end_path = os.path.join(*part[1:])
        else:
            end_path = file[len(skyrim_folder_path) + 1:]
        new_file = os.path.join(os.path.join(output_folder,'ESLifier Compactor Output'), re.sub(r'(.*?)(/|\\)', '', end_path, 1))
        with CFIDs.lock:
            if not os.path.exists(os.path.dirname(new_file)):
                os.makedirs(os.path.dirname(new_file))
            if not os.path.exists(new_file):
                shutil.copy(file, new_file)
        return new_file
    
    #Get files (not including plugins) that may/will need old Form IDs replaced with the new Form IDs
    def sort_files_to_patch_or_rename(master, files):
        #hexaPattern = re.compile(r'([0-9a-fA-F]+){6,}[.](?!p)')
        files_to_patch = []
        files_to_rename = []
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '.jslot', '_srd.', os.path.splitext(os.path.basename(master))[0].lower() + '.seq']
        for file in files:
            if any(match in file.lower() for match in matchers):
                files_to_patch.append(file)
            elif os.path.basename(master).lower() in file.lower() and ('facegeom' in file.lower() or 'voice' in file.lower() or 'facetint' in file.lower()):
                files_to_rename.append(file)
            else:
                raise TypeError(f"File: {file} \nhas no patching method but it is in file_masters...")
        return files_to_patch, files_to_rename

    def rename_files_threader(master, files, form_id_map, skyrim_folder_path, output_folder_path):
        threads = []
        if len(files) > 100:
            split = 100
        elif len(files) > 50:
            split = 50
        else:
            split = 1

        chunk_size = len(files) // split
        chunks = [files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(files[(split) * chunk_size:])
        CFIDs.count = 0
        CFIDs.file_count = len(files)
        for chunk in chunks:
            thread = threading.Thread(target=CFIDs.rename_files, args=(master, chunk, form_id_map, skyrim_folder_path, output_folder_path))
            threads.append(thread)
            thread.start()
        
        for thread in threads: 
            thread.join()

    #Rename each file in the list of files from the old Form IDs to the new Form IDs
    def rename_files(master, files, form_id_map, skyrim_folder_path, output_folder_path):
        facegeom_meshes = []
        master_base_name = os.path.basename(master)
        for file in files:
            if CFIDs.file_count > 20:
                CFIDs.count += 1
                percent = CFIDs.count / CFIDs.file_count * 100
                factor = round(CFIDs.file_count * 0.001)
                if factor == 0:
                    factor = 1
                if (CFIDs.count % factor) >= (factor-1) or CFIDs.count >= CFIDs.file_count:
                    print('\033[F\033[K-    Percentage: ' + str(round(percent,1)) +'%\n-    Files: ' + str(CFIDs.count) + '/' + str(CFIDs.file_count), end='\r')
            
            parts = os.path.relpath(file, skyrim_folder_path).lower().split('\\')
            file_rel_path = os.path.join(*parts[1:])
            for form_ids in form_id_map:
                if form_ids[1].upper() in file.upper():
                    new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
                    renamed_file = new_file.replace(form_ids[1].upper(), form_ids[3].upper())
                    with CFIDs.lock:
                        os.replace(new_file, renamed_file)
                    #end_path = file[len(skyrim_folder_path) + 1:]
                    #new_file_but_skyrim_pathed = os.path.join(skyrim_folder_path, re.sub(r'(.*?)(/|\\)', '', end_path, 1))
                    parts = os.path.relpath(new_file, skyrim_folder_path).lower().split('\\')
                    rel_path_new_file = os.path.join(*parts[1:])
                    parts = os.path.relpath(renamed_file, skyrim_folder_path).lower().split('\\')
                    rel_path_renamed_file = os.path.join(*parts[1:])
                    with CFIDs.lock:
                        #if new_file_but_skyrim_pathed not in CFIDs.compacted_and_patched[master_base_name]:
                        #    CFIDs.compacted_and_patched[master_base_name].append(new_file_but_skyrim_pathed)
                        #if new_file not in CFIDs.compacted_and_patched[master_base_name]:
                        #    CFIDs.compacted_and_patched[master_base_name].append(new_file)
                        if rel_path_new_file not in CFIDs.compacted_and_patched[master_base_name]:
                            CFIDs.compacted_and_patched[master_base_name].append(rel_path_new_file)
                        if rel_path_renamed_file not in CFIDs.compacted_and_patched[master_base_name]:
                            CFIDs.compacted_and_patched[master_base_name].append(rel_path_renamed_file)
                        if 'facegeom' in new_file.lower() and master_base_name.lower() in new_file.lower():
                            facegeom_meshes.append(renamed_file)
                    break
            CFIDs.compacted_and_patched[master_base_name].append(file_rel_path.lower())
        if facegeom_meshes != []:
            CFIDs.patch_files(master, facegeom_meshes, form_id_map, skyrim_folder_path, output_folder_path, False)
        return

    #Create the Form ID map which is a list of tuples that holds four Form Ids that are in \xMASTER\x00\x00\x00 order:
    #original Form ID w/o leading 0s, original Form ID w/ leading 0s, new Form ID w/o 0s, new Form ID w/ 0s, 
    #the orginal Form ID in \x00\x00\x00\xMASTER order, and the new Form ID in the same order.
    def get_form_id_map(file):
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        form_id_map = []
        with open(form_id_file_name, 'r') as fidf:
            form_id_file_data = fidf.readlines()
        for form_id_history in form_id_file_data:
            form_id_conversion = form_id_history.split('|')

            from_id = bytes.fromhex(form_id_conversion[0])[::-1].hex()[2:].removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').upper()
            from_id_with_leading_0s = bytes.fromhex(form_id_conversion[0])[::-1].hex()[2:].upper()
            to_id = bytes.fromhex(form_id_conversion[1])[::-1].hex()[2:].removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').upper()
            to_id_with_leading_0s = bytes.fromhex(form_id_conversion[1])[::-1].hex()[2:].upper()
            from_id_little_endian = bytes.fromhex(form_id_conversion[0])
            to_id_little_endian = bytes.fromhex(form_id_conversion[1])

            form_id_map.append([from_id, from_id_with_leading_0s, to_id, to_id_with_leading_0s, from_id_little_endian, to_id_little_endian])
        return form_id_map

    def patch_files_threader(master, files, form_id_map, skyrim_folder_path, output_folder_path, flag):
        threads = []
        if len(files) > 50:
            split = 50
        elif len(files) > 5:
            split = 5
        else:
            split = 1

        chunk_size = len(files) // split
        chunks = [files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(files[(split) * chunk_size:])
        CFIDs.count = 0
        CFIDs.file_count = len(files)
        for chunk in chunks:
            if CFIDs.file_count > 20:
                CFIDs.count += 1
                percent = CFIDs.count / CFIDs.file_count * 100
                factor = round(CFIDs.file_count * 0.001)
                if factor == 0:
                    factor = 1
                if (CFIDs.count % factor) >= (factor-1) or CFIDs.count >= CFIDs.file_count:
                    print('\033[F\033[K-  Percentage: ' + str(round(percent,1)) +'%\n-  Files: ' + str(CFIDs.count) + '/' + str(CFIDs.file_count), end='\r')
            thread = threading.Thread(target=CFIDs.patch_files, args=(master, chunk, form_id_map, skyrim_folder_path, output_folder_path, flag))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()

    #Patches each file type in a different way as each has Form IDs present in a different format
    #Patched files:
    #   .ini: PO3's distributors, SkyPatcher
    #   config.json: OAR, MCM Helper
    #   _conditions.txt: DAR
    #   _srd.: Sound Record Distributor
    #   .psc: Source Scripts
    #   .json (not config.json): Dynamic Key Activation Framework NG, Smart Harvest Auto NG AutoLoot ::SHSE needs more work for multiline form id lists
    #                           Should work for MNC, Dynamic String Distributor
    #   .jslot: Racemenu files
    #   \facegeom\: Texture paths in face mesh files
    #   .seq: SEQ files
    #   .pex: Compiled script files, should patch any form id in a (formID, plugin) format.
    def patch_files(master, files, form_id_map, skyrim_folder_path, output_folder_path, flag):
        for file in files:
            if flag:
                new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
            else:
                new_file = file
            new_file_lower = new_file.lower()
            basename = os.path.basename(master).lower()
            with CFIDs.lock:
                if '.ini' in new_file_lower: #All of PO3's various distributors patching and whatever else uses ini files with form ids.
                    with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
                        if 'skypatcher' in new_file_lower:
                            for line in f:
                                if basename in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace('|' + form_ids[1], '|' + form_ids[3]).replace('|' + form_ids[0], '|' + form_ids[2]).replace('|' + form_ids[1].lower(), '|' + form_ids[3].lower()).replace('|' + form_ids[0].lower(), '|' + form_ids[2].lower())
                                print(line.strip('\n'))
                        else:
                            for line in f:
                                if basename in line.lower():
                                    for form_ids in form_id_map:
                                        #this is faster than re.sub by a lot ;_;
                                        line = line.replace('0x' + form_ids[0], '0x' + form_ids[2]).replace('0x' + form_ids[1], '0x' + form_ids[3]).replace('0x' + form_ids[0].lower(), '0x' + form_ids[2].lower()).replace('0x' + form_ids[1].lower(), '0x' + form_ids[3].lower()).replace('0X' + form_ids[0], '0X' + form_ids[2]).replace('0X' + form_ids[1], '0X' + form_ids[3]).replace('0X' + form_ids[0].lower(), '0X' + form_ids[2].lower()).replace('0X' + form_ids[1].lower(), '0X' + form_ids[3].lower())
                                print(line.strip('\n'))
                        fileinput.close()
                elif 'config.json' in new_file_lower: #Open Animation Replacer Patching and MCM helper
                    with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
                        if 'openanimationreplacer' in new_file_lower:
                            prev_line = ''
                            for line in f:
                                if 'pluginname' in prev_line.lower() and basename in prev_line.lower():
                                    if 'formid' in line.lower():
                                        for form_ids in form_id_map:
                                            line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                prev_line = line
                                print(line.strip('\n'))
                        elif 'mcm\\config' in new_file_lower: #MCM helper
                            for line in f:
                                if 'sourecform' in line.lower() and basename in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                print(line.strip('\n'))
                        fileinput.close()
                elif '_conditions.txt' in new_file_lower: #Dynamic Animation Replacer Patching
                    CFIDs.dar_patcher(basename, new_file, form_id_map)
                elif '_srd.' in new_file_lower: #Sound record distributor patching
                    CFIDs.srd_patcher(basename, new_file, form_id_map)
                elif '.psc' in new_file_lower: #Script source file patching, this doesn't take into account form ids being passed as variables
                    with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
                        for line in f:
                            if basename in line.lower() and 'getformfromfile' in line.lower():
                                for form_ids in form_id_map:
                                    line = re.sub(r'(0x0{0,7})(' + re.escape(form_ids[0]) + r' *,)', r'\0' + form_ids[2] + ',', line, re.IGNORECASE)
                            print(line.strip('\n'))
                        fileinput.close()
                elif basename.startswith('shse.') and '.json' in new_file_lower: # Smart Harvest SE
                    CFIDs.json_shse_patcher(basename, new_file, form_id_map)
                elif 'dynamicstringdistributor' in new_file_lower and '.json' in new_file_lower: # Dynamic String Distributor
                    CFIDs.json_dsd_patcher(basename, new_file, form_id_map)
                elif 'dkaf' in new_file_lower and '.json' in new_file_lower: # Dynamic Key Activation Framework NG
                    CFIDs.json_dkaf_patcher(basename, new_file, form_id_map)
                elif 'dynamicarmorvariants' in new_file_lower and '.json' in new_file_lower: # Dynamic Armor Variants
                    CFIDs.json_dav_patcher(basename, new_file, form_id_map)
                elif 'creatures.d' in new_file_lower and '.json' in new_file_lower: # Creature Framework
                    CFIDs.json_cf_patcher(basename, new_file, form_id_map)
                elif '.json' in new_file_lower: #Whatever else may be using .json?
                    with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
                        for line in f:
                            if basename in line.lower():
                                for form_ids in form_id_map:
                                    line = line.replace(form_ids[0], form_ids[2]).replace(form_ids[1], form_ids[3]).replace(form_ids[0].lower(), form_ids[2].lower()).replace(form_ids[1].lower(), form_ids[3].lower())
                            print(line.strip('\n'))
                        fileinput.close()
                elif '.jslot' in new_file_lower:
                    CFIDs.jslot_patcher(basename, new_file, form_id_map)
                elif 'facegeom' in new_file_lower and '.nif' in new_file_lower: # FaceGeom mesh patching
                    CFIDs.facegeom_mesh_patcher(basename, new_file, form_id_map)
                elif '.seq' in new_file_lower: #SEQ file patching
                    CFIDs.seq_patcher(new_file, form_id_map)
                elif '.pex' in new_file_lower: #Compiled script patching
                    CFIDs.pex_patcher(basename, new_file, form_id_map)
            parts = os.path.relpath(file, skyrim_folder_path).lower().split('\\')
            rel_path = os.path.join(*parts[1:])
            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(master)].append(rel_path)

    def find_next_non_alphanumeric(text, start_index):
        for i in range(start_index, len(text)):
            if not text[i].isalnum():
                return i
        return -1
    
    def facegeom_mesh_patcher(basename, new_file, form_id_map):
        with open(new_file, 'rb+') as f:
            data = f.readlines()
            bytes_basename = bytes(basename, 'utf-8')
            for i in range(len(data)):
                if bytes_basename in data[i].lower(): #check for plugin name, in file path, in line of nif file.
                    for form_ids in form_id_map:
                        data[i] = data[i].replace(form_ids[1].encode(), form_ids[3].encode()).replace(form_ids[1].encode().lower(), form_ids[3].encode().lower())
            f.seek(0)
            f.writelines(data)
    
    def seq_patcher(new_file, form_id_map):
        with open(new_file, 'rb+') as f:
            data = f.read()
            seq_form_id_list = [data[i:i+4] for i in range(0, len(data), 4)]
            for form_ids in form_id_map:
                for i in range(len(seq_form_id_list)):
                    if form_ids[4] == seq_form_id_list[i]:
                        seq_form_id_list[i] = b'-||+||-' + form_ids[5]+ b'-||+||-'
            data = b''.join(seq_form_id_list)
            data = data.replace(b'-||+||-', b'')
            f.seek(0)
            f.write(data)
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
            master_name_bytes = basename.encode()
            index = strings.index(master_name_bytes, 24, offset)
            data_size = len(data)
            while offset < data_size:
                if data[offset:offset+1] == b'\x03' and data[offset+5:offset+6] == b'\x02' and int.from_bytes(data[offset+6:offset+8]) == index:
                    integer_variable = data[offset+2:offset+5]
                    for form_ids in form_id_map:
                        if integer_variable == form_ids[4][::-1][1:]:
                            data[offset+2:offset+5] = form_ids[4][::-1][1:]
                            offset += 6
                            break
                    offset += 1
                offset += 1
            data = bytes(data)
            f.seek(0)
            f.write(data)
            f.close()
        
    def dar_patcher(basename, new_file, form_id_map):
        with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
            for line in f:
                if basename in line.lower() and '|' in line:
                    index = line.index('|')
                    end_index = CFIDs.find_next_non_alphanumeric(line, index+2)
                    if end_index != -1:
                        form_id_int = int(line[index+1:end_index], 16)
                        for form_ids in form_id_map:
                            old_id_int = int(form_ids[0], 16)
                            if form_id_int == old_id_int:
                                line = line[:index+1] + '0x00' + form_ids[3] + line[end_index:]
                print(line.strip('\n'))
            fileinput.close()

    def srd_patcher(basename, new_file, form_id_map):
        with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
            for line in f:
                if basename in line.lower() and '|' in line:
                    index = line.index('|')
                    form_id_int = int(line[index+1:], 16)
                    for form_ids in form_id_map:
                        old_id_int = int(form_ids[0], 16)
                        if form_id_int == old_id_int:
                            line = line[:index+1] + form_ids[3]
                print(line.strip('\n'))
            fileinput.close()

    def jslot_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+') as f:
            data = json.load(f)
            if 'actor' in data.keys() and 'headTexture' in data['actor'].keys():
                plugin_and_fid = data['actor']['headTexture']
                if plugin_and_fid[:-7].lower() == basename:
                    old_id = plugin_and_fid[-6:]
                    for form_ids in form_id_map:
                        if old_id == form_ids[1]:
                            data['actor']['headTexture'] = plugin_and_fid[:-6] + form_ids[3]
                            break

            if 'headParts' in data.keys():
                for i, part in enumerate(data['headParts']):
                    formIdentifier = part['formIdentifier']
                    if formIdentifier[:-7].lower() == basename:
                        formId = part['formId'].to_bytes(4)
                        old_id = formIdentifier[-6:]
                        for form_ids in form_id_map:
                            if old_id == form_ids[1]:
                                new_form_id = formId[:1] + bytes.fromhex(form_ids[3])
                                data['headParts'][i]['formId'] = int.from_bytes(new_form_id)
                                data['headParts'][i]['formIdentifier'] = formIdentifier[:-6] + form_ids[3]
                                break
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3, separators=(',', ' : '))
            f.close()

    def json_shse_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+') as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = CFIDs.remove_trailing_commas_from_json(string)
            json_dict = CFIDs.extract_values_and_keys(data)
            plugin = False
            for path, value in json_dict:
                if path[-1] == 'plugin' and basename == value.lower():
                    plugin = True
                elif plugin == True and path[-2] == 'form':
                    for form_ids in form_id_map:
                        if value ==  '00' + form_ids[1]:
                            data = CFIDs.change_json_element(data, path, '00' + form_ids[3])
                            break
                else:
                    plugin = False
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dsd_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+', errors='ignore') as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = CFIDs.remove_trailing_commas_from_json(string)
            json_dict = CFIDs.extract_values_and_keys(data)
            for path, value in json_dict:
                if path[-1] == 'form_id':
                    form_id_start = value[2:]
                    form_id = value[2:8]
                    plugin = value[9:]
                    if plugin.lower() == basename:
                        for form_ids in form_id_map:
                            if form_id == form_ids[1]:
                                data = CFIDs.change_json_element(data, path, form_id_start + form_ids[3] + '|' + plugin)
                                break
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dkaf_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+', errors='ignore') as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = CFIDs.remove_trailing_commas_from_json(string)
            json_dict = CFIDs.extract_values_and_keys(data)
            for path, value in json_dict:
                if type(value) is str and '|' in value:
                    index = value.find('|')
                    plugin = value[:index]
                    form_id_int = int(value[index+1:], 16)
                    if plugin.lower() == basename:
                        for form_ids in form_id_map:
                            old_id_int = int(form_ids[0], 16)
                            if form_id_int == old_id_int:
                                data = CFIDs.change_json_element(data, path, plugin + '|0x' + form_ids[2])
                                break
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_dav_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+') as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = CFIDs.remove_trailing_commas_from_json(string)
            json_dict = CFIDs.extract_values_and_keys(data)
            for path, value in json_dict:
                if len(path) > 2 and type(path[-2]) is str and 'replace' in path[-2]:
                    if path[-2] == 'replaceByForm':
                        index = path[-1].index('|')
                        plugin = path[-1][:index]
                        form_id_int = int(path[-1][index+1:], 16)
                        if plugin.lower() == basename:
                            for form_ids in form_id_map:
                                old_int = int(form_ids[0], 16)
                                if form_id_int == old_int:
                                    data = CFIDs.change_json_key(data, path[-1], plugin + '|' + form_ids[2])
                                    break
                    index = value.index('|')
                    plugin = value[:index]
                    form_id_int = int(value[index+1:], 16)
                    if plugin.lower() == basename:
                        for form_ids in form_id_map:
                            old_int = int(form_ids[0], 16)
                            if form_id_int == old_int:
                                data = CFIDs.change_json_element(data, path, plugin + '|' + form_ids[2])
                                break
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def json_cf_patcher(basename, new_file, form_id_map):
        with open(new_file, 'r+') as f:
            try:
                data = json.load(f)
            except:
                f.seek(0)
                string = f.read()
                data = CFIDs.remove_trailing_commas_from_json(string)
            json_dict = CFIDs.extract_values_and_keys(data)
            for path, value in json_dict:
                if type(value) is str and '__formdata' in value.lower():
                    formData_index = value.index('|')
                    index = value.index('|', formData_index+1)
                    plugin = value[formData_index+1:index]
                    if plugin.lower() == basename:
                        form_id_int = int(value[index+1:],16)
                        for form_ids in form_id_map:
                            old_id_int = int(form_ids[0],16)
                            if form_id_int == old_id_int:
                                data = CFIDs.change_json_element(data, path, value[:index+1] + '0x' + form_ids[2])
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            f.close()

    def remove_trailing_commas_from_json(json_string):
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            json_string = re.sub(r',\s*([\]}])', r'\1', json_string)
            return json.loads(json_string)

    def extract_values_and_keys(json_data, path=[]):
        results = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if path:
                    new_path = path.copy()
                    new_path.append(key)
                else:
                    new_path = [key]
                results.extend(CFIDs.extract_values_and_keys(value, new_path))
        elif isinstance(json_data, list):
            for index, item in enumerate(json_data):
                if path:
                    new_path = path.copy()
                    new_path.append(index)
                else:
                    new_path = [index]
                results.extend(CFIDs.extract_values_and_keys(item, new_path))
        else:
            results.append((path, json_data))

        return results

    def change_json_element(data, path, new_value):
        if not path:
            return new_value
        
        key = path[0]
        if isinstance(data, dict):
            data[key] = CFIDs.change_json_element(data[key], path[1:], new_value)
        elif isinstance(data, list):
            index = int(key)
            data[index] = CFIDs.change_json_element(data[index], path[1:], new_value)
        return data

    def change_json_key(data, old_key, new_key):
        if isinstance(data, dict):
            if old_key in data:
                data[new_key] = data.pop(old_key)
            for key, value in data.items():
                CFIDs.change_json_key(value, old_key, new_key)
        elif isinstance(data, list):
            for item in data:
                CFIDs.change_json_key(item, old_key, new_key)
        return data
    
    def decompress_data(data_list, master_count):
        sizes_list = [[] for _ in range(len(data_list))]

        for i in range(len(data_list)):
            if data_list[i][:4] != b'GRUP' and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                try:
                    decompressed = zlib.decompress(data_list[i][28:])  # Decompress the form
                except Exception as e:
                    print(f'Error: {e}\r at Header: {data_list[i][:24]} at Index: {i}' )

                uncompressed_size_from_form = data_list[i][24:28]
                sizes_list[i] = [len(data_list[i]), 0, i, len(data_list[i][28:]), uncompressed_size_from_form]
                data_list[i] = data_list[i][:24] + decompressed

        return data_list, sizes_list
    
    def recompress_data(data_list, sizes_list, master_count):
        for i in range(len(data_list)):
            if data_list[i][:4] != b'GRUP' and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                compressed = zlib.compress(data_list[i][24:], 6)
                formatted = [0] * (sizes_list[i][0]- 28)
                formatted[:24] = data_list[i][:24]
                formatted[24:28] = sizes_list[i][4]
                formatted[28:len(compressed)] = compressed
                if len(formatted) != sizes_list[i][0]:
                    diff = len(formatted) - sizes_list[i][0]
                    sizes_list[i][1] = diff
                    size = int.from_bytes(data_list[i][4:8][::-1])
                    new_size = size + diff
                    formatted[4:8] = [byte for byte in new_size.to_bytes(4, 'little')]
                data_list[i] = bytes(formatted)
        return data_list, sizes_list
    
    def update_grup_sizes(data_list, grup_struct, sizes_list):
        byte_array_data_list = [bytearray(form) for form in data_list]
        for i, size_info in enumerate(sizes_list):
            if size_info and size_info[1] != 0:
                for index in grup_struct[i]:
                    current_size = int.from_bytes(byte_array_data_list[index][4:8][::-1])
                    new_size = current_size + size_info[1]
                    byte_array_data_list[index][4:8] = new_size.to_bytes(4, 'little')
        data_list = [bytes(form) for form in byte_array_data_list]
        return data_list
    
    def create_data_list(data):
        data_list = []
        data_list_offsets = []
        offset = 0
        index = 0
        grup_list = []
        while offset < len(data):
            data_list_offsets.append(offset)
            if data[offset:offset+4] == b'GRUP':
                grup_length = int.from_bytes(data[offset+4:offset+8][::-1])
                grup_list.append([index, offset, offset + grup_length])
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = int.from_bytes(data[offset+4:offset+8][::-1])
                data_list.append(data[offset:offset+24+form_length])
                offset += 24 + form_length
            index += 1
        
        struct = {}

        for i, data_offset in enumerate(data_list_offsets):
            is_inside_of = []
            for index, start, end in grup_list:
                if start <= data_offset < end and index != i:
                    is_inside_of.append(index)
            struct[i] = is_inside_of    

        return data_list, struct
    
    #Compacts master file and returns the new mod folder
    def compact_file(file, skyrim_folder_path, output_folder, update_header):
        form_id_file_name = 'ESLifier_Data/Form_ID_Maps/' + os.path.basename(file).lower() + "_FormIdMap.txt"
        if not os.path.exists(os.path.dirname(form_id_file_name)):
            os.makedirs(os.path.dirname(form_id_file_name))
        new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder)

        #Set ESL flag, update to header 1.71 for new Form IDs, and get data from mod plugin
        data = b''
        with open(new_file, 'rb+') as f:
            f.seek(9)
            f.write(b'\x02')
            if update_header:
                f.seek(0)
                f.seek(30)
                f.write(b'\x48\xE1\xDA\x3F')
            f.seek(0)
            data = f.read()
            f.close()

        data_list, grup_struct = CFIDs.create_data_list(data)

        master_count = data_list[0].count(b'MAST')

        if master_count <= 15:
            mC = '0' + str(master_count)
        else:
            mC = str(master_count)

        data_list, sizes_list = CFIDs.decompress_data(data_list, master_count)

        form_id_list = []
        #Get all form ids in plugin
        for form in data_list:
            if len(form) > 24 and form[15] == master_count and form[12:16] not in form_id_list:
                form_id_list.append([form[12:16], form[:4]])

        master_byte = master_count.to_bytes()

        saved_forms = CFIDs.form_processor.save_all_form_data(data_list, master_byte, new_file)

        form_id_list.sort()

        if update_header:
            new_id = binascii.unhexlify(mC + '000000')
            new_range = 4096
        else:
            new_id = binascii.unhexlify(mC + '000800')
            new_range = 2048
        new_id_len = len(new_id)
        counter = int.from_bytes(new_id, 'big')

        new_form_ids = []
        for i in range(new_range):
            new_id = counter.to_bytes(new_id_len, 'little')
            new_decimal = int.from_bytes(new_id[:3][::-1])
            new_form_ids.append([new_decimal, new_id])
            counter += 1

        to_remove = []
        for old_id, type in form_id_list:
            for new_decimal, new_id in new_form_ids:
                if old_id == new_id:
                    to_remove.append([old_id, type, new_decimal, new_id])
                    break

        for old_id, type, new_decimal, new_id in to_remove:
            form_id_list.remove([old_id, type])
            new_form_ids.remove([new_decimal, new_id])

        matched_ids = []

        form_id_replacements = []
        #Make sure that if a cell form id follows the sub-block convention it keeps it
        for form_id, type in form_id_list:
            if type == b'CELL':
                decimal_form_id = int.from_bytes(form_id[:3][::-1])
                last_two_digits = decimal_form_id % 100
                for new_decimal, new_id in new_form_ids:
                    new_last_two_digits = new_decimal % 100
                    if new_last_two_digits == last_two_digits:
                        form_id_replacements.append([form_id, new_id])
                        new_form_ids.remove([new_decimal, new_id])
                        matched_ids.append(form_id)
                        break

        for form_id, _ in form_id_list:
            if form_id not in matched_ids:
                _, new_id = new_form_ids.pop(0)
                form_id_replacements.append([form_id, new_id])

        form_id_replacements.sort()

        with open(form_id_file_name, 'w') as fidf:
            for form_id, new_id in form_id_replacements:
                fidf.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')

        data_list = CFIDs.form_processor.patch_form_data(data_list, saved_forms, form_id_replacements, master_byte)

        data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list, master_count)

        data_list = CFIDs.update_grup_sizes(data_list, grup_struct, sizes_list)

        #data = b''.join(data_list)

        with open(new_file, 'wb') as f:
            f.write(b''.join(data_list))
            f.close()

        CFIDs.compacted_and_patched[os.path.basename(new_file)] = []
        
    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def patch_dependent_plugins(file, dependents, skyrim_folder_path, output_folder_path, update_header):
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        
        with open(form_id_file_name, 'r') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        threads = []

        for dependent in dependents:
            new_file = CFIDs.copy_file_to_output(dependent, skyrim_folder_path, output_folder_path)
            #dependent_data = b''
            size = os.path.getsize(new_file)
            mb_size = round(size / 1048576, 3)
            print(f'-    {os.path.basename(new_file)} ({mb_size} MB)')
            if mb_size > 40:
                thread = threading.Thread(target=CFIDs.patch_dependent, args=(new_file, update_header,file, dependent, form_id_file_data, skyrim_folder_path))
                threads.append(thread)
                thread.start()
            else:
                CFIDs.patch_dependent(new_file, update_header,file, dependent, form_id_file_data, skyrim_folder_path)
        
        if len(threads) > 0 and any([thread.is_alive() for thread in threads]):
            print('-    Waiting for dependent plugin patching to finish...')
            for thread in threads:
                thread.join()

    def patch_dependent(new_file, update_header,file, dependent, form_id_file_data, skyrim_folder_path):
        with open(new_file, 'rb+') as dependent_file:
            #Update header to 1.71 to fit new records
            if update_header:
                dependent_file.seek(0)
                dependent_file.seek(30)
                dependent_file.write(b'\x48\xE1\xDA\x3F')
                dependent_file.seek(0)

            dependent_data = dependent_file.read()
            
            data_list, grup_struct = CFIDs.create_data_list(dependent_data)
        
            master_count = data_list[0].count(b'MAST')
            data_list, sizes_list = CFIDs.decompress_data(data_list, master_count)

            master_index = CFIDs.get_master_index(file, data_list)

            master_byte = master_index.to_bytes()

            saved_forms = CFIDs.form_processor.save_all_form_data(data_list, master_byte, new_file)
            
            form_id_replacements = []
            for i in range(len(form_id_file_data)):
                form_id_conversion = form_id_file_data[i].split('|')
                from_id = bytes.fromhex(form_id_conversion[0])[:3] + master_byte
                to_id = bytes.fromhex(form_id_conversion[1])[:3] + master_byte
                form_id_replacements.append([from_id, to_id])

            data_list = CFIDs.form_processor.patch_form_data(data_list, saved_forms, form_id_replacements, master_byte)

            data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list, master_count)
            
            data_list = CFIDs.update_grup_sizes(data_list, grup_struct, sizes_list)

            dependent_file.seek(0)
            dependent_file.write(b''.join(data_list))
            dependent_file.close()
        parts = os.path.relpath(dependent, skyrim_folder_path).lower().split('\\')
        rel_path = os.path.join(*parts[1:])
        with CFIDs.lock:
            CFIDs.compacted_and_patched[os.path.basename(file)].append(rel_path)
            #CFIDs.compacted_and_patched[os.path.basename(file)].append(dependent)
            #CFIDs.compacted_and_patched[os.path.basename(file)].append(new_file)
        return

    #gets what master index the file is in inside of the dependent's data
    def get_master_index(file, data_list):
        master_pattern = re.compile(b'MAST..(.*?).DATA', flags=re.DOTALL)
        matches = re.findall(master_pattern, data_list[0])
        master_index = 0
        for match in matches:
            if os.path.basename(file).lower() in str(match).lower():
                return master_index
            else:
                master_index += 1