from settings_page import settings
import os

class _global():
    # Commonly Accessed Settings
    _settings: dict = {}
    skyrim_folder_path = ''
    output_folder_path = ''
    output_folder_name = ''
    output_folder_joined_path = ''
    overwrite_path = ''
    plugins_txt_path = ''
    mo2_modlist_txt_path = ''
    vortex_data_path = ''
    mod_manager_mode = 0
    update_header = True
    generate_cell_master = False
    persistent_ids = True
    free_non_existent = False
    hash_output = True
    hash_plugins_warn = True
    all_patcher_experimental = False

    # Non-Persistent Variables
    mod_staging_folder = '' #set by vortex scanner after reading state.v2
    plugins = [] #plugins list
    mods_with_seq = [] #mods that have seq files
    vortex_error = -1 #storage for vortex error across classes
    bsa_dict = {}

    def init(settings_widget: settings):
        _global._settings = settings_widget.settings

    def update_from_settings():
        _global.skyrim_folder_path =          _global._settings.get('skyrim_folder_path', '')
        _global.output_folder_path =          _global._settings.get('output_folder_path', '')
        _global.output_folder_name =          _global._settings.get('output_folder_name', "ESLifier Output")
        _global.mod_manager_mode =            _global._settings.get('mod_manager_mode', 0)
        _global.mo2_modlist_txt_path =        _global._settings.get('mo2_modlist_txt_path', '')
        _global.vortex_data_path =            _global._settings.get('vortex_data_path', '')
        _global.plugins_txt_path =            _global._settings.get('plugins_txt_path', '')
        _global.overwrite_path =              _global._settings.get('overwrite_path', '')
        _global.update_header =               _global._settings.get('update_header', True)
        _global.generate_cell_master =        _global._settings.get('generate_cell_master', True)
        _global.persistent_ids =              _global._settings.get('persistent_ids', True)
        _global.free_non_existent =           _global._settings.get('free_non_existent', False)
        _global.hash_output =                 _global._settings.get('hash_output', True)
        _global.hash_plugins_warn =           _global._settings.get('hash_plugins_warn', True)
        _global.all_patcher_experimental =    _global._settings.get('all_patcher_experimental', False)
        _global.output_folder_joined_path =   os.path.normpath(os.path.join(_global.output_folder_path, _global.output_folder_name))

    def get_rel_path(file: str) -> str:
        if 'bsa_extracted' in file:
            if 'bsa_extracted_temp' in file:
                start = os.path.join(os.getcwd(), 'bsa_extracted_temp/')
            else:
                start = os.path.join(os.getcwd(), 'bsa_extracted/')
            rel_path = os.path.normpath(os.path.relpath(file, start))
        elif _global.mod_manager_mode == 2 and file.lower().startswith(_global.overwrite_path.lower()):
            rel_path = os.path.normpath(os.path.relpath(file, _global.overwrite_path))
        else:
            if _global.mod_manager_mode == 2:   # MO2
                parts = os.path.normpath(os.path.relpath(file, _global.skyrim_folder_path)).split(os.sep)
                if len(parts) != 1:
                    parts = parts[1:]
                rel_path = os.path.join(*parts)
            elif _global.mod_manager_mode == 1: # Vortex
                #if file.startswith(_global.mod_staging_folder):
                parts = os.path.normpath(os.path.relpath(file, _global.mod_staging_folder)).split(os.sep)
                #else: #Disabled this since we are not currently using skyrim_folder_path
                #    parts = os.path.normpath(os.path.relpath(file, _global.skyrim_folder_path)).split(os.sep)
                if len(parts) != 1:
                    parts = parts[1:]
                rel_path = os.path.join(*parts)
            else:                               # Manual?
                rel_path = os.path.normpath(os.path.relpath(file, _global.skyrim_folder_path))
        return rel_path