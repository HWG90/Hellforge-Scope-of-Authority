/* tables.c without the game: a HellForge-style copy of the Wieldable table (the vanilla index windows from live_data.h,
 * the records at the vanilla offset, room for `slots` records) planted in this process's heap, found, then claimed. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <windows.h>
#include "hellforge_mod.h"
#include "../mod/src/live_data.h"
#include "../mod/src/tables.h"

static char last[512];
static void Log(HfMod* mod, const char* f, ...) { va_list a; va_start(a, f); vsnprintf(last, sizeof last, f, a); va_end(a); printf("  log: %s\n", last); }
static HfApi api;
struct HfMod { const HfApi* api; };

int main(void)
{
    api.log = Log;
    struct HfMod mod = {&api};
    const LiveTable* t = &table_WieldableComponentData;
    size_t size = t->record_offset + (size_t)t->stride * t->slots;
    /* ballast so the scan has real memory to cross */
    static void* volatile ballast[128];
    for (int i = 0; i < 128; i++) { ballast[i] = VirtualAlloc(NULL, 8 << 20, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE); memset(ballast[i], i + 1, 8 << 20); }
    uint8_t* copy = calloc(1, size);
    for (int w = 0; w < 2; w++) memcpy(copy + t->window_at[w], t->window[w], 32);
    uint64_t base = 0x03E67A19B07C6523ull, ours = 0x41F2DEF484634B59ull;
    uint32_t baseIndex = 440;
    /* entries away from the windows: the base's (to its vanilla record) and ours, sharing it as add_weapon leaves it */
    uint32_t free1 = t->slots - 3, free2 = t->slots - 5;
    memcpy(copy + 16 * free1, &base, 8); memcpy(copy + 16 * free1 + 8, &baseIndex, 4);
    memcpy(copy + 16 * free2, &ours, 8); memcpy(copy + 16 * free2 + 8, &baseIndex, 4);
    memset(copy + t->record_offset + (size_t)t->stride * baseIndex, 0x5A, t->stride);
    const LiveTable* tables[] = {t, &table_AnimationComponentData};
    uint64_t entities[] = {ours};
    uintptr_t hint = (uintptr_t)copy; FindTables(&mod, tables, getenv("NOHINT") ? 2 : 1, entities, 1, &hint, getenv("NOHINT") ? 0 : 1);
    int fails = 0;
    uint8_t* rec = FindRecord(&mod, t, ours, base, baseIndex, 1);
    uint32_t claimed = *(uint32_t*)(copy + 16 * free2 + 8);
    if (rec == NULL || claimed == baseIndex || rec != copy + t->record_offset + (size_t)t->stride * claimed || rec[0] != 0x5A) { puts("FAIL claim"); fails++; } else printf("PASS claimed record %u, a copy of the base's\n", claimed);
    if (FindRecord(&mod, t, ours, base, baseIndex, 1) != rec) { puts("FAIL second lookup gives another record"); fails++; } else puts("PASS a second lookup gives the same record");
    /* a non-empty "free" record is refused */
    *(uint32_t*)(copy + 16 * free2 + 8) = baseIndex;
    memset(copy + t->record_offset + (size_t)t->stride * (claimed + 1), 1, 1);
    memset(copy + t->record_offset + (size_t)t->stride * claimed, 0, t->stride);
    memset(copy + t->record_offset + (size_t)t->stride * claimed, 7, 1);
    if (FindRecord(&mod, t, ours, base, baseIndex, 1) != NULL) { puts("FAIL took a record that is not empty"); fails++; } else puts("PASS a record that is not empty is left alone");
    printf("%d failure(s)\n", fails);
    return fails;
}
