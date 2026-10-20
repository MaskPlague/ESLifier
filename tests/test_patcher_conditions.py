"""
patcher_conditions.patch_file_conditions: routes each file to the right patcher based on its
path/extension. These tests replace every patcher with a recorder so only the routing and the
arguments passed along are checked; the patchers themselves are covered in test_file_patchers.py.

Paths use backslashes, exactly as ESLifier sees them on Windows (the code matches on '\\seasons\\' etc.).
"""
import ntpath
import types

import pytest

import patchers.sse_patcher_conditions as pc
from patchers.sse_file_patchers import patchers

MASTER_BYTE = b"\x01"


class Extra:
    """Stand-in for user_and_master_conditions_class."""

    def __init__(self, result=False):
        self.result = result
        self.calls = []

    def check_conditions(self, basename, file, file_lower, form_id_map):
        self.calls.append((basename, file, file_lower))
        return self.result


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    # ESLifier runs on Windows, where os.path understands backslashes. Make the module under test
    # see ntpath so os.path.basename() behaves identically when the suite runs on Linux/macOS.
    monkeypatch.setattr(pc, "os", types.SimpleNamespace(path=ntpath))

    def make(name):
        def recorder(*args, **kwargs):
            recorded.append((name, args, kwargs))
        return recorder

    for name in dir(patchers):
        if name.startswith("_") or not callable(getattr(patchers, name)):
            continue
        if name in ("find_prev_non_alphanumeric", "find_next_non_alphanumeric", "safe_load_json",
                    "extract_values_and_keys", "change_json_element", "change_json_key"):
            continue
        monkeypatch.setattr(patchers, name, make(name))
    return recorded


def route(path, extra=None, encoding="utf-8", update_byte=False, updated_master_index=-1):
    extra = extra or Extra(result=True)
    fmap = {"sentinel": 1}
    pc.patch_file_conditions(path.lower(), path, "mod.esp", fmap, MASTER_BYTE, updated_master_index,
                             update_byte, extra, encoding)
    return fmap, extra


# (path, expected patcher, expected keyword arguments (subset))
ROUTES = [
    # ---- ini
    ("c:\\d\\skse\\plugins\\foo_distr.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_kid.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_swap.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_enbl.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_desc.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_llos.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_ipm.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_mus.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\foo_flm.ini", "ini_form_list_manipulator_patcher", {}),
    ("c:\\d\\skse\\plugins\\seasons\\a.ini", "ini_seasons_patcher", {}),
    ("c:\\d\\skse\\plugins\\payloadinterpreter\\a.ini", "ini_payload_interpreter_and_dtrys_key_utils_patcher", {}),
    ("c:\\d\\skse\\plugins\\dtrykeyutil\\a.ini", "ini_payload_interpreter_and_dtrys_key_utils_patcher", {}),
    ("c:\\d\\skse\\plugins\\muimpactframework\\a.ini", "ini_mu_patcher", {}),
    ("c:\\d\\skse\\plugins\\muskeletoneditor\\a.ini", "ini_mu_patcher", {}),
    ("c:\\d\\skse\\plugins\\poisebreaker_a.ini", "ini_eq_plugin_sep_formid_patcher", {"sep": ":"}),
    ("c:\\d\\skse\\plugins\\skypatcher\\a.ini", "ini_skypatcher_patcher", {}),
    ("c:\\d\\skse\\plugins\\valhallacombat\\a.ini", "ini_eq_plugin_sep_formid_patcher", {"sep": "|"}),
    ("c:\\d\\skse\\plugins\\autobody\\a.ini", "ini_auto_body_patcher", {}),
    ("c:\\d\\skse\\plugins\\vsu\\a.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\completionistdata\\a.ini", "ini_completionist_patcher", {}),
    ("c:\\d\\skse\\kreate\\presets\\a.ini", "ini_kreate_patcher", {}),
    ("c:\\d\\skse\\plugins\\thenewgentleman.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\a_tng.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\rememberlockpickangle.ini", "ini_remember_lockpick_angle_patcher", {}),
    ("c:\\d\\skse\\plugins\\experience\\a.ini", "ini_experience_and_knotwork_patcher", {}),
    ("c:\\d\\skse\\plugins\\knotwork\\a.ini", "ini_experience_and_knotwork_patcher", {}),
    ("c:\\d\\skse\\plugins\\lightplacer\\a.ini", "ini_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\simpleedgeremoverng.ini", "ini_eq_plugin_sep_formid_patcher", {"sep": "|"}),
    ("c:\\d\\skse\\plugins\\a_nup_dist.ini", "ini_npcs_use_potions_patcher", {}),
    ("c:\\d\\skse\\plugins\\truehud\\a.ini", "ini_eq_plugin_sep_formid_patcher", {"sep": ":"}),
    ("c:\\d\\skse\\plugins\\rules\\dyndolod.ini", "ini_dyndolod_rules_patcher", {}),
    ("c:\\d\\skse\\plugins\\knockbackplugin.ini", "ini_knockback_skse_patcher", {}),
    ("c:\\d\\skse\\plugins\\beeingfemale\\enchantments\\a.ini", "ini_beeingfemale_patcher", {}),
    ("c:\\d\\skse\\plugins\\beeingfemale\\addon\\a.ini", "ini_beeingfemale_patcher", {}),
    # ---- txt
    ("c:\\d\\meshes\\actors\\a_conditions.txt", "dynamic_animation_replacer_patcher", {}),
    ("c:\\d\\skse\\plugins\\customskill\\a_config.txt", None, {}),     # plugins\customskill + config.txt, see below
    # ---- json
    ("c:\\d\\meshes\\animationreplacer\\config.json", "json_open_animation_replacer_patcher", {}),
    ("c:\\d\\meshes\\animationreplacer\\user.json", "json_open_animation_replacer_patcher", {}),
    ("c:\\d\\mcm\\config\\x\\config.json", "json_generic_plugin_sep_formid_patcher", {}),
    ("c:\\d\\skse\\plugins\\a_srd.json", "json_generic_plugin_sep_formid_patcher", {}),
    ("c:\\d\\skse\\plugins\\storageutildata\\a.json", "json_storage_util_data_patcher", {}),
    ("c:\\d\\skse\\plugins\\dynamicstringdistributor\\a.json", "json_dynamic_string_distributor_patcher", {}),
    ("c:\\d\\skse\\plugins\\dkaf\\a.json", "json_dynamic_key_activation_framework_patcher", {}),
    ("c:\\d\\skse\\plugins\\dynamicarmorvariants\\a.json", "json_dynamic_armor_variants_patcher", {}),
    ("c:\\d\\skse\\plugins\\ied\\a.json", "json_immersive_equipment_displays_patcher", {}),
    ("c:\\d\\skse\\plugins\\creatures.d\\a.json", "json_jcontainer_patcher", {}),
    ("c:\\d\\skse\\plugins\\inventoryinjector\\a.json", "json_generic_plugin_sep_formid_patcher", {}),
    ("c:\\d\\skse\\plugins\\customskills\\a.json", "json_generic_plugin_sep_formid_patcher", {}),
    ("c:\\d\\skse\\plugins\\coreimpactframework\\a.json", "json_generic_plugin_sep_formid_patcher", {"sep": ":"}),
    ("c:\\d\\skse\\plugins\\lightplacer\\a.json", "json_generic_formid_sep_plugin_patcher", {"sep": "~"}),
    ("c:\\d\\skse\\plugins\\skyrimunbound\\a.json", "json_generic_formid_sep_plugin_patcher", {}),
    ("c:\\d\\skse\\plugins\\mapmarkers\\a.json", "json_generic_plugin_sep_formid_patcher", {}),
    ("c:\\d\\skse\\plugins\\obody_presetdistributionconfig.json", "json_obody_patcher", {}),
    ("c:\\d\\skse\\plugins\\shse.a.json", "json_smart_harvest_patcher", {}),
    ("c:\\d\\skse\\plugins\\ostim\\a.json", "json_ostim_patcher", {}),
    ("c:\\d\\skse\\plugins\\sexlab\\animations\\a.json", "json_generic_formid_sep_plugin_patcher", {"int_type": True}),
    ("c:\\d\\skse\\plugins\\configs\\dse-display-model.json", "json_generic_formid_sep_plugin_patcher", {"int_type": True}),
    ("c:\\d\\skse\\plugins\\gsp\\a.json", "json_generic_formid_sep_plugin_patcher", {"sep": ":"}),
    ("c:\\d\\skse\\plugins\\luma\\a.json", "json_generic_formid_sep_plugin_patcher", {"sep": ":"}),
    ("c:\\d\\skse\\plugins\\spell organizer.json", "json_jcontainer_patcher", {}),
    ("c:\\d\\skse\\plugins\\firehurtsre\\a.json", "json_fire_hurts_re_patcher", {}),
    ("c:\\d\\skse\\undaunted\\groups\\a.json", "json_undaunted_patcher", {}),
    ("c:\\d\\skse\\plugins\\achievementsdata\\a.json", "json_achievement_injector_patcher", {}),
    # ---- pex / toml / yml / yaml
    ("c:\\d\\scripts\\a.pex", "pex_patcher", {}),
    ("c:\\d\\skse\\plugins\\_dynamicanimationcasting\\a.toml", "toml_dynamic_animation_casting_patcher", {}),
    ("c:\\d\\skse\\plugins\\precision\\a.toml", "toml_precision_patcher", {}),
    ("c:\\d\\skse\\plugins\\loki_poise\\a.toml", "toml_loki_and_tdm_patcher", {}),
    ("c:\\d\\skse\\plugins\\truedirectionalmovement\\a.toml", "toml_loki_and_tdm_patcher", {}),
    ("c:\\d\\skse\\plugins\\a_avg.toml", "toml_actor_value_generator_patcher", {}),
    ("c:\\d\\skse\\plugins\\yastm_a.toml", "toml_yet_another_soul_trap_manager_patcher", {}),
    ("c:\\d\\skse\\plugins\\dbd\\configurations\\a.yml", "dbd_patcher", {}),
    ("c:\\d\\skse\\plugins\\alchemyoftime\\a.yml", None, {}),     # note: pattern is '\\plugins\\alchemyoftime\\'
    ("c:\\d\\skse\\plugins\\a_srd.yaml", "sound_record_distributor_patcher", {}),
    ("c:\\d\\skse\\sexlab\\userdata\\stripping.yaml", "yaml_slpp_stripping_patcher", {}),
    ("c:\\d\\skse\\sexlab\\userdata\\voices_npc.yaml", "ini_formid_sep_plugin_patcher", {"sep": "|"}),
    ("c:\\d\\skse\\sexlab\\schlongsofskyrim.yaml", "yaml_slpp_sos_patcher", {}),
    ("c:\\d\\skse\\sexlab\\voices\\a.yaml", "ini_formid_sep_plugin_patcher", {"sep": "|"}),
    # ---- other
    ("c:\\d\\data\\textures\\actors\\character\\facegendata\\facegeom\\mod.esp\\00001234.nif", "facegeom_mesh_patcher", {}),
    ("c:\\d\\data\\seq\\mod.seq", "seq_patcher", {}),
    ("c:\\d\\data\\skse\\plugins\\racemenu\\presets\\a.jslot", "jslot_patcher", {}),
]
ROUTES = [r for r in ROUTES if r[1] is not None]


@pytest.mark.parametrize("path,expected,kwargs", ROUTES, ids=[r[0].split("\\", 2)[-1] for r in ROUTES])
def test_routes_to_expected_patcher(calls, path, expected, kwargs):
    fmap, extra = route(path)
    assert [c[0] for c in calls] == [expected]
    name, args, kw = calls[0]
    for k, v in kwargs.items():
        assert kw[k] == v
    assert extra.calls == []                       # fallback not consulted


def test_basename_map_and_encoding_are_forwarded(calls):
    fmap, _ = route("c:\\d\\scripts\\a.pex", encoding="ansi")
    name, args, kw = calls[0]
    assert args == ("mod.esp", "c:\\d\\scripts\\a.pex", fmap)


def test_encoding_is_forwarded_as_keyword(calls):
    route("c:\\d\\skse\\plugins\\a_distr.ini", encoding="ansi")
    assert calls[0][2]["encoding_method"] == "ansi"


def test_flm_ini_receives_lowercased_path(calls):
    # current behaviour: Form List Manipulator is handed new_file_lower (matters on case sensitive filesystems)
    route("C:\\D\\SKSE\\Plugins\\Foo_FLM.ini")
    assert calls[0][1][1] == "c:\\d\\skse\\plugins\\foo_flm.ini"


def test_paths_are_matched_case_insensitively(calls):
    route("C:\\D\\SKSE\\Plugins\\Seasons\\A.INI")
    assert calls[0][0] == "ini_seasons_patcher"


def test_seq_patcher_gets_master_information(calls):
    route("c:\\d\\mod.seq", update_byte=True, updated_master_index=3)
    name, args, kw = calls[0]
    assert kw == {"updated_master_index": 3, "master_byte": MASTER_BYTE, "update_byte": True}


def test_dyndolod_ligh_json_gets_master_byte(calls):
    route("c:\\d\\dyndolod_data\\mod_ligh.json")
    name, args, kw = calls[0]
    assert name == "json_dyndolod_ligh_patcher"
    assert MASTER_BYTE in args


def test_old_customskill_txt_route(calls):
    route("c:\\d\\skse\\plugins\\customskill.x\\config.txt"[:0] + "c:\\d\\data\\skse\\plugins\\customskill\\config.txt")
    assert calls[0][0] == "old_customskill_patcher"


def test_alchemy_of_time_yml_route(calls):
    route("c:\\d\\data\\skse\\plugins\\alchemyoftime\\x.yml"[:0] + "c:\\d\\skse\\\\plugins\\alchemyoftime\\x.yml")
    # pattern in code is '\\plugins\\alchemyoftime\\'
    assert calls[0][0] == "ini_formid_sep_plugin_patcher"


# ---------------------------------------------------------------------------- fallback behaviour
@pytest.mark.parametrize("path", [
    "c:\\d\\skse\\plugins\\unknown.ini",
    "c:\\d\\skse\\plugins\\unknown.json",
    "c:\\d\\skse\\plugins\\unknown.toml",
    "c:\\d\\skse\\plugins\\unknown.yml",
    "c:\\d\\skse\\plugins\\unknown.yaml",
    "c:\\d\\skse\\plugins\\unknown.xyz",
    "c:\\d\\meshes\\other.nif",
])
def test_unrecognised_files_are_offered_to_user_conditions(calls, path):
    extra = Extra(result=True)
    route(path, extra)
    assert calls == []
    assert len(extra.calls) == 1 and extra.calls[0][0] == "mod.esp"


def test_any_nif_with_facegeom_in_its_path_goes_to_the_facegeom_patcher(calls):
    # The match is a plain substring test on the whole path, so even "not_facegeom.nif" is routed there.
    route("c:\\d\\meshes\\not_facegeom.nif")
    assert [c[0] for c in calls] == ["facegeom_mesh_patcher"]


def test_warns_when_nobody_can_patch_the_file(calls, log):
    route("c:\\d\\skse\\plugins\\unknown.ini", Extra(result=False))
    assert any("Possible missing patcher" in w and "unknown.ini" in w for w in log.warnings)


def test_no_warning_when_user_condition_handled_it(calls, log):
    route("c:\\d\\skse\\plugins\\unknown.ini", Extra(result=True))
    assert log.warnings == []
