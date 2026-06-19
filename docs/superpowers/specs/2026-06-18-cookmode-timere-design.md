# Cook Mode + timere — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-18.
> Backlog-idéer #11 (Cook Mode — hold skjermen våken) + #12 (innebygde timere).
> Samlet i én spec: uavhengige på kode-nivå, men deler detaljvisningen som
> plassering og er begge små kjøkken-under-matlaging-funksjoner.

## Mål

- **Cook Mode (#11):** hindre at skjermen/maskinen sovner mens man lager mat, så
  man slipper å ta på PC-en med skitne fingre. Manuell bryter i en åpen oppskrift.
- **Timere (#12):** gjør tids-uttrykk i trinn-teksten («stek i 20-30 minutter»)
  klikkbare for å starte en nedtelling, med flere samtidige timere og varsel.

## Arkitektur

To uavhengige komponenter (deler kun detaljvisningen som plassering):
- **Cook Mode:** kryssplattform keep-awake i en Rust-kommando + én bryter i UI.
- **Timere:** ren tids-parser (node-testbar TS) + nedtelling/alarm/UI i frontend.

Ingen DB-skriving, ingen Store-persistering (timere lever per app-økt — YAGNI).

### Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src-tauri/src/lib.rs` | `cook_mode(on)` kommando (Win+Linux keep-awake) | Modify |
| `kokebok-app/src-tauri/Cargo.toml` | Linux: `zbus`; Windows: rå FFI eller `windows-sys` | Modify |
| `kokebok-app/src/lib/tid-parsing.ts` | `finnTider(tekst)` — ren parse-logikk | Create |
| `kokebok-app/src/lib/tid-parsing.test.mjs` | node-enhetstester for parseren | Create |
| `kokebok-app/src/routes/+page.svelte` | Cook Mode-bryter, klikkbar tid, timer-panel, alarm, stil | Modify |

Mønstre gjenbrukt: `tema-logikk.ts`/`tema.test.mjs` (node-testbar ren logikk),
`$state`-runer, `setInterval`-nedtelling, `invoke(...)` for Rust-kommando.

## Komponent A: Cook Mode (keep-awake)

### Rust-kommando

`cook_mode(on: bool) -> Result<(), String>` i `lib.rs`, registrert i
`tauri::generate_handler![...]`. Best-effort: feiler aldri hardt.

**Windows** (`#[cfg(windows)]`): `SetThreadExecutionState`.
- på: `ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED`
- av: `ES_CONTINUOUS`
- Tilstandsløst (bare flagg). Implementeres via rå `extern "system"`-deklarasjon
  av `SetThreadExecutionState` (unngår ny crate) ELLER `windows-sys` hvis renere.
  Foretrukket: rå FFI → null nye avhengigheter, skrubbe-trygt.

**Linux** (`#[cfg(target_os = "linux")]`): freedesktop D-Bus screensaver-inhibit
via `zbus`.
- på: `org.freedesktop.ScreenSaver.Inhibit("kokt.nok", "Matlaging")` → returnerer
  en `u32` cookie.
- av: `org.freedesktop.ScreenSaver.UnInhibit(cookie)`.
- Cookien MÅ holdes mellom på/av-kall: en `Mutex<Option<u32>>` i Tauri
  `app.manage(...)`-state (eller en `static`). på når allerede på → UnInhibit
  gammel først (idempotent). D-Bus utilgjengelig → logg, no-op.

**Andre OS / feil:** `Ok(())` uten effekt (no-op). Aldri hard feil.

### Frontend

- State: `let cookModeAktiv = $state(false);`
- Bryter i detaljvisningen («👩‍🍳 Hold skjermen våken»), av som standard.
  Klikk → `cookModeAktiv = !cookModeAktiv; await invoke("cook_mode", { on: cookModeAktiv });`
- **Sikkerhetsnett (maskinen må aldri bli stående våken):**
  - `lukkDetalj()` slår alltid av: `if (cookModeAktiv) { invoke("cook_mode",{on:false}); cookModeAktiv = false; }`
  - `onDestroy` (app-avslutning med oppskrift åpen) slår av.

## Komponent B: Timere

### Ren parser (`tid-parsing.ts`)

```ts
export type TidTreff = {
  tekst: string;   // selve tall+enhet, f.eks. "20-30 minutter"
  start: number;   // indeks i kildeteksten (for klikkbar markering)
  slutt: number;
  sekunder: number;
};
export function finnTider(tekst: string): TidTreff[];
```

Regler (utledet fra ~2035 ekte trinn-tekster):
- Enheter → multiplikator: `sekund(er)/sek` ×1, `minutt(er)/min` ×60,
  `time(r)/t` ×3600.
- Enkelt tall: «40 minutter» → 2400.
- Intervall (bindestrek `-` ELLER em-dash `–`): bruk **øvre grense av DET
  trinnet sitt eget intervall** (ikke et tak): «20-30 minutter» → 1800,
  «1-2 timer» → 7200, «5-6 timer» → 21600. (Øvre grense = tryggest, ikke
  understek.)
- Unicode-brøk (¼=.25, ½=.5, ¾=.75), evt. med heltall foran: «1½ t» → 5400,
  «½ time» → 1800.
- «ca.»/«omtrent» foran påvirker ikke tallet; markert tekst er selve tall+enhet.
- Flere tider i ett trinn → alle returneres (hver blir egen klikkbar timer).
- Robusthet: ingen treff → `[]` (aldri kast). Verdi > 24 t (86400 s) forkastes
  (sannsynlig feilparsing).
- Bare tall MED enhet teller (et løst «5» uten enhet ignoreres).

### Timer-tilstand + nedtelling (`+page.svelte`)

```ts
type Timer = { id: number; navn: string; igjen: number; total: number;
               ferdig: boolean; pauset: boolean };
let timere = $state<Timer[]>([]);
let timerTikk: any;        // ett felles setInterval (1000 ms)
let nesteTimerId = 1;
```

- `startTimer(sekunder, navn)`: legg ny `Timer` i `timere`; opprett `timerTikk`
  hvis ikke aktivt.
- Hvert tikk: for hver ikke-pauset, ikke-ferdig timer `igjen--`; ved `igjen <= 0`
  → `ferdig = true` + utløs alarm.
- Når `timere.length === 0`: `clearInterval(timerTikk)` (spar ressurser).
- `navn` utledes av kontekst: oppskriftsnavn + «trinn N» (så man vet hva som ringer).

### Klikkbar tid i trinn

I trinn-rendringen (`{#each opp.trinn as t, idx}`, ~linje 705): kjør
`finnTider(t.tekst)` og render teksten som segmenter — delene mellom treff som
ren tekst, hvert treff som en `<button class="tid-knapp">` som kaller
`startTimer(treff.sekunder, "<oppskrift> – trinn <n>")`. (Bygg en liten
`@const`-segmentliste per trinn, eller en hjelpефunksjon `segmenter(tekst)`.)

### Flytende timer-panel (globalt)

- Plassert UTENFOR `{#if currentOppskrift}` (fast posisjon, nede til høyre), så
  timere fortsetter å vises/ringe selv når oppskriften lukkes og man blar videre.
- Synlig når `timere.length > 0`. Hver rad: `navn`, `MM:SS`, pause/fortsett-knapp,
  ✕ (fjern). Ferdig timer: utheves/blinker med «🔔 {navn} ferdig!» til ✕.

### Alarm

- **Lyd:** Web Audio API (`AudioContext` + `OscillatorNode`), kort pip, gjentas
  noen ganger eller til kvittering. Ingen lydfil → ingenting å pakke/skrubbe.
  `AudioContext` feiler → kun visuelt varsel (timeren feiler ikke).
  NB: nettlesere krever en bruker-gest for å starte/«resume» en `AudioContext`.
  Siden timeren startes med et klikk (en gest), opprett/«resume» konteksten DA
  (i `startTimer`), ikke ved selve nedtellings-slutt — ellers kan pipet blokkeres.
- **Visuelt:** raden blinker + «🔔». (Cook Mode holder skjermen våken hvis på.)

## Dataflyt

```
COOK MODE:  bryter → invoke(cook_mode,{on}) → Win: SetThreadExecutionState /
            Linux: D-Bus Inhibit(+cookie).  lukkDetalj/onDestroy → off.
TIMER:      trinn-tekst → finnTider() → klikkbar knapp → startTimer(sek,navn)
            → setInterval 1s → igjen-- → igjen<=0 → ferdig + pip + blink → ✕
```

## Feilhåndtering

- `cook_mode`: best-effort på alle plattformer; feil logges, aldri hard feil.
  Linux-cookie i `Mutex<Option<u32>>`; dobbel på/av idempotent.
- Cook Mode slås av ved lukk av detalj OG app-avslutning (maskinen blir aldri
  stående våken).
- Web Audio utilgjengelig → kun visuelt varsel.
- Parser kaster aldri; ugyldig/ingen tid → `[]`. Urimelige verdier forkastes.

## Testing

- **Kjerne — parser:** `tid-parsing.test.mjs` (node, som `tema.test.mjs`):
  «40 minutter»→2400, «20-30 minutter»→1800, «1-2 timer»→7200, «1½ t»→5400,
  «½ time»→1800, «5 min»→300, «30 sekunder»→30, «ca. 45-50 minutter»→3000,
  flere-i-ett «stek 20 min, hvil 5 min»→[1200,300], tekst uten tid→[],
  urimelig «100 timer»→forkastet.
- **Rust:** `cargo build` (kompilerer `#[cfg(windows)]` + `#[cfg(linux)]`-grener).
- **Frontend/e2e (manuell):** klikkbar tid starter timer, nedtelling, pip+blink
  ved 0, flere samtidige, panel globalt synlig, pause/fjern, Cook Mode-bryter
  holder skjermen våken og slås av ved lukk.

## Distribusjon

- Nye Rust-avhengigheter (Linux `zbus`, evt. `windows-sys`) må skrubbe-sjekkes
  med `bygg_portable.py --verifiser` før fengsels-distribusjon (som all kode).
- Ingen lydfiler/bilder (Web Audio er ren kode). Ingen DB-endring → `kokt.db` og
  `kokt-bundle.db` uberørt av denne funksjonen.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Spec-struktur | Én samlet spec (to uavhengige komponenter) |
| Keep-awake | Egen Rust-kommando, Windows + Linux (ingen community-plugin) |
| Cook Mode-aktivering | Manuell bryter i detaljvisning, auto-av ved lukk |
| Timer-start | Klikkbar tid i trinn-tekst (intervall → øvre grense) |
| Antall timere | Flere samtidig |
| Varsel | Web Audio-pip + visuell blink (in-app) |
| Persistering | Ingen (per økt) |
| Parser | Ren TS-modul, node-testbar (`tema-logikk.ts`-mønster) |

## Avgrensninger (ikke i denne saken — YAGNI)

- Ingen persistering av timere mellom økter.
- Ingen OS-notifikasjoner (kun in-app pip + blink).
- Ingen Cook Mode på macOS (kun Windows + Linux nå).
- Ingen manuell «egen timer»-knapp (kun klikkbar tid fra trinn).
- Ingen automatisk Cook Mode (alltid manuell bryter).
