import json5 as json
import os
from typing import Callable, Any
from file_patchers import patchers

class user_and_master_conditions_class():
    def __init__(self):
        master_conditions = self.get_conditions("ESLifier_Data/master_patch_conditions.json")
        user_conditions = self.get_conditions("ESLifier_Data/user_patch_conditions.json")
        self.user_and_master_conditions = master_conditions
        for extension, conditions in user_conditions.items():
            self.user_and_master_conditions[extension].extend(conditions)

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
        except Exception as e:
            print(f"!Error: Issue in conditions file {filename}:")
            print(e)
            return {}
        
        ini_conditions = []
        json_conditions = []
        toml_conditions = []
        yaml_conditions = []
        yml_conditions = []
        txt_conditions = []
        other_conditions = []

        conditions_dict: dict[str, list[dict[str, str | Callable[..., Any]]]] = {
            "ini": ini_conditions,
            "json": json_conditions,
            "toml": toml_conditions,
            "yaml": yaml_conditions,
            "yml": yml_conditions,
            "txt": txt_conditions,
            "other": other_conditions
        }

        patcher_methods = {
            "ini_formid_sep_plugin": patchers.ini_formid_sep_plugin_patcher,
            "ini_plugin_sep_formid": patchers.ini_plugin_sep_formid_patcher,
            "ini_eq_plugin_sep_formid": patchers.ini_eq_plugin_sep_formid_patcher,
            "ini_experience_and_knotwork": patchers.ini_experience_and_knotwork_patcher,
            "ini_payload_interpreter_and_dtrys_key_utils": patchers.ini_payload_interpreter_and_dtrys_key_utils_patcher,
            "json_generic_plugin_sep_formid": patchers.json_generic_plugin_sep_formid_patcher,
            "json_generic_formid_sep_plugin": patchers.json_generic_formid_sep_plugin_patcher,
            "json_generic_key_fid_sep_plugin": patchers.json_generic_key_fid_sep_plugin_patcher,
            "json_generic_key_plugin_sep_fid": patchers.json_generic_key_plugin_sep_fid_patcher,
            "json_storage_util_data": patchers.json_storage_util_data_patcher,
            "json_jcontainer": patchers.json_jcontainer_patcher,
            "toml_loki_and_tdm": patchers.toml_loki_and_tdm_patcher,
            -1: None, # No patching needed, ignore file
        }

        for conditions in conditions_data:
            try:
                extension = conditions["extension"].lower()
                conditions_dict.get(extension, conditions_dict["other"]).append({
                    "contains": os.path.normpath(conditions.get("contains", "").lower().strip()),
                    "endswith": os.path.normpath(conditions.get("endswith", "").lower().strip()),
                    "separator": conditions.get("separator", "").lower().strip(),
                    "int_type": conditions.get("int_type", False),
                    "patcher": patcher_methods[conditions["patcher"]]})
            except Exception as e:
                print(f"A condtion in {os.path.basename(filename)} is missing required fields or has an invalid patcher method.")
                print(e)
        return conditions_dict

    def check_conditions(self, basename, file, file_lower, form_id_map):
        conditions_list = self.user_and_master_conditions.get(os.path.splitext(file_lower)[1].removeprefix('.'), self.user_and_master_conditions.get("other", []))
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
                int_type = condition_set.get("int_type", False)
                args = [basename, file, form_id_map]
                kwargs = {"encoding_method": "utf-8"}
                if separator_symbol != "":
                    kwargs.update({"sep": separator_symbol})
                if int_type:
                    kwargs.update({"int_type": True})
                try:
                    patcher_method(*args, **kwargs)
                except Exception as e:
                    exception_type = type(e)
                    if exception_type == UnicodeDecodeError:
                        kwargs.update({"encoding_method": "ansi"})
                        patcher_method(*args, **kwargs)
                    else:
                        print(f'!Error: Failed to patch file: {file}')
                        print(e)    
                return True
        return False
