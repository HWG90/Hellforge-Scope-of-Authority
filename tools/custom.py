"""Weapon customization items (attachments) per build: {id: (raw row, debug name, add path hash, full decode)}."""
import struct
from dltypes import dlsum, find_instances


def items(b):
    f = open(b.folder + '/generated_weapon_customization_settings.dl_bin', 'rb').read()
    t = b.tl.types[dlsum('WeaponCustomizationSettings')]; m = t['members'][0]
    out = {}
    for base, size in find_instances(f, dlsum('WeaponCustomizationSettings')):
        p, cnt = struct.unpack_from('<qQ', f, base + m['offset']); rt = m['type_id']; rsz = b.tl.types[rt]['size']
        for i in range(cnt):
            at = base + p + rsz * i
            dn = struct.unpack_from('<q', f, at)[0]
            name = f[base + dn:f.index(b'\0', base + dn)].decode('utf-8', 'replace')
            iid = struct.unpack_from('<I', f, at + 8)[0]
            out[iid] = dict(row=f[at:at + rsz], name=name, add=struct.unpack_from('<Q', f, at + 32)[0], at=at, base=base, file=f, type=rt)

    return out
