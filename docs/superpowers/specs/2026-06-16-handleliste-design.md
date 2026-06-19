# Handleliste — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-16.

## Mål

La brukeren legge oppskrifter i en handleliste, se ingrediensene samlet (med
korrekt skalert mengde per valgt porsjonsantall) og en estimert totalsum, og
kunne tømme/justere lista. Backlog-idé #1 (`docs/IDEER.md`).

## Arkitektur

Følger favoritt-mønsteret: en tynn `$lib/handleliste.ts` over Tauri Store, all
logikk i frontend, **ingen skriving til `kokt.db`** (den er read-only).

**Datamodell (persistert i `handleliste.json` via Tauri Store):**
```ts
type HandlelistePost = { id: number; porsjoner: number };
```
Kun oppskrift-id + valgt porsjonsantall lagres (lite, robust). Porsjoner lagres
så «juster i lista» og re-skalering er reproduserbar mellom økter.
Oppskriftsdataene (ingredienser, pris) hentes fra DB ved visning.

### Tre lag

1. **`$lib/handleliste.ts`** (speiler `favoritter.ts`) — Store-wrapper, eier KUN
   persistering. Alle muterende funksjoner returnerer ny liste (Svelte 5-
   reaktivitet) og er best-effort på lagring (feil logges, endring beholdes i
   minnet for økten):
   | Funksjon | Ansvar |
   |----------|--------|
   | `handlelisteLast()` | Last `HandlelistePost[]`; tom ved feil |
   | `handlelisteLeggTil(id, porsjoner, liste)` | Legg til, eller oppdater porsjoner hvis id finnes |
   | `handlelisteFjern(id, liste)` | Fjern én oppskrift |
   | `handlelisteSettPorsjoner(id, porsjoner, liste)` | Endre porsjoner for én post |
   | `handlelisteTøm()` | Tøm hele lista |

2. **Aggregering (ren funksjon, i `+page.svelte` el. liten hjelpefil)** — jobber
   med oppskriftsdata fra DB, ikke Store, derfor utenfor `handleliste.ts`:
   ```ts
   type SamletIngrediens = { navn: string; enhet: string | null;
                             mengde: number | null; raatekst: string };
   function slåSammen(poster: {opp, porsjoner}[]): SamletIngrediens[]
   ```
   Slår sammen på nøkkel `navn.toLowerCase() + "|" + (enhet ?? "")`. Summerer
   skalert `mengde`. Ulik enhet (dl vs stk) → separate linjer. Ingredienser uten
   mengde («salt etter smak») → én linje uten tall. Sortert alfabetisk på navn.

3. **UI i `+page.svelte`** (gjenbruker favoritt-modus-mønsteret):
   - `let handleliste = $state<HandlelistePost[]>([])`, last i `onMount`.
   - Sidebar-knapp «🛒 Handleliste» m/teller (antall oppskrifter), setter
     visningsmodus `currentKategori === "__handle__"` (analogt med `"__fav__"`).
   - «Legg i handleliste»-knapp i `.detail-topbar` (ved favoritt-knappen), bruker
     `curP` (innstilt porsjoner i detaljen).
   - Handleliste-visning: sammenslått ingrediensliste + totalsum + rad per
     oppskrift (porsjoner ± / fjern) + «Tøm»-knapp + tom-tilstand.

### Filer
| Fil | Endring |
|-----|---------|
| `kokebok-app/src/lib/handleliste.ts` | Create — Store-wrapper |
| `kokebok-app/src/routes/+page.svelte` | Modify — state, legg-til-knapp, sidebar, visning, aggregering |

## Dataflyt

```
DETALJ «Legg i handleliste» (curP) → handlelisteLeggTil(opp.id, curP, liste)
SIDEBAR «🛒 Handleliste» (modus __handle__):
  per {id, porsjoner}: hent_oppskrift(id)
  → scaleMengde(mengde, opp.porsjoner, post.porsjoner) per ingrediens
  → slåSammen() på navn+enhet
  → totalsum = Σ (opp.pris.total × post.porsjoner / opp.porsjoner)
JUSTER ± → handlelisteSettPorsjoner → re-aggreger
FJERN → handlelisteFjern; TØM → handlelisteTøm
```

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Sammenslåing | Navn+enhet → summert mengde (ulik enhet separat) |
| Persistering | Tauri Store (`handleliste.json`), lagrer `{id, porsjoner}` |
| Pris | Kun totalsum (sum av skalerte oppskriftstotaler) — ingen ny backend |
| Legg til | Knapp i detalj, bruker innstilt porsjoner |
| Visning | Sidebar «🛒 Handleliste» → egen visning (favoritt-mønster) |
| Handlinger | Tøm alt, fjern én, juster porsjoner |

## Gjenbruk

Tauri Store-mønsteret (favoritter), `scaleMengde`/`fmtMengde` (skalering),
pris-skalering (`curP/origP` fra detalj), sidebar-/visnings-mønsteret
(favoritt-modus), `hent_oppskrift` (per oppskrift — N enkle kall).

## Feilhåndtering

- Store-lagring best-effort (favoritt-mønster).
- Oppskrift som ikke kan hentes (slettet id): hopp over i aggregeringen, ikke
  krasj. (Robust mot at `kokt.db` endres — relevant nå som godt.no-skraping
  legger til rader.)
- Ingrediens uten pris/mengde: vis uten tall; totalsum viser dekningsindikator
  som detaljvisningen alt gjør (`priset`/`total`).
- Tom liste → «Handlelista er tom»-tilstand.

## Testing

Ingen automatisk frontend-testsuite i prosjektet. `slåSammen` skrives som ren
funksjon (testbar/verifiserbar uten Tauri); resten verifiseres via `npm run
build` + manuell e2e: legg til 2 oppskrifter med felles ingrediens → «egg»
summert; juster porsjoner → mengder + pris endres; fjern én; tøm → tom-tilstand;
lukk/åpne app → lista består.

## Avgrensninger (ikke i denne saken)

- Ingen avkrysning av varer i butikken (valgt bort).
- Ingen pris-per-ingrediens (kun totalsum).
- Ingen ny backend-kommando (gjenbruker `hent_oppskrift`). Hvis lista blir stor
  kan en «lett» batch-kommando vurderes senere (YAGNI nå).
