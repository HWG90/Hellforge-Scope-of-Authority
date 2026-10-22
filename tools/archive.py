"""Writes a Helldivers 2 patch archive (<bundle>.patch_<n>, .gpu_resources, .stream), byte-for-byte as HellForge's
ResourceArchive.Write (src/HellForge.Core/GameData/ResourceArchive.cs)."""
import struct, io


def _align(n, a): return (n + a - 1) // a * a


def _pad(f, a):
    n = f.tell()
    f.write(b'\0' * (_align(n, a) - n))


def write(path, resources):
    """resources: {(type, name): (main, gpu, stream)}. Writes path, path.gpu_resources and (if non-empty) path.stream."""
    keys = sorted(resources)
    types = sorted({t for t, _ in keys})
    table_end = 72 + 32 * len(types) + 80 * len(keys)
    arc, gpu, stm = io.BytesIO(), io.BytesIO(), io.BytesIO()
    arc.write(b'\0' * _align(table_end, 256))
    entries = bytearray(80 * len(keys))
    main_sum = gpu_sum = 0
    for i, k in enumerate(keys):
        m, g, s = resources[k]
        _pad(arc, 16); _pad(gpu, 64); _pad(stm, 16)
        struct.pack_into('<QQQQQQQIIIIII', entries, 80 * i, k[1], k[0], arc.tell(), stm.tell(), gpu.tell(), main_sum, gpu_sum,
                         len(m), len(s), len(g), 16, 64, i)
        arc.write(m); gpu.write(g); stm.write(s)
        main_sum += _align(len(m), 256); gpu_sum += _align(len(g), 256)
    head = bytearray(72 + 32 * len(types))
    struct.pack_into('<III', head, 0, 0xF0000011, len(types), len(keys))
    struct.pack_into('<QQ', head, 32, main_sum, gpu_sum)
    for j, t in enumerate(types):
        struct.pack_into('<QIIII', head, 72 + 32 * j + 8, t, sum(1 for x in keys if x[0] == t), 0, 16, 64)
    buf = arc.getbuffer()
    buf[:len(head)] = head
    buf[len(head):len(head) + len(entries)] = entries
    open(path, 'wb').write(buf)
    open(path + '.gpu_resources', 'wb').write(gpu.getvalue())
    if stm.tell():
        open(path + '.stream', 'wb').write(stm.getvalue())
