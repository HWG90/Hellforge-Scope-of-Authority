"""Index every resource (type, name) -> archives for a game data folder; pickled for the other tools."""
import sys, os, pickle, time
sys.path.insert(0, r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\_tools')
from hd2nxa import Data

data_dir, out = sys.argv[1], sys.argv[2]
t = time.time()
d = Data(data_dir)
idx = {}
for a in d.archives():
    for r in d.toc(a):
        idx.setdefault((r['type'], r['name']), []).append(a)
pickle.dump(idx, open(out, 'wb'))
print(data_dir, 'archives', len(d.archives()), 'resources', len(idx), '%.0fs' % (time.time() - t))
