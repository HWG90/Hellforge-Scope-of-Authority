"""One game build's typelib + generated_entities component tables, raw (no names needed: types match by hash)."""
import sys, struct, os
sys.path.insert(0, r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\_tools')
from dltypes import TypeLib, dlsum, find_instances

OLD = r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad/fd_old/datalibrary'
NEW = r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad/fd_new/datalibrary'


class Build:
    def __init__(self, folder):
        self.folder = folder
        self.tl = TypeLib(open(os.path.join(folder, 'dl_library.dl_typelib'), 'rb').read())
        self.ent = open(os.path.join(folder, 'generated_entities.dl_bin'), 'rb').read()
        cid = dlsum('ComponentIndexData')
        self.tables = {}  # table type hash -> (record type hash, record size, base, {resource: index}, records offset)
        for th, t in self.tl.types.items():
            ms = t['members']
            if len(ms) != 2 or ms[0]['type_id'] != cid or ms[0]['atom'] != 'INLINE_ARRAY' or ms[1]['storage'] != 'STRUCT': continue
            inst = next(find_instances(self.ent, th), None)
            if not inst: continue
            base = inst[0]
            idx = {}
            for i in range(ms[0]['arraylen']):
                res, ix = struct.unpack_from('<QI', self.ent, base + 16 * i)
                if res: idx[res] = ix
            rt = ms[1]['type_id']
            self.tables[th] = (rt, self.tl.types[rt]['size'], base, idx, base + ms[1]['offset'], ms[1]['arraylen'])

    def record(self, th, res):
        rt, rsz, base, idx, roff, n = self.tables[th]
        if res not in idx: return None
        return self.ent[roff + rsz * idx[res]: roff + rsz * (idx[res] + 1)]

    def components(self, res):
        return [th for th, t in self.tables.items() if res in t[3]]

    def sharers(self, th, res):
        """Other resources whose index points at the same record."""
        rt, rsz, base, idx, roff, n = self.tables[th]
        return [r for r, i in idx.items() if i == idx.get(res) and r != res]

    def layout(self, tid, seen=None):
        """A comparable signature of a type's layout, recursing into structs."""
        t = self.tl.types.get(tid)
        if t is None: return ('?', tid)
        seen = seen or set()
        if tid in seen: return ('rec', tid)
        seen = seen | {tid}
        ms = []
        for m in t['members']:
            sub = self.layout(m['type_id'], seen) if m['storage'] == 'STRUCT' else (m['type_id'] if m['storage'].startswith('ENUM') else None)
            ms.append((m['offset'], m['size'], m['atom'], m['storage'], m['arraylen'], sub))
        return (t['size'], tuple(ms))

    def has_pointers(self, tid, seen=None):
        t = self.tl.types.get(tid)
        seen = seen or set()
        if t is None or tid in seen: return False
        for m in t['members']:
            if m['atom'] == 'ARRAY' or m['storage'] in ('PTR', 'STR'): return True
            if m['storage'] == 'STRUCT' and self.has_pointers(m['type_id'], seen | {tid}): return True
        return False
