# Egne notater — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-17.

## Mål

La brukeren skrive egne notater på oppskrifter («brukte halv chili»), persistert
mellom økter. Backlog-idé #7.

## Arkitektur

Følger favoritt/handleliste-mønsteret: tynn `$lib/notater.ts` over Tauri Store,
all logikk i frontend, **ingen DB-skriving** (kokt.db er read-only).

**Datamodell (persistert i `notater.json`):** `Record<number, string>` —
`oppskriftId → notattekst`. Kun oppskrifter med ikke-tom tekst lagres. I minnet
holdt som `$state<Record<number, string>>` for reaktivt oppslag/oppdatering.

### To deler

1. **`kokebok-app/src/lib/notater.ts`** (speiler favoritter.ts):
   | Funksjon | Ansvar |
   |----------|--------|
   | `notaterLast()` | Les `Record<number,string>` fra `notater.json`; tomt objekt ved feil |
   | `notatSett(id, tekst, alle)` | Returner nytt objekt: trimmet tom tekst → slett nøkkel, ellers sett `id→tekst`; lagrer (best-effort) |
   Begge returnerer nytt objekt (Svelte 5-reaktivitet).

2. **`kokebok-app/src/routes/+page.svelte`:**
   - State: `let notater = $state<Record<number, string>>({});` lastet i `onMount`.
   - **Notatfelt i detalj** (nederst i `{#if currentOppskrift}`, etter trinn/næring):
     en «📝 Mine notater»-seksjon med `<textarea value={notater[opp.id] ?? ""}>`.
   - **Auto-lagre debounced** (~400 ms, samme `setTimeout`-mønster som søkefeltet):
     ```ts
     function onNotatInput(id, e) {
       const tekst = e.target.value;
       notater = { ...notater, [id]: tekst };       // umiddelbar reaktiv
       clearTimeout(notatTimer);
       notatTimer = setTimeout(async () => {
         notater = await notatSett(id, tekst, notater);  // persister + rydd tom-nøkkel
       }, 400);
     }
     ```
   - **Kort-merke:** i `.card-img-wrap` (ved favoritt-stjernen),
     `{#if notater[r.id]}<div class="card-badge-notat">📝</div>{/if}`.

## Dataflyt

```
OPPSTART: notater = await notaterLast()
SKRIV (detalj-textarea, id): oninput → {...notater,[id]:tekst} (umiddelbar)
  → debounce 400 ms → notatSett(id,tekst,notater) (tom ⇒ slett nøkkel)
KORT: {#if notater[r.id]} → 📝-merke
```

## Feilhåndtering

- Store best-effort (favoritt-mønster): feil logges, app fungerer videre.
- Tomt/whitespace-notat → fjernes fra lagring (intet kort-merke for tomt notat).
- Notat for ikke-eksisterende id → ligger ubrukt i Store, gjør ingen skade.

## Testing

Ingen ren logikk å enhetsteste (Store + UI). Verifiseres via `npm run build` +
manuell e2e: skriv notat → lukk/åpne → består; kort får 📝 etter notat; slett
all tekst → merke forsvinner; lukk app → består; notat på A blandes ikke med B.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Lagring | Tauri Store `notater.json` (`Record<id, tekst>`) |
| Plassering | Felt nederst i detaljvisningen |
| Lagre | Auto-lagre debounced (~400 ms) |
| Kort-merke | 📝 på kort med notat |
| Filter/visning | Ingen (YAGNI) |

## Avgrensninger (ikke i denne saken)

- Ingen sidebar-visning/filter for «oppskrifter med notater» (YAGNI; kan legges
  til senere som favoritt-modus hvis savnet).
- Ren tekst, ikke rik tekst.
