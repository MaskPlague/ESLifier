"""
file_patchers.patchers: BeeingFemale INI, Dynamic Animation Casting / Actor Value Generator TOML, DBD,
DynDOLOD LIGH json (batch 2a). Same mapping as the other file patcher tests:
    0x0A2C8E -> A0A, 0x0A2C8F -> A0B, 0x0A2C90 -> A0C (moves into ESLifier_Cell_Master.esm)
"""
import json

from file_patchers import patchers
from plugin_builder import map_entry

BASENAME = "mod.esp"
CELL_MASTER = "ESLifier_Cell_Master.esm"
FORM_ID_MAP = {
    0x0A2C8E: map_entry("A0A"),
    0x0A2C8F: map_entry("A0B"),
    0x0A2C90: map_entry("A0C", update_name=True),
}


def run_text(tmp_path, fn, text, *args, name="file.txt", mapping=None):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    fn(BASENAME, str(path), FORM_ID_MAP if mapping is None else mapping, *args)
    return path.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------ BeeingFemale
class TestBeeingFemale:
    def run(self, tmp_path, text):
        return run_text(tmp_path, patchers.ini_beeingfemale_patcher, text, name="bf.ini")

    def test_form_lines_after_the_matching_modfile_are_rewritten(self, tmp_path):
        text = "modfile = Mod.esp\nform = 0x0A2C8E\nform=0x0A2C8F\n"
        assert self.run(tmp_path, text) == "modfile = Mod.esp\nform= 0xA0A\nform= 0xA0B\n"

    def test_forms_for_other_modfiles_are_untouched(self, tmp_path):
        text = "modfile = Other.esp\nform = 0x0A2C8E\n"
        assert self.run(tmp_path, text) == text

    def test_plugin_colon_formid_references_inline(self, tmp_path):
        text = "spell = Mod.esp:0A2C8E and mod.esp:0A2C8F\n"
        assert self.run(tmp_path, text) == "spell = Mod.esp:A0A and mod.esp:A0B\n"

    def test_truncated_plugin_name_references(self, tmp_path):
        # BeeingFemale also references "beeingfemale:FormID" without the extension
        text = "x = mod:0A2C8E\n"
        assert self.run(tmp_path, text) == "x = mod:A0A\n"

    def test_unmapped_ids_and_other_plugins_are_untouched(self, tmp_path):
        text = "modfile = Mod.esp\nform = 0x00FFFF\nx = Other.esp:0A2C8E\n"
        assert self.run(tmp_path, text) == text


# ------------------------------------------------------------------------------------------ Dynamic Animation Casting
class TestDynamicAnimationCasting:
    def run(self, tmp_path, text):
        return run_text(tmp_path, patchers.toml_dynamic_animation_casting_patcher, text, name="dac.toml")

    def test_plugin_pipe_formid_in_quotes(self, tmp_path):
        text = 'spells = ["Mod.esp|0x0A2C8E", "MOD.ESP|666767", "Other.esp|0x0A2C8E"]\n'
        assert self.run(tmp_path, text) == 'spells = ["Mod.esp|0xA0A", "MOD.ESP|0xA0B", "Other.esp|0x0A2C8E"]\n'

    def test_espname_keys_patch_the_matching_formid_keys_in_the_same_event(self, tmp_path):
        text = ('[[event]]\n'
                'weaponFormID = 0x0A2C8E\n'
                'weaponEspName = "Mod.esp"\n'
                'weaponFormIDs = [0x0A2C8F, 5]\n'
                'unrelated = 0x0A2C8E\n')
        out = self.run(tmp_path, text)
        assert out == ('[[event]]\n'
                       'weaponFormID = 0xA0A\n'
                       'weaponEspName = "Mod.esp"\n'
                       'weaponFormIDs = [0xA0B, 5]\n'
                       'unrelated = 0x0A2C8E\n')

    def test_weapon_prefix_also_covers_equipped_hand_keys(self, tmp_path):
        text = '[[event]]\nweaponEspName = "mod.esp"\nisEquippedRightFormID = 0x0A2C8E\nisEquippedLeftFormID = 0x0A2C8F\n'
        out = self.run(tmp_path, text)
        assert "isEquippedRightFormID = 0xA0A" in out and "isEquippedLeftFormID = 0xA0B" in out

    def test_the_search_stops_at_the_event_boundary(self, tmp_path):
        text = ('[[event]]\nweaponFormID = 0x0A2C8E\n'
                '[[event]]\nweaponEspName = "Mod.esp"\n'
                '[[event]]\nweaponFormID = 0x0A2C8E\n')
        out = self.run(tmp_path, text)
        assert out == text

    def test_other_plugins_comments_and_unmapped_ids_untouched(self, tmp_path):
        text = ('# "Mod.esp|0x0A2C8E"\n'
                '[[event]]\nweaponEspName = "Other.esp"\nweaponFormID = 0x0A2C8E\n'
                '[[event]]\nactorEspName = "Mod.esp"\nactorFormID = 0x00FFFF\n')
        assert self.run(tmp_path, text) == text


# ------------------------------------------------------------------------------------------ Actor Value Generator
class TestActorValueGenerator:
    def run(self, tmp_path, text):
        return run_text(tmp_path, patchers.toml_actor_value_generator_patcher, text, name="avg.toml")

    def test_object_plugin_double_colon_formid(self, tmp_path):
        text = 'a = "Object: Mod.esp::0x0A2C8E, x"\nb = "Object: MOD.ESP::0x0A2C8F"\n'
        assert self.run(tmp_path, text) == 'a = "Object: Mod.esp::0xA0A, x"\nb = "Object: MOD.ESP::0xA0B"\n'

    def test_other_plugins_unmapped_and_empty_ids_untouched(self, tmp_path):
        text = 'a = "Object: Other.esp::0x0A2C8E"\nb = "Object: Mod.esp::0x00FFFF"\nc = "Object: Mod.esp::0x"\n'
        assert self.run(tmp_path, text) == text

    def test_lines_without_object_are_untouched(self, tmp_path):
        text = 'a = "Mod.esp::0x0A2C8E"\n'
        assert self.run(tmp_path, text) == text


# ------------------------------------------------------------------------------------------ DBD
class TestDBD:
    def run(self, tmp_path, text):
        return run_text(tmp_path, patchers.dbd_patcher, text, name="dbd.txt")

    def test_form_id_pipe_plugin_is_rewritten_keeping_the_prefix_style(self, tmp_path):
        text = "item = 0x0A2C8E|Mod.esp\nitem = 0A2C8F|Mod.esp\n"
        assert self.run(tmp_path, text) == "item = 0xA0A|Mod.esp\nitem = A0B|Mod.esp\n"

    def test_cell_master_replaces_the_plugin(self, tmp_path):
        out = self.run(tmp_path, "item = 0x0A2C90|Mod.esp\n")
        assert out == f"item = 0xA0C|{CELL_MASTER}\n"

    def test_several_references_on_one_line(self, tmp_path):
        out = self.run(tmp_path, "a = 0x0A2C8E|Mod.esp, 0x0A2C8F|Mod.esp\n")
        assert "0xA0A|Mod.esp" in out and "0xA0B|Mod.esp" in out

    def test_other_plugins_and_unmapped_ids_untouched(self, tmp_path):
        text = "a = 0x0A2C8E|Other.esp\nb = 0x00FFFF|Mod.esp\nc = Mod.esp\n"
        assert self.run(tmp_path, text) == text


# ------------------------------------------------------------------------------------------ DynDOLOD LIGH
class TestDynDolodLigh:
    MASTER = b"\x05"

    def run(self, tmp_path, data):
        path = tmp_path / "ligh.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        mapping = {k: dict(v, bytes=bytes.fromhex(v["hex"])) for k, v in FORM_ID_MAP.items()}
        patchers.json_dyndolod_ligh_patcher(BASENAME, str(path), mapping, self.MASTER)
        return json.loads(path.read_text(encoding="utf-8"))

    def test_keys_for_the_plugin_are_renumbered(self, tmp_path):
        data = {"000A2C8E,mod.esp": {"x": 1}, "000A2C8F,Mod.esp": {"x": 2}, "000A2C8E,other.esp": {"x": 3}}
        out = self.run(tmp_path, data)
        assert list(out) == ["00000A0A,mod.esp", "00000A0B,Mod.esp", "000A2C8E,other.esp"]
        assert list(out.values()) == [{"x": 1}, {"x": 2}, {"x": 3}]

    def test_cell_number_with_the_master_byte_is_remapped(self, tmp_path):
        cell = int.from_bytes(self.MASTER + bytes.fromhex("0A2C8E"))
        out = self.run(tmp_path, {"000A2C8E,mod.esp": {"Cell": cell}})
        assert out["00000A0A,mod.esp"]["Cell"] == int.from_bytes(self.MASTER + bytes.fromhex("000A0A"))

    def test_cell_number_below_the_master_byte_is_left_alone(self, tmp_path):
        cell = int.from_bytes(b"\x01" + bytes.fromhex("0A2C8E"))
        out = self.run(tmp_path, {"000A2C8E,mod.esp": {"Cell": cell}})
        assert out["00000A0A,mod.esp"]["Cell"] == cell

    def test_string_values_and_nested_dict_values_ending_with_the_plugin(self, tmp_path):
        data = {"000A2C8E,mod.esp": {"Ref": "000A2C8F,mod.esp", "Other": "000A2C8F,other.esp",
                                     "Sub": {"Ref": "000A2C8E,Mod.esp", "N": 5}}}
        value = self.run(tmp_path, data)["00000A0A,mod.esp"]
        assert value == {"Ref": "00000A0B,mod.esp", "Other": "000A2C8F,other.esp",
                         "Sub": {"Ref": "00000A0A,Mod.esp", "N": 5}}

    def test_entries_for_other_plugins_are_not_touched_at_all(self, tmp_path):
        data = {"000A2C8E,other.esp": {"Cell": 0x050A2C8E, "Ref": "000A2C8F,mod.esp"}}
        out = self.run(tmp_path, data)
        assert out["000A2C8E,other.esp"]["Cell"] == 0x050A2C8E
        assert out["000A2C8E,other.esp"]["Ref"] == "00000A0B,mod.esp"      # values are still patched for references to this plugin
