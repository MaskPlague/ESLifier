"""
file_defined_patcher_conditions.user_and_master_conditions_class: loads the user/master patch-condition
JSON(5) files and applies them to files no built-in rule recognises. Patchers are replaced with recorders.
"""
import json
import os

import pytest

from file_defined_patcher_conditions import user_and_master_conditions_class as Conditions
from file_patchers import patchers


@pytest.fixture
def cond_file(workdir):
    """Write a conditions file into the temp ESLifier_Data folder and return its (relative) path."""
    def make(conditions, name="master_patch_conditions.json", raw=None):
        path = workdir / "ESLifier_Data" / name
        path.write_text(raw if raw is not None else json.dumps({"conditions": conditions}), encoding="utf-8")
        return f"ESLifier_Data/{name}"
    return make


@pytest.fixture
def blank(workdir):
    """An instance that skips __init__ (so no files are needed) for exercising check_conditions directly."""
    obj = Conditions.__new__(Conditions)
    obj.user_and_master_conditions = {}
    return obj


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append((args, kwargs))

    for name in ("ini_formid_sep_plugin_patcher", "json_generic_plugin_sep_formid_patcher",
                 "json_generic_formid_sep_plugin_patcher", "toml_loki_and_tdm_patcher"):
        monkeypatch.setattr(patchers, name, fake)
    return calls


def condition_set(patcher, contains=".", endswith=".", **kw):
    base = {"contains": contains, "endswith": endswith, "separator": kw.pop("separator", ""),
            "int_type": kw.pop("int_type", False), "tkns": {" "}, "fid_start": kw.pop("fid_start", None),
            "to_id_key": kw.pop("to_id_key", None), "patcher": patcher}
    base.update(kw)
    return base


FMAP = {"sentinel": 1}


# ------------------------------------------------------------------------------ get_conditions
def test_missing_conditions_file_is_created_and_returns_empty(workdir, blank):
    result = blank.get_conditions("ESLifier_Data/master_patch_conditions.json")
    assert result == {}
    assert json.loads((workdir / "ESLifier_Data" / "master_patch_conditions.json").read_text()) == {"conditions": []}


def test_conditions_are_grouped_by_extension_case_insensitively(blank, cond_file):
    path = cond_file([
        {"extension": "INI", "patcher": "ini_formid_sep_plugin", "contains": "Foo", "endswith": "_X.ini"},
        {"extension": "json", "patcher": "json_generic_plugin_sep_formid"},
        {"extension": "toml", "patcher": "toml_loki_and_tdm"},
        {"extension": "weird", "patcher": "ini_plugin_sep_formid"},
    ])
    result = blank.get_conditions(path)
    assert set(result) == {"ini", "json", "toml", "yaml", "yml", "txt", "other"}
    assert len(result["ini"]) == 1 and len(result["json"]) == 1 and len(result["toml"]) == 1
    assert len(result["other"]) == 1                 # unknown extensions go to "other"
    assert result["yaml"] == result["yml"] == result["txt"] == []


def test_condition_fields_are_normalised(blank, cond_file):
    path = cond_file([{
        "extension": "ini", "patcher": "ini_formid_sep_plugin", "contains": "Some/Path", "endswith": "_DISTR.ini",
        "separator": "|", "int_type": True, "tkns": ["a", "b"], "fid_start": "0x", "to_id_key": "hex",
    }])
    c = blank.get_conditions(path)["ini"][0]
    assert c["contains"] == os.path.normpath("some/path")      # lower-cased and path-normalised
    assert c["endswith"] == os.path.normpath("_distr.ini")
    assert c["separator"] == "|"
    assert c["int_type"] is True
    assert c["tkns"] == {"a", "b"}
    assert c["fid_start"] == "0x" and c["to_id_key"] == "hex"
    assert c["patcher"] is patchers.ini_formid_sep_plugin_patcher


def test_condition_defaults(blank, cond_file):
    c = blank.get_conditions(cond_file([{"extension": "ini", "patcher": "ini_formid_sep_plugin"}]))["ini"][0]
    assert c["contains"] == "." and c["endswith"] == "."       # normpath("") == "."  -> wildcard
    assert c["separator"] == "" and c["int_type"] is False
    assert c["tkns"] == {" "}
    assert c["fid_start"] is None and c["to_id_key"] is None


def test_minus_one_patcher_means_ignore_file(blank, cond_file):
    c = blank.get_conditions(cond_file([{"extension": "json", "patcher": -1, "contains": "ignore_me"}]))["json"][0]
    assert c["patcher"] is None


@pytest.mark.parametrize("bad", [
    {"extension": "ini", "patcher": "no_such_patcher"},
    {"patcher": "ini_formid_sep_plugin"},                       # no extension
    {"extension": "ini"},                                       # no patcher
])
def test_bad_condition_is_skipped_with_error_and_others_survive(blank, cond_file, log, bad):
    good = {"extension": "ini", "patcher": "ini_formid_sep_plugin"}
    result = blank.get_conditions(cond_file([bad, good]))
    assert len(result["ini"]) == 1
    assert any("missing required fields or has an invalid patcher method" in e for e in log.errors)


def test_invalid_json_reports_error_and_returns_empty(blank, cond_file, log):
    path = cond_file(None, raw="{ this is not valid")
    assert blank.get_conditions(path) == {}
    assert any("Issue in conditions file" in e and "master_patch_conditions.json" in e for e in log.errors)


def test_json5_comments_and_trailing_commas_are_accepted(blank, cond_file):
    raw = """{
        // a comment
        "conditions": [
            {"extension": "ini", "patcher": "ini_formid_sep_plugin",},
        ],
    }"""
    assert len(blank.get_conditions(cond_file(None, raw=raw))["ini"]) == 1


def test_file_without_conditions_key_gives_empty_groups(blank, cond_file):
    result = blank.get_conditions(cond_file(None, raw="{}"))
    assert all(v == [] for v in result.values())


# ------------------------------------------------------------------------------ __init__
def test_init_merges_user_conditions_after_master_conditions(workdir, cond_file):
    cond_file([{"extension": "ini", "patcher": "ini_formid_sep_plugin", "contains": "master"}])
    cond_file([{"extension": "ini", "patcher": "ini_plugin_sep_formid", "contains": "user"},
               {"extension": "json", "patcher": "json_generic_plugin_sep_formid"}], name="user_patch_conditions.json")
    merged = Conditions().user_and_master_conditions
    assert [c["contains"] for c in merged["ini"]] == ["master", "user"]     # master rules take precedence
    assert len(merged["json"]) == 1


def test_init_creates_missing_files(workdir):
    c = Conditions()
    assert c.user_and_master_conditions == {}
    assert (workdir / "ESLifier_Data" / "master_patch_conditions.json").exists()
    assert (workdir / "ESLifier_Data" / "user_patch_conditions.json").exists()


# ------------------------------------------------------------------------------ check_conditions
def check(cond, file, conditions_by_ext):
    cond.user_and_master_conditions = conditions_by_ext
    return cond.check_conditions("mod.esp", file, file.lower(), FMAP)


def test_no_conditions_returns_false(blank):
    assert check(blank, "C:\\d\\thing.ini", {}) is False


def test_matching_condition_calls_patcher_with_default_arguments(blank, recorder):
    cs = condition_set(patchers.ini_formid_sep_plugin_patcher, contains="foo", endswith="_x.ini")
    assert check(blank, "C:\\d\\Foo\\a_X.ini", {"ini": [cs]}) is True
    (args, kwargs), = recorder
    assert args == ("mod.esp", "C:\\d\\Foo\\a_X.ini", FMAP)
    assert kwargs == {"encoding_method": "utf-8"}


@pytest.mark.parametrize("file,expected", [
    ("c:\\d\\foo\\a_x.ini", True),
    ("c:\\d\\bar\\a_x.ini", False),                 # contains fails
    ("c:\\d\\foo\\a_y.ini", False),                 # endswith fails
])
def test_both_contains_and_endswith_must_match(blank, recorder, file, expected):
    cs = condition_set(patchers.ini_formid_sep_plugin_patcher, contains="foo", endswith="_x.ini")
    assert check(blank, file, {"ini": [cs]}) is expected
    assert bool(recorder) is expected


def test_dot_acts_as_wildcard_for_each_field(blank, recorder):
    only_contains = condition_set(patchers.ini_formid_sep_plugin_patcher, contains="foo")
    only_endswith = condition_set(patchers.ini_formid_sep_plugin_patcher, endswith="_x.ini")
    assert check(blank, "c:\\foo\\any.ini", {"ini": [only_contains]}) is True
    assert check(blank, "c:\\other\\a_x.ini", {"ini": [only_endswith]}) is True


def test_first_matching_condition_wins(blank, monkeypatch):
    first, second = [], []
    monkeypatch.setattr(patchers, "ini_formid_sep_plugin_patcher", lambda *a, **k: first.append(1))
    monkeypatch.setattr(patchers, "ini_plugin_sep_formid_patcher", lambda *a, **k: second.append(1))
    sets = [condition_set(patchers.ini_formid_sep_plugin_patcher, contains="foo"),
            condition_set(patchers.ini_plugin_sep_formid_patcher, contains="foo")]
    assert check(blank, "c:\\foo\\a.ini", {"ini": sets}) is True
    assert first == [1] and second == []


def test_none_patcher_skips_file_without_patching(blank, recorder):
    cs = condition_set(None, contains="skipme")
    assert check(blank, "c:\\skipme\\a.ini", {"ini": [cs]}) is True
    assert recorder == []


def test_optional_arguments_are_forwarded_only_when_set(blank, recorder):
    cs = condition_set(patchers.ini_formid_sep_plugin_patcher, separator="|", int_type=True,
                       fid_start="0x", to_id_key="hex")
    check(blank, "c:\\d\\a.ini", {"ini": [cs]})
    assert recorder[0][1] == {"encoding_method": "utf-8", "sep": "|", "int_type": True,
                              "fid_start": "0x", "to_id_key": "hex"}


def test_extension_picks_the_right_list_and_unknown_extensions_use_other(blank, recorder):
    ini_cs = condition_set(patchers.ini_formid_sep_plugin_patcher)
    other_cs = condition_set(patchers.json_generic_plugin_sep_formid_patcher, contains="special")
    conds = {"ini": [ini_cs], "other": [other_cs]}
    assert check(blank, "c:\\special\\a.ini", conds) is True        # ini list used, not "other"
    assert check(blank, "c:\\special\\a.weird", conds) is True      # unknown extension -> "other"
    assert check(blank, "c:\\nothing\\a.weird", conds) is False


@pytest.mark.xfail(reason="check_conditions reads condition_set['tokens'] but get_conditions stores the value "
                          "under 'tkns', so user-defined tokens never reach the patcher", strict=False)
def test_user_defined_tokens_reach_the_patcher(blank, recorder):
    cs = condition_set(patchers.ini_formid_sep_plugin_patcher)
    cs["tkns"] = {"a", "b"}
    check(blank, "c:\\d\\a.ini", {"ini": [cs]})
    assert recorder[0][1].get("tkns") == {"a", "b"}


def test_unicode_decode_error_retries_with_ansi_encoding(blank):
    seen = []

    def flaky(*args, **kwargs):
        seen.append(kwargs["encoding_method"])
        if kwargs["encoding_method"] == "utf-8":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")

    assert check(blank, "c:\\d\\a.ini", {"ini": [condition_set(flaky)]}) is True
    assert seen == ["utf-8", "ansi"]


def test_other_patcher_errors_are_logged_and_file_still_counts_as_handled(blank, log):
    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    assert check(blank, "c:\\d\\a.ini", {"ini": [condition_set(boom)]}) is True
    assert any("Failed to patch file" in e and "a.ini" in e for e in log.errors)
    assert any("kaboom" in e for e in log.errors)


@pytest.mark.xfail(reason="__init__ extends master_conditions[extension] without checking it exists, so a user "
                          "condition for an extension the (missing/empty) master file lacks raises KeyError",
                   strict=False)
def test_init_user_conditions_work_when_master_file_has_none(workdir, cond_file):
    cond_file([{"extension": "ini", "patcher": "ini_formid_sep_plugin", "contains": "user"}],
              name="user_patch_conditions.json")
    merged = Conditions().user_and_master_conditions
    assert [c["contains"] for c in merged["ini"]] == ["user"]
