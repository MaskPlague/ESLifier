"""dependency_getter: builds the master -> dependents map used everywhere else."""
import json
import os

from scanners.dependency_getter import dependecy_getter as dg
from plugin_builder import plugin, simple_records, write

SKYRIM = "Skyrim.esm"


def test_get_masters_lists_masters_in_order(tmp_path):
    f = write(tmp_path / "a.esp", plugin((SKYRIM, "Update.esm", "Other.esp")))
    masters, has_records = dg.get_masters(f)
    assert masters == [SKYRIM, "Update.esm", "Other.esp"]
    assert has_records is False


def test_get_masters_reports_when_plugin_has_records(tmp_path):
    f = write(tmp_path / "a.esp", plugin((SKYRIM,), simple_records(1, [0x800])))
    assert dg.get_masters(f) == ([SKYRIM], True)


def test_get_masters_no_masters(tmp_path):
    f = write(tmp_path / "a.esp", plugin(()))
    assert dg.get_masters(f) == ([], False)


def test_get_masters_unreadable_file_returns_empty_and_logs(tmp_path, log):
    assert dg.get_masters(str(tmp_path / "missing.esp")) == ([], False)
    assert log.errors


def test_dump_and_get_from_file_roundtrip_converts_sets(tmp_path):
    out = str(tmp_path / "d.json")
    dg.dump_to_file(out, {"a": {"x"}, "b": ["y"]})
    assert json.loads(open(out).read()) == {"a": ["x"], "b": ["y"]}
    assert dg.get_from_file(out) == {"a": ["x"], "b": ["y"]}


def test_dump_list(tmp_path):
    out = str(tmp_path / "l.json")
    dg.dump_to_file(out, ["a", "b"])
    assert dg.get_from_file(out) == ["a", "b"]


def test_get_from_file_missing_is_empty_list(tmp_path):
    assert dg.get_from_file(str(tmp_path / "nope.json")) == []


class TestScan:
    def build(self, workdir, g):
        base = write(workdir / "base.esp", plugin((SKYRIM,), simple_records(1, [0x800])))
        child = write(workdir / "child.esp", plugin((SKYRIM, "base.esp"), simple_records(2, [0x800])))
        grandchild = write(workdir / "grand.esp", plugin(("Child.esp",), simple_records(1, [0x800])))
        g.plugins = [base, child, grandchild]
        return base, child, grandchild

    def test_dependency_dictionary(self, workdir, g):
        base, child, grandchild = self.build(workdir, g)
        result = dg.scan()
        assert result["base.esp"] == {child}
        assert result["child.esp"] == {grandchild}
        assert result["grand.esp"] == set()
        assert result["skyrim.esm"] == {base, child}

    def test_scan_writes_json_files(self, workdir, g):
        base, child, grandchild = self.build(workdir, g)
        dg.scan()
        data = workdir / "ESLifier_Data"
        deps = json.loads((data / "dependency_dictionary.json").read_text())
        assert sorted(deps["base.esp"]) == [child]
        assert json.loads((data / "maxed_masters.json").read_text()) == []

    def test_plugin_whose_first_master_is_not_skyrim_is_recorded(self, workdir, g):
        base, child, grandchild = self.build(workdir, g)
        dg.scan()
        missing = json.loads((workdir / "ESLifier_Data" / "missing_game_as_master.json").read_text())
        # grandchild's first master is Child.esp and it has records
        assert missing == {grandchild: "Child.esp"}

    def test_plugin_without_records_is_not_counted_as_missing_skyrim(self, workdir, g):
        empty = write(workdir / "empty.esp", plugin(("Other.esp",)))
        g.plugins = [empty]
        dg.scan()
        missing = json.loads((workdir / "ESLifier_Data" / "missing_game_as_master.json").read_text())
        assert missing == {}

    def test_maxed_masters_detected(self, workdir, g):
        masters = [SKYRIM] + [f"m{i}.esp" for i in range(253)]
        maxed = write(workdir / "maxed.esp", plugin(masters, simple_records(254, [0x800])))
        not_maxed = write(workdir / "ok.esp", plugin(masters[:253], simple_records(253, [0x800])))
        g.plugins = [maxed, not_maxed]
        dg.scan()
        assert dg.maxed_masters == [maxed]

    def test_plugin_that_already_has_cell_master_is_not_maxed(self, workdir, g):
        masters = [SKYRIM] + [f"m{i}.esp" for i in range(252)] + ["ESLifier_Cell_Master.esm"]
        p = write(workdir / "cm.esp", plugin(masters, simple_records(254, [0x800])))
        g.plugins = [p]
        dg.scan()
        assert dg.maxed_masters == []
