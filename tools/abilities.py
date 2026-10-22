import sys, struct, collections; sys.path.insert(0, '.')
from port import Porter
from hd2nxa import murmur64, load_names
from common import ENTS, TYPE_NAMES, S
P = Porter()
names = load_names([S + '/fd_new/hashes/hashes.txt'])
short = lambda h: names.get(h, '%016x' % h).rsplit('/', 1)[-1]
for k, p in ENTS.items():
    h = murmur64(p)
    for th in P.n.components(h):
        nt = P.n.tables[th][0]; ot = P.o.tables[th][0]
        fb = P.o.record(th, h) or bytes(P.o.tl.types[ot]['size'])
        ob, un = P.convert(nt, P.n.record(th, h), ot, fb)
        for e, v, off, sz in un:
            if TYPE_NAMES.get(e) != 'AbilityId': continue
            rt, rsz, base, idx, roff, n = P.o.tables[th]
            use = collections.defaultdict(list)
            for res, i in idx.items():
                ov = int.from_bytes(P.o.ent[roff + rsz * i + off: roff + rsz * i + off + sz], 'little')
                use[ov].append(short(res))
            print('== %s %s +%d live %d (old fallback %d)' % (k, TYPE_NAMES[th], off, v, int.from_bytes(fb[off:off + sz], 'little')))
            for ov, who in sorted(use.items(), key=lambda x: -len(x[1]))[:25]:
                print('    %5d x%-3d %s' % (ov, len(who), ' '.join(sorted(who)[:8])))
