"""Which warbond resources the old build lacks, and what they reference that neither the patch nor the old build has."""
import sys, os, pickle, json, struct
sys.path.insert(0, r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\_tools')
from hd2nxa import Data, tname
S = sys.argv[1]
old = pickle.load(open(S + '/old.pkl', 'rb')); new = pickle.load(open(S + '/new.pkl', 'rb'))
man = json.load(open(r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\manifest.json', encoding='utf-8'))
nd = Data(r'C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2/data')
old_names = {n for (t, n) in old}; new_names = {}
for (t, n), a in new.items(): new_names.setdefault(n, set()).add(t)
archives = sorted({r['archive'] for i in man['items'] for r in i['resources']})
print('archives in old build:', {a: (a in {x for v in old.values() for x in v}) for a in archives})
rows = [r for a in archives for r in nd.toc(a)]
patch = {(r['type'], r['name']) for r in rows}
print('rows', len(rows), 'unique', len(patch), 'already in old', sum(1 for k in patch if k in old))
same = differ = 0
missing = {}
for r in rows:
    k = (r['type'], r['name'])
    m, g, s = nd.read(r)
    for o in range(0, len(m) - 7, 4):
        v = struct.unpack_from('<Q', m, o)[0]
        if v in new_names and v not in old_names and not any((t, v) in patch for t in new_names[v]):
            missing.setdefault(v, set()).add((tname(r['type']), r['name']))
print('referenced but in neither patch nor old build:', len(missing))
for v, who in sorted(missing.items()):
    arcs = sorted({a for t in new_names[v] for a in new[(t, v)]})
    print('  %016x %s in %s <- %s' % (v, [tname(t) for t in new_names[v]], arcs[:4], sorted('%s:%016x' % w for w in who)[:3]))
