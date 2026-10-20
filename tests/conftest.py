"""
Shared pytest setup for the ESLifier regression suite.

ESLifier's core logic lives in ``src/`` and is imported as top-level modules
(``from file_patchers import patchers``). Several modules import PyQt6 or the
Qt-based ``log_stream`` at import time, and ``compact_form_ids`` imports
pywin32 on Windows. None of that matters for the logic under test, so this
conftest:

  * puts ``src/`` on ``sys.path``
  * installs lightweight stand-ins for ``PyQt6`` and ``log_stream`` *before*
    any ESLifier module is imported
  * resets the ``_global`` settings holder and switches into a temp working
    directory for every test (ESLifier reads/writes ``ESLifier_Data/...``
    relative to the cwd)

Run with:  python -m pytest tests -v
"""
import os
import sys
import types

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
# ESLIFIER_SRC lets the same tests run against another checkout's src/ (e.g. a newer version of the program)
SRC_DIR = os.environ.get("ESLIFIER_SRC") or os.path.join(REPO_ROOT, "src")

for p in (SRC_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)


# --------------------------------------------------------------------------- #
# Stand-ins for PyQt6 and log_stream
# --------------------------------------------------------------------------- #
class _FakeQCoreApplication:
    @staticmethod
    def translate(context, text, *args, **kwargs):
        return text


class _Anything:
    """Placeholder class usable as a base class or callable."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *args, **kwargs):
        return _Anything()


def _install_fake_pyqt():
    pyqt6 = types.ModuleType("PyQt6")
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.QCoreApplication = _FakeQCoreApplication
    qtcore.Qt = _Anything()
    qtcore.QThread = _Anything
    qtcore.QObject = _Anything
    qtcore.QTimer = _Anything
    qtcore.QItemSelection = _Anything
    qtcore.QVariantAnimation = _Anything
    qtcore.pyqtSignal = lambda *a, **k: _Anything()
    pyqt6.QtCore = qtcore
    sys.modules["PyQt6"] = pyqt6
    sys.modules["PyQt6.QtCore"] = qtcore


class LogRecorder:
    """Collects everything ESLifier would have written to its log window."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.file_lines = []
        self.normal = []
        self.warnings = []
        self.errors = []
        self.ineligible = []

    def _text(self, text):
        return str(text)


LOG = LogRecorder()


def _install_fake_log_stream():
    mod = types.ModuleType("log_stream")

    def write_to_file(text):
        LOG.file_lines.append(LOG._text(text))

    def write_normal(text, to_file=True):
        LOG.normal.append(LOG._text(text))

    def write_remove(*a, **k):
        pass

    def write_insert(*a, **k):
        pass

    def write_progress(*a, **k):
        pass

    def write_patching(*a, **k):
        pass

    def write_warning(text):
        LOG.warnings.append(LOG._text(text))

    def write_error(text, is_exception_msg=False):
        LOG.errors.append(LOG._text(text))

    def write_ineligible(text):
        LOG.ineligible.append(LOG._text(text))

    def clear_and_close_log():
        pass

    def clear_and_leave_log_open():
        pass

    for fn in (write_to_file, write_normal, write_remove, write_insert, write_progress,
               write_patching, write_warning, write_error, write_ineligible,
               clear_and_close_log, clear_and_leave_log_open):
        setattr(mod, fn.__name__, fn)
    mod.DEBUG = False
    sys.modules["log_stream"] = mod


def _install_fake_qt_widgets_and_gui():
    """Generic stand-ins for PyQt6.QtWidgets / PyQt6.QtGui: any name imported from them becomes a no-op class."""
    class _WidgetMeta(type):
        def __getattr__(cls, name):
            # class-level enums such as QMessageBox.Icon.Warning or QTableWidget.EditTrigger.NoEditTriggers
            if name.startswith("__"):
                raise AttributeError(name)
            return _Anything()

    class _Widget(metaclass=_WidgetMeta):
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: None

    def make_module(modname):
        mod = types.ModuleType(modname)
        classes = {}

        def module_getattr(name):
            if name.startswith("__"):
                raise AttributeError(name)
            if name not in classes:
                classes[name] = type(name, (_Widget,), {})
            return classes[name]

        mod.__getattr__ = module_getattr
        return mod

    sys.modules.setdefault("PyQt6.QtWidgets", make_module("PyQt6.QtWidgets"))
    sys.modules.setdefault("PyQt6.QtGui", make_module("PyQt6.QtGui"))


def _install_fake_plyvel():
    """plyvel (LevelDB bindings, used only for Vortex's database) is a native package; stub it if absent."""
    try:
        import plyvel  # noqa: F401
    except ImportError:
        sys.modules["plyvel"] = types.ModuleType("plyvel")


_install_fake_pyqt()
_install_fake_qt_widgets_and_gui()
_install_fake_log_stream()
_install_fake_plyvel()


def _install_layout_compat():
    """
    Newer ESLifier layouts split ``src/`` into packages (scanners/, patchers/, lists/), rename a few modules and
    take their game from ``data_holder.GAME_MODE`` (run_sse_mode.py sets it to "SSE" before anything else is imported).
    The tests refer to the original flat module names, so for the newer layout set SSE mode and alias the old names
    to the new modules. Nothing changes for the original layout.
    """
    if not os.path.isdir(os.path.join(SRC_DIR, "scanners")):
        return
    import importlib

    import data_holder
    data_holder.GAME_MODE = "SSE"
    data_holder.update_game_globals()
    aliases = {
        "file_patchers": "patchers.sse_file_patchers",
        "patcher_conditions": "patchers.sse_patcher_conditions",
        "file_defined_patcher_conditions": "patchers.file_defined_patcher_conditions",
        "full_form_processor": "full_form_processor_sse",
        "scanner": "scanners.scanner",
        "scanner_mo2": "scanners.scanner_mo2",
        "scanner_none": "scanners.scanner_none",
        "scanner_vortex": "scanners.scanner_vortex",
        "vortex_database_reader": "scanners.vortex_database_reader",
        "cell_changed_scanner": "scanners.cell_changed_scanner",
        "dependency_getter": "scanners.dependency_getter",
        "plugin_qualification_checker": "scanners.plugin_qualification_checker",
        "list_parent": "lists.list_parent",
        "list_compact": "lists.list_compact",
        "list_eslify": "lists.list_eslify",
    }
    for old, new in aliases.items():
        sys.modules[old] = importlib.import_module(new)


_install_layout_compat()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def log():
    LOG.reset()
    return LOG


_GLOBAL_DEFAULTS = None


@pytest.fixture
def g():
    """The ``_global`` settings holder, restored to its import-time defaults."""
    global _GLOBAL_DEFAULTS
    from data_holder import _global

    if _GLOBAL_DEFAULTS is None:
        _GLOBAL_DEFAULTS = {
            k: (v.copy() if isinstance(v, (dict, list, set)) else v)
            for k, v in vars(_global).items()
            if not k.startswith("__") and not callable(v)
        }
    for k, v in _GLOBAL_DEFAULTS.items():
        setattr(_global, k, v.copy() if isinstance(v, (dict, list, set)) else v)
    yield _global
    for k, v in _GLOBAL_DEFAULTS.items():
        setattr(_global, k, v.copy() if isinstance(v, (dict, list, set)) else v)


@pytest.fixture
def workdir(tmp_path, monkeypatch, log, g):
    """
    Temp cwd containing the ``ESLifier_Data`` folders ESLifier expects, with
    ``_global`` pointed at it. Returns the tmp path.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ESLifier_Data").mkdir()
    (tmp_path / "ESLifier_Data" / "Form_ID_Maps").mkdir()
    g.cwd = str(tmp_path)
    return tmp_path
