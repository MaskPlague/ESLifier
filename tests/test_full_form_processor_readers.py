"""
full_form_processor.ctda_reader / script_reader / vmad_reader: the structured sub-record readers that the
record handlers call for CTDA conditions and VMAD (Papyrus script) data.
"""
import struct

from full_form_processor_sse import form_processor as fp
from plugin_builder import fid, record, sub

OWN = fid(1, 0x800)
Z4 = b"\x00" * 4
_n = [0]


def m():
    _n[0] += 1
    return fid(1, 0x3000 + _n[0])


def u16(n):
    return struct.pack("<H", n)


def u32(n):
    return struct.pack("<I", n)


def at(form, offsets):
    return [bytes(form[o:o + 4]) for o in offsets]


# ------------------------------------------------------------------------------------------ CTDA
def ctda(op=0, comparison=Z4, function=1, p1=Z4, p2=Z4, run_on=0, reference=Z4):
    payload = (bytes([op]) + b"\x00" * 3 + comparison + u16(function) + b"\x00\x00" + p1 + p2 + u32(run_on) + reference
               + b"\x00" * 8)
    return record(b"IDLE", OWN, sub(b"CTDA", payload))


def read_ctda(rec):
    return at(rec, fp.ctda_reader(rec, 24))


class TestCtda:
    def test_both_parameters_of_an_ordinary_function(self):
        a, b = m(), m()
        assert read_ctda(ctda(function=1, p1=a, p2=b)) == [a, b]

    def test_zero_parameters_are_skipped(self):
        a = m()
        assert read_ctda(ctda(function=1, p1=Z4, p2=a)) == [a]
        assert read_ctda(ctda(function=1)) == []

    def test_functions_whose_first_parameter_is_not_a_form_id(self):
        a, b = m(), m()
        assert read_ctda(ctda(function=6, p1=a, p2=b)) == [b]        # GetActorValue-like: p1 is an actor value
        assert read_ctda(ctda(function=706, p1=a, p2=b)) == [b]

    def test_functions_whose_second_parameter_is_not_a_form_id(self):
        a, b = m(), m()
        assert read_ctda(ctda(function=53, p1=a, p2=b)) == [a]
        assert read_ctda(ctda(function=98, p1=a, p2=b)) == []        # neither parameter is an id

    def test_global_flag_makes_the_comparison_value_a_form_id(self):
        g = m()
        assert read_ctda(ctda(op=0x04, comparison=g)) == [g]
        assert read_ctda(ctda(op=0x00, comparison=g)) == []

    def test_only_the_low_five_flag_bits_are_considered(self):
        g = m()
        assert read_ctda(ctda(op=0x84, comparison=g)) == [g]         # high bits are the comparison operator
        assert read_ctda(ctda(op=0xE0, comparison=g)) == []

    def test_run_on_reference_adds_the_reference_id(self):
        r = m()
        assert read_ctda(ctda(run_on=2, reference=r)) == [r]
        assert read_ctda(ctda(run_on=1, reference=r)) == []

    def test_everything_together_in_field_order(self):
        g, a, b, r = m(), m(), m(), m()
        assert read_ctda(ctda(op=0x04, comparison=g, function=1, p1=a, p2=b, run_on=2, reference=r)) == [g, a, b, r]


# ------------------------------------------------------------------------------------------ script_reader
def obj(formid, v1=True):
    return formid + b"\x00" * 4 if v1 else b"\x00" * 4 + formid


def prop(name, ptype, value):
    return u16(len(name)) + name + bytes([ptype, 1]) + value


def script(name, props=(), ):
    return u16(len(name)) + name + b"\x00" + u16(len(props)) + b"".join(props)


class TestScriptReader:
    def run(self, data, fmt):
        form = b"\x00" * 10 + data
        offsets, end = fp.script_reader(form, 10, fmt)
        return at(form, offsets), end - 10

    def test_empty_script(self):
        data = script(b"MyScript")
        assert self.run(data, 1) == ([], len(data))

    def test_object_property_in_both_object_formats(self):
        a = m()
        assert self.run(script(b"S", [prop(b"p", 1, obj(a, True))]), 1)[0] == [a]
        assert self.run(script(b"S", [prop(b"p", 1, obj(a, False))]), 2)[0] == [a]

    def test_object_arrays_in_both_object_formats(self):
        a, b = m(), m()
        value = u32(2) + obj(a, True) + obj(b, True)
        assert self.run(script(b"S", [prop(b"p", 11, value)]), 1)[0] == [a, b]
        value = u32(2) + obj(a, False) + obj(b, False)
        assert self.run(script(b"S", [prop(b"p", 11, value)]), 2)[0] == [a, b]

    def test_every_other_property_type_is_skipped_correctly(self):
        a, b = m(), m()
        props = [
            prop(b"s", 2, u16(5) + b"hello"),
            prop(b"i", 3, u32(7)),
            prop(b"f", 4, struct.pack("<f", 1.5)),
            prop(b"b", 5, b"\x01"),
            prop(b"sa", 12, u32(2) + u16(1) + b"x" + u16(2) + b"yz"),
            prop(b"ia", 13, u32(3) + b"\x01\x00\x00\x00" * 3),
            prop(b"fa", 14, u32(2) + b"\x00\x00\x80\x3f" * 2),
            prop(b"ba", 15, u32(4) + b"\x01\x00\x01\x00"),
            prop(b"o1", 1, obj(a)),                                   # an object after all of the above proves the offsets stayed in sync
            prop(b"o2", 11, u32(1) + obj(b)),
        ]
        data = script(b"Sync", props)
        found, end = self.run(data, 1)
        assert found == [a, b]
        assert end == len(data)

    def test_returns_the_offset_just_after_the_script(self):
        a = m()
        first = script(b"A", [prop(b"p", 1, obj(a))])
        form = b"\x00" * 6 + first + b"TAIL"
        offsets, end = fp.script_reader(form, 6, 1)
        assert form[end:] == b"TAIL"


# ------------------------------------------------------------------------------------------ vmad_reader
def vmad(scripts=(), obj_format=2, extra=b""):
    payload = u16(5) + u16(obj_format) + u16(len(scripts)) + b"".join(scripts) + extra
    return sub(b"VMAD", payload)


def read_vmad(rtype, field):
    rec = record(rtype, OWN, field)
    return at(rec, fp.vmad_reader(rec, 24))


class TestVmadReader:
    def test_no_scripts(self):
        assert read_vmad(b"REFR", vmad()) == []

    def test_scripts_are_read_one_after_another(self):
        a, b, c = m(), m(), m()
        scripts = [script(b"One", [prop(b"p", 1, obj(a, False))]),
                   script(b"Two", [prop(b"q", 11, u32(2) + obj(b, False) + obj(c, False))])]
        assert read_vmad(b"REFR", vmad(scripts, obj_format=2)) == [a, b, c]

    def test_object_format_1_is_honoured(self):
        a = m()
        assert read_vmad(b"REFR", vmad([script(b"One", [prop(b"p", 1, obj(a, True))])], obj_format=1)) == [a]

    def test_fragments_of_non_quest_records_are_ignored(self):
        a = m()
        field = vmad([script(b"One", [prop(b"p", 1, obj(a, False))])], extra=b"\x02" + m() * 3)
        for rtype in (b"INFO", b"PACK", b"PERK", b"SCEN", b"ACTI"):
            assert read_vmad(rtype, field) == [a]

    def test_xxxx_sized_vmad_in_a_handler(self):
        a = m()
        field = vmad([script(b"One", [prop(b"p", 1, obj(a, False))])])
        rec = record(b"ACHR", OWN, field)
        (i, form, offsets), = fp.save_all_form_data([rec])
        assert at(form, offsets) == [OWN, a]


class TestVmadQuestData:
    @staticmethod
    def fragment(script_name=b"Frag", func=b"Fragment_0"):
        return b"\x00" * 9 + u16(len(script_name)) + script_name + u16(len(func)) + func

    def quest_extra(self, fragments, alias_blocks, file_name=b"QF_Quest"):
        data = b"\x02" + u16(len(fragments)) + u16(len(file_name)) + file_name + b"".join(fragments)
        data += u16(len(alias_blocks)) + b"".join(alias_blocks)
        return data

    def alias(self, formid, scripts=(), v2=True):
        head = (b"\x00" * 4 + formid) if v2 else (formid + b"\x00" * 4)
        return head + u16(2) + u16(2 if v2 else 1) + u16(len(scripts)) + b"".join(scripts)

    def test_quest_aliases_are_read_after_the_fragments(self):
        a1, a2 = m(), m()
        extra = self.quest_extra([self.fragment(), self.fragment(b"Other", b"Fragment_1")],
                                 [self.alias(a1), self.alias(a2)])
        assert read_vmad(b"QUST", vmad(extra=extra, obj_format=2)) == [a1, a2]

    def test_alias_scripts_are_read_too(self):
        alias_id, prop_id, arr_id = m(), m(), m()
        scr = script(b"AliasScript", [prop(b"p", 1, obj(prop_id, False)),
                                      prop(b"q", 11, u32(1) + obj(arr_id, False))])
        extra = self.quest_extra([self.fragment()], [self.alias(alias_id, [scr])])
        assert read_vmad(b"QUST", vmad(extra=extra, obj_format=2)) == [alias_id, prop_id, arr_id]

    def test_quest_script_and_alias_ids_come_in_file_order(self):
        s_id, alias_id = m(), m()
        extra = self.quest_extra([], [self.alias(alias_id)])
        out = read_vmad(b"QUST", vmad([script(b"Q", [prop(b"p", 1, obj(s_id, False))])], extra=extra))
        assert out == [s_id, alias_id]

    def test_object_format_1_aliases(self):
        a = m()
        extra = self.quest_extra([], [self.alias(a, v2=False)])
        assert read_vmad(b"QUST", vmad(extra=extra, obj_format=1)) == [a]

    def test_quest_without_trailing_data_is_fine(self):
        assert read_vmad(b"QUST", vmad()) == []
