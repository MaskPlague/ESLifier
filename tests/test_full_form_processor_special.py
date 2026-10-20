"""
full_form_processor.save_*_data: handlers whose Form ID locations depend on sizes, counts, flags or other
sub-records. Each test builds a real sub-record layout with unique marker ids and asserts which markers are reported.
"""
import struct

from full_form_processor_sse import form_processor as fp
from plugin_builder import fid, record, sub, call_with_timeout

OWN = fid(1, 0x800)
Z = b"\x00" * 4
_n = [0]


def m():
    _n[0] += 1
    return fid(1, 0x2000 + _n[0])


def u32(n):
    return struct.pack("<I", n)


def ids_of(rec):
    (i, form, offsets), = call_with_timeout(fp.save_all_form_data, [rec])
    return [bytes(form[o:o + 4]) for o in offsets]


def check(rtype, subs, expected):
    assert ids_of(record(rtype, OWN, subs)) == [OWN] + list(expected)


# ------------------------------------------------------------------------------------------ ACHR
def test_achr_pdto_target_is_only_a_form_id_when_the_type_byte_is_zero():
    a, b = m(), m()
    check(b"ACHR", sub(b"PDTO", b"\x00\x00\x00\x00" + a + Z), [a])
    check(b"ACHR", sub(b"PDTO", b"\x01\x00\x00\x00" + b + Z), [])


# ------------------------------------------------------------------------------------------ CLMT / DOBJ / COLL / REGN / WRLD
def test_clmt_wlst_has_a_weather_and_a_global_per_12_byte_entry():
    a, b, c, d = m(), m(), m(), m()
    check(b"CLMT", sub(b"WLST", a + Z + b + c + Z + d), [a, b, c, d])


def test_dobj_dnam_has_a_form_id_in_the_second_half_of_each_8_byte_entry():
    a, b = m(), m()
    check(b"DOBJ", sub(b"DNAM", b"ACTI" + a + b"ALCH" + b), [a, b])


def test_coll_cnam_has_as_many_ids_as_the_intv_count_says():
    a, b, c = m(), m(), m()
    check(b"COLL", sub(b"INTV", u32(2) + Z) + sub(b"CNAM", a + b + c), [a, b])


def test_coll_cnam_without_intv_reports_nothing():
    check(b"COLL", sub(b"CNAM", m()), [])


def test_regn_rdwt_has_ids_at_the_start_and_end_of_each_12_byte_entry():
    a, b, c, d = m(), m(), m(), m()
    check(b"REGN", sub(b"RDWT", a + Z + b + c + Z + d), [a, b, c, d])


def test_wrld_rnam_reads_a_pair_count_then_one_id_per_8_byte_pair():
    a, b = m(), m()
    check(b"WRLD", sub(b"RNAM", Z + u32(2) + a + Z + b + Z), [a, b])


# ------------------------------------------------------------------------------------------ ENCH / WEAP / PERK / NOTE
def test_ench_enit_layout_depends_on_the_field_size():
    a, b = m(), m()
    base = b"\x00" * 28
    check(b"ENCH", sub(b"ENIT", base + a + b), [a, b])                          # 36 bytes (SSE)
    check(b"ENCH", sub(b"ENIT", base + a), [a])                                 # 32 bytes
    check(b"ENCH", sub(b"ENIT", base + a + b + b"\x00" * 4), [])               # 40 bytes: unknown layout


def test_weap_crdt_spell_offset_depends_on_the_field_size():
    a, b = m(), m()
    check(b"WEAP", sub(b"CRDT", b"\x00" * 12 + a), [a])                         # 16 bytes (LE)
    check(b"WEAP", sub(b"CRDT", b"\x00" * 16 + b + b"\x00" * 4), [b])           # 24 bytes (SSE)
    check(b"WEAP", sub(b"CRDT", b"\x00" * 20), [])


def test_perk_data_is_a_form_id_only_when_it_is_4_or_8_bytes():
    a, b = m(), m()
    check(b"PERK", sub(b"DATA", a), [a])
    check(b"PERK", sub(b"DATA", b + Z), [b])
    check(b"PERK", sub(b"DATA", b"\x01\x02\x03\x04\x05"), [])


def test_perk_epfd_is_a_form_id_for_function_types_3_4_and_5():
    for epft, expect in ((1, False), (2, False), (3, True), (4, True), (5, True), (6, False)):
        x = m()
        subs = sub(b"EPFT", bytes([epft])) + sub(b"EPFD", x)
        check(b"PERK", subs, [x] if expect else [])


def test_note_tnam_is_a_form_id_only_when_data_type_is_3():
    a, b = m(), m()
    check(b"NOTE", sub(b"DATA", b"\x03") + sub(b"TNAM", a), [a])
    check(b"NOTE", sub(b"DATA", b"\x01") + sub(b"TNAM", b), [])


# ------------------------------------------------------------------------------------------ LCTN
def test_lctn_reference_lists():
    ids = [m() for _ in range(14)]
    subs = (sub(b"ACPR", ids[0] + ids[1] + Z + ids[2] + ids[3] + Z)          # 2 x 12: ref + location
            + sub(b"LCEP", ids[4] + ids[5] + Z)
            + sub(b"ACUN", ids[6] + ids[7] + ids[8])                         # 12: actor, ref, location
            + sub(b"LCSR", ids[9] + ids[10] + ids[11] + Z)                   # 16: three ids + grid
            + sub(b"RCPR", ids[12] + ids[13]))
    check(b"LCTN", subs, [ids[0], ids[1], ids[2], ids[3], ids[4], ids[5], ids[6], ids[7], ids[8],
                          ids[9], ids[10], ids[11], ids[12], ids[13]])


# ------------------------------------------------------------------------------------------ MGEF / MUST
def test_mgef_sndd_has_a_sound_id_in_the_second_half_of_each_8_byte_entry():
    a, b = m(), m()
    check(b"MGEF", sub(b"SNDD", u32(0) + a + u32(1) + b), [a, b])


def test_mgef_data_reports_each_known_form_id_slot():
    slots = [8, 24, 32, 36, 72, 76, 92, 96, 100, 108, 116, 120, 124, 128, 132, 136]
    payload = bytearray(152)
    expected = []
    for s in slots:
        x = m()
        payload[s:s + 4] = x
        expected.append(x)
    check(b"MGEF", sub(b"DATA", bytes(payload)), expected)


def test_must_snam_skips_null_entries():
    a, b = m(), m()
    check(b"MUST", sub(b"SNAM", a + Z + b), [a, b])


# ------------------------------------------------------------------------------------------ NAVI / NAVM
def test_navi_nvpp_path_table_then_node_table():
    p1, p2, p3, n1, n2 = m(), m(), m(), m(), m()
    payload = (u32(2)
               + u32(2) + p1 + p2                                  # path 1: two ids
               + u32(1) + p3                                       # path 2: one id
               + u32(2) + n1 + Z + n2 + Z)                         # node table: id + 4 more bytes each
    check(b"NAVI", sub(b"NVPP", payload), [p1, p2, p3, n1, n2])


def test_navi_nvmi_walks_all_the_counted_lists_and_ends_with_world_and_cell():
    navmesh, mg1, mg2, pref, d1, d2, world, cell = (m() for _ in range(8))
    payload = (navmesh + b"\x00" * 20
               + u32(2) + mg1 + mg2
               + u32(1) + pref
               + u32(2) + Z + d1 + Z + d2
               + world + cell)
    check(b"NAVI", sub(b"NVMI", payload), [navmesh, mg1, mg2, pref, d1, d2, world, cell])


def test_navi_nvsi_is_a_plain_array():
    a, b = m(), m()
    check(b"NAVI", sub(b"NVSI", a + b), [a, b])


def test_navm_nvnm_skips_vertices_and_triangles_to_find_connections_and_door_triangles():
    world, cell, c1, c2, door = (m() for _ in range(5))
    payload = (b"\x00" * 8 + world + cell
               + u32(2) + b"\x00" * 24                              # 2 vertices x 12 bytes
               + u32(1) + b"\x00" * 16                              # 1 triangle x 16 bytes
               + u32(2) + Z + c1 + b"\x00" * 2 + Z + c2 + b"\x00" * 2   # connections: 10 bytes, navmesh at +4
               + u32(1) + b"\x00" * 6 + door)                        # door triangle: 10 bytes, REFR at +6
    check(b"NAVM", sub(b"NVNM", payload), [world, cell, c1, c2, door])
