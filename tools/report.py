import sys; sys.path.insert(0, '.')
from port import Porter
from hd2nxa import murmur64
from dltypes import dlsum
import pickle
P = Porter()
names = {dlsum(l.strip()): l.strip() for l in open(r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad/fd_new/hashes/dl_type_names.txt', encoding='utf-8') if l.strip()}
old_idx = pickle.load(open(r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad/old.pkl', 'rb'))
E = 'content/fac_helldivers/equipment/'
ents = {'sightliner': E + 'primary_weapons/bolt_action_rifle_simo/sniper_rifle_simo', 'mist': E + 'sidearm_weapons/machine_pistol_bull/machine_pistol_bull',
        'apex': E + 'support_weapons/sniper_rifle_duo/sniper_rifle_duo', 'apex_pack': E + 'backpacks/sniper_rifle_duo_backpack/sniper_rifle_duo_backpack',
        'nova': E + 'support_weapons/laser_rifle_ion/laser_rifle_ion', 'caltrops': E + 'throwables/caltrops_grenade/caltrops_grenade',
        'caltrops_mine': E + 'throwables/caltrops_grenade/caltrops_mine'}
for k, p in ents.items():
    h = murmur64(p)
    print('==', k)
    for th in P.n.components(h):
        nt = P.n.tables[th][0]; ot = P.o.tables[th][0]
        nb = P.n.record(th, h)
        fb = P.o.record(th, h) or bytes(P.o.tl.types[ot]['size'])
        ob, un = P.convert(nt, nb, ot, fb)
        if un: print('  %-40s unmapped %s' % (names.get(th, th), [(names.get(e, '%08x' % e), v) for e, v, _, _ in un]))
