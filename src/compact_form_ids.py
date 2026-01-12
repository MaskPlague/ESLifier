import os
import binascii
import shutil
import zlib
import threading
import subprocess
import struct
import hashlib
import json

from file_patchers import patchers
from intervaltree import IntervalTree
from full_form_processor import form_processor
from create_cell_master import create_new_cell_plugin
import patcher_conditions

import platform
import psutil
if platform.system() == 'Windows':
    from win32 import win32file
    win32file._setmaxstdio(8192)

total_ram = psutil.virtual_memory().available
usable_ram = total_ram * 0.90
thread_memory_usage = 30 * 1024 * 1024
max_threads = max(1, int(usable_ram / thread_memory_usage))
if max_threads > 8192:
    MAX_THREADS = 8192
else:
    MAX_THREADS = max_threads

class CFIDs():
    def __init__(self, skyrim_folder_path: str, output_folder_path: str, output_folder_name: str, overwrite_path: str, update_header: bool, mo2_mode: bool,
                  create_cell_master_class: create_new_cell_plugin, original_files: dict, winning_files_dict: dict, winning_file_history_dict: dict,
                  compacted_and_patched: dict, master_byte_data:dict, bsa_masters: list, bsa_dict: dict, persistent_ids: bool, free_non_existent: bool,
                  additional_file_patcher_conditions):
        self.skyrim_folder_path = os.path.normpath(skyrim_folder_path)
        self.output_folder_path = os.path.normpath(output_folder_path)
        self.output_folder_name = os.path.normpath(output_folder_name)
        self.output_folder = os.path.normpath(os.path.join(output_folder_path, output_folder_name))
        self.overwrite_path = os.path.normpath(overwrite_path)
        self.mo2_mode = mo2_mode
        self.update_header = update_header
        self.create_cell_master_class = create_cell_master_class
        self.original_files: dict = original_files
        self.winning_files_dict: dict = winning_files_dict
        self.winning_file_history_dict = winning_file_history_dict
        self.compacted_and_patched: dict[str, list[str]] = compacted_and_patched
        self.master_byte_data = master_byte_data
        self.bsa_masters = bsa_masters
        self.bsa_dict = bsa_dict
        self.persistent_ids = persistent_ids
        self.free_non_existent = free_non_existent
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(1000)
        self.additional_conditions = additional_file_patcher_conditions

    def save_data(self):
        self.dump_compacted_and_patched('ESLifier_Data/compacted_and_patched.json', self.compacted_and_patched)
        self.dump_dictionary('ESLifier_Data/original_files.json', self.original_files)
        self.dump_dictionary('ESLifier_Data/winning_file_history_dict.json', self.winning_file_history_dict)
        self.dump_dictionary('ESLifier_Data/master_byte_data.json', self.master_byte_data)

    def dump_compacted_and_patched(self, file, dictionary: dict[str, list[str]]):
        data: dict[str, list[str]] = self.get_from_file(file)
        for key, value in dictionary.items():
            if key not in data:
                data[key] = []
            for item in value:
                if item.lower() not in data[key]:
                    data[key].append(item.lower())
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to {file}')
            print(e)
    
    def dump_dictionary(self, file, dictionary: dict):
        data = self.get_from_file(file)
        for key, values in dictionary.items():
            data[key] = values
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump data to {file}')
            print(e)
    
    def get_from_file(self, file: str) -> dict:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def hash_output_files(self, files_to_not_hash: list[str], before_patching:bool = False) -> dict:
        to_hash = {}
        new_file_hashes: dict = self.get_from_file("ESLifier_Data/new_file_hashes.json")
        local_compacted_and_patched = self.get_from_file("ESLifier_Data/compacted_and_patched.json")
        lowered_output = self.output_folder.lower()
        for _1, values in local_compacted_and_patched.items():
            for rel_path in values:
                lower_rel_path = rel_path.lower()
                if lower_rel_path not in to_hash and not lower_rel_path.endswith(('.pex', '.esp', '.esl', '.esm')):
                    full_path = os.path.normpath(os.path.join(lowered_output, lower_rel_path))
                    to_hash[lower_rel_path] = full_path

        for lower_rel_path, file in to_hash.items():
            if file not in files_to_not_hash:
                if os.path.exists(file):
                    try:
                        with open(file, 'rb') as f:
                            sha256_hash = hashlib.sha256(f.read()).hexdigest()
                            f.close()
                        old_hash, changed = new_file_hashes.get(lower_rel_path, (None, False))
                        if not before_patching:
                            new_file_hashes[lower_rel_path] = (sha256_hash, changed)
                        elif before_patching:
                            if old_hash != None and old_hash != sha256_hash:
                                new_file_hashes[lower_rel_path] = (sha256_hash, True)
                            else:
                                new_file_hashes[lower_rel_path] = (sha256_hash, changed)
                    except Exception as e:
                        print(f"!Error: Failed to hash file: {file}")
                        print(e)

        self.dump_dictionary("ESLifier_Data/new_file_hashes.json", new_file_hashes)

    def compact_and_patch(self, file_to_compact: str, dependents: list, all_dependents_have_skyrim_esm_as_master: bool,
                           add_cell_to_master: bool, files_to_patch: dict):
        self.do_generate_cell_master = add_cell_to_master
        self.form_id_map = {}
        self.form_id_rename_map = []
        print(f"Editing Plugin: {os.path.basename(file_to_compact)}...")
        self.compact_file(file_to_compact, all_dependents_have_skyrim_esm_as_master)
        self.get_form_id_map(file_to_compact)
        if dependents != []:
            print(f"-  Patching {len(dependents)} Dependent Plugins...")
            self.patch_dependent_plugins(file_to_compact, dependents, files_to_patch)

        name = os.path.basename(file_to_compact).lower()
        if name in files_to_patch or name in self.bsa_masters:
            patch_or_rename = []
            if name in files_to_patch:
                patch_or_rename = files_to_patch[os.path.basename(file_to_compact).lower()]

            if name in self.bsa_masters:
                print('-  Temporarily Extracting FaceGen/Voice files from BSA for patching...')
                if not os.path.exists('bsa_extracted_temp/'):
                    os.makedirs('bsa_extracted_temp/')
                else:
                    shutil.rmtree('bsa_extracted_temp/')
                    os.makedirs('bsa_extracted_temp/')
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                for bsa_file, values in self.bsa_dict.items():
                    if name in values:
                        try:
                            self.bsa_temp_extract(bsa_file, "\\voice\\", name, startupinfo)
                            self.bsa_temp_extract(bsa_file, "\\facetint\\", name, startupinfo)
                            self.bsa_temp_extract(bsa_file, "\\facegeom\\", name, startupinfo)
                        except Exception as e:
                            print(f'!Error Reading BSA: {file}')
                            print(e)
                                            
                rel_paths = []
                for file in patch_or_rename:
                    rel_path: str = self.get_rel_path(file)
                    rel_paths.append(rel_path.lower())

                start = os.path.join(os.getcwd(), 'bsa_extracted_temp')
                for root, dir, files in os.walk('bsa_extracted_temp/'):
                    for file in files:
                        full_path = os.path.normpath(os.path.join(root, file))
                        rel_path = os.path.relpath(full_path, start).lower()
                        if rel_path not in rel_paths and file.endswith(('.nif', '.dds', '.fuz', '.xwm', '.wav', '.lip')):
                            patch_or_rename.append(full_path)
                            rel_paths.append(rel_path)
                
            to_patch, to_rename = self.sort_files_to_patch_or_rename(file_to_compact, patch_or_rename) #function to get files that need to be edited in some way to function correctly.
            if len(to_patch) > 0:
                print(f"-  Patching {len(to_patch)} Dependent Files...")
                if len(to_patch) > 20:
                    print('\n')
                self.patch_files_threader(file_to_compact, to_patch)
            if len(to_rename) > 0:
                print(f"-  Renaming/Patching {len(to_rename)} Dependent Files...")
                if len(to_rename) > 20:
                    print('\n')
                self.rename_files_threader(file_to_compact, to_rename)
        if os.path.exists('bsa_extracted_temp/'):
            print('-  Deleting temporarily Extracted FaceGen/Voice Files...')
            shutil.rmtree('bsa_extracted_temp/')
        print('CLEAR ALT')
        return self.original_files, self.winning_files_dict, self.master_byte_data, self.winning_file_history_dict, self.compacted_and_patched
    
    def bsa_temp_extract(self, bsa_file: str, type: str, name:str, startupinfo: subprocess.STARTUPINFO):
        with subprocess.Popen(
            ["bsarch/bsarch.exe", "unpack", bsa_file, "bsa_extracted_temp", type + name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            text=True
            ) as p:
                for line in p.stdout:
                    if line.startswith('Unpacking error'):
                        raise Exception(f"During Temp Extraction, {line}")
                    
    def set_flag(self, file: str):
        print("-  Changing ESL flag in: " + os.path.basename(file))
        new_file, _1 = self.copy_file_to_output(file)
        try:
            with open(new_file, 'rb+') as f:
                f.seek(9)
                f.write(b'\x02')
        except Exception as e:
            print('!Error: Failed to set ESL flag in {file}')
            print(e)           
        return self.original_files, self.winning_file_history_dict

    def patch_new(self, compacted_file: str, dependents: list, files_to_patch: list, add_cell_to_master: bool):
        self.do_generate_cell_master = add_cell_to_master
        self.form_id_map = {}
        self.form_id_rename_map = []
        print('Patching new plugins and files for ' + compacted_file + '...')
        self.master_byte = bytes.fromhex(self.master_byte_data[compacted_file]['master_byte'])
        self.updated_master_index = self.master_byte_data[compacted_file]['updated_master_index']
        self.compacted_and_patched[compacted_file] = []
        if dependents != []:
            print("-  Patching New Dependent Plugins...")
            self.patch_dependent_plugins(compacted_file, dependents, files_to_patch)
        if os.path.basename(compacted_file) in files_to_patch:
            to_patch, to_rename = self.sort_files_to_patch_or_rename(compacted_file, files_to_patch[os.path.basename(compacted_file)])
            self.get_form_id_map(compacted_file)
            if len(to_patch) > 0:
                print(f"-  Patching {len(to_patch)} New Dependent Files...")
                if len(to_patch) > 20:
                    print('\n')
                self.patch_files_threader(compacted_file, to_patch)
            if len(to_rename) > 0:
                print(f"-  Renaming/Patching {len(to_rename)} New Dependent Files...")
                if len(to_rename) > 20:
                    print('\n')
                self.rename_files_threader(compacted_file, to_rename)
        print('CLEAR ALT')
        return self.original_files, self.winning_files_dict, self.master_byte_data, self.winning_file_history_dict, self.compacted_and_patched

    #Create a copy of the mod plugin we're compacting
    def copy_file_to_output(self, file: str) -> tuple[str, str]:
        end_path: str = self.get_rel_path(file)
        new_file: str = os.path.normpath(os.path.join(os.path.join(self.output_folder_path, self.output_folder_name), end_path))
        (winning_mod, _) = self.winning_files_dict.get(end_path.lower(), (None, None))
        if winning_mod != None and winning_mod != self.output_folder_name:
            self.winning_file_history_dict[end_path.lower()] = winning_mod
        with self.lock:
            if not os.path.exists(os.path.dirname(new_file)):
                os.makedirs(os.path.dirname(new_file))
            if not os.path.exists(new_file):
                shutil.copy(file, new_file)
        if ((end_path.lower() not in self.original_files or self.original_files[end_path.lower()] != file) and 
            'bsa_extracted' not in file and self.output_folder_name not in file):
            try:
                with open(file, 'rb') as f:
                    sha256_hash = hashlib.sha256(f.read()).hexdigest()
                    f.close()
                self.original_files[end_path.lower()] = [file, sha256_hash]
            except Exception as e:
                print(f'!Error: Failed to hash {file}')
                print(e)
        return new_file, end_path
    
    def get_rel_path(self, file: str) -> str:
        if 'bsa_extracted' in file:
            if 'bsa_extracted_temp' in file:
                start = os.path.join(os.getcwd(), 'bsa_extracted_temp/')
            else:
                start = os.path.join(os.getcwd(), 'bsa_extracted/')
            rel_path = os.path.normpath(os.path.relpath(file, start))
        elif self.mo2_mode and file.lower().startswith(self.overwrite_path.lower()):
            rel_path = os.path.normpath(os.path.relpath(file, self.overwrite_path))
        else:
            if self.mo2_mode:
                parts = os.path.normpath(os.path.relpath(file, self.skyrim_folder_path)).split(os.sep)
                if len(parts) != 1:
                    parts = parts[1:]
                rel_path = os.path.join(*parts)
            else:
                rel_path = os.path.normpath(os.path.relpath(file, self.skyrim_folder_path))
        return rel_path
    
    #Sort the file masters list into files that only need patching and files that need renaming and maybe patching
    def sort_files_to_patch_or_rename(self, master: str, files: list[str]) -> tuple[list[str], list[str]]:
        files_to_patch = []
        files_to_rename = []
        split_name = os.path.splitext(os.path.basename(master))[0].lower()
        matchers = ['.pex', '.ini', '_conditions.txt', '.json', '.jslot', '.yaml', '.yml',
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

    def rename_files_threader(self, master: str, files: list[str]):
        threads = []
        split = len(files)
        if split > MAX_THREADS:
            split = MAX_THREADS

        chunk_size = len(files) // split
        chunks = [files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(files[(split) * chunk_size:])
        self.count = 0
        self.file_count = len(files)
        for chunk in chunks:
            thread = threading.Thread(target=self.rename_files, args=(master, chunk))
            threads.append(thread)
            thread.start()
        
        for thread in threads: 
            thread.join()

    #Rename each file in the list of files from the old Form IDs to the new Form IDs
    def rename_files(self, master: str, files: list[str]) -> None:
        facegeom_meshes = []
        master_base_name = os.path.basename(master)
        for file in files:
            if self.file_count > 20:
                self.count += 1
                percent = self.count / self.file_count * 100
                factor = round(self.file_count * 0.001)
                if factor == 0:
                    factor = 1
                if (self.count % factor) >= (factor-1) or self.count >= self.file_count:
                    print('\033[F\033[K-    Percentage: ' + str(round(percent,1)) +'%\n-    Files: ' + str(self.count) + '/' + str(self.file_count), end='\r')
            
            rel_path = self.get_rel_path(file)
            for form_ids in self.form_id_rename_map:
                if form_ids[0].lower() in file.lower():
                    with self.semaphore:
                        new_file, rel_path_new_file = self.copy_file_to_output(file)
                        index = new_file.lower().index(form_ids[0].lower())
                        renamed_file = new_file[:index] + form_ids[1].upper() + new_file[index+6:]
                        with self.lock:
                            os.replace(new_file, renamed_file)
                        index = rel_path_new_file.lower().index(form_ids[0].lower())
                        rel_path_renamed_file = rel_path_new_file[:index] + form_ids[1].upper() + rel_path_new_file[index+6:]
                        with self.lock:
                            if rel_path_new_file not in self.compacted_and_patched[master_base_name]:
                                self.compacted_and_patched[master_base_name].append(rel_path_new_file)
                            if rel_path_renamed_file not in self.compacted_and_patched[master_base_name]:
                                self.compacted_and_patched[master_base_name].append(rel_path_renamed_file)
                            if 'facegeom' in new_file.lower() and master_base_name.lower() in new_file.lower():
                                facegeom_meshes.append(renamed_file)
                    break
            self.compacted_and_patched[master_base_name].append(rel_path.lower())
        if facegeom_meshes != []:
            self.patch_files(master, facegeom_meshes)
        return

    #Create the Form ID map which is a list of tuples that holds four Form Ids that are in \xMASTER\x00\x00\x00 order:
    #original Form ID w/o leading 0s, original Form ID w/ leading 0s, new Form ID w/o 0s, new Form ID w/ 0s, 
    #the orginal Form ID in \x00\x00\x00\xMASTER order, and the new Form ID in the same order.
    def get_form_id_map(self, file: str):
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        with open(form_id_file_name, 'r') as fidf:
            form_id_file_data = fidf.readlines()
        for form_id_history in form_id_file_data:
            form_id_conversion = form_id_history.split('|')

            from_id_hex = bytes.fromhex(form_id_conversion[0])[:3][::-1].hex().upper()
            from_id_int = int.from_bytes(bytes.fromhex(form_id_conversion[0])[:3], byteorder='little')
            from_id_bytes = bytes.fromhex(form_id_conversion[0])

            to_id_hex = bytes.fromhex(form_id_conversion[1])[:3][::-1].hex().upper()
            to_id_int = int.from_bytes(bytes.fromhex(form_id_conversion[1])[:3], byteorder='little')
            to_id_bytes = bytes.fromhex(form_id_conversion[1])
            to_id_hex_no_0 = to_id_hex.lstrip('0')
            if to_id_hex_no_0 == '':
                to_id_hex_no_0 = '0'

            self.form_id_rename_map.append([from_id_hex, to_id_hex])
            

            if len(to_id_bytes) == 4:
                update_plugin_name = False
            else:
                to_id_bytes = to_id_bytes[:4]
                update_plugin_name = True

            self.form_id_map[from_id_int]   = {"hex": to_id_hex,
                                                "int": to_id_int,
                                                "hex_no_0": to_id_hex_no_0,
                                                "bytes": to_id_bytes,
                                                "update_name": update_plugin_name
                                                }
            
            self.form_id_map[from_id_bytes] = to_id_bytes

    def patch_files_threader(self, master: str, files: list[str]):
        threads = []
        split = len(files)
        if split > MAX_THREADS:
            split = MAX_THREADS

        chunk_size = len(files) // split
        chunks = [files[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(files[(split) * chunk_size:])
        self.count = 0
        self.file_count = len(files)
        for chunk in chunks:
            if self.file_count > 20:
                self.count += 1
                percent = self.count / self.file_count * 100
                factor = round(self.file_count * 0.001)
                if factor == 0:
                    factor = 1
                if (self.count % factor) >= (factor-1) or self.count >= self.file_count:
                    print('\033[F\033[K-  Percentage: ' + str(round(percent,1)) +'%\n-  Files: ' + str(self.count) + '/' + str(self.file_count), end='\r')
            thread = threading.Thread(target=self.patch_files, args=(master, chunk))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()

    #Patches each file type in a different way as each has Form IDs present in a different format
    def patch_files(self, master: str, files: list[str]):
        for file in files:
            new_file, rel_path = self.copy_file_to_output(file)
            new_file_lower = new_file.lower()
            basename = os.path.basename(master).lower()
            try:
                with self.semaphore:
                    with self.lock:
                        try:
                            patcher_conditions.patch_file_conditions(new_file_lower, new_file, basename, self.form_id_map, self.form_id_rename_map, 
                                                                     self.master_byte, self.updated_master_index, self.do_generate_cell_master,
                                                                     self.additional_conditions, 'utf-8')
                        except Exception as e:
                            exception_type = type(e)
                            if exception_type == UnicodeDecodeError:
                                patcher_conditions.patch_file_conditions(new_file_lower, new_file, basename, self.form_id_map, self.form_id_rename_map, 
                                                                         self.master_byte, self.updated_master_index, self.do_generate_cell_master,
                                                                          self.additional_conditions, 'ansi')
                            else:
                                print(f'!Error: Failed to patch file: {new_file}')
                                print(e)
                        self.compacted_and_patched[os.path.basename(master)].append(rel_path)
            except Exception as e:
                print(f'!Error: Failed to patch file: {new_file}')
                print(e)      

    def decompress_data(self, data_list: list) -> tuple[list, list]:
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
    
    def recompress_data(self, data_list: list, sizes_list: list) -> tuple[list, list]:
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
    
    def update_grup_sizes(self, data_list: list, grup_struct: dict, sizes_list: list) -> list:
        byte_array_data_list = [bytearray(form) for form in data_list]
        for i, size_info in enumerate(sizes_list):
            if size_info and size_info[1] != 0:
                for index in grup_struct[i]:
                    current_size = int.from_bytes(byte_array_data_list[index][4:8][::-1])
                    new_size = current_size + size_info[1]
                    byte_array_data_list[index][4:8] = new_size.to_bytes(4, 'little')
        data_list = [bytes(form) for form in byte_array_data_list]
        return data_list
    
    def create_data_list(self, data: bytes) -> tuple[list[bytes], dict]:
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
    def compact_file(self, file: str, all_dependents_have_skyrim_esm_as_master: bool):
        basename = os.path.basename(file)
        form_id_file_name = 'ESLifier_Data/Form_ID_Maps/' + basename.lower() + "_FormIdMap.txt"
        if not os.path.exists(os.path.dirname(form_id_file_name)):
            os.makedirs(os.path.dirname(form_id_file_name))

        new_file, _ = self.copy_file_to_output(file)

        #Set ESL flag, update to header 1.71 for new Form IDs, and get data from mod plugin
        data = b''
        with open(new_file, 'rb+') as f:
            f.seek(9)
            f.write(b'\x02')
            if self.update_header:
                f.seek(0)
                f.seek(30)
                f.write(b'\x48\xE1\xDA\x3F')
            f.seek(0)
            data = f.read()
            f.close()

        data_list, grup_struct = self.create_data_list(data)

        master_count: int
        master_count, has_skyrim_esm_master = self.get_master_count(data_list)

        data_list, sizes_list = self.decompress_data(data_list)
        updated_master_index: int = -1
        if self.do_generate_cell_master:
            new_cell_form_ids = self.create_cell_master_class.add_cells(data_list, grup_struct, master_count, os.path.basename(file))
            data_list, updated_master_index = self.add_cell_master_to_masters(data_list)

        form_id_list = []
        #Get all new form ids in plugin
        for form in data_list:
            if form[:4] not in (b'GRUP', b'TES4') and form[15] >= master_count and form[12:16] not in form_id_list:
                form_id_list.append([form[12:16], form[:4]])

        master_byte = master_count.to_bytes()
        self.master_byte = master_byte
        self.updated_master_index = updated_master_index
        self.master_byte_data[basename] = {'master_byte': master_byte.hex(), 'updated_master_index': updated_master_index}

        saved_forms = form_processor.save_all_form_data(data_list)

        form_id_list.sort(key= lambda x: struct.unpack('<I', x[0])[0])

        all_form_ids_list = [form_id for form_id, record_type in form_id_list]

        if self.update_header and master_count != 0 and has_skyrim_esm_master and all_dependents_have_skyrim_esm_as_master:
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

        for old_id, type, new_decimal, new_id in to_remove:
            form_id_list.remove([old_id, type])
            new_form_ids.remove([new_decimal, new_id])

        matched_ids = []
        form_id_replacements = []
        #If a form id map already exists we want to compact the Form IDs the exact same as they were before
        if self.persistent_ids and os.path.exists(form_id_file_name):
            with open(form_id_file_name, 'r', encoding='utf-8') as f:
                form_id_file_data = f.readlines()
            if self.do_generate_cell_master:
                old_ids_of_new_cells = [old_id for old_id, new_id in new_cell_form_ids]
            else:
                old_ids_of_new_cells = []
            for i in range(len(form_id_file_data)):
                form_id_conversion = form_id_file_data[i].split('|')
                from_id = bytes.fromhex(form_id_conversion[0])[:3] + master_byte
                if from_id in old_ids_of_new_cells:
                    if updated_master_index == -1:
                        to_id = bytes.fromhex(form_id_conversion[1])[:3] + master_byte + b'\xFF'
                    else:
                        to_id = bytes.fromhex(form_id_conversion[1])[:3] + updated_master_index.to_bytes() + b'\xFF'
                else:
                    to_id = bytes.fromhex(form_id_conversion[1])[:4]
                if from_id in all_form_ids_list:
                    form_id_replacements.append([from_id, to_id])
                elif not self.free_non_existent:
                    form_id_replacements.append([from_id, to_id])
        if len(form_id_replacements) > 0:
            matched_from_ids = [from_id[:4] for from_id, to_id in form_id_replacements]
            matched_to_ids = [to_id[:4] for from_id, to_id in form_id_replacements]
            form_id_list[:] = [[old_id, type] for old_id, type in form_id_list if old_id not in matched_from_ids]
            new_form_ids[:] = [[new_decimal, new_id] for new_decimal, new_id in new_form_ids if new_id not in matched_to_ids]

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
                #if len(new_cell_form_ids) <= 0:
                #    break
                _, new_id = new_form_ids.pop(0)
                form_id_replacements.append([form_id, new_id])

        if self.do_generate_cell_master:
            for old_id, new_id in new_cell_form_ids:
                copy = form_id_replacements.copy()
                added = False
                for replacement in copy:
                    if old_id == replacement[0]:
                        form_id_replacements.remove(replacement)
                        if updated_master_index == -1:
                            form_id_replacements.append([old_id, new_id + master_byte + b'\xFF'])
                        else:
                            form_id_replacements.append([old_id, new_id + updated_master_index.to_bytes() + b'\xFF'])
                        added = True
                        break
                if not added:
                    if updated_master_index == -1:
                        form_id_replacements.append([old_id, new_id + master_byte + b'\xFF'])
                    else:
                        form_id_replacements.append([old_id, new_id + updated_master_index.to_bytes() + b'\xFF'])

        form_id_replacements.sort(key= lambda x: struct.unpack('<I', x[0])[0])
        with open(form_id_file_name, 'w', encoding='utf-8') as fidf:
            for form_id, new_id in form_id_replacements:
                fidf.write(str(form_id.hex()) + '|' + str(new_id.hex()) + '\n')

        form_id_replacements_no_master_byte = {old_id[:3]: new_id[:3] if len(new_id) <= 4 else new_id[:4] for old_id, new_id in form_id_replacements}
        
        data_list = form_processor.patch_form_data(data_list, saved_forms, form_id_replacements_no_master_byte, master_byte, 
                                                   set(all_form_ids_list), self.do_generate_cell_master, updated_master_index)

        data_list, sizes_list = self.recompress_data(data_list, sizes_list)

        data_list = self.update_grup_sizes(data_list, grup_struct, sizes_list)

        with open(new_file, 'wb') as f:
            f.write(b''.join(data_list))
            f.close()

        self.compacted_and_patched[os.path.basename(new_file)] = []
        
    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def patch_dependent_plugins(self, file: str, dependents: list, file_masters: dict):
        form_id_file_name = "ESLifier_Data/Form_ID_Maps/" + os.path.basename(file).lower() + "_FormIdMap.txt"
        form_id_file_data = ''
        
        with open(form_id_file_name, 'r', encoding='utf-8') as form_id_file:
            form_id_file_data = form_id_file.readlines()

        threads: list[threading.Thread] = []

        for dependent in dependents:
            new_file, rel_path = self.copy_file_to_output(dependent)
            basename: str = os.path.basename(new_file)
            basename_lower = basename.lower()
            if len(file_masters) > 0 and basename_lower in file_masters and len(file_masters[basename_lower]) > 0 and file_masters[basename_lower][-1].lower().endswith('.seq'):
                new_seq_file, rel_path_seq = self.copy_file_to_output(file_masters[basename_lower][-1])
            else:
                new_seq_file, rel_path_seq = None, None
            if new_seq_file and len(self.form_id_map) > 0:
                print(f'-    {basename} + .seq')
            elif len(self.form_id_map) > 0:
                print(f'-    {basename}')
            thread = threading.Thread(target=self.patch_dependent, args=(new_file, file, form_id_file_data, rel_path, new_seq_file, rel_path_seq))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def patch_dependent(self, new_file: str, file: str, form_id_file_data: list[str], rel_path: str, new_seq_file: str, rel_path_seq: str):
        form_id_replacements = []
        try:
            with open(new_file, 'rb+') as dependent_file:
                #Update header to 1.71 to fit new records
                if self.update_header:
                    dependent_file.seek(0)
                    dependent_file.seek(30)
                    dependent_file.write(b'\x48\xE1\xDA\x3F')
                    dependent_file.seek(0)

                dependent_data = dependent_file.read()

                data_list, grup_struct = self.create_data_list(dependent_data)
            
                data_list, sizes_list = self.decompress_data(data_list)

                master_index = self.get_master_index(file, data_list)

                master_index_byte = master_index.to_bytes()

                form_id_list = []
                master_byte = b''
                updated_master_index: int = -1
                if self.do_generate_cell_master:
                    #Get all new form ids in plugin
                    for form in data_list:
                        if form[:4] not in (b'GRUP', b'TES4') and form[15] >= master_index and form[12:16] not in form_id_list:
                            form_id_list.append(form[12:16])
                    master_byte = self.get_master_count(data_list)[0].to_bytes()
                    with self.lock:
                        data_list, updated_master_index = self.add_cell_master_to_masters(data_list)

                saved_forms = form_processor.save_all_form_data(data_list)

                #TODO: Optimize this, there is no point in splitting the form id map data each dependent
                for i in range(len(form_id_file_data)):
                    form_id_conversion = form_id_file_data[i].split('|')
                    from_id = bytes.fromhex(form_id_conversion[0])[:3]
                    id = bytes.fromhex(form_id_conversion[1])
                    if len(id) > 4 and self.do_generate_cell_master:
                        if updated_master_index == -1:
                            to_id = id[:3] + master_byte
                        else:
                            to_id = id[:3] + updated_master_index.to_bytes()
                    else:
                        to_id = id[:3]
                    form_id_replacements.append([from_id, to_id])
                form_id_replacements_dict = {key: value for key, value in form_id_replacements}
                data_list = form_processor.patch_form_data_dependent(data_list, saved_forms, form_id_replacements_dict, master_index_byte, master_byte,
                                                                    set(form_id_list), self.do_generate_cell_master, updated_master_index)

                data_list, sizes_list = self.recompress_data(data_list, sizes_list)
                
                data_list = self.update_grup_sizes(data_list, grup_struct, sizes_list)

                dependent_file.seek(0)
                dependent_file.truncate(0)
                dependent_file.write(b''.join(data_list))
                dependent_file.close()

            with self.lock:
                self.compacted_and_patched[os.path.basename(file)].append(rel_path)
                self.master_byte_data[os.path.basename(file)]= {'master_byte': master_byte.hex(), 'updated_master_index': updated_master_index}
        except Exception as e:
            print(f'!Error: Failed to patch depdendent: {new_file}')
            print(e)
            return

        if new_seq_file:
            try:
                patchers.seq_patcher(new_seq_file, form_id_replacements, master_byte, updated_master_index=updated_master_index, update_byte=self.do_generate_cell_master, dependent=True)
            except Exception as e:
                print(f'!Error: Failed to patch depdendent\'s SEQ file: {new_seq_file}')
                print(e)
            with self.lock:
                self.compacted_and_patched[os.path.basename(file)].append(rel_path_seq)
        return

    #gets what master index the file is in inside of the dependent's data
    def get_master_index(self, file: str, data_list: list[bytes]) -> int:
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_list: list[str] = []
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
    
    def get_master_count(self, data_list: list[bytes]) -> tuple[int, bool]:
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_list_count = 0
        has_skyrim_esm_master = False
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master_list_count  += 1
                if field_size == 11:
                    if tes4[offset+6:offset+16] == b'Skyrim.esm':
                        has_skyrim_esm_master = True
            offset += field_size + 6
        return master_list_count, has_skyrim_esm_master
    
    def add_cell_master_to_masters(self, data_list: list[bytes]):
        tes4 = data_list[0]
        new_master_data = (
            b'\x4D\x41\x53\x54\x19\x00\x45\x53\x4C\x69\x66\x69' +
            b'\x65\x72\x5F\x43\x65\x6C\x6C\x5F\x4D\x61\x73\x74' +
            b'\x65\x72\x2E\x65\x73\x6D\x00\x44\x41\x54\x41\x08' +
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            )
        offset = 24
        data_len = len(tes4)
        if new_master_data in tes4:
            master_index = 0
            while offset < data_len:
                field = tes4[offset:offset+4]
                field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
                if field == b'MAST':
                    if b'ESLifier_Cell_Master.esm' in tes4[offset+6:offset+6+field_size]:
                        return data_list, master_index
                    master_index += 1
                offset += field_size + 6
        master_exists = False
        cnam_offset = 0
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'CNAM':
                cnam_offset = offset
            if field == b'MAST':
                master_exists = True
            elif field != b'DATA' and master_exists:
                break
            offset += field_size + 6
        tes4_size: int = struct.unpack("<I", tes4[4:8])[0] + 45
        if master_exists:
            tes4 = b'TES4' + tes4_size.to_bytes(4,'little') + tes4[8:offset] + new_master_data + tes4[offset:]
        else:
            field_size = struct.unpack("<H", tes4[cnam_offset+4:cnam_offset+6])[0]
            offset = cnam_offset + 6 + field_size
            tes4 = b'TES4' + tes4_size.to_bytes(4,'little') + tes4[8:offset] + new_master_data + tes4[offset:]

        data_list[0] = tes4
        return data_list, -1