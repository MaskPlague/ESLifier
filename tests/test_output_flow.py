"""main.flow_control and main.utils: the flow state and the disk space estimate behind the compact / ESLify confirmation dialogs."""
import os

import pytest

from main.flow import Flow
from main.utils import estimate_output_size, size_in_units


def make(tmp_path, files):
    paths = {}
    for name, size in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)
        paths[name] = str(p)
    return paths


class TestFlow:
    @pytest.mark.parametrize("flow, redoing, patch_new, only_remove", [
        (Flow.NONE, False, False, False), (Flow.REBUILD, True, False, False),
        (Flow.PATCH_NEW, True, True, False), (Flow.PATCH_NEW_REMOVE_ONLY, True, True, True)])
    def test_properties(self, flow, redoing, patch_new, only_remove):
        assert (flow.redoing, flow.patch_new, flow.only_remove) == (redoing, patch_new, only_remove)


class TestEstimate:
    def test_counts_each_mod_and_everything_that_depends_on_it(self, tmp_path):
        f = make(tmp_path, {"a.esp": 10, "dep.esp": 20, "master.bin": 30, "arc.bsa": 40})
        deps = {"a.esp": [f["dep.esp"]]}
        masters = {"a.esp": [f["master.bin"]]}
        archives = {"a.esp": [f["arc.bsa"]]}
        assert estimate_output_size([f["a.esp"]], deps, masters, archives) == 100
        assert estimate_output_size([f["a.esp"]], deps, masters) == 60            # archives are optional

    def test_a_file_shared_by_two_mods_counts_once(self, tmp_path):
        f = make(tmp_path, {"a.esp": 1, "b.esp": 1, "shared.esp": 100})
        deps = {"a.esp": [f["shared.esp"]], "b.esp": [f["shared.esp"]]}
        assert estimate_output_size([f["a.esp"], f["b.esp"]], deps, {}) == 102

    def test_mods_listed_twice_count_once(self, tmp_path):
        f = make(tmp_path, {"a.esp": 5})
        assert estimate_output_size([f["a.esp"], f["a.esp"]], {}, {}) == 5

    def test_missing_files_are_ignored(self, tmp_path):
        f = make(tmp_path, {"a.esp": 5})
        assert estimate_output_size([f["a.esp"]], {"a.esp": [str(tmp_path / "gone.esp")]}, {}) == 5

    def test_has_others_limits_who_counts_their_dependents(self, tmp_path):
        f = make(tmp_path, {"a.esp": 1, "b.esp": 2, "dep_a.esp": 10, "dep_b.esp": 20})
        deps = {"a.esp": [f["dep_a.esp"]], "b.esp": [f["dep_b.esp"]]}
        assert estimate_output_size([f["a.esp"], f["b.esp"]], deps, {}, has_others={f["a.esp"]}) == 1 + 2 + 10
        assert estimate_output_size([f["a.esp"], f["b.esp"]], deps, {}, has_others=set()) == 3
        assert estimate_output_size([f["a.esp"], f["b.esp"]], deps, {}) == 33

    def test_nothing_selected(self):
        assert estimate_output_size([], {}, {}) == 0


class TestUnits:
    @pytest.mark.parametrize("size, expected", [
        (0, (0.0, "KBs")), (1024, (1.0, "KBs")), (1048576, (1024.0, "KBs")), (1048577, (1.0, "MBs")),
        (5 * 1048576, (5.0, "MBs")), (1024 ** 3, (1024.0, "MBs")), (1024 ** 3 + 1, (1.0, "GBs")),
        (int(2.5 * 1024 ** 3), (2.5, "GBs"))])
    def test_size_in_units(self, size, expected):
        assert size_in_units(size) == expected
