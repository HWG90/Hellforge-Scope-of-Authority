"""Settings rows a weapon references, recursively, ported to the pinned build: for each (table, live id) its old id (when
the enum maps), whether the ported row equals the old row, and the nested references it holds."""
import sys; sys.path.insert(0, '.')
import settings
from port import Porter
from dltypes import dlsum

TABLES = {  # enum type name -> (file, outer type)
    'ProjectileType': ('generated_projectile_settings.dl_bin', 'ProjectileSettings'),
    'DamageInfoType': ('generated_damage_settings.dl_bin', 'DamageSettings'),
    'ExplosionType': ('generated_explosion_settings.dl_bin', 'ExplosionSettings'),
    'BeamType': ('generated_beam_settings.dl_bin', 'BeamSettings'),
    'ArcType': ('generated_arc_settings.dl_bin', 'ArcSettings'),
}


class Rows:
    def __init__(self, P):
        self.P = P
        self.t = {}
        for en, (f, outer) in TABLES.items():
            ro, to, _, _ = settings.rows(P.o, f, outer); rn, tn, _, _ = settings.rows(P.n, f, outer)
            self.t[dlsum(en)] = (en, ro, to, rn, tn)

    def port(self, enum_hash, live_id):
        en, ro, to, rn, tn = self.t[enum_hash]
        nb = rn[live_id]
        old_id = self.P.emap.get(enum_hash, {}).get(live_id)
        fb = ro.get(old_id) if old_id is not None else None
        ob, un = self.P.convert(tn, nb, to, fb if fb is not None else bytes(self.P.o.tl.types[to]['size']))
        return dict(table=en, live=live_id, old=old_id, same=(fb == ob), row=ob, nested=un, row_size=len(ob))

    def closure(self, refs):
        """refs: [(enum hash, live id)] -> {(enum hash, live id): port()} including every nested table reference."""
        out, todo = {}, list(refs)
        while todo:
            e, v = todo.pop()
            if (e, v) in out or e not in self.t or v == 0: continue
            r = self.port(e, v); out[(e, v)] = r
            todo += [(ne, nv) for ne, nv, _, _ in r['nested']]
            # mapped nested references are already translated; still follow them to check their rows
            en, ro, to, rn, tn = self.t[e]
            for om, nm in self.P.pairs(to, tn):
                if nm['storage'].startswith('ENUM') and nm['type_id'] in self.t and nm['atom'] == 'POD':
                    import struct
                    nv = struct.unpack_from('<I', rn[v], nm['offset'])[0]
                    if nv: todo.append((nm['type_id'], nv))
        return out
