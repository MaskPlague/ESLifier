import os
import re
import binascii
import shutil
import fileinput
import zlib
import json
import threading

class CFIDs():
    #TODO: Consider adding an new warning to ESLifierWarn that detects if a master has no _ESLifierBackup/_FormIdMap.txt but its dependents do then they may be the wrong version.
    def compact_and_patch(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header):
        CFIDs.lock = threading.Lock()
        CFIDs.compacted_and_patched = {}
        print("Compacting Plugin: " + os.path.basename(file_to_compact) + '...')
        CFIDs.compact_file(file_to_compact, skyrim_folder_path, output_folder_path, update_header)
        if dependents != []:
            print("-  Patching Dependent Plugins...")
            CFIDs.patch_dependent_plugins(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header)
        
        files_to_patch = CFIDs.get_from_file('ESLifier_Data/file_masters.json')
        if os.path.basename(file_to_compact).lower() in files_to_patch.keys():
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(file_to_compact, files_to_patch[os.path.basename(file_to_compact).lower()]) #function to get files that need to be edited in some way to function correctly.
            form_id_map = CFIDs.get_form_id_map(file_to_compact)
            print("-  Patching Dependent Files...")
            CFIDs.patch_files_threader(file_to_compact, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
            print("-  Renaming Dependent Files...")
            CFIDs.rename_files_threader(file_to_compact, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')
        return
        #TODO: update next object in TES4 header?
        #TODO: SkyPatcher, MCM Helper, possible others to check
        #TODO: add regex to certain replacements in patch files for safety
    
    def dump_to_file(file):
        try:
            data = CFIDs.get_from_file(file)
        except:
            data = {}
        for key, value in CFIDs.compacted_and_patched.items():
            if key not in data.keys():
                data[key] = []
            for item in value:
                if item not in data[key]:
                    data[key].append(item)

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

    def patch_new(compacted_file, dependents, files_to_patch, skyrim_folder_path, output_folder_path, update_header):
        CFIDs.lock = threading.Lock()
        CFIDs.compacted_and_patched = {}
        print('Patching new plugins and files for ' + compacted_file + '...')
        CFIDs.compacted_and_patched[compacted_file] = []
        if dependents != []:
            print("-  Patching New Dependent Plugins...")
            CFIDs.patch_dependent_plugins(compacted_file, dependents, skyrim_folder_path, output_folder_path, update_header)
        if os.path.basename(compacted_file) in files_to_patch.keys():
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(compacted_file, files_to_patch[os.path.basename(compacted_file)])
            form_id_map = CFIDs.get_form_id_map(compacted_file)
            print("-  Patching New Dependent Files...")
            CFIDs.patch_files_threader(compacted_file, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
            print("-  Renaming Dependent Files...")
            CFIDs.rename_files_threader(compacted_file, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')

    #Create a copy of the mod plugin we're compacting
    def copy_file_to_output(file, skyrim_folder_path, output_folder):
        end_path = file[len(skyrim_folder_path) + 1:]
        new_file = os.path.join(os.path.join(output_folder,'ESLifier Compactor Output'), re.sub(r'(.*?)(/|\\)', '', end_path, 1))
        if not os.path.exists(os.path.dirname(new_file)):
            os.makedirs(os.path.dirname(new_file))
        if not os.path.exists(new_file):
            shutil.copy(file, new_file)
        return new_file

    #Yield every file in every directory and subdirectory in every mod folder
    def getAllFiles(modFolders):
        for directory in modFolders:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    yield os.path.join(root,file)
    
    #Get files (not including plugins) that may/will need old Form IDs replaced with the new Form IDs
    def sort_files_to_patch_or_rename(master, files):
        #hexaPattern = re.compile(r'([0-9a-fA-F]+){6,}[.](?!p)')
        files_to_patch = []
        files_to_rename = []
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '_srd.', os.path.splitext(os.path.basename(master))[0].lower() + '.seq']
        for file in files:
            if any(match in file.lower() for match in matchers):
                files_to_patch.append(file)
            elif os.path.basename(master).lower() in file.lower() and ('facegeom' in file.lower() or 'voice' in file.lower() or 'facetint' in file.lower()):
                files_to_rename.append(file)
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
        for file in files:
            CFIDs.count += 1
            percent = CFIDs.count / CFIDs.file_count * 100
            factor = round(CFIDs.file_count * 0.001)
            if factor == 0:
                factor = 1
            if (CFIDs.count % factor) >= (factor-1) or CFIDs.count >= CFIDs.file_count:
                print('\033[F\033[K-  Percentage: ' + str(round(percent,1)) +'%\n-  Files: ' + str(CFIDs.count) + '/' + str(CFIDs.file_count), end='\r')
            for form_ids in form_id_map:
                if form_ids[1].upper() in file.upper():
                    with CFIDs.lock:
                        new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
                        os.replace(new_file, new_file.replace(form_ids[1].upper(), form_ids[3].upper()))
                        end_path = file[len(skyrim_folder_path) + 1:]
                        new_file_but_skyrim_pathed = os.path.join(skyrim_folder_path, re.sub(r'(.*?)(/|\\)', '', end_path, 1))
                        CFIDs.compacted_and_patched[os.path.basename(master)].append(new_file_but_skyrim_pathed)
                        if 'facegeom' in new_file.lower() and os.path.basename(master).lower() in new_file.lower():
                            facegeom_meshes.append(new_file.replace(form_ids[1].upper(), form_ids[3].upper()))
                    break
            CFIDs.compacted_and_patched[os.path.basename(master)].append(file)
        if facegeom_meshes != []:
            print('-  Patching Renamed Files...')
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
        
        for chunk in chunks:
            thread = threading.Thread(target=CFIDs.patch_files, args=(master, chunk, form_id_map, skyrim_folder_path, output_folder_path, flag))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()

    #Patches each file type in a different way as each has Form IDs present in a different format
    def patch_files(master, files, form_id_map, skyrim_folder_path, output_folder_path, flag):
        for file in files:
            if flag:
                new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
            else:
                new_file = file
            if '.ini' in new_file.lower() or '.json' in new_file.lower() or '_conditions.txt' in new_file.lower() or '_srd.' in new_file.lower() or '.psc' in new_file.lower():
                with CFIDs.lock:
                    with fileinput.input(new_file, inplace=True, encoding="utf-8") as f:
                        if '.ini' in new_file.lower(): #All of PO3's various distributors patching and whatever else uses ini files with form ids.
                            #TODO: probably need to add more conditions to this and search for | or ~ before/after plugin name, consider SkyPatcher Format
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for form_ids in form_id_map:
                                        #this is faster than re.sub by a lot ;_;
                                        line = line.replace('0x' + form_ids[0], '0x' + form_ids[2]).replace('0x' + form_ids[1], '0x' + form_ids[3]).replace('0x' + form_ids[0].lower(), '0x' + form_ids[2].lower()).replace('0x' + form_ids[1].lower(), '0x' + form_ids[3].lower()).replace('0X' + form_ids[0], '0X' + form_ids[2]).replace('0X' + form_ids[1], '0X' + form_ids[3]).replace('0X' + form_ids[0].lower(), '0X' + form_ids[2].lower()).replace('0X' + form_ids[1].lower(), '0X' + form_ids[3].lower())
                                print(line.strip('\n'))
                        elif 'config.json' in new_file.lower(): #Open Animation Replacer Patching and MCM helper
                            #TODO: Redo this to look for plugin name on preceeding line (use for i in range()) for OAR
                            # Also add MCM helper structure, use regex so that if a mod somehow has form id "F" or "D" that
                            # gets compacted to something else, it won't break the json formatting i.e. "formid" -> "3ormi2" or "form:" -> "3orm"
                            for line in f:
                                if 'formid' in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                print(line.strip('\n'))
                        elif '_conditions.txt' in new_file.lower(): #Dynamic Animation Replacer Patching
                            for line in f:
                                for form_ids in form_id_map:
                                    line = line.replace('0x00' + form_ids[1], '0x00[][][][]' + form_ids[3]).replace('0x' + form_ids[1], '0x[][][][]' + form_ids[3]).replace('0x00' + form_ids[1].lower(), '0x00[][][][]' + form_ids[3].lower()).replace('0x' + form_ids[1].lower(), '0x[][][][]' + form_ids[3].lower()).replace('0X00' + form_ids[1], '0X00[][][][]' + form_ids[3]).replace('0X' + form_ids[1], '0X[][][][]' + form_ids[3]).replace('0X00' + form_ids[1].lower(), '0X00[][][][]' + form_ids[3].lower()).replace('0X' + form_ids[1].lower(), '0X[][][][]' + form_ids[3].lower())
                                line = line.replace('[][][][]', '') #this is to prevent the event where a form id is in old ids and new ids.
                                print(line.strip('\n'))
                        elif '_srd.' in new_file.lower(): #Sound record distributor patching
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace('|' + form_ids[1], '|[][][][]' + form_ids[3]).replace('|' + form_ids[0], '|[][][][]' + form_ids[2]).replace('|' + form_ids[1].lower(), '|[][][][]' + form_ids[3].lower()).replace('|' + form_ids[0].lower(), '|[][][][]' + form_ids[2].lower())
                                    line = line.replace('[][][][]', '') #this is to prevent the event where a form id is in old ids and new ids.
                                print(line.strip('\n'))
                        elif '.psc' in new_file.lower(): #Script source file patching
                            for line in f:
                                if os.path.basename(master).lower() in line.lower() and 'getformfromfile' in line.lower():
                                    for form_ids in form_id_map:
                                        line = re.sub(r'(0x0{0,7})(' + re.escape(form_ids[0]) + r' *,)', r'\1' + '[][][][]' + form_ids[2] + ',', line, re.IGNORECASE)
                                    line = line.replace('[][][][]', '') #this is to prevent the event where a form id is in old ids and new ids.
                                print(line.strip('\n'))
                        elif '.json' in new_file.lower(): #Dynamic Key Activation Framework NG, Smart Harvest Auto NG AutoLoot and whatever else may be using .json?
                            #TODO: check for other json mods
                            prev_line = ''
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace(form_ids[0], form_ids[2]).replace(form_ids[1], form_ids[3]).replace(form_ids[0].lower(), form_ids[2].lower()).replace(form_ids[1].lower(), form_ids[3].lower())
                                elif 'plugin' in prev_line.lower() and os.path.basename(master).lower() in prev_line.lower(): #Smart Harvest
                                    if 'form' in line.lower():
                                        for form_ids in form_id_map:
                                            line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                prev_line = line
                                print(line.strip('\n'))
                        fileinput.close()
            
            elif 'facegeom' in new_file.lower():
                if '.nif' in new_file.lower(): #FaceGeom mesh patching
                    #TODO: check byte structure via hex editor to see what may go wrong here
                    with CFIDs.lock:
                        with open(new_file, 'rb+') as f:
                            data = f.readlines()
                            for i in range(len(data)):
                                if bytes(os.path.basename(master).upper(), 'utf-8') in data[i].upper(): #check for plugin name, in file path, in line of nif file.
                                    for form_ids in form_id_map:
                                        data[i] = data[i].replace(form_ids[1].encode(), form_ids[3].encode()).replace(form_ids[1].encode().lower(), form_ids[3].encode().lower())
                            f.seek(0)
                            f.writelines(data)

            elif '.seq' in new_file.lower() or '.pex' in new_file.lower():
                with CFIDs.lock:
                    with open(new_file,'rb+') as f:
                        data = f.read()
                        if '.seq' in new_file.lower(): #SEQ file patching
                            seq_form_id_list = [data[i:i+4] for i in range(0, len(data), 4)]
                            for form_ids in form_id_map:
                                for i in range(len(seq_form_id_list)):
                                    if form_ids[4] == seq_form_id_list[i]:
                                        seq_form_id_list[i] = b'-||+||-' + form_ids[5]+ b'-||+||-'
                            data = b''.join(seq_form_id_list)
                            data = data.replace(b'-||+||-', b'')
                            f.seek(0)
                            f.write(data)
                        elif '.pex' in new_file.lower(): #Compiled script patching
                            #TODO: Perhaps implement a method to get a list of form id's that need to be replaced if a .psc exists as that would
                            #lessen the chance that an incorrect integer is replaced as perhaps a random int that matches a form id is in the file
                            #or another mod is present in the file with a similar form id that would also be replaced. 
                            for form_ids in form_id_map:
                                #\x03 indicates a integer in compiled .pex files. \x00 will always be present instead of the master byte
                                data = data.replace(b'\x03\x00' + form_ids[4][::-1][1:], b'\x03\x00-||+||-' + form_ids[5][::-1][1:])
                                #data = re.sub(rb'(?<=\x03\x00)' + form_ids[4][::-1][1:], form_ids[5][::-1][1:], data)
                            data = data.replace(b'-||+||-', b'')
                            f.seek(0)
                            f.write(data)
                        f.close()
            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(master)].append(file)

    def decompress_data(data_list, master_count):
        sizes_list = [[] for _ in range(len(data_list))]

        for i in range(len(data_list)):
            if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                size = int.from_bytes(data_list[i][4:8][::-1])
                decompressed = zlib.decompress(data_list[i][28:size + 24])  # Decompress the form
                sizes_list[i] = [len(data_list[i]), 0, i, len(data_list[i])]
                data_list[i] = data_list[i][:28] + decompressed + data_list[i][size+24:]

        return data_list, sizes_list
    
    def recompress_data(data_list, sizes_list, master_count):
        for i in range(len(data_list)):
            if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                compressed = zlib.compress(data_list[i][28:], 9)
                formatted = [0] * (sizes_list[i][0] - 28)
                formatted[:28] = data_list[i][:28]
                formatted[28:len(compressed)] = compressed
                data_list[i] = bytes(formatted)
                if sizes_list[i][3] < len(data_list[i]):
                    diff = len(data_list[i]) - sizes_list[i][3]
                    sizes_list[i] = [sizes_list[i][0], diff, sizes_list[i][2], sizes_list[i][3]]
                    size = int.from_bytes(data_list[i][4:8][::-1])
                    new_size = size + diff
                    hex_new_size = new_size.to_bytes(4, 'little')
                    data_list[i] = data_list[i][:4] + hex_new_size + data_list[i][8:]
        return data_list, sizes_list
    
    def parse_grups(data):
        top_level_grups = []
        current_grup = None
        i = 0

        # Skip the TES4 header (assume it's always the first 24 bytes)
        if data[:4] == b'TES4':
            tes4_size = int.from_bytes(data[4:8], 'little') + 24
            i += tes4_size

        while i < len(data):
            # Check if this is a GRUP
            if data[i:i+4] == b'GRUP':
                grup_size = int.from_bytes(data[i+4:i+8], 'little')  # Size includes the 24-byte header
                grup_type = data[i+8:i+12]
                grup_offset = i
                grup_data = data[i:i+grup_size]

                # Create a dictionary for this GRUP
                grup = {
                    'offset': grup_offset,
                    'size': grup_size,
                    'type': grup_type,
                    'data': grup_data,
                    'children': [],  # Will hold child GRUPs or forms
                }

                # Determine if this is a top-level GRUP
                if re.match(rb'[A-Z]{3}[A-Z_]', grup_type):
                    # It's a top-level GRUP; add it to the top-level list
                    top_level_grups.append(grup)
                    current_grup = grup  # Track the current top-level GRUP
                else:
                    # It's a child GRUP; add it to the current top-level GRUP or parent GRUP
                    if current_grup and 'children' in current_grup:
                        current_grup['children'].append(grup)

                # Move to the next GRUP/form
                i += 24#grup_size
            else:
                # If it's not a GRUP, it must be a form; add it to the current GRUP's children
                form_size = int.from_bytes(data[i+4:i+8], 'little')
                form_data = data[i:i+form_size + 24]  # Add the 24-byte header size

                form = {
                    'offset': i,
                    'size': form_size,
                    'data': form_data,
                }

                # Add the form to the current GRUP's children
                if current_grup and 'children' in current_grup:
                    current_grup['children'].append(form)

                # Move to the next form
                i += form_size + 24

        return top_level_grups
    
    def update_grup_sizes(grup, sizes_list, offsets):
        """
        Update the sizes of GRUPs based on decompressed forms and propagate size changes upwards.
        Only update GRUP sizes if compression/decompression occurred.
        """
        # Initialize the size with the original size
        original_size = grup['size']
        total_size = original_size# GRUP header size
        size_changed = False

        # Update children recursively
        if 'children' in grup.keys():
            for child in grup['children']:
                child_size = CFIDs.update_grup_sizes(child, sizes_list, offsets)
                size_changed = size_changed or (child_size != child['size'])

        # Include decompression size changes for forms in this GRUP
        for size_info in sizes_list:
            if size_info and size_info[1] != 0:
                form_index = size_info[2]
                form_offset = offsets[form_index] # Convert index to byte offset

                # Check if the form offset falls within this GRUP's bounds
                if grup['offset'] + 24 <= form_offset < grup['offset'] + grup['size']:
                    # Add the decompression size difference
                    total_size += size_info[1]
                    size_changed = True

        # Only update the GRUP size if a size change occurred
        if size_changed:
            grup['data'] = grup['data'][:4] + total_size.to_bytes(4, 'little') + grup['data'][8:]
            grup['size'] = total_size
            grup['modified'] = True
        else:
            total_size = original_size  # Retain the original size if nothing changed

        return total_size
    
    def reassemble_data(grup_hierarchy, data_list, offsets):
        """
        Reassemble the modified data from the updated GRUP hierarchy and the modified data_list.
        Replace chunks of data_list where any GRUP (including child GRUPs) has been updated.
        """
        # Convert offsets to a lookup for faster access
        offset_to_index = {offset: i for i, offset in enumerate(offsets)}

        # Recursively replace GRUP data
        def process_grup(grup, result_data):
            if grup.get('modified', False):
                # Replace this GRUP's data in the corresponding chunk
                index = offset_to_index[grup['offset']]
                original_chunk = data_list[index]
                updated_chunk = grup['data']
                
                # Add updated GRUP to result
                result_data[index] = updated_chunk[:8] + original_chunk[8:]  # Replace GRUP header, retain forms

            # Process children recursively
            if 'children' in grup:
                for child in grup['children']:
                    process_grup(child, result_data)

        # Initialize result as a copy of data_list
        result_data = list(data_list)

        # Process all GRUPs in the hierarchy
        for top_level_grup in grup_hierarchy:
            process_grup(top_level_grup, result_data)

        # Combine the updated chunks into a single byte sequence
        return b''.join(result_data)
    
    def save_nvpp_data(data):
        nvpp_offset = data.index(b'NVPP')
        end_of_nvpp_offset = data.index(b'GRUP', nvpp_offset)
        nvpp_form_ids = [data[i:i + 4] for i in range(nvpp_offset+10, end_of_nvpp_offset, 4)]
        nvpp_start = data[nvpp_offset:nvpp_offset+10]
        data = data.replace(data[nvpp_offset:end_of_nvpp_offset+1], b'=||+||~NVPP_PLACEHOLDER~||+||=')
        return data, nvpp_form_ids, nvpp_start
    
    def fix_nvpp_data(data, nvpp_form_ids, nvpp_start, form_id_replacements):
        for form_id, new_id in form_id_replacements:
            for i in range(len(nvpp_form_ids)):
                if nvpp_form_ids[i] == form_id:
                    nvpp_form_ids[i] = new_id
        new_nvpp = nvpp_start
        new_nvpp += b''.join(nvpp_form_ids)
        data = data.replace(b'=||+||~NVPP_PLACEHOLDER~||+||=', new_nvpp)
        return data

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

        data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z_]................[\x2C\x2B]\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]

        # Calculate the byte offsets of each chunk in data_list
        offsets = []
        current_offset = 0
        for chunk in data_list:
            offsets.append(current_offset)
            current_offset += len(chunk)

        master_count = data_list[0].count(b'MAST')

        if master_count <= 15:
            mC = '0' + str(master_count)
        else:
            mC = str(master_count)

        data_list, sizes_list = CFIDs.decompress_data(data_list, master_count)

        grup_hierarchy = CFIDs.parse_grups(data)

        data = b'-||+||-'.join(data_list)
        nvpp_present = False
        if b'NVPP' in data:
            nvpp_present = True
            data, nvpp_form_ids, nvpp_start = CFIDs.save_nvpp_data(data)

        form_id_list = []
        #Get all form ids in plugin
        for form in data_list:
            if len(form) > 24 and form[15] == master_count and form[12:16] not in form_id_list:
                form_id_list.append([form[12:16], form[:4]])

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

        form_id_replacements = []
        with open(form_id_file_name, 'w') as fidf:
            for form_id, type in form_id_list:
                if type == b'CELL':
                    decimal_form_id = int.from_bytes(form_id[:3][::-1])
                    last_two_digits = decimal_form_id % 100
                    for new_decimal, new_id in new_form_ids:
                        new_last_two_digits = new_decimal % 100
                        if new_last_two_digits == last_two_digits:
                            new_form_ids.remove([new_decimal, new_id])
                            form_id_list.remove([form_id, type])
                            form_id_replacements.append([form_id, new_id])
                            fidf.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')
                            if form_id[:2] == b'\x00\x00':
                                data = re.sub(b'(?<![\x2c\x2b].)' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:1] == b'\x00':
                                data = re.sub(b'(?<![\x2c\x2b]..)' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:2] == b'\xFF\xFF':
                                data = re.sub(re.escape(form_id) + b'(?!.' + int.to_bytes(master_count) + b')', b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:1] == b'\xFF':
                                data = re.sub(re.escape(form_id) + b'(?!..' + int.to_bytes(master_count) + b')', b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:1] == b'~':
                                data = re.sub(b'(?<!' + re.escape(b'=||+||') + b')' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:1] == b'=':
                                data = re.sub(b'(?<!' + re.escape(b'~||+||') + b')' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif form_id[:1] == B'\x20':
                                data = re.sub(b'(?<![A-Z]{3}[A-Z_]{1})' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            elif re.match(b'[A-Z_]', form_id[:1]):
                                data = re.sub(b'(?<![A-Z]{2})' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                            else:
                                #data = re.sub(re.escape(form_id) + b'(?!..' + re.escape(b'~||+||~') + b')', b'~||+||~' + new_id + b'~||+||~', data, flags=re.DOTALL)
                                data = re.sub(re.escape(form_id) + b'(?!..' + re.escape(b'=||+||~') + b')(?!' + re.escape(b'~||+||=') + b')', b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                                #data = data.replace(form_id,  b'~||+||~' + new_id + b'~||+||~')
                            break
                        
            for form_id, _ in form_id_list:
                _, new_id = new_form_ids.pop(0)
                fidf.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')
                form_id_replacements.append([form_id, new_id])
                if form_id[:2] == b'\x00\x00':
                    data = re.sub(b'(?<![\x2C\x2B].)' + re.escape(form_id) + b'(?!.{0,2}' + int.to_bytes(master_count) + b')', b'=||+||~' + new_id + b'~||+||=' , data, flags=re.DOTALL)
                elif form_id[:1] == b'\x00':
                    data = re.sub(b'(?<![\x2C\x2B]..)' + re.escape(form_id) + b'(?!.{0,2}' + int.to_bytes(master_count) + b')', b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif form_id[:2] == b'\xFF\xFF':
                    data = re.sub(re.escape(form_id) + b'(?!.' + int.to_bytes(master_count) + b')',  b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif form_id[:1] == b'\xFF':
                    data = re.sub(re.escape(form_id) + b'(?!..' + int.to_bytes(master_count) + b')',  b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif form_id[:1] == b'~':
                    data = re.sub(b'(?<!' + re.escape(b'=||+||') + b')' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif form_id[:1] == b'=':
                    data = re.sub(b'(?<!' + re.escape(b'~||+||') + b')' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif form_id[:1] == B'\x20':
                    data = re.sub(b'(?<![A-Z]{3}[A-Z_]{1})' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                elif re.match(b'[A-Z_]', form_id[:1]):
                    data = re.sub(b'(?<![A-Z]{2})' + re.escape(form_id), b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                else:
                    data = re.sub(re.escape(form_id) + b'(?!..' + re.escape(b'=||+||~') + b')(?!' + re.escape(b'~||+||=') + b')', b'=||+||~' + new_id + b'~||+||=', data, flags=re.DOTALL)
                    #data = data.replace(form_id,  b'~||+||~' + new_id + b'~||+||~')
        
        if nvpp_present:
            data = CFIDs.fix_nvpp_data(data,nvpp_form_ids,nvpp_start,form_id_replacements)

        data = data.replace(b'~||+||=', b'')
        data = data.replace(b'=||+||~', b'')

        data_list = data.split(b'-||+||-')

        data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list, master_count)

        # Update GRUP sizes recursively
        for top_grup in grup_hierarchy:
            CFIDs.update_grup_sizes(top_grup, sizes_list, offsets)
        
        updated_data = CFIDs.reassemble_data(grup_hierarchy, data_list, offsets)

        with open(new_file, 'wb') as f:
            f.write(updated_data)
            f.close()

        CFIDs.compacted_and_patched[os.path.basename(new_file)] = []
        

    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def patch_dependent_plugins(file, dependents, skyrim_folder_path, output_folder_path, update_header):
        form_if_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        with open(form_if_file_name, 'r') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        for dependent in dependents:
            #TODO: consider if a dependent has compressed forms... please no
            new_file = CFIDs.copy_file_to_output(dependent, skyrim_folder_path, output_folder_path)
            dependent_data = b''
            print('-    ' + new_file)
            with open(new_file, 'rb+') as dependent_file:
                #Update header to 1.71 to fit new records
                if update_header:
                    dependent_file.seek(0)
                    dependent_file.seek(30)
                    dependent_file.write(b'\x48\xE1\xDA\x3F')
                    dependent_file.seek(0)

                dependent_data = dependent_file.read()

                data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................[\x2C\x2B]\x00)|(?=GRUP....................)', dependent_data, flags=re.DOTALL) if x]
                
                offsets = []
                current_offset = 0
                for chunk in data_list:
                    offsets.append(current_offset)
                    current_offset += len(chunk)

                master_count = data_list[0].count(b'MAST')
                data_list, sizes_list = CFIDs.decompress_data(data_list, master_count)
                
                grup_hierarchy = CFIDs.parse_grups(dependent_data)

                dependent_data = b'-||+||-'.join(data_list)
                nvpp_present = False
                if b'NVPP' in dependent_data:
                    nvpp_present = True
                    dependent_data, nvpp_form_ids, nvpp_start = CFIDs.save_nvpp_data(dependent_data)
                
                master_leading_byte = CFIDs.get_master_index(file, dependent_data)
                #if master_leading_byte <= 15:
                #    mC = '0' + str(master_leading_byte)
                #else:
                #    mC = str(master_leading_byte)
                form_id_replacements = []
                for form_id_history in form_id_file_data:
                    form_id_conversion = form_id_history.split('|')
                    from_id = bytes.fromhex(form_id_conversion[0])[:3] + int.to_bytes(master_leading_byte)#bytes.fromhex(mC)
                    to_id = bytes.fromhex(form_id_conversion[1])[:3] + int.to_bytes(master_leading_byte)#bytes.fromhex(mC)
                    form_id_replacements.append([from_id, to_id])
                    if from_id[:2] == b'\x00\x00':
                        dependent_data = re.sub(b'(?<![\x2C\x2B].)' + re.escape(from_id) + b'(?!.{0,2}' + int.to_bytes(master_count) + b')', b'=||+||~' + to_id + b'~||+||=' , dependent_data, flags=re.DOTALL)
                    elif from_id[:1] == b'\x00':
                        dependent_data = re.sub(b'(?<![\x2C\x2B]..)' + re.escape(from_id) + b'(?!.{0,2}' + int.to_bytes(master_count) + b')', b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif from_id[:2] == b'\xFF\xFF':
                        dependent_data = re.sub(re.escape(from_id) + b'(?!.' + int.to_bytes(master_count) + b')',  b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif from_id[:1] == b'\xFF':
                        dependent_data = re.sub(re.escape(from_id) + b'(?!..' + int.to_bytes(master_count) + b')',  b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif from_id[:1] == b'~':
                        dependent_data = re.sub(b'(?<!' + re.escape(b'=||+||') + b')' + re.escape(from_id), b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif from_id[:1] == b'=':
                        dependent_data = re.sub(b'(?<!' + re.escape(b'~||+||') + b')' + re.escape(from_id), b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif from_id[:1] == B'\x20':
                        dependent_data = re.sub(b'(?<![A-Z]{3}[A-Z_]{1})' + re.escape(from_id), b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    elif re.match(b'[A-Z_]', from_id[:1]):
                        dependent_data = re.sub(b'(?<![A-Z]{2})' + re.escape(from_id), b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    else:
                        dependent_data = re.sub(re.escape(from_id) + b'(?!..' + re.escape(b'=||+||~') + b')(?!' + re.escape(b'~||+||=') + b')', b'=||+||~' + to_id + b'~||+||=', dependent_data, flags=re.DOTALL)
                    
                if nvpp_present:
                    dependent_data = CFIDs.fix_nvpp_data(dependent_data,nvpp_form_ids,nvpp_start,form_id_replacements)

                dependent_data = dependent_data.replace(b'~||+||=', b'')
                dependent_data = dependent_data.replace(b'=||+||~', b'')

                data_list = dependent_data.split(b'-||+||-')

                data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list, master_count)

                # Update GRUP sizes recursively
                for top_grup in grup_hierarchy:
                    CFIDs.update_grup_sizes(top_grup, sizes_list, offsets)
                
                updated_data = CFIDs.reassemble_data(grup_hierarchy, data_list, offsets)

                dependent_file.seek(0)
                dependent_file.write(updated_data)
                dependent_file.close()

            CFIDs.compacted_and_patched[os.path.basename(file)].append(dependent)
        return

    #gets what master index the file is in inside of the dependent's data
    def get_master_index(file, data):
        master_pattern = re.compile(b'MAST..(.*?).DATA')
        matches = re.findall(master_pattern, data)
        master_index = 0
        for match in matches:
            if os.path.basename(file).lower() in str(match).lower():
                return master_index
            else:
                master_index += 1