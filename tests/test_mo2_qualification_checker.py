"""MO2 plugin's light qualification checker: must agree with the exe's plugin_qualification_checker."""
import importlib
import sys
import types
import os
import struct
from pathlib import Path

import pytest

from plugin_builder import cell_record, fid, grup, plugin, record, simple_records, sub, write
from scanners.plugin_qualification_checker import qualification_checker as exe_qc

_PKG = (Path(__file__).resolve().parents[1] / "ESLifier MO2 Integration Plugin src" / "ESLifier MO2 Integration")
# The plugin's __init__ imports mobase, so build the package shell by hand; its modules use relative imports.
_pkg = types.ModuleType("mo2_plugin")
_pkg.__path__ = [str(_PKG)]
sys.modules["mo2_plugin"] = _pkg
mo2 = importlib.import_module("mo2_plugin.ESLifier_qualification_checker").qualification_checker

SKYRIM, FO4 = "Skyrim.esm", "Fallout4.esm"
V1_0, V0_95 = struct.pack("<f", 1.0), struct.pack("<f", 0.95)


def make(tmp_path, name, masters=(SKYRIM,), body=b"", **kw):
    return write(tmp_path / name, plugin(masters, body, **kw))


@pytest.fixture
def sse(tmp_path):
    mo2.configure("SSE", [])
    exe_qc.max_record_id = 4096
    exe_qc.dependent_dict, exe_qc.missing_game_esm_as_master, exe_qc.maxed_masters = {"p.esp": []}, {}, []   # exe indexes dependent_dict directly
    return tmp_path


@pytest.fixture
def fo4(tmp_path):
    mo2.configure("FO4", [])
    return tmp_path


def cell_body(count_cells, interior):
    return grup(b"CELL", b"".join(cell_record(fid(1, 0x800 + i), interior) for i in range(count_cells)))


def fo4_cell(formid, subs=b"", compress=False):
    return record(b"CELL", formid, sub(b"EDID", b"c\x00") + subs, compress=compress)


# ------------------------------------------------------------ parity with the exe checker (SSE)
CASES = {
    "small": dict(body=simple_records(1, range(0x800, 0x810))),
    "needs_compacting": dict(body=simple_records(1, [0x800, 0x2000])),
    "interior_cell": dict(body=cell_body(2, True)),
    "exterior_cell": dict(body=cell_body(2, False)),
    "wrld_wthr": dict(body=simple_records(1, [0x800], b"WRLD") + simple_records(1, [0x801], b"WTHR")),
    "compressed_cell": dict(body=grup(b"CELL", cell_record(fid(1, 0x800), True, compress=True))),
    "no_masters": dict(masters=(), body=simple_records(0, range(0x800, 0x800 + 2049))),
    "no_skyrim_master": dict(masters=("Other.esp",), body=simple_records(1, range(0x800, 0x800 + 2049))),
    "2049": dict(body=simple_records(1, range(0x800, 0x800 + 2049))),
    "4097": dict(body=simple_records(1, range(0x800, 0x800 + 4097))),
    "4096": dict(body=simple_records(1, range(0x800, 0x800 + 4096))),
    "esm_flag": dict(body=simple_records(1, [0x800]), esm=True),
}


@pytest.mark.parametrize("update_header", [True, False])
@pytest.mark.parametrize("case", CASES)
def test_matches_exe_checker_for_sse(sse, case, update_header):
    f = make(sse, "p.esp", **CASES[case])
    is_esm = CASES[case].get("esm", False)
    expected = exe_qc.file_reader(f, update_header, is_esm)
    got = mo2.file_reader(f, update_header, is_esm)
    assert got[0] == expected[0]
    if expected[0]:
        assert got == expected
    else:
        assert expected[1].startswith(got[1])        # the exe adds the limit explanation to the same message


def test_dependent_without_game_master_lowers_the_limit_like_the_exe(sse):
    f = make(sse, "base.esp", body=simple_records(1, range(0x800, 0x800 + 2049)))
    exe_qc.dependent_dict = {"base.esp": ["child.esp"]}
    exe_qc.missing_game_esm_as_master = {"child.esp": "base.esp"}
    mo2.dependent_dict = exe_qc.dependent_dict
    mo2.missing_game_esm_as_master = exe_qc.missing_game_esm_as_master
    assert exe_qc.file_reader(f, True, False)[0] is False
    assert mo2.file_reader(f, True, False)[0] is False
    assert mo2.file_reader(f, False, False)[0] is False       # 2048 limit without header update anyway


def test_dependency_data_is_built_from_the_plugin_headers(tmp_path):
    base = make(tmp_path, "Base.esp", body=simple_records(1, [0x800]))
    child = make(tmp_path, "child.esp", ("Base.esp",), simple_records(1, [0x800]))       # first master is not Skyrim.esm
    grandchild = make(tmp_path, "grand.esp", (SKYRIM, "child.esp"), simple_records(2, [0x800]))
    empty = make(tmp_path, "empty.esp", ("Other.esp",))                                  # no records: not reported
    many = make(tmp_path, "many.esp", [f"m{i}.esp" for i in range(254)])
    mo2.configure("SSE", [base, child, grandchild, empty, many])
    assert mo2.dependent_dict["base.esp"] == {child}
    assert mo2.dependent_dict["child.esp"] == {grandchild}
    assert mo2.dependent_dict["skyrim.esm"] == {base, grandchild}
    assert mo2.dependent_dict["grand.esp"] == set()
    assert mo2.missing_game_esm_as_master == {child: "Base.esp"}
    assert mo2.maxed_masters == {many}


def test_maxed_masters_ignores_plugins_that_already_depend_on_the_cell_master(tmp_path):
    names = [f"m{i}.esp" for i in range(253)] + ["ESLifier_Cell_Master.esm"]
    p = make(tmp_path, "many.esp", names)
    mo2.configure("SSE", [p])
    assert mo2.maxed_masters == set()


def test_game_esm_name_follows_the_game_mode(tmp_path):
    fo4_plugin = make(tmp_path, "a.esp", (FO4,), simple_records(1, [0x800]))
    mo2.configure("FO4", [fo4_plugin])
    assert mo2.missing_game_esm_as_master == {}
    mo2.configure("SSE", [fo4_plugin])
    assert mo2.missing_game_esm_as_master == {fo4_plugin: FO4}


def test_dependent_without_game_master_lowers_the_limit_using_self_built_data(tmp_path):
    base = make(tmp_path, "base.esp", body=simple_records(1, range(0x800, 0x800 + 2049)))
    child = make(tmp_path, "child.esp", ("base.esp",), simple_records(1, [0x800]))
    mo2.configure("SSE", [base, child])
    assert mo2.file_reader(base, True, False)[0] is False
    mo2.configure("SSE", [base])                                   # without the dependent the plugin qualifies
    assert mo2.file_reader(base, True, False)[0] is True


def test_unreadable_plugins_are_ignored_when_building_dependency_data(tmp_path):
    mo2.configure("SSE", [str(tmp_path / "gone.esp")])
    assert mo2.dependent_dict == {"gone.esp": set()} and mo2.missing_game_esm_as_master == {}


def test_invalid_game_mode_is_rejected():
    with pytest.raises(ValueError):
        mo2.configure("TES5", [])


# ------------------------------------------------------------ qualification_check wrapper
def test_already_esl_and_unreadable_files_are_skipped(sse):
    assert mo2.qualification_check(None, make(sse, "a.esp", esl=True), True, False)[0] is False
    assert mo2.qualification_check(None, str(sse / "missing.esp"), True, False)[0] is False


def test_esms_are_only_scanned_when_enabled(sse):
    f = make(sse, "a.esm", body=simple_records(1, [0x800]))
    assert mo2.qualification_check(None, f, True, False)[0] is False
    assert mo2.qualification_check(None, f, True, True)[0] is True


def test_non_plugin_and_unreadable_report_a_reason(sse):
    fake = write(sse / "fake.esp", b"NOPE" + b"\x00" * 40)
    assert mo2.file_reader(fake, True, False) == (False, "not plugin")
    assert mo2.file_reader(str(sse / "gone.esp"), True, False) == (False, "read fail")


# ------------------------------------------------------------ Fallout 4
class TestFallout4:
    def read(self, path, update_header=True):
        return mo2.file_reader(path, update_header, False)

    def test_result_shape(self, fo4):
        f = make(fo4, "a.esp", (FO4,), simple_records(1, [0x800]), version=V1_0)
        # allowed, need_compacting, new_cell, has_previs_precombines
        assert self.read(f) == (True, False, False, False)

    def test_master_detection_uses_fallout4_esm(self, fo4):
        data = mo2.create_data_list(plugin((FO4, "x.esp")))
        assert mo2.get_master_count(data, False, True) == (2, True)
        data = mo2.create_data_list(plugin((SKYRIM,)))
        assert mo2.get_master_count(data, False, True) == (1, False)

    @pytest.mark.parametrize("version,update_header,limit", [
        (V1_0, True, 4096), (V0_95, True, 4096),
        (V1_0, False, 2048), (V0_95, False, 2048),
        (struct.pack("<f", 0.8), True, 2048)])
    def test_limit_depends_on_header_version_and_setting(self, fo4, version, update_header, limit):
        ok = make(fo4, "ok.esp", (FO4,), simple_records(1, range(0x800, 0x800 + limit)), version=version)
        over = make(fo4, "over.esp", (FO4,), simple_records(1, range(0x800, 0x800 + limit + 1)), version=version)
        assert self.read(ok, update_header)[0] is True
        assert self.read(over, update_header)[0] is False

    def test_plugin_without_fallout4_esm_is_limited_to_2048(self, fo4):
        f = make(fo4, "a.esp", ("Other.esp",), simple_records(1, range(0x800, 0x800 + 2049)), version=V1_0)
        assert self.read(f)[0] is False

    def test_previs_and_precombine_records_are_detected(self, fo4):
        for sig in (b"XCRI", b"XPRI"):
            body = grup(b"CELL", fo4_cell(fid(1, 0x800), sub(sig, b"\x00" * 4)))
            f = make(fo4, f"{sig.decode()}.esp", (FO4,), body, version=V1_0)
            assert self.read(f) == (True, False, True, True)

    def test_compressed_cell_with_previs_data(self, fo4):
        body = grup(b"CELL", fo4_cell(fid(1, 0x800), sub(b"XPRI", b"\x00" * 4), compress=True))
        f = make(fo4, "c.esp", (FO4,), body, version=V1_0)
        assert self.read(f) == (True, False, True, True)

    def test_cell_without_previs_data(self, fo4):
        body = grup(b"CELL", fo4_cell(fid(1, 0x800), sub(b"DATA", b"\x01\x00")))
        f = make(fo4, "c.esp", (FO4,), body, version=V1_0)
        assert self.read(f) == (True, False, True, False)      # DATA's interior flag is a Skyrim-only concern

    def test_wrld_and_wthr_are_not_reported(self, fo4):
        body = simple_records(1, [0x800], b"WRLD") + simple_records(1, [0x801], b"WTHR")
        f = make(fo4, "w.esp", (FO4,), body, version=V1_0)
        assert self.read(f) == (True, False, False, False)

    def test_xxxx_field_in_a_cell_is_skipped_correctly(self, fo4):
        big = b"\x00" * 70000
        subs = sub(b"XXXX", struct.pack("<I", len(big))) + b"DATA" + struct.pack("<H", 0) + big
        subs += sub(b"XPRI", b"\x00" * 4)
        body = grup(b"CELL", record(b"CELL", fid(1, 0x800), subs))
        f = make(fo4, "x.esp", (FO4,), body, version=V1_0)
        assert self.read(f) == (True, False, True, True)

    def test_need_compacting(self, fo4):
        f = make(fo4, "n.esp", (FO4,), simple_records(1, [0x800, 0x3000]), version=V1_0)
        assert self.read(f) == (True, True, False, False)


def test_dependency_data_matches_the_exe_dependency_getter(tmp_path):
    from data_holder import _global
    from scanners.dependency_getter import dependecy_getter as dg
    plugins = [
        make(tmp_path, "Base.esp", body=simple_records(1, [0x800])),
        make(tmp_path, "child.esp", ("Base.esp",), simple_records(1, [0x800])),
        make(tmp_path, "grand.esp", (SKYRIM, "child.esp"), simple_records(2, [0x800])),
        make(tmp_path, "empty.esp", ("Other.esp",)),
        make(tmp_path, "many.esp", [f"m{i}.esp" for i in range(254)]),
    ]
    old = list(_global.plugins)
    _global.plugins[:] = plugins
    try:
        dg.dependency_dictionary, dg.missing_game_esm_as_master, dg.maxed_masters = {}, {}, []
        dg.create_dependency_dictionary()
    finally:
        _global.plugins[:] = old
    mo2.configure("SSE", plugins)
    assert mo2.dependent_dict == dg.dependency_dictionary
    assert mo2.missing_game_esm_as_master == dg.missing_game_esm_as_master
    assert mo2.maxed_masters == set(dg.maxed_masters)
