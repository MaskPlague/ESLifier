import os
from patchers.fo4_file_patchers import patchers
from patchers.file_defined_patcher_conditions import user_and_master_conditions_class
from log_stream import write_warning
from PyQt6.QtCore import QCoreApplication

def patch_file_conditions(new_file_lower: str, new_file: str, basename: str, form_id_map: dict,
                          additional_conditions: user_and_master_conditions_class, encoding: str):
    if 'facegeom' in new_file_lower and new_file_lower.endswith('.nif'):                    # FaceGeom mesh patching
        patchers.facegeom_mesh_patcher(basename, new_file, form_id_map)
    elif new_file_lower.endswith('.ini'):
        if new_file_lower.endswith(('_distr.ini', '_swap.ini')):                            # PO3's SPID, BOS,
            patchers.ini_formid_sep_plugin_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\robco_patcher\\' in new_file_lower:                                         # 
            patchers.ini_skypatcher_and_robcopatcher_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        else:                                    
            patched = additional_conditions.check_conditions(basename, new_file, new_file_lower, form_id_map, encoding_method=encoding)
            if not patched:                                           
                write_warning(QCoreApplication.translate("patcher_conditions", "Possible missing patcher for: ") + new_file)
    elif new_file_lower.endswith('.json'):
        if new_file_lower.endswith(('config.json', 'keybinds.json')) and 'mcm\\config' in new_file_lower: # MCM?
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\plugins\\transfersettlements\\' in new_file_lower:                          # Transfer Settlements
            patchers.json_transfer_settlements_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\gsp\\' in new_file_lower:                                                   # Generic Synthesis Patcher
            patchers.json_generic_formid_sep_plugin_patcher(basename, new_file, form_id_map, sep= ':', encoding_method=encoding) 
        else:
            patched = additional_conditions.check_conditions(basename, new_file, new_file_lower, form_id_map, encoding_method=encoding)
            if not patched:                                           
                write_warning(QCoreApplication.translate("patcher_conditions", "Possible missing patcher for: ") + new_file)
    elif new_file_lower.endswith('.pex'):                                                   # Compiled script patching
        patchers.pex_patcher(basename, new_file, form_id_map, endian='little')
    else:
        patched = additional_conditions.check_conditions(basename, new_file, new_file_lower, form_id_map, encoding_method=encoding)
        if not patched:                                           
            write_warning(QCoreApplication.translate("patcher_conditions", "Possible missing patcher for: ") + new_file)
