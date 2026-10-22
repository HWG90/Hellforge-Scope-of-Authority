# Scope of Authority on HellForge

The Scope of Authority warbond (live game 01.007.200, Steam build 25988413) as a HellForge code mod for HellForge's
pinned build 25480438. Installed at `F:\Hellforge\mods\scope-of-authority`; this folder is the source.

## What it adds

| Item | How | Base it is registered on |
|---|---|---|
| R-40 Sightliner | arsenal primary (`add_weapon`) | R-63 Diligence |
| P-44 Mist | arsenal sidearm (`add_weapon`) | P-19 Redeemer |
| AMW-20 Apex + Apex Protector backpack | entities + their live hellpod rack, stratagem ↓←←↑↓← (480 s) | GR-8 Recoilless Rifle, Recoilless Rifle backpack |
| LAS-44 Nova | entity + its live hellpod rack, stratagem ↓←→↓↓ (480 s) | LAS-99 Quasar Cannon |
| G-11 Caltrops | already in the pinned build; one WeaponData flag set to live (`hellforge-stats.json`) | — |

Every entity is registered under its live resource name, so its entity id (and a weapon's loadout id) is the live
game's. The base only decides what HellForge copies first and which archive the live resources are patched into: once
the entity data loads, every component record is overwritten with the live game's own record.

## How "exactly as live" is reached

`tools/gen.py` reads both builds' plaintext data tables (FileDiver's mirrors: commit `2ec8950` is build 25480438,
`HEAD` is 01.007.200; every file is the encrypted game file's size less its 48-byte header) and:

- **Records.** Copies each live component record. All tables but one have the same layout in both builds;
  WeaponDataComponentData gained two members in live and is converted by member alignment.
- **Enum ids.** Translates every enum value into the pinned build's numbering. Live inserted values mid-enum, so the
  same number means different things in each build. The map comes from the name lengths left in each typelib (names
  are stripped, string offsets are not). It is checked against every entity both builds share (656/656 abilities,
  481/481 unique damage rows agree).
- **Projectiles and damage.** The four new projectiles and four new damage types are added (`add_projectile` /
  `add_damage`) as copies of the closest vanilla rows, then overwritten with the live rows.
- **Default attachments.** The live default attachments the pinned build lacks have their entity deltas applied, as the
  game does when it builds the weapon (the Sightliner's short magazine, the Apex's DUO 10x scope, the Nova's ION 4x
  scope). The live attachment models are then fitted.
- **Resources.** Models, animations, state machines, sounds and icons are the live game's. `tools/hellforge-data.json`
  includes every resource new to the pinned build from Steam's install, which HellForge's data builder converts
  (materials re-laid out for the pinned build's shaders). Units, bones, physics, particles and state machines were
  checked to be byte-identical between the builds wherever both have them.

- **Everything else new in live.** Every other resource the live patch added (440, among them 86 streamed sounds, 4 shader
  libraries and the parent materials of two live shaders) is patched into its own archive wherever HellForge's build
  also has that archive. Left out: map content, entity resources and package definitions, which only live code asks for.

HellForge's `component_record` only hands out the 46 components in its entity profile. For the others (Wieldable,
Animation, Equipment, EncyclopediaEntry, EffectReference…), `mod/src/tables.c` finds HellForge's moved copy of each
table in memory. The copy keeps the vanilla index, so two runs of it find the table. The record the entity's index
entry names is its own. Where an arsenal weapon still shares its base's record (`add_weapon` owns only profiled
components), it gets the copy's next free record.

At run time (`mod/src/scope_of_authority.c`) a byte the copy's record holds differently from its base was set by
HellForge (its text, the customization record's mastery package) and is kept. The loadout package also stays the
base's: the live package does not exist in this build, and the base's archive is where the live resources are patched.
Each record written, and each byte kept, is logged in the session's `mod-goose.scope-of-authority.log`.

## Overrides of resources edited in place

`tools/overrides.py` writes the live versions of five resources HellForge's build has under the same names (the data
spec cannot replace those):

- **The Helldiver's animation graphs** (`avatar_helldiver`, `fp_cha_avatar`). Each weapon's WeaponReload record names
  its reload and fast-reload states, and only the live graphs have the live weapons' states. Every animation they
  reference is in the pinned build or the mod.
- **The audio project** (`content/audio/project`, `content/audio/custom` and its switch table). The Wieldable record's
  +12 is the switch value for the weapon's handling sounds.

These replace the vanilla versions for every weapon. That is the live game's behaviour, but it is also the first thing
to take out if something unrelated breaks.

## Why the new abilities are donors, not ports

Both `game.dll`s are encrypted on disk: the pinned build's is packed with WinLicense, and live's `.text` is encrypted and
only decrypted at run time under Easy Anti-Cheat. Reading the live code would mean getting around that protection, so
this mod does not. The new abilities run the vanilla routine closest to what the live data drives instead. Animations
and sounds come from data (above), not from the ability code.

## The Sightliner's bolt

The Sightliner's weapon graph has a `cycle` state that plays its live `cycle_bolt` animation. In live, its fire routine
sends `cycle` after each shot. No routine of this build can stand in: the only two that cycle (the R-2124
Constitution's and the R-6 Deadeye's) feed from WeaponRounds, and the Sightliner is magazine-fed.

So the graph's fire state plays `cycle_bolt` in place of the small fire kick (`tools/overrides.py`: its animation at
+576, 164 bytes after the state's name, checked before it is changed). The game's own fire event then cycles the bolt
on every shot, in third and first person, with no code of the mod's.

This is a trade, not what live does. Live plays the fire clip first, then the cycle. Here the weapon model's own fire
clip (a 456-byte kick) no longer plays; the Helldiver's recoil, the muzzle flash and the shot are unchanged. Keeping both
would need the fire state to go on to `cycle` when its clip ends. The list after each state's clip is not that: it is
the same `fire`/`idle`/`fire_done` mapping in every state. The transitions are in a table at the end of the graph
whose format is not worked out.

The Helldiver's own hand on the bolt is a state in the live Helldiver graphs that live code picks by a name the data
does not carry, so it does not play.

## Deliberately not brought over

The 4 shader libraries new in live, and the 2 live materials (with their parent) that use them, stay out
(`gen.py`, `ALL_NEW_TYPES` and `NEW_SHADER_MATERIALS`). They serve two environment decals, nothing of the warbond's, and
live compiled shaders in the pinned build's renderer are a risk for no gain. This is a deviation from live by choice.

The guard-page crashes of 2026-10-22 ("Guard page (0x80000001)" in nvwgf2umx.dll) were not this mod. All six came
with goose.overlay-host and goose.photo-mode loaded, and every data bisect (builds A to E) faulted at the same driver
address.

## What the pinned build cannot have

- **New ability code.** Abilities that are new in live game code take the vanilla ability of the weapon family each was
  cloned from (found by where it sits in the live enum):
  - Sightliner reload and bolt cycle: the R-2124 Constitution's.
  - Mist reload: the P-19 Redeemer's. Its folding-stock ability has no counterpart, so the stock doesn't fold.
  - Apex reload: the APW-1 AMR's. Apex fire and team reload: the AC-8 Autocannon's.
  - Nova overheat: the LAS-98 Laser Cannon's.
- **Nova surface impact.** The Nova bolt's new surface-impact type (live 273) keeps the Quasar-family value.
- **Attachments.** Attachments that are new in live cannot be added to the pinned build's customization table. They
  come fitted by default, but cannot be swapped back once removed. Simo iron sights and the Simo standard magazine are
  not offered.
- **Apex backblast.** The Apex sits on the Recoilless Rifle, the only vanilla support weapon with the same component
  set, so it carries a Backblast record. Its cone is zeroed.
- **Stratagem icons.** The stratagem icons are the bases' (Recoilless, Quasar); the armory, HUD and map icons are live.
- **Armour, helmets, capes and the Stationary Shroud passive.** None of these are in the mod: HellForge has no way to add
  customization kits, and the passive is new game code.

## Rebuilding

```
py -I tools/index_build.py F:/Hellforge/game/data <scratch>/old.pkl
py -I tools/index_build.py "C:/Program Files (x86)/Steam/steamapps/common/Helldivers 2/data" <scratch>/new.pkl
py -I tools/gen.py          # mod/src/live_data.h, tools/hellforge-data.json, tools/gen.log
sh tools/build_data.sh      # mod/data from Steam's install on C:
```

Paths to the FileDiver mirrors and indexes are in `tools/common.py` and `tools/dlbuild.py`. `build_data.sh` names
Steam's C: install explicitly: HellForge's own lookup picks `D:\SteamLibrary`'s Helldivers 2 (build 24826606), which
lacks these resources. That is also why the data ships prebuilt in `mod/data` instead of as a spec. As a result the mod
contains the game's resources: keep it to yourself.

## Credits

- **[SkyeShade](https://github.com/SkyeShade)**: [HellForge](https://github.com/SkyeShade/HellForge), the offline
  Helldivers 2 platform, its mod SDK and loader, which everything here is built on.
- **Goose (HWG90)**: the port.
- **[FileDiver](https://github.com/xypwn/filediver)**: the plaintext mirrors of both builds' data tables and the
  hash lists the tools read.

## Not in this repository

`mod/data/` (the patch files) and `mod/src/live_data.h` (the live records as C arrays) are built from your own game
files, so they are not committed. To rebuild them, run `tools/index_build.py` for both builds, then `tools/gen.py`, then
`tools/build_data.sh`.
