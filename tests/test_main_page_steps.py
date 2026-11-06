"""
main_page's compact and ESL flag steps: collecting the ticked mods, the confirmation (with its disk space estimate) and
starting the workers. Both steps share one implementation (``selected_clicked``) and differ only in the data from
``step_spec``, so most tests run against both.
"""
import json
import os
import types

import pytest

import main.main_page as main_page
import main.workers as workers
from data_holder import _global, ESL_FLAGGED_JSON, FILE_MASTERS_JSON, GAME_ARCHIVE_TYPE
from main.flow import Flow
from main_page_fakes import make_page, UI, Calls, Signal, Recorder, FakeRow, FakeMessageBox


@pytest.fixture
def page(workdir, monkeypatch):
    page = make_page(workdir, monkeypatch)
    page.start_worker = Calls()
    page.finished_button_action = Calls()
    page.compact_confirmed = Calls()
    page.eslify_confirmed = Calls()
    return page


def rows(page, name, *specs):
    """specs: (path, ticked). Fills the list for 'compact' or 'eslify'."""
    mod_list = page.list_compact if name == "compact" else page.list_eslify
    cs = UI.Qt.CheckState
    mod_list.rows = [FakeRow(path, cs.Checked if ticked else cs.Unchecked) for path, ticked in specs]
    return mod_list


both = pytest.mark.parametrize("name", ["compact", "eslify"])


class TestCollectingMods:
    @both
    def test_only_ticked_visible_rows_are_returned(self, page, name):
        mod_list = rows(page, name, ("a.esp", True), ("b.esp", False), ("c.esp", True), ("d.esp", True))
        mod_list.hidden = {2}
        assert page.get_checked_mods(mod_list) == ["a.esp", "d.esp"]

    @both
    def test_lock_checked_rows_marks_them_in_progress(self, page, name):
        mod_list = rows(page, name, ("a.esp", True), ("b.esp", False))
        flags_before = mod_list.rows[1].flags()
        page.lock_checked_rows(mod_list)
        assert mod_list.rows[0].checkState() is UI.Qt.CheckState.PartiallyChecked
        assert mod_list.rows[1].checkState() is UI.Qt.CheckState.Unchecked
        assert mod_list.rows[1].flags() == flags_before

    def test_game_archive_masters_are_inverted(self, page, g):
        g.game_archive_dict = {"A.bsa": ["x.esm", "y.esm"], "B.bsa": ["x.esm"]}
        assert page.game_archive_masters_by_file() == {"x.esm": ["A.bsa", "B.bsa"], "y.esm": ["A.bsa"]}


class TestSelectedClicked:
    @both
    def test_nothing_ticked_just_unlocks(self, page, name):
        rows(page, name, ("a.esp", False))
        page.selected_clicked(name)
        assert page.setEnabled == [((False,), {}), ((True,), {})]
        assert page.finished_button_action == [] and page.confirms == []

    @both
    @pytest.mark.parametrize("flow", [Flow.REBUILD, Flow.PATCH_NEW])
    def test_nothing_ticked_in_a_redo_moves_the_flow_on(self, page, name, flow):
        rows(page, name, ("a.esp", False))
        page.flow = flow
        page.selected_clicked(name)
        assert page.finished_button_action == [((name, []), {})]
        assert page.setEnabled == [((False,), {})]

    @both
    def test_a_redo_confirms_itself(self, page, name):
        rows(page, name, ("a.esp", True))
        page.flow = Flow.REBUILD
        page.selected_clicked(name)
        assert getattr(page, f"{name}_confirmed") == [((["a.esp"],), {})]
        assert page.start_worker == []                      # no estimate needed

    @both
    def test_the_confirmation_can_be_skipped_in_settings(self, page, name):
        rows(page, name, ("a.esp", True))
        page.skip_confirmations.add("COMPACT" if name == "compact" else "FLAG")
        page.selected_clicked(name)
        assert getattr(page, f"{name}_confirmed") == [((["a.esp"],), {})]
        assert page.start_worker == []

    @both
    def test_otherwise_it_asks_while_the_size_is_estimated(self, page, name):
        rows(page, name, ("a.esp", True))
        page.selected_clicked(name)
        confirm, = page.confirms
        assert confirm.shown and confirm.enabled is False
        assert getattr(page, f"{name}_confirmed") == []
        (args, kwargs), = page.start_worker
        assert isinstance(args[0], workers.SizeEstimateWorker)
        confirm.accept()                                    # Yes
        assert getattr(page, f"{name}_confirmed") == [((["a.esp"],), {})]

    def test_compact_estimate_counts_archives_and_everyones_dependents(self, page, g):
        g.game_archive_dict = {"Arc.bsa": ["a.esp"]}
        rows(page, "compact", ("C:/m/a.esp", True))
        page.dependency_dictionary = {"a.esp": ["dep.esp"]}
        page.selected_clicked("compact")
        worker = page.start_worker[0][0][0]
        assert worker.has_others is None
        assert worker.game_archive_masters == {"a.esp": ["Arc.bsa"]}
        assert worker.mods == ["C:/m/a.esp"] and worker.dependency_dictionary == {"a.esp": ["dep.esp"]}
        assert worker.output_folder_path == page.output_folder_path

    def test_eslify_estimate_only_counts_dependents_of_new_interior_cells(self, page):
        rows(page, "eslify", ("a.esp", True), ("b.esp", True))
        page.list_eslify.flag_dict = {"a.esp": {"new_interior_cell"}, "b.esp": {"esl_flaggable"}}
        page.selected_clicked("eslify")
        worker = page.start_worker[0][0][0]
        assert worker.has_others == {"a.esp"} and worker.game_archive_masters is None

    def test_the_estimate_comes_back_to_show_estimate(self, page):
        rows(page, "compact", ("a.esp", True))
        page.show_estimate = Calls()
        page.selected_clicked("compact")
        (args, kwargs), = page.start_worker
        args[3](123, 456)                                    # the worker's finished callback
        (shown_args, _), = page.show_estimate
        assert shown_args[1:] == (["a.esp"], 123, 456) and shown_args[0].name == "compact"

    def test_wrappers_select_the_right_step(self, page):
        del page.compact_selected_clicked, page.eslify_selected_clicked   # use the real wrappers
        page.selected_clicked = Calls()
        page.compact_selected_clicked()
        page.eslify_selected_clicked()
        assert page.selected_clicked == [(("compact",), {}), (("eslify",), {})]


class TestShowEstimate:
    GB = 1024 ** 3

    def shown(self, page, name, size, free, checked=("a.esp",)):
        page.confirm = page.create_confirmation()
        step = page.make_list_obj(name)
        page.show_estimate(step, list(checked), size, free)
        return page.confirm

    @pytest.mark.parametrize("size, value, unit", [(2 * GB, "2.0", "GBs"), (5 * 1048576, "5.0", "MBs"), (2048, "2.0", "KBs")])
    def test_compact_text_has_size_unit_free_space_and_archive_type(self, page, size, value, unit):
        confirm = self.shown(page, "compact", size, 10 * self.GB)
        assert f"up to {value} {unit} of new files" in confirm.text
        assert f"compressed {GAME_ARCHIVE_TYPE}" in confirm.text and "you have 10.0 GBs" in confirm.text

    @pytest.mark.parametrize("size, value, unit", [(2 * GB, "2.0", "GBs"), (5 * 1048576, "5.0", "MBs"), (2048, "2.0", "KBs")])
    def test_eslify_text_has_size_unit_and_free_space(self, page, size, value, unit):
        confirm = self.shown(page, "eslify", size, 10 * self.GB)
        assert f"up to {value} {unit} of new files" in confirm.text and "you have 10.0 GBs" in confirm.text

    @both
    def test_title_counts_the_mods_and_the_dialog_is_usable_again(self, page, name):
        confirm = self.shown(page, name, 1024, 10 * self.GB, checked=("a.esp", "b.esp", "c.esp"))
        assert "3 Mod(s)" in confirm.title and confirm.enabled is True
        assert ("Patching" if name == "compact" else "ESL Flagging") in confirm.title

    @both
    def test_not_enough_space_replaces_the_text_and_removes_yes(self, page, name):
        confirm = self.shown(page, name, 3 * self.GB, 2 * self.GB)
        assert confirm.text.startswith("Not enough space!") and "3.0" in confirm.text and "2.0 GBs" in confirm.text
        assert len(confirm.removed_buttons) == 1

    @both
    def test_exactly_the_free_space_is_not_enough(self, page, name):
        assert self.shown(page, name, 1024, 1024).text.startswith("Not enough space!")

    @both
    def test_enough_space_keeps_yes(self, page, name):
        assert self.shown(page, name, 1024, 2048).removed_buttons == []

    @both
    def test_cancel_unlocks_the_window(self, page, name):
        confirm = self.shown(page, name, 1024, 10 * self.GB)
        confirm.reject()
        assert page.setEnabled[-1] == ((True,), {})


class FakeWorker:
    instances = []

    def __init__(self, *args):
        self.args = args
        self.finished_signal = Signal()
        FakeWorker.instances.append(self)

    def run(self):
        pass

    def flag_files(self):
        pass


class TestConfirmed:
    @pytest.fixture(autouse=True)
    def fake_workers(self, monkeypatch):
        FakeWorker.instances = []
        monkeypatch.setattr(workers, "CompactorWorker", FakeWorker)
        monkeypatch.setattr(workers, "FlagWorker", FakeWorker)

    @pytest.fixture
    def confirm_page(self, page):
        del page.compact_confirmed, page.eslify_confirmed                 # use the real ones
        page.confirm = page.create_confirmation()
        return page

    def test_compact_confirmed_locks_rows_and_starts_the_compactor(self, confirm_page, log):
        page = confirm_page
        rows(page, "compact", ("a.esp", True))
        page.dependency_dictionary = {"a.esp": []}
        page.compact_confirmed(["a.esp"])
        assert page.list_compact.rows[0].checkState() is UI.Qt.CheckState.PartiallyChecked
        assert not page.confirm.shown and len(page.log_stream.show) == 1 and page.start_time > 0
        assert any("Compacting Plugins" in line for line in log.file_lines)
        (args, _), = page.start_worker
        worker = FakeWorker.instances[0]
        assert args[0] is worker
        assert worker.args == (["a.esp"], {"a.esp": []}, page.files_to_not_hash)
        args[3]()                                                         # when the worker finishes
        assert page.finished_button_action == [(("compact", ["a.esp"]), {})]

    def test_eslify_confirmed_without_cell_master_flags_everything(self, confirm_page, workdir):
        page = confirm_page
        rows(page, "eslify", ("a.esp", True))
        page.create_flag_worker = Calls()
        page.eslify_confirmed(["C:/m/a.esp", "C:/m/b.esp"])
        assert page.create_flag_worker == [((["C:/m/a.esp", "C:/m/b.esp"],), {})]
        assert page.list_eslify.rows[0].checkState() is UI.Qt.CheckState.PartiallyChecked

    def test_eslify_confirmed_with_cell_master_splits_flag_only_from_patch_and_flag(self, confirm_page):
        page = confirm_page
        page.generate_cell_master = True
        page.create_flag_worker = Calls()
        page.list_eslify.flag_dict = {"new.esp": {"new_cell"}, "full.esp": {"new_cell", "maxed_masters"}, "plain.esp": set()}
        page.eslify_confirmed(["new.esp", "full.esp", "plain.esp"])
        assert page.create_flag_worker == [((["full.esp", "plain.esp"], ["new.esp"]), {})]

    def test_eslify_confirmed_records_the_flagged_plugins_alongside_existing_ones(self, confirm_page, workdir):
        page = confirm_page
        page.create_flag_worker = Calls()
        with open(ESL_FLAGGED_JSON, "w") as f:
            json.dump(["old.esp"], f)
        page.eslify_confirmed(["C:/m/a.esp"])
        with open(ESL_FLAGGED_JSON) as f:
            assert sorted(json.load(f)) == ["a.esp", "old.esp"]

    def test_flag_worker_chains_into_patch_and_flag(self, page):
        page.create_patch_and_flag_worker = Calls()
        page.create_flag_worker(["a.esp"], ["b.esp"])
        (args, _), = page.start_worker
        worker = FakeWorker.instances[0]
        assert args[0] is worker and worker.args == (["a.esp"], page.files_to_not_hash)
        args[3]()
        assert page.create_patch_and_flag_worker == [((["a.esp"], ["b.esp"]), {})]

    def test_patch_and_flag_runs_the_compactor_then_finishes_with_every_file(self, page):
        page.create_patch_and_flag_worker(["a.esp"], ["b.esp"])
        (args, _), = page.start_worker
        assert args[0] is FakeWorker.instances[0] and FakeWorker.instances[0].args[0] == ["b.esp"]
        args[3]()
        assert page.finished_button_action == [(("eslify", ["a.esp", "b.esp"]), {})]

    def test_without_patch_and_flag_it_finishes_straight_away(self, page, log):
        page.create_patch_and_flag_worker(["a.esp"], [])
        assert page.start_worker == []
        assert page.finished_button_action == [(("eslify", ["a.esp"]), {})]
        assert "File(s) ESL Flagged" in log.normal


class FakeThread:
    instances = []

    def __init__(self):
        self.started, self.finished = Signal(), Signal()
        self.is_started = False
        self.quit = Calls()
        FakeThread.instances.append(self)

    def start(self):
        self.is_started = True


class TestStartWorker:
    @pytest.fixture
    def started(self, page, monkeypatch):
        del page.start_worker
        page.running_workers = []
        FakeThread.instances = []
        monkeypatch.setattr(main_page, "QThread", FakeThread)
        worker = types.SimpleNamespace(moveToThread=Calls(), finished_signal=Signal(), run=lambda: None)
        done = Calls()
        page.start_worker(worker, worker.run, worker.finished_signal, done)
        return page, worker, done, FakeThread.instances[0]

    def test_wires_thread_worker_and_signals(self, started):
        page, worker, done, thread = started
        assert worker.moveToThread == [((thread,), {})]
        assert thread.started.slots == [worker.run] and thread.is_started
        worker.finished_signal.emit(1, 2)
        assert done == [((1, 2), {})]
        assert len(worker.finished_signal.slots) == 2       # the callback, then quitting the thread

    def test_thread_and_worker_are_kept_alive_until_the_thread_has_finished(self, started):
        page, worker, done, thread = started
        assert page.running_workers == [(thread, worker)]
        thread.finished.emit()
        assert page.running_workers == []

    def test_overlapping_workers_are_each_kept_alive(self, started, monkeypatch):
        page, first_worker, _, first_thread = started
        second = types.SimpleNamespace(moveToThread=Calls(), finished_signal=Signal(), run=lambda: None)
        page.start_worker(second, second.run, second.finished_signal)       # e.g. flag -> patch and flag
        assert len(page.running_workers) == 2
        first_thread.finished.emit()
        assert [w for _, w in page.running_workers] == [second]


class TestSizeEstimateWorker:
    def test_emits_the_estimate_and_free_space(self, tmp_path):
        f = tmp_path / "a.esp"
        f.write_bytes(b"x" * 7)
        worker = workers.SizeEstimateWorker([str(f)], None, {}, {}, None, str(tmp_path))
        worker.finished_signal = Recorder()
        worker.run()
        (size, free), = worker.finished_signal.emitted
        assert size == 7 and free > 0
