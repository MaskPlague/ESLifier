"""plugin_qualification_checker: decides which plugins can be ESL flagged / need compacting."""
import json
import os

import pytest

from plugin_builder import (cell_record, fid, grup, plugin, record, simple_records, write, tes4)
from scanners.plugin_qualification_checker import qualification_checker as qc

SKYRIM = "Skyrim.esm"


def make_plugin(tmp_path, name, masters=(SKYRIM,), body=b"", **kw):
    return write(tmp_path / name, plugin(masters, body, **kw))


# ------------------------------------------------------------------ already_esl
class TestAlreadyEsl:
    def test_plain_esp_is_not_esl_and_not_esm(self, tmp_path):
        f = make_plugin(tmp_path, "a.esp")
        assert qc.already_esl(f) == (False, False)

    def test_esl_flag_detected(self, tmp_path):
        f = make_plugin(tmp_path, "a.esp", esl=True)
        assert qc.already_esl(f) == (True, False)

    def test_esm_flag_detected_even_with_esp_extension(self, tmp_path):
        f = make_plugin(tmp_path, "a.esp", esm=True)
        assert qc.already_esl(f) == (False, True)

    def test_esm_extension_counts_as_esm(self, tmp_path):
        f = make_plugin(tmp_path, "a.esm")
        assert qc.already_esl(f) == (False, True)

    def test_esm_and_esl_flags(self, tmp_path):
        f = make_plugin(tmp_path, "a.esm", esm=True, esl=True)
        assert qc.already_esl(f) == (True, True)


# ------------------------------------------------------------------ parsing helpers
class TestParsing:
    def test_create_data_list_splits_forms_and_grup_headers(self):
        body = simple_records(1, [0x800, 0x801])
        data = plugin((SKYRIM,), body)
        parts = qc.create_data_list(data)
        # TES4, GRUP header, two KYWD records
        assert [p[:4] for p in parts] == [b"TES4", b"GRUP", b"KYWD", b"KYWD"]
        assert b"".join(parts) == data
        assert len(parts[1]) == 24

    def test_get_master_count(self):
        data = plugin((SKYRIM, "Update.esm", "Mod.esp"))
        assert qc.get_master_count(qc.create_data_list(data), True, False) == (3, True)

    def test_get_master_count_without_skyrim(self):
        data = plugin(("Other.esp",))
        assert qc.get_master_count(qc.create_data_list(data), True, False) == (1, False)

    def test_get_master_count_no_masters(self):
        data = plugin(())
        assert qc.get_master_count(qc.create_data_list(data), True, False) == (0, False)

    def test_skyrim_master_detection_is_case_sensitive_on_exact_bytes(self):
        data = plugin(("skyrim.esm",))
        assert qc.get_master_count(qc.create_data_list(data), True, False) == (1, False)

    def test_get_from_file_missing_returns_empty_list(self, tmp_path):
        assert qc.get_from_file(str(tmp_path / "nope.json")) == []

    def test_get_from_file_bad_json_returns_empty_list(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        assert qc.get_from_file(str(p)) == []

    def test_get_from_file_reads_json(self, tmp_path):
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"a": [1]}))
        assert qc.get_from_file(str(p)) == {"a": [1]}


# ------------------------------------------------------------------ file_reader
@pytest.fixture
def reader_env(workdir):
    """file_reader reads class-level state that scan() normally sets up."""
    qc.max_record_id = 4096
    qc.num_max_records = 4096
    qc.dependent_dict = {}
    qc.missing_game_esm_as_master = {}
    qc.maxed_masters = []
    return workdir


class TestFileReader:
    def read(self, path, update_header=False, is_esm=False):
        return qc.file_reader(path, update_header, is_esm)

    def test_small_plugin_qualifies(self, reader_env):
        body = simple_records(1, range(0x800, 0x810))
        f = make_plugin(reader_env, "small.esp", body=body)
        # allowed, need_compacting, new_cell, interior, wrld, wthr
        assert self.read(f) == (True, False, False, False, False, False)

    def test_override_records_do_not_count(self, reader_env):
        # master index 0 (< master_count 1) = override of Skyrim.esm record
        recs = b"".join(record(b"KYWD", fid(0, 0x100 + i)) for i in range(5000))
        f = make_plugin(reader_env, "overrides.esp", body=grup(b"KYWD", recs))
        assert self.read(f)[0] is True

    def test_too_many_new_records_rejected(self, reader_env):
        body = simple_records(1, range(0x800, 0x800 + 4097))
        f = make_plugin(reader_env, "big.esp", body=body)
        ok, why = self.read(f)
        assert ok is False and why.startswith("max record count of 2048 exceeded")

    def test_rejection_caused_by_a_dependent_without_game_master_is_reported_as_adhseam(self, reader_env):
        body = simple_records(1, range(0x800, 0x800 + 2049))
        f = make_plugin(reader_env, "base.esp", body=body)
        qc.dependent_dict = {"base.esp": ["child.esp"]}
        qc.missing_game_esm_as_master = {"child.esp": "base.esp"}
        ok, why = self.read(f, update_header=True)
        assert ok is False and "not all dependent plugins have the game esm as a master" in why

    def test_exactly_4096_new_records_with_header_update_qualifies(self, reader_env):
        body = simple_records(1, range(0x800, 0x800 + 4096))
        f = make_plugin(reader_env, "edge.esp", body=body)
        qc.dependent_dict = {"edge.esp": []}
        assert self.read(f, update_header=True)[0] is True

    def test_2049_records_rejected_without_skyrim_master(self, reader_env):
        body = simple_records(1, range(0x800, 0x800 + 2049))
        f = make_plugin(reader_env, "noskyrim.esp", masters=("Other.esp",), body=body)
        assert self.read(f)[0] is False

    def test_2048_records_ok_without_skyrim_master(self, reader_env):
        body = simple_records(1, range(0x800, 0x800 + 2048))
        f = make_plugin(reader_env, "noskyrim.esp", masters=("Other.esp",), body=body)
        assert self.read(f)[0] is True

    def test_no_masters_limits_to_2048(self, reader_env):
        body = simple_records(0, range(0x800, 0x800 + 2049))
        f = make_plugin(reader_env, "nomasters.esp", masters=(), body=body)
        assert self.read(f)[0] is False

    def test_needs_compacting_when_id_above_fff(self, reader_env):
        body = simple_records(1, [0x800, 0x1001])
        f = make_plugin(reader_env, "high.esp", body=body)
        assert self.read(f) == (True, True, False, False, False, False)

    def test_id_0x1000_does_not_need_compacting(self, reader_env):
        body = simple_records(1, [0x1000])
        f = make_plugin(reader_env, "edge.esp", body=body)
        assert self.read(f)[1] is False

    def test_new_exterior_cell(self, reader_env):
        body = grup(b"CELL", cell_record(fid(1, 0x801), interior=False))
        f = make_plugin(reader_env, "cell.esp", body=body)
        assert self.read(f) == (True, False, True, False, False, False)

    def test_new_interior_cell(self, reader_env):
        body = grup(b"CELL", cell_record(fid(1, 0x801), interior=True))
        f = make_plugin(reader_env, "cell.esp", body=body)
        assert self.read(f) == (True, False, True, True, False, False)

    def test_new_interior_cell_compressed(self, reader_env):
        body = grup(b"CELL", cell_record(fid(1, 0x801), interior=True, compress=True))
        f = make_plugin(reader_env, "cellz.esp", body=body)
        assert self.read(f)[2:4] == (True, True)

    def test_cell_override_is_not_new_cell(self, reader_env):
        body = grup(b"CELL", cell_record(fid(0, 0x801), interior=True))
        f = make_plugin(reader_env, "cell.esp", body=body)
        assert self.read(f)[2] is False

    def test_new_worldspace_and_weather(self, reader_env):
        body = (grup(b"WRLD", record(b"WRLD", fid(1, 0x800)))
                + grup(b"WTHR", record(b"WTHR", fid(1, 0x801))))
        f = make_plugin(reader_env, "wrld.esp", body=body)
        res = self.read(f)
        assert res[0] is True and res[4] is True and res[5] is True      # (True, compact, cell, interior, wrld, wthr)

    def test_missing_tes4_header_is_skipped(self, reader_env, log):
        f = write(reader_env / "fake.esp", b"NOPE" + b"\x00" * 40)
        assert self.read(f) == (False, 'not plugin')
        assert any("No TES4 header" in line for line in log.file_lines)

    def test_unreadable_file_reports_error_and_reason(self, reader_env, log):
        res = self.read(str(reader_env / "does_not_exist.esp"))
        assert res == (False, 'read fail')
        assert log.errors

    def test_esm_cell_ids_written_for_esm(self, reader_env):
        os.makedirs("ESLifier_Data/Cell_IDs", exist_ok=True)
        body = grup(b"CELL", cell_record(fid(1, 0x801), interior=False))
        f = make_plugin(reader_env, "master.esm", body=body, esm=True)
        self.read(f, is_esm=True)
        out = reader_env / "ESLifier_Data" / "Cell_IDs" / "master.esm_CellFormIDs.txt"
        # stored as the first three bytes of the little-endian form id, hex encoded
        assert out.read_text().split() == ["010800"]

    def test_cell_ids_not_written_for_non_esm(self, reader_env):
        os.makedirs("ESLifier_Data/Cell_IDs", exist_ok=True)
        body = grup(b"CELL", cell_record(fid(1, 0x801), interior=False))
        f = make_plugin(reader_env, "plain.esp", body=body)
        self.read(f, is_esm=False)
        assert not (reader_env / "ESLifier_Data" / "Cell_IDs" / "plain.esp_CellFormIDs.txt").exists()


# ------------------------------------------------------------------ scan()
class TestScan:
    def setup_scan(self, workdir, g, plugins, dependents=None, maxed=None,
                   missing_skyrim=None, update_header=True):
        g.plugins = plugins
        g.update_header = update_header
        data = workdir / "ESLifier_Data"
        (data / "dependency_dictionary.json").write_text(json.dumps(dependents or {
            os.path.basename(p).lower(): [] for p in plugins}))
        (data / "maxed_masters.json").write_text(json.dumps(maxed or []))
        (data / "missing_game_as_master.json").write_text(json.dumps(missing_skyrim or {}))

    def test_scan_flags_and_output_file(self, workdir, g):
        small = make_plugin(workdir, "small.esp", body=simple_records(1, [0x800]))
        compact = make_plugin(workdir, "compact.esp", body=simple_records(1, [0x800, 0x2000]))
        cell = make_plugin(workdir, "cell.esp",
                           body=grup(b"CELL", cell_record(fid(1, 0x800), interior=True)))
        big = make_plugin(workdir, "big.esp", body=simple_records(1, range(0x800, 0x800 + 5000)))
        already = make_plugin(workdir, "already.esp", esl=True)
        esl_ext = write(workdir / "x.esl", plugin((SKYRIM,)))
        self.setup_scan(workdir, g, [small, compact, cell, big, already, esl_ext])

        result = qc.scan()

        assert result[small] == ["esl_flaggable"]    # new in current main: plugins that already qualify are flagged
        assert result[compact] == ["need_compacting"]
        assert set(result[cell]) == {"esl_flaggable", "new_cell", "new_interior_cell"}
        assert len(result[big]) == 1 and result[big][0].startswith("max record count of 4096 exceeded")     # rejected plugins are now listed with their reason
        assert already not in result   # already ESL flagged
        assert esl_ext not in result   # .esl files are skipped entirely
        on_disk = json.loads((workdir / "ESLifier_Data" / "flag_dictionary.json").read_text())
        assert on_disk == result

    def test_scan_flags_esm_plugins(self, workdir, g):
        esm = make_plugin(workdir, "m.esm", body=simple_records(1, [0x800]), esm=True)
        self.setup_scan(workdir, g, [esm])
        assert qc.scan()[esm] == ["esl_flaggable", "is_esm"]

    def test_scan_flags_maxed_masters_for_cell_plugin(self, workdir, g):
        cell = make_plugin(workdir, "cell.esp",
                           body=grup(b"CELL", cell_record(fid(1, 0x800), interior=False)))
        self.setup_scan(workdir, g, [cell], maxed=[cell])
        assert "maxed_masters" in qc.scan()[cell]

    def test_scan_flags_maxed_masters_via_dependents(self, workdir, g):
        cell = make_plugin(workdir, "cell.esp",
                           body=grup(b"CELL", cell_record(fid(1, 0x800), interior=False)))
        self.setup_scan(workdir, g, [cell], maxed=["child.esp"],
                        dependents={"cell.esp": ["child.esp"]})
        assert "maxed_masters" in qc.scan()[cell]

    def test_scan_wipes_stale_cell_id_files(self, workdir, g):
        stale = workdir / "ESLifier_Data" / "Cell_IDs"
        stale.mkdir()
        (stale / "old.esm_CellFormIDs.txt").write_text("x")
        self.setup_scan(workdir, g, [])
        qc.scan()
        assert os.listdir(stale) == []

    def test_scan_marks_adhseam_when_dependent_lacks_skyrim_master(self, workdir, g):
        # A dependent that has this plugin as its first master (and no Skyrim.esm)
        # drops the record limit to 2048. If the plugin has more than that, it is
        # rejected and reported as a "possible_adhseam_problem" instead of being dropped silently.
        p = make_plugin(workdir, "base.esp", body=simple_records(1, range(0x800, 0x800 + 2049)))
        self.setup_scan(workdir, g, [p],
                        dependents={"base.esp": ["child.esp"]},
                        missing_skyrim={"child.esp": "base.esp"})
        [why] = qc.scan()[p]
        assert why.startswith("max record count of 2048 exceeded") and "not all dependent plugins have the game esm as a master" in why

    def test_scan_without_header_update_uses_2048_limit(self, workdir, g):
        p = make_plugin(workdir, "mid.esp", body=simple_records(1, range(0x800, 0x800 + 2049)))
        self.setup_scan(workdir, g, [p], update_header=False)
        [why] = qc.scan()[p]
        assert why.startswith("max record count of 2048 exceeded") and "header update disabled" in why

    def test_scan_lists_unreadable_and_fake_plugins_with_their_reason(self, workdir, g):
        fake = write(workdir / "fake.esp", b"NOPE" + b"\x00" * 40)
        self.setup_scan(workdir, g, [fake])
        assert qc.scan()[fake] == ["not plugin"]
