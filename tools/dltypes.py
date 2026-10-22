"""Stingray data-library type library and instance decoding, after FileDiver's datalibrary/datalib.go (ParseTypeLib)."""
import struct

ATOMS = ['POD', 'ARRAY', 'INLINE_ARRAY', 'BITFIELD']
STORAGE = ['INT8', 'INT16', 'INT32', 'INT64', 'UINT8', 'UINT16', 'UINT32', 'UINT64', 'FP32', 'FP64', 'ENUM_INT8', 'ENUM_INT16',
           'ENUM_INT32', 'ENUM_INT64', 'ENUM_UINT8', 'ENUM_UINT16', 'ENUM_UINT32', 'ENUM_UINT64', 'STR', 'PTR', 'STRUCT']
FMT = {'INT8': 'b', 'INT16': 'h', 'INT32': 'i', 'INT64': 'q', 'UINT8': 'B', 'UINT16': 'H', 'UINT32': 'I', 'UINT64': 'Q', 'FP32': 'f',
       'FP64': 'd', 'ENUM_INT8': 'b', 'ENUM_INT16': 'h', 'ENUM_INT32': 'i', 'ENUM_INT64': 'q', 'ENUM_UINT8': 'B', 'ENUM_UINT16': 'H',
       'ENUM_UINT32': 'I', 'ENUM_UINT64': 'Q'}
NONE = 0xFFFFFFFF


def dlsum(s):
    r = 5381
    for c in s: r = (r * 33 + ord(c)) & 0xFFFFFFFF
    return (r - 5381) & 0xFFFFFFFF


class TypeLib:
    def __init__(self, data, type_names=()):
        names = {dlsum(n): n for n in type_names}
        (_, ver, tc, ec, mc, evc, eac, dvs, tss) = struct.unpack_from('<4s8I', data)
        at = 36
        thash = struct.unpack_from('<%dI' % tc, data, at); at += 4 * tc
        ehash = struct.unpack_from('<%dI' % ec, data, at); at += 4 * ec
        tdesc = [struct.unpack_from('<II2I2IIII', data, at + 36 * i) for i in range(tc)]; at += 36 * tc
        edesc = [struct.unpack_from('<IIB3xIIIII', data, at + 32 * i) for i in range(ec)]; at += 32 * ec
        mdesc = [struct.unpack_from('<IIIBBHI2I2I2IIII16x', data, at + 72 * i) for i in range(mc)]; at += 72 * mc
        evals = [struct.unpack_from('<IIQ', data, at + 16 * i) for i in range(evc)]; at += 16 * evc
        ealias = [struct.unpack_from('<II', data, at + 8 * i) for i in range(eac)]; at += 8 * eac
        self.defaults = data[at:at + dvs]; at += dvs
        strs = data[at:at + tss]

        def text(off):
            if off == NONE or off >= len(strs): return None
            e = strs.find(b'\0', off)
            return strs[off:e].decode('utf-8', 'replace') if e >= 0 else None

        self.types, self.enums = {}, {}
        for h, (noff, flags, s32, s64, a32, a64, mcount, mstart, coff) in zip(thash, tdesc):
            members = []
            for i in range(mstart, mstart + mcount):
                (mn, mcmt, _, atom, stor, bf, tid, z32, z64, al32, al64, o32, o64, dvo, dvsz, mfl) = mdesc[i]
                members.append(dict(name=text(mn) or ('m%x' % mn), comment=text(mcmt), atom=ATOMS[atom], storage=STORAGE[stor],
                                    arraylen=bf, bits=bf & 0xFF, bitoff=bf >> 8, type_id=tid, size=z64, offset=o64))
            self.types[h] = dict(name=text(noff) or names.get(h, '%08x' % h), size=s64, align=a64, members=members, comment=text(coff))
        for h, (noff, flags, stor, vcount, vstart, acount, astart, coff) in zip(ehash, edesc):
            vals = {}
            for i in range(vstart, vstart + vcount):
                main_alias, _, v = evals[i]
                vals[v] = text(ealias[main_alias][0]) or str(v)
            self.enums[h] = dict(name=text(noff) or names.get(h, '%08x' % h), storage=STORAGE[stor], values=vals)
        self.by_name = {t['name']: h for h, t in self.types.items()}

    def decode(self, type_id, buf, off, base=None, depth=0):
        """Decode a struct instance at buf[off:]; pointers/arrays are relative to base (instance data start)."""
        t = self.types[type_id]
        out = {}
        for m in t['members']:
            out[m['name']] = self.member(m, buf, off + m['offset'], base, depth)
        return out

    def scalar(self, stor, tid, buf, off, base, depth):
        if stor in FMT:
            v = struct.unpack_from('<' + FMT[stor], buf, off)[0]
            if stor.startswith('ENUM') and tid in self.enums:
                return self.enums[tid]['values'].get(v, v)
            return round(v, 6) if stor in ('FP32', 'FP64') else v
        if stor == 'STRUCT':
            if tid not in self.types: return '<struct %08x>' % tid
            return self.decode(tid, buf, off, base, depth + 1)
        if stor == 'STR':
            p = struct.unpack_from('<q', buf, off)[0]
            if base is None or p < 0: return None
            e = buf.find(b'\0', base + p)
            return buf[base + p:e].decode('utf-8', 'replace')
        if stor == 'PTR':
            p = struct.unpack_from('<q', buf, off)[0]
            if base is None or p < 0 or depth > 6: return None
            return self.decode(tid, buf, base + p, base, depth + 1) if tid in self.types else p
        return None

    def elem_size(self, stor, tid):
        if stor in FMT: return struct.calcsize(FMT[stor])
        if stor == 'STRUCT': return self.types[tid]['size']
        return 8

    def member(self, m, buf, off, base, depth):
        stor, tid, atom = m['storage'], m['type_id'], m['atom']
        if atom == 'POD':
            return self.scalar(stor, tid, buf, off, base, depth)
        if atom == 'INLINE_ARRAY':
            n, es = m['arraylen'], self.elem_size(stor, tid)
            return [self.scalar(stor, tid, buf, off + es * i, base, depth) for i in range(n)]
        if atom == 'ARRAY':
            p, n = struct.unpack_from('<qQ', buf, off)
            if base is None or p < 0 or n > 4096: return []
            es = self.elem_size(stor, tid)
            return [self.scalar(stor, tid, buf, base + p + es * i, base, depth) for i in range(n)]
        if atom == 'BITFIELD':
            raw = struct.unpack_from('<' + FMT.get(stor, 'I'), buf, off)[0]
            return (raw >> m['bitoff']) & ((1 << m['bits']) - 1)
        return None


def find_instances(blob, type_hash):
    """Every LDLD instance of type_hash in blob: yields (data_offset, size). Header: LDLD, ver, type, size, is64, pad[7]."""
    sig = b'LDLD' + struct.pack('<I', 1) + struct.pack('<I', type_hash)
    i = blob.find(sig)
    while i >= 0:
        size = struct.unpack_from('<I', blob, i + 12)[0]
        yield i + 24, size
        i = blob.find(sig, i + 1)
