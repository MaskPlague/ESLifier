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
        CFIDs.compact_file(file_to_compact, skyrim_folder_path, output_folder_path, update_header)

        CFIDs.correct_dependents(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header)
        
        files_to_patch = CFIDs.get_from_file('ESLifier_Data/file_masters.json')
        to_patch, to_rename = CFIDs.get_files_to_correct(file_to_compact, files_to_patch[os.path.basename(file_to_compact).lower()]) #function to get files that need to be edited in some way to function correctly.
        form_id_map = CFIDs.get_form_id_map(file_to_compact)
        CFIDs.patch_files_threader(file_to_compact, to_patch, form_id_map, skyrim_folder_path, output_folder_path, True)
        CFIDs.rename_files_threader(file_to_compact, to_rename, form_id_map, skyrim_folder_path, output_folder_path)
        CFIDs.dump_to_file('ESLifier_Data/compacted_and_patched.json')
        return
        #TODO: Add threading
        #TODO: Create setting to change output folder name, with a notification that it requires to reset output
        
        #TODO: update next object in TES4 header?
        #TODO: SkyPatcher, MCM Helper, possible others to check
        #TODO: add regex to certain replacements in patch files for safety
        #TODO: make 1.71 header change optional + setting for starting from 0 or 0x800 (I think it is 0x800)
        #TODO: When compacting multiple masters, there is a chance that a file (an ini for example) may need to be patched twice for two different masters
            # and I need to make sure that the file is NOT overwritten by the original from the SSE folder as that would diregard prior changes.
            # this means that the output folder will need to be emptied and patched every time or an option...
        #TODO: Far in the future, consider actively scanning files for previous compacted files. Maybe a UI option to do a scan or directly select relevant folder/files.
    
    def dump_to_file(file):
        try:
            data = CFIDs.get_from_file(file)
        except:
            data = {}
        for key, value in CFIDs.compacted_and_patched.items():
            if key.lower() not in data.keys():
                data[key.lower()] = []
            for item in value:
                if item not in data[key.lower()]:
                    data[key.lower()].append(item)

        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_from_file(file):
        data = {}
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    
    def set_flag(file, output_folder):
        new_file = CFIDs.copy_file_to_output(file, output_folder)
        with open(new_file, 'rb+') as f:
            f.seek(9)
            f.write(b'\x02')

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
    def get_files_to_correct(master, files):
        #hexaPattern = re.compile(r'([0-9a-fA-F]+){6,}[.](?!p)')
        files_to_patch = []
        files_to_rename = []
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '_srd.', os.path.splitext(os.path.basename(master))[0].lower() + '.seq']
        for file in files:
            if any(match in file.lower() for match in matchers):
                #if CFIDs.scan_file(master, file):
                files_to_patch.append(file)
            elif os.path.basename(master).lower() in file.lower() and ('facegeom' in file.lower() or 'voice' in file.lower() or 'facetint' in file.lower()):
                files_to_rename.append(file)
        return files_to_patch, files_to_rename
    
    @DeprecationWarning
    #Check any given file for certain specific features that would mean it does need patching
    def scan_file(master, file):
        formIdPattern0x = re.compile(r'0x([0-9a-fA-F]+){1,}')
        formIdPatternPipe = re.compile((r'\|([0-9a-fA-F]+){1,}'))
        if '.seq' in file:
            return True
        if not '.pex' in file.lower():
            with open(file, 'r', encoding='utf-8') as f:
                data = f.readlines()
                #if 'config.json' in file.lower():
                #    for line in data:
                #        if 'formid' in line.lower():
                #            return True
                #    return False
                if '.ini' in file.lower() or '_conditions.txt' in file.lower() or '.json' in file.lower(): #PO3's mods, DAR, OAR, MCM helper
                    return True
                    for line in data:
                        s = re.search(formIdPattern0x, line.lower()) #for 0x form ids
                        s2 = re.search(formIdPatternPipe, line.lower()) #for some_mod.esp|form ids
                        if s and os.path.basename(master).lower() in line.lower(): #PO3's mods
                            return True
                        elif 'formid' in line.lower() or ('form_id' in line.lower() and os.path.basename(master).lower() in line.lower()): #OAR and 
                            return True
                        elif s2 and os.path.basename(master).lower() in line.lower(): #MCM helper
                            return True
                    return False
                if  '_srd.' in file.lower(): #Sound Record Distributor
                    for line in data:
                        s = re.search(formIdPatternPipe, line.lower())
                        if s and os.path.basename(master).lower() in line.lower():
                            return True
                    return False
                if '.psc' in file.lower(): #Papyrus Script Sources
                    for line in data:
                        if 'getformfromfile(' in line.lower():
                            return True
                f.close()
        elif '.pex' in file.lower(): #Papyrus Script compiled
            with open(file, 'rb') as f:
                data = f.read()
                if b'getformfromfile' in data.lower():
                    data_list = re.split(b'getformfromfile',data.lower())
                    for dataChunk in data_list:
                        if os.path.basename(master.lower()) in str(re.findall(b'..(.*?)\x00', dataChunk)[0].lower()):
                            return True
                f.close()
        return False

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
        
        for chunk in chunks:
            thread = threading.Thread(target=CFIDs.rename_files, args=(master, chunk, form_id_map, skyrim_folder_path, output_folder_path))
            threads.append(thread)
            thread.start()
        
        for thread in threads: thread.join()
    #Rename each file in the list of files from the old Form IDs to the new Form IDs
    def rename_files(master, files, form_id_map, skyrim_folder_path, output_folder_path):
        facegeom_meshes = []
        for file in files:
            for form_ids in form_id_map:
                if form_ids[1].upper() in file.upper():
                    with CFIDs.lock:
                        new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
                        os.replace(new_file, new_file.replace(form_ids[1].upper(), form_ids[3].upper()))
                        CFIDs.compacted_and_patched[os.path.basename(master).lower()].append(file)
                        CFIDs.compacted_and_patched[os.path.basename(master).lower()].append(new_file)
                        if 'facegeom' in new_file.lower() and os.path.basename(master).lower() in new_file.lower():
                            facegeom_meshes.append(new_file.replace(form_ids[1].upper(), form_ids[3].upper()))
        if facegeom_meshes != []:
            CFIDs.patch_files(master, facegeom_meshes, form_id_map, skyrim_folder_path, output_folder_path, False)
        print('Files Renamed')
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

    def patch_files_threader(master, files, formIdMap, skyrim_folder_path, output_folder_path, flag):
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
            thread = threading.Thread(target=CFIDs.patch_files, args=(master, chunk, formIdMap, skyrim_folder_path, output_folder_path, flag))
            threads.append(thread)
            thread.start()
        
        for thread in threads: thread.join()

    #Patches each file type in a different way as each has Form IDs present in a different format
    def patch_files(master, files, formIdMap, skyrim_folder_path, output_folder_path, flag):
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
                                    for formIds in formIdMap:
                                        #this is faster than re.sub by a lot ;_;
                                        line = line.replace('0x' + formIds[0], '0x' + formIds[2]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x' + formIds[0].lower(), '0x' + formIds[2].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X' + formIds[0], '0X' + formIds[2]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X' + formIds[0].lower(), '0X' + formIds[2].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                                print(line.strip('\n'))
                        elif 'config.json' in new_file.lower(): #Open Animation Replacer Patching and MCM helper
                            #TODO: Redo this to look for plugin name on preceeding line (use for i in range()) for OAR
                            # Also add MCM helper structure, use regex so that if a mod somehow has form id "F" or "D" that
                            # gets compacted to something else, it won't break the json formatting i.e. "formid" -> "3ormi2" or "form:" -> "3orm"
                            for line in f:
                                if 'formid' in line.lower():
                                    for formIds in formIdMap:
                                        line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                                print(line.strip('\n'))
                        elif '_conditions.txt' in new_file.lower(): #Dynamic Animation Replacer Patching
                            for line in f:
                                for formIds in formIdMap:
                                    line = line.replace('0x00' + formIds[1], '0x00' + formIds[3]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x00' + formIds[1].lower(), '0x00' + formIds[3].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X00' + formIds[1], '0X00' + formIds[3]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X00' + formIds[1].lower(), '0X00' + formIds[3].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                                print(line.strip('\n'))
                        elif '_SRD.' in new_file.lower(): #Sound record distributor patching
                            #TODO: check if regex is necessary
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for formIds in formIdMap:
                                        line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                                print(line.strip('\n'))
                        elif '.psc' in new_file.lower(): #Script source file patching
                            for line in f:
                                if os.path.basename(master).lower() in line.lower() and 'getformfromfile' in line.lower():
                                    for formIds in formIdMap:
                                        line = line.replace('0x' + formIds[0], '0x' + formIds[2]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x' + formIds[0].lower(), '0x' + formIds[2].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X' + formIds[0], '0X' + formIds[2]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X' + formIds[0].lower(), '0X' + formIds[2].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                                print(line.strip('\n'))
                        elif '.json' in new_file.lower(): #Dynamic Key Activation Framework NG, Smart Harvest Auto NG AutoLoot and whatever else may be using .json?
                            #TODO: check for other json mods
                            prev_line = ''
                            for line in f:
                                if os.path.basename(master).lower() in line.lower():
                                    for formIds in formIdMap:
                                        line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                                elif 'plugin' in prev_line.lower() and os.path.basename(master).lower() in prev_line.lower(): #Smart Harvest
                                    if 'form' in line.lower():
                                        for formIds in formIdMap:
                                            line = line.replace(formIds[1], formIds[3]).replace(formIds[0], formIds[2]).replace(formIds[1].lower(), formIds[3].lower()).replace(formIds[0].lower(), formIds[2].lower())
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
                                    for formIds in formIdMap:
                                        data[i] = data[i].replace(formIds[1].encode(), formIds[3].encode()).replace(formIds[1].encode().lower(), formIds[3].encode().lower())
                            f.seek(0)
                            f.writelines(data)

            elif '.seq' in new_file or '.pex' in new_file.lower():
                with CFIDs.lock:
                    with open(new_file,'rb+') as f:
                        data = f.read()
                        if '.seq' in new_file: #SEQ file patching
                            for formIds in formIdMap:
                                data = data.replace(formIds[4], formIds[5])
                            f.seek(0)
                            f.write(data)
                        elif '.pex' in new_file: #Compiled script patching
                            #TODO: replace with regex, check for b'\x03\x00\x ?? \xFORM ID
                            #      03 should be saying that this is an integer 00 is spacing since it is a form id without master byte and following bytes are big endian form id i.e 0x800 without 0x
                            for formIds in formIdMap:
                                data = data.replace(formIds[4][::-1][1:], formIds[5][::-1][1:])
                            f.seek(0)
                            f.write(data)
                        f.close()
            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(master).lower()].append(file)
        print("Files Patched")

    #Compacts master file and returns the new mod folder
    def compact_file(file, skyrim_folder_path, output_folder, update_header):
        form_id_file_name = 'ESLifier_Data/Form_ID_Maps/' + os.path.basename(file).lower() + "_FormIdMap.txt"
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

        #print('initial data size:           ' + str(len(data)))
        data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................\x2c\x00.\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]

        master_count = data_list[0].count(b'MAST')
        form_id_list = []

        if master_count <= 15:
            mC = '0' + str(master_count)
        else:
            mC = str(master_count)

        if update_header:
            new_id = binascii.unhexlify(mC + '000000')
        else:
            new_id = binascii.unhexlify(mC + '000800')
        new_id_len = len(new_id)
        counter = int.from_bytes(new_id, 'big')
        sizes_list = [[]] * len(data_list)

        #Decompress any compressed form ids in the plugin
        for i in range(len(data_list)):
            #flag for compressed forms is at byte 10 and is b'04'
            if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                size = int.from_bytes(data_list[i][4:8][::-1])
                #Decompress the compressed form
                decompressed = zlib.decompress(data_list[i][28:size + 24]) #24 is the size of the form header in every kind except GRUP
                sizes_list[i] = [len(data_list[i]), len(decompressed), size]
                new_form = data_list[i].replace(data_list[i][28:size+24], decompressed)

                #get the form ids that were hiding in compressed data
                new_forms = re.split(b'(?=....................\x2c\x00.\x00)', new_form, flags=re.DOTALL)
                if len(new_forms) > 0:
                    for form in new_forms:
                        if form != b'' and len(form) > 16 and form[15] == master_count and form[12:16] not in form_id_list:
                            form_id_list.append(form[12:16])

                data_list[i] = new_form
        
        #recreate data from data that has been altered when decompressed, but with an identifier of the previous split
        data = b'-||+||-'.join(data_list)

        #Get all other form ids in plugin
        for form in data_list:
            if len(form) > 24 and form[15] == master_count and form[12:16] not in form_id_list:
                form_id_list.append(form[12:16])
        

        form_id_list.sort()

        #Replace current Form IDs with the new Form IDs
        with open(form_id_file_name, 'w') as form_id_file:
            #print('decompacted size before:     ' + str(len(data)))
            for form_id in form_id_list:
                new_id = counter.to_bytes(new_id_len, 'little')
                #print("From: " + str(formId.hex()) + " to -> " + str(newId.hex()))
                counter += 1
                form_id_file.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')

                if form_id[:2] != b'\xFF\xFF':
                    data = data.replace(form_id, new_id)
                else: #Prevent issues with replacing VMAD info with its \xFF\xFF structure
                    data = re.sub(re.escape(form_id) + b'(?!.' + int.to_bytes(master_count) + b')', new_id, data, flags=re.DOTALL)

                #'''#Extemely slow and missing \xFF\xFF that is above
                #newIdReplacement1 = newId + bytes(r"\g<2>", 'utf-8')
                #newIdReplacement2 = bytes(r"\g<1>", 'utf-8') + newId + bytes(r"\g<3>", 'utf-8')
                #newIdReplacement3 = bytes(r"\g<1>", 'utf-8') + newId
                '''pattern1 = re.compile(b'(' + re.escape(formId) + b')(....\x2c[\x00-\x7F]{4})') #form id in non grup, form header replacement
                pattern2 = re.compile(b'(\x04\x00)(' + re.escape(formId) + b')([\x00-\x7F]{4}\x2c)') #form id in
                pattern3 = re.compile(b'(GRUP....)(' + re.escape(formId) + b')') #change form ids in grup header
                pattern4 = re.compile(b'(' + re.escape(formId) + b')([A-Z]{4})')
                pattern5 = re.compile(b'([A-Z]{4}..............)(' + re.escape(formId) + b')(...\x00)')
                #print(re.search(pattern3, data))
                data = re.sub(pattern1, newIdReplacement1, data)
                data = re.sub(pattern2, newIdReplacement2, data)
                data = re.sub(pattern3, newIdReplacement3, data)
                data = re.sub(pattern4, newIdReplacement1, data)
                data = re.sub(pattern5, newIdReplacement2, data)'''

            #print('decompacted size after:      ' + str(len(data)))

        data_list = data.split(b'-||+||-')

        for i in range(len(data_list)):
            if len(data_list[i]) > 16 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count): #and data_list[i][15] == masterCount and data_list[i][10] == 0x4:
                #compressed = zlib.compress(data_list[i][28:sizesList[i][2] + 24])
                compressed = zlib.compress(data_list[i][28:len(data_list[i])-1], 9)
                formatted = [0] * (sizes_list[i][0] - 28)
                formatted[:28] = data_list[i][:28]
                formatted[28:len(compressed)] = compressed
                data_list[i] = bytes(formatted)

        data = b''.join(data_list)
        #print('final data size:             ' + str(len(data)))

        with open(new_file, 'wb') as f:
            f.write(data)
            f.close()

        CFIDs.compacted_and_patched[os.path.basename(new_file).lower()] = []
        #print('file compacted')
        

    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def correct_dependents(file, dependents, skyrim_folder_path, output_folder_path, update_header):
        form_if_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        with open(form_if_file_name, 'r') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        for dependent in dependents:
            #TODO: consider if a dependent has compressed forms... please no
            new_file = CFIDs.copy_file_to_output(dependent, skyrim_folder_path, output_folder_path)
            dependent_data = b''
            with open(new_file, 'rb+') as dependent_file:
                #Update header to 1.71 to fit new records
                if update_header:
                    dependent_file.seek(0)
                    dependent_file.seek(30)
                    dependent_file.write(b'\x48\xE1\xDA\x3F')
                    dependent_file.seek(0)

                dependent_data = dependent_file.read()
                #print('initial data size:           ' + str(len(dependentData)))
                data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................\x2c\x00.\x00)|(?=GRUP....................)', dependent_data, flags=re.DOTALL) if x]
                
                master_count = data_list[0].count(b'MAST')
                sizes_list = [[]] * len(data_list)
                for i in range(len(data_list)):
                    #flag for compressed forms is at byte 10 and is b'04'
                    if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_count):
                        size = int.from_bytes(data_list[i][4:8][::-1])
                        #Decompress the compressed form
                        decompressed = zlib.decompress(data_list[i][28:size + 24]) #24 is the size of the form header in every kind except GRUP
                        sizes_list[i] = [len(data_list[i]), len(decompressed), size]
                        newForm = data_list[i].replace(data_list[i][28:size+24], decompressed)
                        data_list[i] = newForm
                
                dependent_data = b'-||+||-'.join(data_list)

                master_leading_byte = CFIDs.get_master_index(file, dependent_data)
                if master_leading_byte <= 15:
                    mC = '0' + str(master_leading_byte)
                else:
                    mC = str(master_leading_byte)
                for form_id_history in form_id_file_data:
                    form_id_conversion = form_id_history.split('|')
                    from_id = bytes.fromhex(form_id_conversion[0])[:3] + bytes.fromhex(mC)
                    to_id = bytes.fromhex(form_id_conversion[1])[:3] + bytes.fromhex(mC)
                    if from_id[:2] != b'\xFF\xFF':
                        dependent_data = dependent_data.replace(from_id, to_id)
                    else: #Prevent issues with replacing VMAD info with its \xFF\xFF structure
                        dependent_data = re.sub(re.escape(from_id) + b'(?!.' + int.to_bytes(master_leading_byte) + b')', to_id, dependent_data, flags=re.DOTALL)

                data_list = dependent_data.split(b'-||+||-')

                for i in range(len(data_list)):
                    if len(data_list[i]) > 24 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= master_leading_byte): #and data_list[i][15] == masterCount and data_list[i][10] == 0x4:
                        #compressed = zlib.compress(data_list[i][28:sizesList[i][2] + 24])
                        compressed = zlib.compress(data_list[i][28:len(data_list[i])-1], 9)
                        formatted = [0] * (sizes_list[i][0] - 28)
                        formatted[:28] = data_list[i][:28]
                        formatted[28:len(compressed)] = compressed
                        data_list[i] = bytes(formatted)

                dependent_data = b''.join(data_list)
                #print('final data size:             ' + str(len(dependentData)))
                dependent_file.seek(0)
                dependent_file.write(dependent_data)
                dependent_file.close()

            CFIDs.compacted_and_patched[os.path.basename(file).lower()].append(dependent)
        
        #print('Dependents patched')
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