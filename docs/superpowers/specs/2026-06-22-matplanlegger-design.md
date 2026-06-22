# Smart matplanlegger — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-22.
> Backlog-idé #15 (overlapper #6 ukesmeny). Gjenbruker match-/diett-motoren fra
> #14 (lager) og #9/#10 (kosthold-filter), handlelista og porsjons-skalering.

## Mål

La brukeren generere en ukemeny (frokost/lunsj/middag/kveldsmat × 7 dager) som
treffer et daglig kalorimål, respekterer aktive kosthold-/allergifiltre, gir
variasjon, og foretrekker retter som deler råvarer (kortere handleliste, mindre
svinn). Regelbasert — **ingen AI/LLM** (offline-/luftgap-distribusjon). Brukeren
kan låse retter og regenerere resten, sende uka til handlelista, og lagre uka.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Pris/budsjett | **Droppet** — prisdata dekker bare ~2000/8421 ingrediensnavn → for tynt for et budsjett. |
| Optimering | Kalorimål + variasjon + ingrediens-gjenbruk (alle tre). |
| Ukestruktur | 4 måltid × 7 dager = 28 slots: frokost, lunsj, middag, kveldsmat. Middag tyngst. |
| Kategori→måltid | Kuratert oppslagstabell i Rust (ikke kcal-styrt, ikke fritekst). |
| Kveldsmat | Lett: brødskive/ostesmørbrød/pålegg — *ikke* full rett-trekking. |
| Kalorimål | Daglig totalmål, fast fordeling per slot (20/25/40/15 %). |
| Personer | Skalerer handlelista (porsjoner × personer); påvirker ikke rett-valg. |
| Kosthold | Gjenbruker aktive globale diett-filtre (ingen ny diett-UI). |
| kcal/porsjon | Beregnes on-demand i Rust per generering — **ingen skjemaendring/cache**. |
| Etter generering | Lås + regener ulåste · send til handleliste · lagre uka. |

## Arkitektur

Egen sidebar-visning `📅 Matplan` (modus `__plan__`, samme mønster som 🧊
Kjøleskap `__lager__`). Tre lag:

1. **Ren logikk (node-testbar)** — `matplan-logikk.ts`: kalori-fordeling på slots,
   variasjons-/gjenbruks-scoring, rester-plassering, lås-respekt. Ingen Tauri-import.
2. **Rust-kommando** — `generer_matplan(...)`: kvalifiserer retter per slot
   (kategori→slot-mapping + on-demand kcal/porsjon + aktive diett-filtre via
   `bygg_diett_filter`), kjører grådig fyll med scoring, returnerer en 28-slot uke.
   Indeksert SQL, server-side.
3. **Store + UI** — `matplan.ts` (`matplan.json`, lagrer aktiv uke) + rutenett-
   visningen i `+page.svelte`.

### Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src/lib/matplan-logikk.ts` | Ren logikk: fordeling, scoring, rester, lås | Create |
| `kokebok-app/src/lib/matplan-logikk.test.mjs` | node-tester | Create |
| `kokebok-app/src/lib/matplan.ts` | Tauri Store-wrapper (`matplan.json`) | Create |
| `kokebok-app/src-tauri/src/lib.rs` | `generer_matplan` + kategori→slot-tabell + on-demand kcal | Modify |
| `kokebok-app/src/routes/+page.svelte` | `__plan__`-visning, rutenett m/kcal, reroll, send-til-handleliste | Modify |

Mønstre gjenbrukt: `lager.ts`/`handleliste.ts` (Store-CRUD), `lager-logikk.ts`
(node-testbar ren logikk), `__lager__`/`__handle__`/`__innst__` (sidebar-modus),
`bygg_diett_filter` (kosthold-filter), `idx_ing_opp_navn` (ingrediens-oppslag),
kcal-CASE fra `hent_oppskrift` (enhet→gram→kcal).

## Datamodell

**`matplan.json`** (Tauri Store, nøkkel `uke`):
```ts
type SlotType = "frokost" | "lunsj" | "middag" | "kveldsmat";
type Slot =
  | { kind: "rett"; id: number; navn: string; kcal: number | null; laast: boolean }
  | { kind: "rester"; visTekst: string; laast: boolean }   // peker på gårsdagens middag
  | { kind: "enkel"; visTekst: string; laast: boolean }    // kveldsmat: «Brødskive», «Ostesmørbrød»
  | { kind: "tom"; grunn: string };                        // ingen passende rett
type Dag = { frokost: Slot; lunsj: Slot; middag: Slot; kveldsmat: Slot; kcalDag: number | null };
type Uke = { dager: Dag[]; /* alltid 7 */ dagsmaal: number; personer: number; generert: string /*ISO*/ };
```

## Komponent A: Ren logikk `matplan-logikk.ts`

Node-testbar. Sentrale funksjoner:

```ts
export const FORDELING = { frokost: 0.20, lunsj: 0.25, middag: 0.40, kveldsmat: 0.15 };
/** kcal-mål per slot ut fra dagsmål. */
export function slotMaal(dagsmaal: number): Record<SlotType, number>;
/** Score en kandidat: nær kcal-mål + variasjon (straff gjentakelse) + gjenbruk
 *  (bonus delte råvarer) + liten jitter. Høyere = bedre. */
export function scoreKandidat(
  kand: { kcal: number | null; type: string; ingredienser: string[] },
  slotMaalKcal: number,
  bruktType: Set<string>,        // typer alt valgt denne uka (variasjon)
  brukteIngredienser: Set<string>, // råvarer alt valgt (gjenbruk)
  jitter: number,
): number;
/** Sum kcal for en dags valgte slots (rester/enkel/tom teller ikke ny kcal). */
export function kcalForDag(slots: Slot[]): number | null;
```

Variasjon og gjenbruk trekker mot hver sin retning; vektene balanseres så man får
*litt* råvare-overlapp uten ensformighet. Variasjons-signal = rettens `type`
(kategori) + tyngste ingredienser (vi har ikke et eksplisitt hovedingrediens-felt).

## Komponent B: Store-wrapper `matplan.ts`

Speiler `lager.ts` (best-effort):
| Funksjon | Ansvar |
|----------|--------|
| `matplanLast()` | les `Uke \| null`; null ved feil/ingen lagret |
| `matplanLagre(uke)` | persistér aktiv uke |
| `matplanTøm()` | slett lagret uke |

## Komponent C: Rust-kommando `generer_matplan`

```rust
#[tauri::command]
fn generer_matplan(
    app: AppHandle,
    dagsmaal: i64,
    personer: i64,            // videreført til frontend for handleliste-skalering
    dietter: Option<Vec<String>>,
    laaste: Vec<LaastSlot>,   // { dag: usize, slot: String, id: i64 } — beholdes
) -> Result<UkeSvar, String>;
```

**Kategori→slot-mapping** — definert ett sted som oppslag:
- **frokost** ← Frokost, Vafler/pannekaker, Drikke, (lett Brød/bakverk)
- **lunsj** ← Lunsj, Sandwich/smørbrød, Salater, Supper, Tapas/småretter, Smårett, Forrett, Forretter
- **middag** ← Middag, Gryter, Ovnsretter, Pasta, Pizza, Biffer, Koteletter, Wok,
  Kyllingfilet, Hele fileter, Steker, Panneretter, Kjøttdeig- og farseretter,
  Grillspyd, Grillet kylling, Vegetar, Turmat
- **kveldsmat** — *spesial*: Sandwich/smørbrød + Pålegg + faste enkle tekster
  («Brødskive», «Ostesmørbrød», «Knekkebrød med pålegg»); lav kcal-andel.
- **Ekskludert fra alle måltids-slots:** Dessert, Kaker, Drikke (utenom frokost),
  Snacks, Koldtbord — brukes ikke som måltid.

**On-demand kcal/porsjon:** for kvalifiserte kandidater per slot, beregn
kcal/porsjon med samme enhet→gram→kcal-CASE som `hent_oppskrift`
(`naering`-join), delt på `porsjoner`. Retter uten kcal-signal beholdes men
ekskluderes fra kcal-scoringen (vises «?»).

**Algoritme (grådig, regelbasert):**
1. Kvalifiser per slot: mapper til slot, passer diett-filtre (`bygg_diett_filter`),
   hent kcal/porsjon + type + ingrediensnavn.
2. `slotMaal(dagsmaal)` gir kcal-andel per slot (±25 % margin som mykt mål).
3. Gå slot for slot gjennom uka; behold låste; for ulåste velg høyest
   `scoreKandidat` (nær kcal + variasjon + gjenbruk + jitter). Oppdater
   brukt-type/-ingrediens-settene underveis.
4. **Rester:** noen lunsjer (f.eks. annenhver) settes til `kind:"rester"` som peker
   på forrige dags middag — trekker ikke ny rett, teller ikke ny kcal/handleliste.
5. **Kveldsmat:** trekk enkelt fra kveldsmat-poolen / faste tekster.
6. Tomt kvalifisert utvalg → `kind:"tom"` med grunn; resten genereres likevel.

Returnerer hele uka + kcal/dag + ukesnitt. `LIMIT`/utvalg holdes effektivt via
kategori-filtrert SQL; kcal beregnes kun for kandidatene som faktisk vurderes.

## Komponent D: UI (`__plan__`-visning i `+page.svelte`)

Ny sidebar-oppføring «📅 Matplan» (f.eks. etter 🧊 Kjøleskap) → `currentKategori
=== "__plan__"`. Må legges i de samme modus-ekskluderingene som `__lager__`
(søk/grid/header/paginering) — fire steder.

**Kontrollrad:** dagsmål-input (kcal), antall personer, «↻ Generer» (bruker aktive
diett-filtre — vis evt. en liten «N filtre aktive»-indikator).

**Rutenett:** tabell, dager nedover (Man–Søn), måltider bortover (frokost/lunsj/
middag/kveldsmat), + **kcal/dag-kolonne** ytterst: grønn ✓ nær dagsmål, oransje ⚠
langt unna. **Ukesnitt** i bunnraden. Hver rett-celle: navn + 🔒 (lås) + ↻ (bytt
enkeltrett). Rester-celle: grå «Rester: \<middag\>». Tom-celle: «Ingen passende
rett — juster filtre». Klikk rett-navn → `åpneOppskrift(id)`.

**Knapper:** «↻ Generer ulåste på nytt», «🛒 Send uka til handleliste» (alle
`kind:"rett"`-retter, porsjoner × personer, via `handlelisteLeggTil`), «💾 Lagre
uka» (`matplanLagre`).

**Reaktivitet:** generering/reroll oppdaterer uka i `$state`; kcal/dag utledes.

## Dataflyt

```
ÅPNE:    uke = await matplanLast()  (gjenoppretter lagret uke om finnes)
GENERER: dagsmål + personer + aktive diett-filtre
         → invoke(generer_matplan, {dagsmaal, personer, dietter, laaste:[]})
REROLL:  lås slots → invoke(generer_matplan, {..., laaste:[…]}) (kun ulåste trekkes)
HANDLE:  «Send til handleliste» → kind:"rett"-retter, porsjoner×personer → handlelisteLeggTil
LAGRE:   matplanLagre(uke) → matplan.json
KCAL:    kcalForDag(slots) → fargekode mot dagsmål; ukesnitt i bunn
```

## Feilhåndtering

- Tomt kvalifisert utvalg for en slot → `kind:"tom"`, resten genereres; aldri krasj.
- Rett uten kcal-signal → ekskludert fra kcal-scoring, kan velges, kcal «?».
- Store best-effort (lager/handleliste-mønster): feil logges, tom/null ved feil.
- Manglende `naering`-/kategori-data → færre kandidater, aldri krasj.

## Testing

- **Ren logikk** (`matplan-logikk.test.mjs`, node): `slotMaal` summerer til
  dagsmålet; `scoreKandidat` premierer nær-kcal og straffer gjentatt type/ingrediens;
  `kcalForDag` ignorerer rester/enkel/tom; lås beholdes.
- **Rust mot DB:** vegetar-filter → alle middager faktisk vegetar; kcal/dag innen
  rimelig margin av dagsmål; ingen Dessert/Kaker i måltids-slots; rester peker på
  riktig middag.
- **Manuell e2e:** generer uke; lås retter + reroll (låste består); send til
  handleliste (skalert på personer); lagre + omstart (uka består); stramt filter →
  «tom»-celler uten krasj.

## Distribusjon

Ingen `kokt.db`-skjemaendring (uke i Store, kcal on-demand). Ingen nye
avhengigheter. Gjenbruker `naering`/`priser`-uavhengig (pris droppet),
`bygg_diett_filter`, `idx_ing_opp_navn` — alt finnes i bundle.

## Avgrensninger (ikke i denne saken — YAGNI)

- Ingen pris/budsjett (data for tynn).
- Ingen flere uker samtidig (én aktiv uke).
- Ingen drag-and-drop mellom slots.
- Ingen egendefinert kcal-fordeling i UI (fast 20/25/40/15 i v1).
- Ingen næringsmål utover kcal (protein/fett finnes i data, ikke i v1).
- Ingen auto-generering av kveldsmat-oppskrifter (faste enkle forslag).
