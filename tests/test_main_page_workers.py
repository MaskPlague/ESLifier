"""
The background workers in main_page: ScannerWorker, CompactorWorker, FlagWorker and HashWorker.

The workers are QObjects whose results leave through signals. Here the signals are replaced with recorders and the heavy
collaborators (scanner, CFIDs, cell master generator) with fakes, so the tests pin the orchestration: what is called, in
what order, with which flags, and what is emitted at the end.
"""
import hashlib
import json
import os

import pytest

import main.workers as workers
from data_holder import (_global, FLAG_DICTIONARY_JSON, MISSING_GAME_AS_MASTER_JSON, FILE_MASTERS_JSON,
                         ORIGINAL_FILES_JSON, WINNING_FILES_DICT_JSON, WINNING_FILE_HISTORY_DICT_JSON)
from main_page_fakes import Recorder


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------ ScannerWorker
class TestScannerWorker:
    @pytest.fixture
    def worker(self, g, monkeypatch):
        w = workers.ScannerWorker()
        w.tr = lambda text, *a: text
        w.finished_signal = Recorder()
        w.cell_scans = []
        monkeypatch.setattr(workers.cell_scanner, "scan", lambda plugins: w.cell_scans.append(list(plugins)), raising=False)
        return w

    def scan_returns(self, monkeypatch, flags, deps=None):
        monkeypatch.setattr(workers.scanner, "scan", lambda *a: (flags, deps or {}), raising=False)

    def test_flags_are_split_into_the_two_lists(self, worker, monkeypatch):
        self.scan_returns(monkeypatch, {
            "esl.esp": ["esl_flaggable"], "cmp.esp": ["need_compacting"],
            "both.esp": ["esl_flaggable", "need_compacting", "new_cell"], "none.esp": ["other"]}, {"x": ["y"]})
        worker.scan_run()
        (esl, cmp, deps), = worker.finished_signal.emitted
        assert set(esl) == {"esl.esp", "both.esp"} and set(cmp) == {"cmp.esp", "both.esp"}
        assert all(isinstance(flags, set) for flags in esl.values())
        assert deps == {"x": ["y"]}

    def test_cell_scanner_only_sees_plugins_with_new_cells(self, worker, monkeypatch):
        self.scan_returns(monkeypatch, {"a.esp": ["new_cell"], "b.esp": ["esl_flaggable"]})
        worker.scan_run()
        assert worker.cell_scans == [["a.esp"]]

    def test_vortex_error_emits_empty_results_and_skips_the_cell_scan(self, worker, monkeypatch, g):
        def failing_scan(*a):
            g.vortex_error = "boom"
            return {"a.esp": ["new_cell"]}, {}

        monkeypatch.setattr(workers.scanner, "scan", failing_scan, raising=False)
        worker.scan_run()
        assert worker.finished_signal.emitted == [({}, {}, {})]
        assert worker.cell_scans == []

    def test_mo2_error_emits_empty_results_and_skips_the_cell_scan(self, worker, monkeypatch, g):
        def failing_scan(*a):
            g.mo2_error = "boom"
            return {"a.esp": ["new_cell"]}, {}

        monkeypatch.setattr(workers.scanner, "scan", failing_scan, raising=False)
        worker.scan_run()
        assert worker.finished_signal.emitted == [({}, {}, {})]
        assert worker.cell_scans == []


# ------------------------------------------------------------------------------------------ fake CFIDs
class FakeCFIDs:
    instances = []

    def __init__(self, *args):
        self.args = args
        self.calls = []
        self.flag_results = {}
        FakeCFIDs.instances.append(self)

    def hash_output_files(self, files_to_not_hash, before_patching=False):
        self.calls.append(("hash", set(files_to_not_hash), before_patching))

    def compact_and_patch(self, *args):
        self.calls.append(("compact", args))

    def save_data(self):
        self.calls.append(("save",))

    def set_flag(self, file):
        self.calls.append(("flag", file))
        return self.flag_results.get("original", {file: ["o"]}), self.flag_results.get("history", {file: ["h"]})


class FakeCellPlugin:
    def __init__(self):
        self.calls = []

    def generate(self, path):
        self.calls.append(("generate", path))

    def finalize_plugin(self):
        self.calls.append(("finalize",))


@pytest.fixture
def fakes(workdir, g, monkeypatch):
    FakeCFIDs.instances = []
    plugin = FakeCellPlugin()
    monkeypatch.setattr(workers, "CFIDs", FakeCFIDs)
    monkeypatch.setattr(workers, "create_new_cell_plugin", lambda: plugin)
    monkeypatch.setattr(workers, "user_and_master_conditions_class", lambda: "conditions")
    g.update_header = False
    g.generate_cell_master = False
    g.hash_output = False
    g.game_archive_dict = {"Skyrim - Misc.bsa": ["Skyrim.esm"], "Other.bsa": ["Update.esm"]}
    g.output_folder_joined_path = "OUT"
    return plugin


def compactor(checked, deps, not_hash=()):
    w = workers.CompactorWorker(checked, deps, set(not_hash))
    w.tr = lambda text, *a: text
    w.finished_signal = Recorder()
    return w


# ------------------------------------------------------------------------------------------ CompactorWorker
class TestCompactorWorker:
    def setup_data(self, flags):
        put(FLAG_DICTIONARY_JSON, flags)
        put(FILE_MASTERS_JSON, {"patch": ["me"]})
        put(ORIGINAL_FILES_JSON, {"orig": 1})
        put(WINNING_FILES_DICT_JSON, {"win": 1})

    def test_each_checked_plugin_is_compacted_then_data_saved(self, fakes):
        self.setup_data({"A.esp": [], "B.esp": []})
        w = compactor(["A.esp", "B.esp"], {"a.esp": ["x.esp"], "b.esp": []})
        w.run()
        cfids, = FakeCFIDs.instances
        kinds = [c[0] for c in cfids.calls]
        assert kinds == ["compact", "compact", "save"]
        first = cfids.calls[0][1]
        assert first == ("A.esp", ["x.esp"], True, False, {"patch": ["me"]})
        assert w.finished_signal.emitted == [()]

    def test_cfids_is_built_from_the_saved_data(self, fakes):
        self.setup_data({"A.esp": []})
        compactor(["A.esp"], {"a.esp": []}).run()
        args = FakeCFIDs.instances[0].args
        assert args[0] is fakes
        assert args[1] == {"orig": 1} and args[2] == {"win": 1} and args[5] == {}   # master byte data not saved yet
        assert sorted(args[6]) == ["Skyrim.esm", "Update.esm"]
        assert args[7] == "conditions"

    def test_dependents_missing_the_game_master_are_reported_to_the_patcher(self, fakes, g):
        g.update_header = True
        put(MISSING_GAME_AS_MASTER_JSON, {"dep.esp": "Master.esm"})
        self.setup_data({"Master.esm": [], "Other.esp": []})
        w = compactor(["Master.esm", "Other.esp"], {"master.esm": ["dep.esp"], "other.esp": ["dep.esp"]})
        w.run()
        compacts = [c[1] for c in FakeCFIDs.instances[0].calls if c[0] == "compact"]
        assert compacts[0][2] is False     # dep.esp lacks the game master and Master.esm is its first master
        assert compacts[1][2] is True      # a different master: unaffected

    def test_missing_game_master_file_is_tolerated(self, fakes, g):
        g.update_header = True
        self.setup_data({"A.esp": []})
        compactor(["A.esp"], {"a.esp": []}).run()
        assert FakeCFIDs.instances[0].calls[0][1][2] is True

    def test_cell_master_is_generated_and_finalised_for_new_cells(self, fakes, g):
        g.generate_cell_master = True
        self.setup_data({"New.esp": ["new_cell"], "Full.esp": ["new_cell", "maxed_masters"], "Plain.esp": []})
        compactor(["New.esp", "Full.esp", "Plain.esp"], {"new.esp": [], "full.esp": [], "plain.esp": []}).run()
        assert fakes.calls == [("generate", "OUT"), ("finalize",)]
        compacts = [c[1] for c in FakeCFIDs.instances[0].calls if c[0] == "compact"]
        assert [c[3] for c in compacts] == [True, False, False]

    def test_no_finalise_when_no_plugin_needed_a_cell_master(self, fakes, g):
        g.generate_cell_master = True
        self.setup_data({"Plain.esp": []})
        compactor(["Plain.esp"], {"plain.esp": []}).run()
        assert fakes.calls == [("generate", "OUT")]

    def test_cell_master_untouched_when_the_setting_is_off(self, fakes):
        self.setup_data({"New.esp": ["new_cell"]})
        compactor(["New.esp"], {"new.esp": []}).run()
        assert fakes.calls == []
        assert FakeCFIDs.instances[0].calls[0][1][3] is False

    def test_hashing_brackets_the_patching_when_enabled(self, fakes, g):
        g.hash_output = True
        self.setup_data({"A.esp": []})
        compactor(["A.esp"], {"a.esp": []}, not_hash={"keep"}).run()
        assert FakeCFIDs.instances[0].calls == [
            ("hash", set(), True),                       # before: spot files changed since last time
            ("compact", ("A.esp", [], True, False, {"patch": ["me"]})),
            ("save",),
            ("hash", {"keep"}, False)]                   # after: record hashes, except for files the user kept

    def test_no_hashing_when_disabled(self, fakes):
        self.setup_data({"A.esp": []})
        compactor(["A.esp"], {"a.esp": []}).run()
        assert not [c for c in FakeCFIDs.instances[0].calls if c[0] == "hash"]

    def test_nothing_checked_still_saves_and_finishes(self, fakes):
        self.setup_data({})
        w = compactor([], {})
        w.run()
        assert [c[0] for c in FakeCFIDs.instances[0].calls] == ["save"]
        assert w.finished_signal.emitted == [()]


# ------------------------------------------------------------------------------------------ FlagWorker
class TestFlagWorker:
    def make(self, files, not_hash=()):
        w = workers.FlagWorker(files, set(not_hash))
        w.tr = lambda text, *a: text
        w.finished_signal = Recorder()
        return w

    def test_every_file_is_flagged_and_results_are_merged_into_the_saved_data(self, fakes):
        put(ORIGINAL_FILES_JSON, {"old.esp": ["keep"]})
        put(WINNING_FILE_HISTORY_DICT_JSON, {"older": ["keep"]})
        w = self.make(["a.esp", "b.esp"])
        w.flag_files()
        cfids, = FakeCFIDs.instances
        assert [c for c in cfids.calls] == [("flag", "a.esp"), ("flag", "b.esp")]
        assert get(ORIGINAL_FILES_JSON) == {"old.esp": ["keep"], "b.esp": ["o"]}      # set_flag returns running totals
        assert get(WINNING_FILE_HISTORY_DICT_JSON) == {"older": ["keep"], "b.esp": ["h"]}
        assert w.finished_signal.emitted == [()]

    def test_cfids_is_built_without_a_cell_plugin_or_master_data(self, fakes):
        put(ORIGINAL_FILES_JSON, {"o": 1})
        put(WINNING_FILES_DICT_JSON, {"w": 1})
        self.make([]).flag_files()
        args = FakeCFIDs.instances[0].args
        assert args[0] is None and args[1] == {"o": 1} and args[2] == {"w": 1} and args[6] == []

    def test_hashing_brackets_the_flagging_when_enabled(self, fakes, g):
        g.hash_output = True
        self.make(["a.esp"], not_hash={"keep"}).flag_files()
        assert FakeCFIDs.instances[0].calls == [("hash", set(), True), ("flag", "a.esp"), ("hash", {"keep"}, False)]

    def test_no_files_still_finishes_and_leaves_saved_data_alone(self, fakes):
        put(ORIGINAL_FILES_JSON, {"o": 1})
        w = self.make([])
        w.flag_files()
        assert get(ORIGINAL_FILES_JSON) == {"o": 1}
        assert w.finished_signal.emitted == [()]


# ------------------------------------------------------------------------------------------ HashWorker
class TestHashWorker:
    @pytest.fixture
    def out(self, tmp_path, g, monkeypatch):
        folder = tmp_path / "out"
        folder.mkdir()
        monkeypatch.setattr(_global, "get_rel_path", lambda f: os.path.relpath(f, str(folder)).replace(os.sep, "/"),
                            raising=False)
        g.hash_plugins_warn = True
        return folder

    def make_files(self, out, files):
        paths = []
        for name, data in files.items():
            p = out / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            paths.append(str(p))
        return paths

    def run(self, paths, hashes):
        w = workers.HashWorker(paths, hashes)
        w.tr = lambda text, *a: text
        w.finished = Recorder()
        w.run()
        (result,), = w.finished.emitted
        return w, result

    def test_unchanged_unknown_and_changed_files_are_told_apart(self, out):
        paths = self.make_files(out, {"same.nif": b"aaa", "new.nif": b"bb", "edited.ini": b"edited"})
        hashes = {"same.nif": (sha(b"aaa"), False), "edited.ini": (sha(b"original"), False)}
        w, r = self.run(paths, hashes)
        assert sorted(os.path.basename(f) for f in r["files_to_remove"]) == ["new.nif", "same.nif"]
        assert r["file_count"] == 2 and r["size"] == 5
        assert [rel for _, rel in r["changed_hashes"]] == ["edited.ini"]
        assert w.new_file_hashes["edited.ini"] == (sha(b"original"), True)   # remembered as changed

    def test_a_file_already_marked_changed_stays_changed(self, out):
        paths = self.make_files(out, {"a.ini": b"x"})
        _, r = self.run(paths, {"a.ini": (sha(b"x"), True)})
        assert r["files_to_remove"] == [] and [rel for _, rel in r["changed_hashes"]] == ["a.ini"]

    def test_unreadable_files_are_skipped(self, out):
        paths = self.make_files(out, {"a.nif": b"1"}) + [str(out / "gone.nif")]
        _, r = self.run(paths, {})
        assert [os.path.basename(f) for f in r["files_to_remove"]] == ["a.nif"]

    def test_plugins_are_not_hashed_but_still_removed_when_warnings_are_off(self, out, g):
        g.hash_plugins_warn = False
        paths = self.make_files(out, {"a.esp": b"12345", "b.esl": b"1", "c.esm": b"12", "d.nif": b"1"})
        _, r = self.run(paths, {"a.esp": (sha(b"different"), False)})
        assert sorted(os.path.basename(f) for f in r["files_to_remove"]) == ["a.esp", "b.esl", "c.esm", "d.nif"]
        assert r["changed_hashes"] == []
        assert r["file_count"] == 4 and r["size"] == 5 + 1 + 2 + 1

    def test_changed_plugins_are_reported_when_warnings_are_on(self, out):
        paths = self.make_files(out, {"a.esp": b"new"})
        _, r = self.run(paths, {"a.esp": (sha(b"old"), False)})
        assert r["files_to_remove"] == [] and [rel for _, rel in r["changed_hashes"]] == ["a.esp"]

    def test_large_files_are_hashed_in_chunks(self, out):
        data = os.urandom(3 * 1048576 + 17)
        paths = self.make_files(out, {"big.bin": data})
        _, r = self.run(paths, {"big.bin": (sha(data), False)})
        assert r["files_to_remove"] == paths and r["size"] == len(data)

    def test_no_files(self, out):
        _, r = self.run([], {})
        assert r == {"size": 0, "file_count": 0, "files_to_remove": [], "changed_hashes": []}

    @pytest.mark.parametrize("count", [1, 5, 16, 17, 31, 100, 1000])
    def test_every_file_is_processed_exactly_once(self, out, count):
        paths = self.make_files(out, {f"f{i}.nif": str(i).encode() for i in range(count)})
        _, r = self.run(paths, {})
        assert sorted(r["files_to_remove"]) == sorted(paths) and r["file_count"] == count

    def test_never_more_threads_than_the_limit(self, out, monkeypatch):
        started = []
        real = workers.threading.Thread

        class CountingThread(real):
            def start(self):
                started.append(self)
                super().start()

        monkeypatch.setattr(workers.threading, "Thread", CountingThread)
        monkeypatch.setattr(workers.os, "cpu_count", lambda: 16)
        paths = self.make_files(out, {f"f{i}.nif": b"x" for i in range(31)})
        self.run(paths, {})
        assert 1 <= len(started) <= 16

    def test_a_failing_chunk_reports_an_error_instead_of_a_partial_list(self, out, monkeypatch, log):
        paths = self.make_files(out, {f"f{i}.nif": b"x" for i in range(20)})
        monkeypatch.setattr(_global, "get_rel_path", lambda f: (_ for _ in ()).throw(RuntimeError("bad path")), raising=False)
        w, r = self.run(paths, {})
        assert r["error"] == "bad path"
        assert r["files_to_remove"] == [] and r["changed_hashes"] == [] and r["file_count"] == 0
        assert log.errors
