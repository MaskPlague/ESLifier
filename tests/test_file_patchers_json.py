"""
file_patchers.patchers: the mod-specific JSON/YAML patchers (batch 1).

Same mapping as test_file_patchers.py:
    0x0A2C8E -> 0x000A0A   (stays in the same plugin)          decimal 666766 -> 2570
    0x0A2C8F -> 0x000A0B   (stays in the same plugin)          decimal 666767 -> 2571
    0x0A2C90 -> 0x000A0C   (moves into ESLifier_Cell_Master.esm, "update_name" = True)

``basename`` is the lower-cased compacted plugin ("mod.esp"); other plugins' entries must never change.
"""
import json

import pytest

from patchers.sse_file_patchers import patchers
from plugin_builder import map_entry

BASENAME = "mod.esp"
CELL_MASTER = "ESLifier_Cell_Master.esm"

FORM_ID_MAP = {
    0x0A2C8E: map_entry("A0A"),
    0x0A2C8F: map_entry("A0B"),
    0x0A2C90: map_entry("A0C", update_name=True),
}


def run_json(tmp_path, fn, data, *args, mapping=None, **kw):
    path = tmp_path / "file.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    fn(BASENAME, str(path), FORM_ID_MAP if mapping is None else mapping, *args, **kw)
    return json.loads(path.read_text(encoding="utf-8"))


def run_text(tmp_path, fn, text, name="file.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    fn(BASENAME, str(path), FORM_ID_MAP)
    return path.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------ storage util data
class TestStorageUtilData:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_storage_util_data_patcher, data)

    def test_hex_ids_stay_hex(self, tmp_path):
        out = self.run(tmp_path, {"a": ["0x0A2C8E|Mod.esp", "0x0A2C8F|mod.esp"]})
        assert out == {"a": ["0xA0A|Mod.esp", "0xA0B|mod.esp"]}

    def test_decimal_ids_stay_decimal(self, tmp_path):
        out = self.run(tmp_path, {"a": f"{0x0A2C8E}|Mod.esp"})
        assert out == {"a": "2570|Mod.esp"}

    def test_cell_master_replaces_the_plugin_name(self, tmp_path):
        out = self.run(tmp_path, {"hex": "0x0A2C90|Mod.esp", "dec": f"{0x0A2C90}|Mod.esp"})
        assert out == {"hex": f"0xA0C|{CELL_MASTER}", "dec": f"2572|{CELL_MASTER}"}

    def test_other_plugins_unmapped_ids_and_plain_strings_are_untouched(self, tmp_path):
        data = {"a": "0x0A2C8E|Other.esp", "b": "0x00FFFF|Mod.esp", "c": "no pipe", "d": 5, "e": {"f": ["x|y"]}}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ OBody NG
class TestOBody:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_obody_patcher, data)

    def test_form_id_keys_under_the_plugin_are_renamed(self, tmp_path):
        out = self.run(tmp_path, {"npc": {"Mod.esp": {"0A2C8E": ["Preset A"], "0A2C8F": ["Preset B"]}}})
        assert out == {"npc": {"Mod.esp": {"000A0A": ["Preset A"], "000A0B": ["Preset B"]}}}

    def test_short_keys_and_prefixed_keys(self, tmp_path):
        out = self.run(tmp_path, {"npc": {"Mod.esp": {"A2C8E": ["x"]}}, "faction": {"MOD.ESP": {"0x0A2C8F": ["y"]}}})
        assert out == {"npc": {"Mod.esp": {"000A0A": ["x"]}}, "faction": {"MOD.ESP": {"0x000A0B": ["y"]}}}

    def test_other_plugins_and_unmapped_ids_are_untouched(self, tmp_path):
        data = {"npc": {"Other.esp": {"0A2C8E": ["x"]}, "Mod.esp": {"00FFFF": ["y"]}}}
        assert self.run(tmp_path, data) == data

    def test_same_form_id_under_another_plugin_is_left_alone(self, tmp_path):
        out = self.run(tmp_path, {"npc": {"Other.esp": {"0A2C8E": ["x"]}, "Mod.esp": {"0A2C8E": ["y"]}}})
        assert out == {"npc": {"Other.esp": {"0A2C8E": ["x"]}, "Mod.esp": {"000A0A": ["y"]}}}


# ------------------------------------------------------------------------------------------ Skyrim Utility Mod
class TestSkyrimUtilityMod:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_skyrim_utility_mod_patcher, data)

    def test_form_id_before_the_plugin_is_rewritten_as_hex(self, tmp_path):
        out = self.run(tmp_path, {"cmd": "formId:0x0A2C8E|Mod.esp"})
        assert out == {"cmd": "formId:0x000A0A|Mod.esp"}

    def test_cell_master_replaces_the_plugin(self, tmp_path):
        out = self.run(tmp_path, {"cmd": "formId:0x0A2C90|Mod.esp rest"})
        assert out == {"cmd": f"formId:0x000A0C|{CELL_MASTER} rest"}

    def test_several_references_in_one_string(self, tmp_path):
        out = self.run(tmp_path, {"cmd": "formId=0x0A2C8E|Mod.esp;formId=0x0A2C8F|Mod.esp"})
        assert out == {"cmd": "formId=0x000A0A|Mod.esp;formId=0x000A0B|Mod.esp"}

    def test_strings_without_formid_or_for_other_plugins_are_untouched(self, tmp_path):
        data = {"a": "0x0A2C8E|Mod.esp", "b": "formId:0x0A2C8E|Other.esp", "c": "formId:0x00FFFF|Mod.esp"}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Undaunted
class TestUndaunted:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_undaunted_patcher, data)

    def test_ids_are_converted_to_decimal_ints(self, tmp_path):
        data = [[["Header", "x", 0], ["Bounty", "Mod.esp", 0x0A2C8E], ["Other", "Other.esp", 0x0A2C8E]],
                [["Hdr", "y", 0], ["B2", "MOD.esp", 0x0A2C8F]]]
        assert self.run(tmp_path, data) == [
            [["Header", "x", 0], ["Bounty", "Mod.esp", 2570], ["Other", "Other.esp", 0x0A2C8E]],
            [["Hdr", "y", 0], ["B2", "MOD.esp", 2571]]]

    def test_the_very_first_line_is_treated_as_a_header_and_skipped(self, tmp_path):
        data = [[["Header", "Mod.esp", 0x0A2C8E], ["Bounty", "Mod.esp", 0x0A2C8E]]]
        assert self.run(tmp_path, data) == [[["Header", "Mod.esp", 0x0A2C8E], ["Bounty", "Mod.esp", 2570]]]

    def test_unmapped_ids_untouched(self, tmp_path):
        data = [[["H", "x", 0], ["B", "Mod.esp", 5]]]
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Achievement Injector
class TestAchievementInjector:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_achievement_injector_patcher, data)

    def test_conditions_inherit_the_files_plugin(self, tmp_path):
        data = {"plugin": "Mod.esp", "achievements": [{"conditions": [{"formID": "0A2C8E"}, {"formID": "0A2C8F"}]}]}
        out = self.run(tmp_path, data)
        assert out["achievements"][0]["conditions"] == [{"formID": "000A0A"}, {"formID": "000A0B"}]

    def test_plugin_override_selects_the_plugin_per_condition(self, tmp_path):
        data = {"plugin": "Other.esp", "achievements": [{"conditions": [
            {"formID": "0A2C8E", "pluginOverride": "Mod.esp"},
            {"formID": "0A2C8E", "pluginOverride": "Third.esp"},
            {"formID": "0A2C8E"}]}]}
        conditions = self.run(tmp_path, data)["achievements"][0]["conditions"]
        assert conditions == [{"formID": "000A0A", "pluginOverride": "Mod.esp"},
                              {"formID": "0A2C8E", "pluginOverride": "Third.esp"},
                              {"formID": "0A2C8E"}]

    def test_override_of_another_plugin_wins_over_the_files_plugin(self, tmp_path):
        data = {"plugin": "Mod.esp", "achievements": [{"conditions": [{"formID": "0A2C8E", "pluginOverride": "Other.esp"}]}]}
        assert self.run(tmp_path, data) == data

    def test_cell_ids_and_cell_master(self, tmp_path):
        data = {"plugin": "Mod.esp", "achievements": [{"conditions": [{"cellID": "0A2C90"}, {"formID": "0A2C90"}]}]}
        conditions = self.run(tmp_path, data)["achievements"][0]["conditions"]
        assert conditions == [{"cellID": "000A0C", "pluginOverride": CELL_MASTER},
                              {"formID": "000A0C", "pluginOverride": CELL_MASTER}]

    def test_file_without_achievements_is_unchanged(self, tmp_path):
        assert self.run(tmp_path, {"plugin": "Mod.esp"}) == {"plugin": "Mod.esp"}


# ------------------------------------------------------------------------------------------ RIM Combat / Hunted or Hunter
class TestRimCombat:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_rim_combat_patcher, data)

    def test_items_for_the_plugin_get_new_hex_ids(self, tmp_path):
        data = {"weapons": [{"mod": "Mod.esp", "formID": "0x0A2C8E"}, {"mod": "mod.esp", "form": "0x0A2C8F"}]}
        assert self.run(tmp_path, data) == {"weapons": [{"mod": "Mod.esp", "formID": "0xA0A"},
                                                         {"mod": "mod.esp", "form": "0xA0B"}]}

    def test_nested_structures_are_searched(self, tmp_path):
        data = {"a": {"b": [{"c": [{"mod": "Mod.esp", "formID": "0x0A2C8E"}]}]}}
        assert self.run(tmp_path, data)["a"]["b"][0]["c"][0]["formID"] == "0xA0A"

    @pytest.mark.parametrize("item", [
        {"mod": "Other.esp", "formID": "0x0A2C8E"},
        {"mod": "Mod.esp", "formID": "0A2C8E"},            # no 0x prefix -> ignored
        {"mod": "Mod.esp"},                                # no id at all
        {"mod": "Mod.esp", "formID": "0x00FFFF"},          # not in the map
    ])
    def test_everything_else_is_untouched(self, tmp_path, item):
        assert self.run(tmp_path, [item]) == [item]


class TestYamlSlppSos:
    def test_ids_in_the_plugins_block_are_updated_in_place(self, tmp_path):
        text = ("- ESP: Mod.esp\n"
                "  ID: 0x0A2C8E\n"
                "  Others:\n"
                "    - 0x0A2C8F\n"
                f"    - {0x0A2C8E}\n"
                "- ESP: Other.esp\n"
                "  ID: 0x0A2C8E\n")
        out = run_text(tmp_path, patchers.yaml_slpp_sos_patcher, text)
        assert out == ("- ESP: Mod.esp\n"
                       "  ID: 0xA0A\n"
                       "  Others:\n"
                       "    - 0xA0B\n"
                       "    - 2570\n"
                       "- ESP: Other.esp\n"
                       "  ID: 0x0A2C8E\n")

    def test_plugin_name_match_is_case_insensitive(self, tmp_path):
        out = run_text(tmp_path, patchers.yaml_slpp_sos_patcher, "- ESP: MOD.ESP\n  ID: 0x0A2C8F\n")
        assert out == "- ESP: MOD.ESP\n  ID: 0xA0B\n"

    def test_unmapped_ids_and_files_for_other_plugins_are_untouched(self, tmp_path):
        text = "- ESP: Mod.esp\n  ID: 0x00FFFF\n- ESP: Other.esp\n  ID: 0x0A2C8E\n"
        assert run_text(tmp_path, patchers.yaml_slpp_sos_patcher, text) == text


# ------------------------------------------------------------------------------------------ Smart Harvest
class TestSmartHarvest:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_smart_harvest_patcher, data)

    def test_forms_after_the_matching_plugin_are_rewritten(self, tmp_path):
        data = {"items": [{"plugin": "Mod.esp", "form": ["0A2C8E", "0A2C8F"]},
                          {"plugin": "Other.esp", "form": ["0A2C8E"]}]}
        out = self.run(tmp_path, data)
        assert out["items"][0] == {"plugin": "Mod.esp", "form": ["00000A0A", "00000A0B"]}
        assert out["items"][1] == {"plugin": "Other.esp", "form": ["0A2C8E"]}

    def test_cell_master_replaces_the_plugin_name(self, tmp_path):
        out = self.run(tmp_path, {"items": [{"plugin": "Mod.esp", "form": ["0A2C90"]}]})
        assert out["items"][0] == {"plugin": CELL_MASTER, "form": ["00000A0C"]}

    def test_unmapped_forms_are_untouched(self, tmp_path):
        data = {"items": [{"plugin": "Mod.esp", "form": ["00FFFF"]}]}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Dynamic String Distributor
class TestDynamicStringDistributor:
    def run(self, tmp_path, data, mapping=None):
        return run_json(tmp_path, patchers.json_dynamic_string_distributor_patcher, data, mapping=mapping)

    def test_six_digit_and_full_eight_digit_ids(self, tmp_path):
        out = self.run(tmp_path, {"a": [{"form_id": "0A2C8E|Mod.esp"}, {"form_id": "000A2C8F|MOD.ESP"}]})
        assert out == {"a": [{"form_id": "000A0A|Mod.esp"}, {"form_id": "000A0B|MOD.ESP"}]}

    def test_light_plugin_ids_use_the_last_three_digits(self, tmp_path):
        mapping = {0x800: map_entry("801")}
        out = self.run(tmp_path, {"a": {"form_id": "FE000800|Mod.esp"}}, mapping)
        assert out == {"a": {"form_id": "000801|Mod.esp"}}

    def test_cell_master(self, tmp_path):
        out = self.run(tmp_path, {"a": {"form_id": "0A2C90|Mod.esp"}})
        assert out == {"a": {"form_id": f"000A0C|{CELL_MASTER}"}}

    def test_only_form_id_fields_for_this_plugin_are_touched(self, tmp_path):
        data = {"form_id": "0A2C8E|Other.esp", "other_key": "0A2C8E|Mod.esp", "x": {"form_id": "0A2C8E"}}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Dynamic Key Activation Framework
class TestDynamicKeyActivationFramework:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_dynamic_key_activation_framework_patcher, data)

    def test_ids_after_the_plugin_name_are_rewritten(self, tmp_path):
        out = self.run(tmp_path, {"a": ["Mod.esp|0x0A2C8E", "MOD.ESP|0x0A2C8F"]})
        assert out == {"a": ["Mod.esp|0xA0A", "MOD.ESP|0xA0B"]}

    def test_cell_master(self, tmp_path):
        assert self.run(tmp_path, {"a": "Mod.esp|0x0A2C90"}) == {"a": f"{CELL_MASTER}|0xA0C"}

    def test_other_plugins_and_unmapped_ids_untouched(self, tmp_path):
        data = {"a": "Other.esp|0x0A2C8E", "b": "Mod.esp|0x00FFFF", "c": "plain"}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Dynamic Armor Variants
class TestDynamicArmorVariants:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_dynamic_armor_variants_patcher, data)

    def test_replace_by_form_keys_and_values_are_both_rewritten(self, tmp_path):
        data = {"v": {"replaceByForm": {"Mod.esp|0A2C8E": "Mod.esp|0A2C8F"}}}
        assert self.run(tmp_path, data) == {"v": {"replaceByForm": {"Mod.esp|A0A": "Mod.esp|A0B"}}}

    def test_values_for_this_plugin_are_patched_even_when_the_key_is_for_another(self, tmp_path):
        data = {"v": {"replaceByForm": {"Other.esp|0A2C8E": "Mod.esp|0A2C8F"}}}
        assert self.run(tmp_path, data) == {"v": {"replaceByForm": {"Other.esp|0A2C8E": "Mod.esp|A0B"}}}

    def test_other_replace_sections_only_patch_values(self, tmp_path):
        data = {"v": {"replaceByEDID": {"SomeEdid": "Mod.esp|0A2C8E"}}}
        assert self.run(tmp_path, data) == {"v": {"replaceByEDID": {"SomeEdid": "Mod.esp|A0A"}}}

    def test_cell_master_for_keys_and_values(self, tmp_path):
        data = {"v": {"replaceByForm": {"Mod.esp|0A2C90": "Mod.esp|0A2C90"}}}
        assert self.run(tmp_path, data) == {"v": {"replaceByForm": {f"{CELL_MASTER}|A0C": f"{CELL_MASTER}|A0C"}}}

    def test_unmapped_ids_untouched(self, tmp_path):
        data = {"v": {"replaceByForm": {"Mod.esp|00FFFF": "Mod.esp|00FFFE"}}}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ JContainers
class TestJContainer:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_jcontainer_patcher, data)

    def test_form_data_values_are_rewritten(self, tmp_path):
        out = self.run(tmp_path, {"a": ["__formData|Mod.esp|0x0A2C8E", "__formdata|MOD.ESP|0x0A2C8F"]})
        assert out == {"a": ["__formData|Mod.esp|0xA0A", "__formdata|MOD.ESP|0xA0B"]}

    def test_form_data_keys_are_rewritten(self, tmp_path):
        out = self.run(tmp_path, {"__formData|Mod.esp|0x0A2C8E": {"count": 1}})
        assert out == {"__formData|Mod.esp|0xA0A": {"count": 1}}

    def test_text_after_the_form_id_is_kept(self, tmp_path):
        out = self.run(tmp_path, {"a": "__formData|Mod.esp|0x0A2C8E|extra"})
        assert out == {"a": "__formData|Mod.esp|0xA0A|extra"}

    def test_other_plugins_and_unmapped_ids_untouched(self, tmp_path):
        data = {"a": "__formData|Other.esp|0x0A2C8E", "b": "__formData|Mod.esp|0x00FFFF", "c": "plain",
                "__formData|Other.esp|0x0A2C8E": {"x": 1}}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Immersive Equipment Displays
class TestImmersiveEquipmentDisplays:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_immersive_equipment_displays_patcher, data)

    def test_numeric_ids_before_the_plugin_are_rewritten(self, tmp_path):
        data = {"e": [{"id": 0x0A2C8E, "plugin": "Mod.esp"}, {"id": 0x0A2C8E, "plugin": "Other.esp"}]}
        assert self.run(tmp_path, data) == {"e": [{"id": 2570, "plugin": "Mod.esp"},
                                                  {"id": 0x0A2C8E, "plugin": "Other.esp"}]}

    def test_cell_master(self, tmp_path):
        out = self.run(tmp_path, {"e": [{"id": 0x0A2C90, "plugin": "MOD.ESP"}]})
        assert out == {"e": [{"id": 2572, "plugin": CELL_MASTER}]}

    def test_unmapped_ids_untouched(self, tmp_path):
        data = {"e": [{"id": 5, "plugin": "Mod.esp"}]}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ OStim
class TestOStim:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_ostim_patcher, data)

    def test_form_ids_following_the_mod_are_rewritten(self, tmp_path):
        data = {"actors": [{"mod": "Mod.esp", "formID": "0x0A2C8E"}, {"mod": "Other.esp", "formID": "0x0A2C8E"}]}
        assert self.run(tmp_path, data) == {"actors": [{"mod": "Mod.esp", "formID": "0xA0A"},
                                                       {"mod": "Other.esp", "formID": "0x0A2C8E"}]}

    def test_cell_master_replaces_the_mod(self, tmp_path):
        out = self.run(tmp_path, {"actors": [{"mod": "Mod.esp", "formID": "0x0A2C90"}]})
        assert out == {"actors": [{"mod": CELL_MASTER, "formID": "0xA0C"}]}

    def test_an_unrelated_key_in_between_ends_the_match(self, tmp_path):
        data = {"actors": [{"mod": "Mod.esp", "note": "x", "formID": "0x0A2C8E"}]}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Dress Up Lovers
class TestDressUpLovers:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_dressuplovers_patcher, data)

    def test_id_after_the_plugin_name_is_rewritten(self, tmp_path):
        out = self.run(tmp_path, {"a": [["Mod.esp", "0A2C8E"], ["MOD.ESP", "0A2C8F"], ["Other.esp", "0A2C8E"]]})
        assert out == {"a": [["Mod.esp", "000A0A"], ["MOD.ESP", "000A0B"], ["Other.esp", "0A2C8E"]]}

    def test_unmapped_ids_untouched(self, tmp_path):
        data = {"a": [["Mod.esp", "00FFFF"]]}
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Dismembering Framework
class TestDismemberingFramework:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_dismembering_framework_patcher, data)

    def test_keys_and_values_are_rewritten(self, tmp_path):
        data = {"cat": {"Mod.esp:0x0A2C8E": ["Mod.esp:0x0A2C8F", "Other.esp:0x0A2C8E"]}}
        assert self.run(tmp_path, data) == {"cat": {"Mod.esp:0xA0A": ["Mod.esp:0xA0B", "Other.esp:0x0A2C8E"]}}

    def test_other_plugin_keys_and_unmapped_ids_untouched(self, tmp_path):
        data = {"cat": {"Other.esp:0x0A2C8E": ["x"], "Mod.esp:0x00FFFF": ["Mod.esp:0x00FFFE"]}}
        assert self.run(tmp_path, data) == data

    def test_plugin_case_is_preserved(self, tmp_path):
        out = self.run(tmp_path, {"cat": {"MOD.ESP:0x0A2C8E": ["y"]}})
        assert out == {"cat": {"MOD.ESP:0xA0A": ["y"]}}


# ------------------------------------------------------------------------------------------ Alternate Perspective
class TestAlternatePerspective:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_alternate_perspective, data)

    def test_top_level_entry_for_the_plugin(self, tmp_path):
        out = self.run(tmp_path, [{"mod": "Mod.esp", "id": "0x0A2C8E"}, {"mod": "Other.esp", "id": "0x0A2C8E"}])
        assert out == [{"mod": "Mod.esp", "id": "0xA0A"}, {"mod": "Other.esp", "id": "0x0A2C8E"}]

    def test_suboptions_inherit_the_mod_and_are_rewritten(self, tmp_path):
        out = self.run(tmp_path, [{"mod": "Mod.esp", "id": "0x0A2C8E", "suboptions": [{"id": "0x0A2C8F"}]}])
        assert out[0]["suboptions"] == [{"id": "0xA0B"}]

    def test_moving_the_outer_entry_to_the_cell_master_pins_inheriting_suboptions_to_the_old_plugin(self, tmp_path):
        data = [{"mod": "Mod.esp", "id": "0x0A2C90", "suboptions": [{"id": "0x0A2C8F"}, {"id": "0x00FFFF"}, {"id": 5}]}]
        out = self.run(tmp_path, data)
        assert out[0]["mod"] == CELL_MASTER and out[0]["id"] == "0xA0C"
        subs = out[0]["suboptions"]
        assert subs[0] == {"mod": "Mod.esp", "id": "0xA0B"}            # keeps pointing at the original plugin
        assert subs[1] == {"mod": "Mod.esp", "id": "0x00FFFF"}
        assert subs[2] == {"mod": "Mod.esp", "id": 5}
        assert list(subs[0])[0] == "mod"                                # the mod key is inserted first

    def test_suboption_that_itself_moves_to_the_cell_master_gets_an_explicit_mod(self, tmp_path):
        data = [{"mod": "Mod.esp", "id": "0x0A2C8E", "suboptions": [{"id": "0x0A2C90"}]}]
        out = self.run(tmp_path, data)
        assert out[0]["mod"] == "Mod.esp"
        assert out[0]["suboptions"] == [{"mod": CELL_MASTER, "id": "0xA0C"}]

    def test_suboption_with_its_own_mod_is_patched_independently(self, tmp_path):
        data = [{"mod": "Other.esp", "id": "0x0A2C8E", "suboptions": [{"mod": "Mod.esp", "id": "0x0A2C90"},
                                                                       {"mod": "Mod.esp", "id": "0x0A2C8F"},
                                                                       {"mod": "Third.esp", "id": "0x0A2C8F"}]}]
        out = self.run(tmp_path, data)
        assert out[0]["id"] == "0x0A2C8E"
        assert out[0]["suboptions"] == [{"mod": CELL_MASTER, "id": "0xA0C"},
                                        {"mod": "Mod.esp", "id": "0xA0B"},
                                        {"mod": "Third.esp", "id": "0x0A2C8F"}]

    def test_entries_without_a_mod_or_matching_plugin_are_untouched(self, tmp_path):
        data = [{"id": "0x0A2C8E"}, {"mod": "Other.esp", "id": "0x0A2C8E", "suboptions": [{"id": "0x0A2C8F"}]}]
        assert self.run(tmp_path, data) == data


# ------------------------------------------------------------------------------------------ Fire Hurts RE
class TestFireHurtsRE:
    def run(self, tmp_path, data):
        return run_json(tmp_path, patchers.json_fire_hurts_re_patcher, data)

    def test_numeric_ids_under_the_plugin_are_rewritten(self, tmp_path):
        data = {"Mod.esp": {"a": {"id": 0x0A2C8E, "name": "x"}, "b": [{"id": 0x0A2C8F}]},
                "Other.esp": {"a": {"id": 0x0A2C8E}}}
        assert self.run(tmp_path, data) == {"Mod.esp": {"a": {"id": 2570, "name": "x"}, "b": [{"id": 2571}]},
                                            "Other.esp": {"a": {"id": 0x0A2C8E}}}

    def test_non_numeric_and_unmapped_ids_untouched(self, tmp_path):
        data = {"mod.esp": {"a": {"id": "0A2C8E"}, "b": {"id": 5}, "c": {"other": 0x0A2C8E}}}
        assert self.run(tmp_path, data) == data
