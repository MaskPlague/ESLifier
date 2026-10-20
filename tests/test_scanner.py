from collections import defaultdict
"""
scanner.scanner: the core scan. It collects files from the mod manager back end, then works out which
plugin each file belongs to (by reading loose files, compiled scripts, SKSE DLLs, SEQ files and BSAs).

ESLifier runs on Windows and the scanner matches on backslash paths ('\\facegeom\\', '\\skse\\plugins'),
so the module under test is given a Windows-flavoured ``os`` (ntpath + '\\' separator). For tests that
need real files with such paths, the "file" is created with the whole backslash string as its name, which
is a perfectly valid single filename on Linux/macOS and behaves identically on Windows.
"""
import json
import ntpath
import os
import struct
import threading
import types

import pytest

import scanner as scanner_module
from data_holder import _global
from plugin_builder import write as write_bytes
from scanner_fakes import touch

S = scanner_module.scanner

DLL_PATTERN = scanner_module.re.compile(rb'\x00([a-z0-9\_\'\-\?\!\(\)\[\]\,\s\.]+\.es[pml])\x00', flags=scanner_module.re.DOTALL)


# ------------------------------------------------------------------------------------------ builders
def make_pex(strings, src=b"a.psc", user=b"user", machine=b"mach"):
    """Smallest byte string the scanner's pex reader will accept (big-endian string table)."""
    out = b"\xfa\x57\xc0\xfa" + b"\x00" * 12
    for part in (src, user, machine):
        out += struct.pack(">H", len(part)) + part
    out += struct.pack(">H", len(strings))
    for s in strings:
        raw = s.encode()
        out += struct.pack(">H", len(raw)) + raw
    return out


def make_bsa(folders, version=104, total_file_name_length=10):
    """A BSA containing only folder records/names (all the scanner looks at)."""
    rec_size = 24 if version == 105 else 16
    header = bytearray(36)
    header[0:3] = b"BSA"
    header[4:8] = struct.pack("<I", version)
    header[8:12] = struct.pack("<I", 36)
    header[16:20] = struct.pack("<I", len(folders))
    header[28:32] = struct.pack("<I", total_file_name_length)
    pos = 36 + rec_size * len(folders)
    records, names = b"", b""
    for name in folders:
        raw = name.encode() + b"\x00"
        block = bytes([len(raw)]) + raw
        offset_field = pos + total_file_name_length
        if version == 105:
            records += b"\x00" * 8 + struct.pack("<I", 0) + b"\x00" * 4 + struct.pack("<I", offset_field) + b"\x00" * 4
        else:
            records += b"\x00" * 8 + struct.pack("<I", 0) + struct.pack("<I", offset_field)
        names += block
        pos += len(block)
    return bytes(header) + records + names


def flat(name, data=b"x"):
    """Create a file in the cwd whose *name* is the given (backslash-containing) string."""
    # On Linux the whole string is one file name; on Windows the backslashes are real separators, so the
    # parent folders have to exist.
    parent = os.path.dirname(name)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(name, "wb") as f:
        f.write(data)
    return name


# ------------------------------------------------------------------------------------------ fixtures
@pytest.fixture
def sc(workdir, monkeypatch):
    """Scanner class with clean state, running against a Windows-flavoured ``os``."""
    shim = types.ModuleType("os")
    shim.__dict__.update(os.__dict__)
    shim.sep = "\\"
    shim.path = ntpath
    monkeypatch.setattr(scanner_module, "os", shim)
    state = dict(
        count=0, file_count=0, percentage=0, lock=threading.Lock(), file_semaphore=threading.Semaphore(100),
        threads=[], pex_files=[], seq_files=[], dll_files=[], file_dict=defaultdict(set), dll_dict=defaultdict(set), archive_dict=defaultdict(list),
        archive_files=[], plugin_basename_set=set(), max_plugin_len=0, all_files=[], extracted=set(),
        ignored_files=set(), game_archive_blacklist=set(), winning_files_dict={}, all_patcher_experimental=False,
        file_extensions=('.ini', '.json', '.jslot', '.toml', '_conditions.txt', '.yaml', '.yml'),
        exclude_contains=(), exclude_endswith=(),
    )
    for k, v in state.items():
        monkeypatch.setattr(S, k, v, raising=False)
    # subprocess.STARTUPINFO only exists on Windows
    monkeypatch.setattr(scanner_module.subprocess, "STARTUPINFO", lambda: types.SimpleNamespace(dwFlags=0), raising=False)
    monkeypatch.setattr(scanner_module.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    return S


def set_plugins(sc, *names):
    sc.plugin_basename_set = {n.lower() for n in names}
    sc.max_plugin_len = max((len(n) for n in sc.plugin_basename_set), default=0)


@pytest.fixture
def reads(sc, monkeypatch):
    """Replace file_reader with a recorder (for testing file_processor's routing in isolation)."""
    calls = []
    monkeypatch.setattr(S, "file_reader", lambda pattern, file, kind: calls.append((file, kind)))
    return calls


def process(sc, *files):
    sc.file_count = len(files)
    sc.file_processor(list(files))
    for t in sc.threads:
        t.join()


# ------------------------------------------------------------------------------------------ small helpers
def test_get_from_file_returns_data_or_an_empty_default(tmp_path):
    good = tmp_path / "g.json"
    good.write_text('["a"]', encoding="utf-8")
    bad = tmp_path / "b.json"
    bad.write_text("{nope", encoding="utf-8")
    assert S.get_from_file(str(good), list) == ["a"]
    assert S.get_from_file(str(bad), dict) == {}
    assert S.get_from_file(str(tmp_path / "missing.json"), list) == []


def test_dump_to_file_converts_sets_and_keeps_unicode(tmp_path):
    out = tmp_path / "o.json"
    S.dump_to_file(str(out), {"plugin.esp": {"Ünï.ini"}, "other": ["x"]})
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {"plugin.esp": ["Ünï.ini"], "other": ["x"]}
    S.dump_to_file(str(out), {"a", "b"})
    assert sorted(json.loads(out.read_text(encoding="utf-8"))) == ["a", "b"]
    S.dump_to_file(str(out), ["z"])
    assert json.loads(out.read_text(encoding="utf-8")) == ["z"]


def test_dump_to_file_failure_is_logged(tmp_path, log):
    S.dump_to_file(str(tmp_path / "nope" / "o.json"), [])
    assert any("Failed to dump data to" in e for e in log.errors)


def test_get_plugins_list_returns_active_plugins_without_extension(tmp_path):
    f = tmp_path / "plugins.txt"
    f.write_text("# header\n*Skyrim.esm\nInactive.esp\n*My Mod.ESP\n*Light.esl\n", encoding="utf-8")
    assert S.get_plugins_list(str(f)) == ["skyrim", "my mod", "light"]


def test_get_plugins_list_missing_file_is_logged(tmp_path, log):
    assert S.get_plugins_list(str(tmp_path / "missing.txt")) == []
    assert any("Failed to get plugins list at" in e for e in log.errors)


def test_sort_archive_files_keeps_only_active_plugins_ordered_by_load_order():
    bsas = {
        "C:\\data\\Beta.bsa": ["x"],
        "C:/data/Alpha - Textures.bsa": ["y"],
        "C:\\data\\Alpha - Textures2.bsa": ["z"],
        "C:\\data\\Gamma.bsa": ["w"],
        "C:\\data\\NotActive.bsa": ["v"],
    }
    result = S.sort_archive_files(bsas, ["alpha", "beta", "gamma"])
    assert list(result) == ["C:/data/Alpha - Textures.bsa", "C:\\data\\Alpha - Textures2.bsa",
                            "C:\\data\\Beta.bsa", "C:\\data\\Gamma.bsa"]


def test_sort_archive_files_with_no_matching_plugins_is_empty():
    assert S.sort_archive_files({"a.bsa": []}, []) == {}


def test_seq_plugin_extension_processor_matches_whichever_extension_exists(sc):
    sc.file_dict = {"a.esp": set(), "b.esl": set(), "c.esm": set()}
    sc.seq_plugin_extension_processor([["a", "a.seq"], ["b", "b.seq"], ["c", "c.seq"], ["zzz", "zzz.seq"]])
    assert _global.mods_with_seq == {"a.esp": "a.seq", "b.esl": "b.seq", "c.esm": "c.seq"}
    assert sc.file_dict["a.esp"] == {"a.seq"} and sc.file_dict["b.esl"] == {"b.seq"}
    assert "zzz.esp" not in sc.file_dict


# ------------------------------------------------------------------------------------------ BSA extraction
class FakePopen:
    def __init__(self, lines):
        self.stdout = iter(lines)
        self.stderr = iter([])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_extract_archive_runs_bsarch_with_the_filter(sc, monkeypatch):
    seen = {}

    def popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakePopen(["Unpacking a.pex\n", "Unpacking b.pex\n"])

    monkeypatch.setattr(scanner_module.subprocess, "Popen", popen)
    S.extract_archive("C:\\x.bsa", None, 0.1, ".pex")
    assert seen["cmd"] == ["bsarch/bsarch.exe", "unpack", "C:\\x.bsa", "bsa_extracted", "-f:.pex", "-mt:no"]


def test_extract_archive_raises_when_bsarch_reports_an_unpacking_error(sc, monkeypatch):
    monkeypatch.setattr(scanner_module.subprocess, "Popen", lambda cmd, **k: FakePopen(["Unpacking error: boom\n"]))
    with pytest.raises(Exception, match="BSArch"):
        S.extract_archive("C:\\x.bsa", None, 0.1, ".pex")


@pytest.fixture
def extraction(sc, monkeypatch):
    calls = []

    def fake_extract(file, startupinfo, update_time, filt):
        if "broken" in file:
            raise Exception("bsarch failed")
        calls.append((file, filt))

    monkeypatch.setattr(S, "extract_archive", fake_extract)
    return calls


def test_extraction_only_for_active_plugins_in_load_order_and_pex_then_seq(sc, extraction):
    bsa_list = [["beta", "C:\\beta.bsa"], ["inactive", "C:\\inactive.bsa"], ["alpha", "C:\\alpha.bsa"]]
    S.extract_scripts_and_seq_from_game_archive(bsa_list, ["alpha", "beta"])
    assert sc.archive_files == ["C:\\alpha.bsa", "C:\\beta.bsa"]
    assert extraction == [("C:\\alpha.bsa", ".pex"), ("C:\\alpha.bsa", ".seq"),
                          ("C:\\beta.bsa", ".pex"), ("C:\\beta.bsa", ".seq")]
    assert sc.extracted == {"C:\\alpha.bsa", "C:\\beta.bsa"}


def test_already_extracted_bsas_are_not_extracted_again(sc, extraction):
    sc.extracted = {"C:\\alpha.bsa"}
    S.extract_scripts_and_seq_from_game_archive([["alpha", "C:\\alpha.bsa"]], ["alpha"])
    assert extraction == []
    assert sc.archive_files == ["C:\\alpha.bsa"]          # still scanned later for plugin names


def test_failed_extraction_is_logged_and_not_marked_extracted(sc, extraction, log):
    S.extract_scripts_and_seq_from_game_archive([["alpha", "C:\\broken.bsa"], ["beta", "C:\\ok.bsa"]], ["alpha", "beta"])
    assert "C:\\broken.bsa" not in sc.extracted and "C:\\ok.bsa" in sc.extracted
    assert any("Error Reading archive" in e and "broken.bsa" in e for e in log.errors)


# ------------------------------------------------------------------------------------------ file_processor routing
def test_data_files_are_sent_to_the_text_reader(sc, reads):
    set_plugins(sc, "a.esp")
    files = ["c:\\d\\a.ini", "c:\\d\\a.JSON", "c:\\d\\a.jslot", "c:\\d\\a.toml", "c:\\d\\a.yaml",
             "c:\\d\\a.yml", "c:\\d\\x_conditions.txt", "c:\\d\\skse\\plugins\\customskill\\config.txt"]
    process(sc, *files)
    assert sorted(reads) == sorted((f, "r") for f in files)


def test_excluded_data_files_are_not_read(sc, reads):
    sc.exclude_contains = ("nemesis_engine", "\\headpartwhitelist\\")
    sc.exclude_endswith = ("\\grasscontrol.ini",)
    process(sc, "c:\\d\\nemesis_engine\\a.ini", "c:\\d\\headpartwhitelist\\a.json", "c:\\d\\grasscontrol.ini",
            "c:\\d\\ok.ini")
    assert reads == [("c:\\d\\ok.ini", "r")]


def test_config_txt_only_counts_inside_customskill_folder(sc, reads):
    process(sc, "c:\\d\\other\\config.txt", "c:\\d\\skse\\plugins\\customskill\\config.txt")
    assert reads == [("c:\\d\\skse\\plugins\\customskill\\config.txt", "r")]


def test_pex_dll_and_seq_files_are_queued_for_later_scanning(sc, reads):
    process(sc, "c:\\d\\scripts\\a.PEX", "c:\\d\\skse\\plugins\\x.dll", "c:\\d\\other\\y.dll", "c:\\d\\Some Mod.SEQ")
    assert reads == []
    assert sc.pex_files == ["c:\\d\\scripts\\a.PEX"]
    assert sc.dll_files == ["c:\\d\\skse\\plugins\\x.dll"]           # only DLLs under skse\plugins
    assert sc.seq_files == [["some mod", "c:\\d\\Some Mod.SEQ"]]


def test_facegeom_facetint_and_voice_files_are_attributed_to_their_plugin(sc, reads):
    set_plugins(sc, "a.esp", "b.esl", "c.esm")
    nif = "c:\\d\\meshes\\actors\\character\\facegeom\\A.esp\\00001234.nif"
    dds = "c:\\d\\textures\\actors\\character\\facetint\\B.esl\\00005678.dds"
    voice = "c:\\d\\sound\\voice\\C.esm\\maleeventoned\\x.fuz"
    process(sc, nif, dds, voice)
    assert sc.file_dict == {"a.esp": {nif}, "b.esl": {dds}, "c.esm": {voice}}


def test_face_and_voice_files_for_inactive_or_non_plugin_folders_are_ignored(sc, reads):
    set_plugins(sc, "a.esp")
    process(sc, "c:\\d\\meshes\\facegeom\\Inactive.esp\\1.nif", "c:\\d\\meshes\\facegeom\\a.es_dir\\1.nif",
            "c:\\d\\sound\\voice\\notaplugin\\1.fuz")
    assert sc.file_dict == {}


def test_several_face_files_for_one_plugin_are_grouped(sc, reads):
    set_plugins(sc, "a.esp")
    f1, f2 = "c:\\d\\facegeom\\a.esp\\1.nif", "c:\\d\\facegeom\\a.esp\\2.nif"
    process(sc, f1, f2)
    assert sc.file_dict["a.esp"] == {f1, f2}


def test_experimental_mode_also_reads_unknown_file_types(sc, reads):
    sc.all_patcher_experimental = True
    process(sc, "c:\\d\\settings.cfg", "c:\\d\\model.nif", "c:\\d\\scripts\\source.psc", "c:\\d\\dialogueviews\\x.txt")
    read_files = {f for f, _ in reads}
    assert read_files == {"c:\\d\\settings.cfg"}


def test_unknown_file_types_are_ignored_outside_experimental_mode(sc, reads):
    process(sc, "c:\\d\\settings.cfg")
    assert reads == []


# ------------------------------------------------------------------------------------------ file_reader: text
def read_text(sc, path):
    sc.file_reader(None, str(path), "r")


def test_text_reader_finds_plugin_names_case_insensitively(sc, tmp_path):
    set_plugins(sc, "MyMod.esp", "Light.esl", "Master.ESM")
    f = tmp_path / "a.ini"
    f.write_text("Plugin=MyMod.ESP|1234\nnothing here\nx = light.esl, MASTER.esm\n", encoding="utf-8")
    read_text(sc, f)
    assert sc.file_dict == {"mymod.esp": {str(f)}, "light.esl": {str(f)}, "master.esm": {str(f)}}


def test_text_reader_ignores_unknown_plugins_and_lookalikes(sc, tmp_path):
    set_plugins(sc, "mymod.esp")
    f = tmp_path / "a.ini"
    f.write_text("Unknown.esp\n.estimate = 4\nmymod.es\n", encoding="utf-8")
    read_text(sc, f)
    assert sc.file_dict == {}


def test_text_reader_prefers_the_longest_matching_plugin_name(sc, tmp_path):
    set_plugins(sc, "bar.esp", "foo bar.esp")
    f = tmp_path / "a.ini"
    f.write_text("x = Foo Bar.esp\n", encoding="utf-8")
    read_text(sc, f)
    assert sc.file_dict == {"foo bar.esp": {str(f)}}


def test_text_reader_handles_the_same_plugin_on_several_lines(sc, tmp_path):
    set_plugins(sc, "a.esp")
    f = tmp_path / "a.json"
    f.write_text('{"a": "a.esp|1", "b": "a.esp|2"}\n"c": "A.ESP"', encoding="utf-8")
    read_text(sc, f)
    assert sc.file_dict == {"a.esp": {str(f)}}


def test_text_reader_tolerates_invalid_utf8(sc, tmp_path):
    set_plugins(sc, "a.esp")
    f = tmp_path / "a.ini"
    f.write_bytes(b"\xff\xfe junk a.esp \xff")
    read_text(sc, f)
    assert "a.esp" in sc.file_dict


def test_text_reader_reports_unreadable_files(sc, tmp_path, log):
    read_text(sc, tmp_path / "missing.ini")
    assert any("Error reading file" in e and "missing.ini" in e for e in log.errors)


def test_luma_json_belongs_to_the_plugin_named_by_its_folder(sc):
    set_plugins(sc, "a.esp")
    f = flat("data\\luma\\A.esp\\settings.json", b"{}")
    sc.file_reader(None, f, "r")
    assert sc.file_dict == {"a.esp": {f}}


def test_jslot_preset_plugins_are_read_from_json_fields(sc, tmp_path):
    set_plugins(sc, "a.esp", "b.esp", "c.esp")
    f = tmp_path / "preset.jslot"
    f.write_text(json.dumps({"actor": {"headTexture": "A.esp|123456"},
                             "headParts": [{"formIdentifier": "B.esp|001234"}, {"other": 1},
                                           {"formIdentifier": "Unlisted.esp|000001"}]}) + "\ntrailing junk",
                 encoding="utf-8")
    read_text(sc, f)
    assert sc.file_dict == {"a.esp": {str(f)}, "b.esp": {str(f)}}


# ------------------------------------------------------------------------------------------ file_reader: pex
def test_pex_with_getformfromfile_is_attributed_to_the_plugins_it_names(sc, tmp_path):
    set_plugins(sc, "mymod.esp")
    f = write_bytes(tmp_path / "a.pex", make_pex(["GetFormFromFile", "MyMod.esp", "Other.esp", "x"]))
    sc.file_reader(None, f, "pex-SSE")
    assert sc.file_dict == {"mymod.esp": {f}}


def test_pex_without_form_lookup_functions_is_not_attributed(sc, tmp_path):
    set_plugins(sc, "mymod.esp")
    f = write_bytes(tmp_path / "a.pex", make_pex(["somethingelse", "MyMod.esp"]))
    sc.file_reader(None, f, "pex-SSE")
    assert sc.file_dict == {}
    assert os.path.exists(f)                                         # not in bsa_extracted, so kept


def test_unneeded_pex_extracted_from_a_bsa_is_deleted(sc):
    set_plugins(sc, "mymod.esp")
    f = flat("bsa_extracted\\scripts\\a.pex", make_pex(["somethingelse"]))
    sc.file_reader(None, f, "pex-SSE")
    assert not os.path.exists(f)


def test_needed_pex_extracted_from_a_bsa_is_kept(sc):
    set_plugins(sc, "mymod.esp")
    f = flat("bsa_extracted\\scripts\\b.pex", make_pex(["getformfromfile", "mymod.esp"]))
    sc.file_reader(None, f, "pex-SSE")
    assert os.path.exists(f)
    assert sc.file_dict == {"mymod.esp": {f}}


def test_pex_with_getmodbyname_records_it_without_crashing(sc, tmp_path, log):
    set_plugins(sc, "mymod.esp")
    f = write_bytes(tmp_path / "a.pex", make_pex(["getmodbyname", "mymod.esp"]))
    sc.file_reader(None, f, "pex-SSE")
    assert log.errors == []


def test_corrupt_pex_is_reported(sc, tmp_path, log):
    f = write_bytes(tmp_path / "bad.pex", b"\x00" * 10)
    sc.file_reader(None, f, "pex-SSE")
    assert any("Error reading file" in e for e in log.errors)
    assert any("pex file is likely corrupt" in e for e in log.errors)


def test_getmodbyname_calls_with_a_plugin_argument_are_recorded(sc):
    strings = [b"getmodbyname", b"mymod.esp", b"other.esp"]
    # instruction: [opcode idx(2)] + 8 filler bytes + 0x02 (string arg type) + [plugin idx(2)]
    call = (0).to_bytes(2) + b"\x00" * 8 + b"\x02" + (1).to_bytes(2)
    S.check_if_modbyname_uses_plugin_names(call + b"\x00\x00\x00", {"mymod.esp", "other.esp"}, "a.pex", 0, strings)
    assert _global.pex_with_getmodbyname == {"mymod.esp": {"a.pex"}}


def test_getmodbyname_calls_with_a_non_string_argument_are_ignored(sc):
    strings = [b"getmodbyname", b"mymod.esp"]
    call = (0).to_bytes(2) + b"\x00" * 8 + b"\x01" + (1).to_bytes(2)
    S.check_if_modbyname_uses_plugin_names(call + b"\x00\x00", {"mymod.esp"}, "a.pex", 0, strings)
    assert _global.pex_with_getmodbyname == {}


# ------------------------------------------------------------------------------------------ file_reader: dll / other
def test_dll_reader_records_plugin_names_found_in_the_binary(sc, tmp_path):
    set_plugins(sc, "mymod.esp", "other.esm")
    f = write_bytes(tmp_path / "plugin.dll", b"MZ\x00MyMod.esp\x00junk\x00Unlisted.esp\x00more\x00MyMod.esp\x00")
    sc.file_reader(DLL_PATTERN, f, "dll")
    assert sc.dll_dict == {"mymod.esp": {f}}


def test_dll_reader_does_not_duplicate_files(sc, tmp_path):
    set_plugins(sc, "mymod.esp")
    f = write_bytes(tmp_path / "plugin.dll", b"\x00MyMod.esp\x00")
    sc.file_reader(DLL_PATTERN, f, "dll")
    sc.file_reader(DLL_PATTERN, f, "dll")
    assert sc.dll_dict == {"mymod.esp": {f}}


def _fake_pe(monkeypatch, file_version_ms):
    pe = types.SimpleNamespace(VS_FIXEDFILEINFO=[types.SimpleNamespace(FileVersionMS=file_version_ms)])
    monkeypatch.setattr(scanner_module.pefile, "PE", lambda path: pe)


def test_engine_fixes_dll_version_7_is_detected(sc, tmp_path, monkeypatch):
    f = write_bytes(tmp_path / "EngineFixes.dll", b"MZ")
    _fake_pe(monkeypatch, 7 << 16)
    sc.file_reader(DLL_PATTERN, f, "dll")
    assert _global.engine_fixes_v7_or_newer


@pytest.mark.xfail(reason="engine_fixes_v7_or_newer is assigned with a trailing comma, so it becomes the tuple "
                          "(False,), which is truthy: older Engine Fixes versions are treated as v7+", strict=False)
def test_engine_fixes_dll_older_than_version_7_is_not_v7(sc, tmp_path, monkeypatch):
    f = write_bytes(tmp_path / "EngineFixes.dll", b"MZ")
    _fake_pe(monkeypatch, 6 << 16)
    sc.file_reader(DLL_PATTERN, f, "dll")
    assert not _global.engine_fixes_v7_or_newer


def test_unknown_reader_type_is_warned_about(sc, tmp_path, log):
    sc.file_reader(None, str(tmp_path / "x.ini"), "bogus")
    assert any("Missing file scan type for" in w for w in log.warnings)


# ------------------------------------------------------------------------------------------ bsa_reader
def read_bsa(sc, tmp_path, folders, version=104, name="a.bsa"):
    f = write_bytes(tmp_path / name, make_bsa(folders, version))
    sc.bsa_reader(f)
    return f


@pytest.mark.parametrize("version", [104, 105])
def test_bsa_reader_finds_plugins_in_face_and_voice_folders(sc, tmp_path, version):
    f = read_bsa(sc, tmp_path, [
        "meshes\\actors\\character\\facegendata\\facegeom\\MyMod.esp",
        "textures\\actors\\character\\facegendata\\facetint\\Light.esl",
        "sound\\voice\\Master.esm",
        "meshes\\unrelated",
    ], version)
    assert sorted(sc.archive_dict[f]) == ["Light.esl", "Master.esm", "MyMod.esp"]


@pytest.mark.parametrize("version", [104, 105])
def test_bsa_reader_finds_plugins_in_voice_folders(sc, tmp_path, version):
    f = read_bsa(sc, tmp_path, ["sound\\voice\\Master.esm", "meshes\\unrelated"], version)
    assert sc.archive_dict[f] == ["Master.esm"]


def test_bsa_reader_lists_each_plugin_once(sc, tmp_path):
    f = read_bsa(sc, tmp_path, ["meshes\\actors\\character\\facegendata\\facegeom\\A.esp", "textures\\actors\\character\\facegendata\\facetint\\A.esp", "sound\\voice\\A.esp"])
    assert sc.archive_dict[f] == ["A.esp"]


def test_bsa_without_plugin_folders_is_not_recorded(sc, tmp_path):
    read_bsa(sc, tmp_path, ["meshes\\armor", "textures\\foo"])
    assert sc.archive_dict == {}


def test_empty_bsa_is_not_recorded(sc, tmp_path, log):
    read_bsa(sc, tmp_path, [])
    assert sc.archive_dict == {} and log.errors == []


def test_file_that_is_not_a_bsa_is_skipped_silently(sc, tmp_path, log):
    f = write_bytes(tmp_path / "fake.bsa", b"RIFF" + b"\x00" * 100)
    sc.bsa_reader(f)
    assert sc.archive_dict == {} and log.errors == []


def test_corrupt_bsa_header_is_reported(sc, tmp_path, log):
    data = bytearray(make_bsa(["meshes\\actors\\character\\facegendata\\facegeom\\A.esp"]))
    data[16:20] = struct.pack("<I", 10_000_000)                    # absurd folder count
    f = write_bytes(tmp_path / "bad.bsa", bytes(data))
    sc.bsa_reader(f)
    assert sc.archive_dict == {}
    assert any("Error Reading BSA" in e and "bad.bsa" in e for e in log.errors)


def test_unreadable_bsa_is_reported(sc, tmp_path, log):
    sc.bsa_reader(str(tmp_path / "missing.bsa"))
    assert any("Error Reading BSA" in e for e in log.errors)


def test_archive_processor_reads_every_file(sc, tmp_path):
    a = write_bytes(tmp_path / "a.bsa", make_bsa(["meshes\\actors\\character\\facegendata\\facegeom\\A.esp"]))
    b = write_bytes(tmp_path / "b.bsa", make_bsa(["sound\\voice\\B.esp"]))
    sc.archive_processor([a, b])
    assert sc.archive_dict == {a: ["A.esp"], b: ["B.esp"]}


# ------------------------------------------------------------------------------------------ get_file_masters (end to end)
def test_get_file_masters_combines_every_source(sc, log):
    set_plugins(sc, "mymod.esp", "other.esp", "seqmod.esp", "face.esp", "pexmod.esp", "dllmod.esp", "bsamod.esp")
    ini = flat("data\\skse\\plugins\\config.ini", b"[x]\nplugin = MyMod.esp\n")
    unrelated = flat("data\\readme.cfg", b"MyMod.esp")                 # unknown type, not experimental
    face = flat("data\\meshes\\actors\\character\\facegeom\\Face.esp\\0001.nif")
    seq = flat("data\\seq\\SeqMod.seq")
    pex = flat("data\\scripts\\a.pex", make_pex(["getformfromfile", "pexmod.esp"]))
    dll = flat("data\\skse\\plugins\\thing.dll", b"MZ\x00DllMod.esp\x00")
    bsa = flat("data\\BsaMod.bsa", make_bsa(["sound\\voice\\BsaMod.esp"]))
    sc.all_files = [ini, unrelated, face, seq, pex, dll]
    sc.file_count = len(sc.all_files)                              # set by the mod-manager back end in a real scan
    sc.archive_files = [bsa]
    sc.get_file_masters()
    assert sc.file_dict == {
        "mymod.esp": {ini},
        "other.esp": set(),
        "face.esp": {face},
        "seqmod.esp": {seq},
        "pexmod.esp": {pex},
        "dllmod.esp": set(),
        "bsamod.esp": set(),
    }
    assert sc.dll_dict == {"dllmod.esp": {dll}}
    assert sc.archive_dict == {bsa: ["BsaMod.esp"]}
    assert _global.mods_with_seq == {"seqmod.esp": seq}
    assert log.errors == []


def test_get_file_masters_with_no_files_is_harmless(sc):
    set_plugins(sc, "a.esp")
    sc.get_file_masters()
    assert sc.file_dict == {"a.esp": set()}


def test_get_file_masters_splits_work_across_threads_without_losing_files(sc):
    set_plugins(sc, "a.esp")
    files = [flat(f"data\\f{i}.ini", b"a.esp") for i in range(40)]
    sc.all_files = files
    sc.file_count = len(files)
    sc.get_file_masters()
    assert sc.file_dict["a.esp"] == set(files)


# ------------------------------------------------------------------------------------------ scan (orchestration)
class FakeDependencyGetter:
    @staticmethod
    def scan():
        return {"dep": ["x"]}


class FakeQualificationChecker:
    @staticmethod
    def scan():
        return {"flags": 1}


@pytest.fixture
def scan_env(sc, workdir, monkeypatch):
    """Everything scan() needs in manager-less mode: Data folder, plugins.txt, ignore lists, stub scanners."""
    monkeypatch.setattr(scanner_module, "dependecy_getter", FakeDependencyGetter)
    monkeypatch.setattr(scanner_module, "qualification_checker", FakeQualificationChecker)
    data = workdir / "ESLifier_Data"
    (data / "ignored_files.json").write_text(json.dumps(["User.ini"]), encoding="utf-8")
    (data / "master_ignored_files.json").write_text(json.dumps({
        "ignored_files": ["Skip.ini"], "ignored_contains": ["bad\\dir"], "ignored_endswith": ["\\skip.json"]}),
        encoding="utf-8")
    game = workdir / "Skyrim"
    touch(game / "Foo.esp")
    touch(game / "config.ini", b"patches Foo.esp")
    touch(game / "Skip.ini", b"Foo.esp")
    touch(game / "User.ini", b"Foo.esp")
    plugins_txt = workdir / "plugins.txt"
    plugins_txt.write_text("# generated\n*Foo.esp\nBar.esp\n", encoding="utf-8")
    _global.mod_manager_mode = 0
    _global.game_folder_path = str(game)
    _global.plugins_txt_path = str(plugins_txt)
    _global.output_folder_name = "ESLifier Output"
    return workdir, game


def saved(root, name):
    return json.loads((root / "ESLifier_Data" / name).read_text(encoding="utf-8"))


def test_full_scan_without_a_mod_manager(scan_env):
    root, game = scan_env
    result = S.scan(True)
    assert result == ({"flags": 1}, {"dep": ["x"]})
    assert [os.path.basename(p) for p in _global.plugins] == ["Foo.esp"]
    masters = saved(root, "file_masters.json")
    assert masters == {"foo.esp": [str(game / "config.ini")]}      # Skip.ini / User.ini are on the ignore lists
    assert saved(root, "dll_dict.json") == {}
    assert saved(root, "extracted_bsa.json") == []
    assert saved(root, "winning_files_dict.json") == {}


def test_scan_without_full_scan_returns_nothing_and_skips_dependency_scans(scan_env, monkeypatch):
    called = []
    monkeypatch.setattr(FakeDependencyGetter, "scan", staticmethod(lambda: called.append("dep")))
    monkeypatch.setattr(FakeQualificationChecker, "scan", staticmethod(lambda: called.append("qual")))
    assert S.scan(False) is None
    assert called == []


def test_ignore_lists_are_merged_and_lowercased(scan_env):
    S.scan(False)
    assert {"skip.ini", "user.ini"} <= S.ignored_files
    assert "bad\\dir" in S.exclude_contains and "nemesis_engine" in S.exclude_contains
    assert "\\skip.json" in S.exclude_endswith and "\\grasscontrol.ini" in S.exclude_endswith


def test_scan_resets_previous_state(scan_env):
    S.pex_files = ["stale.pex"]
    S.file_dict = {"stale.esp": {"x"}}
    _global.plugins.append("stale")
    S.scan(False)
    assert "stale.pex" not in S.pex_files
    assert "stale.esp" not in S.file_dict
    assert "stale" not in _global.plugins


@pytest.mark.parametrize("available_gb,windows,expected_threads", [
    (0.5, False, 100),                 # little RAM: never fewer than 100
    (100000, False, 1024),             # plenty of RAM: capped at 1024 off Windows
    (100000, True, 8192),              # ...and 8192 on Windows
])
def test_thread_limit_is_derived_from_available_ram(scan_env, monkeypatch, available_gb, windows, expected_threads):
    fake_psutil = types.SimpleNamespace(
        virtual_memory=lambda: types.SimpleNamespace(available=int(available_gb * 1024 ** 3)))
    monkeypatch.setattr(scanner_module, "psutil", fake_psutil)
    monkeypatch.setattr(scanner_module, "WINDOWS", windows)
    S.scan(False)
    assert S.max_threads_by_ram == expected_threads
    assert S.archive_threads_by_ram >= 1


def test_scan_with_mo2_uses_winning_files_from_mo2(scan_env, monkeypatch):
    root, game = scan_env
    _global.mod_manager_mode = 2
    monkeypatch.setattr(_global, "get_paths", lambda: True)
    _global.mo2_error = None
    ini = flat("data\\x\\config.ini", b"Foo.esp")
    plugin_path = str(game / "Foo.esp")
    scanner_module.MO2.scanner = None
    monkeypatch.setattr(scanner_module.MO2, "get_winning_files", lambda plugins_list: ([ini], [plugin_path]))
    S.scan(False)
    assert scanner_module.MO2.scanner is S
    assert S.all_files == [ini]
    assert saved(root, "file_masters.json") == {"foo.esp": [ini]}


def test_scan_with_mo2_stops_when_paths_cannot_be_resolved(scan_env, monkeypatch):
    _global.mod_manager_mode = 2
    monkeypatch.setattr(_global, "get_paths", lambda: False)
    assert S.scan(True) == ({}, {})


def test_scan_with_mo2_stops_on_mo2_error(scan_env, monkeypatch):
    _global.mod_manager_mode = 2
    monkeypatch.setattr(_global, "get_paths", lambda: True)
    _global.mo2_error = "boom"
    assert S.scan(True) == ({}, {})


def test_scan_with_vortex_uses_vortex_files_and_stops_on_error(scan_env, monkeypatch):
    root, game = scan_env
    _global.mod_manager_mode = 1
    _global.vortex_error = None
    ini = flat("data\\x\\config.ini", b"Foo.esp")
    monkeypatch.setattr(scanner_module.Vortex, "get_winning_files", lambda: ([ini], [str(game / "Foo.esp")], ["foo"]))
    S.scan(False)
    assert saved(root, "file_masters.json") == {"foo.esp": [ini]}

    _global.vortex_error = "boom"
    assert S.scan(True) == ({}, {})
