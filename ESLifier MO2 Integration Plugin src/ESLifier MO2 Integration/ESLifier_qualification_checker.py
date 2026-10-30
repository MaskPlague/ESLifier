import os
import zlib
import struct

GAME_ESM_NAMES = {"SSE": "Skyrim.esm", "FO4": "Fallout4.esm"}

class qualification_checker():
    game_mode = "SSE"
    game_esm = GAME_ESM_NAMES["SSE"]
    max_record_id = 0xFFF
    dependent_dict: dict = {}
    missing_game_esm_as_master: dict = {}
    maxed_masters: set = set()
    new_cell_ids: dict = {}      # basename -> CELL form id hex strings, for the changed-cell scan

    @staticmethod
    def configure(game_mode: str, plugin_files: list):
        if game_mode not in GAME_ESM_NAMES:
            raise ValueError(f"Invalid GAME_MODE: {game_mode}")
        qualification_checker.game_mode = game_mode
        qualification_checker.game_esm = GAME_ESM_NAMES[game_mode]
        qualification_checker.new_cell_ids = {}
        qualification_checker.create_dependency_data(plugin_files)

    def create_dependency_data(plugin_files: list):
        dependent_dict: dict[str, set] = {os.path.basename(plugin).lower(): set() for plugin in plugin_files}
        missing_game_esm_as_master: dict[str, str] = {}
        maxed_masters: set[str] = set()
        game_esm = qualification_checker.game_esm
        for plugin in plugin_files:
            masters, has_records = qualification_checker.get_masters(plugin)
            if len(masters) > 0:
                for master in masters:
                    dependent_dict.setdefault(master.lower(), set()).add(plugin)
                if masters[0] != game_esm and has_records:
                    missing_game_esm_as_master[plugin] = masters[0]
            if len(masters) >= 254 and 'ESLifier_Cell_Master.esm' not in masters:
                maxed_masters.add(plugin)
        qualification_checker.dependent_dict = dependent_dict
        qualification_checker.missing_game_esm_as_master = missing_game_esm_as_master
        qualification_checker.maxed_masters = maxed_masters

    def get_masters(file: str) -> tuple[list, bool]:
        try:
            with open(file, 'rb') as f:
                f.seek(4)
                tes4_size = int.from_bytes(f.read(4)[::-1]) + 24
                f.seek(0)
                tes4_record = f.read(tes4_size)
                has_records = f.read(5) != b''
        except Exception:
            return [], False
        master_list = []
        offset = 24
        while offset < tes4_size:
            field = tes4_record[offset:offset+4]
            field_size = struct.unpack("<H", tes4_record[offset+4:offset+6])[0]
            if field == b'MAST':
                master_list.append(tes4_record[offset+6:offset+field_size+5].decode('utf-8', errors='replace'))
            offset += field_size + 6
        return master_list, has_records

    def qualification_check(self, plugin, new_header, scan_esms):
        already_esl, is_esm = qualification_checker.already_esl(plugin)
        if already_esl or (is_esm and not scan_esms):
            return (False, 'already esl or not scanning esms')
        return qualification_checker.file_reader(plugin, new_header, is_esm)

    def already_esl(file: str) -> tuple[bool, bool]:
        try:
            with open(file, 'rb') as f:
                f.seek(8)
                flags = struct.unpack("<I", f.read(4))[0]
        except Exception:
            return True, False
        esm = file.lower().endswith('.esm') or bool(flags & 0x1)
        return bool(flags & 0x200), esm

    def create_data_list(data: bytes) -> list:
        data_list = []
        offset = 0
        while offset < len(data):
            if data[offset:offset+4] == b'GRUP':
                data_list.append(data[offset:offset+24])
                offset += 24
            else:
                form_length = struct.unpack("<I", data[offset+4:offset+8])[0]
                offset_end = offset + 24 + form_length
                data_list.append(data[offset:offset_end])
                offset = offset_end
        return data_list

    def get_field_and_size(offset, form) -> tuple[bytes, int, int]:
        field = form[offset:offset+4]
        if field != b'XXXX':
            field_size = struct.unpack("<H", form[offset+4:offset+6])[0]
            return field, field_size, offset
        else:
            offset += 6
            field_size = struct.unpack("<I", form[offset:offset+4])[0]
            offset += 4
            field = form[offset:offset+4]
            return field, field_size, offset

    def get_master_count(data_list: list, is_sse_mode: bool, is_fo4_mode: bool) -> tuple[int, bool]:
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_count = 0
        has_game_esm_master = False
        game_esm = qualification_checker.game_esm.encode()
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master_count += 1
                if is_sse_mode and field_size == 11:
                    if tes4[offset+6:offset+16] == game_esm:
                        has_game_esm_master = True
                elif is_fo4_mode and field_size == 13:
                    if tes4[offset+6:offset+18] == game_esm:
                        has_game_esm_master = True
            offset += field_size + 6
        return master_count, has_game_esm_master

    def file_reader(file: str, update_header: bool, is_esm: bool) -> tuple:
        is_sse_mode = qualification_checker.game_mode == "SSE"
        is_fo4_mode = qualification_checker.game_mode == "FO4"
        basename = os.path.basename(file)
        try:
            with open(file, 'rb') as f:
                data = f.read()
            if data[:4] != b'TES4':
                return (False, 'not plugin')
            data_list = qualification_checker.create_data_list(data)
        except Exception:
            return (False, 'read fail')

        master_count, has_game_esm_master = qualification_checker.get_master_count(data_list, is_sse_mode, is_fo4_mode)
        all_dependents_have_game_esm_as_master = True
        if update_header:
            dependents = set(qualification_checker.dependent_dict.get(basename.lower(), []))
            for plugin_without_game_esm_as_master, master_0 in qualification_checker.missing_game_esm_as_master.items():
                if plugin_without_game_esm_as_master in dependents and basename == master_0:
                    all_dependents_have_game_esm_as_master = False
                    break

        possible_max = 2048
        if is_fo4_mode:
            version_float = round(struct.unpack("<f", data_list[0][30:34])[0], 2)
            is_1_0 = version_float == 1.0                   # Able to use 0x000-0x7FF
            upgradable = version_float == 0.95              # Not able to use <0x800 but can upgrade to 1.0 which can
            if (is_1_0 or upgradable) and update_header:
                possible_max = 4096
        elif is_sse_mode and update_header:
            possible_max = 4096

        limited_to_2048 = (master_count == 0 or not has_game_esm_master
                           or not all_dependents_have_game_esm_as_master)
        num_max_records = 2048 if limited_to_2048 else possible_max

        new_cell = False
        interior_cell_flag = False
        need_compacting = False
        new_wrld = False
        new_wthr = False
        previs_precombines = False
        cell_form_ids = set()
        count = 0
        for form in data_list:
            record_type = form[:4]
            if record_type not in (b'GRUP', b'TES4') and form[15] >= master_count:
                count += 1
                if count > num_max_records:
                    return (False, f'max record count of {num_max_records} exceeded')
                if int.from_bytes(form[12:15], "little") > qualification_checker.max_record_id:
                    need_compacting = True
                if record_type == b'CELL':
                    new_cell = True
                    cell_form_ids.add(form[12:15].hex())
                    if ((not interior_cell_flag and is_sse_mode)
                            or (not previs_precombines and is_fo4_mode)):
                        flag_byte = form[10]
                        compressed_flag = (flag_byte & 0x04) != 0
                        offset = 24
                        form_to_check = form
                        if compressed_flag:
                            form_to_check = zlib.decompress(form[28:])
                            offset = 0
                        form_size = len(form_to_check)
                        while offset < form_size:
                            field, field_size, offset = qualification_checker.get_field_and_size(offset, form_to_check)
                            if field == b'DATA' and is_sse_mode:
                                flags = form_to_check[offset+6]
                                interior_cell_flag = (flags & 0x01) != 0
                            elif field in (b'XCRI', b'XPRI') and is_fo4_mode:
                                previs_precombines = True
                            offset += field_size + 6
                if record_type == b'WRLD':
                    new_wrld = True
                if record_type == b'WTHR':
                    new_wthr = True

        if cell_form_ids and ((is_sse_mode and is_esm) or is_fo4_mode):
            qualification_checker.new_cell_ids[basename] = sorted(cell_form_ids)
        if is_sse_mode:
            return (True, need_compacting, new_cell, interior_cell_flag, new_wrld, new_wthr)
        return (True, need_compacting, new_cell, previs_precombines)
