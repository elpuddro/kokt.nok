# Design: Vinanbefaling fra Vinmonopolet (#19)

**Dato:** 2026-06-22
**Status:** Klar for implementering

---

## Oversikt

Skrap hele Vinmonopolets sortiment (vin, øl, likør, aperitif) inn i kokt.db som statisk tabell. Vis de 3 beste drikkevarene for en oppskrift bak en `🍷 Vinforslag`-knapp i detaljvisningen. Match basert på oppskriftstype (kategori-map) boosted av nøkkelingredienser.

---

## Datamodell

### Ny tabell: `viner`

```sql
CREATE TABLE IF NOT EXISTS viner (
    id          INTEGER PRIMARY KEY,
    varenummer  TEXT UNIQUE NOT NULL,
    navn        TEXT NOT NULL,
    produsent   TEXT,
    land        TEXT,
    varetype    TEXT,
    druetype    TEXT,
    matpasning  TEXT   -- JSON-array av tags, f.eks. '["fisk","skalldyr"]'
);
CREATE INDEX IF NOT EXISTS idx_viner_varetype ON viner(varetype);
```

`matpasning` lagres som JSON-tekst (samme mønster som ingrediens_tagg). Feltet er NULL hvis Vinmonopolet ikke oppgir matpasning for produktet.

---

## Skraper: `scripts/hent_viner.py`

Bruker Vinmonopolets offisielle produkt-API (`apis.vinmonopolet.no`). Krever en **gratis API-nøkkel** som hentes på `developer.vinmonopolet.no` (registrering, ingen kostnad). Nøkkelen sendes som header `Ocp-Apim-Subscription-Key`. Kjøres én gang av utvikler før bundle-bygg — kokt.db er gitignored men selve skriptfilen commites.

**API-endepunkt:** `GET https://apis.vinmonopolet.no/products/v0/details-normal?maxResults=500&start=0`
Paginerer med `start`-parameter inntil alle produkter er hentet.

**Merk om matpasning:** API-et returnerer `description`-feltet (stilbeskrivelse) som fritekst, f.eks. "Passer til pasta, pizza og lette kjøttretter." Det finnes ingen strukturerte matpasnings-tags. Skraperen ekstraherer nøkkelord fra friteksten med en regelbasert parser og lagrer som JSON-array.

**Fritekst-parser — nøkkelord som mappes til tags:**
- pasta, pizza, taco, tapas → `pasta`
- fisk, sjømat, skalldyr, laks, torsk → `fisk`
- kylling, fjærkre → `fjærkre`
- lam, vilt, hjort, elg → `vilt`
- biff, entrecôte, oksekjøtt, storfe → `storfe`
- svin, ribbe, koteletter → `svin`
- grønnsaker, vegetar, salat → `grønnsaker`
- dessert, kake, sjokolade, søtt → `dessert`
- aperitif, forrett, tapas → `aperitif`
- asiatisk, wok, thai, indisk → `asiatisk`

Hvis fritekst er tom eller ingen nøkkelord matcher → `matpasning = NULL`.

**Kategorier som hentes** (filtrert på `mainCategory.name`):
- Rødvin, Hvitvin, Rosévin, Musserende, Dessertvin, Sterkvin
- Øl og Cider
- Likør, Aperitif, Brennevin

**Felter som lagres per produkt:**
- `varenummer` — Vinmonopolets unike ID (`code`-feltet)
- `navn` — produktnavn
- `produsent` — produsent/merkevare
- `land` — opprinnelsesland
- `varetype` — normalisert type (se under)
- `druetype` — druesorter som kommaseparert streng (NULL for øl/likør)
- `matpasning` — JSON-array av ekstraherte tags (NULL hvis ingen treff)

**Normaliserte varetyper** (brukt for ikon-valg i UI):
- `rodvin`, `hvitvin`, `rose`, `musserende`, `dessertvin`, `sterkvin`
- `ol`, `cider`
- `likor`, `aperitif`, `brennevin`

**Skjema-mønster:** SCHEMA-konstant med `CREATE TABLE IF NOT EXISTS` + index, kjøres ved oppstart av skriptet (samme som `hent_naering.py`).

**Estimert volum:** ~15 000 produkter.

---

## Match-logikk: `lib.rs`

### Ny Tauri-kommando: `vin_forslag(oppskrift_id: i64) -> Result<Vec<VinForslag>, String>`

```rust
struct VinForslag {
    id: i64,
    navn: String,
    produsent: Option<String>,
    land: Option<String>,
    varetype: String,
    druetype: Option<String>,
}
```

### Algoritme

1. **Hent oppskrift** — les `type` og ingrediensnavn for `oppskrift_id` fra DB.

2. **Kategori-tags** — slå opp oppskriftstype i hardkodet map → liste av relevante matpasnings-tags og foretrukne varetyper:

   | Oppskriftstype | Matpasnings-tags | Foretrukne varetyper |
   |---|---|---|
   | Fisk, Sjømat, Hele fileter | fisk, skalldyr, sjømat | hvitvin, rose, musserende |
   | Pasta, Pizza | pasta, nudler | hvitvin, rodvin, ol |
   | Middag, Biffer, Steker, Koteletter | kjøtt, storfe, svin | rodvin |
   | Gryter, Ovnsretter | kjøtt, grønnsaker | rodvin, hvitvin |
   | Kyllingfilet, Grillet kylling | fjærkre, kylling | hvitvin, rose, rodvin |
   | Vilt, Grillspyd | vilt, storfe | rodvin |
   | Vegetar | grønnsaker, sopp | hvitvin, rose, ol |
   | Wok, Panneretter | asiatisk, krydret | hvitvin, ol |
   | Dessert, Kaker, Bakst | dessert, søtt | dessertvin, musserende, likor |
   | Forretter, Snacks | aperitif, lett | musserende, aperitif, ol |
   | (fallback) | — | rodvin, hvitvin |

3. **Ingrediens-boost-nøkkelord** — hardkodet map ingrediens-token → matpasnings-tag (samme normaliserte tags som skraperen bruker):
   - laks, ørret, torsk, sei, hyse → `fisk`
   - reke, krabbe, blåskjell, hummer → `skalldyr`
   - kylling → `fjærkre`
   - lam, fårikål → `vilt`
   - biff, entrecôte, indrefilet, oksekjøtt → `storfe`
   - svinekjøtt, ribbe, nakkekoteletter → `svin`
   - sopp → `sopp`
   - sjokolade, vanilje, krem → `dessert`

4. **Scoring** — for hver vin i DB:
   - Base-score: antall matpasnings-tag-overlapp med kategori-tags × 10
   - Boost: antall ingrediens-nøkkelord-treff × 10
   - Foretrukket varetype-bonus: +5 hvis varetypen er i foretrukne-lista
   - Viner med score 0 ekskluderes

5. **Returner topp 3** — sorter DESC på score, ta de 3 øverste.

**Ingen nettverkskall** — alt fra kokt.db. Responstid ~5–10 ms.

---

## Frontend: `+page.svelte`

### Knapp i detaljvisningen

Plassering: under næringsinformasjon-seksjonen, over notater.

```
[🍷 Vinforslag]   ← toggle-knapp, skjult hvis ingen treff
```

Knappen vises bare hvis `vinForslag.length > 0`. Tilstand: `let vinApen = $state(false)`.

### Ekspandert visning

3 kort i CSS grid (`repeat(auto-fit, minmax(140px, 1fr))`), samme stil som næringskort:

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│     🍷      │  │     🥂      │  │     🍺      │
│  Barolo     │  │ Chablis     │  │ Nogne ø     │
│ Antinori    │  │ Brocard     │  │ Norge       │
│ Italia      │  │ Frankrike   │  │             │
│ Nebbiolo    │  │ Chardonnay  │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

**Ikon per varetype:**
- `rodvin` → 🍷
- `hvitvin`, `musserende`, `sterkvin`, `dessertvin` → 🥂
- `rose` → 🌸
- `ol`, `cider` → 🍺
- `likor`, `aperitif`, `brennevin` → 🍸

### State og dataflyt

```typescript
let vinForslag = $state<VinForslag[]>([]);
let vinLaster = $state(false);
let vinApen = $state(false);
let vinForOppskriftId = $state<number | null>(null);

async function lastVinForslag(id: number) {
    if (vinForOppskriftId === id) return; // allerede lastet for denne oppskriften
    vinForslag = [];
    vinApen = false;
    vinLaster = true;
    vinForslag = await invoke<VinForslag[]>("vin_forslag", { oppskriftId: id });
    vinForOppskriftId = id;
    vinLaster = false;
}
```

`lastVinForslag` kalles når detaljvisningen åpnes (samme som næringsinformasjon lastes). Cache nullstilles ved oppskriftsbytte via `vinForOppskriftId`. Knappen vises/skjules basert på `vinForslag.length > 0` etter lasting.

---

## Testplan

- **`hent_viner.py`**: kjøres manuelt, verifiser at tabellen populeres og matpasning-JSON er gyldig
- **`vin_forslag`-kommando**: unit-test i Rust med mock-data (fisk-oppskrift → hvitvin, kjøttrett → rødvin, dessert → dessertvin/musserende)
- **Frontend**: manuell e2e — åpne fiskerett, klikk knapp, verifiser 3 kort med riktige ikoner

---

## Avgrensninger

- Ingen pris vises
- Ingen lenke til Vinmonopolet
- Ingen Vinmonopolet-logo
- Ingen live API-kall fra appen — alt er statisk i DB
- Aldersgrense-varsling er ikke nødvendig (appen viser bare produktnavn, ikke lenke til kjøp)
- `kokt-bundle.db` må rebygges med `bygg_bundle_db.py` etter at `hent_viner.py` er kjørt

---

## Filer som endres/opprettes

| Fil | Endring |
|---|---|
| `scripts/hent_viner.py` | Ny — skraper |
| `kokebok-app/src-tauri/src/lib.rs` | Ny kommando `vin_forslag`, nye structs, kategori-map |
| `kokebok-app/src/routes/+page.svelte` | Knapp + vinforslag-seksjon i detaljvisning |
