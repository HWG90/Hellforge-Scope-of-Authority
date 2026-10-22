/* Finding records HellForge's component_record does not hand out (tables.c). */
#pragma once
#include <stdint.h>
#include "hellforge_mod.h"
#include "live_types.h"

/* Finds HellForge's copies of the tables (the ones indexing one of `entities`), once per entity-data load, in the
 * allocations holding the records component_record handed out (`hints`) and nowhere else. */
void FindTables(HfMod* mod, const LiveTable* const* tables, int count, const uint64_t* entities, int entityCount,
    const uintptr_t* hints, int hintCount);
/* The entity's own record in a table's copy, or NULL (the mod's log says why). With claim, an entity that shares its
 * base's record is given one of its own first. */
uint8_t* FindRecord(HfMod* mod, const LiveTable* t, uint64_t entity, uint64_t base, uint32_t base_index, int claim);
