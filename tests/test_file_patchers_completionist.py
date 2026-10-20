"""
file_patchers.patchers: Completionist INI patchers (current and old format).
Mapping: 0x0A2C8E -> 0x000A0A, 0x0A2C8F -> 0x000A0B, 0x0A2C90 -> 0x000A0C (moves to ESLifier_Cell_Master.esm).
"""
import pytest

from file_patchers import patchers
from plugin_builder import map_entry

BASENAME = "mod.esp"
CELL_MASTER = "ESLifier_Cell_Master.esm"
FORM_ID_MAP = {
    0x0A2C8E: map_entry("A0A"),
    0x0A2C8F: map_entry("A0B"),
    0x0A2C90: map_entry("A0C", update_name=True),
}


def run(tmp_path, fn, text):
    path = tmp_path / "comp.ini"
    path.write_text(text, encoding="utf-8", newline="")
    fn(BASENAME, str(path), FORM_ID_MAP)
    return path.read_text(encoding="utf-8")


def patch_new(tmp_path, text):
    return run(tmp_path, patchers.ini_completionist_patcher, text)


def patch_old(tmp_path, text):
    return run(tmp_path, patchers.old_ini_completionist_patcher, text)


# ============================================================================================ current format
class TestCurrentFormat:
    def test_formids_single_line_for_the_files_own_plugin(self, tmp_path):
        text = "[Quest]\nPluginFileName = Mod.esp\nFormIDs = 0x0A2C8E, 0x0A2C8F\n"
        out = patch_new(tmp_path, text)
        assert "FormIDs = 0x000A0A, 0x000A0B" in out
        assert out.startswith("[Quest]\nPluginFileName = Mod.esp\n")

    def test_files_for_other_plugins_are_not_touched(self, tmp_path):
        text = "[Quest]\nPluginFileName = Other.esp\nFormIDs = 0x0A2C8E, 0x0A2C8F\n"
        assert patch_new(tmp_path, text) == text

    def test_unmapped_ids_stay_as_they_are(self, tmp_path):
        text = "PluginFileName = Mod.esp\nFormIDs = 0x00FFFF, 0x0A2C8E\n"
        assert "FormIDs = 0x00FFFF, 0x000A0A" in patch_new(tmp_path, text)

    def test_cell_master_id_gets_a_plugin_suffix(self, tmp_path):
        out = patch_new(tmp_path, "PluginFileName = Mod.esp\nFormIDs = 0x0A2C90\n")
        assert f"FormIDs = 0x000A0C*{CELL_MASTER}" in out

    def test_formids_block_with_end_tag(self, tmp_path):
        text = ("PluginFileName = Mod.esp\n"
                "FormIDs = <<< END\n"
                "0x0A2C8E, Item one\n"
                "0x0A2C8F, Item two\n"
                "0x0A2C90, Item three\n"
                "END\n"
                "Other = 0x0A2C8E\n")
        out = patch_new(tmp_path, text)
        lines = out.splitlines()
        assert lines[2] == "0x000A0A, Item one"
        assert lines[3] == "0x000A0B, Item two"
        assert lines[4] == f"0x000A0C*{CELL_MASTER}, Item three"
        assert lines[5] == "END"
        assert lines[6] == "Other = 0x0A2C8E"                      # outside the block, not an id list

    @pytest.mark.xfail(reason="_comp_form_id_processor strips the line when it starts with ';', dropping its newline, so a "
                              "commented-out line inside a FormIDs block is glued to the next line", strict=False)
    def test_commented_line_in_a_block_keeps_its_own_line(self, tmp_path):
        text = "PluginFileName = Mod.esp\nFormIDs = <<< END\n; 0x0A2C8F, commented out\n0x0A2C8E, x\nEND\n"
        assert patch_new(tmp_path, text).splitlines()[2:4] == ["; 0x000A0B, commented out", "0x000A0A, x"]

    def test_explicit_plugin_after_a_star_is_honoured(self, tmp_path):
        text = "PluginFileName = Other.esp\nFormIDs = 0x0A2C8E*Mod.esp, 0x0A2C8E*Third.esp, 0x0A2C8E\n"
        out = patch_new(tmp_path, text)
        assert "FormIDs = 0x000A0A*Mod.esp, 0x0A2C8E*Third.esp, 0x0A2C8E" in out

    def test_explicit_plugin_to_cell_master(self, tmp_path):
        out = patch_new(tmp_path, f"PluginFileName = Other.esp\nFormIDs = 0x0A2C90*Mod.esp\n")
        assert f"FormIDs = 0x000A0C*{CELL_MASTER}" in out

    def test_install_from_section_overrides_the_global_plugin(self, tmp_path):
        text = ("PluginFileName = Other.esp\n"
                "[Local]\nInstallFrom = Mod.esp\nFormIDs = 0x0A2C8E\n"
                "[Elsewhere]\nInstallFrom = Third.esp\nFormIDs = 0x0A2C8E\n")
        out = patch_new(tmp_path, text)
        assert "[Local]\nInstallFrom = Mod.esp\nFormIDs = 0x000A0A" in out
        assert "[Elsewhere]\nInstallFrom = Third.esp\nFormIDs = 0x0A2C8E" in out

    def test_variable_lines_have_their_key_rewritten(self, tmp_path):
        text = "PluginFileName = Mod.esp\n0x0A2C8E = 0x0A2C8F, 0x0A2C8E\n"
        out = patch_new(tmp_path, text)
        assert out.splitlines()[1] == "0x000A0A = 0x000A0B, 0x000A0A"

    def test_variable_lines_with_explicit_plugin(self, tmp_path):
        text = "PluginFileName = Other.esp\n0x0A2C8E*Mod.esp = 5\n0x0A2C8E*Other.esp = 6\n"
        lines = patch_new(tmp_path, text).splitlines()
        assert lines[1].startswith("0x000A0A*Mod.esp")
        assert lines[2] == "0x0A2C8E*Other.esp = 6"

    def test_special_suffix_variables_only_change_the_key(self, tmp_path):
        text = "PluginFileName = Mod.esp\n0x0A2C8E_DisplayName = Sword, of 0x0A2C8F\n"
        out = patch_new(tmp_path, text)
        assert out.splitlines()[1].startswith("0x000A0A_DisplayName")
        assert "of 0x0A2C8F" in out                                # the display text is never treated as ids

    def test_base_form_id_uses_the_quest_plugin(self, tmp_path):
        text = ("PluginFileName = Mod.esp\n[A]\nBaseFormID = 0x0A2C8E ; the quest\n"
                "[B]\nPluginFileName = Other.esp\nBaseFormID = 0x0A2C8E\n")
        out = patch_new(tmp_path, text)
        assert "BaseFormID = 0x000A0A ; the quest" in out
        assert "[B]\nPluginFileName = Other.esp\nBaseFormID = 0x0A2C8E" in out

    def test_valid_items_form_id_uses_valid_items_file_name(self, tmp_path):
        text = ("PluginFileName = Other.esp\n[A]\nvalidItemsFileName = Mod.esp\nvalidItemsFormID = 0x0A2C8F\n"
                "[B]\nvalidItemsFileName = Third.esp\nvalidItemsFormID = 0x0A2C8F\n")
        out = patch_new(tmp_path, text)
        assert "validItemsFormID = 0x000A0B" in out
        assert "[B]\nvalidItemsFileName = Third.esp\nvalidItemsFormID = 0x0A2C8F" in out

    def test_non_hex_values_are_not_treated_as_ids(self, tmp_path):
        text = "PluginFileName = Mod.esp\nFormIDs = 12345, 0x0A2C8E\n"
        assert "FormIDs = 12345, 0x000A0A" in patch_new(tmp_path, text)

    def test_comments_and_unrelated_lines_survive(self, tmp_path):
        text = "; comment 0x0A2C8E\n\nPluginFileName = Mod.esp\nName = Hello\n"
        assert patch_new(tmp_path, text) == text


# ============================================================================================ old format
class TestOldFormat:
    def test_formids_single_line(self, tmp_path):
        out = patch_old(tmp_path, "PluginFileName = Mod.esp\nFormIDs = 0x0A2C8E, 0x0A2C8F\n")
        assert "FormIDs = 0x000A0A, 0x000A0B" in out

    def test_other_plugin_untouched(self, tmp_path):
        text = "PluginFileName = Other.esp\nFormIDs = 0x0A2C8E\n"
        assert patch_old(tmp_path, text) == text

    def test_cell_master_suffix(self, tmp_path):
        out = patch_old(tmp_path, "PluginFileName = Mod.esp\nFormIDs = 0x0A2C90\n")
        assert f"0x000A0C*{CELL_MASTER}" in out

    def test_block_with_end_tag_and_comments(self, tmp_path):
        text = "PluginFileName = Mod.esp\nFormIDs <<< END\n0x0A2C8E, a\n0x0A2C8F, b\nEND\n"
        lines = patch_old(tmp_path, text).splitlines()
        assert lines[2] == "0x000A0A, a"
        assert lines[3] == "0x000A0B, b"

    @pytest.mark.xfail(reason="same newline loss as the current format: a ';' line inside a FormIDs block is glued "
                              "to the next line", strict=False)
    def test_commented_line_in_a_block_keeps_its_own_line(self, tmp_path):
        text = "PluginFileName = Mod.esp\nFormIDs <<< END\n; 0x0A2C8F, b\n0x0A2C8E, a\nEND\n"
        assert patch_old(tmp_path, text).splitlines()[2:4] == ["; 0x000A0B, b", "0x000A0A, a"]

    def test_explicit_plugin_star(self, tmp_path):
        out = patch_old(tmp_path, "PluginFileName = Other.esp\nFormIDs = 0x0A2C8E*Mod.esp, 0x0A2C8E*Third.esp\n")
        assert "0x000A0A*Mod.esp, 0x0A2C8E*Third.esp" in out

    def test_variable_lines(self, tmp_path):
        out = patch_old(tmp_path, "PluginFileName = Mod.esp\n0x0A2C8E_Name = 0x0A2C8F\n")
        assert out.splitlines()[1].startswith("0x000A0A_Name")
        assert "0x000A0B" in out.splitlines()[1]

    def test_variable_lines_with_explicit_plugin(self, tmp_path):
        out = patch_old(tmp_path, "PluginFileName = Other.esp\n0x0A2C90*Mod.esp = 0x0A2C8E\n")
        assert out.splitlines()[1].startswith(f"0x000A0C*{CELL_MASTER}")
