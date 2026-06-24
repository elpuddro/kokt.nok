# Høytid og sesongoppskrifter Design

**Dato:** 2026-06-24
**Backlog:** #6 (ukesmeny utvidet) + #23 (sesong- og høytidsspesifikke forslag)

## Mål

Forsiden og matplanleggeren blir høytidsbevisste: i høytidsperioder viser forsiden sesong-kurerte retter i stedet for tidsbaserte forslag, og matplanleggeren får en sesong-toggle som vekter høytidsretter høyere i ukemenyen.

## Arkitektur

Høytidstagning skjer offline via Python-scripts (nøkkelordregler + manuell kurasjon) og skrives til en ny `høytid`-kolonne i `kokt.db`. Dato-logikken (hvilken høytid er aktiv nå?) porteres fra `tema-logikk.ts` til Rust som en ren funksjon `hoytid_aktiv()`. Frontend grener på denne verdien for forside og matplanlegger-toggle.

**Tech Stack:** Python (tagging-scripts), Rust (`lib.rs`), Svelte 5 runes, Tauri Store (`plan.json`), SQLite (`kokt.db`)

## Global Constraints

- `kokt.db` er **read-only** i appen — tagging skjer kun via offline Python-scripts
- Svelte 5 runes kun: `$state`, `$derived` — ingen `$:`, ingen `writable()`
- Tauri Store: `load("plan.json")`, singleton-mønster som resten av appen
- Ingen nye Tauri-kommandoer utover `hoytid_aktiv` + utvidelse av eksisterende
- CSS-variabler fra `app.css`: `--card`, `--text-muted`, `--border`, `--surface`, `--bg`, `--text`, `--radius-sm`, `--font-ui`
- `kokt.db` er delt mellom dev og portable — scripts må kjøres eksplisitt, ikke automatisk ved build

## Høytider som støttes

| Nøkkel | Navn | Datovindu |
|---|---|---|
| `valentins` | Valentinsdag | 7.–14. feb |
| `paske` | Påske | Palmesøndag → 2. påskedag (Computus) |
| `mai17` | 17. mai | 10.–18. mai |
| `sankthans` | Sankthans | 20.–24. jun |
| `farikaal` | Fårikålens dag | Siste torsdag i sept ± 3 dager |
| `halloween` | Halloween | 24.–31. okt |
| `jul` | Jul | 1. des – 6. jan |

Utenfor alle høytidsvindu: vanlig tidsbasert forside, sesong-toggle grået ut.

## Datamodell

### Ny kolonne i `kokt.db`

```sql
ALTER TABLE oppskrifter ADD COLUMN hoytid TEXT;
```

Verdier: kommaseparert streng av høytidsnøkler, f.eks. `"jul"`, `"jul,valentins"`, eller NULL.

Spørring i Rust: `INSTR(',' || hoytid || ',', ',' || ? || ',') > 0` (fungerer korrekt selv for enkelt-verdier uten ledende/etterfølgende komma).

### `data/hoytid_forslag.json`

Mellomformat for kurasjon — scripts skriver hit, du redigerer, `importer_hoytid.py` leser:

```json
{
  "1234": ["jul"],
  "5678": ["paske", "mai17"],
  "9012": ["farikaal"]
}
```

Nøkkel er oppskrift-id som streng. Kun oppskrifter med minst én høytid er med.

## Moduler

### `scripts/tagg_hoytid.py` (ny)

Kjøres fra repo-roten: `python scripts/tagg_hoytid.py`

- Leser alle oppskrifter fra `kokt.db` (navn + ingredienser)
- Kjører nøkkelordregler per høytid (se under)
- Skriver `data/hoytid_forslag.json` — **overskriver ikke eksisterende manuell kurasjon** (merge: eksisterende manuell tagging beholdes, nye regler legges til)
- Printer statistikk: antall tagget per høytid

**Nøkkelordregler (søker i navn + ingrediensnavn, case-insensitiv):**

| Høytid | Nøkkelord |
|---|---|
| `jul` | pinnekjøtt, ribbe, juleskinke, lutefisk, rakfisk, pepperkake, julekake, multekrem, riskrem, risgrøt, gløgg, julemat, julen, advent |
| `paske` | lam, påskelam, påske, seterrømme, fårikål (nei — det er høst), appelsinkake |
| `mai17` | bløtkake, jordbær, pølse, nasjonaldag, 17. mai, bunad |
| `sankthans` | jordbær, rømme, grillmat, spekemat, rømmegrøt, sankthans, midsommer, bål |
| `farikaal` | fårikål, lam og kål, får i kål |
| `halloween` | gresskar, pumpkin, halloween, skumle, spøkelse |
| `valentins` | sjokolade, bær, champagne, hjerte, valentins, romantisk, tiramisu, fondant |

### `scripts/importer_hoytid.py` (ny)

Kjøres etter kurasjon: `python scripts/importer_hoytid.py`

- Leser `data/hoytid_forslag.json`
- Setter `hoytid`-kolonnen for alle id-er i filen (NULL for de som ikke er med)
- Idempotent: trygt å kjøre flere ganger
- Printer antall oppdaterte rader

### `scripts/test_tagg_hoytid.py` (ny)

Node-stil unit-tester med `assert` — samme mønster som `test_tagg_ingredienser.py`:

- 7 tester: én per høytid, sjekker at typisk nøkkelord matcher
- 2 negativtester: "vanlig kyllingrett" matcher ingen høytid; "fårikål" matcher ikke påske

### Rust (`src-tauri/src/lib.rs`)

#### Ny kommando: `hoytid_aktiv`

```rust
#[tauri::command]
fn hoytid_aktiv() -> Option<String>
```

Returnerer gjeldende høytidsnøkkel (f.eks. `"jul"`) eller `None`. Ren funksjon, ingen DB-kall.

**Dato-logikk (portert fra `tema-logikk.ts`):**

```rust
fn paaskedag(aar: i32) -> (u32, u32) // returnerer (maaned, dag) for 1. påskedag

fn hoytid_aktiv_dato(maaned: u32, dag: u32, ukedag: u32, aar: i32) -> Option<String>
```

Sjekker i prioritert rekkefølge:
1. Valentinsdag: feb 7–14
2. Påske: palmesøndag (påske − 7 dager) → 2. påskedag (påske + 1 dag)
3. 17. mai: mai 10–18
4. Sankthans: jun 20–24
5. Fårikålens dag: siste torsdag i september ± 3 dager
6. Halloween: okt 24–31
7. Jul: des 1 – jan 6

#### Utvidet: `forside_oppskrifter`

Ny parameter `hoytid: Option<String>`. Hvis `Some(h)`:

```sql
WHERE INSTR(',' || hoytid || ',', ',' || ? || ',') > 0
```

i stedet for type-filter og nattFilter-logikk. Returnerer tilfeldig utvalg (samme `ORDER BY RANDOM() LIMIT 20` som i dag).

#### Utvidet: `generer_matplan`

Ny parameter `hoytid: Option<String>`. Scoringsjustering i `score()`-funksjonen:

```rust
if let Some(ref h) = hoytid {
    if let Some(ref opp_hoytid) = kandidat.hoytid {
        if opp_hoytid.split(',').any(|t| t.trim() == h) {
            score += 50.0;
        }
    }
}
```

`Kandidat`-struct får nytt felt `hoytid: Option<String>` hentet fra DB.

### Frontend (`+page.svelte`)

#### `lastForside()`

```typescript
const aktivHoytid = await invoke<string | null>("hoytid_aktiv");
if (aktivHoytid) {
    forsideOppskrifter = await invoke("forside_oppskrifter", { hoytid: aktivHoytid });
} else {
    // eksisterende tidsbasert logikk uendret
}
```

#### Høytidsbanner

Over kortgriddet på forsiden, vises kun når `aktivHoytid !== null`:

```html
<div class="hoytid-banner">🎄 Juleoppskrifter</div>
```

Emoji og tekst per høytid — en `HOYTID_BANNER`-konstant i Svelte:

```typescript
const HOYTID_BANNER: Record<string, string> = {
  jul: "🎄 Juleoppskrifter",
  paske: "🐣 Påskeoppskrifter",
  mai17: "🇳🇴 17. mai-mat",
  sankthans: "🔥 Sankthansmat",
  farikaal: "🍲 Fårikålens dag",
  halloween: "🎃 Halloweenmat",
  valentins: "❤️ Valentinsmiddag",
};
```

#### Sesong-toggle i matplanleggeren

Ny state: `planSesong = $state(false)` — lastet fra `plan.json` nøkkel `"sesong"` i `onMount`, persistert ved endring.

Toggle i `plan-kontroll`:

```html
<label class="plan-toggle {!aktivHoytid ? 'deaktivert' : ''}">
  <input type="checkbox" bind:checked={planSesong}
         disabled={!aktivHoytid}
         onchange={onPlanSesongChange} />
  Sesongmeny
</label>
```

`generer_matplan` kalles med `hoytid: planSesong && aktivHoytid ? aktivHoytid : null`.

`aktivHoytid` lagres som toppnivå-state `let aktivHoytid = $state<string | null>(null)` — settes i `onMount` og gjenbrukes av både forside og matplanlegger.

## Kjøreplan for tagging

1. `python scripts/tagg_hoytid.py` — genererer `data/hoytid_forslag.json`
2. Gjennomgå filen manuelt — fjern feil, legg til manglende
3. `python scripts/importer_hoytid.py` — skriver til `kokt.db`
4. Rebygg `kokt-bundle.db`: `python scripts/bygg_bundle_db.py`

## Hva som ikke er med

- Bruker-overstyring av aktiv høytid (manuelt velge "vis julemat" utenfor desember)
- Sesongoppskrifter i handlelisten eller lager-modulen
- Vekting av sesonger (vår/sommer/høst/vinter) — kun høytider
- Redigering av høytid-tagging i appen (kun via scripts)
