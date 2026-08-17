import json
import plyvel
import urllib.request
import json
import os
import time

from enum import Enum

from data_holder import _global
from log_stream import write_to_file

class ReadState(Enum):
    SUCCESS_DB = 1
    SUCCESS_STATE = 2
    ERROR_DB_LOCKED_EXTENSION_MISSING = 4
    ERROR_DB_LOCKED_EXTENSION_UNREACHABLE = 5

class VortexDBParser:
    state:dict = {}
    last_query = None
    def get_section_from_db(start_string: str) -> dict:
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

    def get_key_value_from_db(start_string: str):
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

    def get_section_from_state(start_string:str):
        keys = [key for key in start_string.split("###") if key]
        local_state = VortexDBParser.state
        for key in keys:
            local_state = local_state.get(key, {})
        return local_state

    def get_key_value_from_state(start_string:str):
        keys = [key for key in start_string.split("###") if key]
        local_state = VortexDBParser.state
        for key in keys:
            local_state = local_state.get(key, {})
        return local_state if local_state else None

    def get_section(string:str):
        pass

    def get_key_value(string:str):
        pass
    
    def get_live_vortex_state():
        with open(os.path.join(_global.vortex_data_path, 'plugins/ESLifier Vortex State Getter/port.txt'), 'r') as f:
            port = f.read().strip()

        url = f"http://127.0.0.1:{port}/export-state"
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except Exception as e:
            write_to_file("Failed to get state from Vortex during url request to extension:")
            write_to_file(str(e))
            return ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE

    def is_readable() -> (int|Exception):
        ret_val = None
        try:
            with plyvel.DB(_global.vortex_db_path) as db:
                db.close()
            VortexDBParser.get_section = VortexDBParser.get_section_from_db
            VortexDBParser.get_key_value = VortexDBParser.get_key_value_from_db
            write_to_file("Vortex is closed and DB is readable, using Vortex DB.")
            ret_val = ReadState.SUCCESS_DB
        except plyvel.IOError:
            ret_val = ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE
        except Exception as e:
            ret_val =  e

        if ret_val != ReadState.SUCCESS_DB:
            # if we haven't successfully queried before or we queried more than 5 seconds ago then get the state from Vortex
            if not VortexDBParser.last_query or time.monotonic() - VortexDBParser.last_query >= 5:
                extension = os.path.join(_global.vortex_data_path, 'plugins/ESLifier Vortex State Getter/')
                port_file = os.path.join(extension, 'port.txt')
                VortexDBParser.state = {}
                if os.path.exists(port_file):
                    local_state:dict = VortexDBParser.get_live_vortex_state()
                    if local_state:
                        write_to_file("Successfully obtained Vortex state via the Vortex extension.")
                        VortexDBParser.state = local_state
                        VortexDBParser.get_section = VortexDBParser.get_section_from_state
                        VortexDBParser.get_key_value = VortexDBParser.get_key_value_from_state
                        VortexDBParser.last_query = time.monotonic()
                        return ReadState.SUCCESS_STATE
                    elif isinstance(ret_val, Exception):
                        write_to_file("Error occurred during attempt to read Vortex's Database files:")
                        write_to_file(ret_val)
                        write_to_file("Additionally, the Vortex extension failed to return Vortex's Redux store state info.")
                        return ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE
                elif os.path.exists(extension):
                    return ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE
                else:
                    return ReadState.ERROR_DB_LOCKED_EXTENSION_MISSING
            else:
                if VortexDBParser.state:
                    write_to_file(f"Last queried {time.monotonic() - VortexDBParser.last_query} seconds ago, using cached Vortex state")
                    VortexDBParser.get_section = VortexDBParser.get_section_from_state
                    VortexDBParser.get_key_value = VortexDBParser.get_key_value_from_state
                    return ReadState.SUCCESS_STATE
        return ret_val

    