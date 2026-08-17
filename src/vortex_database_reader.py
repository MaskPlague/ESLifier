import json
import plyvel
from data_holder import _global
from log_stream import write_to_file

class ReadState(Enum):
    SUCCESS_DB = 1
    SUCCESS_STATE = 2
    ERROR_DB_LOCKED_EXTENSION_MISSING = 4
    ERROR_DB_LOCKED_EXTENSION_UNREACHABLE = 5

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
        end_index = start_string.rindex("###", 0, len(start_string)-2)
        key = start_string[end_index+3:-3].encode()
        start_string = start_string[:end_index+3]
        start_bytes = start_string.encode()
        with plyvel.DB(_global.vortex_db_path) as db:
            prefixed = db.prefixed_db(start_bytes)
            return prefixed.get(key, b'').decode()
        return None

    def is_readable() -> (int|Exception):
        try:
            with plyvel.DB(_global.vortex_db_path) as db:
                db.close()
            return 1
        except plyvel.IOError:
            return 0
        except Exception as e:
            return e