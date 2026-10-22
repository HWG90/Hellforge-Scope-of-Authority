"""Parse generated_customization_armor_sets.dl_bin (plaintext, FileDiver mirror) after FileDiver's armor_sets.go."""
import sys, os, struct, json, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd2nxa import murmur64

SLOTS = ['helmet', 'cape', 'torso', 'hips', 'left_leg', 'right_leg', 'left_arm', 'right_arm', 'left_shoulder', 'right_shoulder']
PTYPE = ['armor', 'undergarment', 'accessory']
WEIGHT = ['light', 'medium', 'heavy']
BODY = ['stocky', 'slim', 'unknown', 'any']
KIT = ['Armor', 'Helmet', 'Cape']
RARITY = ['Common', 'Uncommon', 'Heroic']
CAMO = ['none', 'default', 'forest', 'desert', 'arctic', 'crimson']
PIECE_HASHES = ['material_lut', 'pattern_lut', 'cape_lut', 'cape_gradient', 'cape_nac', 'decal_scalar_fields', 'base_data', 'decal_sheet']


def load(path):
    b = open(path, 'rb').read()
    count = struct.unpack_from('<I', b)[0]
    at = 4
    kits = []
    for _ in range(count):
        magic, ver, typ, size = struct.unpack_from('<4sIII', b, at)
        assert magic == b'LDLD'
        base = at + 24
        (kid, dlc, setid, nup, ncase, desc, rar, passive) = struct.unpack_from('<8I', b, base)
        archive, ktype, _, baddr, bcount = struct.unpack_from('<QIIqq', b, base + 32)
        bodies = []
        for i in range(bcount):
            btype, _, paddr, pcount = struct.unpack_from('<IIqq', b, base + baddr + 24 * i)
            pieces = []
            for p in range(pcount):
                # 01.007.200 layout: 112-byte pieces ending in a DLArray of CamouflagePiece {type u32, pad, material_lut u64}.
                o = base + paddr + 112 * p
                path, slot, pt, w, _ = struct.unpack_from('<QIIII', b, o)
                hs = struct.unpack_from('<8Q', b, o + 24)
                tone = b[o + 88]
                caddr, ccount = struct.unpack_from('<qq', b, o + 96)
                camo = []
                for c in range(ccount):
                    ct, _, lut = struct.unpack_from('<IIQ', b, base + caddr + 16 * c)
                    camo.append(dict(camouflage=CAMO[ct] if ct < len(CAMO) else ct, material_lut=lut))
                pieces.append(dict(unit=path, slot=SLOTS[slot] if slot < 10 else slot, type=PTYPE[pt] if pt < 3 else pt,
                                   weight=WEIGHT[w] if w < 3 else w, tone_variations=tone, **dict(zip(PIECE_HASHES, hs)),
                                   camouflage_pieces=camo))
            bodies.append(dict(body=BODY[btype] if btype < 4 else btype, pieces=pieces))
        kits.append(dict(id=kid, dlc_id=dlc, set_id=setid, name_upper=nup, name_cased=ncase, description=desc,
                         rarity=RARITY[rar] if rar < 3 else rar, passive=passive, archive=archive,
                         kit_type=KIT[ktype] if ktype < 3 else ktype, bodies=bodies))
        at = base + size
    return kits


if __name__ == '__main__':
    kits = load(sys.argv[1])
    strings = {int(k): v[0] for k, v in json.load(open(sys.argv[2], encoding='utf-8')).items()}
    print('kits', len(kits))
    targets = [k for k in kits if strings.get(k['name_cased'], '') in
               ('SS-33 Mimetic Marshal', 'SS-15 Focal Point', 'Mimetic Mesh', 'Boundary Banner')]
    sets = {(k['set_id'], k['dlc_id']) for k in targets}
    print('target set/dlc ids', sets)
    for k in kits:
        if (k['set_id'], k['dlc_id']) in sets or k in targets:
            print('%-6s %-28s set=%08x dlc=%08x archive=%016x rarity=%s passive=%08x pieces=%d' % (
                k['kit_type'], strings.get(k['name_cased'], hex(k['name_cased'])), k['set_id'], k['dlc_id'], k['archive'],
                k['rarity'], k['passive'], sum(len(b['pieces']) for b in k['bodies'])))
