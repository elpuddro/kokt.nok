# Kaloriregnskap per dag (#29) — Design

## Mål

Brukeren kan logge hva de har spist (oppskrifter fra appen + fri innføring), og se fremgang mot dagsbehov fra helseprofilen (#20) for dag, uke og måned.

## Arkitektur

- Logg persisteres i Tauri Store (`matvarelogg.json`) — kokt.db er read-only
- Næringsverdier for oppskrifter hentes fra eksisterende `hent_oppskrift` Rust-kommando
- Aggregering (sum per dag, uke, måned) gjøres i TypeScript
- Ny lib-fil: `src/lib/matvarelogg.ts`
- UI integreres som ny visning «Dagbok» i sidebar, mellom Matplan og Innstillinger

## Datastruktur

`matvarelogg.json` → nøkkel `"poster"`:

```ts
type MåltidTidspunkt = "frokost" | "lunsj" | "middag" | "kveldsmat" | "annet";

interface LoggpostOppskrift {
  id: string;           // crypto.randomUUID()
  dato: string;         // "YYYY-MM-DD"
  tidspunkt: MåltidTidspunkt;
  type: "oppskrift";
  oppskriftId: number;
  porsjoner: number;
}

interface LoggpostFri {
  id: string;
  dato: string;
  tidspunkt: MåltidTidspunkt;
  type: "fri";
  beskrivelse: string;  // fritekst, f.eks. "2 egg, stekt"
  kcal: number;
  protein: number;      // gram
  fett: number;         // gram
  karbo: number;        // gram
}

type Loggpost = LoggpostOppskrift | LoggpostFri;
```

## Visning

Ny sidebar-lenke «Dagbok» (ikon: 📖 eller kalender). Tre tabs øverst: **Dag / Uke / Måned**.

### Dag-visning
- Datepicker (standard HTML `<input type="date">`, default i dag)
- Fire seksjoner: Frokost / Lunsj / Middag / Kveldsmat + Annet
- Hver seksjon lister poster med navn, kcal og sletteknapp
- Bunnen: total kcal + protein/fett/karbo for dagen
- Hvis aktiv helseprofil: fremgangsbar kcal mot dagsbehov (grønn < 100%, gul 100–120%, rød > 120%)
- Uten helseprofil: vises sum uten fremgangsbar

### Uke-visning
- Stolpegraf (SVG) — én stolpe per dag, siste 7 dager
- Y-akse: kcal. Stiplet linje ved dagsbehov (hvis profil aktiv)
- Klikk på stolpe → hopper til den dagen i dag-visningen

### Måned-visning
- Samme stolpegraf, siste 30 dager
- Snitt kcal per dag vises under grafen

## Logging — modal

«+»-knapp (flytende, nederst til høyre i Dagbok-visningen) åpner logg-modal:

1. Velg tidspunkt (frokost/lunsj/middag/kveldsmat/annet) — forhåndsvalgt basert på klokkeslett
2. To tabs i modalen:
   - **Fra oppskrift**: søkefelt med autofullføring (henter fra `hent_oppskrifter`), vis bilde+navn, velg porsjoner (−/+ spinner), bekreft → næring beregnes automatisk
   - **Fri innføring**: beskrivelse (fritekst) + kcal (påkrevd) + protein/fett/karbo (valgfritt)
3. «Logg»-knapp lagrer og lukker modal

## lib-grensesnitt (`matvarelogg.ts`)

```ts
export async function loggLast(): Promise<Loggpost[]>
export async function loggLeggTil(post: Loggpost): Promise<Loggpost[]>
export async function loggFjern(id: string): Promise<Loggpost[]>
export function loggForDato(poster: Loggpost[], dato: string): Loggpost[]
export function loggSumNæring(poster: Loggpost[], næring: Record<number, { kcal: number; protein: number; fett: number; karbo: number }>): { kcal: number; protein: number; fett: number; karbo: number }
// næring: map fra oppskriftId → næringsverdier per porsjon (hentet én gang ved visning)
```

## Næring for oppskrift-poster

Ved visning av dag/uke/måned: hent næring for alle unike oppskrift-IDer i loggen via `hent_oppskrift` (eksisterende kommando), bygg et map `id → næring`, beregn summer i TS. Ikke cached mellom sesjoner — hentes på nytt ved visning (rask, fra SQLite).

## Kanttilfeller

- Slettet oppskrift i DB: vis «Ukjent oppskrift» med lagret porsjonsantall, behold kcal som 0
- Ingen aktiv profil: dagsbehov-fremgangsbar skjules, sum vises alltid
- Tom logg: vis «Ingen poster» per seksjon, ikke feilmelding

## Testing

- `matvarelogg.ts`: unit-tester for `loggForDato`, `loggSumNæring` med mock-data
- Manuell e2e: logg oppskrift → verifiser kcal stemmer med detaljvisning, logg fri innføring, slett post, sjekk uke/måned-graf
