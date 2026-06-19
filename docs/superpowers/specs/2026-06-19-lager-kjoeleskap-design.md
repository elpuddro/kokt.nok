# Lager + «Hva har jeg i kjøleskapet?» — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-19.
> Backlog-idé #14 (sammenslåing av tidligere #13/#16/#17). Matplanlegger (#15)
> er en SENERE, separat sak som vil gjenbruke match-motoren herfra.

## Mål

La brukeren registrere hva de har hjemme (skap/kjøl/fryser), holde oversikt med
utløpsvarsel, og få forslag til oppskrifter sortert etter hvor mye av
ingrediensene de allerede har («kan lages nå» / «mangler N»). Reduserer matsvinn.

## Arkitektur

Lageret lagres i Tauri Store (`lager.json`, som handleliste.ts — kokt.db er
read-only). Dekningsgrad-matchingen kjører **server-side i Rust** (indeksert
SQL, gjenbruker `idx_ing_opp_navn(oppskrift_id, navn)` fra kosthold-filteret) via
to nye kommandoer. UI i en egen `🧊 Kjøleskap`-sidebar-visning.

### Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src/lib/lager.ts` | Tauri Store-wrapper (`lager.json`): CRUD på varer | Create |
| `kokebok-app/src/lib/lager-logikk.ts` | Ren logikk: `utlopsStatus(dato, idag)` (node-testbar) | Create |
| `kokebok-app/src/lib/lager-logikk.test.mjs` | node-tester for utløps-klassifisering | Create |
| `kokebok-app/src-tauri/src/lib.rs` | `ingrediens_forslag` + `hva_kan_jeg_lage` + staples-liste | Modify |
| `kokebok-app/src/routes/+page.svelte` | `__lager__`-visning, autocomplete, forslag, «Jeg lagde denne» | Modify |

Mønstre gjenbrukt: `handleliste.ts` (Store-CRUD), `tema-logikk.ts`/`tid-parsing.ts`
(node-testbar ren logikk), `__fav__`/`__handle__`/`__innst__` (sidebar-modus),
`idx_ing_opp_navn` (eksisterende indeks).

## Datamodell

**`lager.json`** (Tauri Store, nøkkel `varer`): `LagerVare[]` der
```ts
type LagerVare = { navn: string; utloper: string | null };  // utloper = ISO "2026-06-21" | null
```
Ingen mengder/enheter (bevisst — lavt taste-arbeid, navnebasert match).

## Komponent A: Store-wrapper `lager.ts`

Speiler `handleliste.ts` (best-effort, returnerer ny liste):
| Funksjon | Ansvar |
|----------|--------|
| `lagerLast()` | les `LagerVare[]`; tom liste ved feil |
| `lagerLeggTil(navn, utloper, liste)` | legg til (dedup på navn, case-insensitivt); returner ny liste |
| `lagerFjern(navn, liste)` | fjern én vare; returner ny liste |
| `lagerTøm()` | tøm; returner `[]` |

## Komponent B: Ren logikk `lager-logikk.ts`

```ts
export type UtlopsStatus = "utgått" | "snart" | "ok" | null;
// dato/idag som ISO "YYYY-MM-DD". snart = ≤3 dager igjen. null hvis ingen dato.
export function utlopsStatus(utloper: string | null, idag: string): UtlopsStatus;
```
Node-testbar (ingen Tauri-import). Tester: utgått (dato < idag), snart (0–3 dager),
ok (>3 dager), null (ingen dato), grensen nøyaktig 3 dager = snart, 4 = ok.

## Komponent C: Rust-kommandoer

**`ingrediens_forslag(prefiks: String) -> Vec<String>`** — autocomplete. Distinkte
`ingredienser.navn` der navnet inneholder prefikset (prioriter de som STARTER med
det), `LIMIT 10`, sortert. Tomt/for kort prefiks (<2 tegn) → tom liste.

**`hva_kan_jeg_lage(varer: Vec<String>) -> Vec<Forslag>`** der
```rust
struct Forslag { id: i64, navn: String, type_: String, bilde: ..., totalt: i64, dekket: i64, mangler: Vec<String> }
```
- **Staples** (ekskluderes fra teller OG nevner) — definert ett sted i Rust som
  delstreng-mønstre: `salt, pepper, vann, sukker, mel, olje, smør`. En oppskrift-
  ingrediens regnes som staple hvis navnet INNEHOLDER et av disse mønstrene
  (`hvetemel`→`mel`, `nøytral olje`/`rapsolje`→`olje`, `kvernet pepper`→`pepper`).
  NB falske staple-treff å være obs på: `melk` inneholder `mel`, `karamell`
  inneholder `mel`, `mela­nge` osv. — bruk ordgrense/sjekk for `mel` og `salt`
  («salat» inneholder `sal…` men ikke `salt` som ord), ELLER bruk mer spesifikke
  staple-navn (`hvetemel`, `sukker`, `salt`, `pepper`, `vann`, `olje`, `smør`) og
  aksepter at f.eks. «sukkererter» feil-klassifiseres som staple (sjelden, lav
  skade — det er den TRYGGE retningen siden staples bare slipper igjennom som
  «har alltid»). Avklares i plan med en datasjekk, som for kosthold-filteret.
- For hver oppskrift: tell ikke-staple-ingredienser (`totalt`) og hvor mange som
  matcher minst én bruker-vare (`dekket`). **Toveis delstreng-match:** en
  oppskrift-ingrediens er dekket hvis `vare LIKE %ingred%` ELLER `ingred LIKE
  %vare%` (lowercased). `mangler` = ikke-staple-ingredienser uten match.
- `HAVING dekket > 0` (vis bare oppskrifter du har NOE til).
- Sortering: `(totalt - dekket) ASC` (færrest mangler først), så `dekket DESC`,
  så `navn`. `LIMIT ~60`.
- Tomt `varer` → tom liste.

Implementasjonsnote: `mangler`-navnene kan hentes med `GROUP_CONCAT` av de
udekkede ikke-staple-navnene per oppskrift, eller i et lite oppfølgings-steg.
Bruker `idx_ing_opp_navn`. Bygges med parametriserte `LIKE`-betingelser fra
brukerens varer (ikke streng-interpolering).

## Komponent D: UI (`__lager__`-visning i `+page.svelte`)

Ny sidebar-oppføring «🧊 Kjøleskap» (etter Handleliste, før Innstillinger) →
`currentKategori === "__lager__"`. To deler:

**Øvre — lageret:**
- Autocomplete-input: debounced `ingrediens_forslag(prefiks)` → dropdown med ≤10
  ekte ingrediensnavn. Velg/skriv fritt + valgfri `<input type="date">` → «Legg til».
- Vareliste, hver rad: navn, evt. utløpsdato fargekodet via `utlopsStatus`
  (rød «utgått» / oransje «snart» / nøytral), ✕ fjern. «Tøm lager»-knapp.

**Nedre — «Hva kan jeg lage»:**
- Lager ≥1 vare → `hva_kan_jeg_lage(varer)` (debounced ved lager-endring). Forslag
  gruppert: «Kan lages nå» (0 mangler), «Mangler 1», «Mangler 2», … Hver rad:
  bilde + navn + «mangler: …»-linje. Klikk → `åpneOppskrift`.
- Tomt lager → hjelpetekst.

**«Jeg lagde denne» (manuelt fratrekk):** knapp i detaljvisningen — «✓ Lagde denne
— fjern brukte varer» — fjerner lager-varer som matcher oppskriftens ingredienser
(toveis delstreng), og viser kort hva som ble fjernet. Ingen match → ingen effekt.

**Reaktivitet:** legg til/fjern vare → re-kjør forslag (debounced).

## Dataflyt

```
LAST:      varer = await lagerLast()
SKRIV:     input → ingrediens_forslag(prefiks) → dropdown → lagerLeggTil → re-forslag
FORSLAG:   varer → invoke(hva_kan_jeg_lage,{varer}) → gruppert «mangler N»-liste
UTLØP:     hver vare → utlopsStatus(v.utloper, idag) → fargekode
LAGDE:     detalj-knapp → fjern matchede lager-varer (toveis delstreng)
```

## Feilhåndtering

- Store best-effort (handleliste-mønster): feil logges, tomt lager ved feil.
- Rust-kommandoer: tomt/ugyldig input → tom liste; manglende indeks → færre treff,
  aldri krasj.
- Utløp valgfri; null håndteres i `utlopsStatus`.
- «Jeg lagde denne» fjerner kun faktiske matcher; ingen match → ingen effekt.

## Testing

- **Ren logikk:** `lager-logikk.test.mjs` (node) — `utlopsStatus`-grenser.
- **Match (Rust):** verifiser mot ekte DB: lager `["kyllingfilet","pasta"]` → kjent
  kyllingpasta lav/null mangel; staples teller ikke; tomt lager → tomt.
- **Frontend/e2e (manuell):** legg til vare m/autocomplete; utløp fargekodes;
  forslag grupperes på «mangler N»; «Jeg lagde denne» fjerner matchede varer;
  restart app → lager består.

## Distribusjon

Ingen `kokt.db`-skjemaendring (lager i Store). Ingen nye avhengigheter.
`idx_ing_opp_navn` finnes alt og følger med i bundle (kopieres med kokt.db) — kreves
for raske forslag i portable.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Rekkefølge | #14 lager+kjøleskap først; #15 matplanlegger separat senere |
| Lager-detalj | Navn + valgfri utløpsdato (ingen mengder) |
| Vare-innlegging | Fritekst med autocomplete fra ekte ingrediensnavn |
| Forslags-logikk | Dekningsgrad-rangering, «mangler N», staples ignorert |
| Utløp + fratrekk | Utløpsvarsel (farge) + manuelt fratrekk («Jeg lagde denne») |
| Plassering | Egen `🧊 Kjøleskap` sidebar-visning (`__lager__`) |
| Match | Server-side Rust, indeksert, toveis delstreng |

## Avgrensninger (ikke i denne saken — YAGNI)

- Ingen mengder/enheter, ingen enhets-konvertering.
- Ingen strekkode-/butikk-integrasjon (offline).
- Ingen auto-fratrekk uten bekreftelse.
- Ingen kategorisering av lager-varer.
- Ingen persistering av forslag (beregnes på etterspørsel).
- Matplanlegger (#15) er en egen sak.
