import sys, pickle, json, hashlib
sys.path.insert(0, r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\_tools')
from hd2nxa import Data, tname, murmur64
S = sys.argv[1]
old = pickle.load(open(S + '/old.pkl', 'rb'))
man = json.load(open(r'C:\Users\david\OneDrive\Documents\GitHub\HD2-Extracts\Scope-of-Authority\manifest.json', encoding='utf-8'))
od = Data('F:/Hellforge/game/data'); nd = Data(r'C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2/data')
for it in man['items']:
    res = it['resources']; inold = same = 0
    for r in res:
        k = (murmur64(r['type']), int(r['name'], 16))
        if k in old:
            inold += 1
            orow = next(x for x in od.toc(old[k][0]) if (x['type'], x['name']) == k)
            if hashlib.sha256(od.read(orow)[0]).hexdigest() == r['sha256']: same += 1
    print('%-32s %3d resources, %3d in old build, %3d identical main' % (it['name'], len(res), inold, same))
for p in ['bolt_action_rifle_simo', 'machine_pistol_bull', 'sniper_rifle_duo', 'sniper_rifle_duo_backpack', 'laser_rifle_ion', 'caltrops_grenade', 'caltrops_mine']:
    h = murmur64('packages/generated/loadout/' + p)
    print(p, 'package in old:', (murmur64('package'), h) in old)
