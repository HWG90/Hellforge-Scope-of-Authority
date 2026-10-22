"""generated_entity_deltas (after FileDiver's entity_deltas.go): an attachment's AddPath -> [(component table type hash,
[(record offset, bytes)])], with each build's component index resolved to its table type."""
import struct, os


def load(build):
    ent = build.ent
    index_type = {}
    pos = ent.find(b'LDLD', 8)
    while pos >= 0:
        index_type[struct.unpack_from('<I', ent, pos - 8)[0]] = struct.unpack_from('<I', ent, pos + 8)[0]
        pos = ent.find(b'LDLD', pos + 4)
    dbin = open(os.path.join(build.folder, 'generated_entity_deltas.dl_bin'), 'rb').read()
    dbase = 28
    (hm_o, hm_n, st_o, st_n, cs_o, cs_n, de_o, de_n, da_o, da_n) = struct.unpack_from('<10Q', dbin, dbase)
    out = {}
    for i in range(hm_n):
        rid, idx = struct.unpack_from('<QI', dbin, dbase + hm_o + 16 * i)
        if not rid: continue
        mcount, first = struct.unpack_from('<II', dbin, dbase + st_o + 8 * idx)
        comps = []
        for c in range(mcount):
            ci, fd, dc = struct.unpack_from('<III', dbin, dbase + cs_o + 12 * (first + c))
            ds = []
            for j in range(dc):
                off, size, doff = struct.unpack_from('<III', dbin, dbase + de_o + 12 * (fd + j))
                ds.append((off, dbin[dbase + da_o + doff:dbase + da_o + doff + size]))
            comps.append((index_type.get(ci), ds))
        out[rid] = comps
    return out
