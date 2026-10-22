"""Per enum (by type hash): each value's name-string offset in the typelib string table. Names are stripped from the build,
but the offsets survive, so consecutive differences give each name's length."""
import struct


def enum_name_offsets(data):
    (_, ver, tc, ec, mc, evc, eac, dvs, tss) = struct.unpack_from('<4s8I', data)
    at = 36
    at += 4 * tc
    ehash = struct.unpack_from('<%dI' % ec, data, at); at += 4 * ec
    at += 36 * tc
    edesc = [struct.unpack_from('<IIB3xIIIII', data, at + 32 * i) for i in range(ec)]; at += 32 * ec
    at += 72 * mc
    evals = [struct.unpack_from('<IIQ', data, at + 16 * i) for i in range(evc)]; at += 16 * evc
    ealias = [struct.unpack_from('<II', data, at + 8 * i) for i in range(eac)]; at += 8 * eac
    at += dvs
    strs = data[at:at + tss]
    out = {}
    for h, (noff, flags, stor, vcount, vstart, acount, astart, coff) in zip(ehash, edesc):
        vals = {}
        for i in range(vstart, vstart + vcount):
            main_alias, _, v = evals[i]
            vals[v] = ealias[main_alias][0]
        out[h] = vals
    return out, strs


def enum_lengths(data):
    """{enum hash: [name length per value, in value order]} (values are 0..n-1 for these enums)."""
    offs, _ = enum_name_offsets(data)
    allo = sorted({o for v in offs.values() for o in v.values()})
    nxt = {a: b for a, b in zip(allo, allo[1:])}
    return {h: [nxt.get(v[k], v[k] + 1) - v[k] - 1 for k in sorted(v)] for h, v in offs.items()}, offs


def maps(old_data, new_data, min_run=4):
    """{enum hash: {new value: old value}} for every enum in both builds, aligned on name lengths."""
    import difflib
    lo, oo = enum_lengths(old_data); ln, on = enum_lengths(new_data)
    out = {}
    for h in ln:
        if h not in lo: continue
        ko, kn = sorted(oo[h]), sorted(on[h])
        sm = difflib.SequenceMatcher(None, lo[h], ln[h], autojunk=False)
        m = {}
        for a, b, size in sm.get_matching_blocks():
            if size >= min_run or (size and len(lo[h]) == len(ln[h])):
                for i in range(size): m[kn[b + i]] = ko[a + i]
        out[h] = m
    return out
