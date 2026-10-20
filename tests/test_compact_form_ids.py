"""
compact_form_ids.CFIDs: the heart of ESLifier. Rewrites a plugin's Form IDs into the ESL
range, remembers the mapping, and patches dependent plugins / SEQ files to match.
"""
import json
import os
import struct
import zlib

import pytest

from compact_form_ids import CFIDs
from create_cell_master import create_new_cell_plugin
from plugin_builder import (HEADER_VERSION_170, HEADER_VERSION_171, cell_record, fid, flatten, get_record,
                            grup, plugin, record, sub, walk, write)

SKYRIM = "Skyrim.esm"
ESL_FLAG_BYTE = 0x02


@pytest.fixture
def env(workdir, g):
    """Manual-mode ESLifier environment: <tmp>/Data (source) and <tmp>/out/ESLifier Output."""
    data = workdir / "Data"
    data.mkdir()
    out_root = workdir / "out"
    out_root.mkdir()
    g._settings = {"mod_manager_mode": 0, "game_folder_path": str(data),
                   "output_folder_path": str(out_root), "output_folder_name": "ESLifier Output",
                   "update_header": True, "generate_cell_master": False, "persistent_ids": True}
    g.cwd = str(workdir)
    g.update_from_settings()

    class Env:
        pass

    e = Env()
    e.root, e.data, e.out = workdir, data, workdir / "out" / "ESLifier Output"
    e.g = g
    return e


def make_cfids(env, cell_master=False, original_files=None):
    cf = CFIDs(create_new_cell_plugin(), original_files if original_files is not None else {}, {}, {}, {}, {}, [], None)
    cf.do_generate_cell_master = cell_master
    cf.form_id_map = {}
    return cf


def build_source_plugin(masters=(SKYRIM,), ids=(0x2000, 0x3000, 0x5000), refs=None):
    """KYWD records for each id, plus one REFR whose NAME points at ids[1]."""
    mc = len(masters)
    kywd = b"".join(record(b"KYWD", fid(mc, i)) for i in ids)
    refr_subs = sub(b"NAME", fid(mc, ids[1])) + sub(b"XOWN", fid(0, 0x14))
    refr = record(b"REFR", fid(mc, 0x9000), refr_subs)
    return plugin(masters, grup(b"KYWD", kywd) + grup(b"REFR", refr), version=HEADER_VERSION_170)


def new_ids(data: bytes, master_count=1):
    tree = walk(data)
    return sorted(int.from_bytes(f[2][:3], "little") for f in flatten(tree)
                  if f[2][3] >= master_count and f[1] != b"TES4")


# ---------------------------------------------------------------------------- helpers
class TestParsingHelpers:
    def test_create_data_list_flat(self, env):
        cf = make_cfids(env)
        data = build_source_plugin()
        data_list, grup_struct = cf.create_data_list(data)
        assert b"".join(data_list) == data
        assert [d[:4] for d in data_list] == [b"TES4", b"GRUP", b"KYWD", b"KYWD", b"KYWD", b"GRUP", b"REFR"]
        # records know which GRUPs enclose them
        assert grup_struct[2] == [1]
        assert grup_struct[6] == [5]
        assert grup_struct[0] == []

    def test_create_data_list_nested_groups(self, env):
        cf = make_cfids(env)
        cell = cell_record(fid(1, 0x800), interior=True)
        data = plugin((SKYRIM,), grup(b"CELL", grup(b"\x00\x00\x00\x00", grup(b"\x00\x00\x00\x00", cell, 3), 2)))
        data_list, grup_struct = cf.create_data_list(data)
        cell_index = [d[:4] for d in data_list].index(b"CELL")
        assert grup_struct[cell_index] == [1, 2, 3]

    def test_get_master_count(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin((SKYRIM, "A.esp", "B.esp")))
        assert cf.get_master_count(dl) == (3, True)

    def test_get_master_index_is_case_insensitive(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin((SKYRIM, "Compacted.ESP", "Other.esp")))
        assert cf.get_master_index("C:/mods/compacted.esp", dl) == 1
        assert cf.get_master_index("other.esp", dl) == 2

    def test_get_master_index_missing_master(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin((SKYRIM,)))
        assert cf.get_master_index("nope.esp", dl) is None


class TestCompression:
    def test_decompress_recompress_roundtrip(self, env):
        cf = make_cfids(env)
        subs = sub(b"NAME", fid(1, 0x800)) + sub(b"EDID", b"x" * 200 + b"\x00")
        data = plugin((SKYRIM,), grup(b"REFR", record(b"REFR", fid(1, 0x900), subs, compress=True)))
        data_list, _ = cf.create_data_list(data)
        data_list, sizes = cf.decompress_data(data_list)
        refr = data_list[2]
        assert refr[24:] == subs            # decompressed in place
        assert sizes[2][4] == struct.pack("<I", len(subs))
        data_list, sizes = cf.recompress_data(data_list, sizes)
        assert zlib.decompress(data_list[2][28:]) == subs
        assert struct.unpack("<I", data_list[2][4:8])[0] == len(data_list[2]) - 24

    def test_uncompressed_forms_are_left_alone(self, env):
        cf = make_cfids(env)
        data_list, _ = cf.create_data_list(build_source_plugin())
        before = list(data_list)
        data_list, sizes = cf.decompress_data(data_list)
        assert data_list == before
        assert all(s == [] for s in sizes)

    def test_update_grup_sizes_after_recompress_changes_length(self, env):
        cf = make_cfids(env)
        subs = sub(b"NAME", fid(1, 0x800)) + sub(b"XOWN", b"\x00" * 4000)
        data = plugin((SKYRIM,), grup(b"REFR", record(b"REFR", fid(1, 0x900), subs, compress=True)))
        data_list, grup_struct = cf.create_data_list(data)
        data_list, sizes = cf.decompress_data(data_list)
        # change the content so the compressed length differs from the original
        data_list[2] = data_list[2][:24] + sub(b"NAME", fid(1, 0x801)) + sub(b"XOWN", os.urandom(4000))
        data_list, sizes = cf.recompress_data(data_list, sizes)
        data_list = cf.update_grup_sizes(data_list, grup_struct, sizes)
        walk(b"".join(data_list))   # raises if any GRUP size is wrong


class TestAddCellMaster:
    def test_appends_master_after_existing_masters(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin((SKYRIM, "A.esp")))
        dl, idx = cf.add_cell_master_to_masters(dl)
        assert idx == -1
        assert cf.get_master_count(dl)[0] == 3
        assert cf.get_master_index("ESLifier_Cell_Master.esm", dl) == 2
        assert struct.unpack("<I", dl[0][4:8])[0] == len(dl[0]) - 24

    def test_is_idempotent_and_reports_existing_index(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin((SKYRIM, "A.esp")))
        dl, _ = cf.add_cell_master_to_masters(dl)
        dl, idx = cf.add_cell_master_to_masters(dl)
        assert idx == 2
        assert cf.get_master_count(dl)[0] == 3

    def test_plugin_without_masters(self, env):
        cf = make_cfids(env)
        dl, _ = cf.create_data_list(plugin(()))
        dl, idx = cf.add_cell_master_to_masters(dl)
        assert idx == -1
        assert cf.get_master_count(dl)[0] == 1


# ---------------------------------------------------------------------------- compact_file
class TestCompactFile:
    def compact(self, env, data=None, name="mod.esp", all_dependents_ok=True, cell_master=False, cf=None):
        src = write(env.data / name, data if data is not None else build_source_plugin())
        cf = cf or make_cfids(env, cell_master=cell_master)
        cf.compact_file(src, all_dependents_ok)
        return cf, src, env.out / name

    def test_sets_esl_flag_and_updates_header_version(self, env):
        cf, src, out = self.compact(env)
        data = out.read_bytes()
        assert data[9] == ESL_FLAG_BYTE
        assert data[30:34] == HEADER_VERSION_171

    def test_header_version_untouched_when_update_header_disabled(self, env):
        env.g._settings["update_header"] = False
        env.g.update_from_settings()
        cf, src, out = self.compact(env)
        assert out.read_bytes()[30:34] == HEADER_VERSION_170

    def test_source_file_is_never_modified(self, env):
        original = build_source_plugin()
        cf, src, out = self.compact(env, original)
        assert open(src, "rb").read() == original

    def test_new_ids_start_at_one_with_header_171(self, env):
        cf, src, out = self.compact(env)
        # three KYWDs + one REFR -> 0x001..0x004 (ESLifier now starts at 1, not 0)
        assert new_ids(out.read_bytes()) == [1, 2, 3, 4]

    def test_new_ids_start_at_0x800_without_header_update(self, env):
        env.g._settings["update_header"] = False
        env.g.update_from_settings()
        cf, src, out = self.compact(env)
        assert new_ids(out.read_bytes()) == [0x800, 0x801, 0x802, 0x803]

    def test_new_ids_start_at_0x800_when_dependents_lack_skyrim_master(self, env):
        cf, src, out = self.compact(env, all_dependents_ok=False)
        assert new_ids(out.read_bytes()) == [0x800, 0x801, 0x802, 0x803]

    def test_new_ids_start_at_0x800_when_plugin_has_no_skyrim_master(self, env):
        data = build_source_plugin(masters=("Other.esp",))
        cf, src, out = self.compact(env, data)
        assert new_ids(out.read_bytes(), master_count=1) == [0x800, 0x801, 0x802, 0x803]

    def test_ids_assigned_in_ascending_order_of_old_ids(self, env):
        cf, src, out = self.compact(env)
        by_old = {}
        for line in (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text().split():
            old, new = line.split("|")
            by_old[int.from_bytes(bytes.fromhex(old)[:3], "little")] = int.from_bytes(bytes.fromhex(new)[:3], "little")
        assert by_old == {0x2000: 1, 0x3000: 2, 0x5000: 3, 0x9000: 4}

    def test_form_id_map_file_format(self, env):
        self.compact(env)
        text = (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text()
        assert text.splitlines()[0] == "00200001|01000001"

    def test_references_inside_plugin_follow_the_new_ids(self, env):
        cf, src, out = self.compact(env)
        refr_bytes = get_record(out.read_bytes(), b"REFR")
        name_off = 24 + 6
        assert refr_bytes[name_off:name_off + 4] == fid(1, 2)       # was 0x3000
        assert refr_bytes[name_off + 10:name_off + 14] == fid(0, 0x14)  # master reference untouched

    def test_overrides_of_master_records_are_not_renumbered(self, env):
        override = record(b"KYWD", fid(0, 0x1234))
        body = grup(b"KYWD", override + record(b"KYWD", fid(1, 0x4000)))
        cf, src, out = self.compact(env, plugin((SKYRIM,), body))
        ids = [(f[2][3], int.from_bytes(f[2][:3], "little")) for f in flatten(walk(out.read_bytes())) if f[1] == b"KYWD"]
        assert (0, 0x1234) in ids
        assert (1, 1) in ids

    def test_ids_already_in_target_range_keep_their_slot(self, env):
        # 0x001 is already inside the new range [0x001, 0xFFF]; it keeps its id and is
        # left out of the map, while the other record takes the first free slot (0x002).
        data = plugin((SKYRIM,), grup(b"KYWD", record(b"KYWD", fid(1, 0x001)) + record(b"KYWD", fid(1, 0x4000))))
        cf, src, out = self.compact(env, data)
        assert new_ids(out.read_bytes()) == [1, 2]
        mapping = dict(line.split("|") for line in
                       (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text().split())
        assert fid(1, 0x4000).hex() in mapping
        assert fid(1, 0x001).hex() not in mapping

    def test_compressed_records_are_patched_and_regrouped(self, env):
        subs = sub(b"NAME", fid(1, 0x3000)) + sub(b"EDID", b"abcdefg" * 50 + b"\x00")
        body = (grup(b"KYWD", record(b"KYWD", fid(1, 0x3000)))
                + grup(b"REFR", record(b"REFR", fid(1, 0x9000), subs, compress=True)))
        cf, src, out = self.compact(env, plugin((SKYRIM,), body))
        data = out.read_bytes()
        walk(data)  # GRUP sizes still consistent after recompression
        rec = get_record(data, b"REFR")
        inner = zlib.decompress(rec[28:])
        assert inner[6:10] == fid(1, 1)           # NAME now points at the compacted KYWD

    def test_records_in_grup_counts_unchanged(self, env):
        cf, src, out = self.compact(env)
        before = [f[1] for f in flatten(walk(build_source_plugin()))]
        after = [f[1] for f in flatten(walk(out.read_bytes()))]
        assert before == after

    def test_master_byte_data_recorded(self, env):
        cf, src, out = self.compact(env)
        assert cf.master_byte_data["mod.esp"] == {"master_byte": "01", "updated_master_index": -1}

    def test_original_file_hash_recorded(self, env):
        cf, src, out = self.compact(env)
        assert cf.original_files["mod.esp"][0] == src
        assert len(cf.original_files["mod.esp"][1]) == 64

    def test_compacted_and_patched_registered(self, env):
        cf, src, out = self.compact(env)
        assert cf.compacted_and_patched == {"mod.esp": set()}

    # ---- persistent ids
    def test_persistent_ids_keep_previous_assignments_across_runs(self, env):
        self.compact(env)
        os.remove(env.out / "mod.esp")           # force a fresh copy of the source
        data = build_source_plugin(ids=(0x1500, 0x2000, 0x3000, 0x5000))
        cf, src, out = self.compact(env, data)
        mapping = {}
        for line in (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text().split():
            old, new = line.split("|")
            mapping[int.from_bytes(bytes.fromhex(old)[:3], "little")] = int.from_bytes(bytes.fromhex(new)[:3], "little")
        # the old assignments are unchanged and the new record got the next free slot
        assert mapping[0x2000] == 1 and mapping[0x3000] == 2 and mapping[0x5000] == 3 and mapping[0x9000] == 4
        assert mapping[0x1500] == 5

    def test_without_persistent_ids_ids_are_reassigned(self, env):
        env.g._settings["persistent_ids"] = False
        env.g.update_from_settings()
        self.compact(env)
        os.remove(env.out / "mod.esp")
        data = build_source_plugin(ids=(0x1500, 0x2000, 0x3000, 0x5000))
        cf, src, out = self.compact(env, data)
        mapping = {}
        for line in (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text().split():
            old, new = line.split("|")
            mapping[int.from_bytes(bytes.fromhex(old)[:3], "little")] = int.from_bytes(bytes.fromhex(new)[:3], "little")
        assert mapping[0x1500] == 1 and mapping[0x2000] == 2

    def test_removed_records_keep_their_slot_by_default(self, env):
        self.compact(env)
        os.remove(env.out / "mod.esp")
        data = build_source_plugin(ids=(0x2000, 0x3000))      # 0x5000 removed
        cf, src, out = self.compact(env, data)
        text = (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text()
        assert "00500001|03000001" in text

    def test_free_non_existent_releases_slots_of_removed_records(self, env):
        env.g._settings["free_non_existent"] = True
        env.g.update_from_settings()
        self.compact(env)
        os.remove(env.out / "mod.esp")
        data = build_source_plugin(ids=(0x2000, 0x3000))
        cf, src, out = self.compact(env, data)
        text = (env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt").read_text()
        assert "00500001" not in text

    def test_duplicate_lines_in_existing_map_are_tolerated(self, env):
        self.compact(env)
        mp = env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt"
        lines = mp.read_text().splitlines()
        mp.write_text("\n".join(lines + [lines[0].split("|")[0] + "|deadbeef"]) + "\n")
        os.remove(env.out / "mod.esp")
        cf, src, out = self.compact(env)
        assert dict(l.split("|") for l in mp.read_text().split())[lines[0].split("|")[0]] == lines[0].split("|")[1]


# ---------------------------------------------------------------------------- get_form_id_map
class TestGetFormIdMap:
    def test_builds_all_lookup_forms(self, env):
        mp = env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt"
        # old id 0x00A200 (master byte 01)  ->  new id 0x00000A (master byte 01)
        mp.write_text("00a20001|0a000001\n")
        cf = make_cfids(env)
        cf.get_form_id_map("whatever/Mod.esp")
        m = cf.form_id_map
        assert m[0xA200] == {"hex": "00000A", "int": 0x0A, "hex_no_0": "A",
                             "bytes": bytes.fromhex("0a000001"), "update_name": False}
        assert m[bytes.fromhex("00a20001")] == bytes.fromhex("0a000001")
        assert m["00a200"] == "00000a"
        assert m[b"00a200"] == b"00000A"

    def test_five_byte_target_means_cell_master_rename(self, env):
        mp = env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt"
        mp.write_text("00a20001|0a000001ff\n")
        cf = make_cfids(env)
        cf.get_form_id_map("mod.esp")
        entry = cf.form_id_map[0xA200]
        assert entry["update_name"] is True
        assert entry["bytes"] == bytes.fromhex("0a000001")

    def test_zero_target_hex_is_a_single_zero(self, env):
        mp = env.root / "ESLifier_Data" / "Form_ID_Maps" / "mod.esp_FormIdMap.txt"
        mp.write_text("00200001|00000001\n")
        cf = make_cfids(env)
        cf.get_form_id_map("mod.esp")
        assert cf.form_id_map[0x2000]["hex_no_0"] == "0"


# ---------------------------------------------------------------------------- dependents
class TestPatchDependent:
    def setup_pair(self, env):
        cf = make_cfids(env)
        master_src = write(env.data / "master.esp", build_source_plugin())
        cf.compact_file(master_src, True)
        # dependent: masters Skyrim, master.esp  -> own records use index 2
        refr = record(b"REFR", fid(2, 0x800), sub(b"NAME", fid(1, 0x3000)) + sub(b"XOWN", fid(0, 0x14)))
        dep_data = plugin((SKYRIM, "master.esp"), grup(b"REFR", refr))
        dep_src = write(env.data / "dep.esp", dep_data)
        return cf, master_src, dep_src

    def test_patches_references_to_the_compacted_master(self, env):
        cf, master_src, dep_src = self.setup_pair(env)
        cf.patch_dependent_plugins(master_src, [dep_src], {})
        out = (env.out / "dep.esp").read_bytes()
        refr = get_record(out, b"REFR")
        assert refr[30:34] == fid(1, 2)                     # NAME: 0x3000 -> 0x002
        assert refr[40:44] == fid(0, 0x14)                  # XOWN: master reference untouched
        assert refr[12:16] == fid(2, 0x800)                 # own id untouched
        walk(out)

    def test_updates_header_version(self, env):
        cf, master_src, dep_src = self.setup_pair(env)
        cf.patch_dependent_plugins(master_src, [dep_src], {})
        assert (env.out / "dep.esp").read_bytes()[30:34] == HEADER_VERSION_171

    def test_registers_patched_file(self, env):
        cf, master_src, dep_src = self.setup_pair(env)
        cf.patch_dependent_plugins(master_src, [dep_src], {})
        assert "dep.esp" in cf.compacted_and_patched["master.esp"]

    def test_patches_seq_file_for_dependent(self, env):
        cf, master_src, dep_src = self.setup_pair(env)
        # SEQ files are flat lists of 4-byte form ids: one of the dependent's own quests
        # (master byte 2) and one reference into the compacted master (master byte 1)
        seq = write(env.data / "Seq" / "dep.seq", fid(2, 0x800) + fid(1, 0x3000))
        env.g.mods_with_seq = {"dep.esp": str(seq)}
        cf.patch_dependent_plugins(master_src, [dep_src], {})
        assert (env.out / "Seq" / "dep.seq").read_bytes() == fid(2, 0x800) + fid(1, 2)
        assert os.path.join("Seq", "dep.seq") in cf.compacted_and_patched["master.esp"]

    def test_bad_dependent_is_reported_not_raised(self, env, log):
        cf, master_src, dep_src = self.setup_pair(env)
        bad = write(env.data / "bad.esp", b"TES4" + b"\x10\x00\x00\x00" + b"\x00" * 20)
        cf.patch_dependent_plugins(master_src, [bad], {})
        assert any("Failed to patch dependent" in e for e in log.errors)

    def test_patching_new_dependent_uses_saved_master_data(self, env):
        cf, master_src, dep_src = self.setup_pair(env)
        cf2 = make_cfids(env)
        cf2.master_byte_data = cf.master_byte_data
        cf2.compacted_and_patched = {"master.esp": set()}
        cf2.get_form_id_map(master_src)
        cf2.patch_dependent_plugins(master_src, [dep_src], {})
        assert "dep.esp" in cf2.compacted_and_patched["master.esp"]


# ---------------------------------------------------------------------------- set_flag / persistence
class TestSetFlag:
    def test_sets_only_the_esl_flag(self, env):
        cf = make_cfids(env)
        data = build_source_plugin()
        src = write(env.data / "mod.esp", data)
        cf.set_flag(src)
        out = (env.out / "mod.esp").read_bytes()
        assert out[9] == ESL_FLAG_BYTE
        assert out[:9] == data[:9] and out[10:] == data[10:]


class TestSaveData:
    def test_dump_compacted_and_patched_merges_and_lowercases(self, env):
        cf = make_cfids(env)
        path = str(env.root / "ESLifier_Data" / "c.json")
        cf.dump_compacted_and_patched(path, {"a.esp": {"Meshes/A.nif"}})
        cf.dump_compacted_and_patched(path, {"a.esp": {"Meshes/B.nif"}, "b.esp": set()})
        data = json.loads(open(path).read())
        assert sorted(data["a.esp"]) == ["meshes/a.nif", "meshes/b.nif"]
        assert data["b.esp"] == []

    def test_dump_dictionary_overwrites_keys_but_keeps_others(self, env):
        cf = make_cfids(env)
        path = str(env.root / "ESLifier_Data" / "d.json")
        cf.dump_dictionary(path, {"a": 1, "b": 2})
        cf.dump_dictionary(path, {"b": 3})
        assert json.loads(open(path).read()) == {"a": 1, "b": 3}

    def test_get_from_file_missing_is_empty_dict(self, env):
        assert make_cfids(env).get_from_file("nope.json") == {}


# ---------------------------------------------------------------------------- with cell master
class TestCompactWithCellMaster:
    def build(self):
        cell = cell_record(fid(1, 0x4000), interior=True)
        # CELL top group -> block (type 2) -> sub-block (type 3) -> cell
        cells = grup(b"CELL", grup(struct.pack("<i", 0), grup(struct.pack("<i", 0), cell, 3), 2))
        kywd = grup(b"KYWD", record(b"KYWD", fid(1, 0x2000)))
        return plugin((SKYRIM,), kywd + cells)

    def test_cell_master_is_added_and_interior_cell_is_moved_to_it(self, env):
        env.g._settings["generate_cell_master"] = True
        env.g.update_from_settings()
        cf = make_cfids(env, cell_master=True)
        cf.create_cell_master_class.generate(str(env.out) if env.out.exists() else str(env.root), True)
        src = write(env.data / "cells.esp", self.build())
        cf.compact_file(src, True)
        out = (env.out / "cells.esp").read_bytes()
        dl, _ = cf.create_data_list(out)
        assert cf.get_master_count(dl)[0] == 2
        assert cf.get_master_index("ESLifier_Cell_Master.esm", dl) == 1
        walk(out)
        mapping = dict(l.split("|") for l in
                       (env.root / "ESLifier_Data" / "Form_ID_Maps" / "cells.esp_FormIdMap.txt").read_text().split())
        cell_target = bytes.fromhex(mapping[fid(1, 0x4000).hex()])
        assert len(cell_target) == 5 and cell_target[4] == 0xFF      # marker: lives in the cell master
        assert cell_target[3] == 1                                   # master index of the plugin
