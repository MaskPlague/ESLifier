"""
scanner_none.NoManager: gathers files straight from the Skyrim Data folder (no mod manager).
"""
import os

import pytest

from data_holder import _global
from scanner_fakes import FakeScanner, touch
from scanner_none import NoManager


@pytest.fixture
def game(workdir, monkeypatch):
    """A fake scanner wired into NoManager and an empty 'Data' folder inside the temp dir."""
    fake = FakeScanner()
    monkeypatch.setattr(NoManager, "scanner", fake)
    data = workdir / "Data"
    data.mkdir()
    return fake, data


def rel(fake, data):
    """all_files as paths relative to the Data folder (extracted files keep their bsa_extracted path)."""
    return sorted(os.path.relpath(f, data).replace(os.sep, "/") for f in fake.all_files)


def test_creates_bsa_extracted_folder(game, workdir):
    fake, data = game
    NoManager.get_files_from_game_folder(str(data), [])
    assert (workdir / "bsa_extracted").is_dir()


def test_gathers_every_file_and_counts_them(game):
    fake, data = game
    touch(data / "a.esp")
    touch(data / "meshes" / "x.nif")
    touch(data / "meshes" / "deep" / "y.nif")
    NoManager.get_files_from_game_folder(str(data), [])
    assert rel(fake, data) == ["a.esp", "meshes/deep/y.nif", "meshes/x.nif"]
    assert fake.file_count == 3


def test_files_in_ignored_list_are_skipped_case_insensitively(game):
    fake, data = game
    fake.ignored_files = {"thumbs.db"}
    touch(data / "Thumbs.db")
    touch(data / "meshes" / "x.nif")
    NoManager.get_files_from_game_folder(str(data), [])
    assert rel(fake, data) == ["meshes/x.nif"]


def test_only_top_level_plugins_are_recorded(game):
    fake, data = game
    touch(data / "Top.esp")
    touch(data / "Top2.ESM")
    touch(data / "Top3.esl")
    touch(data / "nested" / "Nope.esp")
    NoManager.get_files_from_game_folder(str(data), [])
    assert sorted(os.path.basename(p) for p in _global.plugins) == ["Top.esp", "Top2.ESM", "Top3.esl"]
    assert "Nope.esp" in [os.path.basename(f) for f in fake.all_files]    # still gathered as a file


def test_top_level_bsas_are_sent_for_extraction_by_plugin_name(game):
    fake, data = game
    p1 = touch(data / "Mod One.bsa")
    p2 = touch(data / "Mod One - Textures.bsa")
    touch(data / "sub" / "Hidden.bsa")                # not top level -> ignored
    plugins = ["whatever"]
    NoManager.get_files_from_game_folder(str(data), plugins)
    (bsa_list, passed_plugins), = fake.bsa_calls
    assert passed_plugins is plugins
    assert sorted(bsa_list) == sorted([["mod one", p1], ["mod one", p2]])   # " - textures" suffix removed, lower-cased


def test_blacklisted_bsas_are_not_extracted(game):
    fake, data = game
    touch(data / "Skyrim - Misc.bsa")
    NoManager.get_files_from_game_folder(str(data), [])
    assert fake.bsa_calls[0][0] == []


def test_extracted_files_are_added_unless_a_loose_file_overrides_them(game, workdir):
    fake, data = game
    fake.files_to_extract = ["scripts/new.pex", "meshes/x.nif"]
    touch(data / "meshes" / "x.nif", b"loose")         # loose file shadows the BSA copy
    NoManager.get_files_from_game_folder(str(data), [])
    extracted = sorted(os.path.relpath(f, workdir / "bsa_extracted").replace(os.sep, "/")
                       for f in fake.all_files if str(workdir / "bsa_extracted") in f)
    assert extracted == ["scripts/new.pex"]
    assert not (workdir / "bsa_extracted" / "meshes" / "x.nif").exists()   # shadowed copy deleted
    assert (workdir / "bsa_extracted" / "scripts" / "new.pex").exists()


def test_extracted_files_in_ignored_list_are_skipped(game, workdir):
    fake, data = game
    fake.ignored_files = {"new.pex"}
    fake.files_to_extract = ["scripts/new.pex"]
    NoManager.get_files_from_game_folder(str(data), [])
    assert fake.all_files == []
