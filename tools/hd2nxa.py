"""Read-only reader for Helldivers 2 DSAA/DSAR (.nxa) game data, after HellForge's GameDataReader.cs."""
import struct, os, lz4.block
from collections import OrderedDict

M = 0xc6a4a7935bd1e995
MASK = (1 << 64) - 1


def murmur64(s, seed=0):
    b = s.encode() if isinstance(s, str) else s
    h = (seed ^ (len(b) * M)) & MASK
    n = len(b) // 8
    for i in range(n):
        k = struct.unpack_from('<Q', b, 8 * i)[0]
        k = (k * M) & MASK; k ^= k >> 47; k = (k * M) & MASK
        h ^= k; h = (h * M) & MASK
    t = b[8 * n:]
    if t:
        for i in range(len(t) - 1, -1, -1):
            h ^= t[i] << (8 * i)
        h = (h * M) & MASK
    h ^= h >> 47; h = (h * M) & MASK; h ^= h >> 47
    return h


def thin(s):
    return murmur64(s) >> 32


TYPES = ["unit", "material", "texture", "particles", "wwise_bank", "wwise_dep", "wwise_stream", "animation", "state_machine",
         "bones", "physics", "lua", "package", "font", "strings", "entity", "geometry_group", "prefab", "level", "ah_bin",
         "xaml", "speedtree", "shading_environment", "ttf", "render_config", "network_config", "config", "mouse_cursor",
         "shader_library", "shader_library_group", "vector_field", "wwise_metadata", "wwise_properties", "dl_bin",
         "texture_atlas", "timpani_bank", "timpani_master", "apb", "data", "ivf", "bik", "surface_properties", "sound_environment"]
TYPE_NAME = {murmur64(t): t for t in TYPES}
T = {t: murmur64(t) for t in TYPES}


def tname(h):
    return TYPE_NAME.get(h, '%016x' % h)


def _dsar(path):
    with open(path, 'rb') as f:
        hdr = f.read(32)
        assert hdr[:4] == b'DSAR', path
        n = struct.unpack_from('<i', hdr, 8)[0]
        raw = f.read(32 * n)
    return [struct.unpack_from('<QQIIB', raw, 32 * i) for i in range(n)]  # uoff, coff, usize, csize, comp


class Data:
    def __init__(self, folder):
        self.folder = folder
        self.fh = {}
        idx = os.path.join(folder, 'bundles.nxa')
        d = b''.join(self._dec(self._raw(idx, c), c) for c in _dsar(idx))
        assert d[:4] == b'DSAA'
        nb, ni = struct.unpack_from('<ii', d, 12)
        cstr = lambda o: d[o:d.index(b'\0', o)].decode()
        self.bundles = []
        for i in range(nb):
            fn = os.path.join(folder, cstr(struct.unpack_from('<i', d, 24 + 24 * ni + 4 * i)[0]))
            ch = _dsar(fn)
            self.bundles.append((fn, ch, {c[0]: j for j, c in enumerate(ch)}))
        self.items = {}
        for i in range(ni):
            size, nameoff, cnt, at = struct.unpack_from('<QiiQ', d, 24 + 24 * i)
            ents = [(struct.unpack_from('<I', d, at + 16 * e)[0], struct.unpack_from('<I', d, at + 16 * e + 8)[0], d[at + 16 * e + 15])
                    for e in range(cnt)]
            self.items[cstr(nameoff)] = (size, ents)
        self.cache = OrderedDict()

    def _raw(self, fn, c):
        f = self.fh.get(fn) or self.fh.setdefault(fn, open(fn, 'rb'))
        f.seek(c[1]); return f.read(c[3])

    @staticmethod
    def _dec(raw, c):
        if c[4] == 0: return raw
        if c[4] == 3: return lz4.block.decompress(raw, uncompressed_size=c[2])
        raise ValueError('compression %d' % c[4])

    def _chunk(self, b, j):
        k = (b, j)
        if k in self.cache:
            self.cache.move_to_end(k); return self.cache[k]
        fn, ch, _ = self.bundles[b]
        v = self._dec(self._raw(fn, ch[j]), ch[j])
        self.cache[k] = v
        if len(self.cache) > 96: self.cache.popitem(last=False)
        return v

    def item_bytes(self, name, start, length):
        size, ents = self.items[name]
        length = min(length, size - start)
        if length <= 0: return b''
        out = bytearray(length)
        for i, (aoff, boff, bi) in enumerate(ents):
            end = ents[i + 1][0] if i + 1 < len(ents) else size
            if end <= start or aoff >= start + length: continue
            fn, ch, byoff = self.bundles[bi]
            j = byoff[boff]
            at = aoff
            while at < end and at < start + length:
                nxt = at + ch[j][2]
                if nxt > start:
                    data = self._chunk(bi, j)
                    lo, hi = max(at, start), min(nxt, start + length)
                    out[lo - start:hi - start] = data[lo - at:hi - at]
                at = nxt; j += 1
        return bytes(out)

    def archives(self):
        return sorted(n for n in self.items if len(n) == 16 and '.' not in n)

    def toc(self, archive):
        head = self.item_bytes(archive, 0, 72)
        if len(head) < 72 or struct.unpack_from('<I', head)[0] != 0xF0000011: return []
        ntypes, count = struct.unpack_from('<II', head, 4)
        start = 72 + 32 * ntypes
        tbl = self.item_bytes(archive, start, 80 * count)
        rows = []
        for i in range(count):
            name, typ, moff, soff, goff = struct.unpack_from('<QQQQQ', tbl, 80 * i)
            msz, ssz, gsz = struct.unpack_from('<III', tbl, 80 * i + 56)
            rows.append(dict(archive=archive, type=typ, name=name, moff=moff, msz=msz, soff=soff, ssz=ssz, goff=goff, gsz=gsz))
        return rows

    def read(self, r):
        def part(suffix, off, sz):
            n = r['archive'] + suffix
            if sz == 0 or n not in self.items: return b''
            return self.item_bytes(n, off, sz)
        return part('', r['moff'], r['msz']), part('.gpu_resources', r['goff'], r['gsz']), part('.stream', r['soff'], r['ssz'])


def load_names(paths):
    names = {}
    for p in paths:
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                s = line.rstrip('\r\n')
                if not s or s.startswith('//'): continue
                names.setdefault(murmur64(s), s)
    return names


def parse_strings(main):
    if len(main) < 16: return None, {}
    magic, ver, cnt = struct.unpack_from('<4sII', main)
    if cnt == 0: return None, {}
    lang = struct.unpack_from('<I', main, 12)[0]
    ids = struct.unpack_from('<%dI' % cnt, main, 16)
    offs = struct.unpack_from('<%dI' % cnt, main, 16 + 4 * cnt)
    out = {}
    for i, o in zip(ids, offs):
        e = main.index(b'\0', o)
        out[i] = main[o:e].decode('utf-8', 'replace')
    return lang, out
