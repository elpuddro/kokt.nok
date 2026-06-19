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

11. **Cook Mode** — skjermen låser seg ikke / maskinen går ikke i hvilemodus
    mens en oppskrift er åpen, så man slipper å ta på PC-en med skitne fingre.
    Enklest og mest selvstendig: Tauri/OS-API for å hindre skjermsparer/dvale
    (request_user_attention / platform-spesifikk «keep awake»), aktiv kun i
    detaljvisning. Lav risiko, høy kjøkken-nytte.

12. **Innebygde timere** — trykk direkte på steketid i trinn-teksten («kok i 8
    minutter») for å starte nedtelling i appen. **Skjult kostnad:** parse
    tid+enhet ut av fritekst i `trinn.tekst` (regex: «8 minutter», «1 time»,
    «1½ t»), gjøre tallet klikkbart, og en timer-UI med varsel. Ren frontend,
    men tekst-parsingen må være robust.

13. **«Hva har jeg i kjøleskapet?»** — bruker legger inn råvarer de har, appen
    foreslår oppskrifter som bruker disse (mest mulig dekning først) for å
    redusere matsvinn. **Skjult kostnad:** match brukerens råvarer mot
    `ingredienser.navn` over 5962 oppskrifter og ranger på dekningsgrad
    (hvor stor andel av oppskriftens ingredienser brukeren har). Kan bygge på
    eksisterende ingrediens-søk; rangeringslogikken er kjernen.
