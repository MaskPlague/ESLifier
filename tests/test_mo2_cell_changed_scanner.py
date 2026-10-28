"""MO2 plugin's cell changed scanner and the notifier flags built from it."""
import importlib
import struct

import pytest

import test_mo2_qualification_checker as base        # builds the "mo2_plugin" package shell
from plugin_builder import cell_record, fid, grup, plugin, record, simple_records, sub, write
from scanners.cell_changed_scanner import cell_scanner as exe_scanner

mo2 = base.mo2
cell_scanner = importlib.import_module("mo2_plugin.ESLifier_cell_changed_scanner").cell_scanner
notifier_module = importlib.import_module("mo2_plugin.ESLifier_notifier")
SKYRIM, FO4, V1_0 = base.SKYRIM, base.FO4, base.V1_0


def cell_body(formid, interior=False):
    return grup(b"CELL", cell_record(formid, interior))


def fo4_cell(formid, subs=b"", compress=False):
    return grup(b"CELL", record(b"CELL", formid, sub(b"EDID", b"c\x00") + subs, compress=compress))


# ------------------------------------------------------------ is_dependent_modifying
class TestSse:
    def test_override_of_a_new_cell_is_detected(self, tmp_path):
        mod = write(tmp_path / "base.esm", plugin((SKYRIM,), cell_body(fid(1, 0x800)), esm=True))
        dep = write(tmp_path / "dep.esp", plugin((SKYRIM, "base.esm"), cell_body(fid(1, 0x800))))
        assert cell_scanner.is_dependent_modifying(mod, dep, {fid(1, 0x800)[:3].hex()}, "SSE") is True

    def test_matches_exe_scanner(self, tmp_path):
        mod = write(tmp_path / "base.esm", plugin((SKYRIM,), cell_body(fid(1, 0x800)), esm=True))
        ids = [fid(1, 0x800)[:3].hex()]
        deps = {
            "changes": plugin((SKYRIM, "base.esm"), cell_body(fid(1, 0x800))),
            "other_cell": plugin((SKYRIM, "base.esm"), cell_body(fid(1, 0x900))),
            "other_master": plugin((SKYRIM, "base.esm", "x.esp"), cell_body(fid(2, 0x800))),
            "no_cells": plugin((SKYRIM, "base.esm"), simple_records(2, [0x800])),
            "not_a_dependent": plugin((SKYRIM,), cell_body(fid(1, 0x800))),
        }
        for name, data in deps.items():
            dep = write(tmp_path / f"{name}.esp", data)
            assert (cell_scanner.is_dependent_modifying(mod, dep, set(ids), "SSE")
                    == exe_scanner.is_dependent_modifying(mod, dep, ids)), name

    def test_unreadable_dependent_is_not_modifying(self, tmp_path):
        assert cell_scanner.is_dependent_modifying("base.esm", str(tmp_path / "gone.esp"), {"x"}, "SSE") is False


class TestFo4:
    def modifying(self, tmp_path, dep_body):
        mod = write(tmp_path / "base.esp", plugin((FO4,), fo4_cell(fid(1, 0x800)), version=V1_0))
        dep = write(tmp_path / "dep.esp", plugin((FO4, "base.esp"), dep_body, version=V1_0))
        return cell_scanner.is_dependent_modifying(mod, dep, {fid(1, 0x800)[:3].hex()}, "FO4")

    @pytest.mark.parametrize("sig", [b"XCRI", b"XPRI"])
    def test_previs_data_on_the_new_cell_counts(self, tmp_path, sig):
        assert self.modifying(tmp_path, fo4_cell(fid(1, 0x800), sub(sig, b"\x00" * 4))) is True

    def test_compressed_cell(self, tmp_path):
        assert self.modifying(tmp_path, fo4_cell(fid(1, 0x800), sub(b"XPRI", b"\x00" * 4), compress=True)) is True

    def test_plain_override_does_not_count(self, tmp_path):
        assert self.modifying(tmp_path, fo4_cell(fid(1, 0x800), sub(b"DATA", b"\x01\x00"))) is False


# ------------------------------------------------------------ notifier flags
def run_scan(tmp_path, game_mode, plugins, scan_esms=True):
    notifier = notifier_module.check_files()
    return notifier.scan_files(scan_esms, str(tmp_path), True, False, False, False, plugins, None, game_mode)


def test_sse_changed_new_cell_of_an_esm_is_flagged(tmp_path):
    esm = write(tmp_path / "base.esm", plugin((SKYRIM,), cell_body(fid(1, 0x800)), esm=True))
    esm_ok = write(tmp_path / "quiet.esm", plugin((SKYRIM,), cell_body(fid(1, 0x800)), esm=True))
    dep = write(tmp_path / "dep.esp", plugin((SKYRIM, "base.esm"), cell_body(fid(1, 0x800))))
    changed, needs_flag, needs_compacting, *_ = run_scan(tmp_path, "SSE", [esm, esm_ok, dep])
    assert "cell_changed" in needs_flag["base.esm"] and "new_cell" in needs_flag["base.esm"]
    assert "cell_changed" not in needs_flag["quiet.esm"]
    assert changed is True


def test_sse_esp_new_cells_are_never_scanned_for_changes(tmp_path):
    esp = write(tmp_path / "base.esp", plugin((SKYRIM,), cell_body(fid(1, 0x800))))
    dep = write(tmp_path / "dep.esp", plugin((SKYRIM, "base.esp"), cell_body(fid(1, 0x800))))
    _, needs_flag, *_ = run_scan(tmp_path, "SSE", [esp, dep])
    assert "cell_changed" not in needs_flag["base.esp"]      # the exe only records CELL ids for ESMs in SSE


def test_fo4_own_previs_data_is_flagged(tmp_path):
    base = write(tmp_path / "own.esp", plugin((FO4,), fo4_cell(fid(1, 0x800), sub(b"XCRI", b"\x00" * 4)), version=V1_0))
    _, needs_flag, *_ = run_scan(tmp_path, "FO4", [base])
    assert needs_flag["own.esp"] == ["new_cell", "has_previs_precombines"]


def test_fo4_previs_use_by_a_dependent_is_flagged(tmp_path):
    base = write(tmp_path / "base.esp", plugin((FO4,), fo4_cell(fid(1, 0x800)), version=V1_0))
    dep = write(tmp_path / "dep.esp", plugin((FO4, "base.esp"), fo4_cell(fid(1, 0x800), sub(b"XPRI", b"\x00" * 4)),
                                             version=V1_0))
    _, needs_flag, *_ = run_scan(tmp_path, "FO4", [base, dep])
    assert needs_flag["base.esp"] == ["new_cell", "cell_changed"]
    assert needs_flag["dep.esp"] == []                       # it only overrides the cell, nothing new


def test_maxed_masters_flag_for_plugins_with_new_cells(tmp_path):
    esm = write(tmp_path / "base.esm", plugin((SKYRIM,), cell_body(fid(1, 0x800)), esm=True))
    dep = write(tmp_path / "dep.esp", plugin([SKYRIM, "base.esm"] + [f"m{i}.esp" for i in range(252)],
                                             simple_records(254, [0x800])))
    _, needs_flag, *_ = run_scan(tmp_path, "SSE", [esm, dep])
    assert "maxed_masters" in needs_flag["base.esm"]
