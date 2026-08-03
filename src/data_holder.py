from settings_page import settings
from log_stream import write_to_file
import os

class _global():
    # Commonly Accessed Settings
    _settings: dict = {}
    skyrim_folder_path:str = ''
    output_folder_path:str = ''
    output_folder_name:str = ''
    output_folder_joined_path:str = ''
    overwrite_path:str = ''
    plugins_txt_path:str = ''
    mo2_modlist_txt_path:str = ''
    vortex_data_path:str = ''
    vortex_db_path:str = ''
    mod_manager_mode = 0
    update_header = True
    generate_cell_master = False
    persistent_ids = True
    free_non_existent = False
    hash_output = True
    hash_plugins_warn = True
    all_patcher_experimental = False

    # Vars for get_rel_path
    overwrite_path_lower = ''
    overwrite_path_len = 0
    skyrim_folder_path_lower = ''
    skyrim_folder_path_len = 0
    mod_staging_folder_lower = ''
    mod_staging_folder_len = 0

    cwd = os.getcwd()

    # Non-Persistent Variables
    engine_fixes_v7_or_newer = False
    mod_staging_folder = '' #set by vortex scanner after reading state.v2
    plugins = [] #plugins list
    mods_with_seq = {} #{mod: seq_file} mods that have seq files
    vortex_error = -1 #storage for vortex error across classes
    bsa_dict = {}   #{bsa_file: list[mod]} bsa and the mods they contain
    pex_with_getmodbyname: dict[str, set[str]] = {} #{mod: set(pex)} mods with pex with getmodbyname

    def init(settings_widget: settings):
        _global._settings = settings_widget.settings

    def update_from_settings():
        _global.skyrim_folder_path =        _global._settings.get('skyrim_folder_path', '')
        _global.output_folder_path =        _global._settings.get('output_folder_path', '')
        _global.output_folder_name =        _global._settings.get('output_folder_name', "ESLifier Output")
        _global.mod_manager_mode =          _global._settings.get('mod_manager_mode', 0)
        _global.mo2_modlist_txt_path =      _global._settings.get('mo2_modlist_txt_path', '')
        _global.vortex_data_path =          _global._settings.get('vortex_data_path', '')
        _global.vortex_db_path =            os.path.normpath(os.path.join(_global.vortex_data_path, "state.v2"))
        _global.plugins_txt_path =          _global._settings.get('plugins_txt_path', '')
        _global.overwrite_path =            _global._settings.get('overwrite_path', '')
        _global.update_header =             _global._settings.get('update_header', True)
        _global.generate_cell_master =      _global._settings.get('generate_cell_master', True)
        _global.persistent_ids =            _global._settings.get('persistent_ids', True)
        _global.free_non_existent =         _global._settings.get('free_non_existent', False)
        _global.hash_output =               _global._settings.get('hash_output', True)
        _global.hash_plugins_warn =         _global._settings.get('hash_plugins_warn', True)
        _global.all_patcher_experimental =  _global._settings.get('all_patcher_experimental', False)
        _global.output_folder_joined_path = os.path.normpath(os.path.join(_global.output_folder_path, _global.output_folder_name))

        _global.overwrite_path_lower =      _global.overwrite_path.lower()
        _global.overwrite_path_len =        len(_global.overwrite_path)
        _global.skyrim_folder_path_lower =  _global.skyrim_folder_path.lower()
        _global.skyrim_folder_path_len =    len(_global.skyrim_folder_path)
        if _global._settings.get('dump_global', False):
            _global.debug_dump_vars()

    def update_mod_staging_folder_vars():
        _global.mod_staging_folder_lower =  _global.mod_staging_folder.lower()
        _global.mod_staging_folder_len =    len(_global.mod_staging_folder)

    def debug_dump_vars():
        thing = dict(vars(_global))
        string = '\n_global dump:\n'
        for key, value in thing.items():
            if not callable(value) and not key.startswith('_'):
                if isinstance(value, dict):
                    string += str(key) + ":\n"
                    for k, v in value.items():
                        if isinstance(v, list) or isinstance(v, set):
                            string += "    " + str(k) + ": \n"
                            for v2 in v:
                                string += "        " + str(v2) + "\n"
                        else:
                            string += "    " + str(k) + ": " + str(v) + "\n"
                else:
                    string += str(key) + ": " + str(value) + '\n'
        write_to_file(string)

    def get_rel_path(file: str) -> str:
        file_norm = file.replace('\\', os.sep).replace('/', os.sep)

        # ESLifier BSA Extracted
        if 'bsa_extracted' in file_norm:
            if 'bsa_extracted_temp' in file_norm:
                idx = file_norm.find('bsa_extracted_temp')
                if idx != -1:
                    return file_norm[idx + 18:].lstrip(os.sep)
            else:
                idx = file_norm.find('bsa_extracted')
                if idx != -1:
                    return file_norm[idx + 13:].lstrip(os.sep)

        file_lower = file_norm.lower()

        # MO2 Overwrite Path
        if _global.mod_manager_mode == 2 and file_lower.startswith(_global.overwrite_path_lower):
            return file_norm[_global.overwrite_path_len:].lstrip(os.sep)

        # MO2 Mode
        if _global.mod_manager_mode == 2:
            if file_lower.startswith(_global.skyrim_folder_path_lower):
                remainder = file_norm[_global.skyrim_folder_path_len:].lstrip(os.sep)
                idx = remainder.find(os.sep)
                if idx != -1:
                    return remainder[idx+1:]
                return remainder

        # Vortex Mode
        elif _global.mod_manager_mode == 1:
            if file_lower.startswith(_global.mod_staging_folder_lower):
                remainder = file_norm[_global.mod_staging_folder_len:].lstrip(os.sep)
                idx = remainder.find(os.sep)
                if idx != -1:
                    return remainder[idx+1:]
                return remainder

        # Manual Mode
        if file_lower.startswith(_global.skyrim_folder_path_lower):
            return file_norm[_global.skyrim_folder_path_len:].lstrip(os.sep)