"""
vortex_database_reader.VortexDBParser: reads Vortex's state either straight from its LevelDB (when Vortex is
closed) or from the live Redux state exposed by ESLifier's Vortex extension (when Vortex is running).
plyvel (LevelDB) and the extension's HTTP endpoint are replaced with in-memory fakes.
"""
import json
import os
import time

import pytest

import scanners.vortex_database_reader as vdr
from data_holder import _global
from scanners.vortex_database_reader import ReadState, VortexDBParser


# ------------------------------------------------------------------------------------------ fakes
class FakeIOError(Exception):
    pass


class FakeDB:
    """Stands in for plyvel.DB: a sorted in-memory key/value store."""
    items: dict = {}
    open_error = None

    def __init__(self, path):
        if FakeDB.open_error:
            raise FakeDB.open_error
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def iterator(self, prefix=b""):
        for k in sorted(FakeDB.items):
            if k.startswith(prefix):
                yield k, FakeDB.items[k]

    def prefixed_db(self, prefix):
        outer = FakeDB.items

        class Prefixed:
            def get(self, key, default=None):
                return outer.get(prefix + key, default)

        return Prefixed()


@pytest.fixture
def fake_db(monkeypatch):
    FakeDB.items = {}
    FakeDB.open_error = None
    monkeypatch.setattr(vdr.plyvel, "DB", FakeDB, raising=False)
    monkeypatch.setattr(vdr.plyvel, "IOError", FakeIOError, raising=False)
    return FakeDB


def put(key: str, value):
    FakeDB.items[key.encode()] = json.dumps(value).encode()


@pytest.fixture
def parser(monkeypatch, workdir):
    """Clean VortexDBParser class state and a vortex data folder in the temp dir."""
    monkeypatch.setattr(VortexDBParser, "state", {})
    monkeypatch.setattr(VortexDBParser, "last_query", None)
    monkeypatch.setattr(VortexDBParser, "get_section", VortexDBParser.get_section)
    monkeypatch.setattr(VortexDBParser, "get_key_value", VortexDBParser.get_key_value)
    _global.vortex_data_path = str(workdir / "vortex")
    _global.vortex_db_path = str(workdir / "vortex" / "state.v2")
    calls = []
    monkeypatch.setattr(_global, "get_paths", lambda: calls.append("get_paths") or True)
    return calls


def make_extension(workdir, port="4242"):
    ext = workdir / "vortex" / "plugins" / "ESLifier Vortex State Getter"
    ext.mkdir(parents=True)
    if port is not None:
        (ext / "port.txt").write_text(port + "\n", encoding="utf-8")
    return ext


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def serve_state(monkeypatch, payload=None, error=None):
    seen = []

    def urlopen(req):
        seen.append(req.full_url)
        if error:
            raise error
        return FakeResponse(payload)

    monkeypatch.setattr(vdr.urllib.request, "urlopen", urlopen)
    return seen


# ------------------------------------------------------------------------------------------ reading the LevelDB
def test_get_section_from_db_builds_a_nested_dict_from_the_key_path(fake_db):
    put("persistent###mods###skyrimse###ModA###enabled", True)
    put("persistent###mods###skyrimse###ModA###rules", [{"type": "before"}])
    put("persistent###mods###skyrimse###ModB###enabled", False)
    put("persistent###mods###fallout4###Other###enabled", True)       # different game: excluded
    result = VortexDBParser.get_section_from_db("persistent###mods###skyrimse")
    assert result == {"ModA": {"enabled": True, "rules": [{"type": "before"}]}, "ModB": {"enabled": False}}


def test_get_section_from_db_accepts_a_trailing_separator(fake_db):
    put("a###b###c", 1)
    assert VortexDBParser.get_section_from_db("a###b###") == {"c": 1}


def test_get_section_from_db_skips_values_that_are_not_json(fake_db):
    put("a###good", 1)
    FakeDB.items[b"a###bad"] = b"{not json"
    assert VortexDBParser.get_section_from_db("a") == {"good": 1}


def test_get_section_from_db_for_missing_section_is_empty(fake_db):
    assert VortexDBParser.get_section_from_db("nothing###here") == {}


def test_get_key_value_from_db_returns_the_stored_string(fake_db):
    FakeDB.items[b"settings###mods###installPath###skyrimse"] = b"C:\\Vortex\\skyrimse\\mods"
    assert VortexDBParser.get_key_value_from_db("settings###mods###installPath###skyrimse###") == "C:\\Vortex\\skyrimse\\mods"
    assert VortexDBParser.get_key_value_from_db("settings###mods###installPath###skyrimse") == "C:\\Vortex\\skyrimse\\mods"


def test_get_key_value_from_db_missing_key_is_empty_string(fake_db):
    assert VortexDBParser.get_key_value_from_db("settings###mods###installPath###skyrimse###") == ""


# ------------------------------------------------------------------------------------------ reading the live state
STATE = {"settings": {"mods": {"installPath": {"skyrimse": "C:\\staging"}}, "profiles": {"lastActiveProfile": {"skyrimse": "p1"}}},
         "persistent": {"mods": {"skyrimse": {"ModA": {"enabled": True}}}}}


def test_get_section_from_state_walks_the_nested_state(parser):
    VortexDBParser.state = STATE
    assert VortexDBParser.get_section_from_state("persistent###mods###skyrimse###") == {"ModA": {"enabled": True}}
    assert VortexDBParser.get_section_from_state("settings###profiles") == {"lastActiveProfile": {"skyrimse": "p1"}}


def test_get_section_from_state_for_missing_path_is_empty(parser):
    VortexDBParser.state = STATE
    assert VortexDBParser.get_section_from_state("persistent###nope###deeper") == {}


def test_get_key_value_from_state_returns_the_value_or_none(parser):
    VortexDBParser.state = STATE
    assert VortexDBParser.get_key_value_from_state("settings###mods###installPath###skyrimse###") == "C:\\staging"
    assert VortexDBParser.get_key_value_from_state("settings###mods###installPath###fallout4###") is None


def test_get_live_vortex_state_requests_the_port_from_port_txt(parser, workdir, monkeypatch):
    make_extension(workdir, port="5151")
    seen = serve_state(monkeypatch, STATE)
    assert VortexDBParser.get_live_vortex_state() == STATE
    assert seen == ["http://127.0.0.1:5151/export-state"]


def test_get_live_vortex_state_failure_is_logged(parser, workdir, monkeypatch, log):
    make_extension(workdir)
    serve_state(monkeypatch, error=OSError("connection refused"))
    assert VortexDBParser.get_live_vortex_state() == ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE
    assert any("Failed to get state from Vortex" in line for line in log.file_lines)
    assert any("connection refused" in line for line in log.file_lines)


# ------------------------------------------------------------------------------------------ is_readable
def test_closed_vortex_uses_the_database(parser, fake_db, log):
    assert VortexDBParser.is_readable() == ReadState.SUCCESS_DB
    assert VortexDBParser.get_section == VortexDBParser.get_section_from_db
    assert VortexDBParser.get_key_value == VortexDBParser.get_key_value_from_db
    assert parser == ["get_paths"]
    assert any("using Vortex DB" in line for line in log.file_lines)


def test_locked_database_falls_back_to_the_extension_state(parser, fake_db, workdir, monkeypatch):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    serve_state(monkeypatch, STATE)
    assert VortexDBParser.is_readable() == ReadState.SUCCESS_STATE
    assert VortexDBParser.state == STATE
    assert VortexDBParser.get_section == VortexDBParser.get_section_from_state
    assert VortexDBParser.get_key_value == VortexDBParser.get_key_value_from_state
    assert VortexDBParser.last_query is not None
    assert parser == ["get_paths"]


def test_vortex_deploying_cancels_the_action(parser, fake_db, workdir, monkeypatch, log):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    serve_state(monkeypatch, {"deploying__eslifier_tag": True})
    assert VortexDBParser.is_readable() == ReadState.ERROR_DB_LOCKED_DEPLOYING
    assert any("deploying" in line for line in log.file_lines)


def test_vortex_purging_cancels_the_action(parser, fake_db, workdir, monkeypatch):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    serve_state(monkeypatch, {"purging__eslifier_tag": True})
    assert VortexDBParser.is_readable() == ReadState.ERROR_DB_LOCKED_PURGING


def test_locked_database_without_the_extension_installed(parser, fake_db):
    FakeDB.open_error = FakeIOError("locked")
    assert VortexDBParser.is_readable() == ReadState.ERROR_DB_LOCKED_EXTENSION_MISSING


def test_locked_database_with_extension_that_has_not_started(parser, fake_db, workdir):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir, port=None)                              # folder exists but no port.txt
    assert VortexDBParser.is_readable() == ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE


def test_locked_database_and_unreachable_extension_is_reported(parser, fake_db, workdir, monkeypatch):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    serve_state(monkeypatch, error=OSError("connection refused"))
    assert VortexDBParser.is_readable() == ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE


def test_recent_state_is_reused_instead_of_querying_vortex_again(parser, fake_db, workdir, monkeypatch, log):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    seen = serve_state(monkeypatch, STATE)
    assert VortexDBParser.is_readable() == ReadState.SUCCESS_STATE
    assert VortexDBParser.is_readable() == ReadState.SUCCESS_STATE
    assert len(seen) == 1                                          # second call used the cached state
    assert any("using cached Vortex state" in line for line in log.file_lines)


def test_state_older_than_five_seconds_is_refreshed(parser, fake_db, workdir, monkeypatch):
    FakeDB.open_error = FakeIOError("locked")
    make_extension(workdir)
    seen = serve_state(monkeypatch, STATE)
    VortexDBParser.is_readable()
    VortexDBParser.last_query = time.monotonic() - 6
    VortexDBParser.is_readable()
    assert len(seen) == 2


def test_unexpected_database_error_is_returned_when_no_cached_state_exists(parser, fake_db, monkeypatch):
    FakeDB.open_error = RuntimeError("weird")
    VortexDBParser.last_query = time.monotonic()                   # recent query, but nothing cached
    result = VortexDBParser.is_readable()
    assert isinstance(result, RuntimeError)
