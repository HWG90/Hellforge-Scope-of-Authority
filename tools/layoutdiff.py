import sys; sys.path.insert(0, '.')
from dlbuild import Build, OLD, NEW
from hd2nxa import murmur64
o, n = Build(OLD), Build(NEW)
E = 'content/fac_helldivers/equipment/'
ents = {'sightliner': E + 'primary_weapons/bolt_action_rifle_simo/sniper_rifle_simo', 'mist': E + 'sidearm_weapons/machine_pistol_bull/machine_pistol_bull',
        'apex': E + 'support_weapons/sniper_rifle_duo/sniper_rifle_duo', 'apex_pack': E + 'backpacks/sniper_rifle_duo_backpack/sniper_rifle_duo_backpack',
        'nova': E + 'support_weapons/laser_rifle_ion/laser_rifle_ion', 'caltrops': E + 'throwables/caltrops_grenade/caltrops_grenade',
        'caltrops_mine': E + 'throwables/caltrops_grenade/caltrops_mine'}
print('tables old', len(o.tables), 'new', len(n.tables))
for k, p in ents.items():
    h = murmur64(p)
    comps = n.components(h)
    rows = []
    for th in comps:
        rt = n.tables[th][0]
        st = 'NEWTABLE' if th not in o.tables else ('same' if o.layout(o.tables[th][0]) == n.layout(rt) else 'LAYOUT')
        ptr = 'ptr' if n.has_pointers(rt) else ''
        inold = 'inold' if h in o.tables.get(th, (0, 0, 0, {}))[3] else ''
        eq = ''
        if inold: eq = 'eq' if o.record(th, h) == n.record(th, h) else 'diff'
        rows.append('%08x:%s%s%s%s' % (th, st, ':' + ptr if ptr else '', ':' + inold if inold else '', ':' + eq if eq else ''))
    print(k, len(comps)); print('   ' + ' '.join(rows))
