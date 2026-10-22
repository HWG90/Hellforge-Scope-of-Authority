"""Raw rows of a generated_*_settings table, keyed by their first u32 (type / id)."""
import struct, os
from dltypes import dlsum, find_instances


def rows(build, fname, outer):
    b = open(os.path.join(build.folder, fname), 'rb').read()
    tl = build.tl
    t = tl.types[dlsum(outer)]; m = t['members'][0]
    out = {}
    for base, size in find_instances(b, dlsum(outer)):
        p, cnt = struct.unpack_from('<qQ', b, base + m['offset'])
        rt = m['type_id']; rsz = tl.types[rt]['size']
        for i in range(cnt):
            r = b[base + p + rsz * i: base + p + rsz * (i + 1)]
            out[struct.unpack_from('<I', r)[0]] = r
        return out, rt, b, base
    return {}, None, b, None
