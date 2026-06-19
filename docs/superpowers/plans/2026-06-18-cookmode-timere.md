# Cook Mode + timere — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La brukeren (1) holde skjermen/maskinen våken mens en oppskrift er åpen (Cook Mode, Win+Linux), og (2) starte nedtellings-timere ved å klikke på tids-uttrykk i trinn-teksten, med flere samtidige timere og lyd/visuelt varsel.

**Architecture:** To uavhengige komponenter. Cook Mode = en kryssplattform `cook_mode(on)` Tauri-kommando (Windows `SetThreadExecutionState` via rå FFI; Linux D-Bus screensaver-inhibit via `zbus` med cookie i app-state) + én bryter i detaljvisningen. Timere = ren, node-testbar parser `tid-parsing.ts` (`finnTider`) + nedtelling/alarm/UI i `+page.svelte` (Web Audio-pip, globalt flytende panel). Ingen DB- eller Store-skriving.

**Tech Stack:** Rust (Tauri 2, `zbus` for Linux, `windows-sys`/rå FFI for Windows), Svelte 5 (runes), TypeScript (node-testbar via `--experimental-strip-types`), Web Audio API.

**Spec:** `docs/superpowers/specs/2026-06-18-cookmode-timere-design.md`

> **Merknad til implementøren om FFI/D-Bus:** `zbus` 4.x og `windows-sys` 0.59
> sine eksakte API-er (proxy-konstruksjon, `call_method`, body-deserialisering;
> Win32-modulsti/feature-navn) er versjons-sensitive. Hvis cargo gir en
> kompileringsfeil PÅ NETTOPP disse kallene, juster kallet til den installerte
> versjonens API (sjekk `cargo doc -p zbus` / `windows-sys`) — selve strategien
> (Inhibit/UnInhibit med cookie; SetThreadExecutionState med ES-flagg) er riktig.
> På Windows kompileres ikke zbus-grenen (cfg-gated), så Linux-grenen verifiseres
> først ved et Linux-bygg (WSL).

---

## Anker-fakta (verifisert mot kode)

- `generate_handler![get_kategorier, hent_oppskrifter, hent_oppskrift, hent_oppskrifter_by_ids]` — lib.rs linje 567-572. Ny kommando registreres her.
- `use tauri::{AppHandle, Manager};` finnes alt (lib.rs linje 9) — `Manager` trengs for `app.manage(...)`/`app.state()`.
- `tauri::Builder`-kjeden ender ~linje 567; `.manage(...)` legges på builderen for Linux-cookie-state.
- `Cargo.toml [dependencies]` (linje 20-26): `tauri`, `tauri-plugin-opener`, `tauri-plugin-store`. Nye deps legges her.
- `+page.svelte`: `import { onMount } from "svelte";` (linje 3) → utvides med `onDestroy`. `invoke` importeres allerede (brukt i fetchGrid). `lukkDetalj()` linje 305-308. `onMount` linje 362. Detalj-blokk `{@const opp = currentOppskrift}` linje 641; `.detail-topbar` 648-664 (knapper: `.btn-back`, `.detail-fav`, `.detail-handle`). Trinn-rendring linje 705-710 (`{#each opp.trinn as t, idx}` → `.step-tekst`). Detalj-blokk lukkes ~linje 712-734 (samme `{#if currentOppskrift}` som starter 640).
- `tid-parsing`-mønsteret speiler `src/lib/tema-logikk.ts` + `tema.test.mjs` (node-testbar, ingen Tauri-import).

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src-tauri/Cargo.toml` | Nye deps (`zbus` Linux, `windows-sys` Windows) | Modify |
| `kokebok-app/src-tauri/src/lib.rs` | `cook_mode(on)` kommando + registrering + Linux cookie-state | Modify |
| `kokebok-app/src/lib/tid-parsing.ts` | `finnTider(tekst)` — ren parse-logikk | Create |
| `kokebok-app/src/lib/tid-parsing.test.mjs` | node-enhetstester for parseren | Create |
| `kokebok-app/src/routes/+page.svelte` | Cook Mode-bryter, klikkbar tid, timer-panel, alarm, stil | Modify |

**Rekkefølge:** parser+test (T1) → Cook Mode Rust (T2) → Cook Mode UI (T3) → timer-state+nedtelling+alarm (T4) → klikkbar tid + panel (T5) → manuell e2e (T6).

---

## Task 1: Tids-parser `tid-parsing.ts` (ren logikk, TDD)

Node-testbar, ingen Tauri-import (som `tema-logikk.ts`). Regexen er den feilutsatte
biten — testes grundig.

**Files:**
- Create: `kokebok-app/src/lib/tid-parsing.ts`
- Create: `kokebok-app/src/lib/tid-parsing.test.mjs`

- [ ] **Step 1: Skriv testene**

Create `kokebok-app/src/lib/tid-parsing.test.mjs`:
```js
import { finnTider } from "./tid-parsing.ts";
import assert from "node:assert";

let bestått = 0;
function sjekk(navn, fn) {
  try { fn(); bestått++; console.log("  ok  " + navn); }
  catch (e) { console.error("FAIL " + navn + ": " + e.message); process.exitCode = 1; }
}

// Enkelt tall + enhet → sekunder
sjekk("40 minutter = 2400s", () => {
  const t = finnTider("stek i ca. 40 minutter");
  assert.equal(t.length, 1);
  assert.equal(t[0].sekunder, 2400);
});
sjekk("5 min = 300s", () => assert.equal(finnTider("kok 5 min")[0].sekunder, 300));
sjekk("1 minutt = 60s", () => assert.equal(finnTider("vent 1 minutt")[0].sekunder, 60));
sjekk("30 sekunder = 30s", () => assert.equal(finnTider("rør i 30 sekunder")[0].sekunder, 30));
sjekk("2 timer = 7200s", () => assert.equal(finnTider("la heve i 2 timer")[0].sekunder, 7200));
sjekk("1 t = 3600s", () => assert.equal(finnTider("stek 1 t")[0].sekunder, 3600));

// Intervall → øvre grense av DET intervallet
sjekk("20-30 minutter = 1800s (øvre)", () =>
  assert.equal(finnTider("stek i 20-30 minutter")[0].sekunder, 1800));
sjekk("1-2 timer = 7200s (øvre)", () =>
  assert.equal(finnTider("hev i 1-2 timer")[0].sekunder, 7200));
sjekk("5-6 timer = 21600s (øvre, ikke tak)", () =>
  assert.equal(finnTider("la stå i 5-6 timer")[0].sekunder, 21600));
sjekk("em-dash 45–50 minutter = 3000s", () =>
  assert.equal(finnTider("stek 45–50 minutter")[0].sekunder, 3000));

// Brøk
sjekk("1½ t = 5400s", () => assert.equal(finnTider("stek 1½ t")[0].sekunder, 5400));
sjekk("½ time = 1800s", () => assert.equal(finnTider("vent ½ time")[0].sekunder, 1800));
sjekk("1¼ time = 4500s", () => assert.equal(finnTider("kok 1¼ time")[0].sekunder, 4500));

// Flere i ett trinn → alle
sjekk("flere tider", () => {
  const t = finnTider("stek 20 min, deretter hvil 5 min");
  assert.equal(t.length, 2);
  assert.equal(t[0].sekunder, 1200);
  assert.equal(t[1].sekunder, 300);
});

// Posisjon (for klikkbar markering)
sjekk("start/slutt-posisjon", () => {
  const t = finnTider("kok i 5 min nå");
  assert.equal("kok i 5 min nå".slice(t[0].start, t[0].slutt), t[0].tekst);
});

// Robusthet
sjekk("ingen tid → tom", () => assert.equal(finnTider("rør godt sammen").length, 0));
sjekk("løst tall uten enhet ignoreres", () =>
  assert.equal(finnTider("del i 4 biter").length, 0));
sjekk("urimelig stor verdi forkastes (100 timer)", () =>
  assert.equal(finnTider("la stå i 100 timer").length, 0));
sjekk("tom streng → tom", () => assert.equal(finnTider("").length, 0));

console.log(`\n${bestått} tester ok`);
```

- [ ] **Step 2: Kjør testene og bekreft at de feiler**

Run: `cd "<repo>/kokebok-app/src/lib" && node --experimental-strip-types tid-parsing.test.mjs`
Expected: FAIL — `finnTider` finnes ikke (import-feil / not a function).

- [ ] **Step 3: Implementer `tid-parsing.ts`**

Create `kokebok-app/src/lib/tid-parsing.ts`:
```ts
// Ren, node-testbar logikk (ingen Tauri-import, som tema-logikk.ts). Finner
// tids-uttrykk i trinn-tekst og regner ut nedtellingslengde i sekunder.

export type TidTreff = {
  tekst: string;    // selve tall+enhet, f.eks. "20-30 minutter"
  start: number;    // indeks i kildeteksten (for klikkbar markering)
  slutt: number;
  sekunder: number;
};

const BRØK: Record<string, number> = { "¼": 0.25, "½": 0.5, "¾": 0.75 };

const MAKS_SEK = 24 * 3600; // forkast urimelige verdier (sannsynlig feilparsing)

// Et tall: heltall, evt. etterfulgt av unicode-brøk («1½»), ELLER bare brøk («½»),
// evt. intervall «a-b»/«a–b» (bindestrek eller em-dash). Tar ØVRE grense.
// Gruppe 1=første tall(heltall), 2=første brøk, 3=andre tall, 4=andre brøk.
const TALL = String.raw`(\d+)?([¼½¾])?(?:\s*[-–]\s*(\d+)?([¼½¾])?)?`;
const RE = new RegExp(TALL + String.raw`\s*(sekunder|sekund|sek|minutter|minutt|min|timer|time|t)\b`, "giu");

function tilTall(heltall?: string, brøk?: string): number | null {
  let v = 0;
  let har = false;
  if (heltall) { v += parseInt(heltall, 10); har = true; }
  if (brøk) { v += BRØK[brøk] ?? 0; har = true; }
  return har ? v : null;
}

function enhetMultiplikator(enhet: string): number {
  const e = enhet.toLowerCase();
  if (e.startsWith("sek")) return 1;
  if (e.startsWith("min")) return 60;
  return 3600; // time/timer/t
}

export function finnTider(tekst: string): TidTreff[] {
  if (!tekst) return [];
  const treff: TidTreff[] = [];
  for (const m of tekst.matchAll(RE)) {
    const [hel, brøk, hel2, brøk2, enhet] = [m[1], m[2], m[3], m[4], m[5]];
    const a = tilTall(hel, brøk);
    if (a === null) continue;            // ingen tallverdi → ikke et treff
    const b = tilTall(hel2, brøk2);
    const verdi = b !== null ? Math.max(a, b) : a;  // intervall → øvre grense
    const sekunder = Math.round(verdi * enhetMultiplikator(enhet));
    if (sekunder <= 0 || sekunder > MAKS_SEK) continue;
    treff.push({
      tekst: m[0].trim(),
      start: m.index,
      slutt: m.index + m[0].length,
      sekunder,
    });
  }
  return treff;
}
```

Hovedlogikken er `RE` (tall/intervall/brøk + enhet) + `enhetMultiplikator`.

- [ ] **Step 4: Kjør testene og bekreft at de passerer**

Run: `cd "<repo>/kokebok-app/src/lib" && node --experimental-strip-types tid-parsing.test.mjs`
Expected: alle tester «ok», siste linje «N tester ok», exit 0. Hvis en feiler
(typisk intervall- eller brøk-regex), juster `RE`/`tilTall` til alle passerer —
IKKE svekk en test.

- [ ] **Step 5: Bygg (typesjekk i app-konteksten)**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (modulen importeres i T5; den kompilerer alene).

- [ ] **Step 6: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/lib/tid-parsing.ts kokebok-app/src/lib/tid-parsing.test.mjs
git commit -m "feat(timere): tids-parser (finnTider) + node-tester"
```

---

## Task 2: Cook Mode Rust-kommando

**Files:**
- Modify: `kokebok-app/src-tauri/Cargo.toml` (deps)
- Modify: `kokebok-app/src-tauri/src/lib.rs` (kommando + registrering + state)

- [ ] **Step 1: Legg til avhengigheter**

I `kokebok-app/src-tauri/Cargo.toml`, etter `tauri-plugin-store`-linja (~linje 26),
legg til plattform-spesifikke deps som EGNE seksjoner (ikke i `[dependencies]`):
```toml

[target.'cfg(target_os = "linux")'.dependencies]
zbus = "4"

[target.'cfg(windows)'.dependencies]
windows-sys = { version = "0.59", features = ["Win32_System_Power", "Win32_Foundation"] }
```

- [ ] **Step 2: Implementer `cook_mode`-kommandoen**

I `lib.rs`, legg til (f.eks. rett før `// ─── Kommando: kategorier`-blokken ~linje 87):
```rust
// ─── Cook Mode: hold skjermen/maskinen våken (kryssplattform, best-effort) ──────
// Linux trenger å huske en «inhibit cookie» mellom på/av-kall.
#[derive(Default)]
struct CookModeState {
    #[allow(dead_code)]
    cookie: std::sync::Mutex<Option<u32>>,
}

#[cfg(windows)]
fn sett_keep_awake(on: bool) {
    use windows_sys::Win32::System::Power::{
        SetThreadExecutionState, ES_CONTINUOUS, ES_DISPLAY_REQUIRED, ES_SYSTEM_REQUIRED,
    };
    unsafe {
        if on {
            SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED);
        } else {
            SetThreadExecutionState(ES_CONTINUOUS);
        }
    }
}

#[cfg(target_os = "linux")]
fn sett_keep_awake_linux(on: bool, state: &CookModeState) {
    // freedesktop ScreenSaver Inhibit/UnInhibit over D-Bus (sesjonsbuss).
    let mut cookie = state.cookie.lock().unwrap();
    let conn = match zbus::blocking::Connection::session() {
        Ok(c) => c,
        Err(e) => { eprintln!("cook_mode: ingen sesjonsbuss: {e}"); return; }
    };
    let proxy = zbus::blocking::Proxy::new(
        &conn,
        "org.freedesktop.ScreenSaver",
        "/org/freedesktop/ScreenSaver",
        "org.freedesktop.ScreenSaver",
    );
    let proxy = match proxy { Ok(p) => p, Err(e) => { eprintln!("cook_mode: proxy-feil: {e}"); return; } };
    if on {
        // Slå av en evt. gammel inhibit først (idempotent).
        if let Some(c) = cookie.take() {
            let _ = proxy.call_method("UnInhibit", &(c));
        }
        match proxy.call_method("Inhibit", &("kokt.nok", "Matlaging")) {
            Ok(reply) => { if let Ok(c) = reply.body().deserialize::<u32>() { *cookie = Some(c); } }
            Err(e) => eprintln!("cook_mode: Inhibit feilet: {e}"),
        }
    } else if let Some(c) = cookie.take() {
        let _ = proxy.call_method("UnInhibit", &(c));
    }
}

#[tauri::command]
fn cook_mode(
    #[allow(unused_variables)] app: AppHandle,
    on: bool,
) -> Result<(), String> {
    #[cfg(windows)]
    {
        sett_keep_awake(on);
    }
    #[cfg(target_os = "linux")]
    {
        let state = app.state::<CookModeState>();
        sett_keep_awake_linux(on, &state);
    }
    // Andre OS: no-op.
    Ok(())
}
```

- [ ] **Step 3: Registrer kommando + state**

I `lib.rs`, utvid `generate_handler!`-lista (linje 567-572) til å inkludere `cook_mode`:
```rust
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift,
            hent_oppskrifter_by_ids,
            cook_mode
        ])
```
Og legg `CookModeState` på builderen. `pub fn run()` (lib.rs linje 545-548) starter:
```rust
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
```
Legg `.manage(...)` inn rett etter `tauri::Builder::default()`:
```rust
    tauri::Builder::default()
        .manage(CookModeState::default())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
```

- [ ] **Step 4: Bygg**

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo build --features tauri/custom-protocol`
Expected: `Finished` uten feil. (På Windows kompileres kun `#[cfg(windows)]`-grenen;
zbus-grenen sjekkes ikke av kompilatoren på Windows, men `cargo build` på Linux
ville kompilert den. Det er forventet.)

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src-tauri/Cargo.toml kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(cookmode): kryssplattform cook_mode keep-awake-kommando"
```

---

## Task 3: Cook Mode-bryter i UI

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

- [ ] **Step 1: Importer onDestroy**

Endre linje 3 fra:
```ts
  import { onMount } from "svelte";
```
til:
```ts
  import { onMount, onDestroy } from "svelte";
```

- [ ] **Step 2: Legg til state**

Etter de andre `$state`-deklarasjonene (f.eks. etter `let aktiveDietter = $state<string[]>([]);`),
legg til:
```ts
  let cookModeAktiv = $state(false);
```

- [ ] **Step 3: Handler + sikkerhetsnett**

Ved de andre funksjonene (f.eks. etter `lukkDetalj`), legg til:
```ts
  async function toggleCookMode() {
    cookModeAktiv = !cookModeAktiv;
    try {
      await invoke("cook_mode", { on: cookModeAktiv });
    } catch (e) {
      console.error("cook_mode feilet:", e);
    }
  }
  async function slåAvCookMode() {
    if (!cookModeAktiv) return;
    cookModeAktiv = false;
    try { await invoke("cook_mode", { on: false }); } catch (e) { console.error(e); }
  }
```

Endre `lukkDetalj` (linje 305-308) til å slå av Cook Mode:
```ts
  function lukkDetalj() {
    slåAvCookMode();
    currentOppskrift = null;
    portioner = null;
  }
```

Etter `onMount(...)`-blokken (etter linje ~370 der onMount slutter), legg til:
```ts
  onDestroy(() => { slåAvCookMode(); });
```

- [ ] **Step 4: Bryter-knapp i detalj-topbar**

I `.detail-topbar` (linje 648-664), rett ETTER `.detail-handle`-knappen (slutter
linje 661, før `<span class="detail-type-pill">`), legg til:
```svelte
        <button
          class="detail-cook"
          class:aktiv={cookModeAktiv}
          title={cookModeAktiv ? "Skjermen holdes våken" : "Hold skjermen våken under matlaging"}
          onclick={toggleCookMode}
        >{cookModeAktiv ? "👩‍🍳 Holder våken" : "👩‍🍳 Hold skjermen våken"}</button>
```

- [ ] **Step 5: Stil**

I `<style>`, etter `.detail-handle`-reglene (søk etter `.detail-handle`), legg til
(samme mønster som de andre topbar-knappene):
```css
  .detail-cook {
    border: 1px solid var(--border); background: var(--surface); color: var(--text);
    border-radius: var(--radius); padding: 8px 14px; cursor: pointer; font-size: 0.9rem;
  }
  .detail-cook:hover { border-color: var(--border-focus); }
  .detail-cook.aktiv { background: var(--accent); color: #fff; border-color: var(--accent); }
```

- [ ] **Step 6: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (pre-eksisterende a11y-advarsel på recipe-card er OK).

- [ ] **Step 7: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(cookmode): bryter i detaljvisning + auto-av ved lukk/avslutning"
```

---

## Task 4: Timer-state, nedtelling og alarm

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

- [ ] **Step 1: Importer parser**

Etter de andre `$lib`-importene (f.eks. etter `import { diettLast, ... } from "$lib/diett";`),
legg til:
```ts
  import { finnTider } from "$lib/tid-parsing";
```

- [ ] **Step 2: Timer-state + lydkontekst**

Etter `let cookModeAktiv = $state(false);`, legg til:
```ts
  type Timer = { id: number; navn: string; igjen: number; total: number; ferdig: boolean; pauset: boolean };
  let timere = $state<Timer[]>([]);
  let nesteTimerId = 1;
  let timerTikk: any = null;
  let lydCtx: AudioContext | null = null;
```

- [ ] **Step 3: Start/stopp/nedtelling-funksjoner**

Ved de andre funksjonene, legg til:
```ts
  function startTimer(sekunder: number, navn: string) {
    // Opprett/«resume» AudioContext på dette klikket (bruker-gest) så pip ikke
    // blokkeres senere når nedtellingen er ferdig.
    if (!lydCtx) {
      try { lydCtx = new AudioContext(); } catch { lydCtx = null; }
    }
    if (lydCtx && lydCtx.state === "suspended") lydCtx.resume();

    timere = [...timere, {
      id: nesteTimerId++, navn, igjen: sekunder, total: sekunder,
      ferdig: false, pauset: false,
    }];
    startTikkHvisNødvendig();
  }

  function startTikkHvisNødvendig() {
    if (timerTikk) return;
    timerTikk = setInterval(() => {
      let endret = false;
      const oppdatert = timere.map((t) => {
        if (t.pauset || t.ferdig) return t;
        const igjen = t.igjen - 1;
        endret = true;
        if (igjen <= 0) {
          spillAlarm();
          return { ...t, igjen: 0, ferdig: true };
        }
        return { ...t, igjen };
      });
      if (endret) timere = oppdatert;
    }, 1000);
  }

  function pauseTimer(id: number) {
    timere = timere.map((t) => (t.id === id ? { ...t, pauset: !t.pauset } : t));
  }

  function fjernTimer(id: number) {
    timere = timere.filter((t) => t.id !== id);
    if (timere.length === 0 && timerTikk) { clearInterval(timerTikk); timerTikk = null; }
  }

  function spillAlarm() {
    if (!lydCtx) return;
    try {
      // Tre korte pip.
      const nå = lydCtx.currentTime;
      for (let i = 0; i < 3; i++) {
        const osc = lydCtx.createOscillator();
        const gain = lydCtx.createGain();
        osc.frequency.value = 880;
        osc.connect(gain); gain.connect(lydCtx.destination);
        const t0 = nå + i * 0.3;
        gain.gain.setValueAtTime(0.0001, t0);
        gain.gain.exponentialRampToValueAtTime(0.3, t0 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.22);
        osc.start(t0); osc.stop(t0 + 0.25);
      }
    } catch (e) { console.error("alarm feilet:", e); }
  }

  function fmtTid(sek: number): string {
    const m = Math.floor(sek / 60);
    const s = sek % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }
```

Utvid `onDestroy` (lagt til i Task 3) til også å rydde timer-intervallet:
```ts
  onDestroy(() => {
    slåAvCookMode();
    if (timerTikk) clearInterval(timerTikk);
  });
```

- [ ] **Step 4: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (funksjonene brukes i Task 5; de kompilerer alene).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(timere): state, nedtelling, Web Audio-alarm"
```

---

## Task 5: Klikkbar tid i trinn + globalt timer-panel

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

- [ ] **Step 1: Hjelpefunksjon for trinn-segmenter**

Ved de andre funksjonene, legg til en funksjon som deler en trinntekst i segmenter
(ren tekst + klikkbare tider):
```ts
  // Del trinntekst i [{ klikk: false, tekst }, { klikk: true, tekst, sekunder }, ...]
  function trinnSegmenter(tekst: string) {
    const tider = finnTider(tekst);
    if (tider.length === 0) return [{ klikk: false, tekst, sekunder: 0 }];
    const seg: { klikk: boolean; tekst: string; sekunder: number }[] = [];
    let pos = 0;
    for (const t of tider) {
      if (t.start > pos) seg.push({ klikk: false, tekst: tekst.slice(pos, t.start), sekunder: 0 });
      seg.push({ klikk: true, tekst: t.tekst, sekunder: t.sekunder });
      pos = t.slutt;
    }
    if (pos < tekst.length) seg.push({ klikk: false, tekst: tekst.slice(pos), sekunder: 0 });
    return seg;
  }
```

- [ ] **Step 2: Render klikkbar tid i trinn**

Erstatt trinn-tekst-linja (linje 708):
```svelte
                <div class="step-tekst">{t.tekst}</div>
```
med en segment-rendring:
```svelte
                <div class="step-tekst">
                  {#each trinnSegmenter(t.tekst) as s}
                    {#if s.klikk}
                      <button
                        class="tid-knapp"
                        title="Start timer ({fmtTid(s.sekunder)})"
                        onclick={() => startTimer(s.sekunder, `${opp.navn} – trinn ${t.nummer ?? idx + 1}`)}
                      >⏱ {s.tekst}</button>
                    {:else}{s.tekst}{/if}
                  {/each}
                </div>
```

- [ ] **Step 3: Globalt flytende timer-panel**

Finn slutten av detalj-blokken `{#if currentOppskrift}…{/if}` (starter linje 640,
`{/if}` ~linje 734) OG slutten av `{#if loading}`-blokken etter den. Legg panelet
ETTER `{#if loading}…{/if}` men FØR `<style>` (så det er globalt, ikke inni detalj):
```svelte
{#if timere.length > 0}
  <div id="timer-panel">
    {#each timere as t (t.id)}
      <div class="timer-rad" class:ferdig={t.ferdig}>
        <span class="timer-navn">{t.ferdig ? "🔔" : "⏱"} {t.navn}</span>
        <span class="timer-tid">{t.ferdig ? "ferdig!" : fmtTid(t.igjen)}</span>
        {#if !t.ferdig}
          <button class="timer-btn" title={t.pauset ? "Fortsett" : "Pause"} onclick={() => pauseTimer(t.id)}>
            {t.pauset ? "▶" : "⏸"}
          </button>
        {/if}
        <button class="timer-btn" title="Fjern" onclick={() => fjernTimer(t.id)}>✕</button>
      </div>
    {/each}
  </div>
{/if}
```

- [ ] **Step 4: Stil**

I `<style>`, etter `.detail-cook`-reglene, legg til:
```css
  .tid-knapp {
    display: inline; border: none; background: var(--accent-bg);
    color: var(--accent-dark); font: inherit; cursor: pointer;
    border-radius: 4px; padding: 0 4px; white-space: nowrap;
  }
  .tid-knapp:hover { background: var(--accent); color: #fff; }

  #timer-panel {
    position: fixed; right: 18px; bottom: 18px; z-index: 100;
    display: flex; flex-direction: column; gap: 8px; max-width: 320px;
  }
  .timer-rad {
    display: flex; align-items: center; gap: 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 8px 12px; box-shadow: var(--shadow);
  }
  .timer-navn { flex: 1; font-size: 0.85rem; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .timer-tid { font-variant-numeric: tabular-nums; font-weight: 700; color: var(--accent-dark); }
  .timer-btn {
    border: none; background: none; cursor: pointer; font-size: 0.95rem;
    color: var(--text-muted); padding: 0 2px;
  }
  .timer-btn:hover { color: var(--text); }
  .timer-rad.ferdig {
    border-color: var(--accent); background: var(--accent-bg);
    animation: timer-blink 1s steps(2, start) infinite;
  }
  .timer-rad.ferdig .timer-tid { color: var(--accent); }
  @keyframes timer-blink { 50% { opacity: 0.55; } }
```

- [ ] **Step 5: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 6: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(timere): klikkbar tid i trinn + globalt timer-panel"
```

---

## Task 6: Manuell ende-til-ende-verifikasjon

Krever kjørende app. MANUELT (menneske).

**Files:** ingen.

- [ ] **Step 1: Kjør appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`

- [ ] **Step 2: Cook Mode-sjekkliste**

- Åpne en oppskrift → «👩‍🍳 Hold skjermen våken»-knapp i topplinja.
- Trykk → knappen blir aktiv («Holder våken»). La maskinen stå (Windows: skjermen
  skal ikke slukke / gå i dvale mens aktiv).
- Trykk igjen → av. Lukk oppskriften med Cook Mode på → den slås av automatisk.

- [ ] **Step 3: Timer-sjekkliste**

- Åpne en oppskrift med tid i et trinn (f.eks. «stek i 20-30 minutter») → tiden er
  klikkbar (⏱-markert).
- Klikk → en timer starter i panelet nede til høyre, teller ned fra øvre grense
  (30:00).
- Start flere timere (også fra ulike trinn) → alle vises samtidig.
- Pause/fortsett og ✕ virker per rad.
- La en kort timer (lag en på «30 sekunder») gå til 0 → pip (3 korte) + raden
  blinker «🔔 … ferdig!». ✕ kvitterer.
- Lukk oppskriften → timer-panelet vises fortsatt og fortsetter å telle (globalt).
- Intervall-sjekk: «5-6 timer» → timer starter på 6:00:00 (øvre grense, ikke tak).

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** parser m/intervall-øvre-grense+brøk+posisjon+robusthet (T1),
  cook_mode Win(FFI)+Linux(zbus+cookie-state)+no-op-fallback (T2), bryter +
  auto-av ved lukk/onDestroy (T3), timer-state+nedtelling+Web Audio-pip-på-gest
  (T4), klikkbar tid + globalt panel + pause/fjern/blink (T5), manuell e2e (T6).
  Alle spec-beslutninger dekket (én bryter, flere timere, øvre grense, ingen
  persistering, Web Audio uten lydfil).
- **Navn/typer konsistente:** `finnTider`/`TidTreff{tekst,start,slutt,sekunder}`
  (T1) brukt i `trinnSegmenter` (T5). `Timer{id,navn,igjen,total,ferdig,pauset}`
  (T4) brukt i panel (T5). `cook_mode`-kommando (T2) ↔ `invoke("cook_mode",{on})`
  (T3). `cookModeAktiv`/`slåAvCookMode`/`startTimer`/`fmtTid`/`spillAlarm`
  konsistent T3→T4→T5.
- **Kritiske detaljer:** AudioContext opprettes på klikk-gest (T4 startTimer), ikke
  ved nedtellings-slutt (autoplay-blokk unngått). `onDestroy` rydder BÅDE Cook Mode
  og timer-intervall. Panel ligger UTENFOR detalj-blokk (globalt). Linux-cookie i
  Mutex i app-managed state.
- **Verifisert mot kode:** generate_handler (567-572), Manager-import (l.9),
  onMount-import (l.3), lukkDetalj (305-308), detail-topbar (648-664), trinn (705-710).
- **`<repo>`** = repo-roten (`c:/Users/elpud/CODE/kokt.nok` lokalt); bruk faktisk sti.
