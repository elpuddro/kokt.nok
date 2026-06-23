# Tidsbasert forside — Implementeringsplan (#21)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forsiden viser oppskrifter tilpasset tidspunktet på dagen; etter 22:00 filtreres oppskrifter som krever ovn eller stekepanne bort (kun fengselsbygg).

**Architecture:** Frontend bestemmer tidssone via `new Date().getHours()` og kaller Rust-kommandoen `forside_oppskrifter(typer, nattFilter)`. Rust gjør ett `ORDER BY RANDOM() LIMIT 20`-oppslag med valgfri NOT IN-subquery. `nattFilter` settes til `true` kun når klokkeslett er 22–06 OG `aboutInfo === null` (fengselsbygg).

**Tech Stack:** Tauri 2 (Rust, rusqlite, serde), Svelte 5 runes (`$state`, `$derived`), TypeScript, `invoke` fra `@tauri-apps/api/core`.

## Global Constraints

- Svelte 5 runes kun — ingen `$:`, ingen `writable()` stores
- `invoke` fra `@tauri-apps/api/core` — ikke `@tauri-apps/api`
- Rust: `#[tauri::command]` + registrering i `tauri::generate_handler![]` i `run()`
- Ingen nye npm-pakker
- Commit-meldinger uten "Co-Authored-By"-trailer
- DB er read-only — ingen migrasjoner
- Nattfilter aktiv kun for fengselsbygg (`aboutInfo === null`) og kun 22:00–06:00

---

## Filstruktur

| Fil | Endring |
|-----|---------|
| `kokebok-app/src-tauri/src/lib.rs` | Ny `ForsideOppskrift`-struct + `forside_oppskrifter`-kommando + registrering |
| `kokebok-app/src/routes/+page.svelte` | `TIDSSONER`-konstant, state, `lastForside()`, forside-HTML/CSS |

---

## Task 1: Rust-kommando `forside_oppskrifter`

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- Produces: `forside_oppskrifter(app: AppHandle, typer: Vec<String>, natt_filter: bool) -> Vec<ForsideOppskrift>`
- Produces: `struct ForsideOppskrift { id: i64, navn: String, tid: Option<String>, bilde: Option<String> }`

- [ ] **Step 1: Les eksisterende `lib.rs` for å forstå mønsteret**

Åpne `kokebok-app/src-tauri/src/lib.rs`. Se spesielt på:
- `fn hent_oppskrifter` (linje ~279) — viser `open(&app)?`-mønsteret og dynamisk SQL
- `generate_handler![]`-listen (linje ~1168) — der du skal legge til `forside_oppskrifter`

Mønsteret for å åpne DB: `let conn = open(&app)?;`

- [ ] **Step 2: Legg til `ForsideOppskrift`-struct og `forside_oppskrifter` i `lib.rs`**

Finn linjen rett FØR `pub fn run()` (ca. linje 1145). Legg til hele blokken der — etter `about_info`-funksjonene:

```rust
#[derive(serde::Serialize)]
struct ForsideOppskrift {
    id: i64,
    navn: String,
    tid: Option<String>,
    bilde: Option<String>,
}

#[tauri::command]
fn forside_oppskrifter(
    app: AppHandle,
    typer: Vec<String>,
    #[allow(non_snake_case)] nattFilter: bool,
) -> Vec<ForsideOppskrift> {
    let conn = match open(&app) {
        Ok(c) => c,
        Err(_) => return vec![],
    };

    if typer.is_empty() {
        return vec![];
    }

    let placeholders = typer.iter().map(|_| "?").collect::<Vec<_>>().join(", ");

    let sql = if nattFilter {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             AND id NOT IN ( \
                 SELECT DISTINCT oppskrift_id FROM trinn \
                 WHERE LOWER(tekst) LIKE '%ovn%' \
                    OR LOWER(tekst) LIKE '%stekepanne%' \
             ) \
             ORDER BY RANDOM() LIMIT 20"
        )
    } else {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             ORDER BY RANDOM() LIMIT 20"
        )
    };

    let params: Vec<&dyn rusqlite::ToSql> = typer.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    conn.prepare(&sql)
        .and_then(|mut stmt| {
            stmt.query_map(params.as_slice(), |row| {
                Ok(ForsideOppskrift {
                    id: row.get(0)?,
                    navn: row.get(1)?,
                    tid: row.get(2)?,
                    bilde: row.get(3)?,
                })
            })
            .and_then(|rows| rows.collect())
        })
        .unwrap_or_default()
}
```

- [ ] **Step 3: Registrer kommandoen i `generate_handler![]`**

Finn `tauri::generate_handler![` i `run()`. Legg til `forside_oppskrifter` i listen:

```rust
.invoke_handler(tauri::generate_handler![
    get_kategorier,
    hent_oppskrifter,
    hent_oppskrift,
    hent_oppskrifter_by_ids,
    cook_mode,
    ingrediens_forslag,
    hva_kan_jeg_lage,
    generer_matplan,
    about_info,
    forside_oppskrifter   // ← ny
])
```

- [ ] **Step 4: Verifiser kompilering**

Kjør fra `C:\Users\elpud\CODE\kokt.nok\.claude\worktrees\feat+matplanlegger`:

```powershell
cargo build --manifest-path kokebok-app/src-tauri/Cargo.toml
```

Forventet: kompilerer uten feil. Hvis feil om `ToSql` — sjekk at `rusqlite` er i `Cargo.toml` og at `use rusqlite::ToSql;` eller `rusqlite::ToSql` er tilgjengelig (det er det fra eksisterende kode).

- [ ] **Step 5: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(forside): Rust-kommando forside_oppskrifter med nattfilter"
```

---

## Task 2: Frontend — tidslogikk og forsidevisning

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `forside_oppskrifter(typer: string[], nattFilter: bool)` fra Task 1
- Consumes: `aboutInfo` — allerede `$state` fra Task 3 i helseprofil (#20), lastet i `onMount`; er `null` for fengselsbygg
- Consumes: `åpneOppskrift(id: number)` — eksisterende funksjon (linje ~483)
- Consumes: `imgSrc(id)` — eksisterende funksjon (linje ~87)

- [ ] **Step 1: Les `+page.svelte` før du rører den**

Finn og noter:
1. Hvor `let aboutInfo = $state` er deklarert (etter #20 er dette allerede der)
2. Hvor `onMount` slutter (der du skal kalle `lastForside()`)
3. Hvor hoveddelen av main-innholdet starter — spesielt blokken som begynner `{#if currentKategori === "__handle__"}` (ca. linje 838). Forsiden legges inn som en ny `{:else if currentKategori === "alle"}`-gren her, eller som en separat blokk.
4. Eksisterende `recipe-card`-struktur (ca. linje 1163) — du skal lage en forenklet versjon

- [ ] **Step 2: Legg til TypeScript-interface, konstant og state**

Legg til rett etter eksisterende interface/type-deklarasjoner i `<script>`-blokken (søk etter `interface` eller etter `let profilStore`):

```typescript
interface ForsideOppskrift { id: number; navn: string; tid: string | null; bilde: string | null }

const TIDSSONER: Array<{ fra: number; til: number; typer: string[]; tittel: string }> = [
  { fra: 6,  til: 10, typer: ["Frokost", "Sandwich/smørbrød", "Snacks"],         tittel: "God morgen 🌅" },
  { fra: 10, til: 14, typer: ["Lunsj", "Tapas/småretter", "Sandwich/smørbrød"],  tittel: "Tid for lunsj 🥗" },
  { fra: 14, til: 18, typer: ["Middag", "Supper", "Gryter"],                      tittel: "Middagstid 🍽️" },
  { fra: 18, til: 22, typer: ["Middag", "Tapas/småretter", "Forretter"],          tittel: "God kveld 🌆" },
  { fra: 22, til: 6,  typer: ["Middag", "Supper", "Snacks"],                      tittel: "Sent på kvelden 🌙" },
];

let forsideOppskrifter = $state<ForsideOppskrift[]>([]);
let forsideTittel = $state("");
```

- [ ] **Step 3: Legg til `lastForside()`-funksjonen**

Legg til etter `slettProfil`-funksjonen (eller etter siste hjelpefunksjon):

```typescript
  function nåværendeTidssone() {
    const t = new Date().getHours();
    return TIDSSONER.find(s =>
      s.til > s.fra ? t >= s.fra && t < s.til : t >= s.fra || t < s.til
    )!;
  }

  async function lastForside() {
    const sone = nåværendeTidssone();
    forsideTittel = sone.tittel;
    const t = new Date().getHours();
    const nattFilter = (t >= 22 || t < 6) && aboutInfo === null;
    forsideOppskrifter = await invoke<ForsideOppskrift[]>("forside_oppskrifter", {
      typer: sone.typer,
      nattFilter,
    });
  }
```

- [ ] **Step 4: Kall `lastForside()` fra `onMount`**

Finn `onMount`-blokken. Etter at `aboutInfo` er lastet (etter `try { aboutInfo = await invoke("about_info") } catch { ... }`), legg til:

```typescript
  await lastForside();
```

- [ ] **Step 5: Kall `lastForside()` ved navigasjon til forsiden**

Finn `function velgKategori(k: string)` (linje ~182). Den setter `currentKategori = k`. Logoklikk setter `currentKategori = "alle"`. Vi trenger at `lastForside()` kjøres når brukeren navigerer til "alle"-visningen.

Legg til en `$effect` rett etter state-deklarasjonene:

```typescript
  $effect(() => {
    if (currentKategori === "alle" && forsideOppskrifter.length === 0) {
      lastForside();
    }
  });
```

Merk: `forsideOppskrifter.length === 0`-sjekken hindrer unødvendig re-henting når brukeren bare scroller. `onMount` fyller arrayet første gang; effekten håndterer tilfellet der brukeren navigerer vekk og tilbake etter at arrayet er tømt (f.eks. ved logout/reset). For enkelhets skyld: kall også `lastForside()` eksplisitt i `velgKategori("alle")`-stien dersom du ser at effekten ikke trigges riktig.

- [ ] **Step 6: Legg til forsidevisning i HTML**

Finn blokken der `currentKategori === "alle"` rendres (ca. etter de andre `{:else if ...}`-grenene). Den eksisterende "alle"-blokken viser søkegrid. Legg til forsidevisning OVER det eksisterende grid-innholdet, inne i "alle"-blokken. Finn der `{:else if currentKategori === "alle"}` og innholdet under — legg til FØR den eksisterende `<div class="grid-wrap">` (eller tilsvarende):

```svelte
{#if !sok && forsideOppskrifter.length > 0}
  <div class="forside-wrap">
    <div class="forside-header">
      <h2 class="forside-tittel">{forsideTittel}</h2>
      <p class="forside-undertekst">Forslag til deg akkurat nå</p>
    </div>
    <div class="forside-grid">
      {#each forsideOppskrifter as o (o.id)}
        <article class="recipe-card" onclick={() => åpneOppskrift(o.id)}>
          <div class="card-img-wrap">
            {#if imgSrc(o.id)}
              <img src={imgSrc(o.id)} alt={o.navn} loading="lazy" />
            {:else}
              <div class="card-img-placeholder">🍽️</div>
            {/if}
            {#if o.tid}<div class="card-badge-time">⏱ {o.tid}</div>{/if}
          </div>
          <div class="card-body">
            <div class="card-name">{o.navn}</div>
          </div>
        </article>
      {/each}
    </div>
    <hr class="forside-skille" />
  </div>
{/if}
```

Forsideblokken vises kun når `!sok` (bruker søker ikke) og vi har forside-oppskrifter. Eksisterende grid følger like under.

- [ ] **Step 7: Legg til CSS**

Legg til i `<style>`-blokken (på slutten, før `</style>`):

```css
  /* ── Tidsbasert forside ─────────────────────────────────── */
  .forside-wrap { margin-bottom: 24px; }
  .forside-header { margin-bottom: 16px; }
  .forside-tittel { font-size: 1.3rem; font-weight: 700; margin: 0 0 4px; }
  .forside-undertekst { font-size: 0.85rem; color: var(--text-muted); margin: 0; }
  .forside-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  .forside-skille {
    border: none; border-top: 1px solid var(--border);
    margin: 0 0 24px;
  }
```

Gjenbruker eksisterende `.recipe-card`, `.card-img-wrap`, `.card-img-placeholder`, `.card-badge-time`, `.card-body`, `.card-name` — ingen nye klasser for kortene.

- [ ] **Step 8: Verifiser TypeScript**

```powershell
cd kokebok-app && npx tsc --noEmit
```

Forventet: 0 nye feil (ett pre-eksisterende feil i `vite.config.js` er OK).

- [ ] **Step 9: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(forside): tidsbasert forsidevisning med nattfilter"
```

---

## Spec-dekningssjekk (self-review)

- [x] Rust-kommando `forside_oppskrifter(typer, nattFilter)` → Task 1
- [x] `ForsideOppskrift { id, navn, tid, bilde }` → Task 1 Step 2
- [x] `ORDER BY RANDOM() LIMIT 20` → Task 1 Step 2
- [x] Nattfilter-SQL (NOT IN subquery på ovn/stekepanne) → Task 1 Step 2
- [x] Registrering i `generate_handler![]` → Task 1 Step 3
- [x] `TIDSSONER`-konstant med alle 5 intervaller → Task 2 Step 2
- [x] Alle 24 timer dekket (nattintervall 22–6 med `|| <`-logikk) → Task 2 Step 3
- [x] `nattFilter = (t >= 22 || t < 6) && aboutInfo === null` → Task 2 Step 3
- [x] `lastForside()` kalt i `onMount` etter `aboutInfo` er satt → Task 2 Step 4
- [x] Oppdatering ved navigasjon tilbake til forsiden → Task 2 Step 5
- [x] Forside skjult ved søk (`!sok`) → Task 2 Step 6
- [x] Eksisterende grid vises under forside (ikke erstattet) → Task 2 Step 6
- [x] CSS for forsideblokk → Task 2 Step 7
- [x] Hjemmebygg: `aboutInfo !== null` → `nattFilter = false` alltid → Task 2 Step 3
- [x] Fengselsbygg: `aboutInfo === null` → nattfilter aktivt 22–06 → Task 2 Step 3
