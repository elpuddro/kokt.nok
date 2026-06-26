# Idéer / backlog — Kokebok

Hver ny idé bør gjennom brainstorming → spec → plan før implementering
(se `docs/superpowers/`).

Opprinnelig lagt til 2026-06-12. Status oppdatert 2026-06-24 (sist: #18 ferdig).

---

## ✅ Ferdig (hele den opprinnelige backlogen)

1. **Handleliste / innkjøpsliste** — ferdig 2026-06-17. Legg oppskrifter til
   liste, sammenslått ingrediensliste (navn+enhet, skalert per porsjoner),
   estimert totalsum, tøm/fjern/juster. Tauri Store-persistering.
   Spec: `docs/superpowers/specs/2026-06-16-handleliste-design.md`.
2. **Favoritter** — ferdig. Stjern oppskrifter (kort + detalj), filtrert
   sidebar-visning. Tauri Store (`favoritter.json`).
   Spec: `docs/superpowers/specs/2026-06-12-favoritter-design.md`.
3. **Bilder i SQL-databasen** — ferdig. Bilder som BLOB i kokt.db, servert via
   `kbilde://` Rust-protokoll med fil-fallback i dev.
   Spec: `docs/superpowers/specs/2026-06-15-bilder-i-db-design.md`.
4. **Portabel database + exe** — ferdig. `portable/`-mappe med Windows- og
   Linux-binær + delt kokt.db (bilder innebygd), uten installer. Med
   personvern-skrubbe-gate (fengsels-distribusjon).
   Spec: `docs/superpowers/specs/2026-06-16-portabel-distribusjon-design.md`.

**I tillegg (ikke i opprinnelig backlog):**
- **godt.no-skraper** — andre datakilde ved siden av matprat. DB nå 5962
  oppskrifter (4444 matprat + 1518 godt.no).
  Spec: `docs/superpowers/specs/2026-06-15-godt-scraper-design.md`.

---

## 🔧 Løse tråder (ikke funksjoner)

- **Portabel distribusjon er à jour** — bygget 2026-06-24 med alle features (#1–#22),
  bilder komprimert til 400px/q75 (141 MB, ned fra 281 MB). Scrub-gate grønn.
  Neste rebuild trengs kun ved nye features eller nye oppskrifter.

---

## 💡 Nye idéer (lagt til 2026-06-17, ikke designet ennå)

5. **Bedre søk / filtrering** — filtrer på ingrediens («hva kan jeg lage med
   kylling?»), tid, vegetar/vegan, allergener. Mer verdifullt med 5962
   oppskrifter. Bygger på eksisterende søk i `hent_oppskrifter`.

~~6. **Ukesmeny / måltidsplan**~~ — dekket av #15 + #23.

7. ~~**Egne notater / merknader**~~ — ✅ **FERDIG 2026-06-18.** Textarea nederst i
   detaljvisningen, auto-lagret debounced (~400 ms) til Tauri Store
   (`notater.json`: `Record<id, tekst>`). 📝-merke på kort med notat; tømt notat
   fjerner nøkkel + merke. Spec: `docs/superpowers/specs/2026-06-17-notater-design.md`.

8. ~~**Temaer / fargepaletter**~~ — ✅ **FERDIG 2026-06-17.** 11 temaer (varm,
   dark, 4 sesonger, 5 høytider) via `data-tema` + CSS-variabel-overstyring.
   Auto-bytte etter dato (eksakt påske via Computus) + manuell overstyring i
   Innstillinger-visning. Spec: `docs/superpowers/specs/2026-06-17-temaer-design.md`.

9. ~~**Halal/haram-filter**~~ + 10. ~~**Allergi- og diettfilter**~~ — ✅ **FERDIG
   2026-06-18** (samlet, delte én klassifiseringsjobb). Forhåndsberegnet
   `ingrediens_tagg`-tabell (kuraterte, testede nøkkelord-regler i
   `scripts/tagg_ingredienser.py`) + `NOT EXISTS`-filter i `hent_oppskrifter`
   (server-side, korrekt paginering) + toggles i Innstillinger + aktiv-indikator.
   Filtre: halal-vennlig (uten åpenbart haram), vegetar, vegansk, glutenfri,
   laktosefri, uten nøtter (AND-kombinert). Halal = «uten åpenbart haram», ikke
   sertifisering. Spec: `docs/superpowers/specs/2026-06-18-kosthold-filter-design.md`.

11. ~~**Cook Mode**~~ — ✅ **FERDIG 2026-06-18.** `cook_mode(on)` Tauri-kommando
    (Windows `SetThreadExecutionState`, Linux D-Bus screensaver-inhibit) + bryter
    i detaljvisning, auto-av ved lukk. Spec/plan: `docs/superpowers/{specs,plans}/2026-06-18-cookmode-timere*`.

12. ~~**Innebygde timere**~~ — ✅ **FERDIG 2026-06-18.** Klikkbare tider i trinn
    (`finnTider`-parser, 19 node-tester; intervall → øvre grense, brøk),
    flere samtidige timere i globalt panel, Web Audio-pip + visuell blink.
    Samme spec/plan som #11.

~~13. **«Hva har jeg i kjøleskapet?»**~~ — slått inn i #14 nedenfor.

---

## 💡 Nye idéer (lagt til 2026-06-19+)

> **Forkastet (krever AI/LLM ved kjøretid → kolliderer med offline-/luftgap-
> distribusjonen):** ~~AI-oppskriftsgenerator~~ og ~~næringsanalyse-helseprofil
> med AI-forslag~~ ble vurdert og lagt bort 2026-06-19.

~~14. **Lagerstyring + «Hva har jeg i kjøleskapet?»**~~ — ✅ **FERDIG 2026-06-20.**
    Beholdning i skap/kjøl/fryser, utløpsvarsler, «kan lages nå»-matching
    (dekningsgrad-rangering) + «Lagde denne»-knapp trekker brukte ingredienser
    fra lager. Tauri Store (`lager.json`). Ingen AI.
    Spec: `docs/superpowers/specs/2026-06-19-lager-kjoeleskap-design.md`.

~~15. **Smart matplanlegger**~~ — ✅ **FERDIG 2026-06-22.** Ukemeny (frokost/lunsj/
    middag/kveldsmat × 7 dager) ut fra kalorimål, diettfiltre og ingredienstyper.
    Scoring + grådig fyll i Rust, lås/reroll per slot, send ukemeny til
    handleliste, lagring i Tauri Store. Ingen AI.
    Spec: `docs/superpowers/specs/2026-06-22-matplanlegger-design.md`.

5. ~~**Bedre søk / filtrering**~~ — ✅ **FERDIG 2026-06-24.** AND-søk (hvert ord
   matcher navn eller ingredienser), sorteringsvalg (navn A–Å/Å–A, tid kortest/
   lengst) i header-dropdown, persistert i Tauri Store. 5 unit-tester for
   `tid_til_min`-parser.
   Spec: `docs/superpowers/specs/2026-06-24-bedre-sok-design.md`.

~~18. **Oppskriftsversjonering («Git for mat»)**~~ — ✅ **FERDIG 2026-06-24.**
    Bruker redigerer personlig kopi av scraped oppskrift (ingredienser, trinn,
    navn, beskrivelse, porsjoner, tid), manuelt lagrer versjoner med label,
    sammenligner mot original (fargekodet to-kolonne diff) og gjenoppretter.
    Profil-spesifikk, Tauri Store (`versjoner.json`). Ingen AI.
    Spec: `docs/superpowers/specs/2026-06-24-oppskriftsversjonering-design.md`.
    Plan: `docs/superpowers/plans/2026-06-24-oppskriftsversjonering.md`.

~~19. **Vinanbefaling fra Vinmonopolet**~~ — **STRØKET 2026-06-22.** API-problemer
    med Vinmonopolet; uforutsigbar tilgjengelighet og struktur gjør vedlikehold
    for krevende.

~~20. **Næringsanalyse og helseprofil**~~ — ✅ **FERDIG 2026-06-23.** Brukerprofil
    (navn, kjønn, alder, høyde, vekt, aktivitet, mål) med TDEE (Mifflin-St Jeor)
    og dagsbehov (kcal/protein/fett/karbo). Andel-av-dagsbehov-panel i
    detaljvisning. Aktivt profil-merke i header.
    Spec: `docs/superpowers/specs/2026-06-23-helseprofil-design.md`.

21. ~~**Tidsbasert forside**~~ — ✅ **FERDIG 2026-06-23.** Forsiden foreslår
    oppskrifter etter tidspunkt (frokost 06–10, lunsj 10–14, middag 14–18,
    kveld 18–22). Henter fra `forside_oppskrifter` Rust-kommando.
    Spec: `docs/superpowers/specs/2026-06-23-tidsbasert-forside-design.md`.

22. ~~**Midjefilter og sunnere matplan**~~ — ✅ **FERDIG 2026-06-24.** Midjemål i
    helseprofil; over grense (94 cm mann / 80 cm kvinne) aktiveres fett-penalty
    i matplanleggeren (`sunnPlan`-modus). Vises i profilkort.
    Spec: `docs/superpowers/specs/2026-06-24-midjefilter-design.md`.

---

## 💡 Idéer ikke designet ennå

6. **Ukesmeny / måltidsplan (utvidet)** — allerede dekket av #15, men rom for
   utvidelser: budsjett per uke, sesong-spesifikke retter (se #23 nedenfor).

~~23. **Sesong- og høytidsspesifikke oppskriftsforslag**~~ — ✅ **FERDIG 2026-06-25.**
    Forsiden bytter til sesong-kurerte retter i 7 høytidsvindu (jul, påske, 17. mai,
    sankthans, fårikålens dag, halloween, valentinsdag). Matplanleggeren får sesong-toggle
    (+50 score for høytidstagget rett). Nøkkelordbasert tagging via `scripts/tagg_hoytid.py`
    (957 oppskrifter tagget). `høytid TEXT`-kolonne i `kokt.db`. Rust-kommando `hoytid_aktiv()`
    med Computus-påskeberegning. Ingen AI.
    Spec: `docs/superpowers/specs/2026-06-24-hoytid-sesong-design.md`.
    Plan: `docs/superpowers/plans/2026-06-24-hoytid-sesong.md`.

~~24. **Høytidsdekorasjoner**~~ — ✅ **FERDIG 2026-06-25.**
    Diskret, brukerstyrt SVG-pynt på forsidebannerets under aktive høytidsperioder.
    Én dekorasjon per høytid (snøfnugg/egg/konfetti/flamme/spindelvev/hjerter), av som standard.
    Toggle i Innstillinger → Temaer, grås ut utenom høytid. Inline SVG, ingen bildefiler.
    Alkohol-holdige oppskrifter ekskludert permanent fra alle automatiske forslag.
    Spec: `docs/superpowers/specs/2026-06-25-hoytidspynt-design.md`.
    Plan: `docs/superpowers/plans/2026-06-25-hoytidspynt.md`.

---

## 💡 Idéer lagt til 2026-06-25

25. **Android-nettbrett-versjon** — Tauri v2 Android-port av hele appen, distribusjon
    via Google Play. Full funksjonsparitet med Windows/Linux. `ensure_db()` ved
    oppstart, `app_data_dir()`-basert sti, lesbar DB (oppskriftsredigering), wakelock
    for Cook Mode. UI-tilpasning for berøring og portrait/landscape.
    Spec: `docs/superpowers/specs/2026-06-25-android-tablet-design.md`. **Ikke startet.**

~~26. **DB-indeksoptimalisering**~~ — ✅ **FERDIG 2026-06-25.**
    Lagt til `idx_kat_kategori` på `kategorier(kategori)` og
    `idx_opp_hoytid` partial index på `oppskrifter(hoytid) WHERE hoytid IS NOT NULL`.
    Byttet `INSTR`→`LIKE`-query i `forside_oppskrifter` (22× speedup).
    Skript: `scripts/legg_til_indekser.py`.

~~27. **Fuzzy-søk (FTS5 trigram)**~~ — ✅ **FERDIG 2026-06-25.**
    `oppskrift_fts` contentless FTS5 trigram-tabell i `kokt.db`.
    Eksakt substring-søk først; OR-trigram fuzzy-fallback ved 0 treff.
    58× raskere enn LIKE (0.2ms vs 11.6ms). Fanger 1–2 bokstavs-avvik.
    Skript: `scripts/bygg_fts.py`. Rust: `fts_ids_for_ord()` i `lib.rs`.

~~28. **Oppskrift-deling**~~ — ✅ **FERDIG 2026-06-26.** Formatert tekst kopieres til utklippstavle (desktop) eller deles via system share-sheet (Android). Skjult i fengselsutgaven via VITE_UTGAVE=fengsel.

~~29. **Kaloriregnskap per dag**~~ — ✅ **FERDIG 2026-06-26.** Dagbok-visning med
    dag/uke/måned-tabs, logg-modal for oppskrifter og fri innføring, SVG-stolpegraf,
    fremgangsbar mot dagsbehov fra helseprofil. Persistert i Tauri Store. Ingen AI.
    Spec: `docs/superpowers/specs/2026-06-26-kaloriregnskap-design.md`.
    Plan: `docs/superpowers/plans/2026-06-26-kaloriregnskap.md`.

~~30. **Manuell prisregistrering + historikk**~~ — ✅ **FERDIG 2026-06-26.**
    Ingredienspriser registreres via kvitteringsmodus (tabellredigering med autofullføring),
    prishistorikk med SVG-linjediagram, handleliste viser estimert kostnad.
    Spec: `docs/superpowers/specs/2026-06-26-prisregistrering-design.md`.
    Plan: `docs/superpowers/plans/2026-06-26-prisregistrering.md`.

~~31. **Porsjons-kalkulator i Cook Mode**~~ — ✅ **ALLEREDE IMPLEMENTERT.**
    Porsjons-raden (−/+) er alltid synlig i detaljvisningen, som er samme view
    som Cook Mode bruker. Ingen endring nødvendig.

32. **Oppskrift-samlinger / «kokebok»** — brukeren kan lage navngitte samlinger
    (f.eks. «Julemiddag 2026», «Treningsmat», «Barnas favoritter») og legge
    oppskrifter i dem. Utvidelse av Favoritter-konseptet. Tauri Store.
    **Ikke startet.**

33. **Næringssammenligning** — sammenlign næringsinnhold mellom to eller tre
    oppskrifter side-om-side. Nyttig for å velge sunneste alternativ. Bygger
    på eksisterende næringsbereging i `hent_oppskrift`. **Ikke startet.**

~~34. **Mørk modus auto-bytte**~~ — ✅ **FERDIG 2026-06-25.** Auto-modus følger nå
    OS `prefers-color-scheme: dark` og bruker `"dark"`-temaet automatisk. Manuell
    overstyring uberørt. `matchMedia`-lytter for live-bytte (f.eks. systemet bytter
    om kvelden). `effektivtTema()`-hjelpefunksjon i `+page.svelte`.

35. **Offline oppdateringssjekk** (kun åpen/GitHub-utgave, ikke fengselsutgaven) —
    varsle brukeren diskret når en ny versjon er tilgjengelig på GitHub Releases,
    med lenke til nedlasting. Ingen auto-oppdatering, kun informasjon.
    **Ikke startet.**

36. **Sudokøkken** (easter egg) — Sudoku med mattema. Navn på celler/blokker
    inspirert av kjøkken og ingredienser (f.eks. 3×3-blokk kalles «gryte»,
    feil tall = «brent»). Klassisk 9×9-brett, tre vanskelighetsgrader, ingen
    ekstern data. Skjult bak kodenavn/hemmelig navigering. **Ikke startet.**

37. **Kokkeduellen** (easter egg) — blindtest-quiz: vis ingrediensliste fra en
    tilfeldig oppskrift i DB, gjett hva retten heter. Fire svaralternativer,
    poeng for riktig svar og hastighet, highscore i Tauri Store. Null ekstra
    data — henter rett fra eksisterende oppskrifter. **Ikke startet.**
