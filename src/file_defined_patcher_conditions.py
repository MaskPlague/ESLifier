import json5 as json
import os
from typing import Callable, Any
from file_patchers import patchers

class user_and_master_conditions_class():
    def __init__(self):
        user_conditions = self.get_conditions("ESLifier_Data/user_patch_conditions.json")
        master_conditions = self.get_conditions("ESLifier_Data/master_patch_conditions.json")
        self.user_and_master_conditions = user_conditions
        self.user_and_master_conditions.update(master_conditions)

    def get_conditions(self, filename):
        try:
            if not os.path.exists(filename):
                with open(filename, "w", encoding="utf-8") as f:
                    f.write('{"conditions": []}')
                return {}
            else:
                with open(filename, "r", encoding="utf-8") as f:
                    file_data: dict[str] = json.load(f)
                    conditions_data: list[dict[str, str | int]] = file_data.get("conditions", [])
        except:
            return {}
        
        ini_conditions = []
        json_conditions = []
        toml_conditions = []
        yml_conditions = []
        txt_conditions = []
        other_conditions = []

        conditions_dict: dict[str, list[dict[str, str | Callable[..., Any]]]] = {
            "ini": ini_conditions,
            "json": json_conditions,
            "toml": toml_conditions,
            "yml": yml_conditions,
            "txt": txt_conditions,
            "other": other_conditions
        }

        patcher_methods = {
            "ini_fid_tilde_plugin": patchers.ini_formid_tilde_plugin_patcher,
            "ini_eq_plugin_sep_fid": patchers.ini_eq_plugin_sep_formid_patcher,
            "ini_experience_knotwork": patchers.ini_experience_knotwork_patcher,
            "ini_payload_interpreter_dtrys_key_utils": patchers.ini_payload_interpreter_dtrys_key_utils_patcher,
            "json_generic_plugin_sep_formid": patchers.json_generic_plugin_sep_formid_patcher,
            "json_generic_formid_sep_plugin": patchers.json_generic_formid_sep_plugin_patcher,
            "json_jcontainer": patchers.json_jcontainer_patcher,
            -1: None, # No patching needed, ignore file
        }

        for conditions in conditions_data:
            try:
                extension = conditions["extension"].lower()
                conditions_dict.get(extension, conditions_dict["other"]).append({
                    "contains": os.path.normpath(conditions.get("contains", "").lower().strip()),
                    "endswith": os.path.normpath(conditions.get("endswith", "").lower().strip()),
                    "separator": conditions.get("separator", "").lower().strip(),
                    "patcher": patcher_methods[conditions["patcher"]]})
            except Exception as e:
                print(f"A condtion in {os.path.basename(filename)} is missing required fields or has an invalid patcher method.")
                print(e)
        return conditions_dict

    def check_conditions(self, basename, file, file_lower, form_id_map):
        conditions_list = self.user_and_master_conditions.get(os.path.splitext(file_lower)[1].removeprefix('.'), [])
        for condition_set in conditions_list:
            contains = condition_set["contains"]
            endswith = condition_set["endswith"]
            contains_flag = True
            endswith_flag = True
            if contains != ".":
                contains_flag = contains in file_lower
            if endswith != ".":
                endswith_flag = file_lower.endswith(endswith)
            if contains_flag and endswith_flag:
                patcher_method = condition_set["patcher"]
                if patcher_method == None: # if patcher == -1 then it is a file that needs no patching and can be skipped.
                    return True
                separator_symbol = condition_set.get("separator", "")
                if separator_symbol != "":
                    try:
                        patcher_method(basename, file, form_id_map, sep=condition_set["separator"], encoding_method="utf-8")
                    except Exception as e:
                        exception_type = type(e)
                        if exception_type == UnicodeDecodeError:
                            patcher_method(basename, file, form_id_map, encoding_method="ansi")
                        else:
                            print(f'!Error: Failed to patch file: {file}')
                            print(e)    
                else:
                    try:
                        patcher_method(basename, file, form_id_map, encoding_method="utf-8")
                    except Exception as e:
                        exception_type = type(e)
                        if exception_type == UnicodeDecodeError:
                            patcher_method(basename, file, form_id_map, encoding_method="ansi")
                        else:
                            print(f'!Error: Failed to patch file: {file}')
                            print(e)    
                return True
        return False
