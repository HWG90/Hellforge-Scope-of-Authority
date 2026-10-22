import pickle
from dltypes import dlsum
S = r'C:/Users/david/AppData/Local/Temp/claude/C--Users-david--claude-spares-spare-IDJZwx/da3f2fd5-a21e-4afd-bd0b-a7f4f681ac85/scratchpad'
TYPE_NAMES = {dlsum(l.strip()): l.strip() for l in open(S + '/fd_new/hashes/dl_type_names.txt', encoding='utf-8') if l.strip()}
E = 'content/fac_helldivers/equipment/'
ENTS = {'sightliner': E + 'primary_weapons/bolt_action_rifle_simo/sniper_rifle_simo', 'mist': E + 'sidearm_weapons/machine_pistol_bull/machine_pistol_bull',
        'apex': E + 'support_weapons/sniper_rifle_duo/sniper_rifle_duo', 'apex_pack': E + 'backpacks/sniper_rifle_duo_backpack/sniper_rifle_duo_backpack',
        'nova': E + 'support_weapons/laser_rifle_ion/laser_rifle_ion', 'caltrops': E + 'throwables/caltrops_grenade/caltrops_grenade',
        'caltrops_mine': E + 'throwables/caltrops_grenade/caltrops_mine'}
