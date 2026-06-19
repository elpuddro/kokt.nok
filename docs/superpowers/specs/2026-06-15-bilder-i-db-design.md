# Bilder i databasen — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-15.

## Mål

Distribuere appen som **to sluttbruker-artefakter**: app-binæren + én `kokt.db`
med bildene innebygd. Ingen løs `bilder/`-mappe ved siden av. Dette oppfyller
backlog-idé #3 (bilder som BLOB) og legger grunnlaget for idé #4 (portabelt bygg,
egen sak).

## Bakgrunn / nåværende tilstand

- I dag tre ting: app, `kokt.db` (~11 MB, kun stier) og `bilder/` (4444 løse
  WebP, ~294 MB).
- `oppskrifter.bilde` er `TEXT` med relativ sti, f.eks.
  `bilder/{slug}.webp`. `slug` er unik (4444/4444), aldri null; `bilde` aldri
  null. Bildene lastes i frontend via `convertFileSrc` → asset-protokoll
  (`imgSrc` i `+page.svelte`).
- `kokt.db` er sporet i git; `bilder/` er gitignorert.
- DB åpnes `SQLITE_OPEN_READ_ONLY` (`lib.rs`), og i release ligger den i et
  ikke-skrivbart install-katalog.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Bildelagring | BLOB i DB, servert via Rust custom-protokoll `kbilde://` |
| Rekomprimering | 800→600px, WebP q78 (~294 MB → ~197 MB) |
| DB & git | Liten sti-DB (`kokt.db`) i git som kilde; fat `kokt-bundle.db` er et gitignorert byggartefakt |
| Dev vs release | Protokoll prøver DB-BLOB, faller tilbake til løs fil i dev |
| Byggpipeline | To frittstående Python-skript, 2-stegs manuell pakking |
| Favoritter | Uendret — blir i `favoritter.json` (Tauri Store) |

### Hvorfor favoritter IKKE flyttes inn i DB

Den bundlede DB-en er read-only og ligger i et ikke-skrivbart katalog (f.eks.
Program Files). Favoritter er per-bruker skrivedata og kan ikke lagres der. Å
legge dem «i en DB» ville kreve en *andre*, skrivbar DB i app-data — altså
fortsatt to DB-filer, mer maskineri, og oppnår ikke «én DB». Statisk innhold
(oppskrifter + bilder) er det som er read-only og som skal shippes; favoritter er
en annen kategori og blir i Store-fila.

### Måledata bak rekomprimering

Alle bilder er 800×800, allerede nær-optimal WebP (kvalitet alene gir ~0 gevinst;
dimensjon er hele spaken). Projisert full-sett (4444 bilder):

| | q82 | q78 | q72 |
|---|---|---|---|
| 800px (dagens) | 313 | 283 | 264 |
| 700px | 284 | 243 | 208 |
| **600px** | 231 | **197** | 169 |
| 512px | 181 | 155 | 132 |

Kort vises 220–320px, detalj-hero er 320px høy. 600px er fortsatt 2×-skarpt på
kort; eneste milde kompromiss er detalj-hero på stor HiDPI-skjerm. Valgt: 600px
q78 ≈ 197 MB.

## Arkitektur — tre lag

### Lag 1: Byggtids-dataprep (`scripts/`, Python)

**`scripts/recompress_bilder.py`** (engangs, in-place):
- For hver `data/bilder/*.webp`: skaler lengste side til 600px (Lanczos),
  re-enkod WebP q78 method=6, overskriv fila.
- Hopper over filer som allerede er ≤600px (re-kjør forringer ikke videre).
- Effekt: `bilder/` ~294 MB → ~197 MB. Gagner også dev (mindre fallback-filer).

**`scripts/bygg_bundle_db.py`** (kjøres før pakking):
- Kopierer `data/kokt.db` → `data/kokt-bundle.db` (muterer aldri git-kilden).
- Legger til kolonne `bilde_data BLOB` på `oppskrifter`.
- For hver rad: les `bilder/{slug}.webp`, lagre bytene i `bilde_data`.
- Resultat: `kokt-bundle.db` ≈ 197 MB, gitignorert.
- Verifikasjon i skriptet: alle rader har non-null `bilde_data`; stikkprøve på
  at BLOB-er dekoder som gyldig WebP; logg sluttstørrelse.

`kokt-bundle.db` legges i `.gitignore`. `tauri.conf.json` endres til å bundle
`data/kokt-bundle.db` som `kokt.db` og **fjerner `bilder/`-ressursen** (og
asset-protokoll-scope for bilder).

### Lag 2: Runtime bildeservering (Rust custom-protokoll)

Registrer URI-scheme `kbilde` på Tauri-builderen. Handler:
1. Parse oppskrift-**id** fra URL (`kbilde://localhost/{id}`).
2. Åpne DB (gjenbruk `db_path`/`open`).
3. **Prøv DB først:** `SELECT bilde_data FROM oppskrifter WHERE id = ?`. Hvis
   kolonnen finnes og BLOB-en er non-null (release): returner bytene med
   `Content-Type: image/webp`.
4. **Fil-fallback (dev):** hvis `bilde_data` mangler/er null: les
   `bilder/{slug}.webp` fra disk og returner bytene.
5. Ved bom: 404 → frontend viser emoji-placeholder.

Wrinkles:
- `bilde_data`-kolonnen finnes ikke i dev-DB-en (kun lagt til av
  `bygg_bundle_db.py`). Query må tåle manglende kolonne — sjekk kolonne-eksistens
  (f.eks. `PRAGMA table_info` én gang) og gå rett til fil-fallback i dev. Ingen
  feilstøy.
- Custom-protokoll på Windows/WebView2 bruker `http://kbilde.localhost/...` under
  panseret; `register_uri_scheme_protocol` håndterer plattformforskjellene.
  Capabilities-fila kan trenge scheme tillatt — verifiseres mot bundlet Tauri
  2-versjon under implementering.

Ytelse: ett protokoll-kall per synlig kort; handler gjør ett indeksert oppslag på
primærnøkkel. Én tilkobling per request først (matcher dagens per-kommando-mønster);
pooling er YAGNI nå.

### Lag 3: Frontend (`imgSrc`)

`imgSrc()` tar **id** i stedet for `bilde`-sti:
```ts
function imgSrc(id: number | null | undefined): string | null {
  if (id == null) return null;
  return `kbilde://localhost/${id}`;
}
```
Kallesteder: `imgSrc(r.bilde)` → `imgSrc(r.id)` (kort), `imgSrc(opp.bilde)` →
`imgSrc(opp.id)` (detalj-hero). `http`-passthrough-grenen og `resourceDir`/
`resolveResource`-maskineriet for bilder fjernes hvis det blir dødt (sjekkes).
`<img>` onerror/placeholder-fallback står — 404 gir naturlig emoji-placeholder.

## Testing & utrulling

- **Byggsjekk:** `cargo check` + `npm run build` etter hver task (ingen
  automatisk testsuite i prosjektet).
- **Dataprep-verifikasjon:** etter `bygg_bundle_db.py`: alle rader non-null
  `bilde_data`; stikkprøve at BLOB-er dekoder som gyldig 600px WebP;
  `kokt-bundle.db` ≈ 197 MB.
- **Manuell e2e (egentlig akseptanseport):** pakk appen, installer, bekreft at
  kort-thumbnails + detalj-hero rendres fra innebygd DB **uten `bilder/`-mappe**,
  og at install-katalogen kun har binæren + én `.db`. Kjør også
  `npm run tauri dev` for å bekrefte at fil-fallback fortsatt serverer bilder.

## Dokumentasjon

README oppdateres med 2-stegs pakkeflyt:
1. `python scripts/bygg_bundle_db.py` (etter evt. `recompress_bilder.py`).
2. `npm run tauri build`.

## Avgrensninger (ikke i denne saken)

- Handleliste (backlog #1) — egen brainstorming → spec → plan.
- Portabelt sidecar-bygg (backlog #4) — egen sak, bygger på denne.
