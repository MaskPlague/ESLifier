"""
blacklist.blacklist: the persistence logic behind ESLifier's blacklist table (load/save/add/remove).
The Qt widget machinery is stubbed out; only the JSON handling and list bookkeeping are exercised.
"""
import json
import sys
import types

import pytest


def _install_fake_qt_widgets():
    class Widget:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: None

    widgets = types.ModuleType("PyQt6.QtWidgets")
    for name in ("QAbstractItemView", "QMenu", "QTableWidget", "QTableWidgetItem", "QMainWindow", "QWidget",
                 "QHBoxLayout", "QVBoxLayout", "QPushButton", "QLineEdit"):
        setattr(widgets, name, type(name, (Widget,), {}))
    gui = types.ModuleType("PyQt6.QtGui")
    gui.QIcon = type("QIcon", (Widget,), {})
    sys.modules.setdefault("PyQt6.QtWidgets", widgets)
    sys.modules.setdefault("PyQt6.QtGui", gui)


_install_fake_qt_widgets()

import blacklist as bl  # noqa: E402  (needs the fake Qt modules first)

CHECKED, UNCHECKED = "checked", "unchecked"


class FakeItem:
    def __init__(self, text, state):
        self._text, self._state = text, state

    def text(self):
        return self._text

    def checkState(self):
        return self._state


@pytest.fixture
def table(workdir, monkeypatch):
    """A blacklist instance built without Qt, with the table rows replaced by a plain list."""
    monkeypatch.setattr(bl, "Qt", types.SimpleNamespace(
        CheckState=types.SimpleNamespace(Checked=CHECKED, Unchecked=UNCHECKED)))
    t = bl.blacklist.__new__(bl.blacklist)
    t.blacklist = []
    t.rows = []
    t.rebuilt = 0
    t.rowCount = lambda: len(t.rows)
    t.item = lambda row, col: t.rows[row]

    def rebuild():
        t.rebuilt += 1
    t.create_blacklist = rebuild
    return t


def saved(root):
    return json.loads((root / "ESLifier_Data" / "blacklist.json").read_text(encoding="utf-8"))


def seed(root, data):
    (root / "ESLifier_Data" / "blacklist.json").write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------------------------------------ get_data_from_file / dump_to_file
def test_get_data_from_file_missing_or_corrupt_gives_empty_list(table, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[oops", encoding="utf-8")
    assert table.get_data_from_file(str(tmp_path / "missing.json")) == []
    assert table.get_data_from_file(str(bad)) == []


def test_dump_and_load_roundtrip_keeps_unicode(table, tmp_path):
    table.blacklist = ["Bärenfell.esp", "B.esp"]
    out = tmp_path / "b.json"
    table.dump_to_file(str(out))
    assert "Bärenfell.esp" in out.read_text(encoding="utf-8")      # ensure_ascii=False
    assert table.get_data_from_file(str(out)) == ["Bärenfell.esp", "B.esp"]


def test_dump_to_file_failure_is_reported_not_raised(table, tmp_path, capsys):
    table.blacklist = ["A.esp"]
    table.dump_to_file(str(tmp_path / "nope" / "b.json"))
    assert "Failed to dump blacklist data" in capsys.readouterr().out


# ------------------------------------------------------------------------------ add_to_blacklist
def test_add_to_blacklist_creates_file_and_rebuilds_table(table, workdir):
    table.add_to_blacklist(["A.esp", "B.esp"])
    assert saved(workdir) == ["A.esp", "B.esp"]
    assert table.rebuilt == 1


def test_add_to_blacklist_keeps_existing_entries_and_skips_duplicates(table, workdir):
    seed(workdir, ["A.esp"])
    table.add_to_blacklist(["B.esp", "A.esp", "B.esp"])
    assert saved(workdir) == ["A.esp", "B.esp"]


def test_add_to_blacklist_rereads_file_each_time(table, workdir):
    table.blacklist = ["stale.esp"]                  # in-memory copy is out of date
    seed(workdir, ["A.esp"])
    table.add_to_blacklist(["B.esp"])
    assert saved(workdir) == ["A.esp", "B.esp"]


# ------------------------------------------------------------------------------ remove_from_blacklist
def test_remove_from_blacklist_removes_only_checked_rows(table, workdir):
    seed(workdir, ["A.esp", "B.esp", "C.esp"])
    table.rows = [FakeItem("A.esp", CHECKED), FakeItem("B.esp", UNCHECKED), FakeItem("C.esp", CHECKED)]
    table.remove_from_blacklist()
    assert saved(workdir) == ["B.esp"]
    assert table.rebuilt == 1


def test_remove_from_blacklist_with_nothing_checked_changes_nothing(table, workdir):
    seed(workdir, ["A.esp", "B.esp"])
    table.rows = [FakeItem("A.esp", UNCHECKED), FakeItem("B.esp", UNCHECKED)]
    table.remove_from_blacklist()
    assert saved(workdir) == ["A.esp", "B.esp"]


def test_remove_everything_leaves_empty_list(table, workdir):
    seed(workdir, ["A.esp"])
    table.rows = [FakeItem("A.esp", CHECKED)]
    table.remove_from_blacklist()
    assert saved(workdir) == []
