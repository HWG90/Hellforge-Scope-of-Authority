/* One-time research dump (diagnostic build): the pinned build's code this mod needs to run the live game's new
 * abilities natively. The game's executables are packed on disk, so their code can only be read once loaded.
 *
 *   the ability tick dispatcher   game.dll 0x11509E0 (docs/mods.md), 16 KB around it: its prologue (what a case
 *                                 receives) and its switch
 *   animation_event               every module's "animation_event" string, the code that references it (the Lua
 *                                 binding's registration), and the code each nearby reference points at (the binding,
 *                                 and the engine function it wraps)
 *
 * Only plain read-only or executable pages of the two game modules are read (never guard, write or no-access pages:
 * the packer guards some), through ReadProcessMemory. Written to the session's logs folder as goose-soa-code.bin:
 * records of {u32 tag, u32 length, u64 address (module-relative), u64 module base, bytes}. Tags: 1 dispatcher,
 * 2 string, 3 reference site, 4 reference target. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "hellforge_mod.h"
#include "diag.h"

#define DISPATCHER_RVA 0x11509E0u

static FILE* g_out;
static int g_records;

static int Plain(const void* at)
{
    MEMORY_BASIC_INFORMATION m;
    if (VirtualQuery(at, &m, sizeof m) != sizeof m || m.State != MEM_COMMIT || m.Type != MEM_IMAGE) return 0;
    DWORD p = m.Protect;
    if (p & (PAGE_GUARD | PAGE_NOACCESS)) return 0;
    return p == PAGE_READONLY || p == PAGE_EXECUTE_READ || p == PAGE_EXECUTE;
}

/* Copies [at, at+size) of a module, page by page, only where every page is plain; returns the bytes read. */
static size_t Read(uintptr_t at, void* into, size_t size)
{
    size_t done = 0;
    while (done < size)
    {
        uintptr_t page = (at + done) & ~(uintptr_t)0xFFF;
        size_t chunk = page + 0x1000 - (at + done);
        if (chunk > size - done) chunk = size - done;
        SIZE_T got = 0;
        if (!Plain((void*)(at + done)) || !ReadProcessMemory(GetCurrentProcess(), (void*)(at + done), (uint8_t*)into + done, chunk, &got) || got != chunk) break;
        done += chunk;
    }
    return done;
}

static void Record(uint32_t tag, uintptr_t base, uintptr_t at, size_t size)
{
    static uint8_t buffer[1 << 16];
    if (size > sizeof buffer) size = sizeof buffer;
    size_t got = Read(at, buffer, size);
    if (!got) return;
    uint32_t head[2] = {tag, (uint32_t)got};
    uint64_t where[2] = {(uint64_t)(at - base), (uint64_t)base};
    fwrite(head, sizeof head, 1, g_out); fwrite(where, sizeof where, 1, g_out); fwrite(buffer, 1, got, g_out);
    g_records++;
}

/* The module's plain pages, scanned for a string and then for the RIP-relative references to where it was found. */
static void FindReferences(HfMod* mod, const char* module, const char* text)
{
    size_t size = 0;
    uintptr_t base = HF_API(mod)->module_base(module, &size);
    if (!base) return;
    static uint8_t page[0x1000 + 64];
    size_t n = strlen(text) + 1;
    uintptr_t strings[8]; int found = 0;
    for (uintptr_t at = base; at < base + size && found < 8; at += 0x1000)
    {
        size_t got = Read(at, page, 0x1000 + 64 < base + size - at ? 0x1000 + 64 : base + size - at);
        for (size_t i = 0; i + n <= got && i < 0x1000; i++)
            if (memcmp(page + i, text, n) == 0 && (i == 0 || page[i - 1] == 0) && found < 8) { strings[found++] = at + i; Record(2, base, at + i, 64); }
    }
    int sites = 0;
    for (uintptr_t at = base; at < base + size && found && sites < 32; at += 0x1000)
    {
        size_t got = Read(at, page, 0x1000 + 16 < base + size - at ? 0x1000 + 16 : base + size - at);
        for (size_t i = 0; i + 7 <= got && i < 0x1000 && sites < 32; i++)
        {
            /* lea r64, [rip + disp32]: 48/4C 8D modrm(mod 00, rm 101) */
            if ((page[i] != 0x48 && page[i] != 0x4C) || page[i + 1] != 0x8D || (page[i + 2] & 0xC7) != 0x05) continue;
            uintptr_t target = at + i + 7 + *(int32_t*)(page + i + 3);
            int hit = 0;
            for (int s = 0; s < found; s++) hit |= target == strings[s];
            if (!hit) continue;
            uintptr_t site = at + i;
            Record(3, base, site - 0x200, 0x400);
            sites++;
            /* the code that nearby references point at: the binding the name is registered with, and what it calls */
            static uint8_t around[0x400];
            size_t ng = Read(site - 0x200, around, sizeof around);
            for (size_t k = 0; k + 7 <= ng; k++)
                if ((around[k] == 0x48 || around[k] == 0x4C) && around[k + 1] == 0x8D && (around[k + 2] & 0xC7) == 0x05)
                {
                    uintptr_t t = site - 0x200 + k + 7 + *(int32_t*)(around + k + 3);
                    if (t >= base && t < base + size && t != target) Record(4, base, t, 0x800);
                }
        }
    }
    HF_API(mod)->log(mod, "diag: %s: %d \"%s\" string(s), %d reference site(s)", module, found, text, sites);
}

static void Dump(HfMod* mod, HfEvent event, void* user)
{
    const HfApi* hf = HF_API(mod);
    char path[1024];
    snprintf(path, sizeof path, "%s/goose-soa-code.bin", hf->logs_folder(mod));
    g_out = fopen(path, "wb");
    if (!g_out) { hf->log(mod, "diag: %s could not be written", path); return; }
    size_t size = 0;
    uintptr_t game = hf->module_base("game.dll", &size);
    if (game) Record(1, game, game + DISPATCHER_RVA - 0x1000, 0x4000);
    FindReferences(mod, "helldivers2.exe", "animation_event");
    FindReferences(mod, "game.dll", "animation_event");
    fclose(g_out);
    hf->log(mod, "diag: %d record(s) in %s", g_records, path);
}

void DiagInit(const HfApi* hf, HfMod* mod)
{
    hf->on(mod, HF_EVENT_GAME_LOADED, Dump, NULL);
}
