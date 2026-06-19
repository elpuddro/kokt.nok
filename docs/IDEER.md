# Idéer / backlog — Kokebok

Hver ny idé bør gjennom brainstorming → spec → plan før implementering
(se `docs/superpowers/`).

Opprinnelig lagt til 2026-06-12. Status oppdatert 2026-06-17.

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

- **Rebygg portable med ny data:** `kokt-bundle.db` (innebygde bilder, brukt av
  portable-bygget) har fortsatt 4444 matprat-oppskrifter, ikke de nye 5962.
  Kjør `scripts/bygg_bundle_db.py` + rebygg binærene før neste distribusjon.
  Merk: `bygg_bundle_db.py` bruker `shutil.copy2` av hele kokt.db, så den nye
  `ingrediens_tagg`-tabellen (kosthold-filter) følger automatisk med — men
  bundle-en MÅ rebygges for at filtrene skal virke i portable-distribusjonen.

---

## 💡 Nye idéer (lagt til 2026-06-17, ikke designet ennå)

5. **Bedre søk / filtrering** — filtrer på ingrediens («hva kan jeg lage med
   kylling?»), tid, vegetar/vegan, allergener. Mer verdifullt med 5962
   oppskrifter. Bygger på eksisterende søk i `hent_oppskrifter`.

6. **Ukesmeny / måltidsplan** — planlegg flere dager med måltider, generer
   samlet handleliste for uka. Bygger rett på handlelista + porsjonsskalering.

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

13. **«Hva har jeg i kjøleskapet?»** — bruker legger inn råvarer de har, appen
    foreslår oppskrifter som bruker disse (mest mulig dekning først) for å
    redusere matsvinn. **Skjult kostnad:** match brukerens råvarer mot
    `ingredienser.navn` over 5962 oppskrifter og ranger på dekningsgrad
    (hvor stor andel av oppskriftens ingredienser brukeren har). Kan bygge på
    eksisterende ingrediens-søk; rangeringslogikken er kjernen.

---

## 💡 Nye idéer (lagt til 2026-06-19, ikke designet ennå)

> **Felles arkitektur-spørsmål for #14, #18, #19 (og delvis #15):** disse
> forutsetter en AI/LLM ved kjøretid, noe som kolliderer med offline-først /
> luftgap-distribusjonen (fengsel). Hver må avklare mekanisme i brainstorming:
> innebygd lokal modell (stor), online-kun «hjemme»-variant, eller
> mal-/regelbasert pseudo-generering uten LLM.

14. **AI-oppskriftsgenerator** — fritekst inn («noe med laks, spinat og pasta»)
    → generert oppskrift (fremgangsmåte, estimert tid, næring). **Krever LLM ved
    kjøretid** (se arkitektur-note over). Mal-/regelbasert variant mulig uten AI,
    men gir svakere resultat.

15. **Smart matplanlegger** — ukemeny ut fra budsjett, kalorimål, antall personer
    og kosthold; genererer meny + samlet handleliste. Bygger på handlelista +
    porsjonsskalering + pris/næring som alt finnes. Kjernen (constraint-løsing:
    velg retter som treffer budsjett/kalori/diett) kan gjøres **regelbasert uten
    AI**; LLM valgfritt for «variér menyen»-finpuss. Overlapper #6 (ukesmeny).

16. **Lagerstyring (mini-ERP for kjøkkenet)** — registrer beholdning i skap/kjøl/
    fryser, trekk automatisk fra brukte ingredienser (fra handleliste/laging),
    varsle om utløpsdato. **Skjult kostnad:** ny skrivbar datamodell (beholdning +
    utløp) og fratrekks-logikk. Tett koblet til #13/#17. Ren frontend + Tauri
    Store (eller egen skrivbar DB). Ingen AI.

17. **«Hva har jeg i kjøleskapet?»** — *samme som #13* (bruker registrerer råvarer
    → forslag på «kan lages nå» / «mangler få» / «bruk før utløp»). Slå sammen med
    #13; #16 (lager) gir input-dataene. Ingen AI; rangeringslogikk er kjernen.

18. **Oppskriftsversjonering («Git for mat»)** — bruker lagrer egne endringer av en
    oppskrift som versjoner (Lasagne v1.0 → v1.1 «mer hvitløk» → v2.0), kan
    sammenligne/gjenopprette/bla bakover. **Skjult kostnad:** skrivbar versjonert
    datamodell (diff/historikk per oppskrift) + diff-UI. Bygger på «egne
    oppskrifter»-utvidelsen nevnt under notater (#7). Ingen AI.

19. **Næringsanalyse + helseprofil** — bruker legger inn høyde/vekt (→ BMI),
    aktivitetsnivå og mål (vektned-/oppgang); appen analyserer alle oppskrifter
    og gir tilpassede ukesforslag (kalorier/protein/karbo/fett/fiber/vitaminer),
    filtrerbart på lavkarbo/vegetar/vegan/glutenfri/diabetesvennlig + forslag til
    sunnere alternativer. **Skjult kostnad:** bygger på eksisterende `naering`-
    tabell + diett-tagger (#9/#10), men trenger BMR/TDEE-beregning,
    mål-constraint-løsing (gjenbruk #15), og evt. utvidet næringsdata (vitaminer
    finnes ikke i dagens `naering`-tabell — kun makro + fiber). «Ukesforslag» er
    samme constraint-motor som #15. Ingen AI nødvendig (regelbasert).
