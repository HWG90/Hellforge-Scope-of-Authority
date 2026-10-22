"""Generates the Scope of Authority mod's data from the two game builds' own tables:

  src/live_data.h       every warbond entity's component records as the live game (01.007.200) has them, converted to
                        the pinned build's (25480438) layouts and enum numbering, with the base records they are written
                        over (to keep what HellForge set), and the projectile/damage rows the weapons fire
  hellforge-data.json   the warbond's resources new to the pinned build, from Steam's install, patched into the archives
                        of each weapon's base (which its copy loads), and the armory icons into the icon archives

Run with the plaintext tables from FileDiver (dlbuild.OLD / NEW) and the two resource indexes (index_build.py).
Nothing of the game's is written into the mod folder except as C arrays of record bytes for the mod's own build."""
import sys, os, json, struct, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from port import Porter
from rows import Rows
from hd2nxa import murmur64, tname, load_names, Data
from dltypes import dlsum
from common import S, TYPE_NAMES, ENTS, E
import custom, deltas

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mod')
P = Porter(); R = Rows(P)
names = load_names([S + '/fd_new/hashes/hashes.txt'])
OLDIDX = pickle.load(open(S + '/old.pkl', 'rb')); NEWIDX = pickle.load(open(S + '/new.pkl', 'rb'))
OLD_NAMES = {n for (t, n) in OLDIDX}
CUST_O, CUST_N = custom.items(P.o), custom.items(P.n)
DELTAS = deltas.load(P.n)
AB = dlsum('AbilityId'); PT = dlsum('ProjectileType'); DT = dlsum('DamageInfoType')
RACK = 'content/fac_helldivers/hellpod/weapon_rack/'
H = lambda p: murmur64(p)

# Abilities the live build added (new game code): each takes the ability of the vanilla weapon its family was cloned
# from, found by where the new id sits in the live enum (abilities.py): {(component, offset, live id): old id}.
ABILITY_DONORS = {
    # The Sightliner reloads a magazine (its live reload sits among the marksman rifles'): the R-63 Diligence's reload.
    # Its fire routine sits beside the R-2124 Constitution's bolt cycle (the Constitution's reload is a stripper-clip one,
    # for a WeaponRounds record the Sightliner does not have).
    ('WeaponReloadComponentData', 2765): 2750,         # Sightliner reload  <- R-63 Diligence's (marksman_rifle)
    ('WeaponDataComponentData', 2694): 2684,           # Sightliner fire    <- R-2124 Constitution's bolt cycle
    ('WeaponReloadComponentData', 2808): 2794,         # Mist reload        <- P-19 Redeemer's (automatic_pistol)
    ('WeaponDataComponentData', 2712): 0,              # Mist folding stock <- none (the Redeemer has none)
    # The Apex is magazine-fed: its team reload takes the GR-8 Recoilless Rifle's (magazine), not the AC-8's (clips into
    # a WeaponRounds record); its fire routine the common one (43 weapons), not a clip weapon's.
    ('WeaponAssistedReloadComponentData', 2630): 61,   # Apex team reload   <- GR-8 Recoilless Rifle's
    ('WeaponAssistedReloadComponentData', 2629): 60,
    ('WeaponReloadComponentData', 2835): 2820,         # Apex reload        <- APW-1 Anti-Materiel Rifle's (sniper_rifle)
    ('WeaponDataComponentData', 2677): 2708,           # Apex fire          <- the common fire routine
    ('WeaponHeatComponentData', 2881): 2862,           # Nova overheat      <- LAS-98 Laser Cannon's
}

# Each live entity: what HellForge registers it as, its base (whose component set it must have), and its text.
STRINGS = json.load(open(r'C:/Users/david/OneDrive/Documents/GitHub/HD2-Extracts/Scope-of-Authority/strings_en-us.json', encoding='utf-8'))
def text(item, i): return STRINGS[item][i]['text']
ITEMS = [
    dict(key='sightliner', kind='weapon', path=ENTS['sightliner'], base_item='HF_ITEM_R63_DILIGENCE', base=0x03E67A19B07C6523,
         designation=text('R-40 Sightliner', 0), name=text('R-40 Sightliner', 1), description=text('R-40 Sightliner', 3)),
    dict(key='mist', kind='weapon', path=ENTS['mist'], base_item='HF_ITEM_P19_REDEEMER', base=0x3575AABC5F1F9326,
         designation=text('P-44 Mist', 0), name=text('P-44 Mist', 1), description=text('P-44 Mist', 3)),
    dict(key='apex', kind='entity', path=ENTS['apex'], base=0x9F80D67A12A7E40F, extra_ok={'BackblastComponentData'},
         designation=text('AMW-20 Apex', 0), name=text('AMW-20 Apex', 1), description=text('AMW-20 Apex', 3)),
    # the Recoilless Rifle's backpack (the same component set): the Apex is called in on the Recoilless Rifle's stratagem,
    # which loads that backpack's package, so the Apex Protector's resources go into its archive
    dict(key='apex_pack', kind='entity', path=ENTS['apex_pack'], base=0x96DFC6542AA22980,
         designation=text('AMW-20 Apex', 0), name='Apex Protector', description=None),
    dict(key='nova', kind='entity', path=ENTS['nova'], base=0x35A61296619CC47E,
         designation=text('LAS-44 Nova', 0), name=text('LAS-44 Nova', 1), description=text('LAS-44 Nova', 3)),
    dict(key='apex_rack', kind='entity', path=RACK + 'weapon_rack_sniper_rifle_duo', base=H(RACK + 'weapon_rack_recoilless_rifle'),
         designation=None, name=None, description=None),
    dict(key='nova_rack', kind='entity', path=RACK + 'weapon_rack_laser_rifle_ion', base=H(RACK + 'weapon_rack_laser_pulse_cannon'),
         designation=None, name=None, description=None),
]
# Live archives (packages) -> the entity whose base's package loads them in the pinned build.
ARCHIVES = {'ff0ada8dd2ee32cc': 'sightliner', '7160179c08dd7d81': 'mist', 'a193a00ce4bbd529': 'apex', '6f09a6ce25c8ca77': 'apex_pack',
            '601d726de9c3962f': 'nova'}
ICON_ARCHIVES = {'texture': '033fd51c0660afa2', 'material': '07f10cad298067ec'}

# LoadoutPackage: the package (and its bundle tag) stays the base's, the archive our data patches; the sound bank is live.
KEEP = {'LoadoutPackageComponentData': [(0, 16)],
        # the ten text ids: the live ones are not in the pinned build's strings (HellForge gives the text); the icon is live
        'EncyclopediaEntryComponentData': [(0, 48)]}

log = []
def note(*a): log.append(' '.join(str(x) for x in a)); print(*a)


def default_items(rec_new):
    """The live WeaponCustomization record's default attachments: [(index, slot, id)]."""
    return [(i,) + struct.unpack_from('<II', rec_new, 8 * i) for i in range(10) if struct.unpack_from('<I', rec_new, 8 * i + 4)[0]]


def live_records(item):
    """{component table hash: new-layout bytes} for an entity, with the default attachments the pinned build lacks
    applied as their deltas (and dropped from its defaults), as the game would apply them when it builds the weapon."""
    h = H(item['path'])
    recs = {th: bytearray(P.n.record(th, h)) for th in P.n.components(h)}
    wc = dlsum('WeaponCustomizationComponentData')
    if wc in recs:
        for i, slot, iid in default_items(recs[wc]):
            if iid in CUST_O: continue
            it = CUST_N[iid]
            note('  %s: default %s "%s" is not in the pinned build: its delta is applied, the item dropped' % (item['key'], iid, it['name']))
            for th, ds in DELTAS.get(it['add'], []):
                for off, data in ds:
                    recs[th][off:off + len(data)] = data
            struct.pack_into('<II', recs[wc], 8 * i, 0, 0)
    return {th: bytes(b) for th, b in recs.items()}


def c_bytes(b):
    return ','.join('0x%02x' % x for x in b)


out_h = ['/* Generated by tools/gen.py from the game\'s tables (live 01.007.200, pinned 25480438); do not edit. */',
         '#pragma once', '#include "live_types.h"', '']
entities = []
proj_rows, dmg_rows = {}, {}  # live id -> port() result


def want_rows(e, v):
    for (ee, vv), r in R.closure([(e, v)]).items():
        if r['old'] is not None and r['same']: continue          # the pinned build has it as it is
        (proj_rows if ee == PT else dmg_rows if ee == DT else {}).setdefault(vv, r)
        if ee not in (PT, DT): note('  WARNING row %s %d differs and cannot be added' % (r['table'], vv))


for item in ITEMS:
    h = H(item['path'])
    note('==', item['key'], '%016x' % h, 'base %016x' % item['base'])
    live = live_records(item)
    base_comps = set(P.o.components(item['base']))
    missing = set(live) - base_comps
    extra = base_comps - set(live) - {dlsum(x) for x in item.get('extra_ok', ())}
    assert not missing and not extra, (item['key'], [TYPE_NAMES.get(x) for x in missing], [TYPE_NAMES.get(x) for x in extra])
    recs = []
    for th in sorted(live, key=lambda t: TYPE_NAMES[t]):
        cname = TYPE_NAMES[th]
        nt = P.n.tables[th][0]; ot = P.o.tables[th][0]
        base_rec = P.o.record(th, item['base'])
        ob, un = P.convert(nt, live[th], ot, base_rec)
        ob = bytearray(ob)
        fixes = []
        for e, v, off, sz in un:
            if e == AB:
                donor = ABILITY_DONORS[(cname, v)]
                struct.pack_into('<I', ob, off, donor); note('  %s +%d ability %d -> %d (donor)' % (cname, off, v, donor))
            elif e == PT:
                want_rows(PT, v); fixes.append((off, 1, v))
            elif e == DT:
                want_rows(DT, v); fixes.append((off, 2, v))
            else:
                note('  WARNING %s +%d enum %s value %d has no pinned value; the base\'s is kept' % (cname, off, TYPE_NAMES.get(e, '%08x' % e), v))
        # mapped projectile references whose rows the live build changed need their own copy too
        for om, nm in P.pairs(ot, nt):
            if nm['type_id'] == PT and nm['atom'] == 'POD':
                v = struct.unpack_from('<I', live[th], nm['offset'])[0]
                if v and P.emap[PT].get(v) is not None:
                    r = R.port(PT, v)
                    if not r['same'] or any(True for ee, vv, _, _ in r['nested']):
                        want_rows(PT, v); fixes.append((om['offset'], 1, v))
        recs.append(dict(name=cname, live=bytes(ob), base=base_rec, fixes=fixes, keep=KEEP.get(cname, []),
                         base_index=P.o.tables[th][3][item['base']]))
    if 'BackblastComponentData' in item.get('extra_ok', ()):
        th = dlsum('BackblastComponentData'); b = P.o.record(th, item['base'])
        recs.append(dict(name='BackblastComponentData', live=bytes(8) + b[8:], base=b, fixes=[], keep=[],
                         base_index=P.o.tables[th][3][item['base']]))
        note('  BackblastComponentData: the base\'s, with its cone (+0 length, +4 factor) zeroed: the Apex has none')
    entities.append(dict(item, records=recs))

# Settings rows: damage first (projectile rows name them), each a copy of the closest vanilla row, then overwritten.
def closest(table_rows, row):
    return min((k for k in table_rows if k), key=lambda k: sum(1 for i in range(4, len(row)) if table_rows[k][i] != row[i]))

for v, r in sorted(dmg_rows.items()):
    r['base'] = r['old'] if r['old'] else closest(R.t[DT][1], r['row'])
    note('damage live %d -> copy of %d' % (v, r['base']))
for v, r in sorted(proj_rows.items()):
    r['base'] = r['old'] if r['old'] else closest(R.t[PT][1], r['row'])
    en, ro, to, rn, tn = R.t[PT]
    r['row'], r['nested'] = P.convert(tn, rn[v], to, ro[r['base']])   # a new type's row over its base's, not zeros
    r['fixes'] = []
    for e, nv, off, sz in r['nested']:
        if e == PT and off == 0: continue
        if e == DT: r['fixes'].append((off, 2, nv)); assert nv in dmg_rows
        else: note('  WARNING projectile %d +%d enum %s %d unmapped' % (v, off, TYPE_NAMES.get(e, '%08x' % e), nv))
    # mapped damage refs whose rows changed
    note('projectile live %d -> copy of %d, fixes %s' % (v, r['base'], r['fixes']))

# --- C header --------------------------------------------------------------------------------------------------------
def cstr(s): return 'NULL' if s is None else json.dumps(s, ensure_ascii=False)
dmg_ids = sorted(dmg_rows); proj_ids = sorted(proj_rows)
idx = lambda kind, v: (proj_ids if kind == 1 else dmg_ids).index(v)
for v in dmg_ids:
    out_h.append('static const uint8_t damage_%d[] = {%s};' % (v, c_bytes(dmg_rows[v]['row'])))
for v in proj_ids:
    r = proj_rows[v]
    out_h.append('static const uint8_t projectile_%d[] = {%s};' % (v, c_bytes(r['row'])))
    out_h.append('static const LiveFix projectile_%d_fixes[] = {%s{0}};' % (v, ''.join('{%d,%d,%d},' % (o, k, idx(k, nv)) for o, k, nv in r['fixes'])))
out_h.append('static const LiveRow live_damage[] = {%s};' % ','.join('{%d,%d,damage_%d,sizeof damage_%d,NULL}' % (v, dmg_rows[v]['base'], v, v) for v in dmg_ids))
out_h.append('static const LiveRow live_projectiles[] = {%s};' % ','.join('{%d,%d,projectile_%d,sizeof projectile_%d,projectile_%d_fixes}' % (v, proj_rows[v]['base'], v, v, v) for v in proj_ids))
out_h.append('#define LIVE_DAMAGE_COUNT %d' % len(dmg_ids))
out_h.append('#define LIVE_PROJECTILE_COUNT %d' % len(proj_ids))
out_h.append('')
# Each table as the vanilla data has it, for finding HellForge's moved copy of it in memory (scope_of_authority.c,
# FindTables): the copy keeps the vanilla index (slots, 16-byte entries: resource, record index) at its start and the
# vanilla records at the vanilla record offset, with room for as many records as the index has slots. Two 32-byte
# windows of the vanilla index, each unique in the entity data, find it.
def windows(th):
    rt, rsz, base, idx, roff, n = P.o.tables[th]
    slots = P.o.tl.types[th]['members'][0]['arraylen']
    out = []
    for i in list(range(0, slots - 1, max(1, slots // 7)))[1:]:
        for j in range(i, slots - 1):
            a = base + 16 * j
            w = P.o.ent[a:a + 32]
            if struct.unpack_from('<Q', w, 0)[0] and struct.unpack_from('<Q', w, 16)[0] and P.o.ent.count(w) == 1:
                out.append((16 * j, w)); break
        if len(out) == 2: break
    assert len(out) == 2, TYPE_NAMES[th]
    return slots, n, roff - base, rsz, out
tables_done = set()
for e in entities:
    for r in e['records']:
        th = dlsum(r['name'])
        if th in tables_done: continue
        tables_done.add(th)
        slots, n, roff, rsz, ws = windows(th)
        out_h.append('static const LiveTable table_%s = {"%s", %d, %d, %d, %d, {%d, %d}, {{%s}, {%s}}};' % (
            r['name'], r['name'], slots, n, roff, rsz, ws[0][0], ws[1][0], c_bytes(ws[0][1]), c_bytes(ws[1][1])))
out_h.append('')
for e in entities:
    k = e['key']
    for i, r in enumerate(e['records']):
        assert len(r['live']) == len(r['base'])
        out_h.append('static const uint8_t %s_%d_live[] = {%s};' % (k, i, c_bytes(r['live'])))
        out_h.append('static const uint8_t %s_%d_base[] = {%s};' % (k, i, c_bytes(r['base'])))
        out_h.append('static const LiveFix %s_%d_fixes[] = {%s{0}};' % (k, i, ''.join('{%d,%d,%d},' % (o, kd, idx(kd, nv)) for o, kd, nv in r['fixes'])))
        out_h.append('static const LiveKeep %s_%d_keep[] = {%s{0}};' % (k, i, ''.join('{%d,%d},' % kp for kp in r['keep'])))
    out_h.append('static const LiveRecord %s_records[] = {%s{0}};' % (k, ''.join(
        '{"%s",%d,%s_%d_live,%s_%d_base,%s_%d_fixes,%s_%d_keep,&table_%s,%d},' % (r['name'], len(r['live']), k, i, k, i, k, i, k, i, r['name'], r['base_index'])
        for i, r in enumerate(e['records']))))
out_h.append('')
out_h.append('enum { %s, LIVE_ENTITY_COUNT };' % ', '.join('LIVE_%s' % e['key'].upper() for e in entities))
out_h.append('static LiveEntity live_entities[] = {')
for e in entities:
    out_h.append('    {"%s", "%s", 0x%016XULL, %s, %s, %s, %s, %s_records},' % (
        e['key'], e['path'], e['base'], e.get('base_item', '0'), cstr(e['designation']), cstr(e['name']), cstr(e['description']), e['key']))
out_h.append('};')
os.makedirs(os.path.join(MOD, 'src'), exist_ok=True)
open(os.path.join(MOD, 'src', 'live_data.h'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out_h) + '\n')

# --- data spec -------------------------------------------------------------------------------------------------------
nd = Data(r'C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2/data')
base_pkg = {}
lp = dlsum('LoadoutPackageComponentData')
for e in entities:
    r = P.o.record(lp, e['base'])
    if r: base_pkg[e['key']] = '%016x' % struct.unpack_from('<Q', r, 8)[0]
note('base packages', base_pkg)
patches = []
for arc, key in ARCHIVES.items():
    # The patched base archive carries everything the live archive carries, as the live package loads it all with the
    # weapon: what is new from Steam, and what the pinned build has elsewhere (attachments the live weapon shares with
    # other weapons, their materials and textures) from the game copy, which the base's package would not load.
    by_type = collections.defaultdict(list); from_game = collections.defaultdict(list)
    for row in nd.toc(arc):
        k = (row['type'], row['name'])
        if k not in OLDIDX: by_type[tname(row['type'])].append('0x%016X' % row['name'])
        elif base_pkg[key] not in OLDIDX[k]: from_game[tname(row['type'])].append('0x%016X' % row['name'])
    res = [{'type': t, 'include': sorted(ids), 'source': 'steam'} for t, ids in sorted(by_type.items())]
    res += [{'type': t, 'include': sorted(ids)} for t, ids in sorted(from_game.items())]
    targets = [base_pkg[key]]
    patches.append({'archives': sorted(set(targets)), 'resources': res})
    note('patch', arc, '->', targets, 'new', {t: len(v) for t, v in by_type.items()}, 'from the game copy', {t: len(v) for t, v in from_game.items()})
# Everything else the live patch added, in an archive the pinned build also has: patched into that archive, so it loads
# wherever the live game loads it (streamed sounds, shader libraries, UI icons, shared effects and attachments). Map
# content (levels, prefabs, foliage), entity resources and package definitions only matter to live code that asks for
# them, so they stay out.
# Shader libraries stay out: the live build's compiled shaders crash this build's renderer when their archive loads
# ("Guard page (0x80000001)" on the renderer thread, 2026-10-22; bisect builds A-D). The two live materials whose parent
# shaders are new (environment decals) stay out with them.
ALL_NEW_TYPES = {'texture', 'material', 'unit', 'physics', 'animation', 'bones', 'state_machine', 'particles',
                 'wwise_stream', 'wwise_bank', 'wwise_dep'}
NEW_SHADER_MATERIALS = {0x34A3C6136AE14780, 0x552D9529080EF268, 0x7F8A0B068A75497B}
OLD_ARCHIVES = {a for v in OLDIDX.values() for a in v}
in_warbond = {(murmur64(r['type']), int(i, 16)) for p in patches for r in p['resources'] for i in r['include']}
rest = collections.defaultdict(lambda: collections.defaultdict(set))  # archive -> type -> ids
ALL_NEW = os.environ.get('ALL_NEW', '1') != '0'   # ALL_NEW=0: the warbond's own archives only (crash bisect)
for (t, n), arcs in (NEWIDX.items() if ALL_NEW else []):
    if (t, n) in OLDIDX or (t, n) in in_warbond or tname(t) not in ALL_NEW_TYPES or n in NEW_SHADER_MATERIALS: continue
    home = sorted(a for a in arcs if a in OLD_ARCHIVES)
    if home: rest[home[0]][tname(t)].add(n)
for a, by in sorted(rest.items()):
    patches.append({'archives': [a], 'resources': [{'type': t, 'include': sorted('0x%016X' % i for i in ids), 'source': 'steam'} for t, ids in sorted(by.items())]})
note('new in live, patched in place: %d resources in %d archives %s' % (sum(len(i) for by in rest.values() for i in by.values()), len(rest),
     dict(collections.Counter(t for by in rest.values() for t, i in by.items() for _ in i))))

# Every resource a ported record or row names must now be in the pinned build or in a patch.
patched = {int(i, 16) for p in patches for r in p['resources'] for i in r['include']}
new_by_name = collections.defaultdict(set)
for (t, n), a in NEWIDX.items(): new_by_name[n].add(t)
def check(label, b, skip=()):
    for o in range(0, len(b) - 7, 4):
        if any(a <= o < a + n for a, n in skip): continue
        v = struct.unpack_from('<Q', b, o)[0]
        if v in new_by_name and v not in OLD_NAMES and v not in patched:
            note('  MISSING %016x %s in %s named by %s +%d' % (v, sorted(tname(t) for t in new_by_name[v]),
                 sorted({a for t in new_by_name[v] for a in NEWIDX[(t, v)]}), label, o))
for e in entities:
    for r in e['records']: check('%s %s' % (e['key'], r['name']), r['live'], r['keep'])
for v, r in list(dmg_rows.items()) + list(proj_rows.items()): check('row %s %d' % (r['table'], v), r['row'])
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hellforge-data.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps({'format': 1, 'patches': patches}, indent=2) + '\n')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
