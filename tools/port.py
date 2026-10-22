"""Converts the newer build's records into the pinned build's layout and enum numbering.

convert(new_type, new_bytes, old_type, fallback) walks the new record's members: a member the old layout has at the matching
place (by member alignment when the layouts differ) is copied, every enum value translated to the old numbering; members
the old layout lacks are dropped, ones only the old has keep the fallback's bytes. Unmapped enum values (content new to
the newer build) are reported in .unmapped as (enum hash, new value, old offset, size) so the mod can fill them in."""
import struct, difflib
from dlbuild import Build, OLD, NEW
from enumlens import maps

FMT = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}


class Porter:
    def __init__(self):
        self.o, self.n = Build(OLD), Build(NEW)
        self.emap = maps(open(OLD + '/dl_library.dl_typelib', 'rb').read(), open(NEW + '/dl_library.dl_typelib', 'rb').read())

    def sig(self, b, m):
        sub = b.layout(m['type_id']) if m['storage'] == 'STRUCT' else (m['type_id'] if m['storage'].startswith('ENUM') else None)
        return (m['size'], m['atom'], m['storage'], m['arraylen'], sub)

    def pairs(self, ot, nt):
        """(old member, new member) pairs: identical layouts pair by position, others by aligned signatures."""
        om, nm = self.o.tl.types[ot]['members'], self.n.tl.types[nt]['members']
        so, sn = [self.sig(self.o, m) for m in om], [self.sig(self.n, m) for m in nm]
        sm = difflib.SequenceMatcher(None, so, sn, autojunk=False)
        out = []
        for a, b, size in sm.get_matching_blocks():
            out += [(om[a + i], nm[b + i]) for i in range(size)]
        return out

    def convert(self, nt, nb, ot, fallback, unmapped=None, base_o=0):
        out = bytearray(fallback)
        unmapped = [] if unmapped is None else unmapped
        self._conv(nt, nb, 0, ot, out, 0, unmapped)
        return bytes(out), unmapped

    def _conv(self, nt, nb, no, ot, out, oo, unmapped):
        for om, nm in self.pairs(ot, nt):
            count = nm['arraylen'] if nm['atom'] == 'INLINE_ARRAY' else 1
            if nm['storage'] == 'STRUCT':
                es_n, es_o = self.n.tl.types[nm['type_id']]['size'], self.o.tl.types[om['type_id']]['size']
                for i in range(count):
                    self._conv(nm['type_id'], nb, no + nm['offset'] + es_n * i, om['type_id'], out, oo + om['offset'] + es_o * i, unmapped)
                continue
            es = nm['size'] // count if count else 0
            for i in range(count):
                src = no + nm['offset'] + es * i; dst = oo + om['offset'] + es * i
                raw = nb[src:src + es]
                if nm['storage'].startswith('ENUM') and nm['atom'] != 'BITFIELD':
                    v = struct.unpack('<' + FMT[es], raw)[0]
                    m = self.emap.get(nm['type_id'])
                    if m is not None and v in m:
                        raw = struct.pack('<' + FMT[es], m[v])
                    elif m is not None and v != 0:
                        unmapped.append((nm['type_id'], v, dst, es))
                        continue  # keeps the fallback's value; the mod fills it in if it can
                out[dst:dst + es] = raw
