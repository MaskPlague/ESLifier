import os
import zlib
import struct
from concurrent.futures import ThreadPoolExecutor

from .ESLifier_qualification_checker import qualification_checker


class cell_scanner():
    @staticmethod
    def scan(plugins_with_new_cells: list, new_cell_ids: dict, dependent_dict: dict, game_mode: str,
             is_running=lambda: True) -> set:
        result = set()
        dependents_of = {key.lower(): value for key, value in dependent_dict.items()}

        def check(mod):
            basename = os.path.basename(mod)
            cell_form_ids = new_cell_ids.get(basename)
            dependents = dependents_of.get(basename.lower())
            if not cell_form_ids or not dependents:
                return
            ids = set(cell_form_ids)
            for dependent in dependents:
                if not is_running():
                    return
                try:
                    if cell_scanner.is_dependent_modifying(mod, dependent, ids, game_mode):
                        result.add(basename)
                        return
                except:
                    pass

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(check, plugins_with_new_cells))
        return result

    @staticmethod
    def is_dependent_modifying(mod: str, dependent: str, cell_form_ids, game_mode: str) -> bool:
        try:
            with open(dependent, 'rb') as f:
                dependent_data = f.read()
            data_list = qualification_checker.create_data_list(dependent_data)
        except Exception:
            return False
        master_index = cell_scanner.get_master_index(mod, data_list)
        if master_index is None:
            return False
        for form in data_list:
            if form[:4] == b'CELL' and form[15] == master_index and form[12:15].hex() in cell_form_ids:
                if game_mode == "SSE":
                    return True
                if game_mode == "FO4":
                    form_to_check = form
                    offset = 24
                    if (form[10] & 0x04) != 0:
                        form_to_check = zlib.decompress(form[28:])
                        offset = 0
                    form_size = len(form_to_check)
                    while offset < form_size:
                        field, field_size, offset = qualification_checker.get_field_and_size(offset, form_to_check)
                        if field in (b'XCRI', b'XPRI'):
                            return True
                        offset += field_size + 6
        return False

    @staticmethod
    def get_master_index(file: str, data_list: list):
        tes4 = data_list[0]
        offset = 24
        data_len = len(tes4)
        master_index = 0
        name = os.path.basename(file).lower()
        while offset < data_len:
            field = tes4[offset:offset+4]
            field_size = struct.unpack("<H", tes4[offset+4:offset+6])[0]
            if field == b'MAST':
                master = tes4[offset+6:offset+field_size+5].decode('utf-8', errors='replace')
                if name == master.lower():
                    return master_index
                master_index += 1
            offset += field_size + 6
        return None
