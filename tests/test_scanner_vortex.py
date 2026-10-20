"""
scanner_vortex.Vortex: works out Vortex's load order (from mod rules), which mod wins each file (honouring
Vortex "file overrides"/yields), and gathers files from the mod staging folder and Skyrim's Data folder.

Vortex's database is replaced by an in-memory dict keyed by the section string; folders are real temp dirs.
"""
import os

import pytest

from data_holder import _global
from scanner_fakes import FakeScanner, touch
from scanners.scanner_vortex import Vortex, VortexErrors
from scanners.vortex_database_reader import ReadState, VortexDBParser

DATA_SENTINEL = "data_folder_file_eslifier_scan"
BSA_SENTINEL = "archive_extracted_eslifier_scan"


def p(*parts):
    return os.path.join(*parts)


@pytest.fixture
def db(monkeypatch, g):
    """In-memory Vortex database: sections[section_string] -> dict, values[key_string] -> str."""
    class Db:
        sections = {}
        values = {}

    monkeypatch.setattr(VortexDBParser, "get_section", lambda s: Db.sections.get(s))
    monkeypatch.setattr(VortexDBParser, "get_key_value", lambda s: Db.values.get(s))
    return Db


def mod_state(**mods):
    """mod_state(A=True, B=("b-lfn", True)) -> Vortex profile modState"""
    out = {}
    for mod_id, v in mods.items():
        if isinstance(v, tuple):
            lfn, enabled = v
            out[mod_id] = {"enabled": enabled, "logicalFileName": lfn}
        else:
            out[mod_id] = {"enabled": v}
    return out


def rule(kind, **ref):
    return {"type": kind, "reference": ref}


def order(db, states, installed=None, profile="p1"):
    db.sections["persistent###profiles###"] = {profile: {"modState": states}}
    load_order, returned = Vortex.get_load_order(profile, installed or {})
    return load_order, returned


# ------------------------------------------------------------------------------------------ get_load_order
def test_enabled_mods_without_rules_are_all_listed_and_disabled_ones_are_not(db):
    load_order, _ = order(db, mod_state(A=True, B=True, C=False))
    assert sorted(load_order) == ["A", "B"]
    assert _global.vortex_error is None


def test_unknown_profile_gives_an_empty_load_order(db):
    db.sections["persistent###profiles###"] = {}
    assert Vortex.get_load_order("nope", {}) == ([], {})


def test_missing_profiles_section_gives_an_empty_load_order(db):
    assert Vortex.get_load_order("p1", {}) == ([], {})


def test_returns_the_installed_mods_it_was_given(db):
    installed = {"A": {"rules": []}}
    _, returned = order(db, mod_state(A=True), installed)
    assert returned is installed


def test_before_rule_by_id_puts_the_mod_ahead_of_its_target(db):
    installed = {"A": {"rules": [rule("before", id="B")]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert load_order == ["A", "B"]


def test_after_rule_by_id_puts_the_mod_behind_its_target(db):
    installed = {"A": {"rules": [rule("after", id="B")]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert load_order == ["B", "A"]


def test_chain_of_rules_gives_a_full_ordering(db):
    installed = {"C": {"rules": [rule("after", id="B")]}, "B": {"rules": [rule("after", id="A")]}}
    load_order, _ = order(db, mod_state(A=True, B=True, C=True), installed)
    assert load_order == ["A", "B", "C"]


def test_rules_matching_logical_file_name(db):
    installed = {"A": {"rules": [rule("after", logicalFileName="target-lfn")]}}
    load_order, _ = order(db, mod_state(A=True, B=("target-lfn", True)), installed)
    assert load_order == ["B", "A"]


@pytest.mark.parametrize("expression", ["B", "b*", "?", "^B$", "B$"])
def test_rules_matching_file_expressions(db, expression):
    # exact id, glob ('*' / '?', case-insensitive) or regular expression (anything else, case-insensitive)
    installed = {"A": {"rules": [rule("after", fileExpression=expression)]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert load_order.index("B") < load_order.index("A")


def test_expressions_containing_wildcards_are_globs_not_regular_expressions(db):
    installed = {"A": {"rules": [rule("after", fileExpression="b.*")]}}      # as a glob this needs a '.' after the b
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert sorted(load_order) == ["A", "B"]
    assert _global.vortex_error is None


def test_invalid_regular_expression_is_ignored(db):
    installed = {"A": {"rules": [rule("after", fileExpression="(unclosed")]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert sorted(load_order) == ["A", "B"]
    assert _global.vortex_error is None


def test_rules_about_disabled_unknown_or_the_mod_itself_are_ignored(db):
    installed = {"A": {"rules": [rule("after", id="Disabled"), rule("after", id="Missing"), rule("before", id="A")]}}
    load_order, _ = order(db, mod_state(A=True, Disabled=False), installed)
    assert load_order == ["A"]
    assert _global.vortex_error is None


@pytest.mark.parametrize("kind", ["requires", "conflicts", "recommends", None])
def test_only_before_and_after_rules_affect_order(db, kind):
    installed = {"A": {"rules": [{"type": kind, "reference": {"id": "B"}}]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert sorted(load_order) == ["A", "B"]


def test_rules_belonging_to_disabled_mods_are_ignored(db):
    installed = {"Off": {"rules": [rule("after", id="A")]}}
    load_order, _ = order(db, mod_state(A=True, Off=False), installed)
    assert load_order == ["A"]


def test_exact_id_rule_outranks_a_conflicting_name_pattern_rule(db):
    # A says "before B" by exact id (priority 2); B says "before A" only by a wildcard (priority 1).
    installed = {"A": {"rules": [rule("before", id="B")]},
                 "B": {"rules": [rule("before", fileExpression="A*")]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert load_order == ["A", "B"]
    assert _global.vortex_error is None


def test_equal_priority_conflict_is_reported_as_a_cycle(db, log):
    installed = {"A": {"rules": [rule("before", id="B")]}, "B": {"rules": [rule("before", id="A")]}}
    load_order, _ = order(db, mod_state(A=True, B=True), installed)
    assert sorted(load_order) == ["A", "B"]                        # nothing is dropped
    assert _global.vortex_error == VortexErrors.HAS_CYCLES
    assert any("Cyclic rules?" in line and "2 unresolved" in line for line in log.file_lines)
    assert any("Cycle 1" in line for line in log.file_lines)


def test_three_mod_cycle_still_orders_the_unaffected_mods_first(db):
    installed = {"A": {"rules": [rule("before", id="B")]}, "B": {"rules": [rule("before", id="C")]},
                 "C": {"rules": [rule("before", id="A")]}, "Free": {"rules": [rule("before", id="A")]}}
    load_order, _ = order(db, mod_state(A=True, B=True, C=True, Free=True), installed)
    assert load_order[0] == "Free"
    assert sorted(load_order) == ["A", "B", "C", "Free"]
    assert _global.vortex_error == VortexErrors.HAS_CYCLES


def test_find_exact_cycles_reports_each_cycle_once(log):
    adj = {"A": {"B"}, "B": {"C"}, "C": {"A"}, "X": {"Y"}, "Y": {"X"}, "Ok": set()}
    Vortex.find_exact_cycles(adj, {"A", "B", "C", "X", "Y"})
    text = "\n".join(log.file_lines)
    assert text.count("--- Cycle") == 2
    assert "A\n -> B\n -> C\n -> A" in text                         # normalised to start at the smallest id
    assert "X\n -> Y\n -> X" in text


# ------------------------------------------------------------------------------------------ get_file_conflict_resolution
def resolve(order_ids, mod_files, installed=None):
    return Vortex.get_file_conflict_resolution(list(order_ids), mod_files, installed or {})


def test_later_mods_in_load_order_win(db):
    result = resolve(["A", "B", "C"], {"f.nif": ["C", "A", "B"]})
    assert result == {"f.nif": ["A", "B", "C"]}                    # last entry is the winner


def test_any_real_mod_beats_the_data_folder_and_extracted_files(db):
    result = resolve(["A"], {"f.nif": [BSA_SENTINEL, "A", DATA_SENTINEL]})
    assert result["f.nif"][-1] == "A"


def test_loose_data_file_beats_a_file_extracted_from_a_bsa(db):
    result = resolve([], {"f.pex": [BSA_SENTINEL, DATA_SENTINEL]})
    assert result["f.pex"][-1] == DATA_SENTINEL


def test_a_mod_that_yields_a_file_loses_it_even_when_loaded_later(db):
    installed = {"B": {"fileOverrides": ["Meshes\\F.nif"]}}
    result = resolve(["A", "B"], {"meshes/f.nif": ["A", "B"]}, installed)
    assert result["meshes/f.nif"] == ["B", "A"]                    # A wins because B yielded


def test_yield_matching_is_case_and_separator_insensitive_and_allows_partial_paths(db):
    installed = {"B": {"fileOverrides": ["F.NIF"]}}
    result = resolve(["A", "B"], {"meshes\\sub\\f.nif": ["A", "B"]}, installed)
    assert result["meshes\\sub\\f.nif"] == ["B", "A"]


def test_yield_only_applies_to_the_named_file(db):
    installed = {"B": {"fileOverrides": ["other.nif"]}}
    result = resolve(["A", "B"], {"f.nif": ["A", "B"]}, installed)
    assert result["f.nif"] == ["A", "B"]


def test_files_without_providers_are_omitted(db):
    assert resolve(["A"], {"f.nif": []}) == {}


def test_the_callers_load_order_list_is_extended_with_the_sentinels(db):
    ids = ["A", "B"]
    Vortex.get_file_conflict_resolution(ids, {}, {})
    assert ids == [BSA_SENTINEL, DATA_SENTINEL, "A", "B"]


# ------------------------------------------------------------------------------------------ small lookups
def test_last_used_profile(db):
    db.sections["settings###profiles###"] = {"lastActiveProfile": {"skyrimse": "p1", "fallout4": "x"}}
    assert Vortex.get_last_used_game_profile() == "p1"


def test_last_used_profile_missing(db):
    db.sections["settings###profiles###"] = {}
    assert Vortex.get_last_used_game_profile() is None


def test_plugins_list_comes_from_the_profiles_plugins_txt(db, monkeypatch, workdir):
    fake = FakeScanner()
    fake.plugins_list = ["a", "b"]
    monkeypatch.setattr(Vortex, "scanner", fake)
    _global.vortex_data_path = str(workdir / "vd")
    assert Vortex.get_plugins_list("prof1") == ["a", "b"]
    assert fake.plugins_list_paths == [p(str(workdir / "vd"), "skyrimse", "profiles", "prof1", "plugins.txt")]


# ------------------------------------------------------------------------------------------ get_folders
@pytest.fixture
def folders(db, workdir, monkeypatch):
    """Vortex data dir, a staging folder, Skyrim with a Data folder, and an output folder."""
    vdata = workdir / "vortexdata"
    staging = workdir / "staging"
    skyrim = workdir / "Skyrim"
    (skyrim / "Data").mkdir(parents=True)
    staging.mkdir()
    _global.vortex_data_path = str(vdata)
    _global.output_folder_path = str(workdir / "out")
    db.values["settings###mods###installPath###skyrimse###"] = str(staging)
    db.sections["settings###gameMode###discovered###skyrimse"] = {"path": str(skyrim)}
    return db, vdata, staging, skyrim


def test_get_folders_success_sets_global_paths(folders):
    db, vdata, staging, skyrim = folders
    assert Vortex.get_folders() is True
    assert _global.mod_staging_folder == str(staging)
    assert _global.game_folder_path == str(skyrim / "Data")
    assert _global.game_folder_path_lower == str(skyrim / "Data").lower()      # update_vortex_vars ran
    assert _global.folders_grabbed is True


def test_get_folders_expands_vortex_placeholders_and_quotes(folders):
    db, vdata, staging, skyrim = folders
    (vdata / "skyrimse" / "mods").mkdir(parents=True)
    db.values["settings###mods###installPath###skyrimse###"] = '"{USERDATA}/{game}/mods"'
    assert Vortex.get_folders() is True
    assert _global.mod_staging_folder == str(vdata / "skyrimse" / "mods")


@pytest.mark.parametrize("stored", [None, "", "."])
def test_get_folders_assumes_the_default_staging_folder_when_none_is_stored(folders, log, stored):
    db, vdata, staging, skyrim = folders
    (vdata / "skyrimse" / "mods").mkdir(parents=True)
    db.values["settings###mods###installPath###skyrimse###"] = stored
    assert Vortex.get_folders() is True
    assert _global.mod_staging_folder == str(vdata / "skyrimse" / "mods")
    assert any("assuming default" in line for line in log.file_lines)


def test_get_folders_fails_when_the_staging_folder_does_not_exist(folders, log):
    db, vdata, staging, skyrim = folders
    db.values["settings###mods###installPath###skyrimse###"] = str(staging / "nope")
    assert Vortex.get_folders() is False
    assert _global.vortex_error == VortexErrors.INVALID_MSF
    assert any("Non-existent MSF" in line for line in log.file_lines)


def test_get_folders_fails_when_staging_and_output_are_on_different_drives(folders, monkeypatch, log):
    monkeypatch.setattr(os.path, "splitdrive",
                        lambda path: (("D:" if os.path.basename(path) == "out" else "C:"), path))
    assert Vortex.get_folders() is False
    assert _global.vortex_error == VortexErrors.DIFFERENT_MSF_AND_OF_DRIVEs
    assert any("not on the same Drive" in line for line in log.file_lines)


def test_get_folders_fails_without_skyrims_path(folders):
    db, vdata, staging, skyrim = folders
    db.sections["settings###gameMode###discovered###skyrimse"] = {}
    assert Vortex.get_folders() is False
    assert _global.vortex_error == VortexErrors.NO_BASE_PATH


def test_get_folders_fails_when_the_data_folder_is_missing(folders):
    db, vdata, staging, skyrim = folders
    db.sections["settings###gameMode###discovered###skyrimse"] = {"path": str(skyrim / "elsewhere")}
    assert Vortex.get_folders() is False
    assert _global.vortex_error == VortexErrors.NO_BASE_PATH


# ------------------------------------------------------------------------------------------ get_winning_file_conflicts
@pytest.fixture
def vortex(db, workdir, monkeypatch):
    """A staging folder with ModA/ModB/ESLifier Output, a Data folder, a profile with rules, and a fake scanner."""
    fake = FakeScanner()
    monkeypatch.setattr(Vortex, "scanner", fake)
    staging = workdir / "staging"
    data = workdir / "Skyrim" / "Data"
    data.mkdir(parents=True)
    staging.mkdir()
    _global.mod_staging_folder = str(staging)
    _global.game_folder_path = str(data)
    _global.vortex_data_path = str(workdir / "vd")
    db.sections["settings###profiles###"] = {"lastActiveProfile": {"skyrimse": "p1"}}
    db.sections["persistent###profiles###"] = {"p1": {"modState": mod_state(ModA=True, ModB=True, Disabled=False)}}
    db.sections["persistent###mods###skyrimse###"] = {
        "ModB": {"rules": [rule("after", id="ModA")]},
    }
    fake.plugins_list = ["skyrim", "moda", "modb"]
    return fake, staging, data, db


def winners(fake):
    return {k: v[0] for k, v in fake.winning_files_dict.items()}


def test_no_last_profile_aborts_with_an_error(vortex, log):
    fake, staging, data, db = vortex
    db.sections["settings###profiles###"] = {}
    assert Vortex.get_winning_file_conflicts() == ([], [], [])
    assert _global.vortex_error == VortexErrors.NO_LAST_SSE_PROFILE
    assert any("No last used skyrimse profile" in line for line in log.file_lines)


def test_winning_files_follow_load_order_and_data_folder_files_are_included(vortex):
    fake, staging, data, db = vortex
    a = touch(staging / "ModA" / "meshes" / "a.nif")
    b = touch(staging / "ModB" / "meshes" / "a.nif")
    only_a = touch(staging / "ModA" / "textures" / "t.dds")
    loose = touch(data / "meshes" / "loose.nif")
    shadowed = touch(data / "meshes" / "a.nif")                      # Data copy loses to any mod
    files, plugins, plugins_list = Vortex.get_winning_file_conflicts()
    assert sorted(files) == sorted([b, only_a, loose])
    assert a not in files and shadowed not in files
    assert plugins_list == ["skyrim", "moda", "modb"]
    assert winners(fake) == {p("meshes", "a.nif"): "ModB", p("textures", "t.dds"): "ModA",
                             p("meshes", "loose.nif"): DATA_SENTINEL}
    assert fake.winning_files_dict[p("meshes", "a.nif")][1] == b


def test_only_enabled_mod_folders_are_scanned(vortex):
    fake, staging, data, db = vortex
    touch(staging / "Disabled" / "meshes" / "x.nif")
    touch(staging / "NotInProfile" / "meshes" / "y.nif")
    (staging / "stray_file.txt").write_text("x")
    touch(staging / "ModA" / "meshes" / "z.nif")
    files, _, _ = Vortex.get_winning_file_conflicts()
    assert files == [str(staging / "ModA" / "meshes" / "z.nif")]


def test_vortex_bookkeeping_and_ignored_files_are_skipped(vortex):
    fake, staging, data, db = vortex
    fake.ignored_files = {"ignored.txt"}
    touch(staging / "ModA" / "__folder_managed_by_vortex")
    touch(staging / "ModA" / "collection.json")                    # mod-root bookkeeping
    touch(staging / "ModA" / "meta.ini")
    touch(staging / "ModA" / "sub" / "meta.ini")                   # nested: a real file
    touch(staging / "ModA" / "ignored.txt")
    touch(data / "__folder_managed_by_vortex")
    touch(data / "meta.ini")
    files, _, _ = Vortex.get_winning_file_conflicts()
    assert files == [str(staging / "ModA" / "sub" / "meta.ini")]


def test_file_overrides_make_the_yielding_mod_lose(vortex):
    fake, staging, data, db = vortex
    db.sections["persistent###mods###skyrimse###"]["ModB"]["fileOverrides"] = ["meshes\\a.nif"]
    a = touch(staging / "ModA" / "meshes" / "a.nif")
    touch(staging / "ModB" / "meshes" / "a.nif")
    files, _, _ = Vortex.get_winning_file_conflicts()
    assert files == [a]
    assert winners(fake) == {p("meshes", "a.nif"): "ModA"}


def test_plugins_are_returned_with_original_casing_from_mods_and_data_folder(vortex):
    fake, staging, data, db = vortex
    touch(staging / "ModA" / "Mixed Case.ESP")
    touch(staging / "ModA" / "sub" / "Nested.esp")                 # not at the mod root
    touch(staging / "ModB" / "ESLifier_Cell_Master.esm")           # excluded
    touch(data / "Skyrim.esm")
    touch(data / "sub" / "Nested2.esp")
    _, plugins, _ = Vortex.get_winning_file_conflicts()
    assert sorted(os.path.basename(x) for x in plugins) == ["Mixed Case.ESP", "Skyrim.esm"]
    assert str(staging / "ModA" / "Mixed Case.ESP") in plugins
    assert str(data / "Skyrim.esm") in plugins


def test_output_mod_never_counts_as_the_winner_but_still_wins_the_file(vortex):
    fake, staging, data, db = vortex
    db.sections["persistent###profiles###"]["p1"]["modState"] = mod_state(ModA=True, **{"ESLifier Output": True})
    db.sections["persistent###mods###skyrimse###"] = {"ESLifier Output": {"rules": [rule("after", id="ModA")]}}
    a = touch(staging / "ModA" / "meshes" / "a.nif")
    out = touch(staging / "ESLifier Output" / "meshes" / "a.nif")
    only_out = touch(staging / "ESLifier Output" / "meshes" / "o.nif")
    files, _, _ = Vortex.get_winning_file_conflicts()
    assert sorted(files) == sorted([out, only_out])
    assert fake.winning_files_dict[p("meshes", "a.nif")] == ("ModA", a)       # the mod underneath is recorded
    assert p("meshes", "o.nif") not in fake.winning_files_dict


def test_bsas_are_sent_for_extraction_using_the_winning_copy(vortex):
    fake, staging, data, db = vortex
    low = touch(staging / "ModA" / "Shared.bsa")
    high = touch(staging / "ModB" / "Shared.bsa")
    textures = touch(staging / "ModA" / "ModA - Textures.bsa")
    touch(staging / "ModA" / "sub" / "Deep.bsa")                   # not at the mod root
    touch(data / "Skyrim - Misc.bsa")                              # blacklisted
    data_only = touch(data / "Dawnguard.bsa")
    Vortex.get_winning_file_conflicts()
    (bsa_list, plugins_list), = fake.bsa_calls
    assert plugins_list == ["skyrim", "moda", "modb"]
    # (paths are built from the lower-cased file name, which is fine on Windows, so compare ignoring case)
    assert sorted((n, path.lower()) for n, path in bsa_list) == sorted(
        [("shared", high.lower()), ("moda", textures.lower()), ("dawnguard", data_only.lower())])
    assert low.lower() not in [path.lower() for _, path in bsa_list]


def test_files_extracted_from_bsas_are_included_and_loose_files_still_win(vortex, workdir):
    fake, staging, data, db = vortex
    fake.files_to_extract = [p("scripts", "from_bsa.pex"), p("scripts", "both.pex")]
    loose = touch(staging / "ModA" / "scripts" / "both.pex")
    files, _, _ = Vortex.get_winning_file_conflicts()
    extracted = os.path.join(os.getcwd(), "bsa_extracted", p("scripts", "from_bsa.pex"))
    assert sorted(files) == sorted([extracted, loose])
    assert winners(fake)[p("scripts", "from_bsa.pex")] == BSA_SENTINEL
    assert winners(fake)[p("scripts", "both.pex")] == "ModA"


def test_scan_with_no_files_returns_empty_lists(vortex):
    files, plugins, plugins_list = Vortex.get_winning_file_conflicts()
    assert (files, plugins) == ([], [])
    assert plugins_list == ["skyrim", "moda", "modb"]


# ------------------------------------------------------------------------------------------ get_winning_files
def test_get_winning_files_runs_the_scan_when_vortex_data_is_readable(monkeypatch, g):
    for state in (ReadState.SUCCESS_DB, ReadState.SUCCESS_STATE):
        monkeypatch.setattr(VortexDBParser, "is_readable", lambda s=state: s)
        monkeypatch.setattr(Vortex, "get_winning_file_conflicts", lambda: (["f"], ["p"], ["l"]))
        assert Vortex.get_winning_files() == (["f"], ["p"], ["l"])


def test_get_winning_files_stops_if_an_error_is_already_recorded(monkeypatch, g):
    monkeypatch.setattr(VortexDBParser, "is_readable", lambda: ReadState.SUCCESS_DB)
    monkeypatch.setattr(Vortex, "get_winning_file_conflicts", lambda: pytest.fail("should not scan"))
    _global.vortex_error = VortexErrors.INVALID_MSF
    assert Vortex.get_winning_files() == ([], [], [])


@pytest.mark.parametrize("state", [ReadState.ERROR_DB_LOCKED_DEPLOYING, ReadState.ERROR_DB_LOCKED_PURGING,
                                   ReadState.ERROR_DB_LOCKED_EXTENSION_MISSING,
                                   ReadState.ERROR_DB_LOCKED_EXTENSION_UNREACHABLE])
def test_get_winning_files_reports_why_vortex_could_not_be_read(monkeypatch, g, state):
    monkeypatch.setattr(VortexDBParser, "is_readable", lambda: state)
    assert Vortex.get_winning_files() == ([], [], [])
    assert _global.vortex_error == state
