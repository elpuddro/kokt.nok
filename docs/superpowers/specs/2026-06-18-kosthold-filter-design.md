# Kosthold- og allergifilter (halal + diett/allergi) — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-18.
> Backlog-idéer #9 (halal/haram) + #10 (allergi/diett) — samlet, fordi de deler
> én underliggende klassifiseringsjobb. Filtrene er bare UI oppå.

## Mål

La brukeren skjule oppskrifter som ikke passer kostholdet/troen sin: et
halal-vennlig filter (uten åpenbart haram) og allergen-/diettfiltre (vegetar,
vegansk, glutenfri, laktosefri, uten nøtter). Filtrene bor i Innstillinger-
visningen sammen med tema.

## Ærlighetsprinsipp (halal-korrekthet)

Ingrediensnavn-screening er **ikke** halal-sertifisering. Vi kan pålitelig
oppdage *åpenbart haram-ingredienser* (svin og derivater, alkohol, blod,
gelatin/løpe) fra ingrediensnavn + råtekst. Vi kan **ikke** verifisere fra disse
dataene om storfe/kylling/lam ble halal-slaktet, eller kilden til gelatin/løpe.

Derfor (brukervalg, låst): halal-filteret skjuler oppskrifter med *eksplisitt
haram* ingrediens. Vanlig kjøtt tillates (brukeren skaffer halal-kjøtt selv).
UI-et merker det **«halal-vennlig (uten åpenbart haram)»**, ikke
«halal-sertifisert». Allergenfiltrene merkes tilsvarende «beste-evne, ikke en
garanti».

## Arkitektur

Forhåndsberegnet tagg-tabell i `kokt.db` (speiler `naering`/`priser`-mønsteret).
Et versjonert, testet Python-skript klassifiserer ingredienser via kuraterte
nøkkelord-regler. Filteret blir en ren SQL-`NOT EXISTS`-betingelse i den
eksisterende `hent_oppskrifter`-kommandoen, så **paginering og tellinger forblir
korrekte**. Religiøst sensitiv logikk holdes i testbar, reviderbar Python (ikke
LLM, ikke Rust).

### Komponenter

1. **Tagg-tabell + indeks** (`kokt.db`):
   ```sql
   CREATE TABLE ingrediens_tagg (
     navn  TEXT NOT NULL,      -- normalisert ingrediensnavn (lowercase, trimmet)
     tagg  TEXT NOT NULL,      -- se taggsett under
     PRIMARY KEY (navn, tagg)
   );
   CREATE INDEX idx_tagg_navn ON ingrediens_tagg(navn);
   ```
   Én rad per (ingrediens, egenskap). Et navn kan ha flere tagger.

2. **Klassifiseringsskript** `scripts/tagg_ingredienser.py` (speiler
   `hent_naering.py`):
   - Finn DB (samme `_finn_db()`-mønster som de andre skriptene).
   - Hent alle distinkte `navn` + tilhørende `raatekst` fra `ingredienser`.
   - For hvert navn: kjør kuraterte nøkkelord-regler mot **navn OG råtekst**
     (svin gjemmer seg i fritekst, f.eks. «bacon i terninger»). Treff → tagg.
   - Idempotent: `DELETE FROM ingrediens_tagg` (eller DROP+CREATE) før innsetting,
     så re-kjøring gir rent resultat.
   - Skriv én `(navn, tagg)`-rad per treff.

3. **Tagg-regler** (i `tagg_ingredienser.py`, som datastruktur
   `REGLER: dict[str, list[str]]` = tagg → nøkkelord). Nøkkelord matcher som
   delstreng i normalisert (lowercase) navn/råtekst. Seed-lister:

   | Tagg | Seed-nøkkelord |
   |------|----------------|
   | `svin` | svin, bacon, skinke, spekeskinke, serrano, prosciutto, chorizo, pancetta, salami, pepperoni, leverpostei, ister, flesk, bog (svine-), knoke (svine-) |
   | `alkohol` | rødvin, hvitvin, vin (se note), øl (se note), cognac, konjakk, rom (se note), likør, sherry, marsala, mirin, akevitt |
   | `blod` | blod, blodpudding, blodklubb |
   | `gelatin` | gelatin, gelatinplate, husblas; løpe/rennet → *tvilsom, merkes i kommentar* |
   | `kjott` | kjøtt, kjøttdeig, kylling, storfe, biff, lam, kalv, okse, and, kalkun, vilt, reinsdyr, bacon, pølse, skinke, spekemat |
   | `fisk` | fisk, laks, ørret, torsk, sei, makrell, tunfisk, reke, skalldyr, blåskjell, krabbe, sild, ansjos, sardin |
   | `egg` | egg, eggeplomme, eggehvite, majones |
   | `melk` | melk, fløte, kremfløte, smør, ost, parmesan, yoghurt, rømme, crème fraîche, kesam, cottage |
   | `gluten` | hvetemel, hvete, bygg, rug, semulegryn, couscous, brød, pasta, soyasaus, ølgjær |
   | `nott` | mandel, hasselnøtt, valnøtt, peanøtt, cashew, pistasj, pekan, paranøtt, nøtt |
   | `honning` | honning |

   `honning`-taggen brukes KUN av vegansk-filteret (vegetar tillater honning).

   **Falske-positiv-feller (håndteres eksplisitt i regelfila med kommentar):**
   - `vin` må ikke matche «vineddik», «druer/vindruer», «vinmonopol»-fritekst →
     bruk ordgrense / eksplisitt unntaksliste.
   - `øl` må ikke matche «mølje», «kjøttbolle», «smør» osv. → ordgrense.
   - `rom` må ikke matche «romtemperert», «rømme», «aromat» → ordgrense/unntak.
   - `egg` må ikke matche «eggplante/aubergine» → unntak.
   - `and` (fugl) må ikke matche «mandel», «koriander», «vaniljestang» →
     ordgrense + unntak.
   - vaniljeekstrakt → `alkohol` (inneholder alkohol) — eksplisitt regel.
   - worcestershire(saus) → `fisk` (ansjos) — eksplisitt regel.
   - `smør` → `melk`, men *peanøttsmør* → `nott` (ikke melk), *kakaosmør* →
     ingen → eksplisitte unntak.

   Implementasjonsnote (TRE matchestrategier — kritisk for norsk):
   - **ORDGRENSE** `\bord\b` (begge grenser): KUN korte kollisjonsord der prefiks
     ville gi false positives — `and` (mat-fugl, ikke «andre»), `vin` (ikke
     «vineddik»), `øl`, `rom`, `egg`, `honning` (ikke «honningmelon»).
   - **PREFIKS** `\bord` (kun ledende grense): for norske LUKKEDE SAMMENSETNINGER.
     `kylling` må treffe «kyllingfilet», `laks` → «laksefilet», `blod` →
     «blodpudding», `lam` → «lammelår». Dette er avgjørende — uten det slipper
     ~173 kyllingfilet-retter gjennom vegetar-filteret og blodpudding gjennom
     halal. Gjelder kjøtt/fisk/blod-ordene.
   - **DELSTRENG** (ren `in`): lange entydige ord uten kollisjonsfare (gelatin,
     hvetemel, hasselnøtt, svin, melk …).
   Unntakslista fanger prefiks-feller funnet i data: `blodappelsin` (frukt, ikke
   blod), `seig` (ikke «sei»-fisk). Hver regel + sammensetning + felle er dekket
   av en pytest-test (25 tester totalt).

4. **Filter-katalog (én kilde til sannhet)** — hvert brukervendt filter mapper
   til et sett tagger det ekskluderer. Definert TO steder som må holdes i sync
   (dekkes av plan-tasken): frontend `DIETT_FILTRE` (for UI) og Rust-mapping
   (for spørringen).

   | Filter-ID | Visningsnavn | Ekskluderer tagger |
   |-----------|--------------|--------------------|
   | `halal` | Halal-vennlig (uten åpenbart haram) | svin, alkohol, blod, gelatin |
   | `vegetar` | Vegetar | kjott, fisk |
   | `vegansk` | Vegansk | kjott, fisk, egg, melk, gelatin, honning |
   | `glutenfri` | Glutenfri | gluten |
   | `laktosefri` | Laktosefri / melkefri | melk |
   | `nott` | Uten nøtter | nott |

   `honning`-taggen brukes kun her (vegetar tillater honning), derfor er den en
   egen tagg framfor å puttes i `melk`-gruppen.

5. **Store-wrapper** `kokebok-app/src/lib/diett.ts` (speiler `tema.ts`):
   | Funksjon/eksport | Ansvar |
   |------------------|--------|
   | `DIETT_FILTRE` | konstant: liste av `{ id, navn, beskrivelse }` for UI |
   | `diettLast()` | les `string[]` (aktive filter-ID-er) fra `diett.json`; tom liste ved feil |
   | `diettSett(aktive)` | lagre `string[]` (best-effort), returner ny liste |
   Lagres i `diett.json`, nøkkel `aktive`.

6. **Rust-filtrering** — `hent_oppskrifter` får ny valgfri parameter
   `dietter: Option<Vec<String>>`. En intern mapping `filter_id → &[tagg]`
   (samme innhold som tabellen over). For hvert gyldig aktivt filter legges en
   `NOT EXISTS`-betingelse til den eksisterende `conds`-vektoren (AND-kombinert):
   ```sql
   AND NOT EXISTS (
     SELECT 1 FROM ingredienser i
     JOIN ingrediens_tagg t ON t.navn = i.navn
     WHERE i.oppskrift_id = o.id AND t.tagg IN (<filterets tagger>)
   )
   ```
   Tagg-verdiene legges i `owned` som parametre. Gjenbruker eksisterende
   `conds`/`owned`-mekanisme → `COUNT(*)` og `LIMIT/OFFSET` forblir korrekte.
   Ukjente filter-ID-er ignoreres. `hent_oppskrifter_by_ids` (favoritter) berøres
   IKKE — favoritter filtreres aldri bort.

7. **UI i `+page.svelte`:**
   - State: `let aktiveDietter = $state<string[]>([])`, lastet i `onMount`.
   - **Innstillinger-seksjon:** ny `<section class="innst-seksjon">` under
     tema-seksjonen i `__innst__`-visningen. Overskrift «🍽️ Kosthold og
     allergier», ansvarsfraskrivelse-merknad, så én avkrysningsboks per
     `DIETT_FILTRE`-element (`<label class="diett-valg">` med checkbox, samme
     visuelle mønster som tema-radioknappene). Halal-merknad: «halal-vennlig»,
     ikke «halal-sertifisert».
   - **Toggle-handler:** ved endring → oppdater `aktiveDietter` →
     `await diettSett(aktiveDietter)` → `side = 1; fetchGrid()`.
   - **`fetchGrid`:** send `dietter: aktiveDietter` med i `invoke("hent_oppskrifter", …)`.
   - **Aktiv-indikator:** når `aktiveDietter.length > 0`, vis en liten klikkbar
     pille i hovedoverskrift-raden, f.eks. «🍽️ N filtre aktive», som hopper til
     Innstillinger (`currentKategori = "__innst__"`). Hindrer «hvorfor mangler
     oppskrifter?»-forvirring.
   - **Tom-tilstand:** når filtre er på og en kategori blir tom, vis en hjelpe-
     linje i det eksisterende «Ingen oppskrifter funnet»-feltet: «(noen kan være
     skjult av aktive kostholdsfiltre)».

## Dataflyt

```
BYGG (offline):  scripts/tagg_ingredienser.py  →  ingrediens_tagg-tabell i kokt.db
OPPSTART:        aktiveDietter = await diettLast()
TOGGLE (id):     oppdater liste → diettSett(liste) → side=1 → fetchGrid()
FETCH:           invoke(hent_oppskrifter, {..., dietter: aktiveDietter})
                   → Rust legger NOT EXISTS per filter (AND) → korrekt total+side
INDIKATOR:       aktiveDietter.length > 0 → «🍽️ N filtre aktive»-pille
```

## Feilhåndtering

- Store best-effort (tema-mønster): feil logges, app fungerer videre.
- **Manglende `ingrediens_tagg`-tabell** (gammel DB): Rust sjekker at tabellen
  finnes; hvis ikke, hoppes diett-betingelsene over (ingen filtrering) i stedet
  for å krasje. Logges.
- Ukjent filter-ID i lagret liste: ignoreres av Rust-mappingen.
- Ingen treff etter filtrering: normal tom-tilstand med hjelpelinje.

## Testing

- **Kjerne — regel-korrekthet:** `scripts/test_tagg_ingredienser.py` (pytest).
  Dekker hver tagg + falske-positiv-fellene: bacon→{svin,kjott}, rødvin→alkohol,
  vineddik→∅, hvetemel→gluten, mandel→nott, peanøttsmør→nott (ikke melk),
  kylling→kjott, tofu→∅, eggplante→∅ (ikke egg), rømme→melk (ikke alkohol via
  «rom»), «bacon i terninger» (råtekst)→svin, vaniljeekstrakt→alkohol,
  worcestershire→fisk, honning→honning.
- **Frontend/Rust:** `npm run build` (Svelte) + `cargo build` (Rust) + manuell
  e2e: slå på halal → svineretter forsvinner, total/sidetall korrekt; kombiner
  glutenfri → snevrere; aktiv-indikator vises; skru av alt → alt tilbake;
  restart app → valg består.

## Distribusjon (løs tråd foldet inn)

`ingrediens_tagg`-tabellen MÅ bygges inn i både `kokt.db` (kilde) og
`kokt-bundle.db` (portable). `scripts/bygg_bundle_db.py` må ta tabellen med, og
portable-binærene rebygges før neste fengsels-distribusjon. Dette noteres
eksplisitt i planen så det ikke oppdages ved overleveringen. (Bundle-DB-en
henger uansett etter på oppskriftsdata — 4444 vs 5962 — så en bundle-rebygging
trengs uavhengig.)

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Halal-omfang | Skjul kun åpenbart haram; «halal-vennlig», ikke «sertifisert» |
| Diettfiltre v1 | Vegetar, vegansk, glutenfri, laktosefri, uten nøtter |
| Kombinering | AND — alle påslåtte filtre må oppfylles |
| Klassifisering | Forhåndsberegnet `ingrediens_tagg`-tabell, kuraterte regler i Python |
| Synlighet | Seksjon i Innstillinger + liten aktiv-filter-indikator i topplinjen |
| Persistering | Tauri Store `diett.json` (`string[]` aktive filter-ID-er) |

## Klassifiserings-policy (avklart under e2e)

Navn-/ingrediensbasert klassifisering har en irreduserbar hale (eksotiske/
utenlandske termer i søpla-kategorier uten strukturelt signal). Bar satt slik:

- **Tre strategier etter tvetydighet:** delstreng for lange entydige røtter
  (fanger prefiks+suffiks+alene), ordgrense/prefiks for korte kollisjonsord
  (and/sei/lam/uer/sik) med unntakslister.
- **Kategori-signal:** oppskrifter i kjøtt/fisk-`type` (Biffer, Steker,
  Koteletter, Kyllingfilet, Kjøttdeig, Grillet kylling, Hele fileter) skjules av
  vegetar/vegansk uansett ingrediensnavn — fanger «côte de boeuf» o.l.
- **svin ⊆ kjøtt:** alt svin teller som kjøtt (vegetar skjuler salami/ribbe).
- **ribbe = svin** (norsk ribbe; lammeribbe-unntak → forblir lam/halal-ok).
- **pølse = svin** (brukervalg, halal-konservativt): uspesifisert pølse regnes
  som svin. Kylling-/lamme-/vegetarpølse får unntak og forblir ikke-svin.
- **Plantebasert-strip:** ingrediens-/oppskriftsnavn med vegetar/soya/quorn/tofu
  mister kjøtt/fisk/svin-tagg.
- **Harm vs irritasjon:** halal-stien (svin/alkohol/blod/gelatin) holdes tett på
  vanlig haram; vegetar/diett er beste-evne med skjerm-disclaimer. Residual etter
  full audit: halal ~0 reelle på vanlig svin, vegetar ~3 av 2444.
- **Ytelse:** indeks `idx_ing_opp_navn(oppskrift_id, navn)` — uten den henger
  filteret ~35 s (fullt scan per oppskrift); med den ~25 ms.

## Avgrensninger (ikke i denne saken — YAGNI)

- Ingen streng/mild-glidebryter eller mashbooh tri-tilstand (binære tagger v1).
- Ingen per-oppskrift «hvorfor skjult?»-forklaring.
- Ingen LLM-klassifisering (reproduserbarhet/reviderbarhet kreves).
- Favoritter filtreres ikke (bevisst valgt av brukeren).
- Klassifiseringen er navnebasert beste-evne — ikke en medisinsk/religiøs garanti.
