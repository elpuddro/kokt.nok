# Helseprofil og næringsanalyse — Design (#20)

**Dato:** 2026-06-23

---

## Mål

Brukere kan opprette navngitte helseprofiler (høyde, vekt, alder, aktivitet, mål) som gir beregnet daglig energibehov (TDEE). Matplanleggeren bruker TDEE automatisk som dagsmål. Oppskriftsdetaljvisningen viser hvor stor andel av dagsbehovet én porsjon av retten dekker. Flere profiler støttes for flerbrukermiljøer. I tillegg: en "Om appen"-seksjon i Innstillinger for hjemmeversjon (Cargo feature `about`), skjult i fengselsbygg.

---

## Arkitektur

Alle beregninger skjer i frontend (`src/lib/helse.ts`). Ingen ny Rust-kode for helseprofil. Profildata lagres i Tauri Store (`profiler.json`). About-info leveres av en Rust-kommando bak `#[cfg(feature = "about")]`.

---

## Datamodell

### `profiler.json` (Tauri Store)

```typescript
type Aktivitetsnivå = "stillesittende" | "lett" | "moderat" | "aktiv" | "veldig_aktiv"
type Mål = "nedgang" | "vedlikehold" | "oppgang"

interface Brukerprofil {
  id: string          // uuid v4, generert i frontend (crypto.randomUUID())
  navn: string
  kjønn: "mann" | "kvinne"
  alder: number       // år, heltall
  høyde: number       // cm, heltall
  vekt: number        // kg, desimal tillatt
  aktivitet: Aktivitetsnivå
  mål: Mål
}

interface ProfilStore {
  profiler: Brukerprofil[]
  aktivId: string | null  // id til aktiv profil, null = ingen valgt
}
```

---

## TDEE-beregning (`src/lib/helse.ts`)

Mifflin-St Jeor BMR → aktivitetsfaktor → målsjustering:

```typescript
function bmr(p: Brukerprofil): number {
  const base = 10 * p.vekt + 6.25 * p.høyde - 5 * p.alder
  return p.kjønn === "mann" ? base + 5 : base - 161
}

const AKTIVITETSFAKTOR: Record<Aktivitetsnivå, number> = {
  stillesittende: 1.2,   // Lite/ingen trening
  lett:           1.375, // Lett trening 1-3 dager/uke
  moderat:        1.55,  // Moderat trening 3-5 dager/uke
  aktiv:          1.725, // Hard trening 6-7 dager/uke
  veldig_aktiv:   1.9,   // Svært hard trening, fysisk jobb
}

const MÅLSJUSTERING: Record<Mål, number> = {
  nedgang:      -500,
  vedlikehold:     0,
  oppgang:      +500,
}

export function tdee(p: Brukerprofil): number {
  return Math.round(bmr(p) * AKTIVITETSFAKTOR[p.aktivitet] + MÅLSJUSTERING[p.mål])
}
```

### Daglige referanseverdier for makroer (avledet av TDEE)

| Makro | Andel av TDEE | Energi per gram | Formel |
|-------|--------------|-----------------|--------|
| Protein | 15% | 4 kcal/g | `tdee * 0.15 / 4` g |
| Fett | 30% | 9 kcal/g | `tdee * 0.30 / 9` g |
| Karbohydrat | 55% | 4 kcal/g | `tdee * 0.55 / 4` g |

```typescript
export interface Dagsbehov {
  kcal: number
  protein: number  // gram
  fett: number     // gram
  karbo: number    // gram
}

export function dagsbehov(p: Brukerprofil): Dagsbehov {
  const t = tdee(p)
  return {
    kcal:    t,
    protein: Math.round(t * 0.15 / 4),
    fett:    Math.round(t * 0.30 / 9),
    karbo:   Math.round(t * 0.55 / 4),
  }
}

export function dekningsProsent(næring: number, behov: number): number {
  if (!behov) return 0
  return Math.round((næring / behov) * 100)
}
```

---

## UI-komponenter

### 1. Profilvelger i sidefeltet

Plassering: rett under `.sidebar-logo`, over kategorilisten.

- Viser aktiv profils navn + initialer i en liten boble
- Hvis ingen profil: viser "Velg profil" i grå tekst
- Klikk åpner en liten dropdown med alle profiler (klikk velger aktiv)
- "Administrer profiler →"-lenke i bunnen av dropdown åpner Innstillinger → Helseprofil-fanen

### 2. Innstillinger → Helseprofil-fane

Ny fane i Innstillinger-visningen ved siden av eksisterende innhold (temaer, kostholdsfiltre).

Innhold:
- Liste over profiler: navn, TDEE (kcal/dag), aktiv-markering
- "Ny profil"-knapp → inline skjema med feltene: navn, kjønn (mann/kvinne), alder, høyde, vekt, aktivitetsnivå (dropdown med forklarende tekst), mål (nedgang/vedlikehold/oppgang)
- Per profil: "Rediger", "Slett", "Sett som aktiv"
- Sletting krever bekreftelse hvis profilen er aktiv

### 3. Dagsbehov i oppskriftsdetaljvisningen

Plassering: rett under eksisterende næringskort (`naeringPerPorsjon`-blokken).

Vises kun når:
- Aktiv profil finnes (`aktivId !== null`)
- Oppskriften har næringsdata (`naeringPerPorsjon !== null`)

Viser fire prosent-kort (alltid per 1 porsjon, uavhengig av valgt porsjonsstørrelse):

```
🔥 42%  av energibehov
🥩 38%  av proteinbehov
🫙 25%  av fettbehov
🌾 51%  av karbohydratbehov
```

Liten forklaringstekst under: "Basert på profil: [navn] · [TDEE] kcal/dag"

### 4. Matplanleggeren

`planDagsmaal` prepopuleres med `tdee(aktivProfil)` når en profil er aktiv. Brukeren kan fortsatt overstyre feltet manuelt. Hvis ingen profil: feltet starter på 2000 kcal som før.

---

## About-seksjon (Cargo feature `about`)

### Rust (`src-tauri/src/lib.rs`)

```rust
#[cfg(feature = "about")]
#[derive(serde::Serialize)]
struct AboutInfo {
    navn: &'static str,
    epost: &'static str,
    versjon: &'static str,
    beskrivelse: &'static str,
}

#[cfg(feature = "about")]
#[tauri::command]
fn about_info() -> AboutInfo {
    AboutInfo {
        navn: "Frank Simonsen",
        epost: "elpuddro@gmail.com",
        versjon: env!("CARGO_PKG_VERSION"),
        beskrivelse: "Kokebok er en offline basert oppskriftssamling for Windows og Linux. \
            Appen inneholder over 5 900 norske oppskrifter fra matprat.no og godt.no, \
            med næringsinfo fra Matvaretabellen, smarte funksjoner som ukesmenyplanlegger, \
            handleliste, kjøleskapsstyring og kostholdsfiltre med mere.",
    }
}
```

Feature registreres i `Cargo.toml`:
```toml
[features]
about = []
```

Kommandoen registreres betinget i `tauri::Builder`:
```rust
let builder = tauri::Builder::default();
#[cfg(feature = "about")]
let builder = builder.invoke_handler(tauri::generate_handler![..., about_info]);
```

### Frontend

`about_info()` kalles ved oppstart av Innstillinger-visningen. Hvis kommandoen ikke finnes (fengselsbygg), returnerer `invoke` en feil som fanges stille — About-seksjonen vises ikke.

About-seksjonen vises nederst i Innstillinger, under alle faner, kun når data returneres:

```
─────────────────────────────
Om appen · v1.0.0

Kokebok er en offline basert oppskriftssamling for Windows og Linux.
Appen inneholder over 5 900 norske oppskrifter fra matprat.no og godt.no,
med næringsinfo fra Matvaretabellen, smarte funksjoner som ukesmenyplanlegger,
handleliste, kjøleskapsstyring og kostholdsfiltre med mere.

Frank Simonsen · elpuddro@gmail.com
─────────────────────────────
```

### Bygg

| Bygg | Kommando | About | Scrub-gate |
|------|----------|-------|------------|
| Fengselsbygg (default) | `npm run tauri build -- --no-bundle` | Skjult | Ja |
| Hjemmebygg | `npm run tauri build -- --no-bundle --features about` | Synlig | Nei |

`bygg_portable.py` endres ikke — fengselsbygg som alltid.

---

## Filer som endres / opprettes

| Fil | Endring |
|-----|---------|
| `src/lib/helse.ts` | Ny fil — TDEE, dagsbehov, dekningsProsent |
| `src/routes/+page.svelte` | Profilvelger i sidebar, Helseprofil-fane i Innstillinger, dagsbehov-kort i detalj, prepopuler matplan |
| `src-tauri/src/lib.rs` | `about_info`-kommando bak `#[cfg(feature = "about")]` |
| `src-tauri/Cargo.toml` | `[features] about = []` |

---

## Ikke inkludert (YAGNI)

- Vitamin-kolonner i næring (mangler i DB)
- Google Fit-integrasjon (fremtidig)
- Grafer / historikk over vektutvikling
- Kalorilogg per dag
