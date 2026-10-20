"""create_cell_master: builds ESLifier_Cell_Master.esm, which hosts cells moved out of compacted plugins."""
import json
import os
import struct

import pytest

from create_cell_master import create_new_cell_plugin
from plugin_builder import cell_record, fid, flatten, grup, plugin, record, sub, walk
from compact_form_ids import CFIDs

SKYRIM = "Skyrim.esm"


def interior_plugin(cell_ids=(0x4000,)):
    cells = b""
    for cid in cell_ids:
        cell = cell_record(fid(1, cid), interior=True)
        cells += grup(struct.pack("<i", 0), grup(struct.pack("<i", 0), cell, 3), 2)
    return plugin((SKYRIM,), grup(b"CELL", cells))


def exterior_plugin():
    wrld = record(b"WRLD", fid(1, 0x800), sub(b"EDID", b"MyWorld\x00"))
    xclc = sub(b"XCLC", struct.pack("<ii", 3, 4) + b"\x00" * 4)
    persistent = record(b"CELL", fid(1, 0x801), sub(b"DATA", b"\x00\x00") + xclc)
    exterior = record(b"CELL", fid(1, 0x802), sub(b"DATA", b"\x00\x00") + xclc)
    block = grup(struct.pack("<hh", 0, 0), grup(struct.pack("<hh", 0, 0), exterior, 5), 4)
    children = grup(fid(1, 0x800), grup(fid(1, 0x800), persistent, 8) + block, 1)
    return plugin((SKYRIM,), grup(b"WRLD", wrld + children))


@pytest.fixture
def cm(workdir):
    out = workdir / "out"
    out.mkdir()
    c = create_new_cell_plugin()
    c.generate(str(out), True)
    c.out_dir = out
    return c


def parse(c, data):
    helper = CFIDs(c, {}, {}, {}, {}, {}, [], None)
    return helper.create_data_list(data)


class TestGenerate:
    def test_starts_with_empty_state(self, cm):
        assert cm.counter == 1
        assert cm.new_interior_cell_dict == {} and cm.wrld_dict == {}

    def test_header_version_can_be_left_alone(self, workdir):
        c = create_new_cell_plugin()
        c.generate(str(workdir), update_header=False)
        assert c.new_data_list[0][30:34] == bytes([0x9A, 0x99, 0xD9, 0x3F])   # 1.70

    def test_header_version_171(self, cm):
        assert cm.new_data_list[0][30:34] == bytes([0x48, 0xE1, 0xDA, 0x3F])


class TestAddCells:
    def test_interior_cell_gets_new_id_in_cell_master(self, cm):
        dl, gs = parse(cm, interior_plugin())
        mapping = cm.add_cells(dl, gs, 1, "mod.esp")
        assert mapping == [[fid(1, 0x4000), (2049).to_bytes(3, "little")]]
        assert cm.counter == 2
        assert len(cm.new_interior_cell_dict) == 1
        (block,) = cm.new_interior_cell_dict.values()
        assert block["source_plugin"] == "mod.esp"
        (sub_block,) = block["sub_blocks"].values()
        assert len(sub_block["cells"]) == 1

    def test_cell_overrides_of_masters_are_ignored(self, cm):
        cell = cell_record(fid(0, 0x4000), interior=True)
        data = plugin((SKYRIM,), grup(b"CELL", grup(struct.pack("<i", 0), grup(struct.pack("<i", 0), cell, 3), 2)))
        dl, gs = parse(cm, data)
        assert cm.add_cells(dl, gs, 1, "mod.esp") == []

    def test_ids_increment_across_cells_and_plugins(self, cm):
        dl, gs = parse(cm, interior_plugin((0x4000, 0x4001)))
        first = cm.add_cells(dl, gs, 1, "a.esp")
        dl, gs = parse(cm, interior_plugin((0x5000,)))
        second = cm.add_cells(dl, gs, 1, "b.esp")
        ids = [int.from_bytes(m[1], "little") for m in first + second]
        assert ids == [2049, 2050, 2051]

    def test_exterior_cells_and_worldspace(self, cm):
        dl, gs = parse(cm, exterior_plugin())
        mapping = cm.add_cells(dl, gs, 1, "world.esp")
        # worldspace, persistent cell and one exterior cell each get a new id
        assert [m[0] for m in mapping] == [fid(1, 0x800), fid(1, 0x801), fid(1, 0x802)]
        assert [int.from_bytes(m[1], "little") for m in mapping] == [2049, 2050, 2051]
        (wrld,) = cm.wrld_dict.values()
        assert wrld["persistent_cell_data"] != b""
        assert wrld["source_plugin"] == "world.esp"

    def test_exterior_cell_without_worldspace_is_ignored(self, cm):
        persistent = record(b"CELL", fid(1, 0x801), sub(b"DATA", b"\x00\x00"))
        data = plugin((SKYRIM,), grup(b"CELL", persistent))
        dl, gs = parse(cm, data)
        assert cm.add_cells(dl, gs, 1, "x.esp") == []


class TestFinalize:
    def test_interior_cell_master_is_a_valid_esm(self, cm):
        dl, gs = parse(cm, interior_plugin((0x4000, 0x4001)))
        cm.add_cells(dl, gs, 1, "mod.esp")
        cm.finalize_plugin()
        data = open(cm.output_file, "rb").read()
        tree = walk(data)
        assert data[:4] == b"TES4" and data[8] & 0x01            # ESM flag
        cells = [f for f in flatten(tree) if f[1] == b"CELL"]
        assert [int.from_bytes(c[2][:3], "little") for c in cells] == [2049, 2050]
        # no WRLD group when there are no worlds
        assert not any(n[0] == "GRUP" and n[1] == b"WRLD" for n in tree)

    def test_header_record_count_matches_contents(self, cm):
        dl, gs = parse(cm, interior_plugin((0x4000,)))
        cm.add_cells(dl, gs, 1, "mod.esp")
        cm.finalize_plugin()
        data = open(cm.output_file, "rb").read()
        count = struct.unpack("<I", data[34:38])[0]
        grups = data.count(b"GRUP")      # top + block + sub-block (labels can't collide here)
        assert count == 3 + 1 and grups == 3

    def test_exterior_cell_master_is_valid(self, cm):
        dl, gs = parse(cm, exterior_plugin())
        cm.add_cells(dl, gs, 1, "world.esp")
        cm.finalize_plugin()
        data = open(cm.output_file, "rb").read()
        tree = walk(data)
        sigs = [f[1] for f in flatten(tree)]
        assert sigs.count(b"WRLD") == 1 and sigs.count(b"CELL") == 2

    def test_state_is_persisted_and_reloaded(self, cm):
        dl, gs = parse(cm, interior_plugin((0x4000,)))
        cm.add_cells(dl, gs, 1, "mod.esp")
        cm.finalize_plugin()
        saved = json.load(open("ESLifier_Data/cell_master_info.json"))
        assert saved["counter"] == 2
        reloaded = create_new_cell_plugin()
        reloaded.generate(str(cm.out_dir), True)
        assert reloaded.counter == 2
        assert set(reloaded.new_interior_cell_dict) == set(cm.new_interior_cell_dict)

    def test_second_plugin_extends_existing_cell_master(self, cm):
        dl, gs = parse(cm, interior_plugin((0x4000,)))
        cm.add_cells(dl, gs, 1, "a.esp")
        cm.finalize_plugin()
        again = create_new_cell_plugin()
        again.generate(str(cm.out_dir), True)
        dl, gs = parse(again, interior_plugin((0x4000,)))
        mapping = again.add_cells(dl, gs, 1, "b.esp")
        assert int.from_bytes(mapping[0][1], "little") == 2050
        again.finalize_plugin()
        data = open(again.output_file, "rb").read()
        cells = [f for f in flatten(walk(data)) if f[1] == b"CELL"]
        assert len(cells) == 2
