"""
Helpers for building tiny, valid-enough Skyrim SE plugin files and ESLifier
form-ID maps for tests. Nothing here depends on ESLifier itself.

Record layout (all little endian):
    header (24 bytes): type[4] datasize[4] flags[4] formid[4] vcinfo[4] version[2] unknown[2]
    data:              sub-records, each  sig[4] size[2] payload
GRUP layout:
    header (24 bytes): 'GRUP' groupsize[4] label[4] type[4] stamp[2] vc[2] unknown[4]
    (groupsize includes the 24-byte header)
"""
import struct
import zlib

COMPRESSED = 0x00040000
ESM_FLAG = 0x00000001
ESL_FLAG = 0x00000200

HEADER_VERSION_171 = struct.pack("<f", 1.71)
HEADER_VERSION_170 = struct.pack("<f", 1.70)


def fid(master_index: int, object_id: int) -> bytes:
    """Form ID as stored in a plugin (little endian, master index in top byte)."""
    return struct.pack("<I", (master_index << 24) | object_id)


def sub(sig: bytes, payload: bytes) -> bytes:
    assert len(sig) == 4
    return sig + struct.pack("<H", len(payload)) + payload


def record(sig: bytes, formid: bytes, subrecords: bytes = b"", flags: int = 0,
           compress: bool = False) -> bytes:
    assert len(sig) == 4 and len(formid) == 4
    data = subrecords
    if compress:
        flags |= COMPRESSED
        data = struct.pack("<I", len(subrecords)) + zlib.compress(subrecords)
    return (sig + struct.pack("<I", len(data)) + struct.pack("<I", flags)
            + formid + b"\x00" * 4 + struct.pack("<HH", 44, 0) + data)


def grup(label: bytes, contents: bytes, group_type: int = 0) -> bytes:
    assert len(label) == 4
    size = 24 + len(contents)
    return (b"GRUP" + struct.pack("<I", size) + label + struct.pack("<I", group_type)
            + b"\x00" * 8 + contents)


def tes4(masters=(), esm: bool = False, esl: bool = False,
         version: bytes = HEADER_VERSION_170, author: bytes = b"tester\x00") -> bytes:
    flags = (ESM_FLAG if esm else 0) | (ESL_FLAG if esl else 0)
    subs = sub(b"HEDR", version + struct.pack("<II", 0, 0x800))
    subs += sub(b"CNAM", author)
    for m in masters:
        name = m.encode("utf-8") + b"\x00"
        subs += sub(b"MAST", name) + sub(b"DATA", b"\x00" * 8)
    return record(b"TES4", b"\x00\x00\x00\x00", subs, flags=flags)


def plugin(masters=(), body: bytes = b"", esm: bool = False, esl: bool = False,
           version: bytes = HEADER_VERSION_170) -> bytes:
    return tes4(masters, esm=esm, esl=esl, version=version) + body


def simple_records(master_count: int, object_ids, sig: bytes = b"KYWD") -> bytes:
    """A grup of trivial records, one per object id, owned by this plugin."""
    recs = b"".join(record(sig, fid(master_count, oid)) for oid in object_ids)
    return grup(sig, recs)


def cell_record(formid: bytes, interior: bool, compress: bool = False) -> bytes:
    data_flags = b"\x01\x00" if interior else b"\x00\x00"
    subs = sub(b"EDID", b"Cell\x00") + sub(b"DATA", data_flags)
    return record(b"CELL", formid, subs, compress=compress)


def write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def map_entry(to_hex_no_0: str, update_name: bool = False, to_bytes: bytes = None) -> dict:
    """One value of ESLifier's int-keyed form-ID map (see CFIDs.get_form_id_map)."""
    to_hex = to_hex_no_0.upper().rjust(6, "0")
    return {
        "hex": to_hex,
        "int": int(to_hex, 16),
        "hex_no_0": to_hex_no_0.upper(),
        "bytes": to_bytes if to_bytes is not None else bytes.fromhex(to_hex)[::-1] + b"\x00",
        "update_name": update_name,
    }


def walk(data: bytes, start: int = 0, end: int = None):
    """
    Parse a plugin into a nested structure and verify every GRUP size is
    consistent with its contents. Returns a list of
        ("GRUP", label, group_type, [children...])  or  ("REC", sig, formid_bytes)
    Raises AssertionError if sizes don't line up.
    """
    end = len(data) if end is None else end
    out = []
    offset = start
    while offset < end:
        sig = data[offset:offset + 4]
        size = struct.unpack("<I", data[offset + 4:offset + 8])[0]
        if sig == b"GRUP":
            group_end = offset + size
            assert group_end <= end, f"GRUP at {offset} overruns its parent ({group_end} > {end})"
            children = walk(data, offset + 24, group_end)
            out.append(("GRUP", data[offset + 8:offset + 12],
                        struct.unpack("<I", data[offset + 12:offset + 16])[0], children))
            offset = group_end
        else:
            rec_end = offset + 24 + size
            assert rec_end <= end, f"record {sig} at {offset} overruns its parent"
            out.append(("REC", sig, data[offset + 12:offset + 16]))
            offset = rec_end
    assert offset == end, "sizes do not add up exactly"
    return out


def flatten(tree):
    """All ('REC', sig, formid) entries in a walk() result, depth first."""
    for node in tree:
        if node[0] == "REC":
            yield node
        else:
            yield from flatten(node[3])


def iter_records(data: bytes):
    """Yield (offset, sig, raw_bytes) for every non-GRUP record, in file order."""
    offset = 0
    while offset < len(data):
        sig = data[offset:offset + 4]
        size = struct.unpack("<I", data[offset + 4:offset + 8])[0]
        if sig == b"GRUP":
            offset += 24
        else:
            end = offset + 24 + size
            yield offset, sig, data[offset:end]
            offset = end


def get_record(data: bytes, sig: bytes) -> bytes:
    """First record of the given type (never matches a GRUP label)."""
    for _, s, raw in iter_records(data):
        if s == sig:
            return raw
    raise KeyError(sig)


def call_with_timeout(fn, *args, seconds=2.0):
    """Run ``fn`` in a daemon thread so a handler stuck in an infinite loop fails the test instead of hanging
    the suite. (signal.SIGALRM would be simpler but does not exist on Windows.)"""
    import threading
    box = {}

    def target():
        try:
            box["result"] = fn(*args)
        except BaseException as e:      # re-raised in the calling thread
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError("handler did not return (infinite loop?)")
    if "error" in box:
        raise box["error"]
    return box["result"]
