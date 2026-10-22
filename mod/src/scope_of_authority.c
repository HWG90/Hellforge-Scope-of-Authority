/* Scope of Authority (goose.scope-of-authority): the 01.007.200 warbond's weapons on HellForge's pinned build 25480438,
 * built from the live game's own data rather than approximated.
 *
 *   R-40 Sightliner, P-44 Mist  arsenal weapons (add_weapon) under their live names, so their entities and loadout ids
 *                               are the live game's; bases R-63 Diligence and P-19 Redeemer (the same component set).
 *   AMW-20 Apex (+ backpack)    support weapons: entities (register_entity, own_all) delivered by copies of their live
 *   LAS-44 Nova                 hellpod racks, called in by stratagems with the live codes and cooldowns.
 *
 * Every component record of every entity is the live game's record (tools/gen.py: converted to this build's layouts and
 * enum numbers; live_data.h), written over the copy once the entity data has loaded. What HellForge set in a record
 * (text, the customization record's mastery package, the loadout package its data patches) stays. Projectiles and
 * damage the live weapons use that this build lacks are added as copies of the closest vanilla rows and overwritten
 * with the live rows. Models, animations, sounds and icons are the live game's resources, built from Steam's install
 * (hellforge-data.json, "source": "steam") into the archives of each weapon's base.
 *
 * What the pinned build cannot run is said in the log and in README.md: abilities new in the live game's code (reload,
 * fire and overheat routines) take the closest vanilla weapon's, and attachments new to the live game (the Sightliner's
 * short magazine, the Apex's and Nova's scopes) come fitted as the live game fits them by default but cannot be swapped. */
#include <stdio.h>
#include <string.h>
#include "hellforge_mod.h"
#include "live_data.h"
#include "tables.h"
#include "diag.h"

#define SUPPORT_HELLPOD 0x73F8498BFFDCF415ull /* the hellpod support weapons come down in (stratagem payload[1]) */

static uint32_t g_damage[LIVE_DAMAGE_COUNT];          /* the ids HellForge gave the copies of live_damage */
static uint32_t g_projectile[LIVE_PROJECTILE_COUNT];  /* the types HellForge gave the copies of live_projectiles */
static char g_names[LIVE_DAMAGE_COUNT + LIVE_PROJECTILE_COUNT][96];

static uint32_t Resolve(const LiveFix* fix)
{
    return fix->kind == LIVE_FIX_PROJECTILE ? g_projectile[fix->index] : g_damage[fix->index];
}

/* Crash bisect (bisect.txt in the mod's folder, one word per line, read once): `noscan` writes only the records
 * component_record hands out (no table search, no claimed records); a component name leaves that component as HellForge
 * made it. Each skip is logged. */
static char g_bisect[4096];
static int g_noscan;

static void ReadBisect(const HfApi* hf, HfMod* mod)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/bisect.txt", hf->mod_folder(mod));
    FILE* f = fopen(path, "rb");
    if (!f) return;
    size_t n = fread(g_bisect + 1, 1, sizeof g_bisect - 3, f);
    fclose(f);
    g_bisect[0] = '\n'; g_bisect[n + 1] = '\n';
    for (size_t i = 0; i < n + 2; i++) if (g_bisect[i] == '\r' || g_bisect[i] == ' ' || g_bisect[i] == '\t') g_bisect[i] = '\n';
    g_noscan = strstr(g_bisect, "\nnoscan\n") != NULL;
    hf->log(mod, "bisect: %s", g_noscan ? "noscan (only the records component_record hands out)" : "components listed in bisect.txt are skipped");
}

static int Skipped(const char* component)
{
    char word[96];
    snprintf(word, sizeof word, "\n%s\n", component);
    return g_bisect[0] && strstr(g_bisect, word) != NULL;
}

static int Kept(const LiveKeep* keep, uint32_t at)
{
    for (; keep->length; keep++) if (at >= keep->offset && at < keep->offset + keep->length) return 1;
    return 0;
}

/* Writes an entity's live records over its own copies. Runs at every entity-data load (HellForge has redone its own
 * edits by then); a record already written reads as HellForge's and is left as it is, so it is safe to repeat. */
static void WriteEntity(HfMod* mod, LiveEntity* e)
{
    const HfApi* hf = HF_API(mod);
    int written = 0, skipped = 0;
    for (const LiveRecord* r = e->records; r->component; r++)
    {
        uint32_t stride = 0;
        if (Skipped(r->component)) { hf->log(mod, "%s: %s skipped (bisect.txt)", e->key, r->component); skipped++; continue; }
        uint8_t* rec = (uint8_t*)hf->component_record(r->component, e->entity, &stride);
        if (rec == NULL && g_noscan) { hf->log(mod, "%s: %s skipped (bisect: noscan)", e->key, r->component); skipped++; continue; }
        if (rec == NULL)
        {
            /* outside HellForge's profile: its copy of the table, found in memory (tables.c) */
            rec = FindRecord(mod, r->table, e->entity, e->base, r->base_index, 1);
            stride = r->table->stride;
        }
        if (rec == NULL || stride != r->size)
        {
            hf->log(mod, "%s: %s not written (%s, record size %u, expected %u): it stays the base's", e->key, r->component,
                rec == NULL ? "no record of its own" : "another layout", stride, r->size);
            skipped++;
            continue;
        }
        uint32_t kept = 0, changed = 0;
        for (uint32_t i = 0; i < r->size; i++)
        {
            if (rec[i] != r->base[i] || Kept(r->keep, i)) { kept += rec[i] != r->live[i]; continue; }
            if (rec[i] != r->live[i]) { rec[i] = r->live[i]; changed++; }
        }
        for (const LiveFix* f = r->fixes; f->kind; f++) memcpy(rec + f->offset, &(uint32_t){Resolve(f)}, 4);
        hf->log(mod, "%s: %s written (%u bytes live, %u kept as HellForge set them)", e->key, r->component, changed, kept);
        written++;
    }
    hf->log(mod, "%s (%016llx): %d records live, %d the base's", e->key, (unsigned long long)e->entity, written, skipped);
}

static void EntitiesReady(HfMod* mod, HfEvent event, void* user)
{
    const HfApi* hf = HF_API(mod);
    /* the tables component_record does not hand out, found once per load */
    static const LiveTable* wanted[64];
    int count = 0;
    uintptr_t hints[64];
    int hintCount = 0;
    for (int i = 0; i < LIVE_ENTITY_COUNT; i++)
    {
        LiveEntity* e = &live_entities[i];
        if (e->base_item) e->entity = hf->weapon_entity(e->item);
        if (!e->entity) continue;
        for (const LiveRecord* r = e->records; r->component; r++)
        {
            uint32_t stride;
            uintptr_t at = hf->component_record(r->component, e->entity, &stride);
            if (at) { if (hintCount < 64) hints[hintCount++] = at; continue; }
            int seen = 0;
            for (int k = 0; k < count; k++) seen |= wanted[k] == r->table;
            if (!seen && count < 64) wanted[count++] = r->table;
        }
    }
    uint64_t entities[LIVE_ENTITY_COUNT];
    int entityCount = 0;
    for (int i = 0; i < LIVE_ENTITY_COUNT; i++) if (live_entities[i].entity) entities[entityCount++] = live_entities[i].entity;
    if (count && !g_noscan) FindTables(mod, wanted, count, entities, entityCount, hints, hintCount);
    for (int i = 0; i < LIVE_ENTITY_COUNT; i++)
        if (live_entities[i].entity) WriteEntity(mod, &live_entities[i]);
}

/* The live rows over the copies: everything but +0 (the row's own id), then the references to the mod's other rows. */
static void WriteRow(HfMod* mod, const char* what, uintptr_t at, const LiveRow* row, uint32_t id)
{
    if (at == 0) { HF_API(mod)->log(mod, "%s %u (live %u): no row to write", what, id, row->live_id); return; }
    memcpy((uint8_t*)at + 4, row->row + 4, row->size - 4);
    for (const LiveFix* f = row->fixes; f->kind; f++) memcpy((uint8_t*)at + f->offset, &(uint32_t){Resolve(f)}, 4);
    HF_API(mod)->log(mod, "%s %u: the live game's %u", what, id, row->live_id);
}

static void ProjectilesReady(HfMod* mod, HfEvent event, void* user)
{
    const HfApi* hf = HF_API(mod);
    for (int i = 0; i < LIVE_DAMAGE_COUNT; i++)
        if (g_damage[i]) WriteRow(mod, "damage", hf->damage_row(g_damage[i]), &live_damage[i], g_damage[i]);
    for (int i = 0; i < LIVE_PROJECTILE_COUNT; i++)
        if (g_projectile[i]) WriteRow(mod, "projectile", hf->projectile_row(g_projectile[i]), &live_projectiles[i], g_projectile[i]);
}

static int AddRows(const HfApi* hf, HfMod* mod)
{
    int n = 0;
    for (int i = 0; i < LIVE_DAMAGE_COUNT; i++)
    {
        snprintf(g_names[n], sizeof g_names[n], "goose/scope_of_authority/damage_%u", live_damage[i].live_id);
        HfDamage d = {sizeof d};
        d.base = live_damage[i].base;
        d.name = g_names[n++];
        if ((g_damage[i] = hf->add_damage(mod, &d)) == 0) return 1;
    }
    for (int i = 0; i < LIVE_PROJECTILE_COUNT; i++)
    {
        snprintf(g_names[n], sizeof g_names[n], "goose/scope_of_authority/projectile_%u", live_projectiles[i].live_id);
        HfProjectile p = {sizeof p};
        p.base = live_projectiles[i].base;
        p.name = g_names[n++];
        for (const LiveFix* f = live_projectiles[i].fixes; f->kind; f++) if (f->offset == 0x3C) p.damage = Resolve(f);
        if ((g_projectile[i] = hf->add_projectile(mod, &p)) == 0) return 1;
    }
    return 0;
}

/* Each entity owns a record in every component it has: add_weapon takes the list, register_entity own_all. Should
 * add_weapon refuse components outside HellForge's entity profile (src/HellForge.Core/entity-profile.json), it is asked
 * again for those alone; the rest then stay shared with the base, and WriteEntity says which. */
static const char* g_own[LIVE_ENTITY_COUNT][40];
static const char* const PROFILED[] = {"AbilityWeaponComponentData", "ArcWeaponComponentData", "BackpackComponentData",
    "BeamWeaponComponentData", "DepositComponentData", "ExplosiveComponentData", "LoadoutEntryComponentData",
    "LoadoutPackageComponentData", "MeleeAttackComponentData", "MeleeWeaponComponentData", "ProjectileWeaponComponentData",
    "SprayWeaponComponentData", "TagComponentData", "ThrowableComponentData", "ThrowerComponentData", "UnitComponentData",
    "WeaponChargeComponentData", "WeaponCustomizationComponentData", "WeaponDataComponentData", "WeaponHeatComponentData",
    "WeaponLinkedAmmoComponentData", "WeaponMagazineComponentData", "WeaponReloadComponentData", "WeaponRoundsComponentData",
    "WeaponWindUpComponentData", NULL};

static int Profiled(const char* component)
{
    for (const char* const* p = PROFILED; *p; p++) if (strcmp(*p, component) == 0) return 1;
    return 0;
}

static int AddEntity(const HfApi* hf, HfMod* mod, LiveEntity* e)
{
    const char** own = g_own[e - live_entities];
    int n = 0;
    for (const LiveRecord* r = e->records; r->component && n < 39; r++) own[n++] = r->component;
    if (e->base_item)
    {
        HfWeapon w = {sizeof w};
        w.base = e->base_item;
        w.unit = e->name;
        w.designation = e->designation;
        w.name = e->title;
        w.description = e->description;
        w.own_components = own;
        e->item = hf->add_weapon(mod, &w);
        if (e->item == 0)
        {
            hf->log(mod, "%s: refused with every component its own; again with the profiled ones", e->key);
            n = 0;
            for (const LiveRecord* r = e->records; r->component; r++) if (Profiled(r->component)) own[n++] = r->component;
            own[n] = NULL;
            e->item = hf->add_weapon(mod, &w);
        }
        hf->log(mod, "%s %s: loadout id %08x", e->designation, e->title, e->item);
        return e->item == 0;
    }
    static HfEntityDef defs[LIVE_ENTITY_COUNT];
    HfEntityDef* d = &defs[e - live_entities];
    *d = (HfEntityDef){.size = sizeof(HfEntityDef), .name = e->name, .base = e->base, .unit = e->name, .own_all = 1,
        .title = e->title, .designation = e->designation, .description = e->description};
    if (strstr(e->name, "/hellpod/") != NULL) d->unit = NULL; /* a rack keeps the hellpod rack's model */
    e->entity = hf->register_entity(mod, d);
    hf->log(mod, "%s: entity %016llx", e->key, (unsigned long long)e->entity);
    return e->entity == 0;
}

static uint64_t g_payload[2][2];

static int AddStratagem(const HfApi* hf, HfMod* mod, int which, uint32_t base, const char* name, uint64_t rack,
    const char* title, const char* description, const char* code, uint32_t flags)
{
    g_payload[which][0] = rack;
    g_payload[which][1] = SUPPORT_HELLPOD;
    HfStratagem s = {sizeof s};
    s.base = base;
    s.name = name;
    s.title = title;
    s.description = description;
    s.code = code;
    s.cooldown = 480.0f;
    s.payload = g_payload[which];
    s.payload_count = 2;
    s.flags = flags;
    uint32_t type = hf->add_stratagem(mod, &s);
    hf->log(mod, "%s: stratagem type %u (%s)", title, type, code);
    return type == 0;
}

HF_MOD_EXPORT int hellforge_mod_init(const HfApi* hf, HfMod* mod)
{
    if (hf->version < 7) return 1;
    ReadBisect(hf, mod);
    DiagInit(hf, mod); /* one-time research dump of the pinned build's ability dispatcher and animation-event code */
    int refused = AddRows(hf, mod);
    for (int i = 0; i < LIVE_ENTITY_COUNT && !refused; i++) refused |= AddEntity(hf, mod, &live_entities[i]);
    if (refused) { hf->log(mod, "not loaded: %s", hf->size > offsetof(HfApi, last_log) ? hf->last_log(mod) : ""); return 1; }
    /* the live stratagems: AMW-20 Apex D L L U D L, LAS-44 Nova D L R D D, both 480 s (helldivers.wiki.gg, 1.007.200) */
    refused |= AddStratagem(hf, mod, 0, HF_STRATAGEM_GR8_RECOILLESS_RIFLE, "goose/scope_of_authority/amw20_apex",
        live_entities[LIVE_APEX_RACK].entity, "AMW-20 Apex", live_entities[LIVE_APEX].description, "DLLUDL",
        HF_TRAIT_SUPPORT_WEAPON | HF_TRAIT_HELLPOD | HF_TRAIT_BACKPACK | HF_TRAIT_ARMOR_PIERCING);
    refused |= AddStratagem(hf, mod, 1, HF_STRATAGEM_LAS99_QUASAR_CANNON, "goose/scope_of_authority/las44_nova",
        live_entities[LIVE_NOVA_RACK].entity, "LAS-44 Nova", live_entities[LIVE_NOVA].description, "DLRDD",
        HF_TRAIT_SUPPORT_WEAPON | HF_TRAIT_HELLPOD | HF_TRAIT_ARMOR_PIERCING | HF_TRAIT_HEAT);
    hf->on(mod, HF_EVENT_ENTITIES_READY, EntitiesReady, NULL);
    hf->on(mod, HF_EVENT_PROJECTILES_READY, ProjectilesReady, NULL);
    return refused;
}
