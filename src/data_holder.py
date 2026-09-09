from log_stream import write_to_file
import os

from PyQt6.QtCore import QCoreApplication

#from typing import TYPE_CHECKING
#if TYPE_CHECKING:
#    from settings_page import settings
GAME_MODE = "SSE"

def update_game_globals():
    global VERBOSE_GAME_NAME, SHORT_GAME_NAME, VORTEX_GAME_NAME, MO2_GAME_NAME, GAME_ESM_NAME, PROGRAM_NAME, EXE_NAME
    global GAME_ARCHIVE_TYPE, GAME_ARCHIVE_EXTENSION, NEXUS_FILES_TAB_URL, GITHUB_MASTER_JSONS_URL
    VERBOSE_GAME_NAME = "Skyrim Special Edition"        if GAME_MODE == "SSE" else "Fallout 4"
    SHORT_GAME_NAME = "Skyirm"                          if GAME_MODE == "SSE" else "Fallout"
    VORTEX_GAME_NAME = "skyrimse"                       if GAME_MODE == "SSE" else "fallout4"
    MO2_GAME_NAME = "Skyrim Special Edition"            if GAME_MODE == "SSE" else "Fallout 4"
    GAME_ESM_NAME = "Skyrim.esm"                        if GAME_MODE == "SSE" else "Fallout4.esm"

    PROGRAM_NAME = "ESLifier"                           if GAME_MODE == "SSE" else "ESLifier-FO4"
    EXE_NAME = PROGRAM_NAME + ".exe"
    GAME_ARCHIVE_TYPE = "BSA"                           if GAME_MODE == "SSE" else "BA2"
    GAME_ARCHIVE_EXTENSION = "." + GAME_ARCHIVE_TYPE.lower()

    NEXUS_FILES_TAB_URL = ("https://www.nexusmods.com/skyrimspecialedition/mods/145168?tab=files"
                                                        if GAME_MODE == "SSE" else
                           "https://www.nexusmods.com/fallout4/mods/UNK?tab=files")
    GITHUB_MASTER_JSONS_URL = ("https://raw.githubusercontent.com/MaskPlague/ESLifier/refs/heads/main/master_sse_jsons/"
                                                        if GAME_MODE == "SSE" else
                               "https://raw.githubusercontent.com/MaskPlague/ESLifier/refs/heads/main/master_fo4_jsons/")
    
    global ESLIFIER_DATA_FOLDER, CELL_IDS_FOLDER, FORM_ID_MAPS_FOLDER, ESLIFIER_LOG_FILE
    global BLACKLIST_JSON, CELL_CHANGED_JSON, CELL_MASTER_INFO_JSON, COMPACTED_AND_PATCHED_JSON, DEPENDENCY_DICTIONARY_JSON
    global DLL_DICT_JSON, ESL_FLAGGED_JSON, EXTRACTED_GAME_ARCHIVE_JSON, FILE_MASTERS_JSON, FLAG_DICTIONARY_JSON, IGNORED_FILES_JSON
    global MASTER_BYTE_DATA_JSON, MAXED_MASTERS_JSON, MISSING_GAME_AS_MASTER_JSON, NEW_FILE_HASHES_JSON, ORIGINAL_FILES_JSON
    global PREVIOUSLY_COMPACTED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON, SETTINGS_JSON, WINNING_FILES_DICT_JSON, WINNING_FILE_HISTORY_DICT_JSON

    ESLIFIER_DATA_FOLDER = "ESLifier_Data/"             if GAME_MODE == "SSE" else "ESLifier_FO4_Data/"

    CELL_IDS_FOLDER =                                   ESLIFIER_DATA_FOLDER + "Cell_IDs"
    FORM_ID_MAPS_FOLDER =                               ESLIFIER_DATA_FOLDER + "Form_ID_Maps"
    ESLIFIER_LOG_FILE =                                 ESLIFIER_DATA_FOLDER + "ESLifier.log"

    BLACKLIST_JSON =                                    ESLIFIER_DATA_FOLDER + "blacklist.json"
    CELL_CHANGED_JSON =                                 ESLIFIER_DATA_FOLDER + "cell_changed.json"
    CELL_MASTER_INFO_JSON =                             ESLIFIER_DATA_FOLDER + "cell_master_info.json"
    COMPACTED_AND_PATCHED_JSON =                        ESLIFIER_DATA_FOLDER + "compacted_and_patched.json"
    DEPENDENCY_DICTIONARY_JSON =                        ESLIFIER_DATA_FOLDER + "dependency_dictionary.json"
    DLL_DICT_JSON =                                     ESLIFIER_DATA_FOLDER + "dll_dict.json"
    ESL_FLAGGED_JSON =                                  ESLIFIER_DATA_FOLDER + "esl_flagged.json"
    EXTRACTED_GAME_ARCHIVE_JSON =                       ESLIFIER_DATA_FOLDER + "extracted_bsa.json"
    FILE_MASTERS_JSON =                                 ESLIFIER_DATA_FOLDER + "file_masters.json"
    FLAG_DICTIONARY_JSON =                              ESLIFIER_DATA_FOLDER + "flag_dictionary.json"
    IGNORED_FILES_JSON =                                ESLIFIER_DATA_FOLDER + "ignored_files.json"
    MASTER_BYTE_DATA_JSON =                             ESLIFIER_DATA_FOLDER + "master_byte_data.json"
    MAXED_MASTERS_JSON =                                ESLIFIER_DATA_FOLDER + "maxed_masters.json"
    MISSING_GAME_AS_MASTER_JSON =                       ESLIFIER_DATA_FOLDER + "missing_game_as_master.json"
    NEW_FILE_HASHES_JSON =                              ESLIFIER_DATA_FOLDER + "new_file_hashes.json"
    ORIGINAL_FILES_JSON =                               ESLIFIER_DATA_FOLDER + "original_files.json"
    PREVIOUSLY_COMPACTED_JSON =                         ESLIFIER_DATA_FOLDER + "previously_compacted.json"
    PREVIOUSLY_ESL_FLAGGED_JSON =                       ESLIFIER_DATA_FOLDER + "previously_esl_flagged.json"
    SETTINGS_JSON =                                     ESLIFIER_DATA_FOLDER + "settings.json"
    WINNING_FILES_DICT_JSON =                           ESLIFIER_DATA_FOLDER + "winning_files_dict.json"
    WINNING_FILE_HISTORY_DICT_JSON =                    ESLIFIER_DATA_FOLDER + "winning_file_history_dict.json"
update_game_globals()

class _global():
    # Commonly Accessed Settings
    _settings: dict = {}
    game_folder_path:str = ''
    output_folder_path:str = ''
    output_folder_name:str = ''
    output_folder_joined_path:str = ''
    mo2_base_path:str = ''
    mo2_overwrite_path:str = ''
    mo2_profile:str = ''
    mo2_profiles_dir:str = ''
    plugins_txt_path:str = ''
    mo2_modlist_txt_path:str = ''
    mo2_mods_folder:str = ''
    vortex_data_path:str = ''
    vortex_db_path:str = ''
    vortex_restore_backups = True
    mod_manager_mode = 0
    update_header = True
    generate_cell_master = False
    persistent_ids = True
    free_non_existent = False
    hash_output = True
    hash_plugins_warn = True
    all_patcher_experimental = False

    # Vars for get_rel_path
    mo2_overwrite_path_lower = ''
    mo2_overwrite_path_len = 0
    game_folder_path_lower = ''
    game_folder_path_len = 0
    mo2_mods_folder_lower = ''
    mo2_mods_folder_len = 0
    mod_staging_folder_lower = ''
    mod_staging_folder_len = 0
    output_folder_joined_path_lower = ''
    output_folder_joined_path_len = 0
    bsa_extracted_path_len = 0
    bsa_extracted_temp_path_len = 0

    cwd = ''
    folders_grabbed = False

    # Non-Persistent Variables
    engine_fixes_v7_or_newer = False
    mod_staging_folder = '' #set by vortex scanner after reading state.v2
    plugins = [] #plugins list
    mods_with_seq = {} #{mod: seq_file} mods that have seq files
    vortex_error = None #storage for vortex error across classes
    mo2_error = None #storage for mo2 error across classes
    game_archive_dict = {}   #{bsa_file: list[mod]} bsa and the mods they contain
    pex_with_getmodbyname: dict[str, set[str]] = {} #{mod: set(pex)} mods with pex with getmodbyname

    def init(settings_widget, vortex, mo2):
        _global._settings = settings_widget.settings
        _global.Vortex = vortex
        _global.MO2 = mo2
        _global.cwd = os.getcwd()

    def setTabsDisabled(a0:bool=False):
        pass

    def update_from_settings():     
        _global.output_folder_path =                _global._settings.get('output_folder_path', '')
        _global.output_folder_name =                _global._settings.get('output_folder_name', "ESLifier Output")
        _global.mod_manager_mode =                  _global._settings.get('mod_manager_mode', 0)
        _global.mo2_base_path =                     _global._settings.get('mo2_base_path', '')
        _global.mo2_profile =                       _global._settings.get('mo2_profile', 'Default')
        _global.mo2_profiles_dir =                  _global._settings.get('mo2_profiles_dir')
        _global.vortex_data_path =                  _global._settings.get('vortex_data_path', '')
        _global.vortex_db_path =                    os.path.normpath(os.path.join(_global.vortex_data_path, "state.v2"))
        if _global.mod_manager_mode == 0:
            _global.game_folder_path =              _global._settings.get('skyrim_folder_path', '')
            _global.plugins_txt_path =              _global._settings.get('plugins_txt_path', '')
        _global.vortex_restore_backups =            _global._settings.get('vortex_restore_backups', True)
        _global.update_header =                     _global._settings.get('update_header', True)
        _global.generate_cell_master =              _global._settings.get('generate_cell_master', True)
        _global.persistent_ids =                    _global._settings.get('persistent_ids', True)
        _global.free_non_existent =                 _global._settings.get('free_non_existent', False)
        _global.hash_output =                       _global._settings.get('hash_output', True)
        _global.hash_plugins_warn =                 _global._settings.get('hash_plugins_warn', True)
        _global.all_patcher_experimental =          _global._settings.get('all_patcher_experimental', False)
        _global.output_folder_joined_path =         os.path.normpath(os.path.join(_global.output_folder_path, _global.output_folder_name))
        _global.output_folder_joined_path_lower =   _global.output_folder_joined_path.lower()
        _global.output_folder_joined_path_len =     len(_global.output_folder_joined_path)

        _global.game_folder_path_lower =          _global.game_folder_path.lower()
        _global.game_folder_path_len =            len(_global.game_folder_path)

        _global.bsa_extracted_path_len =            len(os.path.normpath(os.path.join(_global.cwd, 'bsa_extracted')))
        _global.bsa_extracted_temp_path_len =       len(os.path.normpath(os.path.join(_global.cwd, 'bsa_extracted_temp')))

        _global.folders_grabbed = False
        if _global._settings.get('dump_global', False):
            _global.debug_dump_vars()

    def update_vortex_vars():
        _global.mod_staging_folder_lower =          _global.mod_staging_folder.lower()
        _global.mod_staging_folder_len =            len(_global.mod_staging_folder)

        _global.game_folder_path_lower =          _global.game_folder_path.lower()
        _global.game_folder_path_len =            len(_global.game_folder_path)
        _global.folders_grabbed = True

    def update_mo2_vars():
        _global.mo2_mods_folder_lower =             _global.mo2_mods_folder.lower()
        _global.mo2_mods_folder_len =               len(_global.mo2_mods_folder)

        _global.mo2_overwrite_path_lower =          _global.mo2_overwrite_path.lower()
        _global.mo2_overwrite_path_len =            len(_global.mo2_overwrite_path)
        _global.folders_grabbed = True

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
                elif isinstance(value, (list, set)):
                    string += str(key) + ":\n"
                    for item in value:
                        string += "    " + str(item) + ": \n"
                else:
                    string += str(key) + ": " + str(value) + '\n'
        write_to_file(string)

    def get_paths():
        if not _global.folders_grabbed:
            if _global.mod_manager_mode == 1:
                return _global.Vortex.get_folders()
            elif _global.mod_manager_mode == 2:
                return _global.MO2.get_instance_paths()
            else:
                _global.folders_grabbed = True
        return True

    def get_rel_path(file: str) -> str:
        if not _global.folders_grabbed:
            if not _global.get_paths():
                RuntimeError(QCoreApplication.translate("Global", "Failed to get necessary paths, see ESLifier.log"))
        file_norm = file.replace('\\', os.sep).replace('/', os.sep)

        # ESLifier BSA Extracted
        if 'bsa_extracted' in file_norm:
            if 'bsa_extracted_temp' in file_norm:
                return file_norm[_global.bsa_extracted_temp_path_len:].lstrip(os.sep)
            else:
                return file_norm[_global.bsa_extracted_path_len:].lstrip(os.sep)

        file_lower = file_norm.lower()

        # MO2 Mode
        if _global.mod_manager_mode == 2:
            # Overwrite
            if file_lower.startswith(_global.mo2_overwrite_path_lower):
                return file_norm[_global.mo2_overwrite_path_len:].lstrip(os.sep)
            # Mods Folder
            elif file_lower.startswith(_global.mo2_mods_folder_lower):
                remainder = file_norm[_global.mo2_mods_folder_len:].lstrip(os.sep)
                idx = remainder.find(os.sep)
                if idx != -1:
                    return remainder[idx+1:]
                return remainder

        # Vortex Mode
        if _global.mod_manager_mode == 1:
            # SSE Data Folder Path
            if _global.game_folder_path and file_lower.startswith(_global.game_folder_path_lower):
                return file_norm[_global.game_folder_path_len:].lstrip(os.sep)
            # Mod Staging Folder
            elif file_lower.startswith(_global.mod_staging_folder_lower):
                remainder = file_norm[_global.mod_staging_folder_len:].lstrip(os.sep)
                idx = remainder.find(os.sep)
                if idx != -1:
                    return remainder[idx+1:]
                return remainder

        # Manual Mode
        if _global.mod_manager_mode == 0:
            if file_lower.startswith(_global.game_folder_path_lower):
                return file_norm[_global.game_folder_path_len:].lstrip(os.sep)

        # Files In Output (renamed facegeom)
        if file_lower.startswith(_global.output_folder_joined_path_lower):
            return file_norm[_global.output_folder_joined_path_len:].lstrip(os.sep)


        raise RuntimeError(
            QCoreApplication.translate(
                "Global", 
                "No relative file path method for file: %1, aborting program execution for safety. Report this to the GitHub with your settings.json."
                ).replace("%1", file)
            )