# Høytidsdekorasjoner — Implementasjonsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Smakfull, brukerstyrt SVG-pynt på forsidebannerets under aktive høytidsperioder.

**Architecture:** Ny `Hoytidspynt.svelte`-komponent rendrer inline SVG basert på `hoytid`-prop. Monteres i `+page.svelte` bak `{#if pynt && aktivHoytid}`. Toggle lagres i Tauri Store (`innstillinger.json`). Ingen backend-endringer.

**Tech Stack:** Svelte 5 runes, Tauri Store (`@tauri-apps/plugin-store`), inline SVG, CSS-animasjoner.

## Global Constraints

- Svelte 5 runes kun: `$state`, `$derived`. Aldri `$:`, aldri `writable()`.
- Inline SVG kun — ingen bildefiler, ingen web-fonter, ingen CDN (portabel fengselsbygg, luftgap).
- Ingen emoji i SVG-elementene — OS-fontavhengig, upålitelig på locked-down Windows/Debian.
- `pointer-events: none` på hele pynt-komponenten — ingen påvirkning på klikkmål.
- Pynten skal ikke påvirke layout (position: absolute, overflow: hidden på banner).
- CSS-animasjoner: subtile — lav hastighet (≥6s syklus), lav opacity-kontrast.
- `fårikaal` har ingen pynt — bevisst valg, skal ikke endres.
- Pynt-state lagres under nøkkelen `"pynt"` (boolean) i `innstillinger.json` via Tauri Store.
- Standard: `false` (av).
- Ingen nye npm-pakker eller Cargo-avhengigheter.

---

### Task 1: `Hoytidspynt.svelte` — komponent med alle SVG-dekorasjoner

**Files:**
- Create: `kokebok-app/src/lib/Hoytidspynt.svelte`

**Interfaces:**
- Consumes: prop `hoytid: string` (én av: `"jul"`, `"paske"`, `"mai17"`, `"sankthans"`, `"halloween"`, `"valentins"`)
- Produces: eksportert Svelte-komponent, importeres i Task 2 som `import Hoytidspynt from "$lib/Hoytidspynt.svelte"`

Det finnes ingen testramme for Svelte-komponenter i prosjektet. Manuell visuell verifisering er eneste testform — se teststeg.

- [ ] **Steg 1: Opprett filen med grunnstruktur**

```svelte
<script lang="ts">
  let { hoytid }: { hoytid: string } = $props();
</script>

<div class="pynt-lag" aria-hidden="true">
  {#if hoytid === "jul"}
    <!-- snøfnugg -->
  {:else if hoytid === "paske"}
    <!-- egg -->
  {:else if hoytid === "mai17"}
    <!-- konfetti -->
  {:else if hoytid === "sankthans"}
    <!-- flamme -->
  {:else if hoytid === "halloween"}
    <!-- spindelvev -->
  {:else if hoytid === "valentins"}
    <!-- hjerter -->
  {/if}
</div>

<style>
  .pynt-lag {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }
</style>
```

- [ ] **Steg 2: Implementer jul — 3 snøfnugg**

Erstatt `<!-- snøfnugg -->` med:

```svelte
<svg class="snofnugg s1" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.35">
  <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
  <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
  <line x1="10" y1="1" x2="7" y2="4"/><line x1="10" y1="1" x2="13" y2="4"/>
  <line x1="10" y1="19" x2="7" y2="16"/><line x1="10" y1="19" x2="13" y2="16"/>
</svg>
<svg class="snofnugg s2" viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.25">
  <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
  <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
</svg>
<svg class="snofnugg s3" viewBox="0 0 20 20" width="11" height="11" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.20">
  <line x1="10" y1="1" x2="10" y2="19"/><line x1="1" y1="10" x2="19" y2="10"/>
  <line x1="3.5" y1="3.5" x2="16.5" y2="16.5"/><line x1="16.5" y1="3.5" x2="3.5" y2="16.5"/>
</svg>
```

Legg til i `<style>`:

```css
  .snofnugg {
    position: absolute;
    right: 12px;
    animation: falle linear infinite;
    color: var(--accent-light, #aac8e8);
  }
  .s1 { top: -18px; animation-duration: 8s; animation-delay: 0s; }
  .s2 { top: -14px; right: 30px; animation-duration: 11s; animation-delay: 3s; }
  .s3 { top: -11px; right: 48px; animation-duration: 9s; animation-delay: 6s; }

  @keyframes falle {
    0%   { transform: translateY(0)   rotate(0deg); }
    100% { transform: translateY(80px) rotate(180deg); }
  }
```

- [ ] **Steg 3: Implementer paske — 3 statiske egg**

Erstatt `<!-- egg -->` med:

```svelte
<svg class="egg e1" viewBox="0 0 24 30" width="22" height="28">
  <ellipse cx="12" cy="16" rx="9" ry="12" fill="#f9d6a0" stroke="#e8b96a" stroke-width="1"/>
</svg>
<svg class="egg e2" viewBox="0 0 24 30" width="18" height="24">
  <ellipse cx="12" cy="16" rx="9" ry="12" fill="#b8dfc8" stroke="#7dbb99" stroke-width="1"/>
</svg>
<svg class="egg e3" viewBox="0 0 24 30" width="20" height="26">
  <ellipse cx="12" cy="16" rx="9" ry="12" fill="#d4b8e0" stroke="#a87cc4" stroke-width="1"/>
</svg>
```

Legg til i `<style>`:

```css
  .egg {
    position: absolute;
    bottom: 4px;
    opacity: 0.55;
  }
  .e1 { left: 12px; }
  .e2 { left: 44px; bottom: 6px; }
  .e3 { left: 74px; }
```

- [ ] **Steg 4: Implementer mai17 — 3 statiske konfetti-rektangler**

Erstatt `<!-- konfetti -->` med:

```svelte
<svg class="konfetti k1" viewBox="0 0 10 18" width="9" height="16">
  <rect width="10" height="18" rx="2" fill="#ef2d3b" transform="rotate(-18 5 9)"/>
</svg>
<svg class="konfetti k2" viewBox="0 0 10 18" width="9" height="16">
  <rect width="10" height="18" rx="2" fill="#ffffff" stroke="#ddd" stroke-width="0.5" transform="rotate(8 5 9)"/>
</svg>
<svg class="konfetti k3" viewBox="0 0 10 18" width="9" height="16">
  <rect width="10" height="18" rx="2" fill="#003087" transform="rotate(-6 5 9)"/>
</svg>
```

Legg til i `<style>`:

```css
  .konfetti {
    position: absolute;
    top: 6px;
    opacity: 0.55;
  }
  .k1 { right: 16px; }
  .k2 { right: 30px; top: 10px; }
  .k3 { right: 44px; top: 5px; }
```

- [ ] **Steg 5: Implementer sankthans — 1 pulserende flamme**

Erstatt `<!-- flamme -->` med:

```svelte
<svg class="flamme" viewBox="0 0 24 36" width="22" height="32" fill="none">
  <path d="M12 34 C6 28, 2 22, 6 14 C8 10, 10 8, 12 2 C14 8, 18 12, 17 18 C16 22, 14 26, 12 34Z"
        fill="#ff8c00" opacity="0.7"/>
  <path d="M12 30 C9 25, 7 20, 10 15 C11 12, 12 10, 12 6 C13 10, 16 14, 15 19 C14 23, 13 26, 12 30Z"
        fill="#ffcc00" opacity="0.8"/>
</svg>
```

Legg til i `<style>`:

```css
  .flamme {
    position: absolute;
    right: 14px;
    bottom: 2px;
    animation: pulsere ease-in-out infinite;
    animation-duration: 2.4s;
    transform-origin: bottom center;
  }

  @keyframes pulsere {
    0%, 100% { transform: scaleY(1)   scaleX(1); }
    50%       { transform: scaleY(1.06) scaleX(0.96); }
  }
```

- [ ] **Steg 6: Implementer halloween — 3 spindelvev**

Erstatt `<!-- spindelvev -->` med:

```svelte
<svg class="spindelvev sv1" viewBox="0 0 40 40" width="36" height="36" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.30">
  <line x1="20" y1="0" x2="20" y2="40"/>
  <line x1="0" y1="20" x2="40" y2="20"/>
  <line x1="0" y1="0" x2="40" y2="40"/>
  <line x1="40" y1="0" x2="0" y2="40"/>
  <circle cx="20" cy="20" r="6" fill="none"/>
  <circle cx="20" cy="20" r="13" fill="none"/>
</svg>
<svg class="spindelvev sv2" viewBox="0 0 30 30" width="26" height="26" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.20">
  <line x1="15" y1="0" x2="15" y2="30"/>
  <line x1="0" y1="15" x2="30" y2="15"/>
  <line x1="0" y1="0" x2="30" y2="30"/>
  <line x1="30" y1="0" x2="0" y2="30"/>
  <circle cx="15" cy="15" r="5" fill="none"/>
  <circle cx="15" cy="15" r="10" fill="none"/>
</svg>
<svg class="spindelvev sv3" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.18">
  <line x1="12" y1="0" x2="12" y2="24"/>
  <line x1="0" y1="12" x2="24" y2="12"/>
  <line x1="0" y1="0" x2="24" y2="24"/>
  <line x1="24" y1="0" x2="0" y2="24"/>
  <circle cx="12" cy="12" r="4" fill="none"/>
</svg>
```

Legg til i `<style>`:

```css
  .spindelvev {
    position: absolute;
    top: 0;
    color: var(--text-muted, #b09cc0);
  }
  .sv1 { left: 0; }
  .sv2 { left: 28px; top: 2px; }
  .sv3 { right: 0; }
```

- [ ] **Steg 7: Implementer valentins — 2 hjerter som flyter opp**

Erstatt `<!-- hjerter -->` med:

```svelte
<svg class="hjerte h1" viewBox="0 0 24 22" width="20" height="18" fill="none" stroke="currentColor" stroke-width="1.4" opacity="0.45">
  <path d="M12 20 C12 20, 2 13, 2 7 A5 5 0 0 1 12 5 A5 5 0 0 1 22 7 C22 13, 12 20, 12 20Z"/>
</svg>
<svg class="hjerte h2" viewBox="0 0 24 22" width="14" height="13" fill="none" stroke="currentColor" stroke-width="1.4" opacity="0.30">
  <path d="M12 20 C12 20, 2 13, 2 7 A5 5 0 0 1 12 5 A5 5 0 0 1 22 7 C22 13, 12 20, 12 20Z"/>
</svg>
```

Legg til i `<style>`:

```css
  .hjerte {
    position: absolute;
    bottom: 4px;
    color: var(--accent, #c2185b);
    animation: flyte ease-in-out infinite;
  }
  .h1 { right: 18px; animation-duration: 6s; animation-delay: 0s; }
  .h2 { right: 44px; animation-duration: 8s; animation-delay: 2s; }

  @keyframes flyte {
    0%   { transform: translateY(0);    opacity: 0.45; }
    50%  { transform: translateY(-18px); opacity: 0.20; }
    100% { transform: translateY(0);    opacity: 0.45; }
  }
```

- [ ] **Steg 8: Verifiser visuelt**

Start dev-serveren:
```
cd kokebok-app
npm run tauri dev
```

For å teste uten å vente på riktig dato: åpne `+page.svelte` i en editor, sett midlertidig `aktivHoytid = "jul"` og `pynt = true` øverst i `onMount`, lagre. Sjekk at snøfnuggene vises i banneret. Gjenta for de øvrige høytidene (`"paske"`, `"mai17"`, `"sankthans"`, `"halloween"`, `"valentins"`). Sjekk at `"farikaal"` ikke viser noe. Fjern de midlertidige verdiene etterpå.

- [ ] **Steg 9: Commit**

```bash
git add kokebok-app/src/lib/Hoytidspynt.svelte
git commit -m "feat: Hoytidspynt-komponent med inline SVG for 6 høytider"
```

---

### Task 2: Pynt-state, toggle og montering i `+page.svelte`

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `Hoytidspynt` fra `$lib/Hoytidspynt.svelte` (Task 1). `aktivHoytid: string | null` (eksisterende state, linje 97). `innstFane` (eksisterende state, linje 72). `load` fra `@tauri-apps/plugin-store` (allerede importert).
- Produces: ingenting nytt eksporteres

- [ ] **Steg 1: Legg til import øverst i `<script>`**

Finn importblokken øverst (linje 2–19). Legg til etter siste import:

```ts
  import Hoytidspynt from "$lib/Hoytidspynt.svelte";
```

- [ ] **Steg 2: Legg til `pynt`-state**

Like under linjen `let aktivHoytid = $state<string | null>(null);` (linje 97), legg til:

```ts
  let pynt = $state(false);
```

- [ ] **Steg 3: Les `pynt` fra Store i `onMount`**

Finn blokken i `onMount` der `planSesong` leses fra `plan.json` (linje ~401 og ~856). Store-operasjoner for `innstillinger.json` finnes ikke ennå — legg til etter `aktivHoytid = await invoke<string | null>("hoytid_aktiv");` (linje 870):

```ts
    const innstStore = await load("innstillinger.json");
    pynt = (await innstStore.get<boolean>("pynt")) ?? false;
```

- [ ] **Steg 4: Legg til `onPyntChange`-funksjon**

Finn funksjonen `onPlanSesongChange` (søk etter den i filen). Legg til rett etter den:

```ts
  async function onPyntChange() {
    const store = await load("innstillinger.json");
    await store.set("pynt", pynt);
    await store.save();
  }
```

- [ ] **Steg 5: Monter `Hoytidspynt` i forsidebannerets**

Finn dette i malen (linje ~1380):

```svelte
        <div class="forside-header">
          <h2 class="forside-tittel">{forsideTittel}</h2>
          {#if !aktivHoytid}
            <p class="forside-undertekst">Forslag til deg akkurat nå</p>
          {/if}
        </div>
```

Gjør `forside-header` til `position: relative` ved å endre til:

```svelte
        <div class="forside-header" style="position:relative;">
          <h2 class="forside-tittel">{forsideTittel}</h2>
          {#if !aktivHoytid}
            <p class="forside-undertekst">Forslag til deg akkurat nå</p>
          {/if}
          {#if pynt && aktivHoytid}
            <Hoytidspynt hoytid={aktivHoytid} />
          {/if}
        </div>
```

- [ ] **Steg 6: Legg til pynt-toggle i Innstillinger → Tema-fanen**

Finn slutten av tema-seksjonen i Innstillinger (linje ~1124–1125):

```svelte
        {/each}
      </details>
      {/if}
      {#if innstFane === "diett"}
```

Legg til toggle-rad mellom `{/each}` og `</details>`:

```svelte
        <label class="tema-valg pynt-toggle {!aktivHoytid ? 'deaktivert' : ''}">
          <input
            type="checkbox"
            checked={pynt}
            disabled={!aktivHoytid}
            onchange={() => { pynt = !pynt; onPyntChange(); }}
          />
          <span>Høytidspynt {aktivHoytid ? '' : '(ingen aktiv høytid)'}</span>
        </label>
```

- [ ] **Steg 7: Legg til CSS for `pynt-toggle`**

Finn `.plan-toggle.deaktivert` i `<style>`-blokken (linje ~2716). Legg til rett etter:

```css
  .pynt-toggle { margin-top: 10px; border-top: 1px solid var(--border-light); padding-top: 10px; }
  .pynt-toggle.deaktivert { opacity: 0.4; cursor: not-allowed; }
```

- [ ] **Steg 8: Verifiser e2e**

Start dev-serveren (`npm run tauri dev`). Sett midlertidig `aktivHoytid = "valentins"` i `onMount` for test.

Sjekk:
1. Innstillinger → Tema viser «Høytidspynt»-toggle (grå tekst «ingen aktiv høytid» i normal drift)
2. Med `aktivHoytid = "valentins"`: toggle er klikkbar
3. Slå på → hjerter vises i forsidebannerets
4. Slå av → hjerter forsvinner
5. Last om appen (Ctrl+R) → pynt-valget persisteres korrekt (fra `innstillinger.json`)
6. Fjern midlertidig testverdi

- [ ] **Steg 9: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat: pynt-toggle i Innstillinger og Hoytidspynt montert i forside-banner"
```
