/* Records HellForge gives an entity but its component_record does not hand out (components outside its entity profile:
 * Wieldable, Animation, Equipment, EncyclopediaEntry, EffectReference...).
 *
 * When an added entity owns a record in a component, HellForge's loader copies that component's table to memory of its
 * own (modloader.log: "registry: component N copied (S slots, R-byte records, new records from V)"): the vanilla index
 * (S entries of {resource u64, record index u32, padding}) at the copy's start, the vanilla records at the vanilla record
 * offset, then room for new records up to S. So a copy is found by two runs of the vanilla index (live_data.h, LiveTable)
 * in a table that also indexes the entity; its record is the one its entry names.
 *
 * An arsenal weapon (add_weapon) owns records only in the profiled components; in the others its entry names its base's
 * record. It is given one here: the next free record of the copy, a copy of the base's, and its entry points at it. */
#include <windows.h>
#include <string.h>
#include "hellforge_mod.h"
#include "live_types.h"
#include "tables.h"

#define MAX_TABLES 64
#define MAX_HITS 4

typedef struct Hits
{
    const LiveTable* table;
    uint8_t* at[MAX_HITS];     /* HellForge's copies of the table that index one of the mod's entities */
    int count;
} Hits;

static Hits g_hits[MAX_TABLES];
static int g_tables;

/* The windows' first words, for a one-probe test at every 16 bytes scanned (open addressing, 0 = empty). */
#define PROBES 512
static struct { uint64_t head; int16_t table, window; } g_probe[PROBES];
static const uint64_t* g_entities;
static int g_entityCount, g_found;
static unsigned long long g_scanned, g_regions;

static Hits* HitsOf(const LiveTable* t)
{
    for (int i = 0; i < g_tables; i++) if (g_hits[i].table == t) return &g_hits[i];
    if (g_tables == MAX_TABLES) return NULL;
    g_hits[g_tables].table = t;
    g_hits[g_tables].count = 0;
    return &g_hits[g_tables++];
}

/* Plain read-write memory only, its protection exactly PAGE_READWRITE: never guard pages, write-combined or uncached
 * memory (Direct3D 12 maps upload buffers write-combined, 0x404). The first version read any page with the read-write
 * bit, write-combined ones too, and the renderer then failed ("Guard page (0x80000001)", 2026-10-22, every time the
 * scan crossed them). */
static int Readable(const MEMORY_BASIC_INFORMATION* m)
{
    return m->State == MEM_COMMIT && m->Type == MEM_PRIVATE && m->Protect == PAGE_READWRITE;
}

/* A table at `start` is one of HellForge's copies when its index has an entry for one of the mod's entities (the vanilla
 * table, if it is still there, has none). Read through ReadProcessMemory: a wrong candidate may point anywhere. */
static int IndexesOurs(const LiveTable* t, const uint8_t* start)
{
    static uint8_t index[16 * 8192];
    SIZE_T size = (SIZE_T)t->slots * 16, got = 0;
    if (size > sizeof index || !ReadProcessMemory(GetCurrentProcess(), start, index, size, &got) || got != size) return 0;
    for (uint32_t i = 0; i < t->slots; i++)
        for (int e = 0; e < g_entityCount; e++)
            if (*(uint64_t*)(index + 16 * i) == g_entities[e]) return 1;
    return 0;
}

/* Scans [from, to) for the tables' windows, a megabyte at a time through ReadProcessMemory (memory the game frees
 * meanwhile fails the read instead of faulting), until every table has a copy. */
static void Scan(uintptr_t from, uintptr_t to, const LiveTable* const* tables, int count)
{
    static uint8_t buffer[1 << 20];
    MEMORY_BASIC_INFORMATION m;
    for (uintptr_t at = from; at < to && g_found < count && VirtualQuery((void*)at, &m, sizeof m) == sizeof m;
         at = (uintptr_t)m.BaseAddress + m.RegionSize)
    {
        if (!Readable(&m)) continue;
        g_regions++;
        uintptr_t end = (uintptr_t)m.BaseAddress + m.RegionSize;
        for (uintptr_t chunk = (uintptr_t)m.BaseAddress; chunk < end && g_found < count; chunk += sizeof buffer - 32)
        {
            SIZE_T want = end - chunk < sizeof buffer ? end - chunk : sizeof buffer, got = 0;
            if (!ReadProcessMemory(GetCurrentProcess(), (void*)chunk, buffer, want, &got) || got < 32) continue;
            g_scanned += got;
            for (SIZE_T i = 0; i + 32 <= got; i += 16)
            {
                uint64_t head = *(uint64_t*)(buffer + i);
                if (head == 0) continue;
                for (uint32_t p = (uint32_t)(head ^ head >> 29) % PROBES; g_probe[p].head; p = (p + 1) % PROBES)
                {
                    if (g_probe[p].head != head) continue;
                    const LiveTable* t = tables[g_probe[p].table];
                    if (memcmp(buffer + i, t->window[g_probe[p].window], 32) != 0) continue;
                    Hits* h = HitsOf(t);
                    uint8_t* start = (uint8_t*)(chunk + i) - t->window_at[g_probe[p].window];
                    int seen = 0;
                    for (int k = 0; h && k < h->count; k++) seen |= h->at[k] == start;
                    if (!h || seen || h->count == MAX_HITS || !IndexesOurs(t, start)) continue;
                    if (h->count++ == 0) g_found++;
                    h->at[h->count - 1] = start;
                }
            }
        }
    }
}

/* HellForge's copies are its own allocations, like the profiled tables' copies whose records component_record hands
 * out (`hints`): those allocations are read first, then the process's other plain read-write memory if a copy is
 * still missing. */
void FindTables(HfMod* mod, const LiveTable* const* tables, int count, const uint64_t* entities, int entityCount,
    const uintptr_t* hints, int hintCount)
{
    const HfApi* hf = HF_API(mod);
    ULONGLONG began = GetTickCount64();
    g_tables = 0; g_found = 0; g_scanned = 0; g_regions = 0;
    g_entities = entities; g_entityCount = entityCount;
    memset(g_probe, 0, sizeof g_probe);
    for (int t = 0; t < count; t++)
    {
        HitsOf(tables[t]);
        for (int w = 0; w < 2; w++)
        {
            uint64_t head = *(const uint64_t*)tables[t]->window[w];
            uint32_t p = (uint32_t)(head ^ head >> 29) % PROBES;
            while (g_probe[p].head) p = (p + 1) % PROBES;
            g_probe[p].head = head; g_probe[p].table = (int16_t)t; g_probe[p].window = (int16_t)w;
        }
    }
    void* bases[64];
    int allocations = 0;
    for (int h = 0; h < hintCount && g_found < count; h++)
    {
        MEMORY_BASIC_INFORMATION m;
        if (VirtualQuery((void*)hints[h], &m, sizeof m) != sizeof m) continue;
        int seen = 0;
        for (int b = 0; b < allocations; b++) seen |= bases[b] == m.AllocationBase;
        if (seen || allocations == 64) continue;
        bases[allocations++] = m.AllocationBase;
        /* the allocation: its regions from its base, as long as they belong to it */
        uintptr_t from = (uintptr_t)m.AllocationBase, to = from;
        while (VirtualQuery((void*)to, &m, sizeof m) == sizeof m && m.AllocationBase == bases[allocations - 1])
            to = (uintptr_t)m.BaseAddress + m.RegionSize;
        Scan(from, to, tables, count);
    }
    if (g_found < count) Scan(0x10000, (uintptr_t)0x7FFFFFFFFFFFull, tables, count);
    for (int t = 0; t < count; t++)
    {
        Hits* h = HitsOf(tables[t]);
        if (!h || h->count != 1) hf->log(mod, "tables: %s: %d copies found (one expected)", tables[t]->component, h ? h->count : 0);
    }
    hf->log(mod, "tables: %d of %d found in %llu ms (%llu MB in %llu regions of %d allocation(s) read)", g_found, count,
        (unsigned long long)(GetTickCount64() - began), g_scanned >> 20, g_regions, allocations);
}

static int64_t Entry(const LiveTable* t, uint8_t* table, uint64_t resource)
{
    for (uint32_t i = 0; i < t->slots; i++) if (*(uint64_t*)(table + 16 * i) == resource) return i;
    return -1;
}

uint8_t* FindRecord(HfMod* mod, const LiveTable* t, uint64_t entity, uint64_t base, uint32_t base_index, int claim)
{
    const HfApi* hf = HF_API(mod);
    Hits* h = HitsOf(t);
    for (int k = 0; h && k < h->count; k++)
    {
        uint8_t* table = h->at[k];
        int64_t mine = Entry(t, table, entity);
        if (mine < 0) continue;                                    /* a copy indexing another of the mod's entities */
        int64_t theirs = Entry(t, table, base);
        uint32_t* index = (uint32_t*)(table + 16 * mine + 8);
        if (theirs < 0 || *(uint32_t*)(table + 16 * theirs + 8) != base_index)
        {
            hf->log(mod, "tables: %s at %p indexes the entity but not its base as the vanilla data does; left alone", t->component, (void*)table);
            return NULL;
        }
        if (*index >= t->slots) { hf->log(mod, "tables: %s: record %u is past the copy's room", t->component, *index); return NULL; }
        if (*index == base_index)
        {
            if (!claim) { hf->log(mod, "tables: %s: the entity shares its base's record; left alone", t->component); return NULL; }
            uint32_t next = t->records;
            for (uint32_t i = 0; i < t->slots; i++)
                if (*(uint64_t*)(table + 16 * i) && *(uint32_t*)(table + 16 * i + 8) >= next) next = *(uint32_t*)(table + 16 * i + 8) + 1;
            if (next >= t->slots) { hf->log(mod, "tables: %s has no free record for it", t->component); return NULL; }
            uint8_t* records = table + t->record_offset;
            /* a free record of the copy's room is untouched memory: anything else is not one (and not ours to take) */
            for (uint32_t b = 0; b < t->stride; b++)
                if (records[(size_t)t->stride * next + b]) { hf->log(mod, "tables: %s: record %u is not empty; left alone", t->component, next); return NULL; }
            memcpy(records + (size_t)t->stride * next, records + (size_t)t->stride * base_index, t->stride);
            *index = next;
            hf->log(mod, "tables: %s: record %u of its own (a copy of its base's %u)", t->component, next, base_index);
        }
        return table + t->record_offset + (size_t)t->stride * *index;
    }
    hf->log(mod, "tables: %s: no copy of the table indexes the entity", t->component);
    return NULL;
}
