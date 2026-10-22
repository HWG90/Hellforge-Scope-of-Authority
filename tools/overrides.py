"""The live game's versions of resources HellForge's build has under the same name, which the data spec cannot replace
(a Steam include must be new to the game copy): written as patches with archive.py into mod/data.

  the Helldiver's animation graphs    avatar_helldiver (third person) and fp_cha_avatar (first person): the states the
                                      live weapons' WeaponReload records name (each weapon's reload and fast reload)
  the audio project                   content/audio/project, content/audio/custom and the project's switch table: the
                                      switch values the live weapons' Wieldable records name for their handling sounds

Every animation the live graphs reference is in the pinned build or in the mod's other patches (checked here)."""
import sys, os, pickle, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd2nxa import Data, murmur64, tname
from common import S
import archive

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'mod', 'data')
NEW = Data(r'C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2/data')
new = pickle.load(open(S + '/new.pkl', 'rb')); old = pickle.load(open(S + '/old.pkl', 'rb'))
spec = json.load(open(os.path.join(HERE, 'hellforge-data.json')))
included = {(murmur64(r['type']), int(i, 16)) for p in spec['patches'] for r in p['resources'] for i in r['include']}

GROUPS = {
    'avatar': [('state_machine', 'content/fac_helldivers/cha_avatar/avatar_helldiver'),
               ('state_machine', 'content/fac_helldivers/fp_cha_avatar/fp_cha_avatar')],
    'audio': [('wwise_metadata', 'content/audio/project'), ('wwise_properties', 'content/audio/custom'),
              (0xE3F2851035957AF5, 0xB9EE36888EF19818)],
}
# OVERRIDES=avatar,audio (the default: both); OVERRIDES=none for neither (the Sightliner graph edit always comes)
wanted = [g for g in os.environ.get('OVERRIDES', 'avatar,audio').split(',') if g in GROUPS]
OVERRIDES = [o for g in wanted for o in GROUPS[g]]
print('overrides:', ', '.join(wanted) or 'none')
AN = murmur64('animation')
by_archive = {}
for t, n in OVERRIDES:
    key = (t if isinstance(t, int) else murmur64(t), n if isinstance(n, int) else murmur64(n))
    arcs = old[key]
    assert arcs == new[key], (t, n, arcs, new[key])   # it stays in the archives it is in
    row = next(x for x in NEW.toc(new[key][0]) if (x['type'], x['name']) == key)
    parts = NEW.read(row)
    if tname(key[0]) == 'state_machine':
        refs = {struct.unpack_from('<Q', parts[0], o)[0] for o in range(0, len(parts[0]) - 7, 4)}
        missing = [v for v in refs if (AN, v) in new and (AN, v) not in old and (AN, v) not in included]
        assert not missing, ('%s needs animations the mod does not have' % n, missing[:5])
    for a in arcs: by_archive.setdefault(a, {})[key] = parts
    print('%s %s: %d bytes, into %s' % (tname(key[0]), n if isinstance(n, str) else '%016x' % n, len(parts[0]), arcs))
# Edited live resources (patched after the data spec's plain copy of them, in the same archive, so they win).
#   The Sightliner's weapon graph: its fire state plays cycle_bolt (the live bolt animation) in place of the small fire
#   kick, so the game's own fire event cycles the bolt. In live, the Sightliner's fire routine sends `cycle` after each
#   shot; no routine of this build does for a magazine-fed weapon. Each state's animation is 164 bytes after its name.
SM = murmur64('state_machine')
SIGHTLINER = 0x41F2DEF484634B59
FIRE_ANIM, CYCLE_BOLT = 0x9BCA4B8601F40676, 0xE63C9B3570413F3E
key = (SM, SIGHTLINER)
row = next(x for x in NEW.toc('ff0ada8dd2ee32cc') if (x['type'], x['name']) == key)
main, gpu, stream = NEW.read(row)
at = 576
assert struct.unpack_from('<Q', main, at)[0] == FIRE_ANIM, 'the Sightliner graph is not the one reviewed'
edited = bytearray(main); struct.pack_into('<Q', edited, at, CYCLE_BOLT)
by_archive.setdefault('2404fa21fe49c32d', {})[key] = (bytes(edited), gpu, stream)
print('state_machine sniper_rifle_simo: fire state plays cycle_bolt (+%d), into 2404fa21fe49c32d' % at)

for a, res in by_archive.items():
    n = 0
    while os.path.exists(os.path.join(OUT, '%s.patch_%d' % (a, n))): n += 1
    archive.write(os.path.join(OUT, '%s.patch_%d' % (a, n)), res)
    print('wrote %s.patch_%d (%d resources)' % (a, n, len(res)))
