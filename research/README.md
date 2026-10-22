Groundwork for running the live game's new abilities natively (the Sightliner fire and reload, the Mist's folding
stock, the Apex's team reload, the Nova's overheat), rather than with vanilla donors.

`loader_abilities.asm` is a disassembly of HellForge's `hellforge_modloader.dll` (engine 0.1.24, `app/sdk-shims`).
That DLL is not packed, unlike the game's. It contains:

- **0x0d420-0x19add**: ability installation. It checks the game's tick dispatcher (game.dll 0x11509E0 per
  docs/mods.md) against the reviewed bytes ("a base ability's case is not the reviewed shape"), points the default
  branch at HellForge's stub, and registers the stub's unwind data.
- **around 0x4565e**: the run-time side, which sets a HellForge ability off on an entity, holds it, then calls its
  base ("abilities: %u set off on entity %u (its base %u runs in %u ticks)").

Still to read from the pinned build in memory (one diagnostic run): the dispatcher's prologue (how a case receives
the entity and tick), and the engine function behind the Lua `Unit.animation_event` binding. Dump only the build
HellForge runs, never the live Steam install (its code is only decrypted under Easy Anti-Cheat).
