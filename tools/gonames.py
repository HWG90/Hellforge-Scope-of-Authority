"""Field and enum names for the typelib, read from FileDiver's typelib-generated Go sources (the build's typelib has its
strings stripped). Go fields are laid out with explicit `_` padding for binary.Read, so each field's byte offset is the
running sum of field sizes; a typelib member is named after the Go field at the same offset."""
import os, re

STRUCT = re.compile(r'^type (\w+) struct \{\n(.*?)^\}', re.M | re.S)
FIELD = re.compile(r'^\s*(\w+)\s+((?:\[\d*\])*[\w.*]+)(?:\s+`[^`]*`)?\s*(?://\s*(.*))?$')
ENUM_TYPE = re.compile(r'^type (\w+) (u?int\d+)\s*$', re.M)
CONST = re.compile(r'^const \(\n(.*?)^\)', re.M | re.S)
BASIC = {'uint8': 1, 'int8': 1, 'bool': 1, 'byte': 1, 'uint16': 2, 'int16': 2, 'uint32': 4, 'int32': 4, 'float32': 4,
         'ThinHash': 4, 'DLHash': 4, 'uint64': 8, 'int64': 8, 'float64': 8, 'Hash': 8, 'Vec2': 8, 'Vec3': 12, 'Vec4': 16,
         'Quat': 16, 'Mat3': 36, 'Mat4': 64, 'DLArray': 16, 'DLString': 8, 'DLPtr': 8}
INT = {'uint8': 1, 'int8': 1, 'uint16': 2, 'int16': 2, 'uint32': 4, 'int32': 4, 'uint64': 8, 'int64': 8}


def load(folder):
    structs, enums, enum_sizes = {}, {}, {}
    for root, _, files in os.walk(folder):
        for f in files:
            if not f.endswith('.go'): continue
            src = open(os.path.join(root, f), encoding='utf-8', errors='replace').read()
            for name, body in STRUCT.findall(src):
                fields = []
                for line in body.splitlines():
                    m = FIELD.match(line)
                    emb = re.match(r'^\s*([\w.]+)\s*(?://.*)?$', line)
                    if m: fields.append((m.group(1), m.group(2), (m.group(3) or '').strip()))
                    elif emb: fields.append((emb.group(1).split('.')[-1], emb.group(1), ''))  # embedded field
                    elif line.strip() and not line.strip().startswith('//'): fields.append(('?', '?', ''))
                structs.setdefault(name, fields)
            for etype, base in ENUM_TYPE.findall(src):
                enum_sizes[etype] = INT[base]
                for block in CONST.findall(src):
                    vals, cur, iota = {}, None, False
                    for line in block.splitlines():
                        line = line.split('//')[0].strip()
                        if not line: continue
                        m = re.match(r'(\w+)\s+%s\s*=\s*(.+)$' % etype, line)
                        if m:
                            expr = m.group(2).strip()
                            if 'iota' in expr:
                                iota, cur = True, 0
                                off = re.search(r'iota\s*([+-])\s*(\d+)', expr)
                                if off: cur = int(off.group(2)) * (1 if off.group(1) == '+' else -1)
                            else:
                                try: cur = int(expr, 0)
                                except ValueError: continue
                                iota = False
                            vals[cur] = m.group(1).split('_', 1)[-1]
                        elif iota and re.match(r'^\w+$', line):
                            cur += 1
                            vals[cur] = line.split('_', 1)[-1]
                    if vals and etype not in enums: enums[etype] = vals
    return structs, enums, enum_sizes


def apply(tl, structs, enums, enum_sizes):
    """Rename typelib members (matched by byte offset) and enum values in place. Returns the number of types named."""
    named = set()

    def size_of(gotype):
        n = 1
        for d in re.findall(r'\[(\d+)\]', gotype): n *= int(d)
        base = re.sub(r'^(\[\d*\])*', '', gotype)
        if base.startswith('[]'): return None
        base = base.split('.')[-1].lstrip('*')
        if base in BASIC: return n * BASIC[base]
        if base in enum_sizes: return n * enum_sizes[base]
        tid = tl.by_name.get(base)
        if tid is not None: return n * tl.types[tid]['size']
        if base in structs:
            s = layout(base)
            return n * s[1] if s and s[1] is not None else None
        return None

    def layout(goname):
        offs, at = {}, 0
        for fname, ftype, comment in structs[goname]:
            sz = size_of(ftype) if fname != '?' else None
            if sz is None: return offs, None  # names up to the first field of unknown size are still placed
            if fname != '_': offs[at] = (fname, re.sub(r'^(\[\d*\])*', '', ftype).split('.')[-1].lstrip('*'), comment, sz)
            at += sz
        return offs, at

    def compatible(gotype, m, fsize=0):
        st = m['storage']
        if gotype in ('uint8', 'byte') and fsize > 1 and fsize == m['size']: return True  # opaque byte blob
        if gotype in ('uint64', 'int64') and st in ('STR', 'PTR'): return True  # raw structs keep strings as offsets
        if m['atom'] == 'BITFIELD': return True
        if gotype in ('float32', 'float64'): return st.startswith('FP')
        if gotype in enums or gotype in enum_sizes: return st.startswith('ENUM') or st.startswith('UINT') or st.startswith('INT')
        if gotype in INT or gotype in ('ThinHash', 'Hash', 'DLHash', 'bool', 'byte'): return st.startswith(('UINT', 'INT', 'ENUM'))
        if gotype in ('Vec2', 'Vec3', 'Vec4', 'Quat', 'Mat3', 'Mat4'): return st in ('STRUCT', 'FP32')
        if gotype in ('DLArray', 'DLString', 'DLPtr'): return m['atom'] == 'ARRAY' or st in ('STR', 'PTR')
        return st in ('STRUCT', 'PTR')

    def name_type(tid, goname):
        if tid in named or tid not in tl.types: return
        t = tl.types[tid]
        # FileDiver keeps the on-disk layout of some settings records in raw<Name> and a resolved form in <Name>.
        g = next((n for n in ('raw' + t['name'], goname, t['name']) if n in structs), None)
        if not g: return
        lay = layout(g)
        if not lay: return
        offs, total = lay
        named.add(tid)
        bitcount = {}
        for m in t['members']:
            hit = offs.get(m['offset'])
            if not hit: continue
            fname, ftype, comment, fsize = hit
            # Once a Go field disagrees in kind with the typelib member at its offset, the Go struct has drifted from this
            # build's layout; leave this and every later member with its raw name rather than mislabel it.
            if not compatible(ftype, m, fsize):
                break
            # One typelib inline array can be several scalar Go fields (Damage, DurableDamage): join their names.
            at, parts = m['offset'] + fsize, [fname]
            while fsize < m['size'] and at in offs and m['atom'] == 'INLINE_ARRAY':
                parts.append(offs[at][0]); fsize += offs[at][3]; at += offs[at][3]
            fname = '/'.join(parts)
            if m['atom'] == 'BITFIELD':
                # Bits packed into one Go byte type: FileDiver lists their names in <Type>Struct, lowest bit first.
                bits = [f[0] for f in structs.get(ftype + 'Struct', []) if f[0] not in ('_', '?')]
                k = bitcount.get(m['offset'], 0); bitcount[m['offset']] = k + 1
                if k < len(bits): fname = bits[k]
            m['name'] = fname
            if comment: m['comment'] = comment
            if m['storage'] in ('STRUCT', 'PTR'): name_type(m['type_id'], ftype)
            if m['storage'].startswith('ENUM') and m['type_id'] in tl.enums and ftype in enums:
                tl.enums[m['type_id']]['values'] = {**tl.enums[m['type_id']]['values'], **enums[ftype]}

    for tid, t in list(tl.types.items()):
        if t['name'].startswith('CApiVector'):
            for m, axis in zip(t['members'], 'xyzw'): m['name'] = axis
        name_type(tid, t['name'])
    for tid, e in tl.enums.items():
        if e['name'] in enums: e['values'] = {**e['values'], **enums[e['name']]}
    return len(named)
