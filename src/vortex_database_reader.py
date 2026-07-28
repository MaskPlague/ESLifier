import json
import plyvel
from data_holder import _global

class VortexDBParser:
    def get_section(start_string: str) -> dict:
        if not start_string.endswith('###'):
            start_string += "###"
        start_bytes = start_string.encode()
        start_string_len = len(start_string)
        data = {}
        with plyvel.DB(_global.vortex_db_path) as db:
            for k, v in db.iterator(prefix=start_bytes):
                try:
                    key_string = k.decode()[start_string_len:]
                    key_parts = key_string.strip().split("###")
                    current = data
                    for part in key_parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[key_parts[-1]] = json.loads(v.decode())     
                except Exception:
                    continue
        return data

    def get_key_value(start_string: str):
        if not start_string.endswith('###'):
            start_string += "###"
        start_bytes = start_string.encode()
        with plyvel.DB(_global.vortex_db_path) as db:
            for _, value in db.iterator(prefix=start_bytes):
                return value.decode()

    def is_readable() -> (int|Exception):
        try:
            with plyvel.DB(_global.vortex_db_path) as db:
                db.close()
            return 1
        except plyvel.IOError:
            return 0
        except Exception as e:
            return e