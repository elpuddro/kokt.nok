# Prisestimat for oppskrifter — design

**Dato:** 2026-06-12
**Status:** Godkjent, klar for implementeringsplan

## Mål

Estimere omtrentlig kostnad for hver oppskrift ved å koble ingrediensene mot
oppdaterte matvarepriser fra [kassal.app](https://kassal.app/docs/api.json).
Vise total kostnad og kostnad per porsjon i oppskrift-detaljvisningen, med en
ærlig indikasjon på hvor stor andel av ingrediensene som faktisk ble priset.

Estimatet er bevisst omtrentlig (tilde-merket), ikke en fasit.

## Ikke-mål (YAGNI)

- Ikke live API-kall fra appen ved kjøring.
- Ikke prissammenligning på tvers av alle butikker — kun Kiwi og Coop Extra.
- Ikke handleliste-funksjonalitet (kan bli en senere idé).
- Ikke prishistorikk/grafer.

## Arkitektur

Samme mønster som eksisterende næringsdata: et offline Python-skript bygger en
pris-cache i `kokt.db`; appen leser bare fra DB. **API-nøkkelen lever kun i
skriptet (lest fra miljøvariabel), aldri i klient-koden** — en Tauri-app kan
dekompileres, så nøkkelen skal ikke bakes inn.

```
scripts/hent_priser.py  ──(≤60 kall/min, store=KIWI + COOP_EXTRA)──>  kassal.app/api/v1/products
        │  streng match (hodeord = første token i produktnavn), parse vekt fra navn
        │  regn enhetspris selv (current_price / parset mengde), velg billigste av Kiwi/Xtra
        ▼
   kokt.db: ny tabell `priser`
        │
        ▼
   src-tauri/src/lib.rs: hent_oppskrift beregner kostnad i samme SQL-stil som næring
        │  (mengde × enhet-konvertering × kilopris), returnerer pris-objekt
        ▼
   src/routes/+page.svelte: "~145 kr · ~36 kr/porsjon · 8 av 10 priset",
        skalerer med eksisterende porsjonsjustering
```

### Fire isolerte deler

1. **`scripts/hent_priser.py`** — henter, matcher, cacher. Gjenbruker
   *infrastrukturen* fra `hent_naering.py` (rate-limit-sleep, 429-backoff,
   `INSERT OR REPLACE`-gjenopptak, UTF-8-fiks) — men **ikke** difflib-fuzzy:
   butikknavn er støyete (merke + vekt), så fuzzy lager flere feiltreff. Her
   kreves streng token-match (se «Bevist mekanikk»).
2. **`priser`-tabellen** — datakontrakt mellom skript og app.
3. **Kostnadsberegning i `lib.rs`** — speiler eksisterende nærings-SQL.
4. **UI-visning i `+page.svelte`** — leser ferdig beregnet tall.

## Datamodell

Ny tabell i `kokt.db` (DB-en ligger nå i `kokebok-app/src-tauri/data/kokt.db`):

> **Verifisert mot ekte API-kall (2026-06-12):** kassal.app sitt
> `current_unit_price` (kilopris) og `weight`/`weight_unit` er `null` for
> praktisk talt alle produkter — også på detalj-endepunktet. Vi kan derfor
> **ikke** bruke kilopris fra APIet. I stedet **parser vi mengde+enhet ut av
> produktnavnet** ("Hvetemel Siktet 1kg", "Gulrot 400g", "Egg ... 18stk") og
> regner enhetsprisen selv fra `current_price`. Se "Bevist mekanikk" under.

```sql
CREATE TABLE IF NOT EXISTS priser (
    ingredient_navn  TEXT PRIMARY KEY,  -- LOWER(TRIM(navn)), samme nøkkel som naering
    produkt_navn     TEXT,              -- hva vi matchet mot (innsyn/feilsøk)
    butikk           TEXT,              -- 'KIWI' eller 'COOP_EXTRA' (den billigste)
    pakkepris        REAL,              -- current_price fra APIet (kr for hele pakka)
    pakke_mengde     REAL,              -- mengde parset fra produktnavn (i basis-enhet)
    enhetsklasse     TEXT,              -- 'g' | 'ml' | 'stk' (hva pakke_mengde er målt i)
    enhetspris       REAL,              -- pakkepris / pakke_mengde (kr per g/ml/stk) ← brukes i beregning
    oppdatert        TEXT               -- ISO-dato; hvor ferske prisene er
);
```

`enhetspris` er forhåndsberegnet i skriptet (kr per gram / ml / stk), så
`lib.rs` bare ganger med ingrediensmengden konvertert til samme `enhetsklasse`.

Nøkkelen `LOWER(TRIM(navn))` er **identisk med `naering`-tabellen**, så `lib.rs`
joiner prisene på akkurat samme måte som næring allerede gjør.

## Skript: hent_priser.py

**API:** `GET https://kassal.app/api/v1/products?search=<navn>&store=<KODE>`
- Bearer-autentisering. API-nøkkel leses fra miljøvariabel
  (f.eks. `KASSAL_API_KEY`), ikke hardkodet.
- Butikk-koder: `KIWI` og `COOP_EXTRA`.
- Søk krever min. 3 tegn.

### Bevist mekanikk (prototypet mot live API)

Hovedmålet er **presisjon, ikke dekning**: et bom er ufarlig (vises ærlig som
«ikke priset»), men et feiltreff er gift (gir et troverdig tall bygget på feil
produkt). Derfor er gaten streng og forkaster ved tvil.

**Per *distinkt* ingrediensnavn (~7195 — ikke per rad):**

1. **Hodeord:** ta ingrediensnavnet, strip tilberednings-prefiks
   (`smeltet`, `finhakket`, `hakket`, `revet`, `grovhakket`, `oppmalt`, `knust`,
   `kvernet`, `kokt`, `stekt`, `frisk`, `fersk`), bruk første gjenværende ord.
   Send hodeordet **verbatim med norske tegn** (`smør`, ikke `smor`) som søk.
   Hopp over hvis < 3 tegn (API-krav).
2. **Søk:** `GET /products?search=<hodeord>&store=KIWI` og `&store=COOP_EXTRA`,
   `size=5` (2 kall).
3. **Match-gate (presisjon):** behold kun produkter der hodeordet er
   **første token** i produktnavnet (`toks[0] == hodeord`, tokens = `[a-zæøå]+`).
   Dette forkaster «Potetgull Salt&Pepper» for `salt` og «Olivero Smør &
   Olivenolje» for `smør`, men beholder «Bakepulver 250g», «Egg 18stk»,
   «Smør Usaltet 250g Tine».
4. **Vekt-parsing:** parse `(tall)(kg|g|hg|l|dl|cl|ml|stk)` fra produktnavnet
   (siste forekomst), normaliser til basis: g (kg×1000, hg×100), ml (l×1000,
   dl×100, cl×10), eller stk. Ingen parsbar vekt → forkast produktet.
5. **Enhetspris:** `current_price / pakke_mengde` → kr per g/ml/stk, med
   `enhetsklasse` = g/ml/stk.
6. **Velg billigste** `enhetspris` på tvers av Kiwi/Xtra (ingen kryssing av
   enhetsklasser — sammenlign bare like klasser; lib.rs velger riktig klasse
   ved beregning).
7. Ingen match som passerer gaten → rad med NULL `enhetspris` (teller mot
   dekning).

**Verifisert resultat** (oppskrift «Bananpannekaker», 6 porsjoner): bakepulver,
egg (2,22 kr/stk via 18-pakke), smør (smeltet→Smør Usaltet Tine) priset
korrekt; salt/melk/hvetemel/banan forkastet/upriset (riktig — ingen
feiltreff). **0 falske treff.**

**Robusthet** (speiler hent_naering.py):
- `INSERT OR REPLACE`, hopper over allerede-matchede → gjenopptagbar.
- `PRISER_LIMIT`-miljøvariabel for testing.
- Rate-limit: sov for å holde ≤60 kall/min; håndter `429 Too Many Requests`
  med backoff (respekter evt. `Retry-After`).
- UTF-8 stdout/stderr (samme Windows-fiks som hent_naering.py).

**Omfang:** Full kjøring av alle ~7195 distinkte ingredienser. 2 kall ×
7195 ÷ 60/min ≈ ~4 timer. Gjenopptagbar, så den kan kjøres i flere økter.

## Beregning i lib.rs

Ny blokk i `hent_oppskrift`, samme stil som nærings-SQL-en (lib.rs, nærings-CASE
rundt linje 206). For hver ingrediens med en `priser`-rad der `enhetspris` ikke
er NULL:

- Konverter ingrediensens `mengde`+`enhet` til en **basis-mengde i samme
  `enhetsklasse`** som pris-raden:
  - `enhetsklasse = 'g'`: `g`→×1, `kg`→×1000, `hg`→×100, `ss`→×15, `ts`→×5,
    `klype`→×1, `never`→×5.
  - `enhetsklasse = 'ml'`: `ml`→×1, `dl`→×100, `l`→×1000, `cl`→×10, `ss`→×15,
    `ts`→×5.
  - `enhetsklasse = 'stk'`: ingrediens-enhet `stk.`/`stk`/`` (tom)→×mengde.
- **Kostnad** = `basis_mengde × enhetspris`. Summer over alle prisede
  ingredienser.
- **Hvis ingrediensens enhet ikke passer pris-radens `enhetsklasse`** (f.eks.
  mel i `dl` mot et produkt parset i `g`, eller banan i `stk` mot et produkt i
  `g`): ingrediensen telles som **ikke priset** (mot dekning). Dette er den
  kjente, aksepterte dekningsgrensen — bedre å utelate enn å gjette feil.

Returnerer `{ totalt, per_porsjon, priset, totalt_antall, oppdatert }`, eller
`Null` hvis 0 ingredienser kunne prises (samme mønster som næring ved 0 energi).

### Kjente dekningsgrenser (akseptert, ikke v1-blokkere)

Bevisst utelatt fra v1 for å holde presisjonen høy og scope bundet:

- **Volum→vekt for tørrvarer:** mel/sukker oppgis i `dl` i oppskrifter, men
  selges i `g`. Uten en tetthet (mel ~0,55 g/ml) prises de ikke. Kan legges til
  senere som en liten tetthets-tabell.
- **Telleenhet→vekt for grønnsaker:** «2 stk gulrot» mot et produkt i `g`.
  En liten, konservativ vekt-tabell (løk≈110g, gulrot≈75g, paprika≈150g,
  tomat≈100g, banan≈120g) kan legges til senere. *Telleenhet→telleenhet*
  (egg 18stk) fungerer allerede uten tabell.
- Disse gjør at dekningen blir < 100 %, men det vises ærlig («X av Y priset»),
  i tråd med målet.

**Retur-objekt:**

```json
{ "totalt": 22.0, "per_porsjon": 3.7,
  "priset": 3, "totalt_antall": 7, "oppdatert": "2026-06-12" }
```

`per_porsjon` = `totalt / oppskriftens porsjoner`.

## UI i +page.svelte

I oppskrift-detaljvisningen, ved siden av næringsboksen, i den varme paletten:

```
💰 Estimert kostnad
~145 kr · ~36 kr/porsjon
8 av 10 ingredienser priset
```

- Tilde-tegn signaliserer «estimat».
- Dekning vises som ærlig brøk («8 av 10 ingredienser priset»).
- **Total** skalerer med den eksisterende porsjonsjusteringen (samme
  `skalering`-faktor som ingrediensmengdene): justerer brukeren opp til dobbel
  porsjon, dobles totalen.
- **Per-porsjon** holder seg stabil uansett porsjonsjustering (kostnad per
  porsjon er den samme om du lager 4 eller 8 porsjoner) — den er
  total-ved-grunnporsjon ÷ grunn-porsjoner.
- `pris === null` → vis ingenting (eller diskré «Pris utilgjengelig»).

## Nøkkelhåndtering

- API-nøkkelen er **ikke** sensitiv (bekreftet av bruker) — ingen regenerering
  nødvendig.
- Av ren kodehygiene leses nøkkelen likevel fra miljøvariabel `KASSAL_API_KEY`
  med en innebygd fallback-konstant i skriptet, slik at skriptet kan kjøres
  uten oppsett. Den hører hjemme i skriptet, ikke i frontend/Tauri-binæren
  (der hører den ingen steder hjemme — appen gjør ingen API-kall).
- `.gitignore` dekker allerede `foods_cache.json` / `.cache/`; et evt.
  `priser_cache.json` legges til samme mønster.

## Verifiserte API-fakta (avklart 2026-06-12)

- Respons-wrapper: `response["data"]` er produkt-arrayet. `store` er et **objekt**
  (`{name, code, url, logo}`), ikke array.
- `current_price` er satt; `current_unit_price`, `weight`, `weight_unit` er
  `null` overalt (også detalj-endepunkt) → derav navn-parsing.
- Søk må bruke korrekt norsk staving (`smør`, ikke `smor` — sistnevnte gir
  tomt resultat). Ingrediensnavnene i DB har allerede riktige tegn.
- Søk krever ≥ 3 tegn. `store`-koder: `KIWI`, `COOP_EXTRA`.
