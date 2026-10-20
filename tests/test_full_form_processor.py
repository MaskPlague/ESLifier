"""full_form_processor: knows where Form IDs live inside each record type, and rewrites them."""
import struct

from full_form_processor import form_processor as fp
from plugin_builder import fid, record, sub, grup


class TestHelpers:
    def test_get_offsets_from_array(self):
        # field starts at 10; payload begins at 16; 12 bytes / 4 = 3 ids
        assert fp.get_offsets_from_array(10, 12) == [16, 20, 24]

    def test_get_offsets_from_array_custom_struct(self):
        assert fp.get_offsets_from_array(0, 24, struct_size=12) == [6, 18]

    def test_get_field_and_size_normal(self):
        form = b"\x00" * 24 + sub(b"EDID", b"abc\x00")
        assert fp.get_field_and_size(24, form) == (b"EDID", 4, 24)

    def test_get_field_and_size_xxxx_extended(self):
        # XXXX holds the real size of the *next* field
        payload_size = 70000
        form = (b"\x00" * 24 + b"XXXX" + struct.pack("<H", 4) + struct.pack("<I", payload_size)
                + b"VMAD" + struct.pack("<H", 0) + b"\x00" * payload_size)
        field, size, offset = fp.get_field_and_size(24, form)
        assert field == b"VMAD"
        assert size == payload_size
        assert offset == 24 + 6 + 4

    def test_get_alt_texture_offsets(self):
        # count=2; each entry: size(4) name(size) texture-formid(4) index(4)
        n1, n2 = b"abc", b"hello!"
        body = struct.pack("<I", 2)
        body += struct.pack("<I", len(n1)) + n1 + fid(1, 0x800) + struct.pack("<i", 0)
        body += struct.pack("<I", len(n2)) + n2 + fid(1, 0x801) + struct.pack("<i", 1)
        form = b"\x00" * 24 + sub(b"MODS", body)
        offsets = fp.get_alt_texture_offsets(24, form)
        assert [form[o:o + 4] for o in offsets] == [fid(1, 0x800), fid(1, 0x801)]


class TestSaveAllFormData:
    def test_default_record_only_has_own_form_id(self):
        rec = record(b"KYWD", fid(1, 0x800), sub(b"EDID", b"x\x00"))
        saved = fp.save_all_form_data([rec])
        assert saved == [[0, bytearray(rec), [12]]]

    def test_refr_collects_name_and_other_reference_fields(self):
        subs = (sub(b"NAME", fid(1, 0x900)) + sub(b"XOWN", fid(1, 0x901))
                + sub(b"EDID", b"ignored"))
        rec = record(b"REFR", fid(1, 0x800), subs)
        (i, form, offsets), = fp.save_all_form_data([rec])
        ids = [bytes(form[o:o + 4]) for o in offsets]
        assert ids == [fid(1, 0x800), fid(1, 0x900), fid(1, 0x901)]

    def test_refr_xlkr_has_two_ids(self):
        rec = record(b"REFR", fid(1, 0x800), sub(b"XLKR", fid(1, 0x900) + fid(1, 0x901)))
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert [bytes(form[o:o + 4]) for o in offsets] == [fid(1, 0x800), fid(1, 0x900), fid(1, 0x901)]

    def test_short_fields_are_ignored(self):
        # a NAME field smaller than 4 bytes cannot be a form id
        rec = record(b"REFR", fid(1, 0x800), sub(b"NAME", b"\x01\x02"))
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert offsets == [12]

    def test_flst_collects_every_lnam(self):
        subs = sub(b"LNAM", fid(1, 0x900)) + sub(b"LNAM", fid(0, 0x12))
        rec = record(b"FLST", fid(1, 0x800), subs)
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert [bytes(form[o:o + 4]) for o in offsets] == [fid(1, 0x800), fid(1, 0x900), fid(0, 0x12)]

    def test_cell_xclr_regions_array(self):
        subs = sub(b"XCLR", fid(1, 0x900) + fid(1, 0x901))
        rec = record(b"CELL", fid(1, 0x800), subs)
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert [bytes(form[o:o + 4]) for o in offsets] == [fid(1, 0x800), fid(1, 0x900), fid(1, 0x901)]

    def test_stat_mods_alternate_textures(self):
        name = b"tex"
        mods = struct.pack("<I", 1) + struct.pack("<I", len(name)) + name + fid(1, 0x900) + struct.pack("<i", 0)
        rec = record(b"STAT", fid(1, 0x800), sub(b"MODS", mods))
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert [bytes(form[o:o + 4]) for o in offsets] == [fid(1, 0x800), fid(1, 0x900)]

    def test_tes4_onam_overridden_forms(self):
        tes4_rec = record(b"TES4", b"\x00" * 4, sub(b"ONAM", fid(0, 0x10) + fid(0, 0x11)))
        (i, form, offsets), = fp.save_all_form_data([tes4_rec])
        assert [bytes(form[o:o + 4]) for o in offsets] == [fid(0, 0x10), fid(0, 0x11)]

    def test_grup_types_with_parent_form_ids(self):
        # group types 1,6,7,8,9 store the parent's form id in the label (offset 8)
        for gtype, expected in ((0, []), (1, [8]), (2, []), (6, [8]), (7, [8]), (8, [8]), (9, [8])):
            g = grup(fid(1, 0x800), b"", group_type=gtype)
            (i, form, offsets), = fp.save_all_form_data([g])
            assert offsets == expected, gtype

    def test_unknown_record_type_logs_error_and_is_skipped(self, log):
        rec = record(b"ZZZZ", fid(1, 0x800))
        assert fp.save_all_form_data([rec]) == []
        assert any("ZZZZ" in e for e in log.errors)

    def test_indices_match_data_list_positions(self):
        recs = [record(b"KYWD", fid(1, 0x800 + n)) for n in range(3)]
        saved = fp.save_all_form_data(recs)
        assert [s[0] for s in saved] == [0, 1, 2]


def _forms(*recs):
    data_list = list(recs)
    return data_list, fp.save_all_form_data(data_list)


class TestPatchFormData:
    MASTER_BYTE = b"\x01"  # plugin has one master

    def test_replaces_own_ids_and_references(self):
        refr = record(b"REFR", fid(1, 0x2000), sub(b"NAME", fid(1, 0x3000)))
        data_list, saved = _forms(refr)
        replacements = {fid(1, 0x2000)[:3]: b"\x00\x00\x00", fid(1, 0x3000)[:3]: b"\x01\x00\x00"}
        out = fp.patch_form_data(data_list, saved, replacements, self.MASTER_BYTE, set(), False, -1)
        assert out[0][12:16] == fid(1, 0x000000)
        assert out[0][24 + 6:24 + 10] == fid(1, 0x000001)

    def test_references_to_masters_are_untouched(self):
        # same 3 low bytes as a replacement key, but owned by master 0 (Skyrim.esm)
        refr = record(b"REFR", fid(1, 0x2000), sub(b"NAME", fid(0, 0x2000)))
        data_list, saved = _forms(refr)
        out = fp.patch_form_data(data_list, saved, {fid(1, 0x2000)[:3]: b"\x05\x00\x00"},
                                 self.MASTER_BYTE, set(), False, -1)
        assert out[0][12:16] == fid(1, 0x5)
        assert out[0][24 + 6:24 + 10] == fid(0, 0x2000)

    def test_unmapped_ids_left_alone(self):
        rec = record(b"KYWD", fid(1, 0x2000))
        data_list, saved = _forms(rec)
        out = fp.patch_form_data(data_list, saved, {}, self.MASTER_BYTE, set(), False, -1)
        assert out[0] == rec

    def test_output_is_bytes_and_in_place(self):
        rec = record(b"KYWD", fid(1, 0x2000))
        data_list, saved = _forms(rec)
        out = fp.patch_form_data(data_list, saved, {}, self.MASTER_BYTE, set(), False, -1)
        assert out is data_list and all(isinstance(x, bytes) for x in out)

    def test_update_masters_bumps_master_byte_when_cell_master_added(self):
        # with a cell master appended, new records move from master byte 1 -> 2
        refr = record(b"REFR", fid(1, 0x2000), sub(b"NAME", fid(1, 0x3000)))
        data_list, saved = _forms(refr)
        replacements = {fid(1, 0x2000)[:3]: b"\x00\x00\x00", fid(1, 0x3000)[:3]: b"\x01\x00\x00"}
        form_ids = {fid(1, 0x2000), fid(1, 0x3000)}
        out = fp.patch_form_data(data_list, saved, replacements, self.MASTER_BYTE, form_ids, True, -1)
        assert out[0][12:16] == b"\x00\x00\x00\x02"
        assert out[0][30:34] == b"\x01\x00\x00\x02"

    def test_update_masters_cell_replacement_with_explicit_master(self):
        # 4-byte replacement means "this form id now lives in the cell master"
        rec = record(b"CELL", fid(1, 0x2000))
        data_list, saved = _forms(rec)
        replacements = {fid(1, 0x2000)[:3]: b"\x07\x00\x00\x03"}
        out = fp.patch_form_data(data_list, saved, replacements, self.MASTER_BYTE, set(), True, -1)
        assert out[0][12:16] == b"\x07\x00\x00\x03"

    def test_update_masters_unmapped_form_still_moves_master_byte(self):
        rec = record(b"KYWD", fid(1, 0x2000))
        data_list, saved = _forms(rec)
        out = fp.patch_form_data(data_list, saved, {}, self.MASTER_BYTE, {fid(1, 0x2000)}, True, -1)
        assert out[0][12:16] == fid(2, 0x2000)

    def test_update_masters_with_existing_cell_master_keeps_master_byte(self):
        rec = record(b"KYWD", fid(1, 0x2000))
        data_list, saved = _forms(rec)
        out = fp.patch_form_data(data_list, saved, {fid(1, 0x2000)[:3]: b"\x01\x00\x00"},
                                 self.MASTER_BYTE, {fid(1, 0x2000)}, True, 5)
        assert out[0][12:16] == fid(1, 0x1)


class TestPatchFormDataDependent:
    """A dependent plugin whose master #2 is the plugin being compacted."""

    MASTER_INDEX = b"\x02"

    def test_patches_references_to_compacted_master(self):
        refr = record(b"REFR", fid(3, 0x800), sub(b"NAME", fid(2, 0x2000)))
        data_list, saved = _forms(refr)
        out = fp.patch_form_data_dependent(
            data_list, saved, {fid(2, 0x2000)[:3]: b"\x01\x00\x00"},
            self.MASTER_INDEX, b"", set(), False, -1)
        assert out[0][12:16] == fid(3, 0x800)
        assert out[0][30:34] == fid(2, 0x1)

    def test_references_to_other_masters_untouched(self):
        refr = record(b"REFR", fid(3, 0x800), sub(b"NAME", fid(1, 0x2000)))
        data_list, saved = _forms(refr)
        out = fp.patch_form_data_dependent(
            data_list, saved, {fid(1, 0x2000)[:3]: b"\x01\x00\x00"},
            self.MASTER_INDEX, b"", set(), False, -1)
        assert out[0][30:34] == fid(1, 0x2000)

    def test_with_cell_master_added_own_ids_shift_and_refs_patch(self):
        # dependent has 3 masters (indexes 0-2), own records use 3; cell master becomes index 3
        refr = record(b"REFR", fid(3, 0x800), sub(b"NAME", fid(2, 0x2000)))
        data_list, saved = _forms(refr)
        out = fp.patch_form_data_dependent(
            data_list, saved, {fid(2, 0x2000)[:3]: b"\x01\x00\x00"},
            self.MASTER_INDEX, b"\x03", {fid(3, 0x800)}, True, -1)
        assert out[0][12:16] == fid(4, 0x800)       # own record moved up by one
        assert out[0][30:34] == fid(2, 0x1)         # patched ref into compacted master

    def test_with_cell_master_added_cell_reference_redirected_to_cell_master(self):
        refr = record(b"REFR", fid(3, 0x800), sub(b"NAME", fid(2, 0x2000)))
        data_list, saved = _forms(refr)
        out = fp.patch_form_data_dependent(
            data_list, saved, {fid(2, 0x2000)[:3]: b"\x09\x00\x00\x03"},
            self.MASTER_INDEX, b"\x03", {fid(3, 0x800)}, True, -1)
        assert out[0][30:34] == b"\x09\x00\x00\x03"
