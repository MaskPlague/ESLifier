"""
main_page flow control: what happens when a scan, a compact or an ESLify run finishes, and how the "redo output"
(rebuild) and Patch New flows chain those steps together.

These pin the CURRENT behaviour so a refactor can be checked against it. Tests marked ``xfail(strict=True)`` describe
behaviour that is wrong today (a flow that never ends, a KeyError); when one is fixed it starts to XPASS, which strict
mode reports as a failure, so remove the marker then.
"""
import json
import os

import pytest

import main.main_page as main_page
from data_holder import _global, PREVIOUSLY_COMPACTED_JSON, PREVIOUSLY_ESL_FLAGGED_JSON
from scanners.vortex_database_reader import ReadState
from main_page_fakes import make_page, UI, FakeMessageBox


@pytest.fixture
def page(workdir, monkeypatch):
    return make_page(workdir, monkeypatch)


def touch_json(path, data=("a.esp",)):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(data), f)


def ended(page):
    """The flow is over: nothing is waiting on a redo and the window is usable again."""
    return (not page.redoing_output and not page.patch_new_running and not page.patch_new_only_remove
            and page.setEnabled and page.setEnabled[-1] == ((True,), {}))


# ------------------------------------------------------------------------------------ finished: compact
class TestCompactFinished:
    def test_normal_run_reenables_ui_and_shows_finished_dialog(self, page, log):
        page.finished_button_action("compact", [])
        assert page.setEnabled == [((True,), {})]
        assert len(page.calculate_stats) == 1
        assert [m.shown for m in FakeMessageBox.instances] == [True]
        assert any("Total Elapsed Time" in line for line in log.normal)

    def test_checked_mods_leave_the_compact_list(self, page):
        page.list_compact.flag_dict = {"a.esp": {"need_compacting"}, "b.esp": {"need_compacting"}}
        page.finished_button_action("compact", ["a.esp"])
        assert list(page.list_compact.flag_dict) == ["b.esp"]
        assert page.list_compact.created == 1

    def test_redo_suppresses_the_finished_dialog(self, page):
        page.redoing_output = True
        page.patch_new_running = True
        page.finished_button_action("compact", [])
        assert FakeMessageBox.instances == []

    def test_patch_new_run_hands_control_back_to_patch_new(self, page):
        page.redoing_output = True
        page.patch_new_running = True
        page.patch_new_only_remove = True
        page.finished_button_action("compact", [])
        assert len(page.patch_new.finished_rebuilding) == 1
        assert ended(page)

    @pytest.mark.xfail(strict=True, reason="pop(mod) raises KeyError if the mod is no longer in flag_dict")
    def test_mod_missing_from_flag_dict_is_tolerated(self, page):
        page.list_compact.flag_dict = {}
        page.finished_button_action("compact", ["gone.esp"])

    def test_cell_master_reminder_is_shown_once(self, page):
        page.generate_cell_master = True
        page.cell_master_warned = False
        page.finished_button_action("compact", [])
        FakeMessageBox.instances[0].accepted.emit()  # click Ok on "Finished"
        assert page.cell_master_warned is True
        assert len(FakeMessageBox.instances) == 2


class TestFinishedMessageText:
    @pytest.mark.parametrize("mode, expected", [(0, "ESLifier Output."), (1, "re-deploy"), (2, "refresh in MO2")])
    def test_message_matches_the_mod_manager(self, page, g, mode, expected):
        texts = []
        original = FakeMessageBox.__init__

        class Box(FakeMessageBox):
            def setText(self, text):
                texts.append(text)

        main_page.QMessageBox = Box  # monkeypatch in make_page restores the original afterwards
        g.mod_manager_mode = mode
        page.finished_button_action("compact", [])
        assert expected in texts[0]


# ------------------------------------------------------------------------------------ finished: eslify
class TestEslifyFinished:
    def test_normal_run_reenables_ui(self, page):
        page.finished_button_action("eslify", [])
        assert page.setEnabled == [((True,), {})]
        assert len(page.calculate_stats) == 1
        assert page.compact_selected_clicked == []

    def test_checked_mods_leave_the_eslify_list(self, page):
        page.list_eslify.flag_dict = {"a.esp": set(), "b.esp": set()}
        page.finished_button_action("eslify", ["b.esp"])
        assert list(page.list_eslify.flag_dict) == ["a.esp"]
        assert page.list_eslify.created == 1

    def test_redo_continues_into_compacting_when_previous_compacts_are_checked(self, page, workdir):
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.list_compact.rows = [UI.Qt.CheckState.Checked, UI.Qt.CheckState.Unchecked]
        page.finished_button_action("eslify", [])
        assert len(page.compact_selected_clicked) == 1
        assert page.list_compact.check_previous_calls == 1
        assert page.redoing_output is True       # still mid-redo
        assert page.setEnabled == []             # and the UI stays locked

    def test_redo_with_nothing_to_compact_ends_the_flow(self, page, workdir):
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.list_compact.rows = [UI.Qt.CheckState.Unchecked]
        page.finished_button_action("eslify", [])
        assert page.compact_selected_clicked == []
        assert ended(page)

    def test_redo_with_nothing_to_compact_finishes_patch_new(self, page, workdir):
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.patch_new_running = True
        page.list_compact.rows = []
        page.finished_button_action("eslify", [])
        assert len(page.patch_new.finished_rebuilding) == 1
        assert not page.patch_new_running and not page.redoing_output

    def test_redo_without_previous_compacts_ends_the_flow(self, page):
        page.redoing_output = True
        page.finished_button_action("eslify", [])
        assert ended(page)
        assert len(page.calculate_stats) == 1

    @pytest.mark.xfail(strict=True, reason="no PREVIOUSLY_COMPACTED_JSON + patch_new_running: finished_rebuilding is never "
                                           "called, so Patch New hangs and patch_new_running stays True")
    def test_redo_without_previous_compacts_finishes_patch_new(self, page):
        page.redoing_output = True
        page.patch_new_running = True
        page.finished_button_action("eslify", [])
        assert len(page.patch_new.finished_rebuilding) == 1
        assert ended(page)


# ------------------------------------------------------------------------------------ scan completed
FLAGS_E = {"esl.esp": {"esl_flaggable"}}
FLAGS_C = {"cmp.esp": {"need_compacting"}}
DEPS = {"cmp.esp": ["dep.esp"]}


class TestCompletedScan:
    def test_populates_both_lists_and_unlocks(self, page):
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert page.list_eslify.flag_dict == FLAGS_E
        assert page.list_compact.flag_dict == FLAGS_C
        assert page.dependency_dictionary == DEPS
        assert page.list_eslify.created == 1 and page.list_compact.created == 1
        assert ended(page)
        assert len(page.calculate_stats) == 1

    def test_a_failing_list_is_logged_and_the_other_still_builds(self, page, log):
        page.list_eslify.fail_create = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert page.list_compact.created == 1
        assert any("ESLify" in e for e in log.errors)
        assert ended(page)

    def test_redo_with_previous_eslify_selection_eslifies_first(self, page, workdir):
        touch_json(PREVIOUSLY_ESL_FLAGGED_JSON)
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert page.list_eslify.check_previous_calls == 1
        assert len(page.eslify_selected_clicked) == 1
        assert page.compact_selected_clicked == []   # compacting is chained after ESLify finishes
        assert page.setEnabled == []

    def test_redo_with_only_previous_compacts_compacts(self, page, workdir):
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert page.list_compact.check_previous_calls == 1
        assert len(page.compact_selected_clicked) == 1
        assert page.eslify_selected_clicked == []

    def test_patch_new_only_remove_hands_back_without_patching(self, page, workdir):
        touch_json(PREVIOUSLY_COMPACTED_JSON)
        page.redoing_output = True
        page.patch_new_running = True
        page.patch_new_only_remove = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert len(page.patch_new.finished_rebuilding) == 1
        assert page.compact_selected_clicked == [] and page.eslify_selected_clicked == []
        assert not page.redoing_output and not page.patch_new_running and not page.patch_new_only_remove

    @pytest.mark.xfail(strict=True, reason="redo with neither PREVIOUSLY_* file: nothing ends the flow, the UI stays disabled")
    def test_redo_with_no_previous_data_ends_the_flow(self, page):
        page.redoing_output = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert ended(page)


class TestScanErrors:
    def test_vortex_error_shows_a_dialog_and_leaves_lists_alone(self, page, g):
        g.vortex_error = ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE
        page.scanned = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert g.vortex_error is None
        assert page.scanned is False
        assert "unresponsive" in page.confirms[0].text and page.confirms[0].shown
        assert page.list_eslify.created == 0
        assert page.setEnabled[-1] == ((True,), {})

    def test_mo2_error_shows_a_dialog_and_leaves_lists_alone(self, page, g):
        g.mo2_error = Exception("bad ini")
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert g.mo2_error is None
        assert "bad ini" in page.confirms[0].text
        assert page.list_compact.created == 0

    def test_unknown_vortex_state_still_gets_a_message(self, page):
        assert "weird" in page.vortex_error_text("weird")

    @pytest.mark.xfail(strict=True, reason="an error during a redo/Patch New leaves redoing_output/patch_new_running set")
    def test_error_during_redo_ends_the_flow(self, page, g):
        g.vortex_error = ReadState.ERROR_DB_LOCKED_EXTENSION_MISSING
        page.redoing_output = True
        page.patch_new_running = True
        page.completed_scan(FLAGS_E, FLAGS_C, DEPS)
        assert ended(page)


# ------------------------------------------------------------------------------------ scan()
class TestScan:
    def test_first_scan_locks_the_ui_and_starts(self, page, log):
        page.scan = main_page.main.scan.__get__(page)
        page.scan()
        assert page.setEnabled == [((False,), {})]
        assert page.scanned is True
        assert len(page.log_stream.show) == 1
        assert any("Running Scan" in line for line in log.file_lines)

    def test_unreadable_vortex_database_blocks_the_scan(self, page, g, monkeypatch):
        page.scan = main_page.main.scan.__get__(page)
        g.mod_manager_mode = 1
        monkeypatch.setattr(main_page.VortexDBParser, "is_readable",
                            staticmethod(lambda: ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE))
        page.scanned = True
        page.scan()
        assert page.setEnabled == []
        assert page.scanned is False
        assert "unresponsive" in page.confirms[0].text and page.confirms[0].shown

    @pytest.mark.xfail(strict=True, reason="vortex_error_text lost the DEPLOYING and PURGING messages when the Vortex error "
                                           "text was centralised, so they fall through to 'unknown error'")
    @pytest.mark.parametrize("state, word", [(ReadState.ERROR_DB_LOCKED_DEPLOYING, "deploy"),
                                             (ReadState.ERROR_DB_LOCKED_PURGING, "purging")])
    def test_deploying_and_purging_have_their_own_messages(self, page, state, word):
        assert word in page.vortex_error_text(state)

    def test_second_scan_asks_first_and_cancel_unlocks(self, page):
        page.scan = main_page.main.scan.__get__(page)
        page.scanned = True
        page.scan()
        confirm = page.confirms[0]
        assert confirm.shown
        confirm.reject()
        assert page.setEnabled[-1] == ((True,), {})
        assert len(page.log_stream.show) == 0

    def test_second_scan_runs_after_accept(self, page):
        page.scan = main_page.main.scan.__get__(page)
        page.scanned = True
        page.scan()
        page.confirms[0].accept()
        assert len(page.log_stream.show) == 1

    def test_rescan_confirmation_can_be_skipped(self, page):
        page.scan = main_page.main.scan.__get__(page)
        page.scanned = True
        page.skip_confirmations.add("RE-SCAN")
        page.scan()
        assert page.confirms == [] and len(page.log_stream.show) == 1

    def test_redo_accepts_the_rescan_prompt_itself(self, page):
        page.scan = main_page.main.scan.__get__(page)
        page.scanned = True
        page.redoing_output = True
        page.scan()
        assert not page.confirms[0].shown
        assert len(page.log_stream.show) == 1


class TestScanAndPatchNew:
    def test_confirm_then_hand_over_to_patch_new(self, page, log):
        page.scan_and_patch_new = main_page.main.scan_and_patch_new.__get__(page)
        page.scan_and_patch_new()
        assert page.setEnabled == [((False,), {})]
        page.confirms[0].accept()
        assert page.patch_new.scan_and_find == [((page,), {})]
        assert any("Patch New" in line for line in log.file_lines)

    def test_cancel_unlocks(self, page):
        page.scan_and_patch_new = main_page.main.scan_and_patch_new.__get__(page)
        page.scan_and_patch_new()
        page.confirms[0].reject()
        assert page.setEnabled[-1] == ((True,), {})
        assert page.patch_new.scan_and_find == []
