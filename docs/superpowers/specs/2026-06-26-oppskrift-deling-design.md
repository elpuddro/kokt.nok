# Oppskrift-deling (#28) — Design

## Mål

Brukeren kan dele en oppskrift som formatert tekst — kopiert til utklippstavle på desktop, via system share-sheet på Android. Kun tilgjengelig i åpen utgave (ikke fengselsutgaven).

## Utgave-mekanisme (ny, gjenbrukbar)

Fengselsutgaven skilles fra åpen utgave via Vite-miljøvariabel satt ved byggetid:

- `.env` (default, åpen): `VITE_UTGAVE=aapen`
- `.env.fengsel`: `VITE_UTGAVE=fengsel`
- Fengselsbygget bygges med: `VITE_UTGAVE=fengsel npm run build`

I Svelte: `const erFengsel = import.meta.env.VITE_UTGAVE === 'fengsel'`

Alle fremtidige utgave-spesifikke features bruker samme variabel. Legg til `VITE_UTGAVE` i `vite.config.js` som `envPrefix`-whitelist hvis nødvendig (SvelteKit eksponerer `VITE_`-prefiks automatisk).

Oppdater `scripts/bygg_portable.py` og `scripts/bygg_bundle_db.py` til å sette `VITE_UTGAVE=fengsel` for fengselsbygg. Dokumenter i `scripts/README` (eller kommentar i scriptet).

## Tekstformat

```
[Oppskriftnavn]
Tid: [X min] | Porsjoner: [N]

INGREDIENSER
- [mengde] [enhet] [ingrediens]
...

FREMGANGSMÅTE
1. [trinn]
2. [trinn]
...

— Delt fra Steike bra
```

Genereres i en ren TypeScript-funksjon `formaterOppskrift(oppskrift: OppskriftDetalj): string` i `src/lib/deling.ts`.

## Desktop (Windows/Linux — åpen utgave)

- «Del»-knapp i oppskrift-detaljvisningen, plassert ved siden av «Favoritt»-stjernen i header
- Klikk → `navigator.clipboard.writeText(formaterOppskrift(oppskrift))`
- Knappen viser «📋 Del» → endres til «✓ Kopiert!» i 2 sekunder → tilbake til «📋 Del»
- `erFengsel === true` → knappen rendres ikke

## Android

- Samme «Del»-knapp i detaljvisningen
- Klikk → `@tauri-apps/plugin-share` → `share({ text: formaterOppskrift(oppskrift) })`
- Åpner Android system share-sheet (WhatsApp, SMS, e-post osv.)
- Plugin legges til i `Cargo.toml` og `tauri.conf.json` capabilities

## lib-grensesnitt (`deling.ts`)

```ts
export function formaterOppskrift(oppskrift: OppskriftDetalj): string
// OppskriftDetalj er eksisterende type fra hent_oppskrift-kommandoen
```

Ingen asynkron logikk i lib-filen — all deling håndteres i komponenten.

## Plattformdeteksjon

Bruk Tauri `platform()`-API for å avgjøre om vi er på Android:

```ts
import { platform } from "@tauri-apps/plugin-os";
const erAndroid = (await platform()) === "android";
```

- Android: bruk share-plugin
- Desktop: bruk clipboard

## Avhengigheter

- `@tauri-apps/plugin-share` — legg til i `package.json` og `src-tauri/Cargo.toml`
- Tauri capability: `"plugin:share|share"` i `capabilities/default.json`
- Kun nødvendig på Android — desktop bruker Web Clipboard API (ingen ekstra plugin)

## Kanttilfeller

- Clipboard ikke tilgjengelig (f.eks. Wayland uten xdg-portal): vis feilmelding «Kunne ikke kopiere — prøv å markere teksten manuelt»
- Oppskrift uten trinn eller ingredienser: seksjonen utelates fra teksten (ikke tom header)
- Android share avbrutt av bruker: ingen feilmelding (normalt brukeratferd)
- `erFengsel === true`: knapp rendres ikke, ingen feilhåndtering nødvendig

## Testing

- `deling.ts`: unit-test for `formaterOppskrift` — verifiser at manglende trinn/ingredienser håndteres, at «Delt fra Steike bra»-footer er med
- Manuell e2e desktop: klikk Del, lim inn i Notepad, verifiser format
- Manuell e2e Android: klikk Del, verifiser share-sheet åpnes med riktig tekst
- Verifiser at knappen er usynlig i fengselsbygg (`VITE_UTGAVE=fengsel npm run build`)
