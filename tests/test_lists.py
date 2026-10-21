"""
list_parent / list_compact / list_eslify: the plugin tables on the Compact and ESLify pages.

The widgets are Qt, so a small stateful stand-in for QTableWidget (rows, items, hidden rows/columns, check states)
is installed on the stand-in base class. The tests cover what the tables decide: which plugins get a row, their
check state, which flags are shown, which rows are hidden, and how previous selections are re-applied.
"""
import enum
import json
import types

import pytest

from lists import list_compact
from lists import list_eslify
from lists import list_parent
from data_holder import _global


# ------------------------------------------------------------------------------------------ fakes
class _Member(int):
    pass


class _NS:
    def __init__(self, name):
        self._name, self._cache = name, {}

    def __getattr__(self, member):
        if member.startswith("__"):
            raise AttributeError(member)
        if member not in self._cache:
            self._cache[member] = _Member(1 << len(self._cache))
        return self._cache[member]


class FakeQt:
    def __init__(self):
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = _NS(name)
        return self._cache[name]


QT = FakeQt()
CHECKED, UNCHECKED, PARTIAL = QT.CheckState.Checked, QT.CheckState.Unchecked, QT.CheckState.PartiallyChecked
USER_CHECKABLE = QT.ItemFlag.ItemIsUserCheckable


class FakeItem:
    def __init__(self, text=""):
        self._text, self._state, self._flags, self._tip, self._col = text, UNCHECKED, _Member(0), "", None

    def text(self): return self._text
    def setText(self, t): self._text = t
    def checkState(self): return self._state
    def setCheckState(self, s): self._state = s
    def flags(self): return self._flags
    def setFlags(self, f): self._flags = f
    def toolTip(self): return self._tip
    def setToolTip(self, t): self._tip = t
    def setTextAlignment(self, a): pass
    def column(self): return self._col


class FakeAnim:
    State = types.SimpleNamespace(Running="running")

    def __init__(self, *a):
        self._state, self.started, self.stopped = None, 0, 0
        self.finished = types.SimpleNamespace(emit=lambda: None, connect=lambda f: None)

    def state(self): return self._state
    def start(self): self.started += 1; self._state = "running"
    def stop(self): self.stopped += 1; self._state = None


class FakeTimer:
    def __init__(self): self.started = self.stopped = 0
    def start(self): self.started += 1
    def stop(self): self.stopped += 1


class FakeLineEdit:
    def __init__(self, text=""): self._t = text
    def text(self): return self._t


class Warnings:
    calls = []


class FakeMessageBox:
    Icon = _NS("Icon")

    class StandardButton:
        Ok = "Ok"

    @staticmethod
    def warning(parent, title, text, buttons=None):
        Warnings.calls.append((title, text))


class Perm:
    """Absorbs any attribute access or call (header objects, signals, ...)."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Perm()

    def __call__(self, *a, **k):
        return Perm()


class FakeBlacklist:
    def __init__(self):
        self.added = []

    def add_to_blacklist(self, mods):
        self.added.append(mods)


def st(obj, name, default):
    """Per-instance state; the stand-in widget base answers any missing attribute, so getattr defaults never apply."""
    return obj.__dict__.setdefault(name, default)


TABLE_METHODS = {}


def table_method(fn):
    TABLE_METHODS[fn.__name__] = fn
    return fn


@table_method
def tr(self, s): return s


for _name in ("horizontalHeaderItem", "horizontalHeader", "verticalHeader"):
    TABLE_METHODS[_name] = lambda self, *a: Perm()
for _name in ("itemChanged", "customContextMenuRequested"):
    TABLE_METHODS[_name] = Perm()


@table_method
def clearContents(self): self._items = {}


@table_method
def setRowCount(self, n): self._rows = n


@table_method
def rowCount(self): return st(self, "_rows", 0)


@table_method
def setItem(self, r, c, item):
    item._col = c
    item._row = r
    self._items = st(self, "_items", {})
    self._items[(r, c)] = item


@table_method
def item(self, r, c): return st(self, "_items", {}).get((r, c))


@table_method
def setRowHidden(self, r, hidden):
    self._hidden_rows = st(self, "_hidden_rows", set())
    (self._hidden_rows.add if hidden else self._hidden_rows.discard)(r)


@table_method
def isRowHidden(self, r): return r in st(self, "_hidden_rows", set())


@table_method
def showColumn(self, c): self.setColumnHidden(c, False)


@table_method
def hideColumn(self, c): self.setColumnHidden(c, True)


@table_method
def setColumnHidden(self, c, hidden):
    self._hidden_cols = st(self, "_hidden_cols", set())
    (self._hidden_cols.add if hidden else self._hidden_cols.discard)(c)


@table_method
def isColumnHidden(self, c): return c in st(self, "_hidden_cols", set())


@table_method
def setCellWidget(self, r, c, w):
    self._widgets = st(self, "_widgets", {})
    self._widgets[(r, c)] = w


@table_method
def cellWidget(self, r, c): return st(self, "_widgets", {}).get((r, c))


@table_method
def blockSignals(self, b): pass


@table_method
def selectedItems(self): return st(self, "_selected", [])


@table_method
def findItems(self, text, flag):
    return [i for i in st(self, "_items", {}).values() if i._col == self.MOD_COL and text.lower() in i.text().lower()]


@pytest.fixture
def lists(monkeypatch, workdir):
    base = list_parent.QTableWidget
    for name, fn in TABLE_METHODS.items():
        monkeypatch.setattr(base, name, fn, raising=False)
    for mod in (list_parent, list_compact, list_eslify):
        monkeypatch.setattr(mod, "Qt", QT)
        monkeypatch.setattr(mod, "QTableWidgetItem", FakeItem)
        monkeypatch.setattr(mod, "QMessageBox", FakeMessageBox, raising=False)
    monkeypatch.setattr(list_parent, "blacklist", FakeBlacklist)
    monkeypatch.setattr(list_compact, "QPushButton", lambda *a, **k: Perm())
    monkeypatch.setattr(list_compact, "QListWidget", lambda *a, **k: Perm(), raising=False)

    def init_filter_flash(self):
        self.flash_anim, self.flash_timer_reminder = FakeAnim(), FakeTimer()

    monkeypatch.setattr(list_parent.list_parent_class, "init_filter_flash", init_filter_flash)
    monkeypatch.setattr(list_parent, "QVariantAnimation", FakeAnim)
    Warnings.calls = []
    for k in ("mods_with_seq", "pex_with_getmodbyname", "plugins"):
        monkeypatch.setattr(_global, k, {} if k != "plugins" else [], raising=False)
    return workdir


def write_data(workdir, name, data):
    (workdir / "ESLifier_Data" / name).write_text(json.dumps(data), encoding="utf-8")


def names(table, col=0):
    return [table.item(r, col).text() for r in range(table.rowCount())]


def hidden(table):
    return sorted(table.item(r, table.MOD_COL).text() for r in range(table.rowCount()) if table.isRowHidden(r))


# ------------------------------------------------------------------------------------------ list_parent helpers
class TestParent:
    @pytest.fixture
    def table(self, lists):
        t = list_compact.list_compactable()
        return t

    def test_get_data_from_file(self, table, tmp_path):
        good = tmp_path / "g.json"
        good.write_text('{"a": 1}')
        bad = tmp_path / "b.json"
        bad.write_text("{nope")
        assert table.get_data_from_file(str(good), dict) == {"a": 1}
        assert table.get_data_from_file(str(bad), list) == []
        assert table.get_data_from_file(str(tmp_path / "missing.json"), dict) == {}

    def make_rows(self, table, specs):
        table.setRowCount(len(specs))
        for r, (text, state, hide) in enumerate(specs):
            it = FakeItem(text)
            it.setCheckState(state)
            table.setItem(r, table.MOD_COL, it)
            if hide:
                table.setItem(r, table.HIDER_COL, FakeItem("hide me"))
        table.hide_rows()

    def test_hide_rows_follows_the_hider_column(self, table):
        self.make_rows(table, [("a", UNCHECKED, False), ("b", UNCHECKED, True)])
        assert [table.isRowHidden(0), table.isRowHidden(1)] == [False, True]

    def test_check_all_skips_hidden_rows_and_partially_checked_items(self, table):
        self.make_rows(table, [("a", UNCHECKED, False), ("b", UNCHECKED, True), ("c", PARTIAL, False), ("d", CHECKED, False)])
        table.check_all()
        assert [table.item(r, 0).checkState() for r in range(4)] == [CHECKED, UNCHECKED, PARTIAL, CHECKED]

    def test_uncheck_all_only_unchecks_checked_items(self, table):
        self.make_rows(table, [("a", CHECKED, False), ("b", CHECKED, True), ("c", PARTIAL, False)])
        table.uncheck_all()
        assert [table.item(r, 0).checkState() for r in range(3)] == [UNCHECKED, UNCHECKED, PARTIAL]

    def test_invert_selection_toggles_checked_and_unchecked_mod_items_only(self, table):
        self.make_rows(table, [("a", CHECKED, False), ("b", UNCHECKED, False), ("c", PARTIAL, False)])
        other_col = FakeItem("x")
        other_col._col = 3
        table.invert_selection([table.item(0, 0), table.item(1, 0), table.item(2, 0), other_col])
        assert [table.item(r, 0).checkState() for r in range(3)] == [UNCHECKED, CHECKED, PARTIAL]

    def test_export_writes_checked_visible_mods(self, table, tmp_path, monkeypatch):
        self.make_rows(table, [("a.esp", CHECKED, False), ("b.esp", CHECKED, True), ("c.esp", UNCHECKED, False),
                               ("d.esp", CHECKED, False)])
        out = tmp_path / "export.json"
        monkeypatch.setattr(table, "select_file_path", lambda *a, **k: str(out))
        shown = []
        monkeypatch.setattr(table, "create_confirmation", lambda *a, **k: types.SimpleNamespace(show=lambda: shown.append(a[0])))
        table.export_check_state_to_file()
        assert json.loads(out.read_text()) == ["a.esp", "d.esp"]
        assert shown == ["Success"]

    def test_export_cancelled_writes_nothing(self, table, monkeypatch, tmp_path):
        self.make_rows(table, [("a.esp", CHECKED, False)])
        monkeypatch.setattr(table, "select_file_path", lambda *a, **k: None)
        table.export_check_state_to_file()
        assert list(tmp_path.glob("*.json")) == []

    def import_with(self, table, monkeypatch, path):
        shown = []
        monkeypatch.setattr(table, "select_file_path", lambda *a, **k: path)
        monkeypatch.setattr(table, "create_confirmation", lambda title, *a, **k: types.SimpleNamespace(show=lambda: shown.append(title)))
        calls = []
        monkeypatch.setattr(table, "check_previous_func", lambda items, warn: calls.append((items, warn)))
        table.import_check_state_from_file()
        return shown, calls

    def test_import_unchecks_everything_then_selects_the_listed_mods(self, table, monkeypatch, tmp_path):
        self.make_rows(table, [("a.esp", CHECKED, False)])
        f = tmp_path / "in.json"
        f.write_text('["a.esp"]')
        shown, calls = self.import_with(table, monkeypatch, str(f))
        assert table.item(0, 0).checkState() == UNCHECKED
        assert calls == [(["a.esp"], False)]
        assert shown == ["Success"]

    def test_import_of_empty_missing_or_invalid_files(self, table, monkeypatch, tmp_path):
        empty = tmp_path / "e.json"
        empty.write_text("[]")
        assert self.import_with(table, monkeypatch, str(empty)) == (["Failed"], [])
        assert self.import_with(table, monkeypatch, str(tmp_path / "gone.json")) == (["Error"], [])
        bad = tmp_path / "bad.json"
        bad.write_text("{")
        assert self.import_with(table, monkeypatch, str(bad)) == ([], [])
        assert self.import_with(table, monkeypatch, None) == ([], [])

    def test_filter_search_hides_rows_that_do_not_match(self, table):
        self.make_rows(table, [("Alpha.esp", UNCHECKED, False), ("Beta.esp", UNCHECKED, False), ("Gamma.esp", UNCHECKED, True)])
        table.filter = FakeLineEdit("alp")
        table.filter_search()
        assert [table.isRowHidden(r) for r in range(3)] == [False, True, True]
        assert table.flash_timer_reminder.stopped == 1

    def test_filter_search_without_results_flashes(self, table):
        self.make_rows(table, [("Alpha.esp", UNCHECKED, False)])
        table.filter = FakeLineEdit("zzz")
        table.filter_search()
        assert table.isRowHidden(0)
        assert table.flash_anim.started == 1 and table.flash_timer_reminder.started == 1

    def test_empty_filter_restores_rows_except_hider_rows(self, table):
        self.make_rows(table, [("a", UNCHECKED, False), ("b", UNCHECKED, True)])
        table.setRowHidden(0, True)
        table.filter = FakeLineEdit("")
        table.filter_search()
        assert [table.isRowHidden(0), table.isRowHidden(1)] == [False, True]


# ------------------------------------------------------------------------------------------ compact list
def compact(lists, flag_dict, **attrs):
    t = list_compact.list_compactable()
    for k, v in attrs.items():
        setattr(t, k, v)
    t.flag_dict = flag_dict
    t.create_list()
    return t


def deps(*mods):
    return {m.lower(): [] for m in mods}


class TestCompactList:
    def data(self, workdir, mods, **extra):
        write_data(workdir, "dependency_dictionary.json", {**deps(*mods), **extra})

    def test_one_row_per_plugin_blacklisted_plugins_are_left_out(self, lists, workdir):
        self.data(workdir, ["A.esp", "B.esp", "C.esp"])
        write_data(workdir, "blacklist.json", ["B.esp"])
        t = compact(lists, {"/mods/A/A.esp": [], "/mods/B/B.esp": [], "/mods/C/C.esp": []})
        assert t.rowCount() == 2
        assert names(t) == ["A.esp", "C.esp"]

    def test_cell_master_mode_blacklists_the_creation_club_plugins(self, lists, workdir):
        write_data(workdir, "blacklist.json", [])
        flags = {"/d/A.esp": [], "/d/ccbgssse025-advdsgs.esm": []}
        self.data(workdir, ["A.esp", "ccbgssse025-advdsgs.esm"])
        assert names(compact(lists, flags, cell_master=True)) == ["A.esp"]
        assert names(compact(lists, flags, cell_master=False)) == ["A.esp", "ccbgssse025-advdsgs.esm"]

    def test_already_compacted_plugins_are_partially_checked_and_not_user_checkable(self, lists, workdir):
        self.data(workdir, ["A.esp", "B.esp"])
        write_data(workdir, "compacted_and_patched.json", {"A.esp": {}})
        t = compact(lists, {"/d/A.esp": [], "/d/B.esp": []})
        a, b = t.item(0, 0), t.item(1, 0)
        assert a.checkState() == PARTIAL and not (a.flags() & USER_CHECKABLE)
        assert b.checkState() == UNCHECKED and (b.flags() & USER_CHECKABLE)
        assert a.toolTip() == "/d/A.esp"

    def test_flags_become_items_in_their_columns(self, lists, workdir):
        self.data(workdir, ["A.esp"])
        write_data(workdir, "dll_dict.json", {"a.esp": ["/skse/x.dll", "/skse/y.dll"]})
        lists_global = _global
        lists_global.mods_with_seq = {"a.esp"}
        lists_global.pex_with_getmodbyname = {"a.esp": ["/p/s.pex"]}
        t = compact(lists, {"/d/A.esp": ["new_cell", "new_wrld", "new_wthr", "is_esm"]})
        assert t.item(0, t.CELL_COL).text() == "New CELL"
        assert t.item(0, t.WRLD_COL).text() == "!!New WRLD!!"
        assert t.item(0, t.WTHR_COL).text() == "!New WTHR!"
        assert t.item(0, t.ESM_COL).text() == "ESM"
        assert t.item(0, t.SEQ_COL).text() == "SEQ"
        assert t.item(0, t.PEX_COL).text() == "PEX" and "s.pex" in t.item(0, t.PEX_COL).toolTip()
        assert t.item(0, t.DLL_COL).text() == "!!SKSE DLL!!"
        assert "x.dll" in t.item(0, t.DLL_COL).toolTip() and "y.dll" in t.item(0, t.DLL_COL).toolTip()
        assert t.item(0, t.HIDER_COL) is None and not t.isRowHidden(0)

    def test_plugin_without_flags_has_no_flag_items(self, lists, workdir):
        self.data(workdir, ["A.esp"])
        t = compact(lists, {"/d/A.esp": []})
        assert [t.item(0, c) for c in range(1, t.COL_COUNT)] == [None] * (t.COL_COUNT - 1)

    def test_changed_new_cell_is_flagged_and_hidden_by_default(self, lists, workdir):
        self.data(workdir, ["A.esp", "B.esp"])
        write_data(workdir, "cell_changed.json", ["A.esp"])
        t = compact(lists, {"/d/A.esp": ["new_cell"], "/d/B.esp": ["new_cell"]})
        assert t.item(0, t.CELL_COL).text() == "!!New CELL Changed!!"
        assert t.item(1, t.CELL_COL).text() == "New CELL"
        assert hidden(t) == ["A.esp"]
        t = compact(lists, {"/d/A.esp": ["new_cell"]}, filter_changed_cells=False)
        assert hidden(t) == []

    def test_changed_cell_with_cell_master_and_maxed_masters(self, lists, workdir):
        self.data(workdir, ["A.esp", "B.esp"])
        write_data(workdir, "cell_changed.json", ["A.esp", "B.esp"])
        t = compact(lists, {"/d/A.esp": ["new_cell", "maxed_masters"], "/d/B.esp": ["new_cell"]}, cell_master=True)
        assert t.item(0, t.CELL_COL).text() == "!!Maxed Masters!!"
        assert t.item(1, t.CELL_COL).text() == "New CELL"
        assert not t.isColumnHidden(t.CELL_COL)

    def test_interior_cells_are_hidden_only_when_filtered(self, lists, workdir):
        self.data(workdir, ["A.esp"])
        flags = {"/d/A.esp": ["new_cell", "new_interior_cell"]}
        t = compact(lists, flags)
        assert t.item(0, t.CELL_COL).text() == "!New Interior CELL!" and hidden(t) == []
        assert hidden(compact(lists, flags, filter_interior_cells=True)) == ["A.esp"]

    def test_engine_fixes_v7_removes_the_cell_column_items(self, lists, workdir, monkeypatch):
        self.data(workdir, ["A.esp"])
        monkeypatch.setattr(_global, "engine_fixes_v7_or_newer", True)
        t = compact(lists, {"/d/A.esp": ["new_cell"]})
        assert t.item(0, t.CELL_COL) is None and t.isColumnHidden(t.CELL_COL)

    @pytest.mark.parametrize("flag,attrs", [
        (["new_cell"], {"show_cells": False}),
        (["new_wrld"], {"filter_worldspaces": True}),
        (["new_wthr"], {"filter_weather": True}),
        (["is_esm"], {"show_esms": False}),
    ])
    def test_rows_hidden_by_their_filter(self, lists, workdir, flag, attrs):
        self.data(workdir, ["A.esp"])
        assert hidden(compact(lists, {"/d/A.esp": flag}, **attrs)) == ["A.esp"]
        assert hidden(compact(lists, {"/d/A.esp": flag})) == []

    def test_dll_seq_and_pex_filters(self, lists, workdir):
        self.data(workdir, ["A.esp"])
        write_data(workdir, "dll_dict.json", {"a.esp": ["/x.dll"]})
        _global.mods_with_seq = {"a.esp"}
        _global.pex_with_getmodbyname = {"a.esp": ["/p.pex"]}
        flags = {"/d/A.esp": []}
        assert hidden(compact(lists, flags)) == []
        assert hidden(compact(lists, flags, show_dlls=False)) == ["A.esp"]
        assert hidden(compact(lists, flags, filter_seq=True)) == ["A.esp"]
        assert hidden(compact(lists, flags, filter_pex=True)) == ["A.esp"]

    def test_worldspaces_are_not_flagged_in_cell_master_mode(self, lists, workdir):
        self.data(workdir, ["A.esp"])
        t = compact(lists, {"/d/A.esp": ["new_wrld"]}, cell_master=True)
        assert t.item(0, t.WRLD_COL) is None

    def test_plugins_with_dependencies_get_a_show_button(self, lists, workdir):
        write_data(workdir, "dependency_dictionary.json", {"a.esp": ["/d/b.esp"], "b.esp": []})
        t = compact(lists, {"/d/A.esp": [], "/d/B.esp": []})
        assert t.cellWidget(0, t.DEP_COL) is not None and t.cellWidget(1, t.DEP_COL) is None

    def test_column_visibility_follows_the_settings(self, lists, workdir):
        self.data(workdir, [])
        t = compact(lists, {}, show_dlls=False, filter_seq=True, show_esms=False, hidden_columns="pex, dependents")
        assert t.isColumnHidden(t.DLL_COL) and t.isColumnHidden(t.SEQ_COL) and t.isColumnHidden(t.ESM_COL)
        assert t.isColumnHidden(t.PEX_COL) and t.isColumnHidden(t.DEP_COL) and t.isColumnHidden(t.DEP_DISP_COL)
        assert not t.isColumnHidden(t.WTHR_COL)
        t = compact(lists, {}, filter_weather=True, filter_worldspaces=True)
        assert t.isColumnHidden(t.WTHR_COL) and t.isColumnHidden(t.WRLD_COL)

    def test_previous_exists_flag(self, lists, workdir):
        self.data(workdir, [])
        assert compact(lists, {}).previous_exists is False
        write_data(workdir, "previously_compacted.json", [])
        assert compact(lists, {}).previous_exists is True


class TestCheckPreviouslyCompacted:
    @pytest.fixture
    def t(self, lists, workdir):
        write_data(workdir, "dependency_dictionary.json", deps("A.esp", "B.esp", "C.esp", "D.esp"))
        write_data(workdir, "cell_changed.json", ["D.esp"])
        return compact(lists, {"/d/A.esp": [], "/d/B.esp": [], "/d/C.esp": [], "/d/D.esp": ["new_cell"]},
                       )

    def states(self, t):
        return {t.item(r, 0).text(): t.item(r, 0).checkState() for r in range(t.rowCount())}

    def test_selects_listed_plugins_that_are_available(self, t):
        t.check_previously_compacted(["A.esp", "C.esp"])
        assert self.states(t) == {"A.esp": CHECKED, "B.esp": UNCHECKED, "C.esp": CHECKED, "D.esp": UNCHECKED}
        assert Warnings.calls == []

    def test_reads_the_previously_compacted_file_when_no_list_is_given(self, t, workdir):
        write_data(workdir, "previously_compacted.json", ["B.esp"])
        t.check_previously_compacted()
        assert self.states(t)["B.esp"] == CHECKED

    def test_missing_file_and_no_list_does_nothing(self, t):
        t.check_previously_compacted()
        assert set(self.states(t).values()) == {UNCHECKED} and Warnings.calls == []

    def test_hidden_and_already_checked_rows_are_not_reselected(self, t):
        t.item(0, 0).setCheckState(PARTIAL)
        t.check_previously_compacted(["A.esp", "D.esp"])
        assert self.states(t)["A.esp"] == PARTIAL
        assert self.states(t)["D.esp"] == UNCHECKED                    # hidden: changed new CELL

    def test_short_warning_when_the_warning_is_not_wanted_in_full(self, t):
        t.check_previously_compacted(["A.esp", "Gone.esp"], full_warning=False)
        (title, text), = Warnings.calls
        assert title == "Warning" and "- Gone.esp" in text and "A.esp" not in text

    def test_full_warning_sorts_unselectable_plugins_into_reasons(self, t, workdir, monkeypatch):
        write_data(workdir, "missing_game_as_master.json", {"/d/Dep.esp": "B.esp"})
        write_data(workdir, "compacted_and_patched.json", {"C.esp": {}})
        monkeypatch.setattr(_global, "plugins", ["/d/A.esp", "/d/B.esp", "/d/C.esp", "/d/D.esp"])
        t.item(1, 0).setCheckState(PARTIAL)                              # B and C cannot be re-selected
        t.item(2, 0).setCheckState(PARTIAL)
        t.check_previously_compacted(["B.esp", "C.esp", "D.esp", "Deleted.esp"])
        (title, text), = Warnings.calls
        assert "- B.esp\n   | Dep.esp" in text                         # has a dependent missing Skyrim.esm
        assert "no longer meet the conditions" in text and "- D.esp" in text   # hidden by filter, not in compacted_and_patched
        assert "- C.esp" not in text                                       # in compacted_and_patched: nothing to warn about
        assert "no-longer exist" in text and "- Deleted.esp" in text
        assert text.rstrip().endswith("Please be careful.")

    def test_errors_are_logged_instead_of_raised(self, t, workdir, log):
        (workdir / "ESLifier_Data" / "previously_compacted.json").write_text("{bad", encoding="utf-8")
        t.check_previously_compacted()
        assert any("previously_compacted.json" in e for e in log.errors)


# ------------------------------------------------------------------------------------------ eslify list
def eslify(lists, flag_dict, **attrs):
    t = list_eslify.list_eslable()
    for k, v in attrs.items():
        setattr(t, k, v)
    t.flag_dict = flag_dict
    t.create_list()
    return t


class TestEslifyList:
    def test_rows_blacklist_and_flagged_state(self, lists, workdir):
        write_data(workdir, "blacklist.json", ["B.esp"])
        write_data(workdir, "esl_flagged.json", ["C.esp"])
        t = eslify(lists, {"/d/A.esp": [], "/d/B.esp": [], "/d/C.esp": []})
        assert names(t) == ["A.esp", "C.esp"]
        assert t.item(0, 0).checkState() == UNCHECKED and (t.item(0, 0).flags() & USER_CHECKABLE)
        assert t.item(1, 0).checkState() == PARTIAL and not (t.item(1, 0).flags() & USER_CHECKABLE)

    def test_flag_items_and_hiding(self, lists, workdir):
        _global.mods_with_seq = {"a.esp"}
        _global.pex_with_getmodbyname = {"a.esp": ["/p.pex"]}
        write_data(workdir, "cell_changed.json", ["A.esp"])
        flags = {"/d/A.esp": ["new_cell", "new_wrld", "is_esm"]}
        t = eslify(lists, flags)
        assert t.item(0, t.CELL_COL).text() == "!!New CELL Changed!!"
        assert t.item(0, t.WRLD_COL).text() == "!!New WRLD!!"
        assert t.item(0, t.SEQ_COL).text() == "SEQ" and t.item(0, t.PEX_COL).text() == "PEX"
        assert t.item(0, t.ESM_COL).text() == "ESM"
        assert hidden(t) == ["A.esp"]                                   # changed new CELL is filtered by default
        assert hidden(eslify(lists, flags, filter_changed_cells=False)) == []
        assert hidden(eslify(lists, flags, filter_changed_cells=False, filter_worldspaces=True)) == ["A.esp"]
        assert hidden(eslify(lists, flags, filter_changed_cells=False, show_esms=False)) == ["A.esp"]
        assert hidden(eslify(lists, flags, filter_changed_cells=False, filter_seq=True)) == ["A.esp"]
        assert hidden(eslify(lists, flags, filter_changed_cells=False, filter_pex=True)) == ["A.esp"]

    def test_column_visibility(self, lists, workdir):
        t = eslify(lists, {}, show_cells=False, filter_seq=True, hidden_columns="pex,esm")
        assert t.isColumnHidden(t.CELL_COL) and t.isColumnHidden(t.SEQ_COL)
        assert t.isColumnHidden(t.PEX_COL) and t.isColumnHidden(t.ESM_COL)
        t = eslify(lists, {}, cell_master=True)
        assert t.isColumnHidden(t.WRLD_COL) and not t.isColumnHidden(t.CELL_COL)

    def test_cell_master_blacklists_the_creation_club_plugins(self, lists, workdir):
        flags = {"/d/A.esp": [], "/d/cceejsse005-cave.esm": []}
        assert names(eslify(lists, flags, cell_master=True)) == ["A.esp"]

    def test_check_previously_esl_flagged(self, lists, workdir, monkeypatch):
        t = eslify(lists, {"/d/A.esp": [], "/d/B.esp": []})
        t.check_previously_esl_flagged(["B.esp", "Gone.esp"])
        assert [t.item(r, 0).checkState() for r in range(2)] == [UNCHECKED, CHECKED]
        (title, text), = Warnings.calls
        assert "re-ESL flagged" in text and "- Gone.esp" in text

    def test_check_previously_esl_flagged_short_warning_and_file(self, lists, workdir):
        t = eslify(lists, {"/d/A.esp": []})
        write_data(workdir, "previously_esl_flagged.json", ["A.esp", "Missing.esp"])
        t.check_previously_esl_flagged(full_warning=False)
        assert t.item(0, 0).checkState() == CHECKED
        (title, text), = Warnings.calls
        assert "already flagged ESL" in text and "- Missing.esp" in text

    def test_previous_file_flag(self, lists, workdir):
        assert eslify(lists, {}).previous_exists is False
        write_data(workdir, "previously_esl_flagged.json", [])
        assert eslify(lists, {}).previous_exists is True
