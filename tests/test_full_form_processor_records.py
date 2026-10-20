"""
full_form_processor.save_*_data: where each record type keeps its Form IDs.

Table-driven. SPEC lists, per record type, the sub-records that hold exactly one form id at payload offset 0
("simple"), and the "special" sub-records (arrays of ids, alternate-texture lists, ids at fixed payload offsets).
Every field gets a unique marker form id; the test asserts that exactly those markers (plus the record's own id)
are reported, in order. Sub-records that need real structure (VMAD, CTDA, size/conditional/looping handlers) are
covered in test_full_form_processor_special.py.

SPEC was produced from the v0.16.17 handlers; if a handler changes which ids it reports this test fails.
"""
import struct

import pytest

from full_form_processor_sse import form_processor as fp
from plugin_builder import fid, record, sub, call_with_timeout

OWN = fid(1, 0x800)


SPEC = {
    b'ACHR': (
        [b"NAME", b"XEZN", b"INAM", b"XMRC", b"XAPR", b"XLRT", b"XHOR", b"XOWN", b"XESP", b"XLCN", b"XLRL", b"XEMI", b"XMBR", b"TNAM"],
        [
            ((b"XLKR",), "offs", [0, 4]),
        ]),
    b'ACTI': (
        [b"SNAM", b"VNAM", b"WNAM", b"KNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"MODS",), "alt", None),
        ]),
    b'ADDN': (
        [b"SNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'ALCH': (
        [b"YNAM", b"ZNAM", b"EFID", b"ETYP"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"ENIT",), "offs", [8, 16]),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'AMMO': (
        [b"YNAM", b"ZNAM", b"DATA"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'ANIO': (
        [],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'APPA': (
        [b"YNAM", b"ZNAM"],
        [
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"MODS",), "alt", None),
        ]),
    b'ARMA': (
        [b"RNAM", b"NAM0", b"NAM1", b"NAM2", b"NAM3", b"MODL", b"SNDD", b"ONAM"],
        [
            ((b"MO2S", b"MO3S", b"MO4S", b"MO5S"), "alt", None),
        ]),
    b'ARMO': (
        [b"EITM", b"YNAM", b"ZNAM", b"ETYP", b"BIDS", b"BAMT", b"RNAM", b"MODL", b"TNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS", b"MO2S", b"MO4S"), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'ARTO': (
        [],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'ASPC': (
        [b"SNAM", b"RDAT", b"BNAM"],
        [
        ]),
    b'AVIF': (
        [b"PNAM", b"SNAM"],
        [
        ]),
    b'BOOK': (
        [b"YNAM", b"ZNAM", b"INAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"DATA",), "offs", [4]),
        ]),
    b'BPTD': (
        [b"RAGA"],
        [
            ((b"MODS",), "alt", None),
            ((b"BPND",), "offs", [12, 16, 32, 36, 68, 72]),
        ]),
    b'CAMS': (
        [b"MNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'CELL': (
        [b"LTMP", b"XLCN", b"XCWT", b"XOWN", b"XILL", b"XCCM", b"XCAS", b"XEZN", b"XCMO", b"XCIM"],
        [
            ((b"XCLR",), "array", None),
        ]),
    b'CLMT': (
        [],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'COBJ': (
        [b"CNAM", b"BNAM", b"CNTO"],
        [
            ((b"COED",), "offs", [0, 4]),
        ]),
    b'COLL': (
        [],
        [
        ]),
    b'CONT': (
        [b"SNAM", b"QNAM", b"CNTO"],
        [
            ((b"MODS",), "alt", None),
            ((b"COED",), "offs", [0, 4]),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'CPTH': (
        [b"SNAM"],
        [
            ((b"ANAM",), "offs", [0, 4]),
        ]),
    b'DIAL': (
        [b"QNAM", b"BNAM"],
        [
        ]),
    b'DLBR': (
        [b"QNAM", b"SNAM"],
        [
        ]),
    b'DLVW': (
        [b"QNAM", b"BNAM", b"TNAM"],
        [
        ]),
    b'DOBJ': (
        [],
        [
        ]),
    b'DOOR': (
        [b"SNAM", b"ANAM", b"BNAM", b"TNAM"],
        [
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'DUAL': (
        [],
        [
        ]),
    b'ECZN': (
        [],
        [
            ((b"DATA",), "offs", [0, 4]),
        ]),
    b'EFSH': (
        [],
        [
            ((b"DATA",), "offs", [244, 308]),
        ]),
    b'ENCH': (
        [b"EFID"],
        [
        ]),
    b'EQUP': (
        [],
        [
            ((b"PNAM",), "array", None),
        ]),
    b'EXPL': (
        [b"EITM", b"MNAM"],
        [
            ((b"DATA",), "offs", [0, 4, 8, 12, 16, 20]),
            ((b"MODS",), "alt", None),
        ]),
    b'FACT': (
        [b"XNAM", b"JAIL", b"WAIT", b"STOL", b"PLCN", b"CRGR", b"JOUT", b"VEND", b"VENC"],
        [
            ((b"PLVD",), "offs", [4]),
        ]),
    b'FLOR': (
        [b"PFIG", b"SNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'FLST': (
        [b"LNAM"],
        [
        ]),
    b'FSTP': (
        [b"DATA"],
        [
        ]),
    b'FSTS': (
        [],
        [
            ((b"DATA",), "array", None),
        ]),
    b'FURN': (
        [b"KNAM", b"NAM1", b"FNMK"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'GLOB': (
        [],
        [
        ]),
    b'HAZD': (
        [b"MNAM"],
        [
            ((b"DATA",), "offs", [24, 28, 32, 36]),
            ((b"MODS",), "alt", None),
        ]),
    b'HDPT': (
        [b"HNAM", b"TNAM", b"RNAM", b"CNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'IDLE': (
        [],
        [
            ((b"ANAM",), "offs", [0, 4]),
        ]),
    b'IDLM': (
        [],
        [
            ((b"IDLA",), "array", None),
            ((b"MODS",), "alt", None),
        ]),
    b'INFO': (
        [b"PNAM", b"TCLT", b"DNAM", b"SNAM", b"LNAM", b"ANAM", b"TWAT", b"ONAM", b"TPIC"],
        [
            ((b"TRDT",), "offs", [16]),
        ]),
    b'INGR': (
        [b"YNAM", b"ZNAM", b"EFID", b"ETYP"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'IPCT': (
        [b"DNAM", b"ENAM", b"SNAM", b"NAM1", b"NAM2"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'IPDS': (
        [],
        [
            ((b"PNAM",), "offs", [0, 4]),
        ]),
    b'KEYM': (
        [b"YNAM", b"ZNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'LAND': (
        [b"ATXT", b"BTXT"],
        [
        ]),
    b'LCTN': (
        [b"ACEC", b"LCEC", b"PNAM", b"NAM1", b"FNAM", b"MNAM", b"NAM0"],
        [
            ((b"RCPR", b"ACID", b"LCID"), "array", None),
            ((b"KWDA",), "array", None),
        ]),
    b'LIGH': (
        [b"SNAM", b"LNAM"],
        [
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"MODS",), "alt", None),
        ]),
    b'LSCR': (
        [b"NNAM"],
        [
        ]),
    b'LTEX': (
        [b"TNAM", b"MNAM", b"GNAM"],
        [
        ]),
    b'LVLI': (
        [b"LVLG"],
        [
            ((b"LVLO",), "offs", [4]),
            ((b"COED",), "offs", [0, 4]),
        ]),
    b'LVLN': (
        [b"LVLG"],
        [
            ((b"COED",), "offs", [0, 4]),
            ((b"MODS",), "alt", None),
            ((b"LVLO",), "offs", [4]),
        ]),
    b'LVSP': (
        [],
        [
            ((b"LVLO",), "offs", [4]),
        ]),
    b'MATT': (
        [b"HNAM", b"PNAM"],
        [
        ]),
    b'MESG': (
        [b"QNAM", b"INAM"],
        [
        ]),
    b'MGEF': (
        [b"MDOB", b"ESCE"],
        [
            ((b"KWDA",), "array", None),
            ((b"DATA",), "offs", [8, 24, 32, 36, 72, 76, 92, 96, 100, 108, 116, 120, 124, 128, 132, 136]),
        ]),
    b'MISC': (
        [b"YNAM", b"ZNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'MSTT': (
        [b"SNAM"],
        [
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'MUSC': (
        [],
        [
            ((b"TNAM",), "array", None),
        ]),
    b'MUST': (
        [],
        [
        ]),
    b'NAVI': (
        [],
        [
            ((b"NVSI",), "array", None),
        ]),
    b'NAVM': (
        [],
        [
            ((b"ONAM",), "array", None),
        ]),
    b'NOTE': (
        [b"ONAM", b"YNAM", b"ZNAM", b"SNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'NPC_': (
        [b"INAM", b"VTCK", b"TPLT", b"RNAM", b"SPLO", b"WNAM", b"ANAM", b"ATKR", b"SPOR", b"OCOR", b"GWOR", b"ECOR", b"PKID", b"CNTO", b"CNAM", b"PNAM", b"HCLF", b"ZNAM", b"GNAM", b"CSDI", b"CSCR", b"DOFT", b"SOFT", b"DPLT", b"CRIF", b"FTST", b"SNAM", b"PRKR"],
        [
            ((b"KWDA",), "array", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"ATKD",), "offs", [2, 26]),
            ((b"COED",), "offs", [0, 4]),
        ]),
    b'OTFT': (
        [],
        [
            ((b"INAM",), "array", None),
        ]),
    b'PACK': (
        [b"CNAM", b"QNAM", b"TPIC", b"INAM"],
        [
            ((b"IDLA",), "array", None),
            ((b"PKCU", b"PDTO", b"PLDT", b"PTDA"), "offs", [4]),
        ]),
    b'PERK': (
        [b"NNAM"],
        [
        ]),
    b'PGRE': (
        [b"NAME", b"XEZN", b"XOWN", b"XPWR", b"XAPR", b"XESP", b"XEMI", b"XMBR", b"XLRL", b"XLRT"],
        [
            ((b"XLKR",), "offs", [0, 4]),
        ]),
    b'PLYR': (
        [b"PLYR"],
        [
        ]),
    b'PROJ': (
        [],
        [
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DATA",), "offs", [16, 20, 36, 40, 56, 60, 64, 84, 88]),
            ((b"MODS", b"DMDS"), "alt", None),
        ]),
    b'QUST': (
        [b"QTGL", b"NAM0", b"ALCO", b"ALEQ", b"KNAM", b"ALRT", b"ALFL", b"ALFR", b"ALUA", b"CNTO", b"SPOR", b"OCOR", b"GWOR", b"ECOR", b"ALDN", b"ALSP", b"ALFC", b"ALPC", b"VTCK", b"QSTA"],
        [
            ((b"KWDA",), "array", None),
            ((b"COED",), "offs", [0, 4]),
        ]),
    b'RACE': (
        [b"SPLO", b"WNAM", b"ATKR", b"GNAM", b"NAM4", b"NAM5", b"NAM7", b"ONAM", b"LNAM", b"MTYP", b"QNAM", b"UNES", b"WKMV", b"HEAD", b"RPRF", b"DFTF", b"ENAM", b"RNMV", b"SWMV", b"FLMV", b"SNMV", b"SPMV", b"RPRM", b"AHCM", b"FTSM", b"DFTM", b"TIND", b"TINC", b"NAM8", b"RNAM", b"AHCF", b"FTSF", b"HNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"VTCK", b"DNAM", b"HCLF"), "offs", [0, 4]),
            ((b"ATKD",), "offs", [8, 26]),
            ((b"MODS",), "alt", None),
        ]),
    b'REFR': (
        [b"NAME", b"LNAM", b"INAM", b"XLRM", b"XEMI", b"XLIB", b"XLRT", b"XOWN", b"XEZN", b"XMBR", b"XPWR", b"XATR", b"XLRL", b"XAPR", b"XTEL", b"XNDP", b"XESP", b"XLTW", b"XTNM", b"XCZC", b"XCZR", b"XSPC", b"XLCN"],
        [
            ((b"XORD",), "offs", [0, 4, 8, 12]),
        ]),
    b'REGN': (
        [b"WNAM", b"RDMO", b"RDGS", b"RDOT"],
        [
            ((b"RDSA",), "array12", None),
        ]),
    b'RELA': (
        [],
        [
            ((b"DATA",), "offs", [0, 4, 12]),
        ]),
    b'RFCT': (
        [],
        [
            ((b"DATA",), "offs", [0, 4]),
        ]),
    b'RGDL': (
        [b"XNAM", b"TNAM"],
        [
        ]),
    b'SCEN': (
        [b"PNAM", b"DATA"],
        [
        ]),
    b'SCOL': (
        [b"ONAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'SCRL': (
        [b"MDOB", b"ETYP", b"YNAM", b"ZNAM", b"EFID"],
        [
            ((b"KWDA",), "array", None),
            ((b"SPIT",), "offs", [32]),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
            ((b"MODS",), "alt", None),
        ]),
    b'SHOU': (
        [b"MDOB"],
        [
            ((b"SNAM",), "offs", [0, 4]),
        ]),
    b'SLGM': (
        [b"NAM0", b"ZNAM", b"YNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS",), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'SMBN': (
        [b"PNAM", b"SNAM"],
        [
        ]),
    b'SMEN': (
        [b"PNAM", b"SNAM"],
        [
        ]),
    b'SMQN': (
        [b"PNAM", b"SNAM", b"NNAM"],
        [
        ]),
    b'SNCT': (
        [b"PNAM"],
        [
        ]),
    b'SNDR': (
        [b"GNAM", b"SNAM", b"ONAM"],
        [
        ]),
    b'SOUN': (
        [b"SDSC"],
        [
        ]),
    b'SPEL': (
        [b"MDOB", b"ETYP", b"EFID"],
        [
            ((b"SPIT",), "offs", [32]),
            ((b"KWDA",), "array", None),
        ]),
    b'STAT': (
        [],
        [
            ((b"DNAM",), "offs", [4]),
            ((b"MODS",), "alt", None),
        ]),
    b'TACT': (
        [b"SNAM", b"VNAM"],
        [
            ((b"MODS",), "alt", None),
            ((b"KWDA",), "array", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'TREE': (
        [b"PFIG", b"SNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'WATR': (
        [b"XNAM", b"SNAM", b"INAM", b"TNAM"],
        [
        ]),
    b'WEAP': (
        [b"BAMT", b"BIDS", b"CNAM", b"EITM", b"ETYP", b"INAM", b"NAM7", b"NAM8", b"NAM9", b"SNAM", b"TNAM", b"UNAM", b"WNAM", b"XNAM", b"YNAM", b"ZNAM"],
        [
            ((b"KWDA",), "array", None),
            ((b"MODS", b"MO3S"), "alt", None),
            ((b"DSTD",), "offs", [8, 12]),
            ((b"DMDS",), "alt", None),
        ]),
    b'WRLD': (
        [b"LTMP", b"XEZN", b"XLCN", b"CNAM", b"NAM2", b"NAM3", b"WNAM", b"PNAM", b"ZNAM"],
        [
            ((b"MODS",), "alt", None),
        ]),
    b'WTHR': (
        [b"MNAM", b"NNAM", b"TNAM", b"SNAM", b"GNAM"],
        [
            ((b"IMSP", b"HNAM"), "offs", [0, 4, 8, 12]),
            ((b"MODS",), "alt", None),
        ]),
}


_counter = [0]


def marker():
    _counter[0] += 1
    return fid(1, 0x1000 + _counter[0])


def build(kind, offs):
    """-> (payload, [marker ids expected, in reporting order])"""
    if kind == "array":
        ids = [marker(), marker(), marker()]
        return b"".join(ids), ids
    if kind == "array12":                                   # 12-byte structs, id first
        ids = [marker(), marker()]
        return b"".join(i + b"\x00" * 8 for i in ids), ids
    if kind == "alt":
        a, b = marker(), marker()
        n1, n2 = b"abc", b"hello!"
        payload = struct.pack("<I", 2)
        payload += struct.pack("<I", len(n1)) + n1 + a + struct.pack("<i", 0)
        payload += struct.pack("<I", len(n2)) + n2 + b + struct.pack("<i", 1)
        return payload, [a, b]
    assert kind == "offs"
    payload = bytearray(max(offs) + 4)
    ids = []
    for o in offs:
        m = marker()
        payload[o:o + 4] = m
        ids.append(m)
    return bytes(payload), ids


def reported(rec):
    """Ids the handler reports; a handler that never returns fails the test instead of hanging the suite."""
    (i, form, offsets), = call_with_timeout(fp.save_all_form_data, [rec])
    return [bytes(form[o:o + 4]) for o in offsets]


def params(cases):
    return [pytest.param(c, id=c.decode()) for c in cases]


CASES = sorted(SPEC)
# placed_data does not check the size of its simple fields
PLACED = {b"PHZD", b"PGRE", b"PMIS", b"PARW", b"PBAR", b"PCON", b"PFLA", b"BEAM"}


@pytest.mark.parametrize("rtype", params(CASES))
def test_record_reports_exactly_its_form_id_fields(rtype):
    simple, special = SPEC[rtype]
    subs, expected = b"", [OWN]
    for name in simple:
        m = marker()
        subs += sub(name, m)
        expected.append(m)
    for names, kind, offs in special:
        for name in names:
            payload, ids = build(kind, offs)
            subs += sub(name, payload)
            expected += ids
    assert reported(record(rtype, OWN, subs)) == expected


@pytest.mark.parametrize("rtype", params([c for c in CASES if SPEC[c][0] and c not in PLACED]))
def test_simple_fields_smaller_than_a_form_id_are_ignored(rtype):
    simple, _ = SPEC[rtype]
    subs = b"".join(sub(name, b"") for name in simple)
    assert reported(record(rtype, OWN, subs)) == [OWN]


@pytest.mark.parametrize("rtype", params(CASES))
def test_unknown_subrecords_are_skipped(rtype):
    rec = record(rtype, OWN, sub(b"ZZZZ", marker() * 4))
    assert reported(rec) == [OWN]


@pytest.mark.parametrize("rtype", params(CASES))
def test_fields_after_an_extended_size_xxxx_field_are_still_read(rtype):
    simple, special = SPEC[rtype]
    if simple:
        name, m = simple[0], marker()
        field = b"XXXX" + struct.pack("<HI", 4, 4) + name + struct.pack("<H", 0) + m
        assert reported(record(rtype, OWN, field)) == [OWN, m]


@pytest.mark.parametrize("rtype", sorted(PLACED), ids=lambda c: c.decode())
def test_all_placed_record_types_share_the_placed_handler(rtype):
    m = marker()
    rec = record(rtype, OWN, sub(b"NAME", m))
    assert reported(rec) == [OWN, m]


DEFAULT_TYPES = [b"AACT", b"ASTP", b"CLAS", b"CLFM", b"CSTY", b"DEBR", b"EYES", b"GMST", b"GRAS", b"IMAD", b"IMGS",
                 b"KYWD", b"LCRT", b"LGTM", b"MATO", b"MOVT", b"REVB", b"SOPM", b"SPGD", b"TXST", b"VTYP", b"WOOP",
                 b"VOLI", b"LENS", b"SCPT", b"CLDC", b"HAIR", b"PWAT"]


@pytest.mark.parametrize("rtype", DEFAULT_TYPES, ids=lambda c: c.decode())
def test_default_record_types_only_report_their_own_id(rtype):
    rec = record(rtype, OWN, sub(b"NAME", marker()) + sub(b"DATA", marker()))
    assert reported(rec) == [OWN]
