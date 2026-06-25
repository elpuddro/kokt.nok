# #24 Høytidsdekorasjoner — Design

**Mål:** Smakfull, tidsstyrt pynt på forsidebannerets i høytidsperiodene — én diskret SVG-dekorasjon per høytid, brukerstyrt av/på-toggle.

**Mantra:** Det er en kokebok. Pynten skal understreke stemningen, ikke dominere.

---

## Styring og datamodell

- `pynt: boolean` lagres i Tauri Store (`innstillinger.json`), standard `false`.
- Leses på `onMount` i `+page.svelte` parallelt med tema-valget.
- Pynten vises kun når `pynt === true` OG `aktivHoytid !== null`.
- Synligheten styres av Svelte (`{#if pynt && aktivHoytid}`) — ingen global CSS-klasse på `<html>`.

---

## Toggle i Innstillinger

- Plassering: samme linje som høytidstema-innstillingen i Innstillinger → Tema-fanen.
- Label: «Høytidspynt»
- Grået ut (`disabled`) og visuelt dempet når ingen høytid er aktiv (`aktivHoytid === null`).
- Skrives til `innstillinger.json` under nøkkelen `"pynt"` (boolean).

---

## Dekorasjoner per høytid

Én dekorasjon per høytid. Alt inline SVG i komponenten — ingen bildefiler, ingen eksterne avhengigheter.

| Høytid | Dekorasjon | Animasjon |
|---|---|---|
| `jul` | 3 snøfnugg (❄-form, SVG) langs høyre kant av banneret | `falle` — glir sakte nedover med ulik `animation-delay` |
| `paske` | 3 egg-ovaler langs bunnen av banneret, pastellfarger | Ingen — statiske |
| `mai17` | 3 konfetti-rektangler (rødt/hvitt/blått), lett rotert | Ingen — statiske |
| `sankthans` | 1 flamme-SVG ytterst til høyre i banneret | `pulsere` — subtil skala-pulsering |
| `farikaal` | Ingen pynt | — |
| `halloween` | 3 spindelvev-SVGer i øvre hjørner av banneret | Ingen — statiske |
| `valentins` | 2 hjerte-SVGer (outline), flyter opp fra bunnen | `flyte` — fade-in/out + translateY |

---

## Komponent: `src/lib/Hoytidspynt.svelte`

Ny komponent. Tar én prop: `hoytid: string`.

Rendrer riktig SVG-blokk via `{#if hoytid === "jul"}` … osv.

Alle CSS-animasjoner (`falle`, `pulsere`, `flyte`) defineres i komponentens `<style>`-blokk.

Komponenten posisjoneres `position: absolute` inni banneret, som har `position: relative`. Den legger seg oppå bannerinnholdet uten å påvirke layout.

Komponenten har `pointer-events: none` — klikk går gjennom til banneret under.

---

## Endringer i `+page.svelte`

1. Ny state: `let pynt = $state(false)`
2. `onMount`: les `pynt` fra `innstillinger.json` (`store.get("pynt") ?? false`)
3. Ny funksjon `onPyntChange()`: skriver `pynt` til `innstillinger.json`
4. I banneret: `{#if pynt && aktivHoytid}<Hoytidspynt hoytid={aktivHoytid} />{/if}`
5. I Innstillinger → Tema-fanen: ny toggle-rad «Høytidspynt» med `disabled={!aktivHoytid}`

---

## Constraints

- Inline SVG kun — ingen bildefiler, ingen web-fonter, ingen CDN. Appen distribueres portabelt (fengselsbygg, luftgap).
- Ingen emoji i SVG-elementene — OS-fontavhengig og upålitelig på locked-down Windows/Debian.
- Pynten skal ikke påvirke layout eller klikkmål.
- CSS-animasjoner holdes subtile: lav hastighet, lav opacity-kontrast.
- `fårikålens dag` har ingen pynt — bevisst valg.
