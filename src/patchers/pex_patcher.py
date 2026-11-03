"""
Two-part Papyrus (.pex) FormID patcher.

Part 1 (parse): walk every function body once and only *record* facts:
  - sinks: values that reach Game.GetFormFromFile(<value>, <basename>)
  - calls: every other call, plus where each argument came from
Part 2 (resolve): propagate "this parameter reaches GetFormFromFile" through
the call graph until nothing changes, then patch every integer literal that
feeds a tainted parameter.

Nothing is patched until the whole file has been parsed, so a function can
call another function that is defined later in the file.

Value sources are tuples:
  ('int', offset)   integer literal whose type byte is at `offset`
  ('param', index)  parameter number `index` of the enclosing function
  ('array', arr)    local array, arr is an _Arr (compared and hashed by identity)

A variable can hold SEVERAL sources at once (a frozenset), because after
`If c  id = 0x800  Else  id = 0x801  EndIf` it holds either literal. Inside a
function the variable states are tracked in instruction order, and merged
(per-variable union) wherever a jump lands. Plain assignment still replaces the
old value, so reused `::temp` variables never leak literals into each other.
Loops (backward jumps) are handled by re-running the function until the jump
states stop changing.
"""

from dataclasses import dataclass, field

class PexParseError(Exception):
    """The file could not be parsed reliably. Nothing is written."""


@dataclass
class FuncRecord:
    idx: int
    obj: bytes
    name: bytes
    params: list                                   # [(name, type)]
    sinks: list = field(default_factory=list)      # every source that can reach GetFormFromFile
    calls: list = field(default_factory=list)      # (callee, object hint, [frozenset of sources per arg])


# opcode -> (operand count, index of the destination operand or None)
# 0x0D, 0x17-0x19, 0x1E, 0x20 and 0x21 are handled explicitly in the parser.
_SIMPLE_OPS = {
    0x00: (0, None),
    **{op: (3, 0) for op in (*range(0x01, 0x0A), *range(0x0F, 0x14), 0x1B, 0x24, 0x26)},
    **{op: (2, 0) for op in (0x0A, 0x0B, 0x0C, 0x0E, 0x1F)},
    0x14: (1, None), 0x1A: (1, None),
    0x15: (2, None), 0x16: (2, None),
    0x1C: (3, 2),    0x1D: (3, None),          # propget (dest last) / propset
    0x22: (4, 1),    0x23: (4, 1),             # array find / rfind
    0x25: (1, 0),                              # FO4: struct create
    **{op: (3, None) for op in (0x27, 0x2A, 0x2B, 0x2D)},
    0x28: (5, 1),    0x29: (5, 1),             # FO4: array find struct / rfind struct
    0x2C: (1, None), 0x2E: (1, None),          # FO4: remove last / clear
}

# only parameters of these types can carry a FormID
_FORM_PARAM_TYPES = (b'int', b'int[]')


class _Arr:
    """A local array. `elems`: literal index -> frozenset of sources, `dyn`: sources stored at a computed index."""
    __slots__ = ("elems", "dyn")

    def __init__(self):
        self.elems = {}
        self.dyn = []


_NONE = frozenset()
_JUMPS = (0x14, 0x15, 0x16)          # jmp, jmpt, jmpf: the offset is always the last operand
_RETURN = 0x1A
_MAX_PASSES = 32


def _array_sources(arr: _Arr):
    return [s for srcs in arr.elems.values() for s in srcs] + arr.dyn


def _analyze_function(rec:FuncRecord, insns, param_init:dict, basename_bytes):
    """
    Fill rec.sinks / rec.calls from the decoded instructions of one function.

    insns: [(opcode, operands)] for most opcodes, [(opcode, (func, hint, dst, args))] for calls.
           An operand is (offset, type, value) as returned by read_var.
    param_init: {param name: frozenset({('param', i)})} for the parameters that can carry a FormID.
    """
    def lookup(state, name):
        return state[name] if name in state else param_init.get(name, _NONE)

    def merge(a, b):
        return {k: lookup(a, k) | lookup(b, k) for k in a.keys() | b.keys()}

    def resolve(state, var):
        off, vtype, val = var
        if vtype == 3:
            return frozenset({('int', off)})
        if vtype == 1:
            return lookup(state, val)
        return _NONE

    def set_dst(state, var, srcs):
        if var[1] == 1:
            state[var[2]] = srcs            # even an empty set: an overwritten parameter is no longer the parameter

    arrays:dict[int, _Arr] = {}            # instruction index -> its array, so identities stay stable across passes
    jump_states:dict[int,dict] = {}        # instruction index -> merged variable state of everything jumping there
    count = len(insns)

    for _pass in range(_MAX_PASSES):
        rec.sinks.clear()
        rec.calls.clear()
        for a in arrays.values():
            a.elems.clear()
            a.dyn.clear()
        before = dict(jump_states)
        state = {}
        reachable = True                    # does `state` flow into the current instruction?

        for n, (op, ops) in enumerate(insns):
            if n in jump_states:
                state = merge(state, jump_states[n]) if reachable else dict(jump_states[n])
                reachable = True
            elif not reachable:
                state = {}                  # unreachable code: nothing is known

            if op in (0x17, 0x18, 0x19):                # calls
                func, hint, dst, args = ops
                if (func == b'getformfromfile' and len(args) >= 2
                        and args[1][1] == 2 and args[1][2] == basename_bytes):
                    rec.sinks.extend(resolve(state, args[0]))
                else:
                    rec.calls.append((func, hint, [resolve(state, a) for a in args]))
                set_dst(state, dst, _NONE)              # after args are resolved
            elif op == 0x0D:                            # assign
                set_dst(state, ops[0], resolve(state, ops[1]))
            elif op == 0x1E:                            # array create
                set_dst(state, ops[0], frozenset({('array', arrays.setdefault(n, _Arr()))}))
            elif op == 0x20:                            # array get element
                srcs = resolve(state, ops[1])
                # an element of an array counts as "the array" (or the param)
                set_dst(state, ops[0], frozenset(s for s in srcs if s[0] in ('array', 'param')))
            elif op == 0x21:                            # array set element
                arr, idx, val = ops
                targets: list[_Arr] = [s[1] for s in resolve(state, arr) if s[0] == 'array']
                vs = frozenset(s for s in resolve(state, val) if s[0] in ('int', 'param'))
                for a in targets:
                    if idx[1] == 3:
                        if len(targets) == 1:           # certain which array: replace the element
                            if vs:
                                a.elems[idx[2]] = vs
                            else:
                                a.elems.pop(idx[2], None)
                        elif vs:                        # one of several arrays: it may or may not be this one
                            a.elems[idx[2]] = a.elems.get(idx[2], _NONE) | vs
                    else:
                        a.dyn.extend(vs)
            else:                                       # everything else only overwrites its destination
                dest = _SIMPLE_OPS[op][1]
                if dest is not None:
                    set_dst(state, ops[dest], _NONE)

            if op in _JUMPS:
                off = ops[-1]
                if off[1] != 3:
                    raise PexParseError(f"jump without an integer offset at offset {off[0]}")
                delta = off[2] - (1 << 32) if off[2] >= (1 << 31) else off[2]
                target = n + delta                      # relative to the jump instruction itself
                if not 0 <= target <= count:
                    raise PexParseError(f"jump target {target} out of range at offset {off[0]}")
                jump_states[target] = merge(jump_states[target], state) if target in jump_states else dict(state)
            if op == 0x14 or op == _RETURN:
                reachable = False

        if jump_states == before:
            break


def _collect_offsets(records:list[FuncRecord]):
    """Phase 2. Returns (offsets of int literals to patch, tainted params)."""
    by_name = {}
    for r in records:
        by_name.setdefault(r.name, []).append(r)

    tainted = set()     # (record idx, param idx) that eventually reach GetFormFromFile
    offsets = set()     # a set, so no literal is ever remapped twice

    def candidates(name, hint):
        found:list[FuncRecord] = by_name.get(name, [])
        if hint is not None:
            found = [c for c in found if c.obj == hint]
        return found

    def apply(rec:FuncRecord, src):
        """Mark `src` as holding a FormID. True if that changed anything."""
        kind = src[0]
        if kind == 'int':
            if src[1] in offsets:
                return False
            offsets.add(src[1])
            return True
        if kind == 'param':
            key = (rec.idx, src[1])
            if key in tainted:
                return False
            tainted.add(key)
            return True
        if kind == 'array':
            changed = False
            for s in _array_sources(src[1]):
                changed |= apply(rec, s)
            return changed
        return False

    for rec in records:
        for src in rec.sinks:
            apply(rec, src)

    changed = True
    while changed:
        changed = False
        for rec in records:
            for callee, hint, srcs in rec.calls:
                for c in candidates(callee, hint):
                    for i, src in enumerate(srcs):
                        if src and (c.idx, i) in tainted:
                            for s in src:
                                if apply(rec, s):
                                    changed = True
    return offsets, tainted


def pex_patcher_for_debug(basename: str, new_file: str, form_id_map: dict,
                          endian: str = 'big', debug: bool = True, log=None,
                          print=print, ineligible=None) -> int:
    """
    Remap FormIDs passed to Game.GetFormFromFile(id, basename) in a compiled script.

    debug=True parses and prints but never writes the file (same as the old
    DEBUG = True). Returns the number of integer literals patched.
    `log` defaults to a module-level write_to_file() if one exists, else print.
    """
    log = log or globals().get('write_to_file') or print
    ineligible = ineligible or globals().get('write_ineligible') or print
    records = []
    strings = []
    data = bytearray()

    def dbg(msg):
        if debug:
            print(msg)

    def dlog(msg):
        if debug:
            log(msg)

    def nm(b):
        return b.decode('utf-8', 'replace') if isinstance(b, (bytes, bytearray)) else str(b)

    def u16(o):
        return int.from_bytes(data[o:o + 2], endian)

    def u32(o):
        return int.from_bytes(data[o:o + 4], endian)

    def read_var(offset):
        """Returns (new offset, (start offset, type, value))."""
        start = offset
        vtype = data[offset]
        offset += 1
        if vtype == 0:                                  # null
            return offset, (start, 0, None)
        if vtype in (1, 2):                             # identifier / string
            return offset + 2, (start, vtype, strings[u16(offset)])
        if vtype == 3:                                  # integer
            return offset + 4, (start, 3, u32(offset))
        if vtype == 4:                                  # float
            return offset + 4, (start, 4, bytes(data[offset:offset + 4]))
        if vtype == 5:                                  # bool
            return offset + 1, (start, 5, bool(data[offset]))
        raise PexParseError(f"unknown variable type {vtype} at offset {start}")

    def patch_int(a):
        if data[a] != 3:
            dbg(f"skipping offset {a}: not an integer literal")
            return False
        lo, hi = (a + 2, a + 5) if endian == 'big' else (a + 1, a + 4)
        before = data[a:a + 6].hex()
        old_id = int.from_bytes(data[lo:hi], endian)
        entry = form_id_map.get(old_id)
        if not entry:
            dlog(f"no patching: {before}")
            return False
        if entry.get("update_name"):
            # the record moved to ESLifier_Cell_Master.esm, so basename can no longer reference it
            ineligible(f'{basename} -> ESLifier_Cell_Master.esm | 0x{old_id:X} -> '
                        f'0x{entry["hex_no_0"]} | {new_file}')
        data[lo:hi] = entry["bytes"][::-1][1:] if endian == 'big' else entry["bytes"][:-1]
        dlog(f"patching: {before}")
        dlog(f"new: {data[a:a + 6].hex()}")
        return True

    def function_processor(offset, objName, parentName, funcName):
        offset += 2 + 2 + 4 + 1                         # return type, doc, user flags, flags
        numParams = u16(offset)
        offset += 2
        params = []
        for _i in range(numParams):
            params.append((strings[u16(offset)], strings[u16(offset + 2)]))
            offset += 4
        numLocals = u16(offset)
        offset += 2 + 4 * numLocals                     # (name, type) per local
        numInstructions = u16(offset)
        offset += 2

        rec = FuncRecord(len(records), objName, funcName, params)
        records.append(rec)
        param_index = {n: i for i, (n, t) in enumerate(params) if t in _FORM_PARAM_TYPES}
        dbg(f"\nfunction {nm(funcName)}({', '.join(nm(n) + ': ' + nm(t) for n, t in params)})")

        insns = []          # decoded first: a jump can point at an instruction that comes later

        for _i in range(numInstructions):
            op = data[offset]
            offset += 1
            if op in _SIMPLE_OPS:
                operands = []
                for _j in range(_SIMPLE_OPS[op][0]):
                    offset, v = read_var(offset)
                    operands.append(v)
                insns.append((op, operands))
            elif op == 0x0D:                            # assign
                offset, dst = read_var(offset)
                offset, src = read_var(offset)
                insns.append((op, [dst, src]))
            elif op == 0x1E:                            # array create
                offset, dst = read_var(offset)
                offset, _size = read_var(offset)
                insns.append((op, [dst]))
            elif op in (0x20, 0x21):                    # array get element / set element
                operands = []
                for _j in range(3):
                    offset, v = read_var(offset)
                    operands.append(v)
                insns.append((op, operands))
            elif op in (0x17, 0x18, 0x19):              # callmethod / callparent / callstatic
                offset, v1 = read_var(offset)
                v2 = None
                if op != 0x18:
                    offset, v2 = read_var(offset)
                offset, dst = read_var(offset)
                offset, nv = read_var(offset)
                if nv[1] != 3:
                    raise PexParseError(f"bad argument count at offset {nv[0]}")
                args = []
                for _j in range(nv[2]):
                    offset, a = read_var(offset)
                    args.append(a)
                if op == 0x17:                          # name, self, dest, n, args
                    func, hint = v1[2], (objName if v2[2] == b'self' else None)
                elif op == 0x19:                        # object, name, dest, n, args
                    func, hint = v2[2], v1[2]
                else:                                   # name, dest, n, args
                    func, hint = v1[2], parentName
                insns.append((op, (func, hint, dst, args)))
            else:
                raise PexParseError(f"unknown opcode {op:#04x} at offset {offset - 1}")

        param_init = {n: frozenset({('param', i)}) for n, i in param_index.items()}
        _analyze_function(rec, insns, param_init, basename_bytes)
        for func, _hint, srcs in rec.calls:
            dbg(f"  {nm(funcName)} calls {nm(func)} ({len(srcs)} args)")
        for src in rec.sinks:
            dbg(f"  GetFormFromFile sink: {src[0]}")
        return offset

    def state_processor(offset, objName, parentName):
        stateName = strings[u16(offset)]
        numFunctions = u16(offset + 2)
        offset += 4
        dbg(f"state {nm(stateName)}: {numFunctions} functions")
        for _i in range(numFunctions):
            functionName = strings[u16(offset)]
            offset += 2
            offset = function_processor(offset, objName, parentName, functionName)
        return offset

    # string literals are stored lowercased in `strings`, so lowercase the basename too
    basename_bytes = basename.lower().encode('utf-8')
    with open(new_file, 'rb') as f:
        data = bytearray(f.read())

    try:
        src_name_length = u16(16)
        offset = 18 + src_name_length
        offset += 2 + u16(offset)                       # user name
        offset += 2 + u16(offset)                       # machine name
        string_count = u16(offset)
        offset += 2
        for _i in range(string_count):
            n = u16(offset)
            strings.append(bytes(data[offset + 2:offset + 2 + n]).lower())
            offset += 2 + n
        dbg(f"{len(strings)} strings")

        debug_info_exists = data[offset]
        offset += 1
        if debug_info_exists == 1:
            offset += 8                                 # modification time
            func_count = u16(offset)
            offset += 2
            for _i in range(func_count):
                offset += 7                             # object, state, function, type
                offset += 2 + 2 * u16(offset)           # instruction count + line numbers
            if endian == 'little':                      # FO4: property groups, struct orders
                groupCount = u16(offset)
                offset += 2
                for _i in range(groupCount):
                    offset += 2 + 2 + 2 + 4
                    offset += 2 + 2 * u16(offset)
                orderCount = u16(offset)
                offset += 2
                for _i in range(orderCount):
                    offset += 2 + 2
                    offset += 2 + 2 * u16(offset)

        userFlagCount = u16(offset)
        offset += 2 + 3 * userFlagCount
        objectCount = u16(offset)
        offset += 2
        dbg(f"{objectCount = }")

        for _i in range(objectCount):
            objName = strings[u16(offset)]
            offset += 2
            obj_end = offset + u32(offset)              # size includes its own 4 bytes
            offset += 4
            parentName = strings[u16(offset)]
            offset += 2                                 # parent class
            offset += 2                                 # doc string
            if endian == 'little':
                offset += 1                             # const flag
            offset += 4                                 # user flags
            offset += 2                                 # auto state name
            dbg(f"\nobject {nm(objName)} extends {nm(parentName)}")

            if endian == 'little':                      # FO4 structs
                structCount = u16(offset)
                offset += 2
                for _j in range(structCount):
                    offset += 2                         # struct name
                    memberCount = u16(offset)
                    offset += 2
                    for _k in range(memberCount):
                        offset += 2 + 2 + 4             # name, type, user flags
                        offset, _v = read_var(offset)
                        offset += 1 + 2                 # const flag, doc string

            numVariables = u16(offset)
            offset += 2
            for _j in range(numVariables):
                offset += 8                             # name, type, user flags
                offset, _v = read_var(offset)

            numProperties = u16(offset)
            offset += 2
            for _j in range(numProperties):
                propName = strings[u16(offset)]
                offset += 10                            # name, type, doc, user flags
                flags = data[offset]
                offset += 1
                if (flags & 4) != 0:                    # auto var name
                    offset += 2
                if (flags & 5) == 1:                    # readable, no auto var
                    offset = function_processor(offset, objName, parentName, b'::get::' + propName)
                if (flags & 6) == 2:                    # writable, no auto var
                    offset = function_processor(offset, objName, parentName, b'::set::' + propName)

            numStates = u16(offset)
            offset += 2
            for _j in range(numStates):
                offset = state_processor(offset, objName, parentName)

            if offset != obj_end:
                dbg(f"WARNING: object parse ended at {offset}, expected {obj_end}")
    except (IndexError, ValueError) as e:
        raise PexParseError(f"{new_file}: ran off the end of the file ({e})") from e

    # patch offsets
    offsets, tainted = _collect_offsets(records)
    if debug:
        for ri, pi in sorted(tainted):
            print(f"param reaches GetFormFromFile: {nm(records[ri].name)}.{nm(records[ri].params[pi][0])}")
        print(f"literal offsets to patch: {sorted(offsets)}")
    patched = sum(1 for o in sorted(offsets) if patch_int(o))

    if not debug and patched:
        with open(new_file, 'wb') as f:
            f.write(data)
    if debug:
        print(f"done processing {new_file}")
    return patched


def pex_patcher(basename: str, new_file: str, form_id_map: dict, endian: str = 'big', ineligible=None) -> int:
    """Same as pex_patcher_for_debug but writes the result."""
    return pex_patcher_for_debug(basename, new_file, form_id_map, endian, debug=False, ineligible=ineligible)
