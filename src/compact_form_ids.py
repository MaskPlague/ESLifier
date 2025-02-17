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
#TODO: continue importing from test and add changes to dependent patcher
class CFIDs():
    record_types = [b'GMST', b'KYWD', b'LCRT', b'AACT', b'TXST', b'GLOB', b'CLAS', b'FACT', b'HDPT', b'EYES', b'RACE', b'SOUN', b'ASPC', b'MGEF', b'LTEX', 
                    b'ENCH', b'SPEL', b'SCRL', b'ACTI', b'TACT', b'ARMO', b'BOOK', b'CONT', b'DOOR', b'INGR', b'LIGH', b'MISC', b'APPA', b'STAT', b'MSTT', 
                    b'GRAS', b'TREE', b'FLOR', b'FURN', b'WEAP', b'AMMO', b'NPC_', b'LVLN', b'KEYM', b'ALCH', b'IDLM', b'COBJ', b'PROJ', b'HAZD', b'SLGM', 
                    b'LVLI', b'WTHR', b'CLMT', b'SPGD', b'RFCT', b'REGN', b'NAVI', b'CELL', b'WRLD', b'DIAL', b'QUST', b'IDLE', b'PACK', b'CSTY', b'LSCR', 
                    b'LVSP', b'ANIO', b'WATR', b'EFSH', b'EXPL', b'DEBR', b'IMGS', b'IMAD', b'FLST', b'PERK', b'BPTD', b'ADDN', b'AVIF', b'CAMS', b'CPTH', 
                    b'VTYP', b'MATT', b'IPCT', b'IPDS', b'ARMA', b'ECZN', b'LCTN', b'MESG', b'DOBJ', b'LGTM', b'MUSC', b'FSTP', b'FSTS', b'SMBN', b'SMQN',
                    b'SMEN', b'DLBR', b'MUST', b'DLVW', b'WOOP', b'SHOU', b'EQUP', b'RELA', b'SCEN', b'ASTP', b'OTFT', b'ARTO', b'MATO', b'MOVT', b'HAZD', 
                    b'SNDR', b'DUAL', b'SNCT', b'SOPM', b'COLL', b'CLFM', b'REVB', b'INFO', b'REFR', b'ACHR', b'NAVM', b'PGRE', b'PHZD', b'LAND']
    def compact_and_patch(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        CFIDs.lock = threading.Lock()
        CFIDs.compacted_and_patched = {}
        CFIDs.mo2_mode = mo2_mode
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

    def patch_new(compacted_file, dependents, files_to_patch, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        CFIDs.lock = threading.Lock()
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
            print("-  Patching New Dependent Files...")
            CFIDs.patch_files_threader(compacted_file, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
            print("-  Renaming Dependent Files...")
            CFIDs.rename_files_threader(compacted_file, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')

    #Create a copy of the mod plugin we're compacting
    def copy_file_to_output(file, skyrim_folder_path, output_folder):
        if CFIDs.mo2_mode:
            end_path = os.path.relpath(file, skyrim_folder_path)
            #part = relative_path.split('\\')
            #end_path = os.path.join(*part[1:])
        else:
            end_path = file[len(skyrim_folder_path) + 1:]
        new_file = os.path.join(os.path.join(output_folder,'ESLifier Compactor Output'), re.sub(r'(.*?)(/|\\)', '', end_path, 1))
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
                        if new_file_but_skyrim_pathed not in CFIDs.compacted_and_patched[os.path.basename(master)]:
                            CFIDs.compacted_and_patched[os.path.basename(master)].append(new_file_but_skyrim_pathed)
                        if new_file not in CFIDs.compacted_and_patched[os.path.basename(master)]:
                            CFIDs.compacted_and_patched[os.path.basename(master)].append(new_file)
                        if 'facegeom' in new_file.lower() and os.path.basename(master).lower() in new_file.lower():
                            facegeom_meshes.append(new_file.replace(form_ids[1].upper(), form_ids[3].upper()))
                    break
            CFIDs.compacted_and_patched[os.path.basename(master)].append(file)
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
        
        for chunk in chunks:
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
    #   \facegeom\: Texture paths in face mesh files
    #   .seq: SEQ files
    #   .pex: integer form ids in compiled scripts
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
                            #TODO: consider using regex to make sure that not only part of a form id gets replaced.
                            basename = os.path.basename(master).lower()
                            if 'skypatcher' in new_file.lower():
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
                        elif 'config.json' in new_file.lower(): #Open Animation Replacer Patching and MCM helper
                            if 'openanimationreplacer' in new_file.lower():
                                basename = os.path.basename(master).lower()
                                prev_line = ''
                                for line in f:
                                    if 'pluginName' in prev_line.lower() and basename in prev_line.lower():
                                        if 'formid' in line.lower():
                                            for form_ids in form_id_map:
                                                line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                    prev_line = line
                                    print(line.strip('\n'))
                            elif 'mcm\\config' in new_file.lower(): #MCM helper
                                basename = os.path.basename(master).lower()
                                for line in f:
                                    if 'sourecform' in line.lower() and basename in line.lower():
                                        for form_ids in form_id_map:
                                            line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                    print(line.strip('\n'))
                        elif '_conditions.txt' in new_file.lower(): #Dynamic Animation Replacer Patching
                            basename = os.path.basename(master).lower()
                            for line in f:
                                if basename in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace('0x00' + form_ids[1], '0x00' + form_ids[3]).replace('0x' + form_ids[1], '0x' + form_ids[3]).replace('0x00' + form_ids[1].lower(), '0x00' + form_ids[3].lower()).replace('0x' + form_ids[1].lower(), '0x' + form_ids[3].lower()).replace('0X00' + form_ids[1], '0X00' + form_ids[3]).replace('0X' + form_ids[1], '0X' + form_ids[3]).replace('0X00' + form_ids[1].lower(), '0X00' + form_ids[3].lower()).replace('0X' + form_ids[1].lower(), '0X' + form_ids[3].lower())
                                print(line.strip('\n'))
                        elif '_srd.' in new_file.lower(): #Sound record distributor patching
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for form_ids in form_id_map:
                                        line = line.replace('|' + form_ids[1], '|' + form_ids[3]).replace('|' + form_ids[0], '|' + form_ids[2]).replace('|' + form_ids[1].lower(), '|' + form_ids[3].lower()).replace('|' + form_ids[0].lower(), '|' + form_ids[2].lower())
                                print(line.strip('\n'))
                        elif '.psc' in new_file.lower(): #Script source file patching, this doesn't take into account form ids being passed as variables
                            for line in f:
                                if os.path.basename(master).lower() in line.lower() and 'getformfromfile' in line.lower():
                                    for form_ids in form_id_map:
                                        line = re.sub(r'(0x0{0,7})(' + re.escape(form_ids[0]) + r' *,)', r'\0' + form_ids[2] + ',', line, re.IGNORECASE)
                                print(line.strip('\n'))
                        elif '.json' in new_file.lower(): #Dynamic Key Activation Framework NG, Smart Harvest Auto NG AutoLoot and whatever else may be using .json?
                            #TODO: check for other json mods
                            #TODO: convert this to read the files as jsons instead of line replacements...
                            basename = os.path.basename(master).lower()
                            if basename.startswith('shse.'):
                                prev_line = ''
                                for line in f:
                                    if 'plugin' in prev_line.lower() and basename in prev_line.lower(): #Smart Harvest
                                        if 'form' in line.lower():
                                            for form_ids in form_id_map:
                                                line = line.replace(form_ids[1], form_ids[3]).replace(form_ids[0], form_ids[2]).replace(form_ids[1].lower(), form_ids[3].lower()).replace(form_ids[0].lower(), form_ids[2].lower())
                                    prev_line = line
                                    print(line.strip('\n'))
                            else: #Dynamic Key Activation Framework NG, Dynamic String Distributor
                                for line in f:
                                    if basename in line.lower():
                                        for form_ids in form_id_map:
                                            line = line.replace(form_ids[0], form_ids[2]).replace(form_ids[1], form_ids[3]).replace(form_ids[0].lower(), form_ids[2].lower()).replace(form_ids[1].lower(), form_ids[3].lower())
                                    print(line.strip('\n'))
                            
                                    
                        fileinput.close()
            
            elif 'facegeom' in new_file.lower():
                if '.nif' in new_file.lower(): #FaceGeom mesh patching
                    #TODO: check byte structure via hex editor to see what may go wrong here
                    with CFIDs.lock:
                        with open(new_file, 'rb+') as f:
                            data = f.readlines()
                            bytes_basename = bytes(os.path.basename(master).upper(), 'utf-8')
                            for i in range(len(data)):
                                if bytes_basename in data[i].upper(): #check for plugin name, in file path, in line of nif file.
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
                            #TODO: figure out the proper method of getting to the variables so I don't accidentally replace the wrong bytes
                            for form_ids in form_id_map:
                                #\x03 indicates a integer in compiled .pex files. \x00 will always be present instead of the master byte
                                data = data.replace(b'\x03\x00' + form_ids[4][::-1][1:], b'\x03\x00-||+||-' + form_ids[5][::-1][1:])
                            data = data.replace(b'-||+||-', b'')
                            f.seek(0)
                            f.write(data)
                        f.close()
            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(master)].append(file)

    def decompress_data(data_list, master_count):
        sizes_list = [[] for _ in range(len(data_list))]

        for i in range(len(data_list)):
            if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count) and data_list[i][:4] != b'GRUP':
                size = int.from_bytes(data_list[i][4:8][::-1])
                try:
                    decompressed = zlib.decompress(data_list[i][28:size + 24])  # Decompress the form
                except Exception as e:
                    print(f'Error: {e}\rHeader: {data_list[i][:24]}' )
                    
                sizes_list[i] = [len(data_list[i]), 0, i, len(data_list[i])]
                data_list[i] = data_list[i][:28] + decompressed + data_list[i][size+24:]

        return data_list, sizes_list
    
    def recompress_data(data_list, sizes_list, master_count):
        for i in range(len(data_list)):
            if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count) and data_list[i][:4] != b'GRUP':
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
    
    def get_kwda_offsets(in_field_offset, form):
        offsets = []
        ksiz_offset = form.find(b'KSIZ', 24)
        ksiz = int.from_bytes(form[ksiz_offset+6:ksiz_offset+10][::-1])
        in_field_offset += 6
        for _ in range(ksiz):
            offsets.append(in_field_offset)
            in_field_offset += 4
        return offsets

    def get_alt_texture_offsets(in_field_offset, form):
        offsets = []
        alternate_texture_count = int.from_bytes(form[in_field_offset+6:in_field_offset+10][::-1])
        in_field_offset += 10
        for _ in range(alternate_texture_count):
            alt_tex_size = int.from_bytes(form[in_field_offset:in_field_offset+4][::-1])
            offsets.append(in_field_offset+alt_tex_size+4)
            in_field_offset += 8
        return offsets
        
    def patch_form_data(data_list, forms, form_id_replacements):
        for i, form, offsets in forms:
            for offset in offsets:
                for from_id, to_id in form_id_replacements:
                    if form[offset:offset+4] == from_id:
                        form[offset:offset+4] = to_id
                        break
            data_list[i] = bytes(form)
        return data_list
    
    def save_form_data(data_list, master_byte):
        saved_forms = []
        for i, form in enumerate(data_list):
            if b'REFR' == form[:4]:
                saved_forms.append(CFIDs.save_refr_data(i, form, master_byte))
                data_list[i] = form[:24]
            elif b'ACHR' == form[:4]: #TODO this needs something like LAND b'LAND' == form[:4] or (form[:4] == b'GRUP' and len(form) > 24 and form[24:28] == b'LAND'):
                saved_forms.append(CFIDs.save_achr_data(i, form, master_byte))
                data_list[i] = form[:24]
            elif b'ACTI' == form[:4]:
                saved_forms.append(CFIDs.save_acti_data(i, form, master_byte))
                data_list[i] = form[:24]
            elif b'AACT' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'ADDN' == form[:4]:
                saved_forms.append(CFIDs.save_addn_data(i, form))
                data_list[i] = form[:24]
            elif b'ALCH' == form[:4]:
                saved_forms.append(CFIDs.save_alch_data(i, form, master_byte))
                data_list[i] = form[:24]
            elif b'AMMO' == form[:4]:
                saved_forms.append(CFIDs.save_ammo_data(i, form))
                data_list[i] = form[:24]
            elif b'ANIO' == form[:4]:
                saved_forms.append(CFIDs.save_anio_data(i, form))
                data_list[i] = form[:24]
            elif b'APPA' == form[:4]:
                saved_forms.append(CFIDs.save_appa_data(i, form, master_byte))
                data_list[i] == form[:24]
            elif b'ARMA' == form[:4]:
                saved_forms.append(CFIDs.save_arma_data(i, form))
                data_list[i] == form[:24]
            elif b'ARMO' == form[:4]:
                saved_forms.append(CFIDs.save_armo_data(i, form))
                data_list[i] = form[:24]
            elif b'ARTO' == form[:4]:
                saved_forms.append(CFIDs.save_arto_data(i, form))
                data_list[i] = form[:24]
            elif b'ASPC' == form[:4]:
                saved_forms.append(CFIDs.save_aspc_data(i, form))
                data_list[i] = form[:24]
            elif b'ASTP' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'AVIF' == form[:4]:
                saved_forms.append(CFIDs.save_avif_data(i, form))
                data_list[i] = form[:24]
            elif b'BOOK' == form[:4]:
                saved_forms.append(CFIDs.save_book_data(i, form))
                data_list[i] = form[:24]
            elif b'BPTD' == form[:4]:
                saved_forms.append(CFIDs.save_bptd_data(i, form))
                data_list[i] = form[:24]
            elif b'CAMS' == form[:4]:
                saved_forms.append(CFIDs.save_cams_data(i, form))
                data_list[i] = form[:24]
            elif b'CELL' == form[:4]:
                saved_forms.append(CFIDs.save_cell_data(i, form))
                data_list[i] = form[:24]
            elif b'CLAS' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'CLFM' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'CLMT' == form[:4]:
                saved_forms.append(CFIDs.save_clmt_data(i, form))
                data_list[i] = form[:24]
            elif b'COBJ' == form[:4]:
                saved_forms.append(CFIDs.save_cobj_data(i, form))
                data_list[i] = form[:24]
            elif b'COLL' == form[:4]:
                saved_forms.append(CFIDs.save_coll_data(i, form))
                data_list[i] = form[:24]
            elif b'CONT' == form[:4]:
                saved_forms.append(CFIDs.save_cont_data(i, form))
                data_list[i] = form[:24]
            elif b'CPTH' == form[:4]:
                saved_forms.append(CFIDs.save_cpth_data(i, form))
                data_list[i] = form[:24]
            elif b'CSTY' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'DEBR' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'DIAL' == form[:4]:
                saved_forms.append(CFIDs.save_dial_data(i, form))
                data_list[i] = form[:24]
            elif b'DLBR' == form[:4]:
                saved_forms.append(CFIDs.save_dlbr_data(i, form))
                data_list[i] = form[:24]
            elif b'DLVW' == form[:4]:
                saved_forms.append(CFIDs.save_dlvw_data(i, form))
                data_list[i] = form[:24]
            elif b'DOBJ' == form[:4]:
                saved_forms.append(CFIDs.save_dobj_data(i, form))
                data_list[i] = form[:24]
            elif b'DOOR' == form[:4]:
                saved_forms.append(CFIDs.save_door_data(i, form))
                data_list[i] = form[:24]
            elif b'DUAL' == form[:4]:
                saved_forms.append(CFIDs.save_dual_data(i, form))
                data_list[i] = form[:24]
            elif b'ECZN' == form[:4]:
                saved_forms.append(CFIDs.save_eczn_data(i, form))
                data_list[i] = form[:24]
            elif b'EFSH' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'ENCH' == form[:4]:
                saved_forms.append(CFIDs.save_ench_data(i, form))
                data_list[i] = form[:24]
            elif b'EQUP' == form[:4]:
                saved_forms.append(CFIDs.save_equp_data(i, form))
                data_list[i] = form[:24]
            elif b'EXPL' == form[:4]:
                saved_forms.append(CFIDs.save_expl_data(i, form))
                data_list[i] = form[:24]
            elif b'EYES' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'FACT' == form[:4]:
                saved_forms.append(CFIDs.save_fact_data(i, form))
                data_list[i] = form[:24]
            elif b'FLOR' == form[:4]:
                saved_forms.append(CFIDs.save_flor_data(i, form))
                data_list[i] = form[:24]
            elif b'FLST' == form[:4]:
                saved_forms.append(CFIDs.save_flst_data(i, form))
                data_list[i] = form[:24]
            elif b'FSTP' == form[:4]:
                saved_forms.append(CFIDs.save_fstp_data(i, form))
                data_list[i] = form[:24]
            elif b'FSTS' == form[:4]:
                saved_forms.append(CFIDs.save_fsts_data(i, form))
                data_list[i] = form[:24]
            elif b'FURN' == form[:4]:
                saved_forms.append(CFIDs.save_furn_data(i, form))
                data_list[i] = form[:24]
            elif b'GLOB' == form[:4]:
                saved_forms.append(CFIDs.save_glob_data(i, form))
                data_list[i] = form[:24]
            elif b'GMST' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'GRAS' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'GRUP' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
            elif b'HAZD' == form[:4]:
                saved_forms.append(CFIDs.save_hazd_data(i, form))
                data_list[i] = form[:24]
            elif b'HDPT' == form[:4]:
                saved_forms.append(CFIDs.save_hdpt_data(i, form))
                data_list[i] = form[:24]
            elif b'IDLE' == form[:4]:
                saved_forms.append(CFIDs.save_idle_data(i, form))
                data_list[i] = form[:24]
            elif b'IDLM' == form[:4]:
                saved_forms.append(CFIDs.save_idlm_data(i, form))
                data_list[i] = form[:24]
            elif b'IMAD' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'IMGS' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'INFO' == form[:4]:
                saved_forms.append(CFIDs.save_info_data(i, form))
                data_list[i] = form[:24]
            elif b'INGR' == form[:4]:
                saved_forms.append(CFIDs.save_ingr_data(i, form))
                data_list[i] = form[:24]
            elif b'IPCT' == form[:4]:
                saved_forms.append(CFIDs.save_ipct_data(i, form))
                data_list[i] = form[:24]
            elif b'IPDS' == form[:4]:
                saved_forms.append(CFIDs.save_ipds_data(i, form))
                data_list[i] = form[:24]
            elif b'KEYM' == form[:4]:
                saved_forms.append(CFIDs.save_keym_data(i, form))
                data_list[i] = form[:24]
            elif b'KYWD' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]
            elif b'LAND' == form[:4] or (form[:4] == b'GRUP' and len(form) > 24 and form[24:28] == b'LAND'):
                saved_forms.append(CFIDs.save_land_data(i, form))
                data_list[i] = form[:24]
            elif b'LCRT' == form[:4]:
                saved_forms.append([i, bytearray(form), [12]])
                data_list[i] = form[:24]


            elif b'MGEF' == form[:4]:
                saved_forms.append(CFIDs.save_mgef_data(i, form, master_byte))
                data_list[i] = form[:24]
            elif b'STAT' == form[:4]:
                saved_forms.append(CFIDs.save_stat_data(i, form))
                data_list[i] == form[:24]

        
        return saved_forms

    

    def save_refr_data(i, form, master_byte):
        refr_fields = [b'NAME', b'LNAM', b'INAM', b'XLRM', b'XEMI', b'XLIB', b'XLRT', b'XOWN', b'XEZN', b'XMBR', b'XPWR', b'XATR', b'INAM', b'XLRL', b'XAPR',  b'XTEL', b'XNDP', b'XESP']
        special_refr_fields = [b'PDTO', b'XLOC', b'XLKR', b'XPOD', b'VMAD']

        refr_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in refr_fields:
                refr_offsets.append(offset + 6)
            elif field in special_refr_fields:
                if field == b'PDTO' or field == b'XLOC':
                    refr_offsets.append(offset + 10)
                elif field == b'XLKR' or field == b'XPOD':
                    refr_offsets.append(offset + 6)
                    refr_offsets.append(offset + 10)
                elif field == b'VMAD':
                    refr_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), refr_offsets]

    def save_mgef_data(i, form, master_byte):
        mgef_fields = [b'MDOB', b'ESCE']
        special_mgef_fields = [b'KWDA', b'SNDD', b'CTDA', b'VMAD', b'DATA']

        mgef_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in mgef_fields:
                mgef_offsets.append(offset + 6)
            elif field in special_mgef_fields:
                if field == b'KWDA':
                    mgef_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'SNDD':
                    list_size = field_size // 8
                    in_field_offset = offset + 6
                    for _ in range(list_size):
                        mgef_offsets.append(in_field_offset+4)
                        in_field_offset += 8
                elif field == b'CTDA':
                    mgef_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
                elif field == b'VMAD':
                    mgef_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'DATA':
                    data_offset = offset + 6 #start of DATA's data
                    mgef_offsets.append(data_offset + 8)    # 08:RelatedID
                    mgef_offsets.append(data_offset + 24)   # 18:LightID
                    mgef_offsets.append(data_offset + 32)   # 20:HitShader
                    mgef_offsets.append(data_offset + 36)   # 24:EnchantShader
                    mgef_offsets.append(data_offset + 72)   # 48:ProjectileID
                    mgef_offsets.append(data_offset + 76)   # 4C:ExplosionID
                    mgef_offsets.append(data_offset + 92)   # 5C:CastingArtID
                    mgef_offsets.append(data_offset + 96)   # 60:HitEffectArtID
                    mgef_offsets.append(data_offset + 100)  # 64:ImpactDataID
                    mgef_offsets.append(data_offset + 108)  # 6C:DualCastID
                    mgef_offsets.append(data_offset + 116)  # 74:EnchantArtID
                    mgef_offsets.append(data_offset + 128)  # 80:EquipAbility
                    mgef_offsets.append(data_offset + 132)  # 84:ImageSpaceModID
                    mgef_offsets.append(data_offset + 136)  # 88:PerkID
            offset += field_size + 6

        return [i, bytearray(form), mgef_offsets]
    
    def save_achr_data(i, form, master_byte):
        #XESP and XAPR are structs but FormID is in same offset as others
        achr_fields = [b'NAME', b'XEZN', b'INAM', b'XAPR', b'XLRT', b'XHOR', b'XOWN', b'XESP', b'XLCN', b'XLRL']
        special_achr_fields = [b'PDTO', b'VMAD']

        achr_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in achr_fields:
                achr_offsets.append(offset + 6)
            elif field in special_achr_fields:
                if field == b'PDTO':
                    if form[offset+6:offset+7] == b'\x00':
                        achr_offsets.append(offset + 10)
                elif field == b'VMAD':
                    achr_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
            offset += field_size + 6
        return [i, bytearray(form), achr_offsets]
    
    def save_acti_data(i, form, master_byte):
        acti_fields = [b'SNAM', b'VNAM', b'WNAM', b'KNAM']
        special_acti_fields = [b'KWDA', b'MODS', b'VMAD', b'DSTD', b'DMDS']

        acti_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in acti_fields:
                acti_offsets.append(offset + 6)
            elif field in special_acti_fields:
                if field == b'KWDA':
                    acti_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'DSTD':
                    acti_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    acti_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    acti_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'MODS':
                    acti_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    acti_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))

            offset += field_size + 6

        return [i, bytearray(form), acti_offsets]

    def save_addn_data(i, form):
        addn_fields = [b'SNAM']

        addn_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in addn_fields:
                addn_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), addn_offsets]

    def save_alch_data(i, form, master_byte):
        alch_fields = [b'YNAM', b'ZNAM', b'EFID']
        special_alch_fields = [b'KWDA', b'ENIT', b'MODS', b'CTDA']

        alch_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in alch_fields:
                alch_offsets.append(offset + 6)
            elif field in special_alch_fields:
                if field == b'KWDA':
                    alch_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'MODS':
                    alch_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'ENIT':
                    alch_offsets.append(offset + 14) #Addiction     6 + 8
                    alch_offsets.append(offset + 22) #UseSound SNDR 6 + 16
                elif field == b'CTDA':
                    alch_offsets.append(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), alch_offsets]

    def save_ammo_data(i, form):
        ammo_fields = [b'YNAM', b'ZNAM', b'DATA']
        special_ammo_fields = [b'KWDA']

        ammo_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in ammo_fields:
                ammo_offsets.append(offset + 6)
            elif field in special_ammo_fields:
                if field == b'KWDA':
                    ammo_offsets.extend(CFIDs.get_kwda_offsets(offset,form))
            offset += field_size + 6

        return [i, bytearray(form), ammo_offsets]

    def save_anio_data(i, form):
        special_anio_fields = [b'MODS']

        anio_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_anio_fields:
                if field == b'MODS':
                    anio_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), anio_offsets]

    def save_appa_data(i, form, master_byte):
        appa_fields = [b'YNAM', b'ZNAM']
        special_appa_fields = [b'DSTD', b'DMDS', b'VMAD']

        appa_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in appa_fields:
                appa_offsets.append(offset + 6)
            elif field in special_appa_fields:
                if field == b'DSTD':
                    appa_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    appa_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    appa_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    appa_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), appa_offsets]

    def save_arma_data(i, form):
        arma_fields = [b'RNAM', b'NAM0', b'NAM1', b'NAM2', b'NAM3', b'MODL', b'SNDD', b'ONAM']

        arma_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in arma_fields:
                arma_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), arma_offsets]
    
    def save_armo_data(i, form, master_byte):
        armo_fields = [b'EITM', b'YNAM', b'ZNAM', b'ETYP', b'BIDS', b'BAMT', b'RNAM', b'MODL', b'TNAM']
        special_armo_fields = [b'KWDA', b'VMAD', b'MODS', b'MO2S', b'MO4S', b'DSTD', b'DMDS']

        armo_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in armo_fields:
                armo_offsets.append(offset + 6)
            elif field in special_armo_fields:
                if field == b'KWDA':
                    armo_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'VMAD':
                    armo_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'MODS' or field == b'MO2S' or field == b'MO4S':
                    armo_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    armo_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    armo_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    armo_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), armo_offsets]

    def save_arto_data(i, form):
        special_arto_fields = [b'MODS']

        arto_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_arto_fields:
                if field == b'MODS':
                    arto_offsets.extend(CFIDs.get_alt_texture_offsets(offset,form))
            offset += field_size + 6

        return [i, bytearray(form), arto_offsets]

    def save_aspc_data(i, form):
        aspc_fields = [b'SNAM', b'RDAT', b'BNAM']

        aspc_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in aspc_fields:
                aspc_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), aspc_offsets]

    def save_avif_data(i, form):
        avif_fields = [b'PNAM', b'SNAM']

        avif_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in avif_fields:
                avif_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), avif_offsets]

    def save_book_data(i, form, master_byte):
        book_fields = [b'YNAM', b'ZNAM', b'INAM']
        special_book_fields = [b'VMAD', b'MODS', b'DSTD', b'DMDS', b'KWDA' b'DATA']

        book_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in book_fields:
                book_offsets.append(offset + 6)
            elif field in special_book_fields:
                if field == b'KWDA':
                    book_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'VMAD':
                    book_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'MODS':
                    book_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    book_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    book_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    book_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'DATA':
                    book_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), book_offsets]

    def save_bptd_data(i, form):
        bptd_fields = [b'RAGA']
        special_bptd_fields = [b'MODS', b'BPND']

        bptd_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in bptd_fields:
                bptd_offsets.append(offset + 6)
            elif field in special_bptd_fields:
                if field == b'MODS':
                    bptd_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'BPND':
                    in_field_offset = offset + 6
                    bptd_offsets.append(in_field_offset+ 12) # DEBR
                    bptd_offsets.append(in_field_offset+ 16) # EXPL
                    bptd_offsets.append(in_field_offset+ 32) # DEBR
                    bptd_offsets.append(in_field_offset+ 36) # EXPL
                    bptd_offsets.append(in_field_offset+ 68) # Severable IPDS
                    bptd_offsets.append(in_field_offset+ 72) # Explodable IPDS
            offset += field_size + 6

        return [i, bytearray(form), bptd_offsets]

    def save_cams_data(i, form):
        cams_fields = [b'MNAM']

        cams_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in cams_fields:
                cams_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), cams_offsets]

    def save_cell_data(i, form):
        cell_fields = [b'LTMP', b'XLCN', b'XCWT', b'XOWN', b'XILL', b'XCCM', b'XCAS', b'XEZN', b'XCMO', b'XCIM']
        special_cell_fields = [b'XCLR']

        cell_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in cell_fields:
                cell_offsets.append(offset + 6)
            elif field in special_cell_fields:
                if field == b'XCLR':
                    form_id_count = field_size // 4
                    in_field_offset = offset + 6
                    for _ in range(form_id_count):
                        cell_offsets.append(in_field_offset)
                        in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), cell_offsets]

    def save_clmt_data(i, form):
        special_clmt_fields = [b'WLST']

        clmt_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])

            if field in special_clmt_fields:
                if field == b'WLST':
                    array_size = field_size // 12
                    in_field_offset = offset + 6
                    for _ in range(array_size):
                        clmt_offsets.append(in_field_offset)
                        clmt_offsets.append(in_field_offset + 8)
                        in_field_offset += 12
            offset += field_size + 6

        return [i, bytearray(form), clmt_offsets]

    def save_cobj_data(i, form, master_byte):
        cobj_fields = [b'CNAM', b'BNAM', b'CNTO']
        special_cobj_fields = [b'COED', b'CTDA']

        cobj_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in cobj_fields:
                cobj_offsets.append(offset + 6)
            elif field in special_cobj_fields:
                if field == b'COED':
                    cobj_offsets.append(offset + 6)
                    cobj_offsets.append(offset + 10)
                elif field == b'CTDA':
                    cobj_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), cobj_offsets]

    def save_coll_data(i, form):
        special_coll_fields = [b'CNAM']

        coll_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_coll_fields:
                if field == b'CNAM':
                    intv_offset = form.find(b'INTV', 24)
                    intv = int.from_bytes(form[intv_offset+6:intv_offset+10][::-1])
                    in_field_offset = offset + 6
                    for _ in range(intv):
                        coll_offsets.append(in_field_offset)
                        in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), coll_offsets]
    
    def save_cont_data(i, form, master_byte):
        cont_fields = [b'SNAM', b'QNAM', b'CNTO']
        special_cont_fields = [b'MODS', b'VMAD', b'COED']

        cont_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in cont_fields:
                cont_offsets.append(offset + 6)
            elif field in special_cont_fields:
                if field == b'MODS':
                    cont_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    cont_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'COED':
                    cont_offsets.append(offset + 6)
                    cont_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), cont_offsets]

    def save_cpth_data(i, form, master_byte):
        cpth_fields = [b'SNAM']
        special_cpth_fields = [b'ANAM', b'CTDA']

        cpth_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in cpth_fields:
                cpth_offsets.append(offset + 6)
            elif field in special_cpth_fields:
                if field == b'ANAM':
                    cpth_offsets.append(offset + 6)
                    cpth_offsets.append(offset + 10)
                elif field == b'CTDA':
                    cpth_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), cpth_offsets]

    def save_dial_data(i, form):
        dial_fields = [b'QNAM', b'BNAM']

        dial_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in dial_fields:
                dial_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dial_offsets]
    
    def save_dlbr_data(i, form):
        dlbr_fields = [b'QNAM', b'SNAM']

        dlbr_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in dlbr_fields:
                dlbr_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dlbr_offsets]
    
    def save_dlvw_data(i, form):
        dlvw_fields = [b'QNAM', b'BNAM', b'TNAM']

        dlvw_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in dlvw_fields:
                dlvw_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), dlvw_offsets]

    def save_dobj_data(i, form): 
        special_dobj_fields = [b'DNAM']

        dobj_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_dobj_fields:
                if field == b'DNAM':
                    array_size = field_size // 8
                    in_field_offset = offset + 6
                    for _ in range(array_size):
                        dobj_offsets.append(in_field_offset + 4)
                        in_field_offset += 8
                        
            offset += field_size + 6

        return [i, bytearray(form), dobj_offsets]

    def save_door_data(i, form, master_byte): 
        door_fields = [b'SNAM', b'ANAM', b'BNAM', b'TNAM']
        special_door_fields = [b'VMAD', b'MODS']

        door_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in door_fields:
                door_offsets.append(offset + 6)
            elif field in special_door_fields:
                if field == b'MODS':
                    door_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'VMAD':
                    door_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), door_offsets]

    def save_dual_data(i, form): 
        special_dual_fields = [b'DATA']

        dual_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_dual_fields:
                if b'DATA':
                    in_field_offset = offset + 6
                    dual_offsets.append(in_field_offset)    # PROJ
                    dual_offsets.append(in_field_offset+ 4) # EXPL
                    dual_offsets.append(in_field_offset+ 8) # EFSH
                    dual_offsets.append(in_field_offset+ 12)# ARTO
                    dual_offsets.append(in_field_offset+ 16)# IPDS
            offset += field_size + 6

        return [i, bytearray(form), dual_offsets]

    def save_eczn_data(i, form): 
        special_eczn_fields = [b'DATA']

        eczn_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_eczn_fields:
                if field == b'DATA':
                    eczn_offsets.append(offset + 6)
                    eczn_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), eczn_offsets]

    def save_ench_data(i, form, master_byte):
        ench_fields = [b'EFID']
        special_ench_fields = [b'ENIT', b'CTDA']

        ench_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in ench_fields:
                ench_offsets.append(offset + 6)
            elif field in special_ench_fields:
                if field == b'CTDA':
                    ench_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
                elif field == b'ENIT':
                    if field_size == 36:
                        ench_offsets.append(offset + 34) #Base Enchantment (28 + 6)
                        ench_offsets.append(offset + 38) #Worn Restrictions FLST (32 + 6)
                    elif field_size == 32:
                        ench_offsets.append(offset + 34) #Base Enchantment (28 + 6)
            offset += field_size + 6

        return [i, bytearray(form), ench_offsets]

    def save_equp_data(i, form): 
        special_equp_fields = [b'PNAM']

        equp_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_equp_fields:
                if field == b'PNAM':
                    pnam_size = field_size // 4
                    in_field_offset = offset + 6
                    for _ in range(pnam_size):
                        equp_offsets.append(in_field_offset)
                        in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), equp_offsets]

    def save_expl_data(i, form): 
        expl_fields = [b'EITM', b'MNAM']

        expl_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in expl_fields:
                expl_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), expl_offsets]

    def save_fact_data(i, form, master_byte): 
        fact_fields = [b'XNAM', b'JAIL', b'WAIT', b'STOL', b'PLCN', b'CRGR', b'JOUT' b'VEND', b'VENC']
        special_fact_fields = [b'PLVD', b'CTDA']

        fact_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in fact_fields:
                fact_offsets.append(offset + 6)
            elif field in special_fact_fields:
                if field == b'PLVD':
                    fact_offsets.append(offset + 10)
                elif field == b'CTDA':
                    fact_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), fact_offsets]

    def save_flor_data(i, form, master_byte): 
        flor_fields = [b'PFIG', b'SNAM']
        special_flor_fields = [b'KWDA', b'VMAD', b'MODS', b'DSTD', b'DMDS']

        flor_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in flor_fields:
                flor_offsets.append(offset + 6)
            elif field in special_flor_fields:
                if field == b'KWDA':
                    flor_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'VMAD':
                    flor_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'MODS':
                    flor_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    flor_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    flor_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    flor_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), flor_offsets]

    def save_flst_data(i, form): 
        flst_fields = [b'FLST']

        flst_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in flst_fields:
                flst_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), flst_offsets]

    def save_fstp_data(i, form): 
        fstp_fields = [b'DATA']

        fstp_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in fstp_fields:
                fstp_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), fstp_offsets]

    def save_fsts_data(i, form): 
        special_fsts_fields = [b'DATA']

        fsts_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_fsts_fields:
                if field == b'DATA':
                    data_length = field_size // 4
                    in_field_offset = offset + 6
                    for _ in range(data_length):
                        fsts_offsets.append(in_field_offset)
                        in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), fsts_offsets]

    def save_furn_data(i, form, master_byte): 
        furn_fields = [b'KNAM', b'NAM1', b'FNMK']
        special_furn_fields = [b'VMAD', b'MODS', b'KWDA', b'DSTD', b'DMDS']

        furn_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in furn_fields:
                furn_offsets.append(offset + 6)
            elif field in special_furn_fields:
                if field == b'KWDA':
                    furn_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'VMAD':
                    furn_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'MODS':
                    furn_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
                elif field == b'DSTD':
                    furn_offsets.append(offset+14) #ExplosionID 6 + 4 + 4
                    furn_offsets.append(offset+18) #DebrisID    6 + 4 + 4 + 4
                elif field == b'DMDS':
                    furn_offsets.extend(CFIDs.get_alt_texture_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), furn_offsets]

    def save_glob_data(i, form, master_byte): 
        special_glob_fields = [b'VMAD']

        glob_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_glob_fields:
                if field == b'VMAD':
                    glob_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), glob_offsets]

    def save_hazd_data(i, form): 
        hazd_fields = [b'MNAM']
        special_hazd_fields = [b'DATA']

        hazd_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in hazd_fields:
                hazd_offsets.append(offset + 6)
            elif field in special_hazd_fields:
                if field == b'DATA':
                    in_field_offset = offset + 6
                    hazd_offsets.append(in_field_offset+ 24) #Spell
                    hazd_offsets.append(in_field_offset+ 28) #Light
                    hazd_offsets.append(in_field_offset+ 32) #Impact Data Set
                    hazd_offsets.append(in_field_offset+ 36) #Sound
            offset += field_size + 6

        return [i, bytearray(form), hazd_offsets]

    def save_hdpt_data(i, form): 
        hdpt_fields = [b'HNAM', b'TNAM', b'RNAM', b'CNAM']

        hdpt_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in hdpt_fields:
                hdpt_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), hdpt_offsets]
    
    def save_idle_data(i, form, master_byte): 
        special_idle_fields = [b'CTDA', b'ANAM']

        idle_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_idle_fields:
                if field == b'CTDA':
                    idle_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
                elif field == b'ANAM':
                    idle_offsets.append(offset + 6)
                    idle_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), idle_offsets]

    def save_idlm_data(i, form): 
        special_idlm_fields = [b'IDLA']

        idlm_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_idlm_fields:
                idla_length = field_size // 4
                in_field_offset = offset + 6
                for _ in range(idla_length):
                    idlm_offsets.append(in_field_offset)
                    in_field_offset += 4
            offset += field_size + 6

        return [i, bytearray(form), idlm_offsets]

    def save_info_data(i, form, master_byte): 
        info_fields = [b'PNAM', b'TCLT', b'DNAM', b'SNAM', b'LNAM', b'ANAM', b'TWAT', b'ONAM']
        special_info_fields = [b'VMAD', b'TRDT', b'CTDA']

        info_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in info_fields:
                info_offsets.append(offset + 6)
            elif field in special_info_fields:
                if field == b'VMAD':
                    info_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'TRDT':
                    info_offsets.append(offset + 22) #response.SoundFile (16 + 6)
                elif field == b'CTDA':
                    info_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), info_offsets]

    def save_ingr_data(i, form, master_byte): 
        ingr_fields = [b'YNAM', b'ZNAM']
        special_ingr_fields = [b'VMAD', b'KWDA', b'CTDA']

        ingr_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in ingr_fields:
                ingr_offsets.append(offset + 6)
            elif field in special_ingr_fields:
                if field == b'VMAD':
                    ingr_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'KWDA':
                    ingr_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
                elif field == b'CTDA':
                    ingr_offsets.extend(CFIDs.ctda_reader(form, offset, master_byte))
            offset += field_size + 6

        return [i, bytearray(form), ingr_offsets]

    def save_ipct_data(i, form): 
        ipct_fields = [b'DNAM', b'ENAM', b'SNAM', b'NAM1', b'NAM2']

        ipct_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in ipct_fields:
                ipct_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), ipct_offsets]

    def save_ipds_data(i, form): 
        special_ipds_fields = [b'PNAM']

        ipds_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_ipds_fields:
                if field == b'PNAM':
                    ipds_offsets.append(offset + 6)
                    ipds_offsets.append(offset + 10)
            offset += field_size + 6

        return [i, bytearray(form), ipds_offsets]

    def save_keym_data(i, form, master_byte): 
        keym_fields = [b'YNAM', b'ZNAM']
        special_keym_fields = [b'VMAD', b'KWDA']

        keym_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in keym_fields:
                keym_offsets.append(offset + 6)
            elif field in special_keym_fields:
                if field == b'VMAD':
                    keym_offsets.extend(CFIDs.vmad_reader(form, offset, master_byte))
                elif field == b'KWDA':
                    keym_offsets.extend(CFIDs.get_kwda_offsets(offset, form))
            offset += field_size + 6

        return [i, bytearray(form), keym_offsets]

    def save_land_data(i, form): 
        land_fields = [b'ATXT', b'BTXT']

        land_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in land_fields:
                land_offsets.append(offset + 6)
            offset += field_size + 6

        return [i, bytearray(form), land_offsets]

    def save_lctn_data(i, form): #TODO: THIS
        lctn_fields = [b'ACEC', b'LCEC', b'PNAM', b'NAM1', b'FNAM', b'MNAM', b'NAM0']
        special_lctn_fields = [b'ACPR', b'LCPR', b'RCPR', b'ACUN', b'LCUN', b'ACSR', b'LCSR', b'ACID', b'LCID', b'KWDA']

        lctn_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in lctn_fields:
                lctn_offsets.append(offset + 6)
            elif field in special_lctn_fields:
                pass
            offset += field_size + 6

        return [i, bytearray(form), lctn_offsets]


    def save_stat_data(i, form):
        special_stat_fields = [b'DNAM', b'MODS']

        stat_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in special_stat_fields:
                if field == b'DNAM':
                    stat_offsets.append(offset+10)
                elif field == b'MODS':
                    in_field_offset = offset
                    alternate_texture_count = int.from_bytes(form[offset+6:offset+10][::-1])
                    in_field_offset += 10
                    for _ in range(alternate_texture_count):
                        alt_tex_size = int.from_bytes(form[in_field_offset:in_field_offset+4][::-1])
                        stat_offsets.append(in_field_offset+alt_tex_size+4)
                        in_field_offset += 8
            offset += field_size + 6

        return [i, bytearray(form), stat_offsets]

    
    
    #Template for each type of form
    def save_FORMtemplate_data(i, form, master_byte): #Master byte will be for VMAD and temporarily is for CTDA
        FORM_fields = [b'']
        special_FORM_fields = [b'']

        FORM_offsets = [12]
        offset = 24
        while offset < len(form):
            field = form[offset:offset+4]
            field_size = int.from_bytes(form[offset+4:offset+6][::-1])
            if field in FORM_fields:
                FORM_offsets.append(offset + 6)
            elif field in special_FORM_fields:
                pass
            offset += field_size + 6

        return [i, bytearray(form), FORM_offsets]

                    
    def ctda_reader(form, offset, master_byte): #TODO: proper implementation... ugh
        offsets = []
        ctda_size = int.from_bytes(form[offset+4:offset+6][::-1]) + offset
        while offset < ctda_size and offset < len(form):
            offset = form.find(master_byte, offset+1)
            if offset != -1:
                offsets.append(offset - 3)
            else:
                return offsets
        return offsets

    def vmad_reader(form, offset, master_byte): #TODO: patch script file names in plugin 
        offsets = []
        obj_format = int.from_bytes(form[offset+8:offset+10][::-1])
        script_count = int.from_bytes(form[offset+10:offset+12][::-1])
        offset += 12
        for _ in range(script_count):
            script_name_size = int.from_bytes(form[offset:offset+2][::-1])
            #script_name = form[offset+2:offset+script_name_size+2]
            offset += script_name_size + 2
            property_count = int.from_bytes(form[offset+1:offset+3][::-1])
            offset += 3
            #print(script_name)
            for _ in range(property_count):
                property_name_size = int.from_bytes(form[offset:offset+2][::-1])
                #property_name = form[offset+2: offset +property_name_size + 2]
                offset += property_name_size + 2
                object_type = int.from_bytes(form[offset:offset+1])
                offset += 2
                if object_type == 1:
                    if obj_format == 1:
                        offsets.append(offset)
                    else:
                        offsets.append(offset+4)
                    offset += 8
                elif object_type == 2:
                    string_size = int.from_bytes(form[offset:offset+2][::-1])
                    offset += string_size + 2
                elif object_type == 3:
                    offset += 4
                elif object_type == 4:
                    offset += 4
                elif object_type == 5:
                    offset += 1
                elif object_type == 11:
                    item_count = int.from_bytes(form[offset:offset+4][::-1])
                    offset += 4
                    if obj_format == 1:
                        for _ in range(item_count):
                            offsets.append(offset)
                            offset += 8
                    else:
                        for _ in range(item_count):
                            offsets.append(offset+4)
                            offset += 8
                elif object_type == 12:
                    item_count = int.from_bytes(form[offset:offset+4][::-1])
                    offset += 4
                    for _ in range(item_count):
                        string_size = int.from_bytes(form[offset:offset+2][::-1])
                        offset += string_size + 2
                elif object_type == 13:
                    item_count = int.from_bytes(form[offset:offset+4][::-1])
                    offset += 4
                    for _ in range(item_count):
                        offset += 4
                    print('type: 13\n\n\n')
                elif object_type == 14:
                    item_count = int.from_bytes(form[offset:offset+4][::-1])
                    offset += 4
                    for _ in range(item_count):
                        offset += 4
                    print('type: 14\n\n\n')
                elif object_type == 15:
                    item_count = int.from_bytes(form[offset:offset+4][::-1])
                    offset += 4
                    for _ in range(item_count):
                        offset += 1
                    print('type: 15\n\n\n')
            
        #if form[:4] in (b'INFO', b'PACK', b'PERK', b'QUST', b'SCEN'):
        #    print(f'process fragments of {form[:4]}')
        
        return offsets
    
    def get_possible_form_id_offsets(master_byte, data):
        offset = 0
        possible_form_id_offsets = []
        while True:
            offset = data.find(master_byte, offset+1)
            if offset != -1:
                possible_form_id_offsets.append(offset - 3)
            else:
                return possible_form_id_offsets
            
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
        record_types_pattern = b'|'.join(CFIDs.record_types)
        pattern = rb'(?=(?:' + record_types_pattern + rb')................[\x2C\x2B]\x00)|(?=GRUP....................)'
        data_list = [x for x in re.split(pattern, data, flags=re.DOTALL) if x]
        #data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z_]................[\x2C\x2B]\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x[:4] in CFIDs.record_types]

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

        form_id_list = []
        #Get all form ids in plugin
        for form in data_list:
            if len(form) > 24 and form[15] == master_count and form[12:16] not in form_id_list:
                form_id_list.append([form[12:16], form[:4]])

        master_byte = master_count.to_bytes()

        saved_forms = CFIDs.save_form_data(data_list, master_byte)

        data = bytearray(b'-||+||-'.join(data_list))
        
        nvpp_present = False
        if b'NVPP' in data:
            nvpp_present = True
            data, nvpp_form_ids, nvpp_start = CFIDs.save_nvpp_data(data)

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
        for old_id in form_id_list:
            if old_id in new_form_ids:
                to_remove.append(old_id)
        
        #TODO: Untested, should remove ids that already fit in the new range
        for id in to_remove:
            form_id_list.remove(id)
            new_form_ids.remove(id)

        possible_form_id_offsets = CFIDs.get_possible_form_id_offsets(master_byte, data)

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
                
        possible_form_id_offsets.reverse()

        previous_offset = len(data) + 4

        for offset in possible_form_id_offsets:
            for from_id, to_id in form_id_replacements:
                if data[offset:offset+4] == from_id and offset <= previous_offset - 4:
                    if b'DATA' in data[offset-5:offset]:
                        continue
                    if from_id[:2] == b'\x00\x00':
                        if data[offset-2:offset-1] in (b'\x2C', b'\x2B'):
                            continue
                        if master_byte not in data[offset+4:offset+6]:
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                        elif data[offset+1:offset+5] not in form_id_list and data[offset+2:offset+6] not in form_id_list:
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                    elif from_id[:1] == b'\x00' or (from_id[1:2] == b'\x00' and not bool(re.match(b'[A-Z_]', from_id[:1]))):
                        if data[offset-3:offset-2] in (b'\x2C', b'\x2B'):
                            continue
                        if master_byte not in data[offset+4:offset+6]:
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                        elif data[offset+1:offset+5] not in form_id_list and data[offset+2:offset+6] not in form_id_list:
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                    elif from_id[:2] == b'\xFF\xFF':
                        if master_byte != data[offset+4:offset+7]:
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                    elif from_id[:1] == b'\xFF':
                        if master_byte not in data[offset+4:offset+7]:
                            data[offset:offset+4] = to_id
                        previous_offset = offset
                    elif from_id[:1] == B'\x20':
                        if not re.match(b'[A-Z]{3}[A-Z_]{1}', data[offset-4:offset]):
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                    elif re.match(b'[A-Z_]', from_id[:1]):
                        if not re.match(b'[A-Z]{2}', data[offset-2:offset]):
                            data[offset:offset+4] = to_id
                            previous_offset = offset
                    else:
                        data[offset:offset+4] = to_id
                        previous_offset = offset
                    break
        
        if nvpp_present:
            data = CFIDs.fix_nvpp_data(data,nvpp_form_ids,nvpp_start,form_id_replacements)

        data = bytes(data)
        data_list = data.split(b'-||+||-')

        data_list = CFIDs.patch_form_data(data_list, saved_forms, form_id_replacements)

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
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''

        record_types_pattern = b'|'.join(CFIDs.record_types)
        pattern = rb'(?=(?:' + record_types_pattern + rb')................[\x2c\x2b]\x00)|(?=GRUP....................)'
        
        with open(form_id_file_name, 'r') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        for dependent in dependents:
            new_file = CFIDs.copy_file_to_output(dependent, skyrim_folder_path, output_folder_path)
            dependent_data = b''
            print('-    ' + os.path.basename(new_file))
            size = os.path.getsize(new_file)
            calculated_size = round(size / 1048576,2)
            print_progress = False
            if calculated_size > 40:
                print_progress = True
                print(f'-    Size is {calculated_size} MBs which will take a longer time to patch.')
                print(f'-    This program uses a dumb method that is slower than xEdit.')

            with open(new_file, 'rb+') as dependent_file:
                #Update header to 1.71 to fit new records
                if update_header:
                    dependent_file.seek(0)
                    dependent_file.seek(30)
                    dependent_file.write(b'\x48\xE1\xDA\x3F')
                    dependent_file.seek(0)

                dependent_data = dependent_file.read()
                
                data_list = [x for x in re.split(pattern, dependent_data, flags=re.DOTALL) if x]
                
                offsets = []
                current_offset = 0
                for chunk in data_list:
                    offsets.append(current_offset)
                    current_offset += len(chunk)

                master_count = data_list[0].count(b'MAST')
                data_list, sizes_list = CFIDs.decompress_data(data_list, master_count)
                
                grup_hierarchy = CFIDs.parse_grups(dependent_data)

                land_present = False
                for form in data_list:
                    if b'LAND' == form[:4] or (form[:4] == b'GRUP' and len(form) > 24 and form[24:28] == b'LAND'):
                        land_present = True
                        break

                if land_present:
                    data_list, land_forms = CFIDs.get_land_data(data_list)

                dependent_data = bytearray(b'-||+||-'.join(data_list))

                nvpp_present = False
                if b'NVPP' in dependent_data:
                    nvpp_present = True
                    dependent_data, nvpp_form_ids, nvpp_start = CFIDs.save_nvpp_data(dependent_data)

                master_index = CFIDs.get_master_index(file, dependent_data)
                
                form_id_replacements = []
                loop = 0

                master_byte = master_index.to_bytes()
                possible_form_id_offsets = CFIDs.get_possible_form_id_offsets(master_byte, dependent_data)

                for i in range(len(form_id_file_data)):
                    form_id_conversion = form_id_file_data[i].split('|')
                    from_id = bytes.fromhex(form_id_conversion[0])[:3] + master_byte
                    to_id = bytes.fromhex(form_id_conversion[1])[:3] + master_byte
                    form_id_replacements.append([from_id, to_id])

                form_id_list = [id for id, _ in form_id_replacements]

                previous_offset = len(dependent_data) + 4

                possible_form_id_offsets.reverse()

                for i in range(len(possible_form_id_offsets)):
                    offset = possible_form_id_offsets[i]
                    for from_id, to_id in form_id_replacements:
                        if loop == 5000 and print_progress:
                            loop = 0
                            percent = round((i / len(possible_form_id_offsets)) * 100,2)
                            print(f'-     Progress: {percent}%', end='\r')
                        elif print_progress:
                            loop +=1
                        if dependent_data[offset:offset+4] == from_id and offset < previous_offset - 4:
                            if b'DATA' in dependent_data[offset-5:offset]:
                                continue
                            if from_id[:2] == b'\x00\x00':
                                if dependent_data[offset-2:offset-1] in (b'\x2C', b'\x2B'):
                                    continue
                                if master_byte not in dependent_data[offset+4:offset+6]:
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                                elif dependent_data[offset+1:offset+5] not in form_id_list and dependent_data[offset+2:offset+6] not in form_id_list:
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                            elif from_id[:1] == b'\x00' or (from_id[1:2] == b'\x00' and not bool(re.match(b'[A-Z_]', from_id[:1]))):
                                if dependent_data[offset-3:offset-2] in (b'\x2C', b'\x2B'):
                                    continue
                                if master_byte not in dependent_data[offset+4:offset+6]:
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                                elif dependent_data[offset+1:offset+5] not in form_id_list and dependent_data[offset+2:offset+6] not in form_id_list:
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                            elif from_id[:2] == b'\xFF\xFF':
                                if master_byte != dependent_data[offset+4:offset+7]:
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                            elif from_id[:1] == b'\xFF':
                                if master_byte not in dependent_data[offset+4:offset+7]:
                                    dependent_data[offset:offset+4] = to_id
                                previous_offset = offset
                            elif from_id[:1] == B'\x20':
                                if not re.match(b'[A-Z]{3}[A-Z_]{1}', dependent_data[offset-4:offset]):
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                            elif re.match(b'[A-Z_]', from_id[:1]):
                                if not re.match(b'[A-Z]{2}', dependent_data[offset-2:offset]):
                                    dependent_data[offset:offset+4] = to_id
                                    previous_offset = offset
                            else:
                                dependent_data[offset:offset+4] = to_id
                                previous_offset = offset
                            break
                        
                dependent_data = bytes(dependent_data)
                
                if nvpp_present:
                    dependent_data = CFIDs.fix_nvpp_data(dependent_data,nvpp_form_ids,nvpp_start,form_id_replacements)

                data_list = dependent_data.split(b'-||+||-')

                if land_present:
                    data_list = CFIDs.patch_land_data(data_list, land_forms, form_id_replacements)

                data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list, master_count)

                # Update GRUP sizes recursively
                for top_grup in grup_hierarchy:
                    CFIDs.update_grup_sizes(top_grup, sizes_list, offsets)
                
                updated_data = CFIDs.reassemble_data(grup_hierarchy, data_list, offsets)

                dependent_file.seek(0)
                dependent_file.write(updated_data)
                dependent_file.close()

            CFIDs.compacted_and_patched[os.path.basename(file)].append(dependent)
            CFIDs.compacted_and_patched[os.path.basename(file)].append(new_file)
        return

    #gets what master index the file is in inside of the dependent's data
    def get_master_index(file, data):
        master_pattern = re.compile(b'MAST..(.*?).DATA', flags=re.DOTALL)
        matches = re.findall(master_pattern, data)
        master_index = 0
        for match in matches:
            if os.path.basename(file).lower() in str(match).lower():
                return master_index
            else:
                master_index += 1