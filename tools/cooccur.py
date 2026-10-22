"""Enum value maps learnt from entities both builds have: the same field of the same entity's record holds the value in
each build's numbering. {enum hash: {new: old}} where the evidence is unanimous."""
import collections, struct, pickle, os
from common import S


def learn(P):
    cache = S + '/cooccur.pkl'
    if os.path.exists(cache): return pickle.load(open(cache, 'rb'))
    votes = collections.defaultdict(collections.Counter)
    for th, (nt, nsz, nbase, nidx, nroff, _) in P.n.tables.items():
        if th not in P.o.tables: continue
        ot, osz, obase, oidx, oroff, _ = P.o.tables[th]
        fields = []
        def walk(om_t, nm_t, oo, no):
            for om, nm in P.pairs(om_t, nm_t):
                cnt = nm['arraylen'] if nm['atom'] == 'INLINE_ARRAY' else 1
                if nm['storage'] == 'STRUCT':
                    for i in range(cnt):
                        walk(om['type_id'], nm['type_id'], oo + om['offset'] + P.o.tl.types[om['type_id']]['size'] * i,
                             no + nm['offset'] + P.n.tl.types[nm['type_id']]['size'] * i)
                elif nm['storage'].startswith('ENUM') and nm['atom'] != 'BITFIELD':
                    es = nm['size'] // cnt
                    for i in range(cnt): fields.append((nm['type_id'], oo + om['offset'] + es * i, no + nm['offset'] + es * i, es))
        walk(ot, nt, 0, 0)
        for res, ni in nidx.items():
            oi = oidx.get(res)
            if oi is None: continue
            for e, oo, no, es in fields:
                nv = int.from_bytes(P.n.ent[nroff + nsz * ni + no: nroff + nsz * ni + no + es], 'little')
                ov = int.from_bytes(P.o.ent[oroff + osz * oi + oo: oroff + osz * oi + oo + es], 'little')
                votes[(e, nv)][ov] += 1
    out = collections.defaultdict(dict)
    for (e, nv), c in votes.items():
        if len(c) == 1: out[e][nv] = next(iter(c))
    out = dict(out)
    pickle.dump(out, open(cache, 'wb'))
    return out
