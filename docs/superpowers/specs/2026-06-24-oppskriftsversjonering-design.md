# Oppskriftsversjonering Design

**Dato:** 2026-06-24
**Backlog:** #18

## Mål

Brukeren kan lage sin egen personlige versjon av en scraped oppskrift — redigere ingredienser, fremgangsmåte, tittel, beskrivelse, porsjoner og tid. Originalen i `kokt.db` røres aldri. Endringer er profil-spesifikke og kan spores over tid (manuelt lagrede versjoner).

## Arkitektur

Alt brukerspesifikt lagres i `versjoner.json` via Tauri Store — samme mønster som `notater.json` og `favoritter.json`. Rust-backend trenger ingen endringer. Visningslogikken (diff for sammenligning, ingrediens/trinn-manipulasjon) isoleres i `versjoner-logikk.ts` med testdekning.

**Tech Stack:** Svelte 5 runes (`$state`, `$derived`), `@tauri-apps/plugin-store`, TypeScript, Vitest (`.test.mjs`)

## Global Constraints

- `kokt.db` er **read-only** — aldri skriv til den
- Svelte 5 runes kun: `$state`, `$derived`, `$props` — ingen `$:`, ingen `writable()`
- Tauri Store: `load("versjoner.json")`, `store.get/set/save()`
- `invoke` fra `@tauri-apps/api/core`
- Ingen nye Rust-kommandoer
- CSS-variabler fra `app.css`: `--card`, `--card-hover`, `--text-muted`, `--border`, `--surface`, `--bg`, `--text`, `--radius-sm`, `--font-ui`
- Versjonering er **profil-spesifikk**: profil-ID som ytterste nøkkel
- Versjoner uten profil (profilId = `"__global__"`) lagres ikke — versjonering krever aktiv profil
- Ingen drag-resortering av trinn — pil opp/ned-knapper

## Datamodell

Lagres i `versjoner.json`:

```typescript
// Ytterste nøkkel: profilId (string fra helse.ts), deretter oppskriftId (number)
type VersjonerStore = {
  [profilId: string]: {
    [oppskriftId: number]: OppskriftEntry
  }
}

type OppskriftEntry = {
  kladd: OppskriftKopi | null   // autolaget fra løpende redigering
  historikk: VersjonSnapshot[]  // manuelt lagrede versjoner
}

type OppskriftKopi = {
  navn: string
  beskrivelse: string | null
  porsjoner: number | null
  tid: string | null
  ingredienser: KopiIngrediens[]
  trinn: KopiTrinn[]
}

type KopiIngrediens = {
  gruppe: string | null
  mengde: number | null
  enhet: string | null
  navn: string | null
  sortering: number
}

type KopiTrinn = {
  nummer: number
  tekst: string
}

type VersjonSnapshot = {
  id: string              // crypto.randomUUID()
  lagretTidspunkt: string // ISO 8601 (new Date().toISOString())
  label: string           // valgfri brukertekst, f.eks. "Med gresskar"
  kopi: OppskriftKopi
}
```

## Moduler

### `src/lib/versjoner.ts` (ny)

Håndterer all Tauri Store I/O. Eksporterer:

```typescript
export async function versjonerLast(profilId: string, oppskriftId: number): Promise<OppskriftEntry | null>
export async function kladd_sett(profilId: string, oppskriftId: number, kopi: OppskriftKopi): Promise<void>
export async function kladd_fjern(profilId: string, oppskriftId: number): Promise<void>
export async function versjon_lagre(profilId: string, oppskriftId: number, label: string, kopi: OppskriftKopi): Promise<VersjonSnapshot[]>
export async function versjon_slett(profilId: string, oppskriftId: number, versjonId: string): Promise<VersjonSnapshot[]>
```

Singleton-store-mønster (som `notater.ts`): én `load("versjoner.json")`-promise.

### `src/lib/versjoner-logikk.ts` (ny)

Ren logikk uten Tauri-avhengigheter — testbar med Vitest.

```typescript
// Bygg OppskriftKopi fra et oppskrift-objekt returnert av hent_oppskrift
export function kopiFraOppskrift(opp: OppskriftRaw): OppskriftKopi

// Beregn strukturell diff mellom to OppskriftKopi for sammenligning
export type IngrediensDiff = { orig: KopiIngrediens | null; versjon: KopiIngrediens | null; endret: boolean }
export type TrinnDiff = { orig: KopiTrinn | null; versjon: KopiTrinn | null; endret: boolean }
export type OppskriftDiff = {
  navn: { orig: string; versjon: string; endret: boolean }
  beskrivelse: { orig: string | null; versjon: string | null; endret: boolean }
  porsjoner: { orig: number | null; versjon: number | null; endret: boolean }
  tid: { orig: string | null; versjon: string | null; endret: boolean }
  ingredienser: IngrediensDiff[]
  trinn: TrinnDiff[]
}
export function beregnDiff(orig: OppskriftKopi, versjon: OppskriftKopi): OppskriftDiff
```

### `src/lib/versjoner-logikk.test.mjs` (ny)

Tester for `kopiFraOppskrift` og `beregnDiff` — uendret ingrediens, endret mengde, ny ingrediens, slettet ingrediens, omskrevet trinn.

### `+page.svelte` (modifisert)

Ny state i detaljpanelet:

```typescript
let redigerModus = $state(false)
let kladd = $state<OppskriftKopi | null>(null)
let historikk = $state<VersjonSnapshot[]>([])
let sammenlignVersjon = $state<VersjonSnapshot | null>(null)
let lagreModalApen = $state(false)
let lagreLabel = $state("")
```

`$derived` for hva som faktisk vises i detaljpanelet:

```typescript
// kladd og historikk lastes fra versjonerLast() i onMount når detaljpanelet åpnes (ved opp-endring)
let visOppskrift = $derived(
  redigerModus && kladd ? kladd :
  kladd ? kladd :
  opp ? kopiFraOppskrift(opp) : null
)
```

## UI-flyt

### Detaljpanel — normal visning

- Ny knapp i `detail-topbar`: "✏️ Rediger" — vises kun når aktiv profil finnes (`aktivProfil !== null`). Uten aktiv profil er versjonering ikke tilgjengelig.
- Hvis brukeren har en kladd: merkebadge "Redigert" vises på knappen
- Knapp "📋 Historikk (N)" vises hvis `historikk.length > 0`

### Redigeringsmodus

Aktiveres ved klikk på "Rediger". `kladd` initialiseres fra eksisterende kladd eller fra `kopiFraOppskrift(opp)`.

**Topbar i redigeringsmodus:**
- "← Avbryt" — tilbakestiller `kladd` til sist lagrede kladd, lukker redigeringsmodus
- "💾 Lagre versjon" — åpner `lagreModal`
- Autolaging av kladd: debounce 800 ms på enhver endring, kaller `kladd_sett()`

**Redigerbare felt:**
- Navn: `<input type="text">`
- Beskrivelse: `<textarea>`
- Porsjoner: `<input type="number" min="1">`
- Tid: `<input type="text">`

**Ingredienser i redigeringsmodus:**
- Hvert element: `<input>` for mengde (number), enhet (text), navn (text)
- "🗑" slett-knapp per element
- "＋ Legg til ingrediens" på bunnen (legger til tomt element)

**Trinn i redigeringsmodus:**
- Hvert trinn: `<textarea>` for tekst
- "↑" / "↓" knapper for resortering (deaktivert for første/siste)
- "🗑" slett-knapp per trinn
- "＋ Legg til trinn" på bunnen

### Lagremodal

Liten `<dialog>`-modal over detaljpanelet:
- Overskrift: "Lagre versjon"
- `<input type="text" placeholder="Beskrivelse (valgfri), f.eks. «Med gresskar»">` bundet til `lagreLabel`
- "Lagre" — kaller `versjon_lagre()`, lukker modal, lukker redigeringsmodus
- "Avbryt" — lukker modal

### Historikkpanel

Vises som en `<section class="versjon-historikk">` nederst i `detail-body` (etter notat-seksjonen), synlig kun når `historikk.length > 0`.

Liste over `VersjonSnapshot[]` sortert nyeste øverst:
- Tidspunkt (formatert: "22. jun 2026, 14:30")
- Label (eller "Ingen beskrivelse" i kursiv)
- Knapper: "Sammenlign" · "Gjenopprett" · "Slett"

### Sammenligningsvisning

Aktiveres av "Sammenlign"-knapp — setter `sammenlignVersjon`. Vises som et overlay/modal over detaljpanelet (samme mønster som `detail-overlay`):

**Metadata-rad øverst:** endrede felter vises som `original → versjon`.

**To-kolonne tabell for ingredienser:**
- Rader farges: grønn bakgrunn = ny i versjon, rød bakgrunn = finnes kun i original, gul bakgrunn = endret mengde/enhet/navn.

**Fremgangsmåte:** tilsvarende to-kolonne, endrede trinn markeres.

"✕ Lukk" knapp. "Bruk denne versjonen" kopierer snapshot til ny kladd og lukker sammenligning.

## Lagringsformat — eksempel

```json
{
  "profil-uuid-123": {
    "4201": {
      "kladd": {
        "navn": "Pasta Carbonara (min variant)",
        "beskrivelse": null,
        "porsjoner": 2,
        "tid": "20 min",
        "ingredienser": [...],
        "trinn": [...]
      },
      "historikk": [
        {
          "id": "ver-uuid-abc",
          "lagretTidspunkt": "2026-06-22T14:30:00.000Z",
          "label": "Uten bacon",
          "kopi": { ... }
        }
      ]
    }
  }
}
```

## Hva som ikke er med

- Deling av versjoner mellom profiler
- Eksport/import av versjoner
- Versjonsbegrensning (alle manuelt lagrede beholdes)
- Sammenligning mellom to brukerversjoner (kun original vs. versjon)
- Redigering av kategori/type/bilde
