import struct, os
def read(path):
    a = open(path, 'rb').read()
    g = open(path + '.gpu_resources', 'rb').read() if os.path.exists(path + '.gpu_resources') else b''
    s = open(path + '.stream', 'rb').read() if os.path.exists(path + '.stream') else b''
    nt, n = struct.unpack_from('<II', a, 4)
    out = {}
    for i in range(n):
        name, typ, mo, so, go = struct.unpack_from('<QQQQQ', a, 72 + 32 * nt + 80 * i)
        ms, ss, gs = struct.unpack_from('<III', a, 72 + 32 * nt + 80 * i + 56)
        out[(typ, name)] = (a[mo:mo + ms], g[go:go + gs], s[so:so + ss])
    return out
