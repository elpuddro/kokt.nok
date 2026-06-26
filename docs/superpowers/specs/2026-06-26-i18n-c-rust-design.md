# Tospråklig app — Sub-prosjekt C: Rust + DB-kobling (#38c) — Design

## Mål

Alle Rust-kommandoer som returnerer tekstinnhold fra DB (oppskriftnavn, beskrivelse, trinn, ingrediensnavn) tar en `lang: String`-parameter og bruker `COALESCE(kolonne_en, kolonne)` for å returnere riktig språk. Sub-prosjekt C er avhengig av at sub-prosjekt B (DB-skjema + oversettelse) er gjennomført.

## Avhengigheter

- **Sub-prosjekt B må være kjørt** — kolonnene `navn_en`, `beskrivelse_en`, `tekst_en` (trinn), `navn_en` (ingredienser) må eksistere i DB.
- Sub-prosjekt A kan implementeres uavhengig — men hele #38 er ikke komplett før alle tre er på plass.

## Hvilke kommandoer endres

| Kommando | Tabeller berørt | Nye felt med COALESCE |
|----------|----------------|----------------------|
| `sok_oppskrifter` | `oppskrifter` | `COALESCE(o.navn_en, o.navn) AS navn` |
| `hent_oppskrift` | `oppskrifter`, `trinn`, `ingredienser` | navn, beskrivelse, trinn.tekst, ingrediens.navn |
| `hent_favoritter` | `oppskrifter` | `COALESCE(o.navn_en, o.navn) AS navn` |
| `hent_matplan` | `oppskrifter` | `COALESCE(o.navn_en, o.navn) AS navn` |
| `hent_lager_dekning` | `oppskrifter`, `ingredienser` | oppskriftnavn + ingrediensnavn |
| `get_kategorier` | `oppskrifter` | kategori-`type` er norsk nøkkel — **ikke endre** (frontend oversetter via `t()`) |

**`get_kategorier` berøres ikke** — frontend oversetter kategoristrenger via `t("cat_<slug>", lang)` (sub-prosjekt A). Kategoristrengen fra DB er bare en nøkkel.

## `lang`-parameter

Alle berørte kommandoer får:

```rust
#[tauri::command]
fn sok_oppskrifter(app: AppHandle, q: String, lang: String) -> Result<Vec<Oppskrift>, String> {
```

Inne i funksjonen bestemmer `lang` hvilken COALESCE-side som er aktiv:

```rust
let bruk_en = lang == "en";
```

Fordi SQLite ikke støtter betingede kolonner direkte, brukes en fast `COALESCE`-SQL som alltid fungerer — den engelske kolonnen er enten fylt (returnerer engelsk) eller NULL (faller tilbake til norsk):

```sql
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       COALESCE(o.beskrivelse_en, o.beskrivelse) AS beskrivelse,
       ...
FROM oppskrifter o
WHERE ...
```

`lang`-parameteren trenger altså ikke brukes til betinget SQL — `COALESCE` håndterer fallback automatisk. `lang` sendes likevel med i signaturen for fremtidig bruk (f.eks. tredje språk) og for klarhet.

## Endringer per kommando

### `sok_oppskrifter`

```rust
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       o.tid, o.porsjoner, o.type, o.kilde
FROM oppskrifter o
WHERE LOWER(COALESCE(o.navn_en, o.navn)) LIKE ?1
   OR LOWER(o.navn) LIKE ?1
ORDER BY ...
```

Merk: søket søker i begge språk (`OR LOWER(o.navn) LIKE ?1`) slik at norsk søk finner engelske oppskrifter og omvendt.

### `hent_oppskrift`

```rust
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       COALESCE(o.beskrivelse_en, o.beskrivelse) AS beskrivelse,
       o.tid, o.porsjoner, o.type, o.kilde,
       o.naering_energi, o.naering_protein, o.naering_fett, o.naering_karbo
FROM oppskrifter o
WHERE o.id = ?1
```

Trinn:
```rust
SELECT t.nummer,
       COALESCE(t.tekst_en, t.tekst) AS tekst
FROM trinn t
WHERE t.oppskrift_id = ?1
ORDER BY t.nummer
```

Ingredienser:
```rust
SELECT i.id,
       COALESCE(i.navn_en, i.navn) AS navn,
       oi.mengde, oi.enhet
FROM ingredienser i
JOIN oppskrift_ingredienser oi ON i.id = oi.ingrediens_id
WHERE oi.oppskrift_id = ?1
```

### `hent_favoritter`

```rust
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       o.tid, o.porsjoner, o.type
FROM oppskrifter o
WHERE o.id IN (...)
```

### `hent_matplan`

```rust
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       o.tid, o.porsjoner, o.type
FROM oppskrifter o
WHERE o.id = ?1
```

### `hent_lager_dekning`

```rust
SELECT o.id,
       COALESCE(o.navn_en, o.navn) AS navn,
       ...
FROM oppskrifter o
...
-- ingredienser i dekning-join:
SELECT COALESCE(i.navn_en, i.navn) AS navn, ...
FROM ingredienser i ...
```

## Frontend-kall — lang sendes med

I `+page.svelte` sendes `lang` med i alle berørte `invoke`-kall:

```ts
await invoke('sok_oppskrifter', { q: sokeTekst, lang });
await invoke('hent_oppskrift', { id: oppskriftId, lang });
await invoke('hent_favoritter', { ids: favorittIds, lang });
// osv.
```

`lang`-variabelen er allerede reaktiv `$state` (sub-prosjekt A). Siden `lang` sendes med ved hvert kall, trenger ikke Rust-laget å huske språkvalget — det er alltid frontend som bestemmer.

## `sok_ingredienser` (eksisterende kommando)

Kommandoen `sok_ingredienser` (lagt til i #30) returnerer ingrediensnavn for priser-autocompletе. Den bør også støtte lang:

```rust
#[tauri::command]
fn sok_ingredienser(app: AppHandle, q: String, lang: String) -> Result<Vec<String>, String> {
    ...
    let sql = "SELECT DISTINCT COALESCE(navn_en, navn) FROM ingredienser 
               WHERE LOWER(COALESCE(navn_en, navn)) LIKE ?1 
                  OR LOWER(navn) LIKE ?1 
               ORDER BY 1 LIMIT 20";
    ...
}
```

## Struct-er — ingen endring

Eksisterende Rust-struct-er (`Oppskrift`, `Trinn`, `Ingrediens` osv.) bruker feltnavnet `navn` (ikke `navn_en`). Det er korrekt — COALESCE i SQL aliaser resultatet som `navn`, så struct-en ser bare én `navn`-kolonne uansett språk. **Ingen struct-endring nødvendig.**

## Søkebidireksjonalitet

Søket (`sok_oppskrifter`) bruker:
```sql
WHERE LOWER(COALESCE(o.navn_en, o.navn)) LIKE ?1
   OR LOWER(o.navn) LIKE ?1
```

Dette gir:
- Norsk bruker søker «fårikål» → finner oppskrift selv om engelsk navn er «Mutton and cabbage stew»
- Engelsk bruker søker «mutton» → finner oppskrift fordi `navn_en` inneholder «mutton»
- Bidireksjonelt søk er konsistent for begge språk

## Testing

### Rust-tester (rustdoc/integration)

Rust har ikke enhetstester for SQL-logikk direkte. Test via:
1. Bygg appen med `cargo tauri dev`
2. Veksle språk i Innstillinger (sub-prosjekt A)
3. Verifiser at oppskriftnavn, beskrivelse, trinn og ingredienser bytter språk

### Automatisk verifisering

Etter sub-prosjekt B-scriptet:
```sql
-- Sjekk at COALESCE gir engelsk når tilgjengelig
SELECT id, navn, navn_en, COALESCE(navn_en, navn) AS valgt
FROM oppskrifter LIMIT 10;
```

Forventet: `valgt` = `navn_en` når `navn_en IS NOT NULL`, ellers `navn`.

## Migrasjonsrekkefølge

1. Kjør sub-prosjekt B (DB-kolonner + oversettelse)
2. Bytt inn i appen med oppdatert `kokt-bundle.db`
3. Implementer sub-prosjekt A (GUI `lang`-variabel)
4. Implementer sub-prosjekt C (Rust `lang`-parameter + COALESCE)
5. E2e-test: bytt til engelsk → alt innhold er på engelsk
