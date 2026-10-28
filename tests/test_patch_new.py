"""
patch_new: the "Patch New" feature, which looks for changes since the last run (modified output files,
changed mod-manager conflict winners, new dependents/files) and re-patches only what's needed.

  * PatchNewScannerWorker  - works out which output files to delete and which new files need patching
  * PatchNewWorker         - patches the new files (CFIDs is replaced by a recorder here)
  * patch_new              - the UI glue (message boxes, thread hand-offs); Qt is faked

The real Qt classes are stubbed out (see conftest), so signals are replaced with recorders and ``tr`` with
the identity function.
"""
import hashlib
import json
import os
import pathlib
import threading
import types

import pytest

import patch_new as pn
from data_holder import _global
from plugin_builder import write as write_bytes


# ------------------------------------------------------------------------------------------ fakes
class Sig:
    """A pyqtSignal stand-in: records emits and remembers connected callbacks."""

    def __init__(self):
        self.calls = []
        self.callbacks = []

    def emit(self, *args):
        self.calls.append(args)

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeParent:
    def __init__(self):
        self.events = []
        self.redoing_output = None
        self.patch_new_running = None
        self.patch_new_only_remove = None

    def setEnabled(self, value):
        self.events.append(("setEnabled", value))

    def calculate_stats(self):
        self.events.append(("calculate_stats",))

    def scan(self):
        self.events.append(("scan",))


class FakeMessageBox:
    instances = []
    warnings = []
    Icon = types.SimpleNamespace(Information="info")
    StandardButton = types.SimpleNamespace(Ok="ok", Abort="abort")

    def __init__(self):
        FakeMessageBox.instances.append(self)
        self.accepted, self.rejected = Sig(), Sig()
        self.title = self.text = None
        self.buttons = []
        self.shown = self.hidden = False

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.text = text

    def setWindowIcon(self, icon):
        pass

    def addButton(self, button):
        self.buttons.append(button)

    def show(self):
        self.shown = True

    def hide(self):
        self.hidden = True

    @staticmethod
    def warning(parent, title, text):
        FakeMessageBox.warnings.append((title, text))


@pytest.fixture
def boxes(monkeypatch):
    FakeMessageBox.instances = []
    FakeMessageBox.warnings = []
    monkeypatch.setattr(pn, "QMessageBox", FakeMessageBox)
    return FakeMessageBox


@pytest.fixture
def logcalls(monkeypatch):
    calls = []
    monkeypatch.setattr(pn, "clear_and_close_log", lambda: calls.append("close"))
    monkeypatch.setattr(pn, "clear_and_leave_log_open", lambda: calls.append("leave_open"))
    return calls


# ------------------------------------------------------------------------------------------ environment
@pytest.fixture
def env(workdir, monkeypatch, logcalls):
    """Skyrim data folder + output folder in the temp dir, manual-mode globals, and a simple get_rel_path."""
    sky = workdir / "Skyrim"
    out = workdir / "Output" / "ESLifier Output"
    sky.mkdir()
    out.mkdir(parents=True)
    _global.output_folder_name = "ESLifier Output"
    _global.output_folder_joined_path = str(out)
    _global.mod_manager_mode = 0
    _global.hash_output = False
    monkeypatch.setattr(_global, "get_rel_path", lambda f: _rel(str(f), str(sky), str(out)))
    scans = []
    monkeypatch.setattr(pn, "scanner", types.SimpleNamespace(scan=lambda full: scans.append(("scan", full))))
    monkeypatch.setattr(pn, "dependecy_getter", types.SimpleNamespace(scan=lambda: scans.append(("deps",))))
    monkeypatch.setattr(pn.PatchNewScannerWorker, "tr", lambda self, s: s, raising=False)
    monkeypatch.setattr(pn.PatchNewWorker, "tr", lambda self, s: s, raising=False)
    return types.SimpleNamespace(root=workdir, sky=sky, out=out, scans=scans)


def _rel(path, sky, out):
    for base in (out, sky):
        if path.startswith(base):
            return os.path.relpath(path, base)
    raise RuntimeError("no relative path for " + path)


def rp(text):
    """Spell a relative path with the OS separator (the fixtures below write them with '/').
    Absolute POSIX-looking paths such as '/mods/x' are left alone."""
    if isinstance(text, str) and not text.startswith("/"):
        return text.replace("/", os.sep)
    return text


def _native(obj):
    if isinstance(obj, dict):
        return {rp(k): _native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_native(v) for v in obj]
    return rp(obj)


def data(env, name, content):
    path = env.root / "ESLifier_Data" / name
    path.write_text(json.dumps(_native(content)), encoding="utf-8")
    return path


def read(env, name):
    return json.loads((env.root / "ESLifier_Data" / name).read_text(encoding="utf-8"))


def make_worker(env):
    worker = pn.PatchNewScannerWorker(FakeParent())
    worker.finished_signal = Sig()
    worker.delete_confirmation_signal = Sig()
    return worker


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sky(env, *parts):
    return str(env.sky.joinpath(*parts))


def out(env, *parts):
    return str(env.out.joinpath(*parts))


# ------------------------------------------------------------------------------------------ detect_new_files
@pytest.fixture
def new_files_data(env):
    """Existing compacted mod ModA.esp that already patched meshes/old.nif and scripts/old.pex."""
    data(env, "compacted_and_patched.json", {"ModA.esp": ["meshes/old.nif", "scripts/old.pex"]})
    data(env, "file_masters.json", {"moda.esp": [sky(env, "meshes", "old.nif"), sky(env, "meshes", "new.nif")]})
    data(env, "dependency_dictionary.json", {"moda.esp": [sky(env, "scripts", "old.pex"), sky(env, "Dep.esp")]})
    data(env, "dll_dict.json", {})
    return env


def test_new_files_and_new_dependents_are_found(new_files_data):
    w = make_worker(new_files_data)
    w.detect_new_files()
    (mod_list, new_deps, new_files, hash_n, conflict_n, skse), = w.finished_signal.calls
    assert new_files == {"ModA.esp": [sky(new_files_data, "meshes", "new.nif")]}
    assert new_deps == {"ModA.esp": [sky(new_files_data, "Dep.esp")]}
    assert mod_list == ["ModA.esp"]
    assert (hash_n, conflict_n, skse) == (0, 0, [])


def test_mod_list_lists_dependents_first_then_mods_with_only_new_files(env):
    data(env, "compacted_and_patched.json", {"ModA.esp": [], "ModB.esp": [], "ModC.esp": []})
    data(env, "file_masters.json", {"moda.esp": [sky(env, "a_file.ini")], "modb.esp": [sky(env, "b_file.ini")]})
    data(env, "dependency_dictionary.json", {"modb.esp": [sky(env, "dep.esp")], "modc.esp": [sky(env, "dep2.esp")]})
    data(env, "dll_dict.json", {})
    w = make_worker(env)
    w.detect_new_files()
    mod_list = w.finished_signal.calls[0][0]
    assert mod_list == ["ModB.esp", "ModC.esp", "ModA.esp"]


def test_nothing_new_gives_an_empty_mod_list(env):
    data(env, "compacted_and_patched.json", {"ModA.esp": ["meshes/old.nif"]})
    data(env, "file_masters.json", {"moda.esp": [sky(env, "meshes", "old.nif")]})
    data(env, "dependency_dictionary.json", {})
    data(env, "dll_dict.json", {})
    w = make_worker(env)
    w.detect_new_files()
    assert w.finished_signal.calls == [([], {}, {}, 0, 0, [])]


def test_masters_missing_from_the_dictionaries_are_skipped(env):
    data(env, "compacted_and_patched.json", {"Unknown.esp": []})
    data(env, "file_masters.json", {})
    data(env, "dependency_dictionary.json", {})
    data(env, "dll_dict.json", {})
    w = make_worker(env)
    w.detect_new_files()
    assert w.finished_signal.calls[0][:3] == ([], {}, {})


def test_dll_that_references_a_compacted_mod_triggers_a_warning(new_files_data):
    data(new_files_data, "dll_dict.json", {"moda.esp": ["/x/a.dll"], "modz.esp": ["z.dll"]})
    data(new_files_data, "compacted_and_patched.json", {"ModA.esp": ["meshes/old.nif", "scripts/old.pex"]})
    data(new_files_data, "file_masters.json", {"moda.esp": [sky(new_files_data, "meshes", "old.nif")]})
    data(new_files_data, "dependency_dictionary.json", {"moda.esp": [sky(new_files_data, "scripts", "old.pex")]})
    w = make_worker(new_files_data)
    w.detect_new_files()
    skse = w.finished_signal.calls[0][5]
    assert skse == [("moda.esp", ["a.dll"])]                       # modz isn't compacted


def test_no_dll_warning_when_the_mod_is_already_being_repatched(new_files_data):
    data(new_files_data, "dll_dict.json", {"moda.esp": ["a.dll"]})
    w = make_worker(new_files_data)
    w.detect_new_files()
    assert w.finished_signal.calls[0][5] == []


def test_counts_of_earlier_changes_are_passed_along(new_files_data):
    w = make_worker(new_files_data)
    w.hash_mismatches = [("a", "a"), ("b", "b")]
    w.conflict_changes = [("c", "c", "c")]
    w.detect_new_files()
    assert w.finished_signal.calls[0][3:5] == (2, 1)


def test_missing_compacted_data_ends_early(env):
    w = make_worker(env)
    w.detect_new_files()
    assert len(w.finished_signal.calls) == 1
    assert w.finished_signal.calls[0][1:] == ({}, {}, 0, 0, [])


def test_missing_compacted_data_emits_a_list_for_the_mod_list(env):
    w = make_worker(env)
    w.detect_new_files()
    assert isinstance(w.finished_signal.calls[0][0], list)


@pytest.mark.parametrize("missing", ["file_masters.json", "dependency_dictionary.json", "dll_dict.json"])
def test_a_missing_dictionary_is_reported_and_ends_early(new_files_data, missing, log):
    (new_files_data.root / "ESLifier_Data" / missing).unlink()
    w = make_worker(new_files_data)
    w.detect_new_files()
    assert w.finished_signal.calls == [([], {}, {}, 0, 0, [])]
    assert any("Failed to find a required dictionary" in e for e in log.errors)


# ------------------------------------------------------------------------------------------ compare_previous_hash_to_current
def test_changed_file_is_recorded_as_a_hash_mismatch(env):
    path = write_bytes(env.out / "meshes" / "a.nif", b"new content")
    w = make_worker(env)
    w.compare_previous_hash_to_current(path, sha(b"old content"))
    assert w.hash_mismatches == [(os.path.join("meshes", "a.nif"), path)]


def test_unchanged_and_missing_files_are_not_mismatches(env):
    path = write_bytes(env.out / "a.nif", b"same")
    w = make_worker(env)
    w.compare_previous_hash_to_current(path, sha(b"same"))
    w.compare_previous_hash_to_current(out(env, "missing.nif"), sha(b"anything"))
    assert w.hash_mismatches == []


# ------------------------------------------------------------------------------------------ detect_changes
@pytest.fixture
def changes(env, monkeypatch):
    """A scan state where ModA.esp (compacted) patched meshes/a_patched.nif; captures the delete step."""
    data(env, "compacted_and_patched.json", {"ModA.esp": ["meshes/a_patched.nif"], "ModB.esp": []})
    data(env, "file_masters.json", {"moda.esp": [sky(env, "meshes", "a_patched.nif"), sky(env, "meshes", "a.nif")]})
    data(env, "dependency_dictionary.json", {"base.esm": [sky(env, "ModA.esp"), sky(env, "ModF.esp")]})
    # run the per-file hash checks one after another (in file order) so results are deterministic
    class SyncThread:
        def __init__(self, target=None, args=()):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

        def join(self):
            pass

    monkeypatch.setattr(pn, "threading", types.SimpleNamespace(
        Thread=SyncThread, Lock=threading.Lock, Semaphore=threading.Semaphore))
    captured = []
    monkeypatch.setattr(pn.PatchNewScannerWorker, "delete_and_patch_changed",
                        lambda self, files, only_remove, history, cap: captured.append(
                            (files, only_remove, history, cap)))
    return env, captured


def original(env, **entries):
    """original_files.json from {rel: (full_path, hash)}, creating each file with content b'current'."""
    payload = {}
    for rel, (full, h) in entries.items():
        write_bytes(env.out / rel, b"current")
        payload[rel.lower()] = [full, h]
    data(env, "original_files.json", payload)


def test_scan_runs_the_scanner_and_dependency_getter_first(changes):
    env, captured = changes
    w = make_worker(env)
    w.detect_changes()
    assert env.scans == [("scan", False), ("deps",)]


def test_unchanged_output_goes_straight_to_detecting_new_files(changes, monkeypatch):
    env, captured = changes
    original(env, **{"meshes/a_patched.nif": (out(env, "meshes", "a_patched.nif"), sha(b"current"))})
    w = make_worker(env)
    monkeypatch.setattr(w, "detect_new_files", lambda: w.finished_signal.emit("new files detected"))
    w.detect_changes()
    assert captured == []
    assert w.finished_signal.calls == [("new files detected",)]
    assert read(env, "previously_compacted.json") == ["ModA.esp", "ModB.esp"]


def test_modified_compacted_plugin_removes_it_and_everything_patched_for_it(changes):
    env, captured = changes
    original(env, **{"ModA.esp": (out(env, "ModA.esp"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    (files, only_remove, history, cap), = captured
    assert files == set([out(env, "ModA.esp"), out(env, "meshes", "a_patched.nif")])
    assert only_remove is False                                     # plugin must be rebuilt, not just deleted
    assert cap == {"ModB.esp": set()}                                  # ModA is no longer considered compacted


def test_modified_patched_file_is_removed_and_forgotten(changes):
    env, captured = changes
    original(env, **{"meshes/a_patched.nif": (out(env, "meshes", "a_patched.nif"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    (files, only_remove, history, cap), = captured
    assert files == set([out(env, "meshes", "a_patched.nif")])
    assert only_remove is False
    assert cap == {"ModA.esp": set(), "ModB.esp": set()}


def test_modified_output_file_nobody_tracks_is_just_deleted(changes):
    env, captured = changes
    original(env, **{"textures/x.dds": (out(env, "textures", "x.dds"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    (files, only_remove, history, cap), = captured
    assert files == set([out(env, "textures", "x.dds")])
    assert only_remove is True                                      # nothing to re-patch, only remove


def test_modified_esl_flagged_plugin_is_removed(changes):
    env, captured = changes
    data(env, "esl_flagged.json", ["ModF.esp"])
    original(env, **{"ModF.esp": (out(env, "ModF.esp"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    (files, only_remove, history, cap), = captured
    assert files == set([out(env, "ModF.esp")])


def test_a_modified_plugin_and_its_modified_patched_file_are_both_removed(changes):
    env, captured = changes
    original(env, **{"ModA.esp": (out(env, "ModA.esp"), "stale-hash"),
                     "meshes/a_patched.nif": (out(env, "meshes", "a_patched.nif"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    files = captured[0][0]
    assert set(files) == {out(env, "ModA.esp"), out(env, "meshes", "a_patched.nif")}


def test_each_file_is_only_queued_for_deletion_once(changes):
    env, captured = changes
    original(env, **{"ModA.esp": (out(env, "ModA.esp"), "stale-hash"),
                     "meshes/a_patched.nif": (out(env, "meshes", "a_patched.nif"), "stale-hash")})
    w = make_worker(env)
    w.detect_changes()
    files = captured[0][0]
    assert len(files) == len(set(files))


def test_hash_check_is_skipped_without_original_files_data(changes, monkeypatch):
    env, captured = changes
    w = make_worker(env)
    monkeypatch.setattr(w, "detect_new_files", lambda: None)
    w.detect_changes()
    assert w.hash_mismatches == [] and captured == []


class MO2Mode:
    """Conflict detection only runs with a mod manager; set the mode before building the worker."""

    @staticmethod
    def enable(env):
        _global.mod_manager_mode = 2


def test_conflict_detection_is_skipped_in_manual_mode(changes, monkeypatch):
    env, captured = changes
    data(env, "winning_file_history_dict.json", {"meshes/a.nif": "OldMod"})
    data(env, "winning_files_dict.json", {"meshes/a.nif": ["NewMod", "/mods/NewMod/meshes/a.nif"]})
    w = make_worker(env)
    monkeypatch.setattr(w, "detect_new_files", lambda: None)
    w.detect_changes()
    assert w.conflict_changes == [] and captured == []


def test_changed_conflict_winners_are_detected(changes, monkeypatch):
    env, captured = changes
    MO2Mode.enable(env)
    data(env, "winning_file_history_dict.json", {"meshes/a.nif": "OldMod", "meshes/gone.nif": "OldMod",
                                                 "meshes/same.nif": "Mod"})
    data(env, "winning_files_dict.json", {"meshes/a.nif": ["NewMod", "/mods/NewMod/meshes/a.nif"],
                                          "meshes/same.nif": ["Mod", "/mods/Mod/meshes/same.nif"]})
    w = make_worker(env)
    monkeypatch.setattr(w, "detect_new_files", lambda: None)
    w.detect_changes()
    assert sorted(w.conflict_changes) == sorted([
        (rp("meshes/a.nif"), "/mods/NewMod/meshes/a.nif", "c"),                # a different mod wins now
        (rp("meshes/gone.nif"), os.path.join(w.output_path, rp("meshes/gone.nif")), "c"),   # no mod provides it any more
    ])
    # only the output copy of the vanished file is removable; the new winner lives outside the output folder
    assert captured[0][0] == set([os.path.join(w.output_path, rp("meshes/gone.nif"))])


def test_changed_winner_of_a_patched_file_forces_repatching(changes, monkeypatch):
    env, captured = changes
    MO2Mode.enable(env)
    data(env, "compacted_and_patched.json", {"ModA.esp": ["meshes/a.nif"]})
    data(env, "winning_file_history_dict.json", {"meshes/a.nif": "OldMod"})
    data(env, "winning_files_dict.json", {"meshes/a.nif": ["NewMod", "/mods/NewMod/meshes/a.nif"]})
    w = make_worker(env)
    w.detect_changes()
    (files, only_remove, history, cap), = captured
    assert files == set([out(env, "meshes", "a.nif")])
    assert only_remove is False
    assert cap == {"ModA.esp": set()}
    assert history == {rp("meshes/a.nif"): "OldMod"}


def test_unreadable_data_file_stops_the_scan_cleanly(env, log):
    data(env, "dependency_dictionary.json", {})                      # file_masters.json is missing
    w = make_worker(env)
    w.detect_changes()
    assert len(w.finished_signal.calls) == 1


# ------------------------------------------------------------------------------------------ delete_and_patch_changed
def test_only_existing_files_inside_the_output_folder_are_offered_for_deletion(env):
    existing = write_bytes(env.out / "meshes" / "a.nif", b"x")
    outside = write_bytes(env.sky / "meshes" / "b.nif", b"x")        # exists, but not in ESLifier's output
    missing = out(env, "meshes", "missing.nif")
    w = make_worker(env)
    w.delete_and_patch_changed([existing, outside, missing], True, {"h": 1}, {"c": []})
    (text, files, history, only_remove, cap), = w.delete_confirmation_signal.calls
    assert files == [existing]
    assert "delete 1 files" in text
    assert (history, only_remove, cap) == ({"h": 1}, True, {"c": []})
    assert "game plugins" not in text and "destructive" in text


def test_plugins_are_called_out_in_the_confirmation_text(env):
    plugin = write_bytes(env.out / "ModA.esp", b"x")
    other = write_bytes(env.out / "a.nif", b"x")
    w = make_worker(env)
    w.delete_and_patch_changed([plugin, other], False, {}, {})
    text = w.delete_confirmation_signal.calls[0][0]
    assert "delete 2 files" in text
    assert "1 are game plugins" in text
    assert "The plugins that will be deleted are:" in text and " - ModA.esp" in text


def test_long_plugin_lists_are_truncated_to_ten(env):
    files = [write_bytes(env.out / f"Mod{i:02}.esp", b"x") for i in range(13)]
    w = make_worker(env)
    w.delete_and_patch_changed(files, False, {}, {})
    text = w.delete_confirmation_signal.calls[0][0]
    assert "Some plugins that will be deleted include:" in text
    assert text.count(" - Mod") == 10
    assert "and 3 more..." in text


def test_nothing_to_confirm_deletes_immediately(env, monkeypatch):
    w = make_worker(env)
    calls = []
    monkeypatch.setattr(w, "delete_files", lambda *a: calls.append(a))
    w.delete_and_patch_changed([out(env, "missing.nif")], True, {"h": 1}, {"c": []})
    assert w.delete_confirmation_signal.calls == []
    assert calls == [([], {"h": 1}, True, {"c": []})]


# ------------------------------------------------------------------------------------------ delete_files
@pytest.fixture
def deletion(env):
    data(env, "original_files.json", {"meshes/a.nif": ["x", "h1"], "meshes/b.nif": ["y", "h2"], "keep.nif": ["z", "h3"]})
    return env


def test_delete_files_removes_files_and_forgets_them(deletion):
    env = deletion
    a = write_bytes(env.out / "meshes" / "a.nif", b"x")
    b = write_bytes(env.out / "meshes" / "b.nif", b"x")
    w = make_worker(env)
    w.delete_files([a, b, out(env, "meshes", "already_gone.nif")], {rp("meshes/a.nif"): "Mod", "other.nif": "Mod"},
                   True, {"ModA.esp": ["x"]})
    assert not os.path.exists(a) and not os.path.exists(b)
    assert read(env, "compacted_and_patched.json") == {"ModA.esp": ["x"]}
    assert read(env, "original_files.json") == {"keep.nif": ["z", "h3"]}
    assert read(env, "winning_file_history_dict.json") == {"other.nif": "Mod"}


def test_delete_files_restarts_the_scan_flagged_as_a_patch_new_run(deletion, logcalls):
    env = deletion
    w = make_worker(env)
    w.delete_files([], {}, False, {})
    parent = w.main_parent
    assert parent.redoing_output is True and parent.patch_new_running is True
    assert parent.patch_new_only_remove is False
    assert parent.events == [("scan",)]
    assert "leave_open" in logcalls


def test_delete_files_restores_vortex_backups_for_hardlinked_files(deletion, monkeypatch):
    env = deletion
    _global.mod_manager_mode = 1
    _global.vortex_restore_backups = True
    data_dir = env.sky
    monkeypatch.setattr(pn.VortexDBParser, "get_section",
                        lambda s: {"path": str(data_dir.parent)} if "discovered" in s else {})
    (data_dir.parent / "Data").mkdir(exist_ok=True)
    skyrim_data = data_dir.parent / "Data"
    out_file = write_bytes(env.out / "meshes" / "a.nif", b"ESLifier version")
    game_file = skyrim_data / "meshes" / "a.nif"
    game_file.parent.mkdir(parents=True)
    os.link(out_file, game_file)                                     # Vortex deploys by hardlink
    backup = write_bytes(skyrim_data / "meshes" / "a.nif.vortex_backup", b"original version")
    # a second file with a backup that is NOT linked to the output copy must be left alone
    out_other = write_bytes(env.out / "meshes" / "b.nif", b"ESLifier b")
    game_other = pathlib.Path(write_bytes(skyrim_data / "meshes" / "b.nif", b"someone else's b"))
    write_bytes(skyrim_data / "meshes" / "b.nif.vortex_backup", b"backup b")
    monkeypatch.setattr(_global, "get_rel_path", lambda f: os.path.relpath(f, str(env.out)))
    w = make_worker(env)
    w.delete_files([out_file, out_other], {}, True, {})
    assert not os.path.exists(out_file) and not os.path.exists(out_other)
    assert game_file.read_bytes() == b"original version"             # backup restored over the hardlink
    assert game_other.read_bytes() == b"someone else's b"            # untouched


# ------------------------------------------------------------------------------------------ PatchNewWorker
class FakeCFIDs:
    instances = []

    def __init__(self, *args):
        self.args = args
        self.patched = []
        self.hashed = []
        self.saved = 0
        FakeCFIDs.instances.append(self)

    def patch_new(self, mod, dependents, files):
        self.patched.append((mod, list(dependents), files))

    def hash_output_files(self, files_to_skip, before):
        self.hashed.append((files_to_skip, before))

    def save_data(self):
        self.saved += 1


@pytest.fixture
def patch_worker(env, monkeypatch):
    FakeCFIDs.instances = []
    monkeypatch.setattr(pn, "CFIDs", FakeCFIDs)
    monkeypatch.setattr(pn, "user_and_master_conditions_class", lambda: "conditions")
    return env


def make_patch_worker(mods, deps, files):
    w = pn.PatchNewWorker(mods, deps, files)
    w.finished_signal = Sig()
    return w


def test_patch_new_files_patches_each_mod_with_its_dependents(patch_worker):
    env = patch_worker
    data(env, "original_files.json", {"o": 1})
    data(env, "winning_files_dict.json", {"w": 2})
    data(env, "master_byte_data.json", {"m": 3})
    deps = {"ModA.esp": ["dep1.esp", "dep2.esp"]}
    files = {"ModA.esp": ["a.nif"], "ModB.esp": ["b.nif", "a.nif"]}
    w = make_patch_worker(["ModA.esp", "ModB.esp"], deps, files)
    w.patch_new_files()
    cfids, = FakeCFIDs.instances
    assert cfids.patched == [("ModA.esp", ["dep1.esp", "dep2.esp"], files), ("ModB.esp", [], files)]
    _, original_files, winning, history, compacted, master_bytes, game_archive_masters, conditions = cfids.args
    assert (original_files, winning, master_bytes) == ({"o": 1}, {"w": 2}, {"m": 3})
    assert history == {} and compacted == {} and game_archive_masters == [] and conditions == "conditions"
    assert cfids.saved == 1
    assert w.finished_signal.calls == [(4,)]                         # dep1, dep2, a.nif, b.nif: unique files only


def test_patch_new_files_with_hash_output_hashes_before_and_after(patch_worker):
    _global.hash_output = True
    w = make_patch_worker(["ModA.esp"], {}, {})
    w.patch_new_files()
    cfids, = FakeCFIDs.instances
    assert cfids.hashed == [([], True), ([], True)]
    assert w.finished_signal.calls == [(0,)]


def test_patch_new_files_without_hash_output_does_not_hash(patch_worker):
    _global.hash_output = False
    w = make_patch_worker(["ModA.esp"], {}, {})
    w.patch_new_files()
    assert FakeCFIDs.instances[0].hashed == []


def test_worker_get_from_file(env):
    w = make_patch_worker([], {}, {})
    good = env.root / "ESLifier_Data" / "g.json"
    good.write_text('{"a": 1}', encoding="utf-8")
    bad = env.root / "ESLifier_Data" / "b.json"
    bad.write_text("{nope", encoding="utf-8")
    assert w.get_from_file(str(good)) == {"a": 1}
    assert w.get_from_file(str(bad)) == {} and w.get_from_file("missing.json") == {}


def test_worker_dump_dictionary_merges_into_existing_data(env):
    w = make_patch_worker([], {}, {})
    path = data(env, "d.json", {"keep": 1, "replace": "old"})
    w.dump_dictionary(str(path), {"replace": "new", "add": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"keep": 1, "replace": "new", "add": 2}


def test_worker_dump_dictionary_failure_is_logged(env, log):
    w = make_patch_worker([], {}, {})
    w.dump_dictionary(str(env.root / "no_such_dir" / "d.json"), {"a": 1})
    assert any("Failed to dump data to" in e for e in log.errors)


# ------------------------------------------------------------------------------------------ patch_new (UI glue)
@pytest.fixture
def ui(env, boxes, monkeypatch):
    p = pn.patch_new()
    p.main_parent = FakeParent()
    p.mod_manager_mode = 0
    p.file_conflict_num = 0
    p.hash_mismatch_num = 0
    return p


def write_data_files(env, *names):
    for d in ("ESLifier_Data", "ESLifier_data"):                     # the code checks both spellings of the folder
        os.makedirs(env.root / d, exist_ok=True)
        for name in names:
            (env.root / d / name).write_text("{}", encoding="utf-8")


def test_scan_and_find_warns_when_nothing_has_been_compacted(env, boxes, logcalls):
    p = pn.patch_new()
    parent = FakeParent()
    p.scan_and_find(parent)
    box, = boxes.instances
    assert "No Compacted/Patched Mods" in box.title and box.shown
    assert parent.events == [("setEnabled", True)]
    assert logcalls == ["close"]
    assert not hasattr(p, "scanner_worker")                          # no scan was started


def test_scan_and_find_warns_when_the_output_predates_master_byte_data(env, boxes, logcalls):
    write_data_files(env, "compacted_and_patched.json")
    p = pn.patch_new()
    parent = FakeParent()
    p.scan_and_find(parent)
    box, = boxes.instances
    assert "outdated build" in box.title and "v0.12.0" in box.text
    assert parent.events == [("setEnabled", True)]
    assert not hasattr(p, "scanner_worker")


def test_scan_and_find_starts_the_scan_when_the_output_is_usable(env, boxes, logcalls):
    write_data_files(env, "compacted_and_patched.json", "master_byte_data.json")
    p = pn.patch_new()
    parent = FakeParent()
    _global.update_header = False
    _global.generate_cell_master = True
    p.scan_and_find(parent)
    assert boxes.instances == []
    assert p.main_parent is parent
    assert p.update_header is False and p.generate_cell_master is True
    assert hasattr(p, "scanner_worker") and hasattr(p, "patch_new_scan_thread")


def test_esl_flagged_data_alone_is_enough_to_start(env, boxes, logcalls):
    write_data_files(env, "esl_flagged.json", "master_byte_data.json")
    p = pn.patch_new()
    p.scan_and_find(FakeParent())
    assert boxes.instances == [] and hasattr(p, "scanner_worker")


def test_completed_scan_warns_about_skse_dlls_referencing_compacted_mods(ui, boxes, monkeypatch):
    monkeypatch.setattr(ui, "patch_new_plugins_and_files", lambda: None)
    ui.completed_scan(["ModA.esp"], {}, {}, 0, 0, [("moda.esp", ["a.dll", "b.dll"])])
    (title, text), = boxes.warnings
    assert "SKSE dll" in title
    assert "Mod: moda.esp" in text and "a.dll" in text and "b.dll" in text


def test_completed_scan_checks_new_cells_before_patching(ui, monkeypatch):
    calls = []
    monkeypatch.setattr(pn.cell_scanner, "scan_new_dependents", lambda mods, deps: calls.append((mods, deps)))
    monkeypatch.setattr(ui, "patch_new_plugins_and_files", lambda: calls.append("patch"))
    ui.completed_scan(["ModA.esp"], {"ModA.esp": ["dep"]}, {}, 3, 2, [])
    assert calls == [(["ModA.esp"], {"ModA.esp": ["dep"]}), "patch"]
    assert (ui.hash_mismatch_num, ui.file_conflict_num) == (3, 2)


def test_completed_scan_skips_cell_check_without_new_dependents(ui, monkeypatch):
    calls = []
    monkeypatch.setattr(pn.cell_scanner, "scan_new_dependents", lambda *a: calls.append("cells"))
    monkeypatch.setattr(ui, "patch_new_plugins_and_files", lambda: calls.append("patch"))
    ui.completed_scan(["ModA.esp"], {}, {"ModA.esp": ["f"]}, 0, 0, [])
    assert calls == ["patch"]


def test_completed_scan_with_nothing_to_patch_finishes_immediately(ui, boxes, logcalls, monkeypatch):
    monkeypatch.setattr(ui, "patch_new_plugins_and_files", lambda: pytest.fail("nothing to patch"))
    ui.completed_scan([], {}, {}, 0, 0, [])
    assert logcalls == ["close"]
    assert boxes.instances[-1].title == "Patch New Done"
    assert ("setEnabled", True) in ui.main_parent.events


def test_finished_patching_reports_and_reenables_the_window(ui, logcalls, monkeypatch, log):
    shown = []
    monkeypatch.setattr(ui, "create_completion_message", lambda n: shown.append(n))
    ui.finished_patching(7)
    assert shown == [7] and logcalls == ["close"]
    assert ("setEnabled", True) in ui.main_parent.events
    assert any("Finished Patching" in line for line in log.normal)


@pytest.mark.parametrize("new_files,mode,hash_n,conflict_n,expected", [
    (3, 0, 0, 0, ["3 new files that needed patching have been patched.",
                  "No files with a hash mismatched were found."]),
    (0, 0, 0, 0, ["No new files that need patching have been found.",
                  "No files with a hash mismatched were found."]),
    (0, 0, 2, 0, ["No new files that need patching have been found.",
                  "2 files had hash mismatches and were corrected."]),
    (0, 2, 0, 0, ["No files with a winning conflict change were found."]),
    (0, 2, 0, 4, ["(or they were patched due to a conflict change)",
                  "4 files had winning conflicts change and were corrected."]),
    (5, 1, 1, 1, ["5 new files that needed patching have been patched.",
                  "1 files had hash mismatches and were corrected.",
                  "1 files had winning conflicts change and were corrected."]),
])
def test_completion_message_text(ui, boxes, new_files, mode, hash_n, conflict_n, expected):
    ui.mod_manager_mode, ui.hash_mismatch_num, ui.file_conflict_num = mode, hash_n, conflict_n
    ui.create_completion_message(new_files)
    box = boxes.instances[-1]
    assert box.title == "Patch New Done" and box.shown
    for line in expected:
        assert line in box.text
    assert ("calculate_stats",) in ui.main_parent.events


def test_completion_message_hides_conflict_lines_in_manual_mode(ui, boxes):
    ui.mod_manager_mode, ui.file_conflict_num = 0, 9
    ui.create_completion_message(0)
    text = boxes.instances[-1].text
    assert "winning conflict" not in text and "conflict change" not in text


def test_completion_message_ok_button_closes_it(ui, boxes):
    ui.create_completion_message(1)
    box = boxes.instances[-1]
    assert box.buttons == ["ok"] and box.accepted.callbacks == [box.hide]


def test_delete_confirmation_accept_deletes_the_files(ui, boxes):
    ui.scanner_worker = types.SimpleNamespace(delete_files=lambda *a: ui.main_parent.events.append(("delete", a)))
    ui.create_delete_message("Really?", ["f1", "f2"], {"h": 1}, True, {"c": []})
    box = boxes.instances[-1]
    assert box.title == "Delete 2 files?" and box.text == "Really?" and box.shown
    assert box.buttons == ["abort", "ok"]
    box.accepted.callbacks[0]()
    assert box.hidden
    assert ui.main_parent.events == [("delete", (["f1", "f2"], {"h": 1}, True, {"c": []}))]


def test_delete_confirmation_reject_aborts_patch_new(ui, boxes, logcalls, log):
    quits = []
    ui.patch_new_scan_thread = types.SimpleNamespace(quit=lambda: quits.append(1))
    ui.scanner_worker = types.SimpleNamespace(delete_files=lambda *a: pytest.fail("must not delete"))
    ui.create_delete_message("Really?", ["f1"], {}, False, {})
    box = boxes.instances[-1]
    box.rejected.callbacks[0]()
    assert box.hidden and quits == [1]
    assert ui.main_parent.events == [("setEnabled", True), ("calculate_stats",)]
    assert logcalls == ["close"]
    assert any("User canceled Patch New file deletion" in line for line in log.normal)


def test_finished_rebuilding_looks_for_new_files(ui):
    called = []
    ui.scanner_worker = types.SimpleNamespace(detect_new_files=lambda: called.append(1))
    ui.finished_rebuilding()
    assert called == [1]
