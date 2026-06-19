# 🍳 kokt.nok

Offline-først norsk kokebok-app for skrivebordet, med ~5962 oppskrifter
(matprat.no + godt.no). Bygget med **Svelte 5 + SvelteKit + Tauri 2**
(Rust-backend, rusqlite, SQLite-database).

Selve appen ligger i [`kokebok-app/`](kokebok-app/).

> **Designmål:** appen skal kunne kjøre helt offline på et svært
> personvernsensitivt sted. Distribusjon er én mappe (binær + database), uten
> installer og uten nettverk ved kjøring. Utvikler-/verktøyspor skrubbes ut av
> binærene før distribusjon — se skrubbe-porten under.

## Funksjoner

Bla i oppskrifter med bilder · søk på navn/ingrediens · favoritter ·
handleliste (skalert etter porsjoner, med prisestimat) · næringsberegning ·
egne notater · 11 temaer med sesong-/høytidsbytte + dark mode ·
kosthold- og allergifilter (BETA: halal-vennlig, vegetar, vegansk, glutenfri,
laktosefri, uten nøtter) · innebygde bilder via `kbilde://`-protokoll.

---

## Krav

- **Node.js** ≥ 18 og **npm**
- **Rust** (stable, via [rustup](https://rustup.rs)) + MSVC build tools (Windows)
- **Python** ≥ 3.10 (kun for næringsskriptet)
- WebView2-runtime (følger med Windows 11)

---

## Kjøre i utvikling

```bash
cd kokebok-app
npm install
npm run tauri dev
```

## Bygge installer

```bash
cd kokebok-app
npm run tauri build
```

Ferdig NSIS-installer havner i
`kokebok-app/src-tauri/target/release/bundle/nsis/Kokebok_1.0.0_x64-setup.exe`
(ca. 300 MB – databasen og bildene pakkes med).

---

## Pakking til distribusjon (2 steg)

Bildene ligger som løse WebP under `kokebok-app/src-tauri/data/bilder/` i
utvikling, men pakkes inn i databasen for distribusjon, slik at sluttbygget kun
er to filer: app-binæren + én `kokt.db`.

1. **Bygg bundle-databasen** (engangs per bildeendring):
   ```bash
   # valgfritt: rekomprimer bildene 800→600px først (sparer ~30 % plass)
   .venv/Scripts/python.exe scripts/recompress_bilder.py
   # generer kokt-bundle.db med bildene innebygd som BLOB
   .venv/Scripts/python.exe scripts/bygg_bundle_db.py
   ```
2. **Bygg appen:**
   ```bash
   cd kokebok-app && npm run tauri build
   ```
   `tauri.conf.json` bundler `kokt-bundle.db` som `kokt.db`. Ingen `bilder/`-mappe
   følger med — bildene serveres fra DB-en via `kbilde`-protokollen.

I `npm run tauri dev` finnes ikke `bilde_data`-kolonnen i sti-DB-en, så
bildehandleren faller tilbake til å lese de løse filene fra `data/bilder/`.

---

## Portabel distribusjon (Windows + Linux)

Lager en `portable/`-mappe med binær + én delt `kokt.db` (bilder innebygd),
kjørbar uten installasjon. Appen finner `kokt.db` ved siden av exe-en.

**Forutsetning:** bygg bundle-databasen først (`scripts/bygg_bundle_db.py`).

Bygg appen med Tauri-CLI-en (ikke `cargo build` direkte — `npm run tauri build`
aktiverer `custom-protocol` som hindrer at prosjektstien bakes inn i binæren):

```bash
cd kokebok-app && npm install
npm run tauri build
```

**Personvern (byggsti-remapping):** for å unngå at utviklerens brukernavn lekker
inn i binæren via panic-/debug-info, kopier
`kokebok-app/src-tauri/.cargo/config.toml.example` →
`.cargo/config.toml` og fyll inn dine egne stier. Fila er gitignorert (maskin-
spesifikk).

> **Skrubbe-verktøyet** (`bygg_portable.py` — pakker `portable/` og verifiserer
> at ingen personspor er bakt inn i binærene) holdes **utenfor dette repoet** av
> personvernhensyn, siden det inneholder deteksjons­mønstre med konkrete navn for
> en spesifikk distribusjon. Det vedlikeholdes lokalt.
Merk: webview-runtime må finnes på sluttbruker-maskinen (WebView2 på Windows,
WebKitGTK på Linux) — «portabel» = ingen installer, men OS-ets webview kreves.

---

## Data

- **Database:** `kokebok-app/src-tauri/data/kokt.db` – pakkes med appen som
  ressurs (bundles til `$RESOURCE/kokt.db`). **Ligger ikke i git** (regenererbar;
  se `.gitignore`).
  Tabeller: `oppskrifter`, `ingredienser`, `trinn`, `kategorier`, `naering`,
  `priser`, `ingrediens_tagg` (kosthold/diett/allergi).
- **Bilder:** `kokebok-app/src-tauri/data/bilder/` – komprimerte WebP-bilder,
  bundles inn i DB-en som BLOB for distribusjon (`bygg_bundle_db.py`).

> **⚠️ Bygging fra bunnen — kjent begrensning:** skriptene i `scripts/`
> **beriker en eksisterende `kokt.db`** (de oppretter ikke skjemaet og har ingen
> matprat-skraper for basis-oppskriftene). Du trenger derfor en base-`kokt.db`
> som utgangspunkt før `hent_godt.py`, `hent_naering.py`, `hent_priser.py` og
> `tagg_ingredienser.py` kan kjøres. En komplett «bygg fra null»-pipeline
> (skjema + full skraping) er en åpen oppgave i `docs/IDEER.md`.

### Oppdatere næringsdata (valgfritt)

Næringstabellen (`naering`) hentes fra [matvaretabellen.no](https://www.matvaretabellen.no)
(ingen API-nøkkel). Skriptet matcher ingredienser mot matvarer og fyller inn
energi/protein/fett/karbo/fiber per 100 g.

```bash
python scripts/hent_naering.py   # fra repo-roten; oppdaterer kokebok-app/src-tauri/data/kokt.db
```

`foods_cache.json` caches API-svaret lokalt. Sett `NAERING_LIMIT=N` for å
begrense antall ingredienser under testing. Etter en oppdatering må appen
bygges på nytt for at den nye `kokt.db` skal pakkes med.

### Oppdatere prisdata (valgfritt)

`priser`-tabellen hentes fra [kassal.app](https://kassal.app) (Kiwi + Coop
Extra). Skriptet matcher ingredienser mot butikkprodukter, parser pakkevekt fra
produktnavnet og regner billigste enhetspris. Appen viser et estimat per
oppskrift (total + per porsjon) med dekningsindikator.

```bash
python scripts/hent_priser.py        # fra repo-roten; oppdaterer data/kokt.db
```

API-nøkkel leses fra `KASSAL_API_KEY` (med innebygd fallback). Maks 60 API-kall
per minutt, så full kjøring (~7195 ingredienser × 2 kall) tar noen timer;
skriptet er gjenopptagbart (hopper over allerede-behandlede). `PRISER_LIMIT=N`
begrenser under testing. Etter oppdatering må appen bygges på nytt for at den
nye `kokt.db` skal pakkes med.

Den rene match-/parse-logikken ligger i `scripts/kassal.py` med tester i
`scripts/test_kassal.py` (`cd scripts && python -m pytest`).

---

## Skrape godt.no (valgfritt, privat bruk)

`scripts/hent_godt.py` henter oppskrifter (med 600px-bilder) fra godt.no inn i
`kokt.db` som en andre datakilde. Sitemap-drevet, respekterer robots.txt for egen
user-agent, rate-limiter og cacher i `scripts/godt_cache/`.

Krever **Pillow** (bildebehandling). Bruk samme Python som har avhengighetene –
typisk prosjektets `.venv` (ikke bare `py`):

```bash
# installer avhengigheter én gang:
.venv/Scripts/python.exe -m pip install -r scripts/requirements-dev.txt

# trygg første kjøring – 10 oppskrifter, sjekk resultatet i appen/DB:
.venv/Scripts/python.exe scripts/hent_godt.py --limit 10
# hele katalogen:
.venv/Scripts/python.exe scripts/hent_godt.py
```

Kjør på en egen git-branch og inspiser radtellingene før du committer (skriptet
endrer den sporede `kokt.db`). Etter skraping: kjør `hent_naering.py` og
`hent_priser.py` på nytt for å dekke de nye oppskriftene med næring/pris.

---

## Arkitektur

| Lag        | Fil                                   | Ansvar                                              |
|------------|---------------------------------------|-----------------------------------------------------|
| Frontend   | `src/routes/+page.svelte`             | Hele UI-et (rutenett, søk, detalj, porsjonsskalering, filtre) |
| Lib        | `src/lib/*.ts`                        | Store-wrappere + ren logikk (favoritter, handleliste, tema, notater, diett) |
| Stil       | `src/app.css` + `+page.svelte`        | Varm kokebok-palett + temaer (`[data-tema]`)        |
| Backend    | `src-tauri/src/lib.rs`                | DB-kommandoer (kategorier, liste m/filter, full oppskrift) + `kbilde://`-protokoll |
| Config     | `src-tauri/tauri.conf.json`           | Vindu, ressurser, asset-protokoll, NSIS             |

Funksjoner går gjennom brainstorming → spec → plan → implementering.
Design-spesifikasjoner og implementeringsplaner ligger i
[`docs/superpowers/`](docs/superpowers/); backloggen i
[`docs/IDEER.md`](docs/IDEER.md).

---

## Lisens

Koden er lisensiert under **MIT** — se [`LICENSE`](LICENSE).

Oppskriftsdata © matprat.no og © godt.no · næringsdata © matvaretabellen.no ·
prisdata © kassal.app (Kiwi / Coop Extra). Disse dataene tilhører sine kilder og
er **ikke** dekket av MIT-lisensen.
