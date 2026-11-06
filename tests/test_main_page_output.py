"""
main_page output management: reset, rebuild, delete_output, output statistics and the "changed files" dialog that
follows hashing the output. Everything runs against real files in a temp directory.
"""
import json
import os

import pytest

import main.main_page as main_page
from data_holder import (COMPACTED_AND_PATCHED_JSON, ESL_FLAGGED_JSON, PREVIOUSLY_COMPACTED_JSON,
                         PREVIOUSLY_ESL_FLAGGED_JSON, NEW_FILE_HASHES_JSON, ORIGINAL_FILES_JSON, MASTER_BYTE_DATA_JSON,
                         WINNING_FILE_HISTORY_DICT_JSON, WINNING_FILES_DICT_JSON, FORM_ID_MAPS_FOLDER, CELL_IDS_FOLDER,
                         CELL_MASTER_INFO_JSON)
from main_page_fakes import make_page, UI, FakeMessageBox, Calls


@pytest.fixture
def page(workdir, monkeypatch):
    page = make_page(workdir, monkeypatch)
    os.makedirs(page.output_folder_full)
    return page


def put(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_output(page, files):
    """files: {relative path: bytes}. Returns the full paths."""
    paths = []
    for rel, data in files.items():
        full = os.path.join(page.output_folder_full, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        paths.append(full)
    return paths


# -------------------------------------------------------------------------------------------- listing / stats
class TestOutputWalk:
    def test_lists_every_file_with_its_size(self, page):
        write_output(page, {"a.esp": b"12345", "meshes/x/y.nif": b"1234567890", "meshes/z.nif": b""})
        found = dict(page.walk_output_files(page.output_folder_full))
        assert {os.path.relpath(p, page.output_folder_full): s for p, s in found.items()} == {
            "a.esp": 5, os.path.join("meshes", "x", "y.nif"): 10, os.path.join("meshes", "z.nif"): 0}

    def test_missing_folder_is_empty_not_an_error(self, page):
        assert list(page.walk_output_files(os.path.join(page.output_folder_path, "nope"))) == []

    def test_calculate_existing_output(self, page):
        paths = write_output(page, {"a.esp": b"123", "db.esp": b"45"})
        files, size, count = page.calculate_existing_output()
        assert sorted(files) == sorted(paths) and size == 5 and count == 2


class FakeStats:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


class TestStats:
    def test_units_follow_the_size(self, page):
        page.stats = FakeStats()
        write_output(page, {"a.esp": b"x" * 2048})
        page.calculate_stats = main_page.main.calculate_stats.__get__(page)
        page.calculate_stats()
        assert "2.0 KBs" in page.stats.text and "> 1" in page.stats.text
        write_output(page, {"big.bin": b"x" * (2 * 1048576)})
        page.calculate_stats()
        assert "MBs" in page.stats.text

    def test_scanned_stats_only_count_visible_rows(self, page):
        page.stats = FakeStats()
        page.scanned = True
        page.list_eslify.rows = [0, 0, 0]
        page.list_eslify.hidden = {1}
        page.list_compact.rows = [0, 0]
        page.calculate_stats = main_page.main.calculate_stats.__get__(page)
        page.calculate_stats()
        assert "Flaggable:\n    > 2" in page.stats.text and "Compactible:\n    > 2" in page.stats.text

    def test_scan_section_hidden_before_a_scan(self, page):
        page.stats = FakeStats()
        page.calculate_stats = main_page.main.calculate_stats.__get__(page)
        page.calculate_stats()
        assert "Scanned Stats" not in page.stats.text


# -------------------------------------------------------------------------------------------- delete_output
class TestDeleteOutput:
    def test_removes_files_and_empty_folders_but_keeps_the_root(self, page):
        files = write_output(page, {"a.esp": b"1", "meshes/deep/b.nif": b"2"})
        keep = write_output(page, {"keep/c.txt": b"3"})
        page.delete_output(page.output_folder_full, files)
        assert not any(os.path.exists(f) for f in files)
        assert not os.path.exists(os.path.join(page.output_folder_full, "meshes"))
        assert os.path.exists(keep[0]) and os.path.isdir(page.output_folder_full)

    def test_refuses_to_delete_outside_an_eslifier_folder(self, page, workdir):
        other = workdir / "mods" / "SomethingElse"
        other.mkdir()
        victim = other / "a.esp"
        victim.write_bytes(b"1")
        page.delete_output(str(other), [str(victim)])
        assert victim.exists()

    def test_clears_form_id_maps_only_when_asked(self, page):
        put(os.path.join(FORM_ID_MAPS_FOLDER, "m.json"), {})
        put(os.path.join(CELL_IDS_FOLDER, "c.json"), {})
        put(CELL_MASTER_INFO_JSON, {})
        put(WINNING_FILES_DICT_JSON, {})
        put(WINNING_FILE_HISTORY_DICT_JSON, {})
        page.delete_output(page.output_folder_full, [], remove_maps=False)
        assert os.path.exists(os.path.join(FORM_ID_MAPS_FOLDER, "m.json"))
        for gone in (os.path.join(CELL_IDS_FOLDER, "c.json"), CELL_MASTER_INFO_JSON, WINNING_FILES_DICT_JSON,
                     WINNING_FILE_HISTORY_DICT_JSON):
            assert not os.path.exists(gone)
        page.delete_output(page.output_folder_full, [], remove_maps=True)
        assert not os.path.exists(os.path.join(FORM_ID_MAPS_FOLDER, "m.json"))

    def test_wait_cursor_is_always_restored(self, page, monkeypatch):
        app = main_page.QApplication
        monkeypatch.setattr(page, "prune_empty_dirs_recursive", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            page.delete_output(page.output_folder_full, [])
        assert len(app.setOverrideCursor) == 1 and len(app.restoreOverrideCursor) == 1

    def test_a_file_that_cannot_be_removed_is_logged_not_fatal(self, page, monkeypatch, log):
        files = write_output(page, {"a.esp": b"1", "b.esp": b"2"})
        real_remove = os.remove

        def flaky(path):
            if path.endswith("a.esp"):
                raise PermissionError("locked")
            real_remove(path)

        monkeypatch.setattr(os, "remove", flaky)
        page.delete_output(page.output_folder_full, files)
        assert os.path.exists(files[0]) and not os.path.exists(files[1])
        assert any("a.esp" in line for line in log.file_lines)


class TestVortexRestore:
    @pytest.fixture
    def vortex(self, page, g, workdir, monkeypatch):
        g.mod_manager_mode = 1
        g.vortex_restore_backups = True
        data = workdir / "game" / "Data"
        data.mkdir(parents=True)
        monkeypatch.setattr(main_page.VortexDBParser, "get_section",
                            staticmethod(lambda key: {"path": str(workdir / "game")}))
        return data

    def test_backup_is_restored_over_the_deployed_link(self, page, vortex):
        out = write_output(page, {"x.esp": b"patched"})[0]
        deployed = vortex / "x.esp"
        os.link(out, deployed)
        (vortex / "x.esp.vortex_backup").write_bytes(b"original")
        page.delete_output(page.output_folder_full, [out])
        assert deployed.read_bytes() == b"original"
        assert not os.path.exists(out)

    def test_unrelated_file_with_a_backup_is_left_alone(self, page, vortex):
        out = write_output(page, {"x.esp": b"patched"})[0]
        (vortex / "x.esp").write_bytes(b"someone else's")
        (vortex / "x.esp.vortex_backup").write_bytes(b"original")
        page.delete_output(page.output_folder_full, [out])
        assert (vortex / "x.esp").read_bytes() == b"someone else's"
        assert not os.path.exists(out)

    def test_missing_deployed_file_does_not_stop_the_deletion(self, page, vortex):
        files = write_output(page, {"x.esp": b"1", "y.esp": b"2"})
        (vortex / "x.esp.vortex_backup").write_bytes(b"original")
        page.delete_output(page.output_folder_full, files)
        assert not any(os.path.exists(f) for f in files)


# -------------------------------------------------------------------------------------------- state bookkeeping
class TestArchiveHelpers:
    def test_compacted_and_patched_keys_become_the_previous_list(self, page):
        put(COMPACTED_AND_PATCHED_JSON, {"a.esp": ["x"], "b.esp": ["y"]})
        page.archive_compacted_and_patched()
        assert get(PREVIOUSLY_COMPACTED_JSON) == ["a.esp", "b.esp"]
        assert not os.path.exists(COMPACTED_AND_PATCHED_JSON)

    def test_corrupt_compacted_and_patched_is_left_in_place(self, page, log):
        with open(COMPACTED_AND_PATCHED_JSON, "w") as f:
            f.write("{not json")
        page.archive_compacted_and_patched()
        assert os.path.exists(COMPACTED_AND_PATCHED_JSON)
        assert not os.path.exists(PREVIOUSLY_COMPACTED_JSON)
        assert log.errors

    def test_esl_flagged_replaces_the_older_previous_copy(self, page):
        put(PREVIOUSLY_ESL_FLAGGED_JSON, ["old.esp"])
        put(ESL_FLAGGED_JSON, ["new.esp"])
        page.archive_esl_flagged()
        assert get(PREVIOUSLY_ESL_FLAGGED_JSON) == ["new.esp"]
        assert not os.path.exists(ESL_FLAGGED_JSON)

    def test_nothing_to_archive_is_a_no_op(self, page):
        page.archive_compacted_and_patched()
        page.archive_esl_flagged()
        assert not os.path.exists(PREVIOUSLY_COMPACTED_JSON) and not os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON)

    def test_safe_remove_tolerates_missing_and_locked_files(self, page, monkeypatch, log):
        page.safe_remove("ESLifier_Data/not_there.json")
        put("ESLifier_Data/x.json", {})
        monkeypatch.setattr(os, "remove", lambda p: (_ for _ in ()).throw(PermissionError("locked")))
        page.safe_remove("ESLifier_Data/x.json")
        assert any("x.json" in line for line in log.file_lines)


class TestResetOutput:
    def run_reset(self, page, files=(), changed=()):
        page.skip_confirmations.add("OUTPUT-RESET")
        page.reset_output_next(list(files), 2097152, len(files), list(changed))

    def populate_state(self, page):
        put(COMPACTED_AND_PATCHED_JSON, {"c.esp": []})
        put(ESL_FLAGGED_JSON, ["e.esp"])
        put(ORIGINAL_FILES_JSON, {})
        put(MASTER_BYTE_DATA_JSON, {})

    def test_confirmation_reports_the_count_and_size(self, page):
        page.reset_output_next(["a", "b", "c"], 3 * 1048576, 3, [])
        assert "3 files" in page.confirms[0].text and "3.0 MBs" in page.confirms[0].text
        assert page.confirms[0].shown

    def test_state_is_archived_and_files_removed(self, page):
        self.populate_state(page)
        files = write_output(page, {"a.esp": b"1"})
        page.list_compact.flag_dict = {"x": 1}
        self.run_reset(page, files)
        assert get(PREVIOUSLY_COMPACTED_JSON) == ["c.esp"]
        assert get(PREVIOUSLY_ESL_FLAGGED_JSON) == ["e.esp"]
        for gone in (COMPACTED_AND_PATCHED_JSON, ESL_FLAGGED_JSON, ORIGINAL_FILES_JSON, MASTER_BYTE_DATA_JSON, files[0]):
            assert not os.path.exists(gone)
        assert page.list_compact.flag_dict == {} and page.list_eslify.flag_dict == {}
        assert page.list_compact.created == 1 and page.list_eslify.created == 1
        assert len(page.calculate_stats) == 1

    def test_cancel_changes_nothing(self, page):
        self.populate_state(page)
        page.reset_output_next([], 0, 0, [])
        page.confirms[0].reject()
        assert os.path.exists(COMPACTED_AND_PATCHED_JSON) and os.path.exists(ORIGINAL_FILES_JSON)

    def test_a_corrupt_state_file_does_not_abort_the_reset(self, page, log):
        with open(COMPACTED_AND_PATCHED_JSON, "w") as f:
            f.write("{not json")
        put(ORIGINAL_FILES_JSON, {})
        files = write_output(page, {"a.esp": b"1"})
        self.run_reset(page, files)
        assert not os.path.exists(files[0]) and not os.path.exists(ORIGINAL_FILES_JSON)
        assert log.errors

    def test_hash_info_is_offered_then_previous_selection_data(self, page, g):
        g.hash_output = True
        put(NEW_FILE_HASHES_JSON, {"a.esp": ["abc", True]})
        put(PREVIOUSLY_COMPACTED_JSON, ["c.esp"])
        put(PREVIOUSLY_ESL_FLAGGED_JSON, ["e.esp"])
        self.run_reset(page, changed=["a.esp"])
        assert len(page.removal_confirms) == 1 and "hash" in page.removal_confirms[0].text
        assert get(NEW_FILE_HASHES_JSON)["a.esp"] == ["abc", False]   # reset the changed flag of files being deleted
        page.removal_confirms[0].accept()
        assert not os.path.exists(NEW_FILE_HASHES_JSON)
        assert len(page.removal_confirms) == 2 and "previously" in page.removal_confirms[1].text
        page.removal_confirms[1].accept()
        assert not os.path.exists(PREVIOUSLY_COMPACTED_JSON) and not os.path.exists(PREVIOUSLY_ESL_FLAGGED_JSON)

    def test_declining_the_hash_question_still_asks_about_previous_data(self, page, g):
        g.hash_output = True
        put(NEW_FILE_HASHES_JSON, {})
        self.run_reset(page)
        page.removal_confirms[0].reject()
        assert os.path.exists(NEW_FILE_HASHES_JSON)
        assert len(page.removal_confirms) == 2

    def test_without_hashing_only_previous_data_is_offered(self, page, g):
        g.hash_output = False
        put(NEW_FILE_HASHES_JSON, {})
        put(PREVIOUSLY_COMPACTED_JSON, ["c.esp"])
        self.run_reset(page)
        assert len(page.removal_confirms) == 1 and "previously" in page.removal_confirms[0].text
        page.removal_confirms[0].reject()
        assert os.path.exists(PREVIOUSLY_COMPACTED_JSON) and os.path.exists(NEW_FILE_HASHES_JSON)

    def test_reset_output_guard_rejects_the_game_folder(self, page, log):
        page.game_folder_path = os.path.join(page.output_folder_path, page.output_folder_name)
        page.reset_output()
        assert any("output folder" in e for e in log.errors)
        assert page.confirms == [] and page.removal_confirms == []


class TestRebuildOutput:
    def run_rebuild(self, page, files=(), changed=()):
        page.skip_confirmations.add("OUTPUT-REBUILD")
        page.rebuild_output_next(list(files), 0, len(files), list(changed))

    def test_nothing_to_rebuild_touches_nothing(self, page):
        put(ORIGINAL_FILES_JSON, {})
        put(WINNING_FILES_DICT_JSON, {})
        put(MASTER_BYTE_DATA_JSON, {})
        put(NEW_FILE_HASHES_JSON, {"a.esp": ["h", True]})
        files = write_output(page, {"a.esp": b"1"})
        self.run_rebuild(page, files, ["a.esp"])
        assert [t for t, _ in FakeMessageBox.warnings] == ["No Existing Output Data"]
        for kept in (ORIGINAL_FILES_JSON, WINNING_FILES_DICT_JSON, MASTER_BYTE_DATA_JSON, files[0]):
            assert os.path.exists(kept)
        assert get(NEW_FILE_HASHES_JSON)["a.esp"] == ["h", True]
        assert page.scan == [] and page.redoing_output is False

    def test_rebuild_archives_deletes_and_starts_the_redo(self, page):
        put(COMPACTED_AND_PATCHED_JSON, {"c.esp": []})
        put(ESL_FLAGGED_JSON, ["e.esp"])
        for cache in (ORIGINAL_FILES_JSON, WINNING_FILE_HISTORY_DICT_JSON, WINNING_FILES_DICT_JSON, MASTER_BYTE_DATA_JSON):
            put(cache, {})
        put(os.path.join(FORM_ID_MAPS_FOLDER, "m.json"), {})
        files = write_output(page, {"a.esp": b"1"})
        self.run_rebuild(page, files)
        assert get(PREVIOUSLY_COMPACTED_JSON) == ["c.esp"] and get(PREVIOUSLY_ESL_FLAGGED_JSON) == ["e.esp"]
        for gone in (COMPACTED_AND_PATCHED_JSON, ESL_FLAGGED_JSON, ORIGINAL_FILES_JSON, WINNING_FILE_HISTORY_DICT_JSON,
                     WINNING_FILES_DICT_JSON, MASTER_BYTE_DATA_JSON, files[0]):
            assert not os.path.exists(gone)
        assert os.path.exists(os.path.join(FORM_ID_MAPS_FOLDER, "m.json"))   # maps survive a rebuild
        assert page.redoing_output is True and len(page.scan) == 1

    def test_rebuild_can_run_from_the_previous_lists_alone(self, page):
        put(PREVIOUSLY_COMPACTED_JSON, ["c.esp"])
        put(PREVIOUSLY_ESL_FLAGGED_JSON, ["e.esp"])
        self.run_rebuild(page)
        assert get(PREVIOUSLY_COMPACTED_JSON) == ["c.esp"] and get(PREVIOUSLY_ESL_FLAGGED_JSON) == ["e.esp"]
        assert page.redoing_output is True and len(page.scan) == 1

    def test_changed_files_chosen_for_removal_get_their_flag_reset(self, page):
        put(ESL_FLAGGED_JSON, ["e.esp"])
        put(NEW_FILE_HASHES_JSON, {"a.esp": ["h", True], "b.esp": ["h2", True]})
        self.run_rebuild(page, changed=["a.esp"])
        assert get(NEW_FILE_HASHES_JSON) == {"a.esp": ["h", False], "b.esp": ["h2", True]}

    def test_cancel_changes_nothing(self, page):
        put(ESL_FLAGGED_JSON, ["e.esp"])
        page.rebuild_output_next([], 0, 0, [])
        page.confirms[0].reject()
        assert os.path.exists(ESL_FLAGGED_JSON) and page.scan == []


# -------------------------------------------------------------------------------------------- hashing dialog
class TestOnHashingFinished:
    @pytest.fixture
    def hashing(self, page):
        page.calculate_requester = "reset_output"
        page.reset_output_next = Calls()
        page.rebuild_output_next = Calls()
        page.new_file_hashes = {"a.esp": ["h", True]}
        return page

    def result(self, changed=(), files=("f1",), size=10, count=1, error=None):
        r = {"size": size, "file_count": count, "files_to_remove": list(files), "changed_hashes": list(changed)}
        if error:
            r["error"] = error
        return r

    def test_failure_stops_before_anything_is_deleted(self, hashing):
        hashing.on_hashing_finished(self.result(error="disk on fire"))
        assert hashing.setEnabled[-1] == ((True,), {})
        assert FakeMessageBox.warnings and hashing.reset_output_next == []

    def test_no_changes_goes_straight_to_the_confirmation(self, hashing):
        hashing.files_to_not_hash.add("stale")
        hashing.on_hashing_finished(self.result())
        assert hashing.reset_output_next == [((["f1"], 10, 1, []), {})]
        assert hashing.files_to_not_hash == set()

    def test_rebuild_requester_goes_to_rebuild(self, hashing):
        hashing.calculate_requester = "rebuild_output"
        hashing.on_hashing_finished(self.result())
        assert len(hashing.rebuild_output_next) == 1 and hashing.reset_output_next == []

    def changed(self, page, workdir):
        files = write_output(page, {"p.esp": b"abc", "q.esl": b"de", "cfg.ini": b"f"})
        rel = ["p.esp", "q.esl", "cfg.ini"]
        return list(zip(files, rel))

    def test_closing_the_dialog_keeps_everything(self, hashing, workdir):
        changed = self.changed(hashing, workdir)
        hashing.on_hashing_finished(self.result(changed))
        (files, size, count, rel), _ = hashing.reset_output_next[0]
        assert files == ["f1"] and rel == []
        assert hashing.files_to_not_hash == {os.path.normpath(f).lower() for f, _ in changed}
        assert get(NEW_FILE_HASHES_JSON) == {"a.esp": ["h", True]}

    def test_plugins_and_other_files_are_listed_separately(self, hashing, workdir):
        changed = self.changed(hashing, workdir)
        hashing.on_hashing_finished(self.result(changed))
        plugins, others = UI.list_widgets
        assert [i.toolTip() for i in plugins.items] == [os.path.normpath(changed[0][0]), os.path.normpath(changed[1][0])]
        assert [i.data(0) for i in others.items] == ["cfg.ini"]

    def test_delete_all_removes_every_changed_file(self, hashing, workdir):
        changed = self.changed(hashing, workdir)
        UI.on_dialog_exec = lambda: UI.click("Delete All")
        hashing.on_hashing_finished(self.result(changed))
        (files, size, count, rel), _ = hashing.reset_output_next[0]
        assert files == ["f1"] + [f for f, _ in changed]
        assert rel == ["p.esp", "q.esl", "cfg.ini"] and size == 10 + 6 and count == 4
        assert hashing.files_to_not_hash == set()

    def test_delete_selected_removes_only_checked_files(self, hashing, workdir):
        changed = self.changed(hashing, workdir)

        def choose():
            UI.list_widgets[0].items[1].setCheckState(UI.Qt.CheckState.Checked)   # q.esl
            UI.click("Delete Selected")

        UI.on_dialog_exec = choose
        hashing.on_hashing_finished(self.result(changed))
        (files, size, count, rel), _ = hashing.reset_output_next[0]
        assert files == ["f1", os.path.normpath(changed[1][0])] and rel == ["q.esl"]
        assert hashing.files_to_not_hash == {os.path.normpath(changed[0][0]).lower(), os.path.normpath(changed[2][0]).lower()}

    def test_keep_all_button_keeps_everything(self, hashing, workdir):
        changed = self.changed(hashing, workdir)
        UI.on_dialog_exec = lambda: UI.click("Keep All")
        hashing.on_hashing_finished(self.result(changed))
        assert hashing.reset_output_next[0][0][3] == []
        assert len(hashing.files_to_not_hash) == 3
