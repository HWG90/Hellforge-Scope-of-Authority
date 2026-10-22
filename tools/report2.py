import sys, struct; sys.path.insert(0, '.')
from port import Porter
from rows import Rows
from hd2nxa import murmur64
from common import ENTS as ents, TYPE_NAMES as names
P = Porter(); R = Rows(P)
for k, p in ents.items():
    h = murmur64(p); refs = []
    for th in P.n.components(h):
        nt = P.n.tables[th][0]
        nb = P.n.record(th, h)
        def walk(t, off):
            for m in P.n.tl.types[t]['members']:
                cnt = m['arraylen'] if m['atom'] == 'INLINE_ARRAY' else 1
                if m['storage'] == 'STRUCT':
                    es = P.n.tl.types[m['type_id']]['size']
                    for i in range(cnt): walk(m['type_id'], off + m['offset'] + es * i)
                elif m['storage'].startswith('ENUM') and m['type_id'] in R.t:
                    es = m['size'] // cnt
                    for i in range(cnt):
                        v = int.from_bytes(nb[off + m['offset'] + es * i: off + m['offset'] + es * (i + 1)], 'little')
                        if v: refs.append((m['type_id'], v))
        walk(nt, 0)
    print('==', k)
    for (e, v), r in sorted(R.closure(refs).items(), key=lambda x: (x[1]['table'], x[0][1])):
        print('   %-15s live %4d -> old %-5s %s nested-unmapped=%s' % (r['table'], v, r['old'], 'SAME' if r['same'] else 'differs', [(R.t[ne][0] if ne in R.t else '%08x' % ne, nv) for ne, nv, _, _ in r['nested']]))
