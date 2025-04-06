import os
import binascii
import shutil
import zlib
import json
import threading
import subprocess
import struct
from file_patchers import patchers
from intervaltree import IntervalTree

class CFIDs():
    def compact_and_patch(form_processor, file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header, mo2_mode, bsab):
        CFIDs.lock = threading.Lock()
        CFIDs.compacted_and_patched = {}
        CFIDs.mo2_mode = mo2_mode
        CFIDs.form_processor = form_processor
        print(f"Compacting Plugin: {os.path.basename(file_to_compact)}...")
        CFIDs.compact_file(file_to_compact, skyrim_folder_path, output_folder_path, update_header)
        files_to_patch = CFIDs.get_from_file('ESLifier_Data/file_masters.json')
        if dependents != []:
            print(f"-  Patching {len(dependents)} Dependent Plugins...")
            CFIDs.patch_dependent_plugins(file_to_compact, dependents, skyrim_folder_path, output_folder_path, update_header, files_to_patch)
        
        bsa_dict = CFIDs.get_from_file('ESLifier_Data/bsa_dict.json')
        name = os.path.basename(file_to_compact).lower()
        bsa_masters = []
        for value in bsa_dict.values():
            bsa_masters.extend(value)
        if name in files_to_patch or name in bsa_masters:
            patch_or_rename = []
            if name in files_to_patch:
                patch_or_rename = files_to_patch[os.path.basename(file_to_compact).lower()]

            if name in bsa_masters:
                print('-  Temporarily Extracting FaceGen/Voice files from BSA for patching...')
                if not os.path.exists('bsa_extracted_temp/'):
                    os.makedirs('bsa_extracted_temp/')
                else:
                    shutil.rmtree('bsa_extracted_temp/')
                    os.makedirs('bsa_extracted_temp/')
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                for bsa_file, values in bsa_dict.items():
                    if name in values:
                        try:
                            try:
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf8", "-f", "\\voice\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-8 failed switching to utf-7 for {file}')
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf8", "-f", "\\facetint\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-8 failed switching to utf-7 for {file}')
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf8", "-f", "\\facegeom\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-8 failed switching to utf-7 for {file}')
                            except Exception as e:
                                print(e)
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf7", "-f", "\\voice\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-7 failed for {file}')
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf7", "-f", "\\facetint\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-7 failed for {file}')
                                with subprocess.Popen(
                                    [bsab, bsa_file, "--encoding", "utf7", "-f", "\\facegeom\\" + name, "-e", "-o", "bsa_extracted_temp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=startupinfo,
                                    text=True
                                    ) as p:
                                        for line in p.stdout:
                                            if line.startswith('An error'):
                                                raise EncodingWarning(f'~utf-7 failed for {file}')
                        except Exception as e:
                            print(f'!Error Reading BSA: {file}')
                            print(e)
                                            
                rel_paths = []
                for file in patch_or_rename:
                    rel_path = CFIDs.get_rel_path(file, skyrim_folder_path)
                    rel_paths.append(rel_path.lower())

                start = os.path.join(os.getcwd(), 'bsa_extracted_temp')
                for root, dir, files in os.walk('bsa_extracted_temp/'):
                    for file in files:
                        full_path = os.path.normpath(os.path.join(root, file))
                        rel_path = os.path.relpath(full_path, start).lower()
                        if rel_path not in rel_paths and file.endswith(('.nif', '.dds', '.fuz', '.xwm', '.wav', '.lip')):
                            patch_or_rename.append(full_path)
                            rel_paths.append(rel_path)
                
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(file_to_compact, patch_or_rename) #function to get files that need to be edited in some way to function correctly.
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
        if os.path.exists('bsa_extracted_temp/'):
            print('-  Deleting temporarily Extracted FaceGen/Voice Files...')
            shutil.rmtree('bsa_extracted_temp/')
        print('CLEAR ALT')
        return
    
    def dump_to_file(file):
        try:
            data = CFIDs.get_from_file(file)
        except:
            data = {}
        for key, value in CFIDs.compacted_and_patched.items():
            if key not in data:
                data[key] = []
            for item in value:
                if item.lower() not in data[key]:
                    data[key].append(item.lower())
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print('!Error: Failed to dump data to {file}')
            print(e)

    def get_from_file(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data
    
    def set_flag(file, skyrim_folder, output_folder, mo2_mode):
        CFIDs.mo2_mode = mo2_mode
        CFIDs.lock = threading.Lock()
        print("-  Changing ESL flag in: " + os.path.basename(file))
        new_file, _ = CFIDs.copy_file_to_output(file, skyrim_folder, output_folder)
        try:
            with open(new_file, 'rb+') as f:
                f.seek(9)
                f.write(b'\x02')
        except Exception as e:
            print('!Error: Failed to set ESL flag in {file}')
            print(e)            

    def patch_new(form_processor, compacted_file, dependents, files_to_patch, skyrim_folder_path, output_folder_path, update_header, mo2_mode):
        CFIDs.lock = threading.Lock()
        CFIDs.form_processor = form_processor
        CFIDs.compacted_and_patched = {}
        CFIDs.mo2_mode = mo2_mode
        print('Patching new plugins and files for ' + compacted_file + '...')
        CFIDs.compacted_and_patched[compacted_file] = []
        if dependents != []:
            print("-  Patching New Dependent Plugins...")
            CFIDs.patch_dependent_plugins(compacted_file, dependents, skyrim_folder_path, output_folder_path, update_header, files_to_patch)
        if os.path.basename(compacted_file) in files_to_patch:
            to_patch, to_rename = CFIDs.sort_files_to_patch_or_rename(compacted_file, files_to_patch[os.path.basename(compacted_file)])
            form_id_map = CFIDs.get_form_id_map(compacted_file)
            if len(to_patch) > 0:
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
        if 'bsa_extracted' in file:
            if 'bsa_extracted_temp' in file:
                start = os.path.join(os.getcwd(), 'bsa_extracted_temp/')
            else:
                start = os.path.join(os.getcwd(), 'bsa_extracted/')
            end_path = os.path.normpath(os.path.relpath(file, start))
        elif CFIDs.mo2_mode and '\\overwrite\\' in file:
            overwrite_path = os.path.join(os.path.split(skyrim_folder_path)[0], 'overwrite')
            end_path = os.path.normpath(os.path.relpath(file, overwrite_path))
        else:
            if CFIDs.mo2_mode:
                end_path = os.path.join(*os.path.normpath(os.path.relpath(file, skyrim_folder_path)).split(os.sep)[1:])
            else:
                end_path = os.path.normpath(os.path.relpath(file, skyrim_folder_path))
        new_file = os.path.normpath(os.path.join(os.path.join(output_folder,'ESLifier Compactor Output'), end_path))
        with CFIDs.lock:
            if not os.path.exists(os.path.dirname(new_file)):
                os.makedirs(os.path.dirname(new_file))
            if not os.path.exists(new_file):
                shutil.copy(file, new_file)
        return new_file, end_path
    
    def get_rel_path(file, skyrim_folder_path):
        if 'bsa_extracted' in file:
            if 'bsa_extracted_temp' in file:
                start = os.path.join(os.getcwd(), 'bsa_extracted_temp/')
            else:
                start = os.path.join(os.getcwd(), 'bsa_extracted/')
            rel_path = os.path.normpath(os.path.relpath(file, start))
        else:
            if CFIDs.mo2_mode:
                rel_path = os.path.join(*os.path.normpath(os.path.relpath(file, skyrim_folder_path)).split(os.sep)[1:])
            else:
                rel_path = os.path.normpath(os.path.relpath(file, skyrim_folder_path))
        return rel_path
    
    #Sort the file masters list into files that only need patching and files that need renaming and maybe patching
    def sort_files_to_patch_or_rename(master, files):
        files_to_patch = []
        files_to_rename = []
        split_name = os.path.splitext(os.path.basename(master))[0].lower()
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '.jslot', '_srd.',
                    split_name + '.seq', '.toml', 'netscriptframework\\plugins\\customskill']
        for file in files:
            file_lower = file.lower()
            if any(match in file_lower for match in matchers):
                files_to_patch.append(file)
            elif os.path.basename(master).lower() in file_lower and ('facegeom' in file_lower or 'voice' in file_lower or 'facetint' in file_lower):
                files_to_rename.append(file)
            else:
                raise TypeError(f"{os.path.basename(master).lower()} - File: {file} \nhas no patching method but it is in file_masters...")
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
            
            rel_path = CFIDs.get_rel_path(file, skyrim_folder_path)
            for form_ids in form_id_map:
                if form_ids[1].lower() in file.lower():
                    new_file, rel_path_new_file = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
                    index = new_file.lower().index(form_ids[1].lower())
                    renamed_file = new_file[:index] + form_ids[3].upper() + new_file[index+6:]
                    with CFIDs.lock:
                        os.replace(new_file, renamed_file)
                    index = rel_path_new_file.lower().index(form_ids[1].lower())
                    rel_path_renamed_file = rel_path_new_file[:index] + form_ids[3].upper() + rel_path_new_file[index+6:]
                    with CFIDs.lock:
                        if rel_path_new_file not in CFIDs.compacted_and_patched[master_base_name]:
                            CFIDs.compacted_and_patched[master_base_name].append(rel_path_new_file)
                        if rel_path_renamed_file not in CFIDs.compacted_and_patched[master_base_name]:
                            CFIDs.compacted_and_patched[master_base_name].append(rel_path_renamed_file)
                        if 'facegeom' in new_file.lower() and master_base_name.lower() in new_file.lower():
                            facegeom_meshes.append(renamed_file)
                    break
            CFIDs.compacted_and_patched[master_base_name].append(rel_path.lower())
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

            from_id = bytes.fromhex(form_id_conversion[0])[::-1].hex()[2:].lstrip('0').upper()
            from_id_with_leading_0s = bytes.fromhex(form_id_conversion[0])[::-1].hex()[2:].upper()
            to_id = bytes.fromhex(form_id_conversion[1])[::-1].hex()[2:].lstrip('0').upper()
            if to_id == '': to_id = '0'
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
    def patch_files(master, files, form_id_map, skyrim_folder_path, output_folder_path, flag):
        for file in files:
            if flag:
                new_file, rel_path = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder_path)
            else:
                rel_path = CFIDs.get_rel_path(file, output_folder_path)
                new_file = file
            new_file_lower = new_file.lower()
            basename = os.path.basename(master).lower()
            try:
                with CFIDs.lock:
                    if new_file_lower.endswith('.ini'):
                        if new_file_lower.endswith(('_distr.ini', '_kid.ini', '_swap.ini', '_enbl.ini',     # PO3's SPID, KID, BOS, ENBL
                                                    '_desc.ini', '_flm.ini', '_llos.ini', '_ipm.ini', '_mus.ini ')): # Description Framework, FLM, LLOS, IPM, MTD
                            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map)
                        elif 'seasons\\' in new_file_lower:                                                 # Po3's Seasons of Skyrim
                            patchers.ini_season_patcher(basename, new_file, form_id_map)
                        elif 'payloadinterpreter\\' in new_file_lower:                                      # Payload Interpreter
                            patchers.ini_pi_dtry_patcher(basename, new_file, form_id_map)
                        elif 'dtrykeyutil\\' in new_file_lower:                                             # DtryKeyUtil
                            patchers.ini_pi_dtry_patcher(basename, new_file, form_id_map)
                        elif 'muimpactframework\\' in new_file_lower or 'muskeletoneditor\\' in new_file_lower: # MU
                            patchers.ini_mu_patcher(basename, new_file, form_id_map)
                        elif '\\poisebreaker' in new_file_lower:                                            # Poise Breaker
                            patchers.ini_pb_patcher(basename, new_file, form_id_map)
                        elif 'skypatcher\\' in new_file_lower:                                              # Sky Patcher
                            patchers.ini_sp_patcher(basename, new_file, form_id_map)
                        elif 'valhallacombat\\' in new_file_lower:                                          # Valhalla Combat
                            patchers.ini_vc_patcher(basename, new_file, form_id_map)
                        elif '\\autobody\\' in new_file_lower:                                              # AutoBody
                            patchers.ini_ab_patcher(basename, new_file, form_id_map)
                        elif 'vsu\\' in new_file_lower:                                                     # VSU
                            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map)
                        elif 'completionistdata\\' in new_file_lower:                                       # Completionist
                            patchers.ini_completionist_patcher(basename, new_file, form_id_map)
                        elif 'kreate\\presets' in new_file_lower:                                           # KreatE
                            patchers.ini_kreate_patcher(basename, new_file, form_id_map)
                        elif new_file_lower.endswith('thenewgentleman.ini'):                                # The New Gentleman
                            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map)
                        else:                                                                               # Might patch whatever else is using .ini?
                            print(f'Warn: Possible missing patcher for: {new_file}')
                    elif new_file_lower.endswith('_conditions.txt'):                                        # Dynamic Animation Replacer
                        patchers.dar_patcher(basename, new_file, form_id_map)
                    elif new_file_lower.endswith('.json'):
                        if 'animationreplacer\\' in new_file_lower and ('config.json' in new_file_lower or 'user.json' in new_file_lower): # Open Animation Replacer
                            patchers.json_oar_patcher(basename, new_file, form_id_map)
                        elif 'mcm\\config' in new_file_lower and 'config.json' in new_file_lower:           # MCM helper
                            patchers.json_generic_plugin_pipe_formid_patcher(basename, new_file, form_id_map)
                        elif '\\storageutildata\\' in new_file_lower:                                       # PapyrusUtil's StorageDataUtil
                            patchers.json_sud_patcher(basename, new_file, form_id_map)
                        elif '\\dynamicstringdistributor\\' in new_file_lower:                              # Dynamic String Distributor
                            patchers.json_dsd_patcher(basename, new_file, form_id_map)
                        elif '\\dkaf\\' in new_file_lower:                                                  # Dynamic Key Activation Framework NG
                            patchers.json_dkaf_patcher(basename, new_file, form_id_map)
                        elif '\\dynamicarmorvariants\\' in new_file_lower:                                  # Dynamic Armor Variants
                            patchers.json_dav_patcher(basename, new_file, form_id_map)
                        elif '\\ied\\' in new_file_lower:                                                   # Immersive Equipment Display
                            patchers.json_ied_patcher(basename, new_file, form_id_map)
                        elif '\\lightplacer\\' in new_file_lower:                                           # Light Placer
                            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map)
                        elif '\\creatures.d\\' in new_file_lower:                                           # Creature Framework
                            patchers.json_cf_patcher(basename, new_file, form_id_map)
                        elif '\\inventoryinjector\\' in new_file_lower:                                     # Inventory Injector
                            patchers.json_generic_plugin_pipe_formid_patcher(basename, new_file, form_id_map)
                        elif '\\customskills\\' in new_file_lower:                                          # Custom Skills Framework
                            patchers.json_generic_plugin_pipe_formid_patcher(basename, new_file, form_id_map)
                        elif '\\skyrimunbound\\' in new_file_lower:                                         # Skyrim Unbound
                            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
                        elif '\\playerequipmentmanager\\' in new_file_lower:                                # Player Equipment Manager
                            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
                        elif '\\mapmarker\\' in new_file_lower:                                             # CoMAP
                            patchers.json_generic_plugin_pipe_formid_patcher(basename, new_file, form_id_map)
                        elif new_file_lower.endswith('obody_presetdistributionconfig.json'):                # OBody NG
                            patchers.json_obody_patcher(basename, new_file, form_id_map)
                        elif os.path.basename(new_file_lower).startswith('shse.'):                          # Smart Harvest
                            patchers.json_shse_patcher(basename, new_file, form_id_map)
                        elif 'plugins\\rcs\\' in new_file_lower:                                            # Race Compatibility SKSE
                            patchers.json_generic_plugin_pipe_formid_patcher(basename, new_file, form_id_map)
                        elif 'plugins\\ostim\\' in new_file_lower:                                          # OStim
                            patchers.json_ostim_patcher(basename, new_file, form_id_map)
                        elif os.path.basename(new_file_lower) == 'sexlabconfig.json':                       # SL MCM Generated config
                            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
                        elif 'sexlab\\expression_' in new_file_lower:                                       # SL expressions
                            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
                        elif 'sexlab\\animations' in new_file_lower:                                        # SL animations?
                            if not new_file_lower.endswith('arrokreversecowgirl.json'):
                                patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map, int_type=True)
                        elif 'configs\\dse-soulgem-oven' in new_file_lower:                                 # SoulGem Oven
                            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
                        else:
                            print(f'Warn: Possible missing patcher for: {new_file}')
                    elif new_file_lower.endswith('.pex'):                                                   # Compiled script patching
                        patchers.pex_patcher(basename, new_file, form_id_map)
                    elif new_file_lower.endswith('.toml'):
                        if '\\_dynamicanimationcasting\\' in new_file_lower:                                # Dynamic Animation Casting (Original/NG)
                            patchers.toml_dac_patcher(basename, new_file, form_id_map)
                        elif '\\precision\\' in new_file_lower:                                             # Precision
                            patchers.toml_precision_patcher(basename, new_file, form_id_map)
                        elif '\\loki_poise\\' in new_file_lower:                                            # Loki Poise
                            patchers.toml_loki_tdm_patcher(basename, new_file, form_id_map)
                        elif '\\truedirectionalmovement\\' in new_file_lower:                               # TDM
                            patchers.toml_loki_tdm_patcher(basename,new_file, form_id_map)
                        else:
                            print(f'Warn: Possible missing patcher for: {new_file}')
                    elif new_file_lower.endswith('_srd.yaml'):                                              # Sound record distributor
                        patchers.srd_patcher(basename, new_file, form_id_map)
                    elif new_file_lower.endswith('.psc'):                                                   # Script source file patching, this doesn't take into account form ids being passed as variables
                        patchers.psc_patcher(basename, new_file, form_id_map)
                    elif 'facegeom' in new_file_lower and new_file_lower.endswith('.nif'):                  # FaceGeom mesh patching
                        patchers.facegeom_mesh_patcher(basename, new_file, form_id_map)
                    elif new_file_lower.endswith('.seq'):                                                   # SEQ file patching
                        patchers.seq_patcher(new_file, form_id_map)
                    elif new_file_lower.endswith('.jslot'):                                                 # Racemenu Presets
                        patchers.jslot_patcher(basename, new_file, form_id_map)
                    elif new_file_lower.endswith('config.txt') and 'plugin\\customskill' in new_file_lower: # CSF's old txt format
                        patchers.old_customskill_patcher(basename, new_file, form_id_map)
                    else:
                        print(f'Warn: Possible missing patcher for: {new_file}')
                        
                    CFIDs.compacted_and_patched[os.path.basename(master)].append(rel_path)

            except Exception as e:
                print(f'!Error: Failed to patch file: {new_file}')
                print(e)    

    def decompress_data(data_list):
        sizes_list = [[] for _ in range(len(data_list))]

        for i in range(len(data_list)):
            flag_byte = data_list[i][10]
            compressed_flag = (flag_byte & 0x04) != 0
            if data_list[i][:4] != b'GRUP' and compressed_flag:
                try:
                    decompressed = zlib.decompress(data_list[i][28:])  # Decompress the form
                except Exception as e:
                    print(f'!Error: {e}\r at Header: {data_list[i][:24]} at Index: {i}' )

                uncompressed_size_from_form = data_list[i][24:28]
                sizes_list[i] = [len(data_list[i]), 0, i, len(data_list[i][28:]), uncompressed_size_from_form]
                data_list[i] = data_list[i][:24] + decompressed

        return data_list, sizes_list
    
    def recompress_data(data_list, sizes_list):
        for i in range(len(data_list)):
            flag_byte = data_list[i][10]
            compressed_flag = (flag_byte & 0x04) != 0
            if data_list[i][:4] != b'GRUP' and compressed_flag:
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
    
    #Compacts master file and returns the new mod folder
    def compact_file(file, skyrim_folder_path, output_folder, update_header):
        form_id_file_name = 'ESLifier_Data/Form_ID_Maps/' + os.path.basename(file).lower() + "_FormIdMap.txt"
        if not os.path.exists(os.path.dirname(form_id_file_name)):
            os.makedirs(os.path.dirname(form_id_file_name))
        new_file, _ = CFIDs.copy_file_to_output(file, skyrim_folder_path, output_folder)

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

        master_count = CFIDs.get_master_count(data_list)

        data_list, sizes_list = CFIDs.decompress_data(data_list)

        form_id_list = []
        #Get all new form ids in plugin
        for form in data_list:
            if form[:4] not in (b'GRUP', b'TES4') and form[15] >= master_count and form[12:16] not in form_id_list:
                form_id_list.append([form[12:16], form[:4]])

        master_byte = master_count.to_bytes()

        saved_forms = CFIDs.form_processor.save_all_form_data(data_list, new_file)

        form_id_list.sort(key= lambda x: struct.unpack('<I', x[0])[0])

        if update_header and master_count != 0:
            new_id = binascii.unhexlify(master_count.to_bytes().hex() + '000000')
            new_range = 4096
        else:
            new_id = binascii.unhexlify(master_count.to_bytes().hex() + '000800')
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

        if len(to_remove) > 0:
            new_next_available_object_id = to_remove[-1][0]
        else:
            new_next_available_object_id = b'\x00\x00\x00\x01'

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

        form_id_replacements.sort(key= lambda x: struct.unpack('<I', x[0])[0])

        with open(form_id_file_name, 'w', encoding='utf-8') as fidf:
            for form_id, new_id in form_id_replacements:
                fidf.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')

        form_id_replacements_no_master_byte = [[old_id[:3], new_id[:3]] for old_id, new_id in form_id_replacements]

        data_list = CFIDs.form_processor.patch_form_data(data_list, saved_forms, form_id_replacements_no_master_byte, master_byte)

        data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list)

        data_list = CFIDs.update_grup_sizes(data_list, grup_struct, sizes_list)

        if struct.unpack('<I', form_id_replacements[-1][1])[0] > struct.unpack('<I', new_next_available_object_id)[0]:
            new_next_available_object_id = (struct.unpack('<I', form_id_replacements[-1][1])[0] + 1).to_bytes(4, 'little')
        else:
            new_next_available_object_id = (struct.unpack('<I', new_next_available_object_id)[0] + 1).to_bytes(4, 'little')

        data_list[0] = data_list[0][:38] + new_next_available_object_id[:3] + b'\x00' + data_list[0][42:]

        with open(new_file, 'wb') as f:
            f.write(b''.join(data_list))
            f.close()

        CFIDs.compacted_and_patched[os.path.basename(new_file)] = []
        
    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def patch_dependent_plugins(file, dependents, skyrim_folder_path, output_folder_path, update_header, file_masters):
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        
        with open(form_id_file_name, 'r', encoding='utf-8') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        threads = []

        for dependent in dependents:
            new_file, rel_path = CFIDs.copy_file_to_output(dependent, skyrim_folder_path, output_folder_path)
            basename = os.path.basename(new_file)
            basename_lower = basename.lower()
            if len(file_masters) > 0 and basename_lower in file_masters and len(file_masters[basename_lower]) > 0 and file_masters[basename_lower][-1].lower().endswith('.seq'):
                new_seq_file, rel_path_seq = CFIDs.copy_file_to_output(file_masters[basename_lower][-1], skyrim_folder_path, output_folder_path)
            else:
                new_seq_file, rel_path_seq = None, None
            if new_seq_file:
                print(f'-    {basename} + .seq')
            else:
                print(f'-    {basename}')
            thread = threading.Thread(target=CFIDs.patch_dependent, args=(new_file, update_header, file, form_id_file_data, rel_path, new_seq_file, rel_path_seq))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def patch_dependent(new_file, update_header, file, form_id_file_data, rel_path, new_seq_file, rel_path_seq):
        form_id_replacements = []
        try:
            with open(new_file, 'rb+') as dependent_file:
                #Update header to 1.71 to fit new records
                if update_header:
                    dependent_file.seek(0)
                    dependent_file.seek(30)
                    dependent_file.write(b'\x48\xE1\xDA\x3F')
                    dependent_file.seek(0)

                dependent_data = dependent_file.read()
                
                data_list, grup_struct = CFIDs.create_data_list(dependent_data)
            
                data_list, sizes_list = CFIDs.decompress_data(data_list)

                master_index = CFIDs.get_master_index(file, data_list)

                master_byte = master_index.to_bytes()

                saved_forms = CFIDs.form_processor.save_all_form_data(data_list, new_file)
                
                for i in range(len(form_id_file_data)):
                    form_id_conversion = form_id_file_data[i].split('|')
                    from_id = bytes.fromhex(form_id_conversion[0])[:3]
                    to_id = bytes.fromhex(form_id_conversion[1])[:3]
                    form_id_replacements.append([from_id, to_id])

                data_list = CFIDs.form_processor.patch_form_data_dependent(data_list, saved_forms, form_id_replacements, master_byte)

                data_list, sizes_list = CFIDs.recompress_data(data_list, sizes_list)
                
                data_list = CFIDs.update_grup_sizes(data_list, grup_struct, sizes_list)

                dependent_file.seek(0)
                dependent_file.truncate(0)
                dependent_file.write(b''.join(data_list))
                dependent_file.close()

            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(file)].append(rel_path)
        except Exception as e:
            print(f'!Error: Failed to patch depdendent: {new_file}')

        if new_seq_file:
            try:
                patchers.seq_patcher(new_seq_file, form_id_replacements, True)
            except Exception as e:
                print(f'!Error: Failed to patch depdendent\'s SEQ file: {new_seq_file}')
                print(e)
            with CFIDs.lock:
                CFIDs.compacted_and_patched[os.path.basename(file)].append(rel_path_seq)
        return

    #gets what master index the file is in inside of the dependent's data
    def get_master_index(file, data_list):
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_list = []
        master_index = 0
        name = os.path.basename(file).lower()
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master_list.append(tes4[offset+6:offset+field_size+5].decode('utf-8'))
            offset += field_size + 6
        for master in master_list:
            if name == master.lower():
                return master_index
            else:
                master_index += 1
    
    def get_master_count(data_list):
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_list_count = 0
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master_list_count  += 1
            offset += field_size + 6
        return master_list_count