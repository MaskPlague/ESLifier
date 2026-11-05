"""
Test doubles for driving ``main_page.main`` and its workers without Qt.

``make_page`` builds a ``main`` instance WITHOUT running ``__init__`` (which would build the whole window) and fills in just
the attributes the flow code reads. ``install_qt_stubs`` swaps the Qt names ``main_page`` imported for small stateful
stand-ins, so dialogs, buttons and list widgets can be inspected and "clicked" from a test.
"""
import types

import main.main_page as main_page


class Calls(list):
    """A callable that records how it was called: ``calls[0] == (args, kwargs)``."""

    def __call__(self, *args, **kwargs):
        self.append((args, kwargs))


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *args):
        for fn in list(self.slots):
            fn(*args)


class Recorder:
    """Stand-in for a pyqtSignal on a worker: remembers what was emitted."""

    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)


class FakeConfirm:
    """A confirmation dialog: ``accept()`` / ``reject()`` run the connected slots, like clicking Yes / No."""

    def __init__(self, color="", icon=None):
        self.color, self.icon = color, icon
        self.accepted, self.rejected = Signal(), Signal()
        self.text, self.shown = None, False

    def setText(self, text):
        self.text = text

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    def accept(self):
        self.accepted.emit()

    def reject(self):
        self.rejected.emit()

    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeRemovalConfirm(FakeConfirm):
    """What ``create_removal_confirmation`` returns: accepting runs ``function`` then ``next_function``."""

    def __init__(self, text, function, next_function=None):
        super().__init__()
        self.text = text
        self.accepted.connect(function)
        if next_function is not None:
            self.accepted.connect(next_function)
            self.rejected.connect(next_function)


class FakeList:
    """list_compact / list_eslify: only what main_page touches."""
    MOD_COL = 0

    def __init__(self, check_state_enum):
        self.flag_dict = {}
        self.created = 0
        self.fail_create = False
        self.rows = []  # list of check states
        self.hidden = set()
        self.check_previous_calls = 0
        self._cs = check_state_enum

    def create_list(self):
        if self.fail_create:
            raise RuntimeError("create_list failed")
        self.created += 1

    def check_previously_compacted(self):
        self.check_previous_calls += 1

    def check_previously_esl_flagged(self):
        self.check_previous_calls += 1

    def rowCount(self):
        return len(self.rows)

    def item(self, row, col):
        state = self.rows[row]
        return types.SimpleNamespace(checkState=lambda: state)

    def isRowHidden(self, row):
        return row in self.hidden


# ------------------------------------------------------------------------------------------------------------ Qt stubs
class _Enumish:
    """Any attribute is a stable child object, ``|`` is allowed: stands in for Qt enums and flags."""

    def __init__(self):
        self._children = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self._children.setdefault(name, _Enumish())

    def __or__(self, other):
        return self

    __ror__ = __or__


class _Dummy:
    """Absorbs any attribute access and call."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self

    def __call__(self, *args, **kwargs):
        return self


class FakeMessageBox(_Dummy):
    warnings = []
    StandardButton = _Enumish()
    ButtonRole = _Enumish()
    Icon = _Enumish()

    def __init__(self, *args, **kwargs):
        self.accepted = Signal()
        self.shown = False
        FakeMessageBox.instances.append(self)

    instances = []

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        FakeMessageBox.warnings.append((title, text))


class FakeButton(_Dummy):
    def __init__(self, text="", *args, **kwargs):
        self.text = text
        self.clicked = Signal()
        UI.buttons.append(self)

    def setText(self, text):
        self.text = text


class FakeListItem:
    def __init__(self, text=""):
        self._text, self._state, self._tip, self._data = text, None, "", None

    def flags(self):
        return 0

    def setFlags(self, flags):
        pass

    def setCheckState(self, state):
        self._state = state

    def checkState(self):
        return self._state

    def setToolTip(self, tip):
        self._tip = tip

    def toolTip(self):
        return self._tip

    def setData(self, role, data):
        self._data = data

    def data(self, role):
        return self._data


class FakeListWidget(_Dummy):
    EditTrigger = _Enumish()
    SelectionBehavior = _Enumish()
    SelectionMode = _Enumish()

    def __init__(self, *args, **kwargs):
        self.items = []
        self.itemChanged = Signal()
        UI.list_widgets.append(self)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]

    def selectedItems(self):
        return []


class FakeDialog(_Dummy):
    def exec(self):
        if UI.on_dialog_exec:
            UI.on_dialog_exec()

    def close(self):
        pass


class UI:
    """State shared between the stubs and the test."""
    buttons = []
    list_widgets = []
    on_dialog_exec = None
    Qt = _Enumish()

    @classmethod
    def reset(cls):
        cls.buttons, cls.list_widgets, cls.on_dialog_exec = [], [], None
        FakeMessageBox.warnings, FakeMessageBox.instances = [], []

    @classmethod
    def click(cls, text):
        """Click the button whose label contains ``text`` (in the order they were created)."""
        for button in cls.buttons:
            if text in button.text:
                button.clicked.emit()
                return
        raise AssertionError(f"no button containing {text!r}: {[b.text for b in cls.buttons]}")


def install_qt_stubs(monkeypatch):
    UI.reset()
    app = types.SimpleNamespace(setOverrideCursor=Calls(), restoreOverrideCursor=Calls())
    replacements = {
        "Qt": UI.Qt, "QMessageBox": FakeMessageBox, "QDialog": FakeDialog, "QListWidget": FakeListWidget,
        "QListWidgetItem": FakeListItem, "QPushButton": FakeButton, "QLabel": _Dummy, "QLineEdit": _Dummy,
        "QWidget": _Dummy, "QVBoxLayout": _Dummy, "QHBoxLayout": _Dummy, "QTimer": _Dummy(), "QCursor": _Dummy,
        "QIcon": _Dummy, "QApplication": app,
    }
    for name, value in replacements.items():
        monkeypatch.setattr(main_page, name, value, raising=True)
    return app


def make_page(workdir, monkeypatch):
    """A ``main`` with its flow state set up and every collaborator replaced by a recorder."""
    install_qt_stubs(monkeypatch)
    page = object.__new__(main_page.main)
    cs = UI.Qt.CheckState
    page.tr = lambda text, *a: text
    page.setEnabled = Calls()
    page.calculate_stats = Calls()
    page.compact_selected_clicked = Calls()
    page.eslify_selected_clicked = Calls()
    page.scan = Calls()
    page.log_stream = types.SimpleNamespace(show=Calls())
    page.patch_new = types.SimpleNamespace(finished_rebuilding=Calls(), scan_and_find=Calls())
    page.list_compact = FakeList(cs)
    page.list_eslify = FakeList(cs)
    page.skip_confirmations = {"TIMERS"}
    page.redoing_output = False
    page.patch_new_running = False
    page.patch_new_only_remove = False
    page.generate_cell_master = False
    page.cell_master_warned = True
    page.scanned = False
    page.start_time = 0
    page.dependency_dictionary = {}
    page.files_to_not_hash = set()
    page.output_folder_path = str(workdir / "mods")
    page.output_folder_name = "ESLifier_Output"
    page.output_folder_full = str(workdir / "mods" / "ESLifier_Output")
    page.game_folder_path = str(workdir / "game")
    page.confirms = []

    def create_confirmation(color="", icon=None):
        confirm = FakeConfirm(color, icon)
        page.confirms.append(confirm)
        return confirm

    page.create_confirmation = create_confirmation
    page.removal_confirms = []

    def create_removal_confirmation(text, function, next_function=None):
        confirm = FakeRemovalConfirm(text, function, next_function)
        page.removal_confirms.append(confirm)
        return confirm

    page.create_removal_confirmation = create_removal_confirmation
    return page
