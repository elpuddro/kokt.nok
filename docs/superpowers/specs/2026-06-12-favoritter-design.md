# Favoritter — design

**Dato:** 2026-06-12
**Status:** Godkjent, klar for implementeringsplan

## Mål

La brukeren markere oppskrifter som favoritt med en stjerne, og se en filtrert
visning av favorittene sine. Favoritter persisteres mellom økter.

## Ikke-mål (YAGNI)

- Ikke søk innenfor favoritt-visningen (v1 — søk er inaktivt i favoritt-modus).
- Ikke synkronisering mellom maskiner (lokal per installasjon).
- Ikke kategorier/mapper for favoritter — én flat liste.
- Ikke favoritt-telling/badges.

## Bakgrunn / tekniske fakta (verifisert)

- `kokt.db` åpnes `SQLITE_OPEN_READ_ONLY` fra resource-dir ([lib.rs:35](../../../kokebok-app/src-tauri/src/lib.rs)),
  så favoritter **kan ikke** skrives dit. De trenger egen skrivbar lagring.
- Valgt lagring: **Tauri Store-plugin** (`@tauri-apps/plugin-store` +
  `tauri-plugin-store`), som skriver en JSON-fil i appens data-katalog —
  robust mot at webview-cache tømmes. (Gjenbrukbart for handleliste senere.)
- Frontend bruker Svelte 5 `$state`-runer; ingen `localStorage`/store i bruk ennå.
- Oppskriftskort: `<article class="recipe-card" onclick={åpneOppskrift}>`
  ([+page.svelte:269](../../../kokebok-app/src/routes/+page.svelte)).
  Detalj-topplinje har «← Tilbake»-knapp (linje ~316). Sidebar-kategorier
  rendres rundt linje ~235.
- Backend `hent_oppskrifter` pagineres `(kategori, sok, side, perSide)` og
  kjenner ikke favoritter.

## Arkitektur

Favoritter er en liste med oppskrift-IDer. **All favoritt-logikk i frontend**;
backend får én ny les-kommando + plugin-registrering.

```
src/lib/favoritter.ts   ← tynn wrapper rundt Store-plugin
  favorittLast(): Promise<Set<number>>          – load('favoritter.json'), les 'ids'
  favorittToggle(id, settet): Promise<Set<number>>
                                                – muter Set + store.set('ids',[...]) + save(),
                                                  returnerer nytt Set (for $state-reaktivitet)
  (Set holdes i +page.svelte som $state)

+page.svelte
  let favoritter = $state<Set<number>>(new Set())
  onMount: favoritter = await favorittLast()
  stjerne på recipe-card (linje 269) + i detalj-topplinje (linje ~316)
  '⭐ Favoritter'-filter øverst i sidebar-kategoriene

lib.rs
  .plugin(tauri_plugin_store::Builder::default().build())   ← registrering
  #[tauri::command] hent_oppskrifter_by_ids(ids) -> Vec<kort>  ← ny kommando

Cargo.toml: + tauri-plugin-store
package.json: + @tauri-apps/plugin-store
capabilities/default.json: + "store:default"
```

### Tre isolerte deler

1. **`src/lib/favoritter.ts`** — innkapsler Store-API-et (load/set/save).
   Grensesnitt: `favorittLast()`, `favorittToggle(id, settet)`. Endres uten å
   røre UI. **Svelte 5-merknad:** `$state<Set>` reagerer ikke på `.add()/.delete()`
   alene — `favorittToggle` returnerer et **nytt** Set som tilordnes
   `favoritter = await favorittToggle(...)` for å trigge reaktivitet.
2. **Stjerne-knapp** — gjenbrukt markup på kort + detalj; leser
   `favoritter.has(id)`, kaller toggle.
3. **Favoritt-filter** — sidebar-valg som styrer rutenett-visningen via
   `hent_oppskrifter_by_ids`.

## Datahenting i favoritt-modus

Backend-pagineringen kjenner ikke favoritter, så favoritt-visningen bruker en
**ny kommando**:

```rust
#[tauri::command]
fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>) -> Result<Vec<Value>, String>
```
- Returnerer samme kortfelt som listen ellers (`id, slug, navn, type,
  porsjoner, tid, bilde`), via `WHERE id IN (...)`.
- Tom `ids` → tom liste (frontend viser «Ingen favoritter ennå»).
- Sortering: `ORDER BY navn COLLATE NOCASE` (som hovedlisten).

Flyt: «⭐ Favoritter» valgt → `hent_oppskrifter_by_ids([...favoritter])` → vis i
samme rutenett. Søkefeltet deaktiveres/skjules i favoritt-modus (v1).

## UI

**Stjerne-knapp:**
- På kort: liten ⭐/☆-knapp i hjørnet. Klikk toggler favoritt og **stopper
  event-propagering** (kortet åpner ellers detalj ved klikk).
- I detalj-topplinjen (ved «← Tilbake»): stjerne for den åpne oppskriften.
- Fylt ⭐ når favorisert, tom ☆ ellers. Varm palett / eksisterende CSS-variabler.

**Favoritt-filter:**
- «⭐ Favoritter» øverst i sidebar-kategorilisten (over «alle»), samme
  aktiv-stil som kategoriene.
- Tom liste → «Ingen favoritter ennå. Trykk ⭐ på en oppskrift for å legge den
  til.»

## Feilhåndtering

- Store-lasting feiler (manglende/korrupt fil) → start med tom favorittliste,
  logg til konsoll, ikke krasj. Favoritter er ikke kritiske data.
- `store.save()` feiler → toggle beholdes i minnet for økten, feil logges.
  Best effort.
- `hent_oppskrifter_by_ids` feiler → samme `console.error`-mønster som
  eksisterende `hent_oppskrift`-kall.

## Testing

Prosjektet har ingen frontend-testoppsett (kun pytest for prisskriptet).
Favoritt-logikken er enkel (Set + Store-kall). **Manuell verifikasjon i
`tauri dev`:**
- Stjern en oppskrift fra kort → stjernen fylles, detalj viser samme.
- Velg «⭐ Favoritter» → kun favoritter vises.
- Av-stjern → forsvinner fra favoritt-visningen.
- Restart appen → favoritter består (persistert til JSON).
- Tom favorittliste → vennlig melding, ingen krasj.

Ingen Vitest-oppsett innføres for denne funksjonen (bevisst — unngå ny
testinfrastruktur for en liten feature).

## Åpne detaljer for implementeringsplanen

- Eksakt Tauri Store v2-API verifisert: `import { load } from
  '@tauri-apps/plugin-store'`; `const store = await load('favoritter.json')`;
  `store.set('ids', [...])`; `store.get('ids')`; `store.save()`. Plugin
  registreres i lib.rs med `tauri_plugin_store::Builder::default().build()`;
  permission `store:default` i capabilities.
- `src/lib/`-katalogen finnes ikke ennå — opprettes for `favoritter.ts`.
