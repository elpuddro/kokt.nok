# Manuell prisregistrering + historikk (#30) — Design

## Mål

Brukeren registrerer priser på ingredienser fra kvittering. Priser brukes til kostnadsestimater i handlelisten (#1) og vises som pristrend over tid. Særlig nyttig i fengselsutgaven der 120 beboere kan bidra kollektivt uten internett.

## Arkitektur

- Priser persisteres i Tauri Store (`priser.json`) — kokt.db er read-only
- Autofullføring henter ingrediensnavn via ny Rust-kommando `sok_ingredienser(q: String) -> Vec<String>` (søk i `ingredienser`-tabellen i kokt.db)
- Ny lib-fil: `src/lib/priser.ts`
- UI: ny «Priser»-visning i sidebar + kvitteringsmodus-modal + kobling til handleliste

## Datastruktur

`priser.json` → nøkkel `"poster"`:

```ts
interface Prispost {
  id: string;           // crypto.randomUUID()
  ingrediens: string;   // fritekst (matcher mot DB-ingredienser via autofullføring, men lagres som navn)
  pris: number;         // kroner
  enhet: "kg" | "l" | "stk" | "pakke" | "dl" | "g";
  dato: string;         // "YYYY-MM-DD"
  butikk?: string;      // valgfritt fritekst
}
```

## Kvitteringsmodus

Dedikert flyt for rask registrering av mange varer:

1. **Header**: datepicker (default i dag) + valgfritt butikknavn-felt
2. **Tabell-editor**: kolonner — Ingrediens | Pris (kr) | Enhet
   - Én rad per vare
   - Ingrediens-feltet: autofullføring fra DB-ingredienser mens du skriver, men fritekst tillatt for ukjente varer
   - Enter i siste felt på en rad → fokus hopper til ingrediens-feltet på neste rad (ny rad opprettes automatisk)
   - Sletteknapp per rad (×)
3. **«+ Legg til rad»**-knapp under tabellen
4. **«Bekreft kvittering»**-knapp: validerer at alle rader har ingrediens + pris, lagrer alle samlet, lukker modal

Åpnes via «Legg inn kvittering»-knapp i Priser-visningen.

## Priser-visning

Ny sidebar-lenke «Priser» (ikon: 🏷️). Innhold:

- **«Legg inn kvittering»**-knapp øverst
- Søkefelt for å finne ingrediens
- Liste over ingredienser med registrert pris:
  - Siste pris + dato + butikk
  - Klikk → ekspander til prishistorikk med SVG-linjediagram (dato på x-akse, kr/enhet på y-akse)
  - Rediger/slett enkeltpost

## Kobling til handlelisten

Eksisterende handleliste-visning viser estimert totalkostnad. Når priser finnes:
- Matcher ingrediensnavn fra oppskrift mot prispost-ingrediens (eksakt match først, deretter case-insensitiv substring)
- Viser pris per ingrediens i handlelisten ved siden av ingrediensnavnet
- Viser sum nederst
- Ingredienser uten pris vises med «—»

Handleliste-komponenten henter priser via `prisForIngrediens(navn, poster)` fra `priser.ts`.

## lib-grensesnitt (`priser.ts`)

```ts
export async function priserLast(): Promise<Prispost[]>
export async function priserLeggTilFlere(nye: Omit<Prispost, "id">[]): Promise<Prispost[]>
export async function prisOppdater(oppdatert: Prispost): Promise<Prispost[]>
export async function prisSlett(id: string): Promise<Prispost[]>
export function prisForIngrediens(navn: string, poster: Prispost[]): Prispost | null
export function prisHistorikk(navn: string, poster: Prispost[]): Prispost[]
// returnerer alle poster for ingrediensen, sortert dato asc
```

## SVG-linjediagram

Samme mønster som planlagt for kaloriregnskap: ren SVG generert i Svelte, ingen eksterne biblioteker. X-akse: dato, Y-akse: pris per enhet. Punkter forbundet med linje, tooltip ved hover.

## Kanttilfeller

- Samme ingrediens, ulike butikker: begge vises i historikk, handleliste bruker nyeste uansett butikk
- Ukjent ingrediens (ikke i DB): lagres som fritekst, ingen autofullføring-match, vises i historikk
- Tom kvittering bekreftet: ingen poster lagres, modal lukkes stille
- Ingrediensnavn med ulik stavemåte («kyllingfilet» vs «Kyllingfilet»): case-insensitiv match

## Testing

- `priser.ts`: unit-tester for `prisForIngrediens` (eksakt, substring, ingen match), `prisHistorikk` (sortering)
- Manuell e2e: legg inn kvittering med 5 varer, verifiser i handleliste, sjekk historikkdiagram
