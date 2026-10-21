"""
cell_changed_scanner.cell_scanner: finds mods whose new cells are modified by plugins that depend on them
(those mods can't be ESL-flagged/compacted safely). Uses tiny hand-built plugins from plugin_builder.
"""
import json
import ntpath
import threading
import types

import pytest

from scanners import cell_changed_scanner
from scanners.cell_changed_scanner import cell_scanner
from plugin_builder import cell_record, fid, grup, plugin, record, tes4, write


@pytest.fixture
def scanner(workdir, monkeypatch):
    """Fresh class-level state (cell_scanner keeps everything on the class) inside a temp cwd."""
    # ESLifier runs on Windows; make os.path in the module under test split backslashes on any platform.
    monkeypatch.setattr(cell_changed_scanner, "os", types.SimpleNamespace(path=ntpath))
    cell_scanner.result_set = set()
    cell_scanner.lock = threading.Lock()
    cell_scanner.dependency_dict = {}
    (workdir / "ESLifier_Data" / "Cell_IDs").mkdir()
    return workdir


def stored_hex(object_id: int) -> str:
    """The text ESLifier stores in *_CellFormIDs.txt: the 3 object-id bytes in file (little endian) order."""
    return fid(0, object_id)[:3].hex()


def dependent_plugin(masters, cell_object_id, master_index):
    """A plugin that overrides one cell of the master at ``master_index``."""
    cell = cell_record(fid(master_index, cell_object_id), interior=True)
    return plugin(masters, grup(b"CELL", cell))


def write_cell_ids(root, mod, object_ids):
    path = root / "ESLifier_Data" / "Cell_IDs" / f"{mod}_CellFormIDs.txt"
    path.write_text("\n".join(stored_hex(i) for i in object_ids) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------ create_data_list
def test_create_data_list_splits_records_and_keeps_grup_headers_separate():
    a = record(b"KYWD", fid(0, 1))
    b = record(b"KYWD", fid(0, 2), b"abcd")
    data = tes4() + grup(b"KYWD", a + b)
    parts = cell_scanner.create_data_list(data)
    assert [p[:4] for p in parts] == [b"TES4", b"GRUP", b"KYWD", b"KYWD"]
    assert len(parts[1]) == 24                     # GRUP is just its header
    assert b"".join(parts) == data                 # nothing lost or duplicated


def test_create_data_list_empty_input():
    assert cell_scanner.create_data_list(b"") == []


# ------------------------------------------------------------------------------ get_master_index
@pytest.mark.parametrize("name,expected", [
    ("A.esm", 0), ("B.esp", 1), ("c.esl", 2),
    ("b.ESP", 1),                                    # case-insensitive
])
def test_get_master_index_by_position_in_master_list(name, expected):
    data_list = cell_scanner.create_data_list(plugin(["A.esm", "B.esp", "C.esl"]))
    assert cell_scanner.get_master_index(name, data_list) == expected


def test_get_master_index_uses_basename_of_path(scanner):
    data_list = cell_scanner.create_data_list(plugin(["A.esm", "B.esp"]))
    assert cell_scanner.get_master_index("C:\\mods\\Some Mod\\B.esp", data_list) == 1
    assert cell_scanner.get_master_index("/mods/Some Mod/B.esp", data_list) == 1


def test_get_master_index_returns_none_when_not_a_master():
    data_list = cell_scanner.create_data_list(plugin(["A.esm"]))
    assert cell_scanner.get_master_index("Other.esp", data_list) is None


def test_get_master_index_with_no_masters():
    data_list = cell_scanner.create_data_list(plugin([]))
    assert cell_scanner.get_master_index("A.esm", data_list) is None


# ------------------------------------------------------------------------------ is_dependent_modifying
# It only answers the question for one dependent; check_if_dependents_modify_new_cells records the mod.
def test_dependent_overriding_one_of_the_new_cells_is_modifying(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    assert cell_scanner.is_dependent_modifying("C:\\mods\\Mod\\Mod.esp", dep, [stored_hex(0x800)]) is True
    assert cell_scanner.result_set == set()          # recording the result is the caller's job


def test_dependent_ignores_cells_not_in_the_new_cell_list(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x801, master_index=0))
    assert cell_scanner.is_dependent_modifying("Mod.esp", dep, [stored_hex(0x800)]) is False


def test_dependent_ignores_cells_owned_by_a_different_master(scanner):
    # Same object id, but it belongs to master #1 (Other.esp), not Mod.esp (master #0).
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp", "Other.esp"], 0x800, master_index=1))
    assert cell_scanner.is_dependent_modifying("Mod.esp", dep, [stored_hex(0x800)]) is False


def test_dependent_uses_the_masters_actual_index(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Base.esm", "Mod.esp"], 0x800, master_index=1))
    assert cell_scanner.is_dependent_modifying("Mod.esp", dep, [stored_hex(0x800)]) is True


def test_dependent_non_cell_records_are_ignored(scanner):
    body = grup(b"KYWD", record(b"KYWD", fid(0, 0x800)))
    dep = write(scanner / "dep.esp", plugin(["Mod.esp"], body))
    assert cell_scanner.is_dependent_modifying("Mod.esp", dep, [stored_hex(0x800)]) is False


def test_dependent_that_does_not_list_the_mod_as_a_master_is_not_modifying(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Other.esp"], 0x800, master_index=0))
    assert cell_scanner.is_dependent_modifying("Mod.esp", dep, [stored_hex(0x800)]) is False


# ------------------------------------------------------------------------------ check_if_dependents_modify_new_cells
def test_check_if_dependents_flags_mod(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    write_cell_ids(scanner, "Mod.esp", [0x800, 0x900])
    cell_scanner.dependency_dict = {"mod.esp": [dep]}
    cell_scanner.check_if_dependents_modify_new_cells("C:\\mods\\Mod\\Mod.esp")
    assert cell_scanner.result_set == set(["Mod.esp"])


def test_check_if_dependents_checks_every_dependent_until_a_hit(scanner):
    miss = write(scanner / "miss.esp", dependent_plugin(["Mod.esp"], 0x999, master_index=0))
    hit = write(scanner / "hit.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    write_cell_ids(scanner, "Mod.esp", [0x800])
    cell_scanner.dependency_dict = {"mod.esp": [miss, hit]}
    cell_scanner.check_if_dependents_modify_new_cells("Mod.esp")
    assert cell_scanner.result_set == set(["Mod.esp"])


def test_check_if_dependents_does_nothing_without_a_cell_id_file(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    cell_scanner.dependency_dict = {"mod.esp": [dep]}
    cell_scanner.check_if_dependents_modify_new_cells("Mod.esp")
    assert cell_scanner.result_set == set()


def test_check_if_dependents_does_nothing_when_mod_has_no_dependents_entry(scanner):
    write_cell_ids(scanner, "Mod.esp", [0x800])
    cell_scanner.dependency_dict = {"someone_else.esp": []}
    cell_scanner.check_if_dependents_modify_new_cells("Mod.esp")
    assert cell_scanner.result_set == set()


def test_check_if_dependents_does_nothing_when_cell_id_file_is_empty(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    (scanner / "ESLifier_Data" / "Cell_IDs" / "Mod.esp_CellFormIDs.txt").write_text("", encoding="utf-8")
    cell_scanner.dependency_dict = {"mod.esp": [dep]}
    cell_scanner.check_if_dependents_modify_new_cells("Mod.esp")
    assert cell_scanner.result_set == set()


# ------------------------------------------------------------------------------ scan / scan_new_dependents
def read_result(root):
    return set(json.loads((root / "ESLifier_Data" / "cell_changed.json").read_text(encoding="utf-8")))


def test_scan_reads_dependency_dictionary_and_writes_result(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    write_cell_ids(scanner, "Mod.esp", [0x800])
    (scanner / "ESLifier_Data" / "dependency_dictionary.json").write_text(
        json.dumps({"mod.esp": [dep]}), encoding="utf-8")
    cell_scanner.scan(["Mod.esp"])
    assert read_result(scanner) == set(["Mod.esp"])


def test_scan_handles_several_mods_in_threads(scanner):
    deps = {}
    for n in range(6):
        name = f"Mod{n}.esp"
        write_cell_ids(scanner, name, [0x800])
        # even-numbered mods have their cell changed by a dependent, odd-numbered ones don't
        cell_id = 0x800 if n % 2 == 0 else 0x801
        deps[name.lower()] = [write(scanner / f"dep{n}.esp", dependent_plugin([name], cell_id, 0))]
    (scanner / "ESLifier_Data" / "dependency_dictionary.json").write_text(json.dumps(deps), encoding="utf-8")
    cell_scanner.scan([f"Mod{n}.esp" for n in range(6)])
    assert set(sorted(read_result(scanner))) == set(["Mod0.esp", "Mod2.esp", "Mod4.esp"])


def test_scan_with_missing_dependency_dictionary_writes_empty_result(scanner):
    cell_scanner.scan(["Mod.esp"])
    assert read_result(scanner) == set()


def test_scan_new_dependents_lowercases_keys_and_skips_unknown_mods(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["mod.esp"], 0x800, master_index=0))
    write_cell_ids(scanner, "mod.esp", [0x800])
    write_cell_ids(scanner, "unlisted.esp", [0x800])
    cell_scanner.scan_new_dependents(["mod.esp", "unlisted.esp"], {"Mod.ESP": [dep]})
    assert cell_scanner.dependency_dict == {"mod.esp": [dep]}
    assert read_result(scanner) == set(["mod.esp"])


def test_scan_new_dependents_finds_mixed_case_mod_names(scanner):
    dep = write(scanner / "dep.esp", dependent_plugin(["Mod.esp"], 0x800, master_index=0))
    write_cell_ids(scanner, "Mod.esp", [0x800])
    cell_scanner.scan_new_dependents(["Mod.esp"], {"Mod.esp": [dep]})
    assert read_result(scanner) == set(["Mod.esp"])


def test_scan_new_dependents_resets_previous_results(scanner):
    cell_scanner.result_set = set(["Stale.esp"])
    cell_scanner.scan_new_dependents([], {})
    assert read_result(scanner) == set()


# ------------------------------------------------------------------------------ file helpers
def test_get_from_file_roundtrip_and_failures(tmp_path):
    good = tmp_path / "good.json"
    good.write_text('{"a": [1, 2]}', encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cell_scanner.get_from_file(str(good)) == {"a": [1, 2]}
    assert cell_scanner.get_from_file(str(bad)) == {}
    assert cell_scanner.get_from_file(str(tmp_path / "missing.json")) == {}


def test_dump_to_file_writes_list_with_unicode(tmp_path):
    cell_scanner.result_set = set(["Mödé.esp", "B.esp"])
    out = tmp_path / "out.json"
    cell_scanner.dump_to_file(str(out))
    text = out.read_text(encoding="utf-8")
    assert "Mödé.esp" in text                        # ensure_ascii=False
    assert set(json.loads(text)) == set(["Mödé.esp", "B.esp"])


def test_dump_to_file_reports_error_instead_of_raising(tmp_path, log):
    cell_scanner.result_set = set()
    cell_scanner.dump_to_file(str(tmp_path / "no_such_dir" / "out.json"))
    assert any("Failed to dump data to" in e for e in log.errors)


def test_unreadable_dependent_is_reported_and_skipped(scanner, log):
    assert cell_scanner.is_dependent_modifying("Mod.esp", str(scanner / "does_not_exist.esp"), [stored_hex(0x800)]) is False
    assert any("Failed to read data of" in e for e in log.errors)
