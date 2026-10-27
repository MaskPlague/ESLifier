"""
compact_form_ids.CFIDs: everything around the plugin rewrite itself: copying into the output folder, hashing,
sorting/renaming/patching dependent files, the threaders, and the compact_and_patch / patch_new orchestration.
"""
import hashlib
import json
import os

import pytest

import compact_form_ids as cfi
from compact_form_ids import CFIDs
from plugin_builder import fid, write
from test_compact_form_ids import build_source_plugin, env, make_cfids, SKYRIM  # noqa: F401  (env is a fixture)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


# ------------------------------------------------------------------------------------------ sort_files_to_patch_or_rename
class TestSortFiles:
    MASTER = "/data/My Mod.esp"      # a POSIX path: os.path.basename must work on the test platform

    def sort(self, env, files, experimental=False):
        cf = make_cfids(env)
        cf.all_patcher_experimental = experimental
        return cf.sort_files_to_patch_or_rename(self.MASTER, files)

    @pytest.mark.parametrize("name", [
        "C:\\Data\\scripts\\thing.pex", "C:\\Data\\skse\\plugins\\a.ini", "C:\\Data\\skse\\plugins\\a.json",
        "C:\\Data\\skse\\plugins\\a.toml", "C:\\Data\\x\\foo_conditions.txt", "C:\\Data\\x\\a.jslot", "C:\\Data\\x\\a.yaml",
        "C:\\Data\\x\\a.yml", "C:\\Data\\Seq\\my mod.seq", "C:\\Data\\NetScriptFramework\\Plugins\\CustomSkill\\x.txt",
        "C:\\DATA\\SCRIPTS\\THING.PEX",
    ])
    def test_files_that_are_edited_in_place(self, env, name):
        assert self.sort(env, [name]) == ([name], [])

    @pytest.mark.parametrize("name", [
        "C:\\Data\\meshes\\actors\\character\\facegendata\\facegeom\\My Mod.esp\\00012345.nif",
        "C:\\Data\\textures\\actors\\character\\facegendata\\facetint\\My Mod.esp\\00012345.dds",
        "C:\\Data\\sound\\voice\\My Mod.esp\\npc\\x_00012345_1.fuz",
        "C:\\DATA\\SOUND\\VOICE\\MY MOD.ESP\\NPC\\X_00012345_1.FUZ",
    ])
    def test_facegen_and_voice_files_are_renamed(self, env, name):
        assert self.sort(env, [name]) == ([], [name])

    def test_seq_files_of_other_plugins_are_not_accepted(self, env):
        with pytest.raises(TypeError):
            self.sort(env, ["C:\\Data\\Seq\\other.seq"])

    def test_luma_json_is_renamed_for_the_plugin_and_patched_otherwise(self, env):
        mine = "C:\\Data\\skse\\Luma\\My Mod.esp\\00012345.json"
        other = "C:\\Data\\skse\\Luma\\Other.esp\\00012345.json"
        assert self.sort(env, [mine, other]) == ([other], [mine])

    def test_unknown_files_raise_unless_the_experimental_patcher_is_on(self, env):
        with pytest.raises(TypeError):
            self.sort(env, ["C:\\Data\\x\\mystery.bin"])
        assert self.sort(env, ["C:\\Data\\x\\mystery.bin"], experimental=True) == (["C:\\Data\\x\\mystery.bin"], [])

    def test_mixed_list_keeps_each_files_group(self, env):
        a, b, c = "C:\\d\\a.pex", "C:\\d\\facegeom\\My Mod.esp\\00000001.nif", "C:\\d\\b.ini"
        assert self.sort(env, [a, b, c]) == ([a, c], [b])


# ------------------------------------------------------------------------------------------ try_replace_rename
class TestTryReplaceRename:
    def test_renames_over_an_existing_file(self, env):
        a, b = env.root / "a.txt", env.root / "b.txt"
        a.write_text("new")
        b.write_text("old")
        make_cfids(env).try_replace_rename(str(a), str(b))
        assert b.read_text() == "new" and not a.exists()

    def test_retries_while_the_file_is_locked(self, env, monkeypatch):
        calls = []

        def flaky(src, dst):
            calls.append(1)
            if len(calls) < 4:
                raise PermissionError("locked")

        monkeypatch.setattr(cfi.os, "replace", flaky)
        monkeypatch.setattr(cfi.time, "sleep", lambda s: None)
        make_cfids(env).try_replace_rename("a", "b")
        assert len(calls) == 4

    def test_gives_up_after_fifteen_attempts(self, env, monkeypatch):
        calls = []
        monkeypatch.setattr(cfi.os, "replace", lambda s, d: calls.append(1) or (_ for _ in ()).throw(OSError("busy")))
        monkeypatch.setattr(cfi.time, "sleep", lambda s: None)
        with pytest.raises(OSError):
            make_cfids(env).try_replace_rename("a", "b")
        assert len(calls) == 15


# ------------------------------------------------------------------------------------------ copy_file_to_output / set_flag
class TestCopyToOutput:
    def test_copies_to_the_same_relative_path_and_records_the_original(self, env):
        src = put(env.data / "meshes" / "a.nif", b"mesh")
        cf = make_cfids(env)
        new_file, rel = cf.copy_file_to_output(src)
        assert os.path.normpath(new_file) == str(env.out / "meshes" / "a.nif")
        assert rel == os.path.join("meshes", "a.nif")
        assert (env.out / "meshes" / "a.nif").read_bytes() == b"mesh"
        assert cf.original_files[rel.lower()] == [src, sha(b"mesh")]

    def test_existing_output_is_not_overwritten(self, env):
        src = put(env.data / "a.ini", b"original")
        put(env.out / "a.ini", b"already patched")
        make_cfids(env).copy_file_to_output(src)
        assert (env.out / "a.ini").read_bytes() == b"already patched"

    def test_records_the_overridden_winner_in_the_history(self, env):
        src = put(env.data / "a.ini", b"x")
        cf = make_cfids(env)
        cf.winning_files_dict = {"a.ini": ("SomeMod", "x")}
        cf.copy_file_to_output(src)
        assert cf.winning_file_history_dict == {"a.ini": "SomeMod"}

    def test_the_output_folder_itself_as_winner_is_not_recorded(self, env):
        src = put(env.data / "a.ini", b"x")
        cf = make_cfids(env)
        cf.winning_files_dict = {"a.ini": (cf.output_folder_name, "x")}
        cf.copy_file_to_output(src)
        assert cf.winning_file_history_dict == {}

    def test_original_is_not_rehashed_when_already_recorded_for_the_same_file(self, env):
        src = put(env.data / "a.ini", b"x")
        cf = make_cfids(env)
        cf.original_files = {"a.ini": [src, "recorded-hash"]}
        cf.copy_file_to_output(src)
        assert cf.original_files["a.ini"] == [src, "recorded-hash"]

    def test_a_different_source_replaces_the_record(self, env):
        src = put(env.data / "a.ini", b"x")
        cf = make_cfids(env)
        cf.original_files = {"a.ini": ["/elsewhere/a.ini", "old"]}
        cf.copy_file_to_output(src)
        assert cf.original_files["a.ini"] == [src, sha(b"x")]

    def test_files_from_the_output_folder_or_bsa_extraction_are_not_recorded_as_originals(self, env):
        cf = make_cfids(env)
        in_output = put(env.out / "b.ini", b"x")
        cf.copy_file_to_output(in_output)
        extracted = put(env.root / "bsa_extracted" / "c.ini", b"x")
        env.g.archive_extracted_path_len = len(str(env.root / "bsa_extracted"))
        cf.copy_file_to_output(extracted)
        assert cf.original_files == {}


class TestSetFlag:
    def test_sets_the_flag_byte_in_the_output_copy_only(self, env):
        data = bytearray(build_source_plugin())
        src = write(env.data / "mod.esp", bytes(data))
        cf = make_cfids(env)
        originals, history = cf.set_flag(src)
        assert (env.out / "mod.esp").read_bytes()[9] & 0x02
        assert os.path.exists(src) and open(src, "rb").read() == bytes(data)
        assert originals is cf.original_files and history is cf.winning_file_history_dict

    def test_failure_to_write_is_logged(self, env, monkeypatch, log):
        cf = make_cfids(env)
        monkeypatch.setattr(cf, "copy_file_to_output", lambda f: (str(env.out / "missing" / "x.esp"), "x.esp"))
        cf.set_flag("whatever.esp")
        assert log.errors


# ------------------------------------------------------------------------------------------ hashing
class TestHashing:
    @pytest.fixture
    def hashing(self, env, monkeypatch):
        """Output folder with lower-case paths (the hasher lower-cases them) and the json lists it reads."""
        out = env.root / "out" / "eslifier output"
        out.mkdir(parents=True)
        cf = make_cfids(env)
        cf.output_folder = str(out)
        monkeypatch.setattr(cfi, "MAX_THREADS", 2)
        return cf, out

    def data_file(self, env, name, obj):
        (env.root / "ESLifier_Data" / name).write_text(json.dumps(obj), encoding="utf-8")

    def hashes(self, env):
        return json.loads((env.root / "ESLifier_Data" / "new_file_hashes.json").read_text())

    def test_hashes_compacted_plugins_their_patched_files_and_flagged_plugins(self, env, hashing):
        cf, out = hashing
        put(out / "a.esp", b"A")
        put(out / "scripts" / "a.pex", b"PEX")
        put(out / "flagged.esp", b"F")
        self.data_file(env, "compacted_and_patched.json", {"A.esp": ["Scripts\\a.pex".replace("\\", os.sep), "gone.ini"]})
        self.data_file(env, "esl_flagged.json", ["Flagged.esp", "Missing.esp"])
        cf.hash_output_files(set())
        assert self.hashes(env) == {"a.esp": [sha(b"A"), False],
                                    os.path.join("scripts", "a.pex"): [sha(b"PEX"), False],
                                    "flagged.esp": [sha(b"F"), False]}

    def test_nothing_to_hash_writes_nothing(self, env, hashing):
        cf, out = hashing
        self.data_file(env, "compacted_and_patched.json", {"A.esp": []})
        cf.hash_output_files(set())
        assert not (env.root / "ESLifier_Data" / "new_file_hashes.json").exists()

    def test_files_to_not_hash_are_skipped(self, env, hashing):
        cf, out = hashing
        a = put(out / "a.esp", b"A")
        put(out / "b.esp", b"B")
        self.data_file(env, "compacted_and_patched.json", {"a.esp": [], "b.esp": []})
        cf.hash_output_files({os.path.normpath(a).lower()})   # the app stores lower-cased paths
        assert list(self.hashes(env)) == ["b.esp"]

    def test_after_patching_hashes_keep_their_changed_flag(self, env, hashing):
        cf, out = hashing
        put(out / "a.esp", b"A")
        self.data_file(env, "compacted_and_patched.json", {"a.esp": []})
        self.data_file(env, "new_file_hashes.json", {"a.esp": ["old", True]})
        cf.hash_output_files(set(), before_patching=False)
        assert self.hashes(env)["a.esp"] == [sha(b"A"), True]

    def test_before_patching_a_different_hash_marks_the_file_as_changed(self, env, hashing):
        cf, out = hashing
        put(out / "a.esp", b"A")
        put(out / "b.esp", b"B")
        put(out / "c.esp", b"C")
        self.data_file(env, "compacted_and_patched.json", {"a.esp": [], "b.esp": [], "c.esp": []})
        self.data_file(env, "new_file_hashes.json", {"a.esp": ["stale", False], "b.esp": [sha(b"B"), False]})
        cf.hash_output_files(set(), before_patching=True)
        h = self.hashes(env)
        assert h["a.esp"] == [sha(b"A"), True]          # content differs from the stored hash
        assert h["b.esp"] == [sha(b"B"), False]         # unchanged
        assert h["c.esp"] == [sha(b"C"), False]         # new file: nothing to compare against

    def test_many_files_are_split_across_the_worker_threads(self, env, hashing):
        cf, out = hashing
        names = [f"f{i}.esp" for i in range(7)]
        for n in names:
            put(out / n, n.encode())
        self.data_file(env, "compacted_and_patched.json", {n: [] for n in names})
        cf.hash_output_files(set())
        assert self.hashes(env) == {n: [sha(n.encode()), False] for n in names}

    def test_unreadable_files_are_logged_and_skipped(self, env, hashing, log):
        cf, out = hashing
        put(out / "a.esp", b"A")
        put(out / "b.esp", b"B")
        self.data_file(env, "compacted_and_patched.json", {"a.esp": [], "b.esp": []})
        real_open = open

        def flaky_open(path, *a, **k):
            if str(path).endswith("a.esp") and "rb" in a:
                raise PermissionError("denied")
            return real_open(path, *a, **k)

        import builtins
        orig = builtins.open
        builtins.open = flaky_open
        try:
            cf.hash_output_files(set())
        finally:
            builtins.open = orig
        assert list(self.hashes(env)) == ["b.esp"]
        assert any("Failed to hash file" in e for e in log.errors)


# ------------------------------------------------------------------------------------------ rename_files
class TestRenameFiles:
    @pytest.fixture
    def cf(self, env):
        cf = make_cfids(env)
        cf.form_id_map = {"012345": "000001", "0abcde": "000abc"}
        cf.compacted_and_patched = {"mod.esp": set()}
        cf.master_byte, cf.updated_master_index = b"\x01", 0
        cf.patched = []
        cf.patch_files = lambda master, files: cf.patched.append((master, list(files)))
        return cf

    def run(self, cf, files):
        cf.file_count, cf.count = len(files), 0
        cf.rename_files("mod.esp", files)

    def test_facegeom_mesh_is_renamed_to_the_new_id_and_then_patched(self, env, cf):
        src = put(env.data / "meshes/actors/character/facegendata/facegeom/mod.esp/00012345.nif", b"mesh")
        self.run(cf, [src])
        out_dir = env.out / "meshes/actors/character/facegendata/facegeom/mod.esp"
        assert (out_dir / "00000001.nif").read_bytes() == b"mesh"
        assert not (out_dir / "00012345.nif").exists()                  # the copy was moved, not duplicated
        assert os.path.exists(src)                                      # the source is untouched
        assert cf.patched == [("mod.esp", [str(out_dir / "00000001.nif")])]
        rels = cf.compacted_and_patched["mod.esp"]
        assert {r.replace(os.sep, "/") for r in rels} == {
            "meshes/actors/character/facegendata/facegeom/mod.esp/00012345.nif",
            "meshes/actors/character/facegendata/facegeom/mod.esp/00000001.nif"}

    def test_facetint_texture_is_renamed_but_not_patched(self, env, cf):
        src = put(env.data / "textures/actors/character/facegendata/facetint/mod.esp/000abcde.dds", b"dds")
        self.run(cf, [src])
        assert (env.out / "textures/actors/character/facegendata/facetint/mod.esp/00000ABC.dds").exists()
        assert cf.patched == []

    def test_voice_file_is_renamed_keeping_the_rest_of_its_name(self, env, cf):
        src = put(env.data / "sound/voice/mod.esp/femalenord/modquest_greeting_00012345_1.fuz", b"fuz")
        self.run(cf, [src])
        out_dir = env.out / "sound/voice/mod.esp/femalenord"
        assert (out_dir / "modquest_greeting_00000001_1.fuz").read_bytes() == b"fuz"
        assert not (out_dir / "modquest_greeting_00012345_1.fuz").exists()

    def test_files_whose_id_was_not_compacted_are_registered_but_left_alone(self, env, cf):
        src = put(env.data / "meshes/actors/character/facegendata/facegeom/mod.esp/00ffffff.nif")
        self.run(cf, [src])
        assert not (env.out / "meshes").exists()
        assert cf.patched == []
        assert len(cf.compacted_and_patched["mod.esp"]) == 1

    def test_luma_json_is_renamed_then_patched(self, env, cf):
        flat = str(env.data) + os.sep + "skse\\Luma\\mod.esp\\012345.json"
        put(__import__("pathlib").Path(flat), b"{}")
        self.run(cf, [flat])
        renamed = env.out / "skse" / "Luma" / "mod.esp" / "000001.json"
        assert renamed.read_bytes() == b"{}"
        assert cf.patched == [("mod.esp", [str(renamed)])]

    def test_luma_json_with_an_unchanged_id_is_still_patched(self, env, cf):
        flat = str(env.data) + os.sep + "skse\\Luma\\mod.esp\\ffffff.json"
        put(__import__("pathlib").Path(flat), b"{}")
        self.run(cf, [flat])
        assert cf.patched == [("mod.esp", [flat])]                      # patched from its original location

    def test_progress_is_reported_for_long_lists(self, env, cf, log):
        files = [put(env.data / f"meshes/facegendata/facegeom/mod.esp/00ff{i:04x}.nif") for i in range(25)]
        self.run(cf, files)
        assert cf.count == 25


# ------------------------------------------------------------------------------------------ threaders
class TestThreaders:
    @pytest.fixture
    def cf(self, env, monkeypatch):
        monkeypatch.setattr(cfi, "MAX_THREADS", 3)
        cf = make_cfids(env)
        cf.calls = []
        return cf

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 7, 10])
    def test_patch_files_threader_hands_every_file_to_a_worker_exactly_once(self, cf, n):
        cf.patch_files = lambda master, chunk: cf.calls.append(list(chunk))
        files = [f"f{i}" for i in range(n)]
        cf.patch_files_threader("mod.esp", files)
        assert sorted(f for chunk in cf.calls for f in chunk) == sorted(files)
        assert cf.file_count == n

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 7, 10])
    def test_rename_files_threader_hands_every_file_to_a_worker_exactly_once(self, cf, n):
        cf.rename_files = lambda master, chunk: cf.calls.append(list(chunk))
        files = [f"f{i}" for i in range(n)]
        cf.rename_files_threader("mod.esp", files)
        assert sorted(f for chunk in cf.calls for f in chunk) == sorted(files)
        assert cf.file_count == n

    def test_worker_count_is_capped(self, cf):
        cf.patch_files = lambda master, chunk: cf.calls.append(list(chunk))
        cf.patch_files_threader("mod.esp", [f"f{i}" for i in range(30)])
        assert len([c for c in cf.calls if c]) <= 3 + 1


# ------------------------------------------------------------------------------------------ patch_files
class TestPatchFiles:
    @pytest.fixture
    def cf(self, env, monkeypatch):
        cf = make_cfids(env)
        cf.master_byte, cf.updated_master_index = b"\x01", 0
        cf.form_id_map = {}
        cf.compacted_and_patched = {"Mod.esp": set()}
        cf.calls = []
        return cf

    def patcher(self, monkeypatch, cf, fail=None):
        def fake(new_file_lower, new_file, basename, form_id_map, master_byte, updated_master_index, update_byte,
                 additional, encoding):
            cf.calls.append((new_file_lower, new_file, basename, encoding))
            if fail and fail.get(encoding):
                raise fail[encoding]

        monkeypatch.setattr(cfi.patcher_conditions, "patch_file_conditions", fake)

    def test_each_file_is_copied_to_the_output_and_patched_there(self, env, cf, monkeypatch):
        self.patcher(monkeypatch, cf)
        src = put(env.data / "Scripts" / "Thing.pex", b"pex")
        cf.patch_files("Mod.esp", [src])
        new_file = str(env.out / "Scripts" / "Thing.pex")
        assert cf.calls == [(new_file.lower(), new_file, "mod.esp", "utf-8")]
        assert (env.out / "Scripts" / "Thing.pex").read_bytes() == b"pex"
        assert cf.compacted_and_patched["Mod.esp"] == {os.path.join("Scripts", "Thing.pex")}

    def test_undecodable_files_are_retried_as_ansi(self, env, cf, monkeypatch):
        self.patcher(monkeypatch, cf, fail={"utf-8": UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")})
        src = put(env.data / "a.ini", b"\xff")
        cf.patch_files("Mod.esp", [src])
        assert [c[3] for c in cf.calls] == ["utf-8", "cp1252"]
        assert "a.ini" in cf.compacted_and_patched["Mod.esp"]

    def test_failures_are_logged_and_the_file_is_still_registered(self, env, cf, monkeypatch, log):
        self.patcher(monkeypatch, cf, fail={"utf-8": ValueError("boom")})
        src = put(env.data / "a.ini")
        cf.patch_files("Mod.esp", [src])
        assert any("Failed to patch file" in e for e in log.errors)
        assert "a.ini" in cf.compacted_and_patched["Mod.esp"]

    def test_all_files_in_the_chunk_are_handled_even_after_a_failure(self, env, cf, monkeypatch):
        self.patcher(monkeypatch, cf, fail={"utf-8": ValueError("boom")})
        cf.patch_files("Mod.esp", [put(env.data / "a.ini"), put(env.data / "b.ini")])
        assert len(cf.calls) == 2
        assert cf.compacted_and_patched["Mod.esp"] == {"a.ini", "b.ini"}


# ------------------------------------------------------------------------------------------ patch_dependent_plugins
class TestPatchSeveralDependents:
    def test_every_dependent_is_patched_and_registered(self, env):
        from plugin_builder import grup, plugin, record, sub
        cf = make_cfids(env)
        master_src = write(env.data / "master.esp", build_source_plugin())
        cf.compact_file(master_src, True)
        deps = []
        for name in ("dep1.esp", "dep2.esp", "dep3.esp"):
            refr = record(b"REFR", fid(2, 0x800), sub(b"NAME", fid(1, 0x3000)))
            deps.append(write(env.data / name, plugin((SKYRIM, "master.esp"), grup(b"REFR", refr))))
        cf.patch_dependent_plugins(master_src, deps, {})
        for name in ("dep1.esp", "dep2.esp", "dep3.esp"):
            assert (env.out / name).exists()
            assert name in cf.compacted_and_patched["master.esp"]

    def test_no_dependents_is_a_noop(self, env):
        cf = make_cfids(env)
        master_src = write(env.data / "master.esp", build_source_plugin())
        cf.compact_file(master_src, True)
        cf.patch_dependent_plugins(master_src, [], {})
        assert not (env.out / "dep1.esp").exists()


# ------------------------------------------------------------------------------------------ compact_and_patch / patch_new
def make_dependent(env, name="dep.esp"):
    from plugin_builder import grup, plugin, record, sub
    refr = record(b"REFR", fid(2, 0x800), sub(b"NAME", fid(1, 0x3000)))
    return write(env.data / name, plugin((SKYRIM, "master.esp"), grup(b"REFR", refr)))


class TestCompactAndPatch:
    @pytest.fixture
    def cf(self, env):
        cf = make_cfids(env)
        cf.all_patcher_experimental = False
        cf.routed = {"patch": [], "rename": []}
        cf.patch_files_threader = lambda master, files: cf.routed["patch"].extend(files)
        cf.rename_files_threader = lambda master, files: cf.routed["rename"].extend(files)
        return cf

    def test_compacts_the_plugin_and_patches_dependents(self, env, cf):
        master = write(env.data / "master.esp", build_source_plugin())
        dep = make_dependent(env)
        result = cf.compact_and_patch(master, [dep], True, False, {})
        assert (env.out / "master.esp").read_bytes()[9] & 0x02
        assert (env.out / "dep.esp").exists()
        assert "dep.esp" in cf.compacted_and_patched["master.esp"]
        assert result == (cf.original_files, cf.winning_files_dict, cf.master_byte_data,
                          cf.winning_file_history_dict, cf.compacted_and_patched)
        assert cf.form_id_map and cf.do_generate_cell_master is False

    def test_dependent_files_are_split_into_patched_and_renamed(self, env, cf):
        master = write(env.data / "master.esp", build_source_plugin())
        pex = put(env.data / "scripts" / "a.pex")
        face = put(env.data / "meshes/actors/character/facegendata/facegeom/master.esp/00012345.nif")
        cf.compact_and_patch(master, [], True, False, {"master.esp": [pex, face]})
        assert cf.routed == {"patch": [pex], "rename": [face]}

    def test_files_of_other_plugins_are_ignored(self, env, cf):
        master = write(env.data / "master.esp", build_source_plugin())
        cf.compact_and_patch(master, [], True, False, {"other.esp": [put(env.data / "a.pex")]})
        assert cf.routed == {"patch": [], "rename": []}

    def test_cell_master_flag_is_stored_for_the_patchers(self, env, cf):
        master = write(env.data / "master.esp", build_source_plugin())
        cf.compact_and_patch(master, [], True, True, {})
        assert cf.do_generate_cell_master is True

    def test_bsa_facegen_and_voice_files_are_extracted_temporarily_and_routed(self, env, cf, monkeypatch):
        import subprocess
        monkeypatch.setattr(subprocess, "STARTUPINFO", lambda: type("SI", (), {"dwFlags": 0})(), raising=False)
        monkeypatch.setattr(subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
        temp = env.root / "bsa_extracted_temp"
        env.g.archive_extracted_temp_path_len = len(str(temp))
        master = write(env.data / "master.esp", build_source_plugin())
        cf.bsa_masters = {"master.esp"}
        cf.archive_dict = cf.bsa_dict = {"/bsa/Master - Textures.bsa": ["master.esp"], "/bsa/Master.bsa": ["master.esp"],
                                         "/bsa/Other.bsa": ["other.esp"]}   # attribute was renamed bsa_dict -> archive_dict
        extracted = []

        def fake_extract(bsa, part, name, startupinfo):
            extracted.append((os.path.basename(bsa), part, name))      # one bsarch call per archive; it applies the facetint/facegeom/voice filters itself
            put(temp / "textures/actors/character/facegendata/facetint/master.esp/00012345.dds")
            put(temp / "sound/voice/master.esp/npc/x_00012345_1.fuz")
            put(temp / "sound/voice/master.esp/npc/notes.txt")        # not a game asset: ignored

        cf.bsa_temp_extract = fake_extract
        existing = put(env.data / "scripts" / "a.pex")
        cf.compact_and_patch(master, [], True, False, {"master.esp": [existing]})
        assert sorted(extracted) == [("Master - Textures.bsa", "tempSSE|", "master.esp"),
                                      ("Master.bsa", "tempSSE|", "master.esp")]
        assert cf.routed["patch"] == [existing]
        names = sorted(os.path.basename(f) for f in cf.routed["rename"])
        assert names == ["00012345.dds", "x_00012345_1.fuz"]
        assert not temp.exists() and not os.path.exists("bsa_extracted_temp")      # temporary extraction cleaned up

    def test_a_stale_temp_extraction_folder_is_cleared_first(self, env, cf, monkeypatch):
        import subprocess
        monkeypatch.setattr(subprocess, "STARTUPINFO", lambda: type("SI", (), {"dwFlags": 0})(), raising=False)
        monkeypatch.setattr(subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
        stale = put(env.root / "bsa_extracted_temp" / "textures" / "old.dds")
        env.g.archive_extracted_temp_path_len = len(str(env.root / "bsa_extracted_temp"))
        master = write(env.data / "master.esp", build_source_plugin())
        cf.bsa_masters = {"master.esp"}
        cf.bsa_dict = {}
        cf.compact_and_patch(master, [], True, False, {})
        assert cf.routed == {"patch": [], "rename": []}
        assert not os.path.exists(stale)


class TestPatchNew:
    @pytest.fixture
    def setup(self, env):
        cf = make_cfids(env)
        master = write(env.data / "master.esp", build_source_plugin())
        cf.compact_file(master, True)
        dep = make_dependent(env)
        cf2 = make_cfids(env)
        cf2.master_byte_data = cf.master_byte_data
        cf2.all_patcher_experimental = False
        cf2.routed = {"patch": [], "rename": []}
        cf2.patch_files_threader = lambda m, files: cf2.routed["patch"].extend(files)
        cf2.rename_files_threader = lambda m, files: cf2.routed["rename"].extend(files)
        return cf2, "master.esp", dep

    def test_patches_new_dependent_plugins_with_the_saved_master_data(self, env, setup):
        cf2, master, dep = setup
        saved = cf2.master_byte_data["master.esp"]["master_byte"]
        result = cf2.patch_new(master, [dep], {})
        assert "dep.esp" in cf2.compacted_and_patched["master.esp"]
        assert (env.out / "dep.esp").exists()
        assert cf2.master_byte == bytes.fromhex(saved)
        assert result == (cf2.original_files, cf2.winning_files_dict, cf2.master_byte_data,
                          cf2.winning_file_history_dict, cf2.compacted_and_patched)

    def test_previously_patched_files_for_the_master_are_forgotten(self, env, setup):
        cf2, master, dep = setup
        cf2.compacted_and_patched["master.esp"] = {"stale.pex"}
        cf2.patch_new(master, [], {})
        assert cf2.compacted_and_patched["master.esp"] == set()

    def test_new_dependent_files_are_sorted_and_routed(self, env, setup):
        cf2, master, dep = setup
        pex = put(env.data / "scripts" / "new.pex")
        face = put(env.data / "meshes/actors/character/facegendata/facegeom/master.esp/00012345.nif")
        cf2.patch_new(master, [], {"master.esp": [pex, face]})
        assert cf2.routed == {"patch": [pex], "rename": [face]}
        assert cf2.form_id_map                                         # the saved form id map was reloaded

    def test_files_of_other_plugins_are_not_touched(self, env, setup):
        cf2, master, dep = setup
        cf2.patch_new(master, [], {"other.esp": [put(env.data / "scripts" / "x.pex")]})
        assert cf2.routed == {"patch": [], "rename": []}

    def test_cell_master_setting_is_taken_from_the_global_settings(self, env, setup):
        cf2, master, dep = setup
        env.g._settings["generate_cell_master"] = True
        env.g.update_from_settings()
        cf2.patch_new(master, [], {})
        assert cf2.do_generate_cell_master is True
