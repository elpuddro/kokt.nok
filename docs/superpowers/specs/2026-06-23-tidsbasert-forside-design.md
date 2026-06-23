# Tidsbasert forside — Design (#21)

**Dato:** 2026-06-23

---

## Mål

Forsiden (ingen kategori valgt) viser oppskrifter tilpasset tidspunktet på dagen. Frokostoppskrifter om morgenen, lunsj midt på dagen, middag på ettermiddagen og kvelden. Etter 22:00 og før 06:00 filtreres oppskrifter som krever ovn eller stekepanne bort — kun i fengselsbygg. Hjemmebygg har ingen nattfiltrering.

---

## Arkitektur

Tidslogikken lever i frontend (`+page.svelte`). `new Date().getHours()` kjøres i `onMount` og ved navigasjon tilbake til forsiden. Frontend slår opp i en lokal `TIDSSONER`-konstant for å finne riktige `type`-verdier og tittel, og kaller deretter en ny Rust-kommando `forside_oppskrifter(typer, natt_filter)` som returnerer maks 20 tilfeldige treff.

Nattfilteret (`natt_filter: bool`) bestemmes av frontend: `natt_filter = (time >= 22 || time < 6) && aboutInfo === null`. `aboutInfo` er allerede lastet i `onMount` fra `about_info`-kommandoen (null i fengselsbygg, objekt i hjemmebygg).

Ingen nye npm-pakker. Ingen ny Cargo-feature. Ingen DB-endringer.

---

## Tidsintervaller

| Intervall | Typer | Tittel |
|-----------|-------|--------|
| 06–10 | `["Frokost", "Sandwich/smørbrød", "Snacks"]` | God morgen 🌅 |
| 10–14 | `["Lunsj", "Tapas/småretter", "Sandwich/smørbrød"]` | Tid for lunsj 🥗 |
| 14–18 | `["Middag", "Supper", "Gryter"]` | Middagstid 🍽️ |
| 18–22 | `["Middag", "Tapas/småretter", "Forretter"]` | God kveld 🌆 |
| 22–06 | `["Middag", "Supper", "Snacks"]` | Sent på kvelden 🌙 |

Ingen overlap mellom intervaller. Alle 24 timer dekket. Grensene er inklusiv på venstre side (time >= start && time < slutt), med unntak av natt som er `time >= 22 || time < 6`.

---

## Rust-kommando

### `forside_oppskrifter`

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
    state: tauri::State<DbState>,
    typer: Vec<String>,
    natt_filter: bool,
) -> Vec<ForsideOppskrift> { ... }
```

**SQL når `natt_filter = false`:**
```sql
SELECT id, navn, tid, bilde
FROM oppskrifter
WHERE type IN (rparams)
ORDER BY RANDOM()
LIMIT 20
```

**SQL når `natt_filter = true`:**
```sql
SELECT id, navn, tid, bilde
FROM oppskrifter
WHERE type IN (rparams)
AND id NOT IN (
    SELECT DISTINCT oppskrift_id FROM trinn
    WHERE LOWER(tekst) LIKE '%ovn%'
       OR LOWER(tekst) LIKE '%stekepanne%'
)
ORDER BY RANDOM()
LIMIT 20
```

`rparams` er rusqlite repeat-params (`?,?,?` generert dynamisk basert på `typer.len()`). Kommandoen returnerer tom `Vec` ved DB-feil (samme mønster som eksisterende kommandoer).

Registreres i `tauri::generate_handler![]` i `run()`.

---

## Frontend

### Konstant

```typescript
const TIDSSONER: Array<{ fra: number; til: number; typer: string[]; tittel: string }> = [
  { fra: 6,  til: 10, typer: ["Frokost", "Sandwich/smørbrød", "Snacks"],         tittel: "God morgen 🌅" },
  { fra: 10, til: 14, typer: ["Lunsj", "Tapas/småretter", "Sandwich/smørbrød"],  tittel: "Tid for lunsj 🥗" },
  { fra: 14, til: 18, typer: ["Middag", "Supper", "Gryter"],                      tittel: "Middagstid 🍽️" },
  { fra: 18, til: 22, typer: ["Middag", "Tapas/småretter", "Forretter"],          tittel: "God kveld 🌆" },
  { fra: 22, til: 6,  typer: ["Middag", "Supper", "Snacks"],                      tittel: "Sent på kvelden 🌙" },
];
```

### State og logikk

```typescript
let forsideOppskrifter = $state<ForsideOppskrift[]>([]);
let forsideTittel = $state("");

interface ForsideOppskrift { id: number; navn: string; tid: string | null; bilde: string | null }

function nåværendeTidssone() {
  const t = new Date().getHours();
  return TIDSSONER.find(s => s.til > s.fra ? t >= s.fra && t < s.til : t >= s.fra || t < s.til)!;
}

async function lastForside() {
  const sone = nåværendeTidssone();
  forsideTittel = sone.tittel;
  const natt = (new Date().getHours() >= 22 || new Date().getHours() < 6) && aboutInfo === null;
  forsideOppskrifter = await invoke("forside_oppskrifter", { typer: sone.typer, nattFilter: natt });
}
```

`lastForside()` kalles fra `onMount` (etter `aboutInfo` er lastet) og når brukeren navigerer tilbake til forsiden (klikk på logo → `currentKategori = null`).

### HTML (vises kun når `currentKategori === null`)

```svelte
{#if currentKategori === null}
  <div class="forside-wrap">
    <div class="forside-header">
      <h2 class="forside-tittel">{forsideTittel}</h2>
      <p class="forside-undertekst">Forslag til deg akkurat nå</p>
    </div>
    {#if forsideOppskrifter.length > 0}
      <div class="oppskrift-grid">
        {#each forsideOppskrifter as o (o.id)}
          <button class="oppskrift-kort" onclick={() => velgOppskrift(o.id)}>
            <img src={imgSrc(o.bilde)} alt={o.navn} />
            <div class="kort-navn">{o.navn}</div>
            {#if o.tid}<div class="kort-tid">⏱ {o.tid}</div>{/if}
          </button>
        {/each}
      </div>
    {:else}
      <p class="forside-tom">Ingen forslag akkurat nå.</p>
    {/if}
  </div>
{/if}
```

Gjenbruker eksisterende CSS-klasser fra oppskriftslisten der de finnes. Nye klasser: `forside-wrap`, `forside-header`, `forside-tittel`, `forside-undertekst`, `forside-tom`.

### Navigasjon

Eksisterende logo-klikk (eller tilbake-til-forside) setter allerede `currentKategori = null`. `lastForside()` utløses derfra — enten via en `$effect` på `currentKategori`, eller ved å kalle `lastForside()` eksplisitt der `currentKategori = null` settes. Implementer velger den reneste løsningen basert på eksisterende kode.

---

## Ikke inkludert (YAGNI)

- "Last inn flere"-knapp
- Automatisk oppdatering mens appen er åpen
- Brukerstyrt nattfilter-innstilling
- Sesongbasert visning (dekket av temaer)
- Favoritt-baserte forslag

---

## Filer som endres

| Fil | Endring |
|-----|---------|
| `kokebok-app/src-tauri/src/lib.rs` | Ny `forside_oppskrifter`-kommando + `ForsideOppskrift`-struct |
| `kokebok-app/src/routes/+page.svelte` | `TIDSSONER`, state, `lastForside()`, forside-HTML + CSS |
