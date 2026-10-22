"""Old <-> new enum value maps, from FileDiver's per-build enum Go files (each value's name length, in value order):
the two length sequences are aligned (difflib); runs that align map one-to-one."""
import os, re, difflib
FD = r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad'


def load(build):
    out = {}
    d = os.path.join(FD, 'fd_' + build, 'datalibrary', 'enum')
    for f in os.listdir(d):
        if f.endswith('_string.go') or not f.endswith('.go'): continue
        src = open(os.path.join(d, f), encoding='utf-8').read()
        m = re.search(r'type (\w+) ', src)
        if not m: continue
        name = m.group(1)
        vals = []
        for line in src.split('const (', 1)[-1].split(')', 1)[0].splitlines():
            line = line.strip()
            if not line.startswith(name + '_'): continue
            mm = re.search(r'_Value_(\d+)_Len_(\d+)', line)
            vals.append(('L%s' % mm.group(2)) if mm else line.split()[0][len(name) + 1:])  # known names compare by name
        out[name] = vals
    return out


def mapping(old, new, min_run=3):
    """new value -> old value for one enum (value = index in the list)."""
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    m = {}
    for a, b, size in sm.get_matching_blocks():
        if size >= min_run or (size and all(not x.startswith('L') for x in old[a:a + size])):
            for i in range(size): m[b + i] = a + i
    return m


if __name__ == '__main__':
    o, n = load('old'), load('new')
    for k in sorted(n):
        if k not in o: print(k, 'NEW ENUM'); continue
        m = mapping(o[k], n[k])
        if len(o[k]) != len(n[k]) or any(a != b for b, a in m.items()):
            print('%-32s old %4d new %4d mapped %4d shifted %4d' % (k, len(o[k]), len(n[k]), len(m), sum(1 for b, a in m.items() if a != b)))
