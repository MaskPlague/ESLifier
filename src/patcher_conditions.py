import os
from file_patchers import patchers

def patch_file_conditions(new_file_lower, new_file, basename, form_id_map, form_id_rename_map, encoding):
    if new_file_lower.endswith('.ini'):
        if new_file_lower.endswith(('_distr.ini', '_kid.ini', '_swap.ini', '_enbl.ini',     # PO3's SPID, KID, BOS, ENBL
                                    '_desc.ini', '_flm.ini', '_llos.ini', '_ipm.ini', '_mus.ini')): # Description Framework, FLM, LLOS, IPM, MTD
            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'seasons\\' in new_file_lower:                                                 # Po3's Seasons of Skyrim
            patchers.ini_season_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'payloadinterpreter\\' in new_file_lower:                                      # Payload Interpreter
            patchers.ini_pi_dtry_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'dtrykeyutil\\' in new_file_lower:                                             # DtryKeyUtil
            patchers.ini_pi_dtry_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'muimpactframework\\' in new_file_lower or 'muskeletoneditor\\' in new_file_lower: # MU
            patchers.ini_mu_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\poisebreaker_' in new_file_lower:                                            # Poise Breaker
            patchers.ini_eq_plugin_sep_fid_patcher(basename, new_file, form_id_map, sep=':', encoding_method=encoding)
        elif 'skypatcher\\' in new_file_lower:                                              # Sky Patcher
            patchers.ini_sp_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'valhallacombat\\' in new_file_lower:                                          # Valhalla Combat
            patchers.ini_eq_plugin_sep_fid_patcher(basename, new_file, form_id_map, sep='|', encoding_method=encoding)
        elif '\\autobody\\' in new_file_lower:                                              # AutoBody
            patchers.ini_ab_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\vsu\\' in new_file_lower:                                                     # VSU
            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'completionistdata\\' in new_file_lower:                                       # Completionist
            patchers.ini_completionist_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'kreate\\presets' in new_file_lower:                                           # KreatE
            patchers.ini_kreate_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif new_file_lower.endswith(('thenewgentleman.ini', 'thenewgentleman5.ini', '_tng.ini')): # The New Gentleman
            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif new_file_lower.endswith('rememberlockpickangle.ini'):                          # Remember Lockpicking Angle - Updated
            patchers.ini_rla_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'plugins\\experience\\' in new_file_lower:                                     # Experience
            patchers.ini_exp_knt_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\lightplacer\\' in new_file_lower:                                           # Light Placer
            patchers.ini_0xfid_tilde_plugin_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif 'plugins\\knotwork\\' in new_file_lower:                                       # Knotwork
            patchers.ini_exp_knt_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif new_file_lower.endswith('\\simpleedgeremoverng.ini'):                          # Simple Edge Glow Remover NG
            patchers.ini_eq_plugin_sep_fid_patcher(basename, new_file, form_id_map, sep='|',encoding_method=encoding)
        else:                                                                               
            print(f'Warn: Possible missing patcher for: {new_file}')
    elif new_file_lower.endswith('_conditions.txt'):                                        # Dynamic Animation Replacer
        patchers.dar_patcher(basename, new_file, form_id_map, encoding_method=encoding)
    elif new_file_lower.endswith('.json'):
        if new_file_lower.endswith(('config.json', 'user.json')) and 'animationreplacer\\' in new_file_lower: # Open Animation Replacer
            patchers.json_oar_patcher(basename, new_file, form_id_map)
        elif new_file_lower.endswith(('config.json', 'keybinds.json')) and 'mcm\\config' in new_file_lower: # MCM helper
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif new_file_lower.endswith('_srd.json'):                                          # Sound Record Distributor JSON
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif '\\storageutildata\\' in new_file_lower:                                       # PapyrusUtil's StorageDataUtil
            patchers.json_sud_patcher(basename, new_file, form_id_map)
        elif '\\dynamicstringdistributor\\' in new_file_lower:                              # Dynamic String Distributor
            patchers.json_dsd_patcher(basename, new_file, form_id_map)
        elif '\\dkaf\\' in new_file_lower:                                                  # Dynamic Key Activation Framework NG
            patchers.json_dkaf_patcher(basename, new_file, form_id_map)
        elif '\\dynamicarmorvariants\\' in new_file_lower:                                  # Dynamic Armor Variants
            patchers.json_dav_patcher(basename, new_file, form_id_map)
        elif '\\ied\\' in new_file_lower:                                                   # Immersive Equipment Display
            patchers.json_ied_patcher(basename, new_file, form_id_map)
        elif '\\creatures.d\\' in new_file_lower:                                           # Creature Framework
            patchers.json_cf_sr_patcher(basename, new_file, form_id_map)
        elif '\\spell research\\' in new_file_lower or '\\spellresearch' in new_file_lower: # Spell Research
            patchers.json_cf_sr_patcher(basename, new_file, form_id_map)
        elif '\\inventoryinjector\\' in new_file_lower:                                     # Inventory Injector
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif '\\customskills\\' in new_file_lower or 'interface\\metaskillsmenu\\' in new_file_lower: # Custom Skills Framework
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif 'plugins\\rain extinguishes fires\\' in new_file_lower:                        # Rain Extinguishes Fires
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif '\\coreimpactframework\\' in new_file_lower:                                   # Core Impact Framework
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map, ':')
        elif 'plugins\\objectimpactframework' in new_file_lower:                            # Object Impact Framework
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map, ':')
        elif '\\skyrimunbound\\' in new_file_lower:                                         # Skyrim Unbound
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif '\\playerequipmentmanager\\' in new_file_lower:                                # Player Equipment Manager
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif '\\mapmarkers\\' in new_file_lower:                                            # CoMAP
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif new_file_lower.endswith('obody_presetdistributionconfig.json'):                # OBody NG
            patchers.json_obody_patcher(basename, new_file, form_id_map)
        elif os.path.basename(new_file_lower).startswith('shse.'):                          # Smart Harvest
            patchers.json_shse_patcher(basename, new_file, form_id_map)
        elif 'plugins\\rcs\\' in new_file_lower:                                            # Race Compatibility SKSE
            patchers.json_generic_plugin_sep_formid_patcher(basename, new_file, form_id_map)
        elif 'plugins\\perkadjuster' in new_file_lower:                                     # Perk Adjuster
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif 'plugins\\ostim\\' in new_file_lower:                                          # OStim
            patchers.json_ostim_patcher(basename, new_file, form_id_map)
        elif new_file_lower.endswith('sexlabconfig.json'):                                  # SL MCM Generated config
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif 'sexlab\\expression_' in new_file_lower:                                       # SL expressions
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif 'sexlab\\animations' in new_file_lower:                                        # SL animations?
            if not new_file_lower.endswith('arrokreversecowgirl.json'):
                patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map, int_type=True)
        elif 'configs\\dse-soulgem-oven' in new_file_lower:                                 # SoulGem Oven
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map)
        elif 'configs\\dse-display-model' in new_file_lower:                                # dse-display-model
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map, int_type=True)
        elif 'plugins\\ypsfashion\\' in new_file_lower:                                     # Immersive Hair Growth and Styling
            patchers.json_generic_formid_pipe_plugin_patcher(basename, new_file, form_id_map, int_type=True)
        elif 'plugins\\skyrim - utility mod\\' in new_file_lower:                           # Inte's Skyrim - Utility Mod
            patchers.json_sum_patcher(basename, new_file, form_id_map)
        else:
            print(f'Warn: Possible missing patcher for: {new_file}')
    elif new_file_lower.endswith('.pex'):                                                   # Compiled script patching
        patchers.pex_patcher(basename, new_file, form_id_map)
    elif new_file_lower.endswith('.toml'):
        if '\\_dynamicanimationcasting\\' in new_file_lower:                                # Dynamic Animation Casting (Original/NG)
            patchers.toml_dac_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\precision\\' in new_file_lower:                                             # Precision
            patchers.toml_precision_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\loki_poise\\' in new_file_lower:                                            # Loki Poise
            patchers.toml_loki_tdm_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif '\\truedirectionalmovement\\' in new_file_lower:                               # TDM
            patchers.toml_loki_tdm_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        elif new_file_lower.endswith('_avg.toml'):                                          # Actor Value Generator
            patchers.toml_avg_patcher(basename, new_file, form_id_map, encoding_method=encoding)
        else:
            print(f'Warn: Possible missing patcher for: {new_file}')
    elif new_file_lower.endswith('_srd.yaml'):                                              # Sound record distributor YAML
        patchers.srd_patcher(basename, new_file, form_id_map, encoding_method=encoding)
    elif 'facegeom' in new_file_lower and new_file_lower.endswith('.nif'):                  # FaceGeom mesh patching
        patchers.facegeom_mesh_patcher(basename, new_file, form_id_rename_map)
    elif new_file_lower.endswith('.seq'):                                                   # SEQ file patching
        patchers.seq_patcher(new_file, form_id_map)
    elif new_file_lower.endswith('.jslot'):                                                 # Racemenu Presets
        patchers.jslot_patcher(basename, new_file, form_id_map)
    elif new_file_lower.endswith('config.txt') and 'plugins\\customskill' in new_file_lower: # CSF's old txt format
        patchers.old_customskill_patcher(basename, new_file, form_id_map, encoding_method=encoding)
    else:
        print(f'Warn: Possible missing patcher for: {new_file}')
