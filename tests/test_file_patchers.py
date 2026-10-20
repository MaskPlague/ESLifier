"""
file_patchers.patchers: rewrites Form IDs inside the many config/script file formats that
reference a plugin that has just been compacted.

Every patcher has the signature   patcher(basename, new_file, form_id_map, ...)
where ``basename`` is the lower-cased compacted plugin name and ``form_id_map`` maps old
form id (int) -> {"hex", "int", "hex_no_0", "bytes", "update_name"}.

The tests below use one common mapping:
    0x0A2C8E -> 0x000A0A   (stays in the same plugin)
    0x0A2C8F -> 0x000A0B   (stays in the same plugin)
    0x0A2C90 -> 0x000A0C   (moves into ESLifier_Cell_Master.esm, "update_name" = True)
"""
import json
import struct

import pytest

from patchers.sse_file_patchers import patchers
from plugin_builder import fid, map_entry, write

BASENAME = "mod.esp"
CELL_MASTER = "ESLifier_Cell_Master.esm"

FORM_ID_MAP = {
    0x0A2C8E: map_entry("A0A"),
    0x0A2C8F: map_entry("A0B"),
    0x0A2C90: map_entry("A0C", update_name=True),
}


def patch(tmp_path, fn, content, *args, name="file.txt", mapping=None, binary=False, **kw):
    """Write ``content`` to a file, run ``fn`` on it and return the new contents."""
    path = tmp_path / name
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="")
    fn(BASENAME, str(path), FORM_ID_MAP if mapping is None else mapping, *args, **kw)
    return path.read_bytes() if binary else path.read_text(encoding="utf-8")


def patch_json(tmp_path, fn, data, *args, **kw):
    path = tmp_path / "file.json"
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    fn(BASENAME, str(path), FORM_ID_MAP, *args, **kw)
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- helpers
class TestStringHelpers:
    def test_find_prev_non_alphanumeric(self):
        assert patchers.find_prev_non_alphanumeric("a=bcd", 4) == 1
        assert patchers.find_prev_non_alphanumeric("abcd", 3) == -1

    def test_find_prev_treats_spaces_as_part_of_word_unless_token(self):
        assert patchers.find_prev_non_alphanumeric("a b|c", 4) == 3
        assert patchers.find_prev_non_alphanumeric("a b", 2, tokens={" "}) == 1

    def test_find_next_non_alphanumeric(self):
        assert patchers.find_next_non_alphanumeric("0x12,ab", 0) == 4
        assert patchers.find_next_non_alphanumeric("abcd", 0) == 4

    def test_find_next_stops_at_tokens(self):
        assert patchers.find_next_non_alphanumeric("ab cd", 0, tokens={"b"}) == 1


class TestJsonHelpers:
    def test_extract_values_and_keys(self):
        data = {"a": [1, {"b": "x"}], "c": 2}
        assert patchers.extract_values_and_keys(data) == [(["a", 0], 1), (["a", 1, "b"], "x"), (["c"], 2)]

    def test_change_json_element(self):
        data = {"a": [1, {"b": "x"}]}
        assert patchers.change_json_element(data, ["a", 1, "b"], "y") == {"a": [1, {"b": "y"}]}

    def test_change_json_key_is_recursive(self):
        data = {"old": 1, "n": [{"old": 2}]}
        assert patchers.change_json_key(data, "old", "new") == {"n": [{"new": 2}], "new": 1}

    def test_safe_load_json_falls_back_to_json5(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text('{ // comment\n "a": 1, }')
        with open(p) as f:
            assert patchers.safe_load_json(f) == {"a": 1}


# --------------------------------------------------------------------------- binary files
class TestFacegeomMesh:
    def test_form_id_in_texture_path_is_replaced(self, tmp_path):
        # ...FaceTint\Mod.esp\000A2C8E.dds : skip "\00", then 6 hex digits
        content = b"\x01\x02FaceTint\\Mod.esp\\000A2C8E.dds\x00\x03"
        m = {b"0a2c8e": b"00000A"}
        out = patch(tmp_path, patchers.facegeom_mesh_patcher, content, mapping=m, binary=True, name="f.nif")
        assert out == b"\x01\x02FaceTint\\Mod.esp\\0000000A.dds\x00\x03"

    def test_other_plugins_and_unknown_ids_untouched(self, tmp_path):
        content = b"FaceTint\\Other.esp\\000A2C8E.dds FaceTint\\Mod.esp\\00FFFFFF.dds"
        m = {b"0a2c8e": b"00000A"}
        assert patch(tmp_path, patchers.facegeom_mesh_patcher, content, mapping=m, binary=True) == content

    def test_multiple_references(self, tmp_path):
        content = b"x\\Mod.esp\\000A2C8E.nif|y\\MOD.ESP\\000A2C8F.nif"
        m = {b"0a2c8e": b"00000A", b"0a2c8f": b"00000B"}
        out = patch(tmp_path, patchers.facegeom_mesh_patcher, content, mapping=m, binary=True)
        assert out == b"x\\Mod.esp\\0000000A.nif|y\\MOD.ESP\\0000000B.nif"

    def test_file_with_no_match_is_unchanged(self, tmp_path):
        content = b"\x00\x01nothing here"
        assert patch(tmp_path, patchers.facegeom_mesh_patcher, content, mapping={}, binary=True) == content


class TestSeqPatcher:
    MAP = {fid(1, 0x2000): fid(1, 0x0001)}

    def run(self, tmp_path, data, update_byte=False, master_byte=b"\x01", updated_index=-1, mapping=None):
        p = tmp_path / "q.seq"
        p.write_bytes(data)
        patchers.seq_patcher(str(p), self.MAP if mapping is None else mapping, updated_master_index=updated_index,
                             master_byte=master_byte, update_byte=update_byte)
        return p.read_bytes()

    def test_own_ids_are_remapped_and_master_ids_kept(self, tmp_path):
        data = fid(1, 0x2000) + fid(0, 0x14) + fid(1, 0x7777)
        assert self.run(tmp_path, data) == fid(1, 1) + fid(0, 0x14) + fid(1, 0x7777)

    def test_master_byte_bumped_when_cell_master_appended(self, tmp_path):
        data = fid(1, 0x2000) + fid(0, 0x14)
        assert self.run(tmp_path, data, update_byte=True) == fid(2, 1) + fid(0, 0x14)

    def test_master_byte_not_bumped_when_cell_master_already_present(self, tmp_path):
        data = fid(1, 0x2000)
        assert self.run(tmp_path, data, update_byte=True, updated_index=4) == fid(1, 1)

    def test_empty_seq(self, tmp_path):
        assert self.run(tmp_path, b"") == b""


# --------------------------------------------------------------------------- INI patchers
class TestIniFormIdSepPlugin:
    """SPID / KID / BOS / ENBL / LightPlacer ... : ``0xFORMID~Plugin.esp``."""

    def test_replaces_form_id(self, tmp_path):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, "Spell = 0x0A2C8E~Mod.esp|ActorTypeNPC\n")
        assert out == "Spell = 0xA0A~Mod.esp|ActorTypeNPC\n"

    def test_renames_plugin_when_moved_to_cell_master(self, tmp_path, log):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, "Spell = 0x0A2C90~Mod.esp|X\n")
        assert out == f"Spell = 0xA0C~{CELL_MASTER}|X\n"
        assert any("Plugin Name Replaced" in l for l in log.file_lines)

    def test_leaves_other_plugins_and_comments(self, tmp_path):
        content = "; Spell = 0x0A2C8E~Mod.esp\nSpell = 0x0A2C8E~Other.esp\n"
        assert patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, content) == content

    def test_two_plugins_on_one_line_only_matching_one_changes(self, tmp_path):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher,
                    "Spell = 0x0A2C8E~Other.esp,0x0A2C8F~Mod.esp\n")
        assert out == "Spell = 0x0A2C8E~Other.esp,0xA0B~Mod.esp\n"

    def test_ids_not_in_map_are_untouched(self, tmp_path):
        content = "Spell = 0x00FFFF~Mod.esp\n"
        assert patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, content) == content

    def test_custom_separator_and_prefix(self, tmp_path):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, "x = 0x0A2C8E|Mod.esp\n", sep="|")
        assert out == "x = 0xA0A|Mod.esp\n"

    def test_long_form_ids_use_last_six_digits(self, tmp_path):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, "x = 0x010A2C8E~Mod.esp\n")
        assert out == "x = 0xA0A~Mod.esp\n"

    def test_hex_key_variant(self, tmp_path):
        out = patch(tmp_path, patchers.ini_formid_sep_plugin_patcher, "x = 0x0A2C8E~Mod.esp\n",
                    to_id_key="hex", fid_start="0x")
        assert out == "x = 0x000A0A~Mod.esp\n"


class TestIniPluginSepFormId:
    def test_replaces(self, tmp_path):
        out = patch(tmp_path, patchers.ini_plugin_sep_formid_patcher, "Armor=Mod.esp|0x0A2C8E,Other.esp|0x5\n", sep="|")
        assert out == "Armor=Mod.esp|0xA0A,Other.esp|0x5\n"

    def test_renames_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_plugin_sep_formid_patcher, "Armor=Mod.esp|0x0A2C90,Z\n", sep="|")
        assert out == f"Armor={CELL_MASTER}|0xA0C,Z\n"


class TestIniSeasons:
    def test_single_pair(self, tmp_path):
        assert patch(tmp_path, patchers.ini_seasons_patcher, "0x0A2C8E~Mod.esp\n") == "0xA0A~Mod.esp\n"

    def test_double_pair(self, tmp_path):
        out = patch(tmp_path, patchers.ini_seasons_patcher, "0x0A2C8E~Mod.esp|0x0A2C8F~Mod.esp\n")
        assert out == "0xA0A~Mod.esp|0xA0B~Mod.esp\n"

    def test_renamed_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_seasons_patcher, "0x0A2C90~Mod.esp\n")
        assert out == f"0xA0C~{CELL_MASTER}\n"

    def test_mixed_pair_keeps_foreign_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_seasons_patcher, "0x0A2C8E~Mod.esp|0x000800~Skyrim.esm\n")
        assert out == "0xA0A~Mod.esp|0x000800~Skyrim.esm\n"

    def test_beta_typo_03x_prefix_is_repaired(self, tmp_path):
        assert patch(tmp_path, patchers.ini_seasons_patcher, "03x0A2C8E~Mod.esp\n") == "0xA0A~Mod.esp\n"

    def test_comment_lines_ignored(self, tmp_path):
        content = "; 0x0A2C8E~Mod.esp\n"
        assert patch(tmp_path, patchers.ini_seasons_patcher, content) == content


class TestIniPayloadInterpreter:
    def test_replaces(self, tmp_path):
        out = patch(tmp_path, patchers.ini_payload_interpreter_and_dtrys_key_utils_patcher, "Spell=0x0A2C8E|Mod.esp\n")
        assert out == "Spell=0xA0A|Mod.esp\n"

    def test_renames_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_payload_interpreter_and_dtrys_key_utils_patcher, "Spell=0x0A2C90|Mod.esp\n")
        assert out == f"Spell=0xA0C|{CELL_MASTER}\n"

    def test_keeps_trailing_fields(self, tmp_path):
        out = patch(tmp_path, patchers.ini_payload_interpreter_and_dtrys_key_utils_patcher, "Spell=0x0A2C8E|Mod.esp|1.0\n")
        assert out == "Spell=0xA0A|Mod.esp|1.0\n"


class TestIniFormListManipulator:
    def test_replaces(self, tmp_path):
        out = patch(tmp_path, patchers.ini_form_list_manipulator_patcher, "Add = 0x0A2C8E~Mod.esp\n")
        assert out == "Add = 0xA0A~Mod.esp\n"

    def test_renames_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_form_list_manipulator_patcher, "Add = 0x0A2C90~Mod.esp\n")
        assert out == f"Add = 0xA0C~{CELL_MASTER}\n"

    def test_non_hex_entries_skipped(self, tmp_path):
        content = "Add = EditorID~Mod.esp\n"
        assert patch(tmp_path, patchers.ini_form_list_manipulator_patcher, content) == content


class TestIniMu:
    def test_replaces(self, tmp_path):
        assert patch(tmp_path, patchers.ini_mu_patcher, "Form=(Mod.esp|0x0A2C8E)\n") == "Form=(Mod.esp|0xA0A)\n"

    def test_renames_plugin(self, tmp_path):
        assert patch(tmp_path, patchers.ini_mu_patcher, "Form=(Mod.esp|0x0A2C90)\n") == f"Form=({CELL_MASTER}|0xA0C)\n"


class TestIniSkyPatcher:
    def test_replaces(self, tmp_path):
        out = patch(tmp_path, patchers.ini_skypatcher_patcher, "filterByNpcs=Mod.esp|0A2C8E\n")
        assert out == "filterByNpcs=Mod.esp|A0A\n"

    def test_renames_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_skypatcher_patcher, "filterByNpcs=Mod.esp|0A2C90\n")
        assert out == f"filterByNpcs={CELL_MASTER}|A0C\n"

    def test_list_of_plugins_only_ours_changes(self, tmp_path):
        out = patch(tmp_path, patchers.ini_skypatcher_patcher, "filterByNpcs=Skyrim.esm|13,Mod.esp|0A2C8E\n")
        assert out == "filterByNpcs=Skyrim.esm|13,Mod.esp|A0A\n"


class TestIniEqPluginSepFormId:
    def test_0x_form_ids(self, tmp_path):
        out = patch(tmp_path, patchers.ini_eq_plugin_sep_formid_patcher, "Key = Mod.esp|0x0A2C8E\n", sep="|")
        assert out == "Key = Mod.esp|0xA0A\n"

    def test_plain_form_ids_are_written_as_eight_digits(self, tmp_path):
        out = patch(tmp_path, patchers.ini_eq_plugin_sep_formid_patcher, "Key = Mod.esp|000A2C8E\n", sep="|")
        assert out == "Key = Mod.esp|00000A0A\n"

    def test_colon_separator(self, tmp_path):
        out = patch(tmp_path, patchers.ini_eq_plugin_sep_formid_patcher, "Key = Mod.esp:0x0A2C8E\n", sep=":")
        assert out == "Key = Mod.esp:0xA0A\n"

    def test_renames_plugin(self, tmp_path):
        out = patch(tmp_path, patchers.ini_eq_plugin_sep_formid_patcher, "Key = Mod.esp|0x0A2C90\n", sep="|")
        assert out == f"Key = {CELL_MASTER}|0xA0C\n"

    def test_other_plugin_untouched(self, tmp_path):
        content = "Key = Other.esp|0x0A2C8E\n"
        assert patch(tmp_path, patchers.ini_eq_plugin_sep_formid_patcher, content, sep="|") == content


class TestIniMisc:
    def test_auto_body(self, tmp_path):
        out = patch(tmp_path, patchers.ini_auto_body_patcher, "Mod.esp|0A2C8E\nOther.esp|0A2C8E\n")
        assert out == "Mod.esp|A0A\nOther.esp|0A2C8E\n"

    def test_remember_lockpick_angle(self, tmp_path):
        out = patch(tmp_path, patchers.ini_remember_lockpick_angle_patcher,
                    "requiredPerk = 0A2C8E\nmodName = Mod.esp\n")
        assert out == "requiredPerk = A0A\nmodName = Mod.esp\n"

    def test_experience_patches_only_its_section(self, tmp_path):
        content = "[Other.esp]\n000A2C8E = 1\n[Mod.esp]\n000A2C8F = 2\n"
        out = patch(tmp_path, patchers.ini_experience_and_knotwork_patcher, content)
        assert out == "[Other.esp]\n000A2C8E = 1\n[Mod.esp]\n00000A0B = 2\n"

    def test_npcs_use_potions(self, tmp_path):
        out = patch(tmp_path, patchers.ini_npcs_use_potions_patcher, "Potion = <0A2C8E,Mod.esp>\n")
        assert out == "Potion = <A0A,Mod.esp>\n"

    def test_dyndolod_rules(self, tmp_path):
        out = patch(tmp_path, patchers.ini_dyndolod_rules_patcher, "Mod.esp;000A2C8E;rest\n")
        assert out == "Mod.esp;00000A0A;rest\n"

    def test_knockback(self, tmp_path):
        out = patch(tmp_path, patchers.ini_knockback_skse_patcher, "Mod.esp|000A2C8E\n")
        assert out == "Mod.esp|00000A0A\n"

    def test_kreate_updates_symbol_and_id(self, tmp_path):
        import configparser
        content = "[Weather]\nWeatherSymbol = Mod.esp|0A2C8E\nWeatherID = 0x0A2C8E\nOther = 1\n"
        out = patch(tmp_path, patchers.ini_kreate_patcher, content)
        cp = configparser.ConfigParser()
        cp.optionxform = str
        cp.read_string(out)
        assert cp["Weather"]["WeatherSymbol"] == "Mod.esp|a0a"
        assert cp["Weather"]["WeatherID"] == "0xa0a"
        assert cp["Weather"]["Other"] == "1"

    def test_kreate_without_leading_section(self, tmp_path):
        out = patch(tmp_path, patchers.ini_kreate_patcher, "WeatherSymbol = Mod.esp|0A2C8E\n")
        assert "[" not in out and "Mod.esp|a0a" in out


# --------------------------------------------------------------------------- TOML / TXT / YAML
class TestToml:
    def test_precision(self, tmp_path):
        out = patch(tmp_path, patchers.toml_precision_patcher, 'k = [ { formID = 0x0A2C8E, plugin = "Mod.esp" } ]\n')
        assert out == 'k = [ { formID = 0xA0A, plugin = "Mod.esp" } ]\n'

    def test_loki_and_tdm(self, tmp_path):
        out = patch(tmp_path, patchers.toml_loki_and_tdm_patcher, 'formID = 0x0A2C8E\nplugin = "Mod.esp"\n')
        assert out == 'formID = 0xA0A\nplugin = "Mod.esp"\n'

    def test_loki_ignores_other_plugins(self, tmp_path):
        content = 'formID = 0x0A2C8E\nplugin = "Other.esp"\n'
        assert patch(tmp_path, patchers.toml_loki_and_tdm_patcher, content) == content

    def test_yastm(self, tmp_path):
        out = patch(tmp_path, patchers.toml_yet_another_soul_trap_manager_patcher, '[0x0A2C8E, "Mod.esp"]\n')
        assert out == '[0xA0A, "Mod.esp"]\n'


class TestTextFormats:
    def test_dynamic_animation_replacer(self, tmp_path):
        out = patch(tmp_path, patchers.dynamic_animation_replacer_patcher, 'IsRace "Mod.esp" | 0x0A2C8E\n')
        assert out == 'IsRace "Mod.esp" |0x000A0A\n'

    def test_sound_record_distributor_yaml(self, tmp_path):
        out = patch(tmp_path, patchers.sound_record_distributor_patcher, "- Type: Mod.esp|0A2C8E\n")
        assert out.startswith("- Type: Mod.esp|000A0A")

    def test_old_custom_skill_txt(self, tmp_path):
        content = "File = Mod.esp\nId = 0x0A2C8E\n"
        out = patch(tmp_path, patchers.old_customskill_patcher, content)
        assert out == "File = Mod.esp\nId = 0xA0A\n"

    def test_slpp_stripping_yaml(self, tmp_path):
        # keys are decimal form ids under a plugin heading
        content = f"Mod.esp:\n  {0x0A2C8E}: [1, 2]\nOther.esp:\n  {0x0A2C8E}: [3]\n"
        out = patch(tmp_path, patchers.yaml_slpp_stripping_patcher, content)
        assert out == f"Mod.esp:\n  {0x0A0A}: [1, 2]\nOther.esp:\n  {0x0A2C8E}: [3]\n"


# --------------------------------------------------------------------------- JSON patchers
class TestJsonGenericPluginSepFormId:
    def test_0x_ids(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher,
                         {"a": "Mod.esp|0x0A2C8E", "b": ["Mod.esp|0x0A2C8F", "Other.esp|0x0A2C8E"], "c": 5})
        assert out == {"a": "Mod.esp|0xA0A", "b": ["Mod.esp|0xA0B", "Other.esp|0x0A2C8E"], "c": 5}

    def test_plain_hex_ids(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher, {"a": "Mod.esp|0A2C8E"})
        assert out == {"a": "Mod.esp|A0A"}

    def test_cell_master_rename(self, tmp_path, log):
        out = patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher, {"a": "Mod.esp|0x0A2C90"})
        assert out == {"a": f"{CELL_MASTER}|0xA0C"}
        assert any("Plugin Name Replaced" in l for l in log.file_lines)

    def test_colon_separator(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher, {"a": "Mod.esp:0x0A2C8E"}, sep=":")
        assert out == {"a": "Mod.esp:0xA0A"}

    def test_json_with_comments_is_accepted(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher,
                         '{ // note\n "a": "Mod.esp|0x0A2C8E", }')
        assert out == {"a": "Mod.esp|0xA0A"}

    def test_unmapped_ids_untouched(self, tmp_path):
        data = {"a": "Mod.esp|0x00FFFF"}
        assert patch_json(tmp_path, patchers.json_generic_plugin_sep_formid_patcher, data) == data


class TestJsonGenericFormIdSepPlugin:
    def test_replaces(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_formid_sep_plugin_patcher, {"a": "0x0A2C8E|Mod.esp"})
        assert out == {"a": "0xA0A|Mod.esp"}

    def test_plain_hex(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_formid_sep_plugin_patcher, {"a": "0A2C8E|Mod.esp"})
        assert out == {"a": "A0A|Mod.esp"}

    def test_decimal_ids(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_formid_sep_plugin_patcher,
                         {"a": f"{0x0A2C8E}|Mod.esp"}, int_type=True)
        assert out == {"a": f"{0xA0A}|Mod.esp"}

    def test_cell_master_rename(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_formid_sep_plugin_patcher, {"a": "0x0A2C90|Mod.esp"})
        assert out == {"a": f"0xA0C|{CELL_MASTER}"}

    def test_custom_separator(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_formid_sep_plugin_patcher, {"a": "0x0A2C8E~Mod.esp"}, sep="~")
        assert out == {"a": "0xA0A~Mod.esp"}


class TestJsonKeyPatchers:
    def test_key_fid_sep_plugin(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_key_fid_sep_plugin_patcher, {"0A2C8E:Mod.esp": 1, "x": 2})
        assert out == {"000A0A:Mod.esp": 1, "x": 2}

    def test_key_fid_sep_plugin_cell_master(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_key_fid_sep_plugin_patcher, {"0A2C90:Mod.esp": 1})
        assert out == {f"000A0C:{CELL_MASTER}": 1}

    def test_key_plugin_sep_fid(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_key_plugin_sep_fid_patcher, {"Mod.esp:0A2C8E": 1})
        assert out == {"Mod.esp:000A0A": 1}

    def test_nested_keys(self, tmp_path):
        out = patch_json(tmp_path, patchers.json_generic_key_plugin_sep_fid_patcher,
                         {"outer": {"Mod.esp:0A2C8E": [1]}})
        assert out == {"outer": {"Mod.esp:000A0A": [1]}}


class TestJsonSpecific:
    def test_open_animation_replacer(self, tmp_path):
        data = {"conditions": [{"pluginName": "Mod.esp", "formID": "0A2C8E"}, {"pluginName": "Other.esp", "formID": "0A2C8E"}]}
        out = patch_json(tmp_path, patchers.json_open_animation_replacer_patcher, data)
        assert out["conditions"][0]["formID"] == "A0A"
        assert out["conditions"][1]["formID"] == "0A2C8E"

    def test_open_animation_replacer_renames_plugin(self, tmp_path):
        data = {"c": {"pluginName": "Mod.esp", "formID": "0A2C90"}}
        out = patch_json(tmp_path, patchers.json_open_animation_replacer_patcher, data)
        assert out["c"] == {"pluginName": CELL_MASTER, "formID": "A0C"}

    def test_open_animation_replacer_bad_form_id_is_logged(self, tmp_path, log):
        data = {"c": {"pluginName": "Mod.esp", "formID": "not hex"}}
        patch_json(tmp_path, patchers.json_open_animation_replacer_patcher, data)
        assert any("Invalid Form ID" in l for l in log.file_lines)


# --------------------------------------------------------------------------- PEX
PEX_STRINGS = [b"Mod.esp", b"GetFormFromFile", b"Quest", b"other", b"dest", b"tmp"]


def _pv(kind, value=0):
    """One Papyrus variable operand: null=0, identifier=1, string=2, integer=3 (big endian)."""
    if kind == 0:
        return b"\x00"
    if kind == 3:
        return b"\x03" + struct.pack(">I", value)
    return bytes([kind]) + struct.pack(">H", value)


def build_pex(form_id: int, plugin_index: int = 0, via_var: bool = False, store_null_first: bool = False):
    """A structurally valid Skyrim SE script with one object/state/function calling
    ``GetFormFromFile(<form_id>, "Mod.esp")`` (the integer is the call argument, or goes through a
    temporary variable when ``via_var``)."""
    out = b"\xFA\x57\xC0\xDE" + bytes([3, 9]) + struct.pack(">H", 1) + b"\x00" * 8
    for text in (b"src.psc", b"user", b"machine"):
        out += struct.pack(">H", len(text)) + text
    out += struct.pack(">H", len(PEX_STRINGS))
    for text in PEX_STRINGS:
        out += struct.pack(">H", len(text)) + text
    out += b"\x00"                                   # no debug info
    out += struct.pack(">H", 0)                       # no user flags
    out += struct.pack(">H", 1)                       # one object
    out += struct.pack(">H", 2) + struct.pack(">I", 0) + b"\x00" * 10          # name, size, parent/doc/flags/auto-state
    out += struct.pack(">H", 0) + struct.pack(">H", 0)                           # no variables, no properties
    out += struct.pack(">H", 1)                       # one state
    out += struct.pack(">H", 0) + struct.pack(">H", 1)                           # state name, one function
    out += struct.pack(">H", 5)                       # function name
    out += b"\x00" * 9                                # return type, doc string, user flags, flags
    out += struct.pack(">H", 0) + struct.pack(">H", 0)                           # no params, no locals
    instructions = b""
    count = 0
    if store_null_first:                              # dest = None
        instructions += b"\x0D" + _pv(1, 4) + _pv(0)
        count += 1
    if via_var:
        instructions += b"\x0D" + _pv(1, 5) + _pv(3, form_id)                  # tmp = <form_id>
        arg1 = _pv(1, 5)
        count += 1
    else:
        arg1 = _pv(3, form_id)
    # CALLSTATIC Quest.GetFormFromFile(arg1, "Mod.esp") -> dest
    instructions += b"\x19" + _pv(1, 2) + _pv(1, 1) + _pv(1, 4) + _pv(3, 2) + arg1 + _pv(2, plugin_index)
    count += 1
    out += struct.pack(">H", count) + instructions
    return out


class TestPex:
    def test_integer_form_id_passed_with_plugin_name_is_patched(self, tmp_path):
        out = patch(tmp_path, patchers.pex_patcher, build_pex(0x0A2C8E), binary=True, name="s.pex")
        assert out == build_pex(0x000A0A)

    def test_form_id_held_in_a_temporary_variable_is_patched(self, tmp_path):
        out = patch(tmp_path, patchers.pex_patcher, build_pex(0x0A2C8E, via_var=True), binary=True, name="s.pex")
        assert out == build_pex(0x000A0A, via_var=True)

    def test_unmapped_form_id_untouched(self, tmp_path):
        data = build_pex(0x00FFFF)
        assert patch(tmp_path, patchers.pex_patcher, data, binary=True) == data

    def test_integer_followed_by_other_string_not_patched(self, tmp_path):
        data = build_pex(0x0A2C8E, plugin_index=3)
        assert patch(tmp_path, patchers.pex_patcher, data, binary=True) == data

    def test_cell_master_rename_is_still_patched(self, tmp_path):
        out = patch(tmp_path, patchers.pex_patcher, build_pex(0x0A2C90), binary=True)
        assert out == build_pex(0x000A0C)

    def test_cell_master_rename_is_reported_as_ineligible(self, tmp_path, log):
        patch(tmp_path, patchers.pex_patcher, build_pex(0x0A2C90), binary=True)
        assert log.ineligible and "ESLifier_Cell_Master.esm" in log.ineligible[0]

    def test_script_that_assigns_none_before_the_call_is_still_patched(self, tmp_path):
        out = patch(tmp_path, patchers.pex_patcher, build_pex(0x0A2C8E, store_null_first=True), binary=True)
        assert out == build_pex(0x000A0A, store_null_first=True)


# --------------------------------------------------------------------------- jslot
class TestJslot:
    def test_head_texture_and_head_parts(self, tmp_path):
        data = {"actor": {"headTexture": "Mod.esp|0A2C8E"},
                "headParts": [{"formIdentifier": "Mod.esp|0A2C8F", "formId": 0x010A2C8F}]}
        out = patch_json(tmp_path, patchers.jslot_patcher, data)
        assert out["actor"]["headTexture"] == "Mod.esp|000A0A"
        assert out["headParts"][0]["formIdentifier"] == "Mod.esp|000A0B"
        assert out["headParts"][0]["formId"] == 0x01000A0B

    def test_other_plugin_untouched(self, tmp_path):
        data = {"actor": {"headTexture": "Other.esp|0A2C8E"}}
        assert patch_json(tmp_path, patchers.jslot_patcher, data) == data
