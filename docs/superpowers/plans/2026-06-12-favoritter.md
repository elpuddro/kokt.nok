# Favoritter Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La brukeren stjerne oppskrifter (på kort + i detalj) og se en filtrert favoritt-visning, med favoritter persistert via Tauri Store-plugin.

**Architecture:** All favoritt-logikk i frontend: en `src/lib/favoritter.ts`-modul innkapsler Tauri Store-plugin, `+page.svelte` holder favoritt-IDene som `$state<Set<number>>`, stjerne-knapper toggler, og et sidebar-filter viser favorittene via én ny backend-kommando `hent_oppskrifter_by_ids`.

**Tech Stack:** Svelte 5 (runes), Tauri 2 (`@tauri-apps/plugin-store` + `tauri-plugin-store`), Rust/rusqlite.

**Spec:** `docs/superpowers/specs/2026-06-12-favoritter-design.md`

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src-tauri/Cargo.toml` | Legg til `tauri-plugin-store` | Modify |
| `kokebok-app/package.json` | Legg til `@tauri-apps/plugin-store` | Modify (via npm) |
| `kokebok-app/src-tauri/capabilities/default.json` | `store:default`-permission | Modify |
| `kokebok-app/src-tauri/src/lib.rs` | Registrer store-plugin + ny `hent_oppskrifter_by_ids`-kommando | Modify |
| `kokebok-app/src/lib/favoritter.ts` | Tynn wrapper rundt Store-plugin (`favorittLast`, `favorittToggle`) | Create |
| `kokebok-app/src/routes/+page.svelte` | Favoritt-state, stjerne-knapper, sidebar-filter, favoritt-visning | Modify |

**Rekkefølge:** backend-plumbing (plugin + kommando) først, så frontend-modul, så UI-integrasjon. Hver task etterlater prosjektet kompilerbart.

---

## Task 1: Installer og registrer Tauri Store-plugin

Plumbing. Ingen oppførsel ennå — bare at plugin er registrert og appen fortsatt bygger.

**Files:**
- Modify: `kokebok-app/src-tauri/Cargo.toml`
- Modify: `kokebok-app/package.json` (via npm)
- Modify: `kokebok-app/src-tauri/capabilities/default.json`
- Modify: `kokebok-app/src-tauri/src/lib.rs:347-348`

- [ ] **Step 1: Legg til Rust-avhengighet**

Run (Git Bash): `cd "<repo>/kokebok-app/src-tauri" && cargo add tauri-plugin-store`
Expected: `tauri-plugin-store` legges til i Cargo.toml `[dependencies]`.

- [ ] **Step 2: Legg til JS-avhengighet**

Run: `cd "<repo>/kokebok-app" && npm install @tauri-apps/plugin-store`
Expected: pakken legges til i `package.json` dependencies.

- [ ] **Step 3: Legg til permission**

I `kokebok-app/src-tauri/capabilities/default.json`, endre `permissions`-arrayet fra:
```json
  "permissions": [
    "core:default",
    "opener:default"
  ]
```
til:
```json
  "permissions": [
    "core:default",
    "opener:default",
    "store:default"
  ]
```

- [ ] **Step 4: Registrer plugin i lib.rs**

I `kokebok-app/src-tauri/src/lib.rs`, i `run()` (linje ~347-348), endre:
```rust
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
```
til:
```rust
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
```

- [ ] **Step 5: Kompiler backend**

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo check`
Expected: `Finished` uten feil.

- [ ] **Step 6: Bygg frontend (sjekk JS-pakken løser)**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 7: Commit**

```bash
git add kokebok-app/src-tauri/Cargo.toml kokebok-app/src-tauri/Cargo.lock kokebok-app/package.json kokebok-app/package-lock.json kokebok-app/src-tauri/capabilities/default.json kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(favoritter): installer og registrer tauri-plugin-store"
```

---

## Task 2: Backend-kommando `hent_oppskrifter_by_ids`

Henter favoritt-oppskriftene (samme kortfelt som listen). Bygger dynamisk `IN (?,?,...)` etter mønsteret i eksisterende `hent_oppskrifter`.

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (ny funksjon før `run()`, ~linje 343; registrer i `generate_handler!` ~linje 349-353)

- [ ] **Step 1: Legg til kommandoen**

I `kokebok-app/src-tauri/src/lib.rs`, rett FØR `#[cfg_attr(mobile, tauri::mobile_entry_point)]` (linje ~345), legg til:

```rust
// ─── Kommando: oppskrifter etter id-liste (favoritter) ─────────────────────────
#[tauri::command]
fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>) -> Result<Vec<Value>, String> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let conn = open(&app)?;

    // Bygg "?,?,?,..." og eier id-ene som ToSql-referanser (samme mønster som
    // hent_oppskrifter sin owned/filter_refs).
    let placeholders = vec!["?"; ids.len()].join(",");
    let sql = format!(
        "SELECT id, slug, navn, type, porsjoner, tid, bilde
         FROM   oppskrifter
         WHERE  id IN ({placeholders})
         ORDER  BY navn COLLATE NOCASE"
    );
    let refs: Vec<&dyn rusqlite::ToSql> =
        ids.iter().map(|i| i as &dyn rusqlite::ToSql).collect();

    query_json(&conn, &sql, refs.as_slice())
}
```

- [ ] **Step 2: Registrer kommandoen**

I samme fil, i `generate_handler!` (linje ~349-353), endre:
```rust
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift
        ])
```
til:
```rust
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift,
            hent_oppskrifter_by_ids
        ])
```

- [ ] **Step 3: Kompiler**

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo check`
Expected: `Finished` uten feil.

- [ ] **Step 4: Verifiser SQL mot ekte DB**

Run (Git Bash):
```bash
cd "<repo>/kokebok-app/src-tauri/data" && python -c "import sqlite3; db=sqlite3.connect('kokt.db'); ids=[r[0] for r in db.execute('SELECT id FROM oppskrifter LIMIT 3')]; q='SELECT id, navn FROM oppskrifter WHERE id IN (%s) ORDER BY navn COLLATE NOCASE' % ','.join('?'*len(ids)); [print(r) for r in db.execute(q, ids)]"
```
Expected: 3 rader (id, navn), alfabetisk sortert. Bekrefter at `IN (...)`-formen og kolonnene stemmer.

- [ ] **Step 5: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(favoritter): hent_oppskrifter_by_ids-kommando"
```

---

## Task 3: Frontend-modul `src/lib/favoritter.ts`

Innkapsler Store-plugin-et. Ren grenseflate mot UI. (Ingen testinfrastruktur i prosjektet; verifiseres via bygg + manuell test i Task 5.)

**Files:**
- Create: `kokebok-app/src/lib/favoritter.ts`

- [ ] **Step 1: Opprett modulen**

Create `kokebok-app/src/lib/favoritter.ts`:

```ts
// Favoritter persisteres i en JSON-fil i appens data-katalog via Tauri Store.
// kokt.db er read-only, så favoritter kan ikke skrives dit.
import { load, type Store } from "@tauri-apps/plugin-store";

const FIL = "favoritter.json";
const NOKKEL = "ids";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last favoritt-IDer. Returnerer tomt Set ved feil (favoritter er ikke kritiske). */
export async function favorittLast(): Promise<Set<number>> {
  try {
    const store = await hentStore();
    const ids = (await store.get<number[]>(NOKKEL)) ?? [];
    return new Set(ids);
  } catch (err) {
    console.error("favorittLast feilet:", err);
    return new Set();
  }
}

/**
 * Toggle favoritt-status for en oppskrift. Muterer ikke `settet` direkte —
 * returnerer et NYTT Set (Svelte 5 $state<Set> reagerer ikke på .add/.delete).
 * Best effort: ved lagringsfeil beholdes endringen i minnet for økten.
 */
export async function favorittToggle(
  id: number,
  settet: Set<number>,
): Promise<Set<number>> {
  const nytt = new Set(settet);
  if (nytt.has(id)) nytt.delete(id);
  else nytt.add(id);
  try {
    const store = await hentStore();
    await store.set(NOKKEL, [...nytt]);
    await store.save();
  } catch (err) {
    console.error("favorittToggle lagring feilet:", err);
  }
  return nytt;
}
```

- [ ] **Step 2: Bygg (typecheck modulen)**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil (importen `@tauri-apps/plugin-store` og typene løser).

- [ ] **Step 3: Commit**

```bash
git add kokebok-app/src/lib/favoritter.ts
git commit -m "feat(favoritter): favoritter.ts store-wrapper"
```

---

## Task 4: Favoritt-state + stjerne-knapper i +page.svelte

State, lasting ved oppstart, og stjerne på kort + i detalj-topplinje.

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (import + state ~linje 1-31, onMount ~192, kort ~269, detalj-topbar ~315, style)

- [ ] **Step 1: Importer modulen + legg til state**

I `<script>`, etter de eksisterende importene (linje ~4), legg til:
```ts
  import { favorittLast, favorittToggle } from "$lib/favoritter";
```

I state-blokken (etter linje 31, `let resourceDir = $state("");`), legg til:
```ts
  let favoritter = $state<Set<number>>(new Set());
```

- [ ] **Step 2: Last favoritter ved oppstart**

I `onMount` (linje ~192-196), etter `resourceDir = await resolveResource("");`, legg til:
```ts
    favoritter = await favorittLast();
```

- [ ] **Step 3: Legg til toggle-funksjon**

I `<script>`, etter `velgKategori`-funksjonen (linje ~113), legg til:
```ts
  async function toggleFavoritt(id: number, e?: Event) {
    e?.stopPropagation();   // ikke åpne detalj når stjerne klikkes på kortet
    favoritter = await favorittToggle(id, favoritter);
  }
```

- [ ] **Step 4: Stjerne-knapp på kortet**

I recipe-card (linje 269-286), inni `<div class="card-img-wrap">`, rett etter linjen `{#if r.tid}<div class="card-badge-time">⏱ {r.tid}</div>{/if}` (linje 276), legg til:
```svelte
              <button
                class="card-fav"
                class:aktiv={favoritter.has(r.id)}
                title={favoritter.has(r.id) ? "Fjern favoritt" : "Legg til favoritt"}
                onclick={(e) => toggleFavoritt(r.id, e)}
              >{favoritter.has(r.id) ? "⭐" : "☆"}</button>
```

- [ ] **Step 5: Stjerne i detalj-topplinjen**

I `.detail-topbar` (linje 315-319), etter `<button class="btn-back" ...>← Tilbake</button>` (linje 316), legg til:
```svelte
        <button
          class="detail-fav"
          class:aktiv={favoritter.has(opp.id)}
          title={favoritter.has(opp.id) ? "Fjern favoritt" : "Legg til favoritt"}
          onclick={() => toggleFavoritt(opp.id)}
        >{favoritter.has(opp.id) ? "⭐ Favoritt" : "☆ Favoritt"}</button>
```

- [ ] **Step 6: Stil for stjerne-knappene**

I `<style>`-blokken (ved siden av `.recipe-card`/`.detail-topbar`-reglene), legg til. `.card-img-wrap` har allerede `position: relative` (linje 522), så stjernen kan posisjoneres absolutt uten ny regel. `.card-badge-time` ligger nederst-høyre; stjernen legges øverst-venstre, så ingen kollisjon.
```css
  .card-fav {
    position: absolute;
    top: 8px; left: 8px;
    border: none;
    background: rgba(0, 0, 0, 0.35);
    color: #fff;
    font-size: 1.1rem;
    line-height: 1;
    padding: 4px 6px;
    border-radius: 8px;
    cursor: pointer;
  }
  .card-fav.aktiv { background: rgba(0, 0, 0, 0.5); }
  .detail-fav {
    border: 1px solid var(--border);
    background: var(--bg-warm);
    color: var(--text);
    padding: 6px 12px;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .detail-fav.aktiv { border-color: var(--accent-dark); }
```

- [ ] **Step 7: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 8: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(favoritter): stjerne-knapper på kort og i detalj"
```

---

## Task 5: Favoritt-filter i sidebar + favoritt-visning

Sidebar-knapp som henter og viser favorittene; tom-tilstand; søk skjult i favoritt-modus.

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (fetchGrid ~78, velgKategori ~108, sidebar ~228, search-wrap ~207, empty-state ~261)

- [ ] **Step 1: La fetchGrid håndtere favoritt-modus**

I `fetchGrid` (linje ~74-93), erstatt selve invoke-blokken. Endre fra:
```ts
    loading = true;
    try {
      const data: any = await invoke("hent_oppskrifter", {
        kategori: currentKategori, sok, side, perSide,
      });
      if (seq !== fetchSeq) return;
      total = data.total;
      oppskrifter = data.oppskrifter;
      side = data.side;
```
til:
```ts
    loading = true;
    try {
      if (currentKategori === "__fav__") {
        const liste: any[] = await invoke("hent_oppskrifter_by_ids", {
          ids: [...favoritter],
        });
        if (seq !== fetchSeq) return;
        oppskrifter = liste;
        total = liste.length;
        side = 1;
      } else {
        const data: any = await invoke("hent_oppskrifter", {
          kategori: currentKategori, sok, side, perSide,
        });
        if (seq !== fetchSeq) return;
        total = data.total;
        oppskrifter = data.oppskrifter;
        side = data.side;
      }
```
(La resten av try/catch/finally stå uendret.)

- [ ] **Step 2: Legg til favoritt-valg-funksjon**

I `<script>`, rett etter `velgKategori` (linje ~108-113), legg til:
```ts
  function velgFavoritter() {
    currentKategori = "__fav__";
    side = 1;
    sok = "";
    fetchGrid();
  }
```

- [ ] **Step 3: Sidebar-knapp for favoritter**

I `<nav id="kategori-liste">`, rett ETTER den lukkende `</button>` for «alle»-knappen og FØR `<div class="kat-divider"></div>` (linje ~228-229), legg til:
```svelte
    <button
      class="kat-btn"
      class:active={currentKategori === "__fav__"}
      onclick={velgFavoritter}
    >
      <span class="kat-emoji">⭐</span>
      <span class="kat-navn">Favoritter</span>
      <span class="kat-teller">{favoritter.size}</span>
    </button>
```

- [ ] **Step 4: Skjul søkefeltet i favoritt-modus**

I `.search-wrap` (linje ~207), legg til en `{#if}` rundt søke-inputen. Endre:
```svelte
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input
      id="sok-input"
      type="search"
      placeholder="Søk oppskrifter…"
      autocomplete="off"
      value={sok}
      oninput={onSearchInput}
    />
  </div>
```
til (pakk input i en betingelse — vis bare når IKKE favoritt-modus):
```svelte
  {#if currentKategori !== "__fav__"}
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input
        id="sok-input"
        type="search"
        placeholder="Søk oppskrifter…"
        autocomplete="off"
        value={sok}
        oninput={onSearchInput}
      />
    </div>
  {/if}
```

- [ ] **Step 5: Tom-tilstand for favoritter**

I recipe-grid (linje ~261-266), gjør empty-state betinget på modus. Endre:
```svelte
      {#if oppskrifter.length === 0}
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h3>Ingen oppskrifter funnet</h3>
          <p>Prøv å søke på noe annet, eller velg en annen kategori.</p>
        </div>
```
til:
```svelte
      {#if oppskrifter.length === 0}
        <div class="empty-state">
          {#if currentKategori === "__fav__"}
            <div class="empty-icon">⭐</div>
            <h3>Ingen favoritter ennå</h3>
            <p>Trykk ⭐ på en oppskrift for å legge den til.</p>
          {:else}
            <div class="empty-icon">🔍</div>
            <h3>Ingen oppskrifter funnet</h3>
            <p>Prøv å søke på noe annet, eller velg en annen kategori.</p>
          {/if}
        </div>
```

- [ ] **Step 6: Header-tittel i favoritt-modus**

I `#main-header` (linje ~247-253), `#header-tittel` viser i dag «alle»/kategori. Endre:
```svelte
    <h1 id="header-tittel">
      {#if currentKategori === "alle"}
        {sok ? `Søkeresultater for «${sok}»` : "Alle oppskrifter"}
      {:else}
        {currentKategori}
      {/if}
    </h1>
```
til:
```svelte
    <h1 id="header-tittel">
      {#if currentKategori === "__fav__"}
        ⭐ Favoritter
      {:else if currentKategori === "alle"}
        {sok ? `Søkeresultater for «${sok}»` : "Alle oppskrifter"}
      {:else}
        {currentKategori}
      {/if}
    </h1>
```

- [ ] **Step 7: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 8: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(favoritter): sidebar-filter og favoritt-visning"
```

---

## Task 6: Manuell ende-til-ende-verifikasjon

Favoritter krever en kjørende app for å verifiseres (Store-plugin + persistering). Dette steget er MANUELT (krever menneske ved skjermen).

**Files:** ingen (verifikasjon).

- [ ] **Step 1: Kjør appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`

- [ ] **Step 2: Verifiser (manuell sjekkliste)**

- Stjern en oppskrift via ☆ på kortet → stjernen blir ⭐, detaljen viser «⭐ Favoritt».
- Klikk på stjernen åpner IKKE oppskriften (event-propagering stoppet).
- Velg «⭐ Favoritter» i sidebaren → kun stjernede oppskrifter vises; søkefeltet er skjult; telleren viser antall.
- Av-stjern en favoritt fra favoritt-visningen → den forsvinner fra lista.
- Tom favorittliste → «Ingen favoritter ennå»-melding, ingen krasj.
- Lukk appen helt og start på nytt → favorittene består (lest fra favoritter.json).

- [ ] **Step 3: (valgfritt) Bekreft persisteringsfila**

Favoritter lagres i appens data-katalog (Windows: `%APPDATA%/<bundle-identifier>/favoritter.json`, dvs. `%APPDATA%/no.kokebok.app/favoritter.json`). Bekreft at fila finnes og inneholder `{"ids":[...]}` etter at minst én favoritt er satt.

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** Store-lagring (T1+T3), `hent_oppskrifter_by_ids` (T2),
  `favoritter.ts`-grensesnitt (T3), stjerne på kort+detalj (T4), sidebar-filter
  + tom-tilstand + søk-skjult (T5), manuell test (T6). Alt dekket.
- **Typer/navn konsistente:** `favorittLast()`/`favorittToggle(id, settet)` likt
  i T3 og T4. `currentKategori === "__fav__"` brukt likt i T5 (fetchGrid,
  sidebar, search-wrap, empty-state, header). Kommandonavn
  `hent_oppskrifter_by_ids` + param `ids` likt i T2 (Rust) og T5 (invoke).
- **Svelte 5-reaktivitet:** `favoritter = await favorittToggle(...)` (ny Set-
  tilordning) sikrer reaktiv oppdatering — flagget i T3 og brukt i T4.
- **Mulig kollisjon:** `.card-img-wrap { position: relative }` kan finnes fra
  før — T4 Step 6 ber implementeren sjekke og ikke duplisere.
