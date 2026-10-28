"""MO2 plugin notification dialog: columns depend on the game."""
import importlib

import pytest

import test_mo2_qualification_checker  # noqa: F401  (builds the "mo2_plugin" package shell)

display = importlib.import_module("mo2_plugin.ESLifier_notification_display")


class Item:
    def __init__(self, text=""):
        self.text, self.tip = text, ""

    def setText(self, text): self.text = text
    def setToolTip(self, tip): self.tip = tip


class Table:
    EditTrigger = type("E", (), {"NoEditTriggers": 0})

    def __init__(self):
        self.cols, self.items, self.hidden, self.headers = 0, {}, set(), []

    def setColumnCount(self, n): self.cols = n
    def setItem(self, row, col, item):
        assert col < self.cols, f"column {col} does not exist"
        self.items[(row, col)] = item
    def hideColumn(self, col): self.hidden.add(col)
    def showColumn(self, col): self.hidden.discard(col)
    def setHorizontalHeaderLabels(self, labels): self.headers = list(labels)
    def __getattr__(self, name): return lambda *a, **k: self


def dialog(monkeypatch, mode, cell_master=False):
    monkeypatch.setattr(display, "QTableWidget", Table)
    monkeypatch.setattr(display, "QTableWidgetItem", Item)
    monkeypatch.setattr(display.notification_display_dialog, "setLayout", lambda *a: None, raising=False)
    d = display.notification_display_dialog("icons", mode)
    d.cell_master = cell_master
    return d


def texts(table):
    return {k: v.text for k, v in table.items.items()}


def test_sse_columns(monkeypatch):
    d = dialog(monkeypatch, "SSE")
    t = d.needs_compacting_flag_table
    d.populate_flag_table(t, {"a.esm": ["new_cell", "new_wrld", "new_wthr"]}, weather=True)
    assert t.cols == 4 and t.headers == ["Mod", "Cell Flag", "Worldspace Flag", "Weather Flag"]
    assert texts(t) == {(0, 0): "a.esm", (0, 1): "New CELL", (0, 2): "New Worldspace", (0, 3): "New Weather"}


def test_sse_changed_cell_and_maxed_masters(monkeypatch):
    d = dialog(monkeypatch, "SSE")
    t = d.needs_flag_table
    d.populate_flag_table(t, {"a.esm": ["new_cell", "cell_changed"], "b.esm": ["new_cell", "new_interior_cell"]})
    assert texts(t)[(0, 1)] == "!!New CELL Changed!!" and texts(t)[(1, 1)] == "New Interior CELL"
    d = dialog(monkeypatch, "SSE", cell_master=True)
    t = d.needs_flag_table
    d.populate_flag_table(t, {"a.esm": ["new_cell", "cell_changed", "maxed_masters"], "b.esm": ["new_cell", "cell_changed"]})
    assert texts(t)[(0, 1)] == "!!Maxed Masters!!" and texts(t)[(1, 1)] == "New CELL"


def test_fo4_only_has_mod_and_previs_columns(monkeypatch):
    d = dialog(monkeypatch, "FO4")
    t = d.needs_flag_table
    d.populate_flag_table(t, {"a.esp": ["new_cell", "has_previs_precombines"], "b.esp": ["new_cell", "cell_changed"],
                              "c.esp": ["new_cell"]})
    assert t.cols == 2 and t.headers == ["Mod", "PreVis/PreCombine"]
    assert texts(t) == {(0, 0): "a.esp", (0, 1): "PreVis/PreCombine", (1, 0): "b.esp", (1, 1): "PreVis/PreCombine",
                        (2, 0): "c.esp"}
