<script lang="ts">
  import { invoke, convertFileSrc } from "@tauri-apps/api/core";
  import { onMount, onDestroy } from "svelte";
  import { favorittLast, favorittToggle } from "$lib/favoritter";
  import {
    handlelisteLast, handlelisteLeggTil, handlelisteFjern,
    handlelisteSettPorsjoner, handlelisteTøm, type HandlelistePost,
  } from "$lib/handleliste";
  import { temaLast, temaSett, aktivtTema, gjeldendeTema, TEMAER, type TemaId, type Lagret } from "$lib/tema";
  import { notaterLast, notatSett } from "$lib/notater";
  import { diettLast, diettSett, DIETT_FILTRE } from "$lib/diett";
  import { lagerLast, lagerLeggTil, lagerFjern, lagerTøm, type LagerVare } from "$lib/lager";
  import { utlopsStatus } from "$lib/lager-logikk";
  import { finnTider } from "$lib/tid-parsing";

  // ── Kategori-emojier ─────────────────────────────────────────────────────────
  const EMOJI: Record<string, string> = {
    "alle": "🍽️", "Annet": "🍽️", "Biffer": "🥩", "Brød/bakverk": "🍞",
    "Dessert": "🍰", "Drikke": "🥤", "Forretter": "🥗", "Frokost": "🍳",
    "Grillet kylling": "🍗", "Grillspyd": "🔥", "Gryter": "🍲",
    "Hele fileter": "🐟", "Kaker": "🎂", "Kjøttdeig- og farseretter": "🫕",
    "Koldtbord": "🧆", "Koteletter": "🥩", "Kyllingfilet": "🍗",
    "Ovnsretter": "🫙", "Panneretter": "🍳", "Pasta": "🍝", "Pizza": "🍕",
    "Pålegg": "🧈", "Salater": "🥙", "Sandwich/smørbrød": "🥪", "Steker": "🥩",
    "Supper": "🍜", "Tapas/småretter": "🫔", "Tilbehør": "🫙", "Turmat": "⛺",
    "Vafler/pannekaker": "🧇", "Vegan": "🌱", "Vegetar": "🥦", "Wok": "🥡",
  };
  const emoji = (t: string | null | undefined) => EMOJI[t ?? ""] ?? "🍽️";

  // ── State (Svelte 5 runes) ─────────────────────────────────────────────────
  let kategorier = $state<any[]>([]);
  let currentKategori = $state("alle");
  let sok = $state("");
  let side = $state(1);
  let perSide = $state(24);
  let total = $state(0);
  let oppskrifter = $state<any[]>([]);
  let currentOppskrift = $state<any>(null);
  let portioner = $state<number | null>(null);
  let loading = $state(false);
  let favoritter = $state<Set<number>>(new Set());
  let handleliste = $state<HandlelistePost[]>([]);
  let temaValg = $state<Lagret>({ modus: "auto", tema: null });
  let aktivtTemaId = $state<TemaId>("varm");
  let notater = $state<Record<number, string>>({});
  let notatTimer: any;
  let aktiveDietter = $state<string[]>([]);
  let lager = $state<LagerVare[]>([]);
  let lagerForslag = $state<any[]>([]);
  let lagerForslagTimer: any = null;
  let nyVareNavn = $state("");
  let nyVareUtloper = $state("");
  let autoForslag = $state<string[]>([]);
  let autoTimer: any = null;
  let cookModeAktiv = $state(false);
  type Timer = { id: number; navn: string; igjen: number; total: number; ferdig: boolean; pauset: boolean };
  let timere = $state<Timer[]>([]);
  let nesteTimerId = 1;
  let timerTikk: any = null;
  let lydCtx: AudioContext | null = null;

  let pages = $derived(Math.ceil(total / perSide));
  let totalAlle = $derived(kategorier.reduce((s, k) => s + k.antall, 0));
  let pageNums = $derived(
    [...new Set([1, pages, side, side - 1, side + 1].filter((p) => p >= 1 && p <= pages))].sort((a, b) => a - b)
  );

  // Bilder serveres fra databasen via kbilde-protokollen (se lib.rs).
  // convertFileSrc lager den plattform-riktige URL-en (http://kbilde.localhost/… på Windows).
  function imgSrc(id: number | null | undefined): string | null {
    if (id == null) return null;
    return convertFileSrc(String(id), "kbilde");
  }

  // ── Tallformatering for skalerte ingredienser ───────────────────────────────
  const FRACS: [number, string][] = [
    [1 / 8, "⅛"], [1 / 4, "¼"], [1 / 3, "⅓"], [1 / 2, "½"], [2 / 3, "⅔"], [3 / 4, "¾"],
  ];
  function fmtMengde(v: number | null | undefined): string {
    if (v == null || v <= 0) return "";
    const whole = Math.floor(v);
    const frac = v - whole;
    let fracStr = "";
    for (const [f, s] of FRACS) {
      if (Math.abs(frac - f) < 0.08) { fracStr = s; break; }
    }
    if (v < 1 && fracStr) return fracStr;
    if (v < 1) return v.toFixed(2).replace(/\.?0+$/, "");
    if (v < 10) {
      if (fracStr) return `${whole || ""}${fracStr}`;
      return (Math.round(v * 4) / 4).toFixed(2).replace(/\.?0+$/, "");
    }
    if (v < 100) return String(Math.round(v));
    return String(Math.round(v / 5) * 5);
  }
  const scaleMengde = (m: number | null, fromP: number, toP: number) =>
    m == null ? m : (m / fromP) * toP;

  // ── Datahenting med request-id guard (porter fetchGrid-fiksen) ──────────────
  let fetchSeq = 0;
  async function fetchGrid() {
    const seq = ++fetchSeq;
    loading = true;
    try {
      if (currentKategori === "__fav__") {
        const liste: any[] = await invoke("hent_oppskrifter_by_ids", {
          ids: [...favoritter],
        });
        if (seq !== fetchSeq) return;
        oppskrifter = liste;
        total = liste.length;
        side = 1;
      } else {
        const data: any = await invoke("hent_oppskrifter", {
          kategori: currentKategori, sok, side, perSide, dietter: aktiveDietter,
        });
        if (seq !== fetchSeq) return;
        total = data.total;
        oppskrifter = data.oppskrifter;
        side = data.side;
      }
    } catch (err) {
      if (seq !== fetchSeq) return;
      console.error("fetchGrid failed:", err);
      oppskrifter = [];
      total = 0;
    } finally {
      if (seq === fetchSeq) loading = false;
    }
  }

  // ── Søk (debounced) – nullstiller kategori til «alle» (porter søkefiksen) ────
  let searchTimer: any;
  function onSearchInput(e: Event) {
    const val = (e.target as HTMLInputElement).value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      sok = val;
      side = 1;
      if (val && currentKategori !== "alle") currentKategori = "alle";
      fetchGrid();
    }, 280);
  }

  function onNotatInput(id: number, e: Event) {
    const tekst = (e.target as HTMLTextAreaElement).value;
    notater = { ...notater, [id]: tekst };   // umiddelbar reaktiv oppdatering
    clearTimeout(notatTimer);
    notatTimer = setTimeout(async () => {
      notater = await notatSett(id, tekst, notater);
    }, 400);
  }

  async function toggleDiett(id: string) {
    const ny = aktiveDietter.includes(id)
      ? aktiveDietter.filter((d) => d !== id)
      : [...aktiveDietter, id];
    aktiveDietter = await diettSett(ny);
    side = 1;
    // Oppdater både rutenettet og sidebar-tellingene (begge påvirkes av filteret).
    kategorier = await invoke("get_kategorier", { dietter: aktiveDietter });
    await fetchGrid();
  }

  function velgKategori(k: string) {
    currentKategori = k;
    side = 1;
    sok = "";
    fetchGrid();
  }

  function velgFavoritter() {
    currentKategori = "__fav__";
    side = 1;
    sok = "";
    fetchGrid();
  }

  function velgHandleliste() {
    currentKategori = "__handle__";
    side = 1;
    sok = "";
    oppskrifter = [];
    lastHandleAgg();
  }

  function velgInnstillinger() {
    currentKategori = "__innst__";
    side = 1;
    sok = "";
    oppskrifter = [];
  }

  function velgKjøleskap() {
    currentKategori = "__lager__";
    side = 1;
    sok = "";
    oppskrifter = [];
    oppdaterLagerForslag();
  }

  async function fjernVare(navn: string) {
    lager = await lagerFjern(navn, lager);
    oppdaterLagerForslag();
  }
  async function tømLager() {
    lager = await lagerTøm();
    lagerForslag = [];
  }
  function oppdaterLagerForslag() {
    clearTimeout(lagerForslagTimer);
    lagerForslagTimer = setTimeout(async () => {
      if (lager.length === 0) { lagerForslag = []; return; }
      try {
        lagerForslag = await invoke("hva_kan_jeg_lage", { varer: lager.map((v) => v.navn) });
      } catch (e) { console.error("hva_kan_jeg_lage feilet:", e); lagerForslag = []; }
    }, 300);
  }

  function applyTema(id: TemaId) {
    aktivtTemaId = id;
    const el = document.documentElement;
    if (id === "varm") el.removeAttribute("data-tema");
    else el.setAttribute("data-tema", id);
  }

  async function velgTemaAuto() {
    temaValg = await temaSett("auto", null);
    applyTema(aktivtTema(temaValg, new Date()));
  }

  async function velgTemaManuell(id: TemaId) {
    temaValg = await temaSett("manuell", id);
    applyTema(id);
  }

  // Aggregert handleliste-visning. Lastes når modus åpnes eller lista endres.
  type SamletIngrediens = { navn: string; enhet: string | null; mengde: number | null; raatekst: string };
  let handleAgg = $state<{
    ingredienser: SamletIngrediens[];
    totalsum: number;
    oppskrifter: { id: number; navn: string; porsjoner: number; origP: number }[];
  }>({ ingredienser: [], totalsum: 0, oppskrifter: [] });
  let handleLaster = $state(false);

  function slåSammen(
    poster: { opp: any; porsjoner: number }[],
  ): SamletIngrediens[] {
    const kart = new Map<string, SamletIngrediens>();
    for (const { opp, porsjoner } of poster) {
      const origP = opp.porsjoner || 4;
      for (const i of opp.ingredienser ?? []) {
        const navn = (i.navn ?? i.raatekst ?? "").trim();
        if (!navn) continue;
        const enhet = i.enhet ?? null;
        const nokkel = navn.toLowerCase() + "|" + (enhet ?? "");
        const skalert = i.mengde == null ? null : scaleMengde(i.mengde, origP, porsjoner);
        const eks = kart.get(nokkel);
        if (eks) {
          if (skalert != null) eks.mengde = (eks.mengde ?? 0) + skalert;
        } else {
          kart.set(nokkel, { navn, enhet, mengde: skalert, raatekst: i.raatekst ?? navn });
        }
      }
    }
    return [...kart.values()].sort((a, b) => a.navn.localeCompare(b.navn, "nb"));
  }

  async function lastHandleAgg() {
    handleLaster = true;
    try {
      const poster: { opp: any; porsjoner: number }[] = [];
      for (const p of handleliste) {
        try {
          const opp: any = await invoke("hent_oppskrift", { id: p.id });
          if (opp) poster.push({ opp, porsjoner: p.porsjoner });
        } catch (err) {
          console.error("hent_oppskrift i handleliste feilet:", p.id, err);
        }
      }
      let sum = 0;
      for (const { opp, porsjoner } of poster) {
        const origP = opp.porsjoner || 4;
        const pr = opp.pris;
        if (pr && pr.totalt > 0) sum += pr.totalt * (porsjoner / origP);
      }
      handleAgg = {
        ingredienser: slåSammen(poster),
        totalsum: Math.round(sum),
        oppskrifter: poster.map(({ opp, porsjoner }) => ({
          id: opp.id, navn: opp.navn, porsjoner, origP: opp.porsjoner || 4,
        })),
      };
    } finally {
      handleLaster = false;
    }
  }

  async function handleEndrePorsjoner(id: number, origP: number, delta: number) {
    const post = handleliste.find((p) => p.id === id);
    if (!post) return;
    const ny = Math.max(1, Math.min(post.porsjoner + delta, 100));
    handleliste = await handlelisteSettPorsjoner(id, ny, handleliste);
    await lastHandleAgg();
  }
  async function handleFjern(id: number) {
    handleliste = await handlelisteFjern(id, handleliste);
    await lastHandleAgg();
  }
  async function handleTøm() {
    handleliste = await handlelisteTøm();
    await lastHandleAgg();
  }

  async function toggleFavoritt(id: number, e?: Event) {
    e?.stopPropagation();   // ikke åpne detalj når stjerne klikkes på kortet
    favoritter = await favorittToggle(id, favoritter);
    // I favoritt-visningen er lista et øyeblikksbilde fra fetchGrid; hent på nytt
    // så en av-stjernet oppskrift faktisk forsvinner fra lista.
    if (currentKategori === "__fav__") fetchGrid();
  }

  async function leggIHandleliste(id: number, porsjoner: number) {
    handleliste = await handlelisteLeggTil(id, porsjoner, handleliste);
  }

  function gåTilSide(p: number) {
    if (p < 1 || p > pages) return;
    side = p;
    fetchGrid();
  }

  // ── Detalj ──────────────────────────────────────────────────────────────────
  async function åpneOppskrift(id: number) {
    loading = true;
    try {
      const opp: any = await invoke("hent_oppskrift", { id });
      if (!opp) return;
      currentOppskrift = opp;
      portioner = opp.porsjoner ?? 4;
    } catch (err) {
      console.error("hent_oppskrift failed:", err);
    } finally {
      loading = false;
    }
  }
  function lukkDetalj() {
    slåAvCookMode();
    currentOppskrift = null;
    portioner = null;
  }

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

  function startTimer(sekunder: number, navn: string) {
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
  function endrePorsjoner(delta: number) {
    const cur = portioner ?? currentOppskrift?.porsjoner ?? 4;
    portioner = Math.max(1, Math.min(cur + delta, 100));
  }

  // ── Avledet detalj-data ─────────────────────────────────────────────────────
  let origP = $derived(currentOppskrift?.porsjoner || 4);
  let curP = $derived(portioner ?? origP);

  let grupper = $derived.by(() => {
    if (!currentOppskrift) return [] as [string, any[]][];
    const g: Record<string, any[]> = {};
    for (const i of currentOppskrift.ingredienser) {
      const key = i.gruppe || "Ingredienser";
      (g[key] ??= []).push(i);
    }
    return Object.entries(g);
  });
  let multiGroup = $derived(grupper.length > 1);

  let naeringPerPorsjon = $derived.by(() => {
    const n = currentOppskrift?.naering;
    if (!n || !(n.energi > 0)) return null;
    return {
      e: Math.round(n.energi / curP),
      p: Math.round((n.protein / curP) * 10) / 10,
      f: Math.round((n.fett / curP) * 10) / 10,
      k: Math.round((n.karbohydrat / curP) * 10) / 10,
      fi: n.fiber ? Math.round((n.fiber / curP) * 10) / 10 : null,
      treff: n.treff, totalt: n.totalt,
    };
  });

  // Pris: backend gir total for GRUNN-porsjoner. Total skalerer med curP/origP;
  // per-porsjon er stabil (total / origP), som nærings-per-porsjon.
  let prisVist = $derived.by(() => {
    const pr = currentOppskrift?.pris;
    if (!pr || !(pr.totalt > 0)) return null;
    const skala = curP / origP;
    return {
      total: Math.round(pr.totalt * skala),
      perPorsjon: Math.round(pr.totalt / origP),
      priset: pr.priset,
      antall: pr.totalt_antall,
    };
  });

  // ── Tastatur: Esc lukker detalj ─────────────────────────────────────────────
  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && currentOppskrift) lukkDetalj();
  }

  // ── Boot ────────────────────────────────────────────────────────────────────
  onMount(async () => {
    favoritter = await favorittLast();
    handleliste = await handlelisteLast();
    temaValg = await temaLast();
    applyTema(aktivtTema(temaValg, new Date()));
    notater = await notaterLast();
    aktiveDietter = await diettLast();
    lager = await lagerLast();
    kategorier = await invoke("get_kategorier", { dietter: aktiveDietter });
    await fetchGrid();
  });

  onDestroy(() => {
    slåAvCookMode();
    if (timerTikk) clearInterval(timerTikk);
  });
</script>

<svelte:window on:keydown={onKeydown} />

<aside id="sidebar">
  <div class="sidebar-logo">
    <span class="logo-icon">🍳</span>
    <span class="logo-text">Kokebok</span>
  </div>

  {#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__"}
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input
        id="sok-input"
        type="search"
        placeholder="Søk oppskrifter…"
        autocomplete="off"
        value={sok}
        oninput={onSearchInput}
      />
    </div>
  {/if}

  <nav id="kategori-liste">
    <button
      class="kat-btn alle"
      class:active={currentKategori === "alle"}
      onclick={() => velgKategori("alle")}
    >
      <span class="kat-emoji">{EMOJI["alle"]}</span>
      <span class="kat-navn">Alle oppskrifter</span>
      <span class="kat-teller">{totalAlle.toLocaleString("nb-NO")}</span>
    </button>
    <button
      class="kat-btn"
      class:active={currentKategori === "__fav__"}
      onclick={velgFavoritter}
    >
      <span class="kat-emoji">⭐</span>
      <span class="kat-navn">Favoritter</span>
      <span class="kat-teller">{favoritter.size}</span>
    </button>
    <button
      class="kat-btn"
      class:active={currentKategori === "__handle__"}
      onclick={velgHandleliste}
    >
      <span class="kat-emoji">🛒</span>
      <span class="kat-navn">Handleliste</span>
      <span class="kat-teller">{handleliste.length}</span>
    </button>
    <button
      class="kat-btn"
      class:active={currentKategori === "__lager__"}
      onclick={velgKjøleskap}
    >
      <span class="kat-emoji">🧊</span>
      <span class="kat-navn">Kjøleskap</span>
      <span class="kat-teller">{lager.length}</span>
    </button>
    <button
      class="kat-btn"
      class:active={currentKategori === "__innst__"}
      onclick={velgInnstillinger}
    >
      <span class="kat-emoji">⚙️</span>
      <span class="kat-navn">Innstillinger</span>
    </button>
    <div class="kat-divider"></div>

    {#each kategorier as k}
      <button
        class="kat-btn"
        class:active={currentKategori === k.kategori}
        onclick={() => velgKategori(k.kategori)}
      >
        <span class="kat-emoji">{emoji(k.kategori)}</span>
        <span class="kat-navn">{k.kategori}</span>
        <span class="kat-teller">{k.antall}</span>
      </button>
    {/each}
  </nav>
</aside>

<main id="main">
  <div id="main-header">
    <h1 id="header-tittel">
      {#if currentKategori === "__innst__"}
        ⚙️ Innstillinger
      {:else if currentKategori === "__handle__"}
        🛒 Handleliste
      {:else if currentKategori === "__lager__"}
        🧊 Kjøleskap
      {:else if currentKategori === "__fav__"}
        ⭐ Favoritter
      {:else if currentKategori === "alle"}
        {sok ? `Søkeresultater for «${sok}»` : "Alle oppskrifter"}
      {:else}
        {currentKategori}
      {/if}
    </h1>
    {#if currentKategori !== "__innst__" && currentKategori !== "__lager__"}
    <span id="header-antall" class="count-badge">
      {#if currentKategori === "__handle__"}
        {handleliste.length} oppskrifter
      {:else}
        {total.toLocaleString("nb-NO")} oppskrifter
      {/if}
    </span>
    {/if}
    {#if aktiveDietter.length > 0 && currentKategori !== "__innst__" && currentKategori !== "__lager__"}
      <button class="diett-pille" onclick={() => (currentKategori = "__innst__")}>
        🍽️ {aktiveDietter.length} {aktiveDietter.length === 1 ? "filter" : "filtre"} aktive
      </button>
    {/if}
  </div>

  {#if currentKategori === "__handle__"}
    <div id="handle-wrap">
      {#if handleliste.length === 0}
        <div class="empty-state">
          <div class="empty-icon">🛒</div>
          <h3>Handlelista er tom</h3>
          <p>Åpne en oppskrift og trykk «🛒 Legg i handleliste».</p>
        </div>
      {:else}
        <div class="handle-oppskrifter">
          <div class="handle-topp">
            <h2>Oppskrifter ({handleAgg.oppskrifter.length})</h2>
            <button class="handle-tom" onclick={handleTøm}>🗑 Tøm handleliste</button>
          </div>
          {#each handleAgg.oppskrifter as o (o.id)}
            <div class="handle-rad">
              <span class="handle-navn">{o.navn}</span>
              <span class="handle-porsjoner">
                <button class="portion-btn" disabled={o.porsjoner <= 1} onclick={() => handleEndrePorsjoner(o.id, o.origP, -1)}>−</button>
                <span>{o.porsjoner} porsjoner</span>
                <button class="portion-btn" onclick={() => handleEndrePorsjoner(o.id, o.origP, 1)}>+</button>
              </span>
              <button class="handle-fjern" title="Fjern" onclick={() => handleFjern(o.id)}>✕</button>
            </div>
          {/each}
        </div>

        <div class="handle-ingredienser">
          <h2>Innkjøpsliste</h2>
          {#if handleLaster}
            <p>Laster…</p>
          {:else}
            <ul>
              {#each handleAgg.ingredienser as i (i.navn + "|" + (i.enhet ?? ""))}
                <li>
                  <span class="handle-mengde">{fmtMengde(i.mengde)} {i.enhet ?? ""}</span>
                  <span class="handle-ingnavn">{i.navn}</span>
                </li>
              {/each}
            </ul>
            {#if handleAgg.totalsum > 0}
              <div class="handle-sum">💰 Estimert totalsum: ca. {handleAgg.totalsum} kr</div>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#if currentKategori === "__innst__"}
    <div id="innst-wrap">
      <details class="innst-seksjon">
        <summary><h2>🎨 Tema</h2></summary>
        <p class="innst-hint">
          Automatisk velger tema etter årstid og høytider. Nå:
          <strong>{TEMAER.find((t) => t.id === gjeldendeTema(new Date()))?.navn ?? "Varm"}</strong>.
        </p>
        <label class="tema-valg" class:valgt={temaValg.modus === "auto"}>
          <input type="radio" name="tema" checked={temaValg.modus === "auto"} onchange={velgTemaAuto} />
          <span>Automatisk (følg årstid / høytid)</span>
        </label>
        {#each TEMAER as t (t.id)}
          <label class="tema-valg" class:valgt={temaValg.modus === "manuell" && temaValg.tema === t.id}>
            <input
              type="radio" name="tema"
              checked={temaValg.modus === "manuell" && temaValg.tema === t.id}
              onchange={() => velgTemaManuell(t.id)}
            />
            <span>{t.navn}</span>
          </label>
        {/each}
      </details>
      <details class="innst-seksjon">
        <summary>
          <h2>🍽️ Kosthold og allergier <span class="beta-merke">BETA</span></h2>
          {#if aktiveDietter.length > 0}<span class="innst-teller">{aktiveDietter.length}</span>{/if}
        </summary>
        <p class="innst-hint">
          Beste-evne-filtrering basert på ingrediensnavn — ikke en garanti.
          For alvorlige allergier: les alltid den fulle ingredienslista selv.
        </p>
        {#each DIETT_FILTRE as f (f.id)}
          <label class="tema-valg" class:valgt={aktiveDietter.includes(f.id)}>
            <input
              type="checkbox"
              checked={aktiveDietter.includes(f.id)}
              onchange={() => toggleDiett(f.id)}
            />
            <span>{f.navn}</span>
          </label>
        {/each}
      </details>
    </div>
  {/if}

  {#if currentKategori === "__lager__"}
    <div id="lager-wrap">
      <section class="lager-rediger">
        <h2>Mitt kjøleskap</h2>
        <p class="innst-hint">Legg til varer du har, så foreslår vi oppskrifter under.</p>
        <!-- autocomplete-input fylles i T5 -->
        {#if lager.length === 0}
          <p class="lager-tom">Ingen varer registrert ennå.</p>
        {:else}
          <ul class="lager-liste">
            {#each lager as v (v.navn)}
              {@const st = utlopsStatus(v.utloper, new Date().toISOString().slice(0, 10))}
              <li class="lager-vare" class:utgaatt={st === "utgått"} class:snart={st === "snart"}>
                <span class="lager-navn">{v.navn}</span>
                {#if v.utloper}<span class="lager-utlop">
                  {st === "utgått" ? "⚠ utgått" : st === "snart" ? "⚠ går ut snart" : ""} {v.utloper}
                </span>{/if}
                <button class="lager-fjern" title="Fjern" onclick={() => fjernVare(v.navn)}>✕</button>
              </li>
            {/each}
          </ul>
          <button class="lager-tom-btn" onclick={tømLager}>🗑 Tøm kjøleskap</button>
        {/if}
      </section>
      <section class="lager-forslag">
        <h2>Hva kan jeg lage?</h2>
        <!-- forslagsliste fylles i T5 -->
      </section>
    </div>
  {/if}

  {#if currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__"}
  <div id="grid-wrap">
    <div id="recipe-grid">
      {#if oppskrifter.length === 0}
        <div class="empty-state">
          {#if currentKategori === "__fav__"}
            <div class="empty-icon">⭐</div>
            <h3>Ingen favoritter ennå</h3>
            <p>Trykk ⭐ på en oppskrift for å legge den til.</p>
          {:else}
            <div class="empty-icon">🔍</div>
            <h3>Ingen oppskrifter funnet</h3>
            <p>Prøv å søke på noe annet, eller velg en annen kategori.</p>
            {#if aktiveDietter.length > 0}
              <p class="empty-hint">Noen kan være skjult av aktive kostholdsfiltre.</p>
            {/if}
          {/if}
        </div>
      {:else}
        {#each oppskrifter as r (r.id)}
          <article class="recipe-card" title={r.navn} onclick={() => åpneOppskrift(r.id)}>
            <div class="card-img-wrap">
              {#if imgSrc(r.id)}
                <img src={imgSrc(r.id)} alt={r.navn} loading="lazy" />
              {:else}
                <div class="card-img-placeholder">{emoji(r.type)}</div>
              {/if}
              {#if r.tid}<div class="card-badge-time">⏱ {r.tid}</div>{/if}
              {#if notater[r.id]}<div class="card-badge-notat" title="Du har et notat">📝</div>{/if}
              <button
                class="card-fav"
                class:aktiv={favoritter.has(r.id)}
                title={favoritter.has(r.id) ? "Fjern favoritt" : "Legg til favoritt"}
                onclick={(e) => toggleFavoritt(r.id, e)}
              >{favoritter.has(r.id) ? "⭐" : "☆"}</button>
            </div>
            <div class="card-body">
              <div class="card-cat">{emoji(r.type)} {r.type ?? ""}</div>
              <div class="card-name">{r.navn}</div>
              <div class="card-meta">
                <span>👤 {r.porsjoner}</span>
                {#if r.tid}<span>⏱ {r.tid}</span>{/if}
              </div>
            </div>
          </article>
        {/each}
      {/if}
    </div>

    {#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__" && pages > 1}
      <div id="pagination">
        <button class="page-btn" disabled={side === 1} onclick={() => gåTilSide(side - 1)}>‹</button>
        {#each pageNums as p, idx (p)}
          {#if idx > 0 && p - pageNums[idx - 1] > 1}
            <span class="page-ellipsis">…</span>
          {/if}
          <button class="page-btn" class:active={p === side} onclick={() => gåTilSide(p)}>{p}</button>
        {/each}
        <button class="page-btn" disabled={side === pages} onclick={() => gåTilSide(side + 1)}>›</button>
      </div>
    {/if}
  </div>
  {/if}
</main>

<!-- ── Detalj-overlay ──────────────────────────────────────────────── -->
{#if currentOppskrift}
  {@const opp = currentOppskrift}
  <div
    id="detail-overlay"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) lukkDetalj(); }}
  >
    <div id="detail-panel">
      <div class="detail-topbar">
        <button class="btn-back" onclick={lukkDetalj}>← Tilbake</button>
        <button
          class="detail-fav"
          class:aktiv={favoritter.has(opp.id)}
          title={favoritter.has(opp.id) ? "Fjern favoritt" : "Legg til favoritt"}
          onclick={() => toggleFavoritt(opp.id)}
        >{favoritter.has(opp.id) ? "⭐ Favoritt" : "☆ Favoritt"}</button>
        <button
          class="detail-handle"
          class:aktiv={handleliste.some((p) => p.id === opp.id)}
          title={handleliste.some((p) => p.id === opp.id) ? "I handlelista" : "Legg i handleliste"}
          onclick={() => leggIHandleliste(opp.id, curP)}
        >{handleliste.some((p) => p.id === opp.id) ? "🛒 I handleliste" : "🛒 Legg i handleliste"}</button>
        <button
          class="detail-cook"
          class:aktiv={cookModeAktiv}
          title={cookModeAktiv ? "Skjermen holdes våken" : "Hold skjermen våken under matlaging"}
          onclick={toggleCookMode}
        >{cookModeAktiv ? "👩‍🍳 Holder våken" : "👩‍🍳 Hold skjermen våken"}</button>
        <span class="detail-type-pill">{emoji(opp.type)} {opp.type ?? "Oppskrift"}</span>
        {#if opp.tid}<span class="detail-time-pill">⏱ {opp.tid}</span>{/if}
      </div>

      <div class="detail-hero">
        {#if imgSrc(opp.id)}
          <img src={imgSrc(opp.id)} alt={opp.navn} />
        {:else}
          <div class="detail-hero-placeholder">{emoji(opp.type)}</div>
        {/if}
        <div class="detail-hero-gradient"></div>
      </div>

      <div class="detail-body">
        <h2 class="detail-title">{opp.navn}</h2>
        {#if opp.beskrivelse}<p class="detail-desc">{opp.beskrivelse}</p>{/if}

        <div class="portion-row">
          <span class="portion-label">Porsjoner:</span>
          <div class="portion-ctrl">
            <button class="portion-btn" disabled={curP <= 1} onclick={() => endrePorsjoner(-1)}>−</button>
            <span class="portion-num">{curP}</span>
            <button class="portion-btn" onclick={() => endrePorsjoner(1)}>+</button>
          </div>
        </div>

        <div class="detail-columns">
          <div>
            <div class="detail-section-title">Ingredienser</div>
            {#each grupper as [g, ings]}
              {#if multiGroup}<div class="ing-group-title">{g}</div>{/if}
              {#each ings as i}
                {@const m = fmtMengde(scaleMengde(i.mengde, origP, curP))}
                <div class="ing-item">
                  <span class="ing-mengde">{m}</span>
                  <span class="ing-enhet">{i.enhet ?? ""}</span>
                  <span class="ing-navn">{i.navn ?? ""}</span>
                </div>
              {/each}
            {/each}
          </div>
          <div>
            <div class="detail-section-title">Fremgangsmåte</div>
            {#each opp.trinn as t, idx}
              <div class="step-item">
                <div class="step-num">{t.nummer ?? idx + 1}</div>
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
              </div>
            {/each}
          </div>
        </div>

        <div class="naering-wrap">
          {#if naeringPerPorsjon}
            {@const n = naeringPerPorsjon}
            <div class="naering-title">📊 Næringsinformasjon – per porsjon (ca.)</div>
            <div class="naering-grid">
              <div class="naering-card">
                <div class="naering-icon">🔥</div>
                <div class="naering-val">{n.e}</div>
                <div class="naering-unit">kcal</div>
                <div class="naering-lbl">Energi</div>
              </div>
              <div class="naering-card">
                <div class="naering-icon">🥩</div>
                <div class="naering-val">{n.p}</div>
                <div class="naering-unit">g</div>
                <div class="naering-lbl">Protein</div>
              </div>
              <div class="naering-card">
                <div class="naering-icon">🫙</div>
                <div class="naering-val">{n.f}</div>
                <div class="naering-unit">g</div>
                <div class="naering-lbl">Fett</div>
              </div>
              <div class="naering-card">
                <div class="naering-icon">🌾</div>
                <div class="naering-val">{n.k}</div>
                <div class="naering-unit">g</div>
                <div class="naering-lbl">Karbohydrat</div>
              </div>
              {#if n.fi != null}
                <div class="naering-card">
                  <div class="naering-icon">🌿</div>
                  <div class="naering-val">{n.fi}</div>
                  <div class="naering-unit">g</div>
                  <div class="naering-lbl">Fiber</div>
                </div>
              {/if}
            </div>
            <div class="naering-disclaimer">
              Beregnet fra {n.treff} av {n.totalt} ingredienser · Kilde: Matvaretabellen.no
            </div>
          {:else}
            <div class="naering-title">📊 Næringsinformasjon</div>
            <div class="naering-unavailable">
              Ikke nok ingrediensdata til å beregne næringsinnhold for denne oppskriften.
            </div>
          {/if}
        </div>
        {#if prisVist}
          {@const pr = prisVist}
          <div class="pris-wrap">
            <div class="pris-title">💰 Estimert kostnad</div>
            <div class="pris-tall">
              ~{pr.total} kr · ~{pr.perPorsjon} kr/porsjon
            </div>
            <div class="pris-dekning">
              {pr.priset} av {pr.antall} ingredienser priset
            </div>
          </div>
        {/if}
        <section class="detail-notat">
          <div class="detail-notat-title">📝 Mine notater</div>
          <textarea
            class="detail-notat-felt"
            placeholder="Skriv ditt eget notat… (lagres automatisk)"
            value={notater[opp.id] ?? ""}
            oninput={(e) => onNotatInput(opp.id, e)}
          ></textarea>
        </section>
      </div>
    </div>
  </div>
{/if}

{#if loading}
  <div id="loader"><div class="spinner"></div></div>
{/if}

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

<style>
  /* Layout-CSS portert fra renderer/styles.css. Globale variabler i app.css. */
  :global(body) { display: flex; }

  #sidebar {
    width: var(--sidebar-w); min-width: var(--sidebar-w);
    background: var(--sidebar-bg); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; height: 100vh; overflow: hidden; z-index: 10;
  }
  .sidebar-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 22px 20px 18px; border-bottom: 1px solid var(--border); background: var(--bg-warm);
  }
  .logo-icon { font-size: 26px; }
  .logo-text {
    font-family: var(--font-head); font-size: 1.35rem; font-weight: 700;
    color: var(--accent-dark); letter-spacing: 0.2px;
  }

  .search-wrap { position: relative; padding: 14px 14px 8px; }
  .search-icon {
    position: absolute; left: 26px; top: 50%; transform: translateY(-50%);
    font-size: 13px; pointer-events: none; opacity: 0.45;
  }
  #sok-input {
    width: 100%; background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-sm); color: var(--text); font-family: var(--font-ui);
    font-size: 0.88rem; padding: 8px 12px 8px 32px; outline: none;
    transition: border-color 0.2s, box-shadow 0.2s; box-shadow: var(--shadow-sm);
  }
  #sok-input::placeholder { color: var(--text-dim); }
  #sok-input:focus { border-color: var(--border-focus); box-shadow: 0 0 0 3px rgba(181,69,27,0.12); }

  #kategori-liste { flex: 1; overflow-y: auto; padding: 6px 10px 16px; }
  .kat-btn {
    display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 10px;
    border: none; background: transparent; border-radius: var(--radius-sm); cursor: pointer;
    color: var(--text-muted); font-family: var(--font-ui); font-size: 0.87rem;
    text-align: left; transition: background 0.15s, color 0.15s; user-select: none;
  }
  .kat-btn:hover { background: rgba(181,69,27,0.07); color: var(--text); }
  .kat-btn.active { background: var(--accent-bg); color: var(--accent); font-weight: 600; }
  .kat-btn.alle { color: var(--text); font-weight: 600; margin-bottom: 4px; }
  .kat-btn.alle.active { color: var(--accent); }
  .kat-emoji { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
  .kat-navn { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kat-teller {
    font-size: 0.73rem; color: var(--text-dim); background: rgba(44,26,14,0.06);
    border-radius: 10px; padding: 1px 6px; flex-shrink: 0;
  }
  .kat-btn.active .kat-teller { background: var(--accent-bg2); color: var(--accent); }
  .kat-divider { height: 1px; background: var(--border); margin: 8px 4px; }

  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }
  #main-header {
    padding: 20px 28px 14px; border-bottom: 1px solid var(--border-light);
    display: flex; align-items: baseline; gap: 10px; flex-shrink: 0;
    background: var(--surface); box-shadow: 0 1px 3px rgba(44,26,14,0.06);
  }
  #header-tittel {
    font-family: var(--font-head); font-size: 1.5rem; font-weight: 700;
    color: var(--text); letter-spacing: -0.2px;
  }
  .count-badge {
    display: inline-block; font-size: 0.8rem; color: var(--text-muted);
    background: var(--bg-warm); border: 1px solid var(--border-light);
    border-radius: 12px; padding: 2px 10px;
  }

  #grid-wrap {
    flex: 1; overflow-y: auto; padding: 24px 26px 20px;
    display: flex; flex-direction: column; background: var(--bg);
  }
  #recipe-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 18px; align-content: start;
  }
  .recipe-card {
    background: var(--card); border: 1px solid var(--border-light); border-radius: var(--radius);
    overflow: hidden; cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s;
    box-shadow: var(--shadow-sm);
  }
  .recipe-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: var(--border); }
  .card-img-wrap { position: relative; width: 100%; aspect-ratio: 4 / 3; overflow: hidden; background: var(--bg-warm); }
  .card-img-wrap img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.35s ease; display: block; }
  .recipe-card:hover .card-img-wrap img { transform: scale(1.05); }
  .card-img-placeholder {
    width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
    font-size: 2.5rem; color: var(--text-dim); background: var(--bg-warm);
  }
  .card-badge-time {
    position: absolute; bottom: 8px; right: 8px; background: rgba(255,255,255,0.92);
    backdrop-filter: blur(4px); border-radius: 20px; padding: 3px 8px; font-size: 0.72rem;
    color: var(--text-muted); font-weight: 600; border: 1px solid var(--border-light);
  }
  .card-fav {
    position: absolute;
    top: 8px; left: 8px;
    border: none;
    background: rgba(0, 0, 0, 0.35);
    color: #fff;
    font-size: 1.1rem;
    line-height: 1;
    padding: 4px 6px;
    border-radius: 8px;
    cursor: pointer;
  }
  .card-fav.aktiv { background: rgba(0, 0, 0, 0.5); }
  .card-badge-notat {
    position: absolute; top: 8px; right: 8px;
    background: rgba(255,255,255,0.92); border-radius: 20px;
    padding: 2px 6px; font-size: 0.8rem; border: 1px solid var(--border-light);
  }
  .detail-notat { margin-top: 24px; }
  .detail-notat-title { font-weight: 700; margin-bottom: 8px; color: var(--text); }
  .detail-notat-felt {
    width: 100%; min-height: 90px; resize: vertical;
    padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--surface); color: var(--text); font-family: var(--font-ui); font-size: 0.95rem;
  }
  .detail-notat-felt:focus { outline: none; border-color: var(--border-focus); }
  .detail-fav {
    border: 1px solid var(--border);
    background: var(--bg-warm);
    color: var(--text);
    padding: 6px 12px;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .detail-fav.aktiv { border-color: var(--accent-dark); }
  .detail-handle {
    border: 1px solid var(--border);
    background: var(--bg-warm);
    color: var(--text);
    padding: 6px 12px;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .detail-handle.aktiv { border-color: var(--accent-dark); }
  .detail-cook {
    border: 1px solid var(--border); background: var(--surface); color: var(--text);
    border-radius: var(--radius); padding: 8px 14px; cursor: pointer; font-size: 0.9rem;
  }
  .detail-cook:hover { border-color: var(--border-focus); }
  .detail-cook.aktiv { background: var(--accent); color: #fff; border-color: var(--accent); }
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
  #handle-wrap { padding: 24px 32px; max-width: 900px; }
  .handle-topp { display: flex; justify-content: space-between; align-items: center; }
  .handle-tom {
    border: 1px solid var(--border); background: var(--bg-warm); color: var(--text);
    padding: 6px 12px; border-radius: var(--radius); cursor: pointer; font-size: 0.85rem;
  }
  .handle-rad {
    display: flex; align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid var(--border-light);
  }
  .handle-navn { flex: 1; font-weight: 600; }
  .handle-porsjoner { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--text-muted); }
  .handle-fjern {
    border: none; background: none; cursor: pointer; color: var(--text-muted); font-size: 1rem;
  }
  .handle-ingredienser { margin-top: 28px; }
  .handle-ingredienser ul { list-style: none; padding: 0; }
  .handle-ingredienser li {
    display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--border-light);
  }
  .handle-mengde { min-width: 90px; color: var(--accent-dark); font-weight: 600; }
  .handle-sum {
    margin-top: 18px; font-size: 1.05rem; font-weight: 700; color: var(--text);
  }
  #innst-wrap { flex: 1; overflow-y: auto; padding: 24px 32px; }
  .innst-seksjon {
    max-width: 640px; margin-bottom: 16px;
    border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--surface); overflow: hidden;
  }
  .innst-seksjon > summary {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 18px; cursor: pointer; list-style: none;
    user-select: none; background: var(--bg-warm);
  }
  .innst-seksjon > summary::-webkit-details-marker { display: none; }
  .innst-seksjon > summary::after {
    content: "▾"; margin-left: auto; font-size: 0.9rem;
    color: var(--text-muted); transition: transform 0.15s;
  }
  .innst-seksjon[open] > summary::after { transform: rotate(180deg); }
  .innst-seksjon > summary h2 { margin: 0; font-size: 1.15rem; }
  .innst-teller {
    background: var(--accent); color: #fff; border-radius: 20px;
    min-width: 20px; padding: 1px 7px; font-size: 0.78rem; text-align: center;
  }
  /* Innhold i seksjonen (alt bortsett fra summary) får padding */
  .innst-seksjon > :not(summary) { margin-left: 18px; margin-right: 18px; }
  .innst-seksjon > p.innst-hint { margin-top: 14px; }
  .innst-seksjon > label:last-child { margin-bottom: 16px; }
  .innst-hint { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 16px; }
  .tema-valg {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    border: 1px solid var(--border); border-radius: var(--radius);
    margin-bottom: 8px; cursor: pointer; background: var(--surface);
  }
  .tema-valg:hover { background: var(--card-hover); }
  .tema-valg.valgt { border-color: var(--accent); background: var(--accent-bg); }
  .tema-valg input { accent-color: var(--accent); }
  .diett-pille {
    display: inline-flex; align-items: center; gap: 6px;
    margin-left: 12px; padding: 4px 10px;
    background: var(--accent-soft, var(--bg-warm)); color: var(--text);
    border: 1px solid var(--border); border-radius: 20px;
    font-size: 0.82rem; cursor: pointer;
  }
  .diett-pille:hover { border-color: var(--border-focus); }
  #lager-wrap { flex: 1; overflow-y: auto; padding: 24px 32px; max-width: 760px; }
  .lager-rediger, .lager-forslag { margin-bottom: 28px; }
  .lager-liste { list-style: none; padding: 0; }
  .lager-vare {
    display: flex; align-items: center; gap: 10px; padding: 8px 10px;
    border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 6px;
    background: var(--surface);
  }
  .lager-navn { flex: 1; font-weight: 600; }
  .lager-utlop { font-size: 0.82rem; color: var(--text-muted); }
  .lager-vare.snart { border-color: #d8821a; }
  .lager-vare.snart .lager-utlop { color: #d8821a; }
  .lager-vare.utgaatt { border-color: #c0392b; }
  .lager-vare.utgaatt .lager-utlop { color: #c0392b; font-weight: 700; }
  .lager-fjern { border: none; background: none; cursor: pointer; color: var(--text-muted); font-size: 1rem; }
  .lager-fjern:hover { color: var(--text); }
  .lager-tom, .lager-tom-btn { color: var(--text-muted); }
  .lager-tom-btn { border: 1px solid var(--border); background: var(--surface); border-radius: var(--radius); padding: 6px 12px; cursor: pointer; margin-top: 4px; }
  .empty-hint { font-size: 0.85rem; opacity: 0.7; margin-top: 6px; }
  .beta-merke {
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.5px;
    background: var(--accent); color: #fff; border-radius: 4px;
    padding: 1px 5px; vertical-align: middle; margin-left: 6px;
  }
  .card-body { padding: 12px 14px 14px; }
  .card-cat {
    font-size: 0.7rem; color: var(--accent); font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; margin-bottom: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .card-name {
    font-family: var(--font-head); font-size: 0.95rem; font-weight: 700; line-height: 1.35;
    color: var(--text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; min-height: 2.55em; margin-bottom: 8px;
  }
  .card-meta { display: flex; gap: 10px; font-size: 0.75rem; color: var(--text-muted); }
  .card-meta span { display: flex; align-items: center; gap: 3px; }

  #pagination {
    display: flex; justify-content: center; align-items: center; gap: 4px;
    padding: 20px 0 8px; flex-wrap: wrap;
  }
  .page-btn {
    min-width: 34px; height: 34px; border: 1px solid var(--border); background: var(--surface);
    color: var(--text-muted); border-radius: var(--radius-sm); cursor: pointer; font-size: 0.85rem;
    font-family: var(--font-ui); padding: 0 8px; transition: all 0.15s; box-shadow: var(--shadow-sm);
  }
  .page-btn:hover:not(:disabled) { background: var(--bg-warm); color: var(--text); border-color: var(--accent); }
  .page-btn.active {
    background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 700;
    box-shadow: 0 2px 8px rgba(181,69,27,0.3);
  }
  .page-btn:disabled { opacity: 0.3; cursor: not-allowed; box-shadow: none; }
  .page-ellipsis { color: var(--text-dim); padding: 0 4px; }

  .empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 12px; padding: 80px 20px; color: var(--text-muted); text-align: center; grid-column: 1 / -1;
  }
  .empty-state .empty-icon { font-size: 3rem; opacity: 0.4; }

  #detail-overlay {
    position: fixed; inset: 0; background: rgba(44,26,14,0.45); backdrop-filter: blur(3px);
    z-index: 100; display: flex; align-items: stretch; justify-content: flex-end;
  }
  #detail-panel {
    width: min(880px, 100vw); background: var(--surface); overflow-y: auto;
    border-left: 1px solid var(--border); animation: slideIn 0.22s ease;
  }
  @keyframes slideIn { from { transform: translateX(50px); opacity: 0 } to { transform: translateX(0); opacity: 1 } }

  .detail-topbar {
    position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border-light); padding: 13px 22px;
    display: flex; align-items: center; gap: 10px; z-index: 5;
  }
  .btn-back {
    display: flex; align-items: center; gap: 5px; background: var(--bg-warm);
    border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-muted);
    font-family: var(--font-ui); font-size: 0.85rem; padding: 6px 12px; cursor: pointer; transition: all 0.15s;
  }
  .btn-back:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
  .detail-type-pill {
    background: var(--accent-bg); color: var(--accent); border: 1px solid rgba(181,69,27,0.2);
    border-radius: 20px; padding: 3px 12px; font-size: 0.78rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .detail-time-pill {
    display: flex; align-items: center; gap: 4px; background: var(--bg-warm);
    border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px;
    font-size: 0.78rem; color: var(--text-muted); margin-left: auto;
  }

  .detail-hero { position: relative; width: 100%; height: 320px; overflow: hidden; background: var(--bg-warm); }
  .detail-hero img { width: 100%; height: 100%; object-fit: cover; }
  .detail-hero-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 4rem; }
  .detail-hero-gradient {
    position: absolute; bottom: 0; left: 0; right: 0; height: 100px;
    background: linear-gradient(to top, rgba(255,255,255,0.9), transparent);
  }

  .detail-body { padding: 0 28px 20px; }
  .detail-title {
    font-family: var(--font-head); font-size: 1.9rem; font-weight: 700; letter-spacing: -0.3px;
    line-height: 1.2; padding: 18px 0 8px; color: var(--text);
  }
  .detail-desc {
    color: var(--text-muted); font-size: 0.93rem; line-height: 1.7; margin-bottom: 18px;
    max-width: 680px; font-style: italic;
  }

  .portion-row {
    display: flex; align-items: center; gap: 14px; padding: 14px 0 18px;
    border-top: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); margin-bottom: 24px;
  }
  .portion-label { font-size: 0.9rem; color: var(--text-muted); }
  .portion-ctrl {
    display: flex; align-items: center; background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow-sm);
  }
  .portion-btn {
    width: 36px; height: 36px; border: none; background: var(--bg-warm); color: var(--text-muted);
    font-size: 1.2rem; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; justify-content: center;
  }
  .portion-btn:hover { background: var(--accent-bg); color: var(--accent); }
  .portion-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .portion-num {
    width: 44px; text-align: center; font-size: 1rem; font-weight: 700; color: var(--text);
    border-left: 1px solid var(--border); border-right: 1px solid var(--border);
    line-height: 36px; font-family: var(--font-head);
  }

  .detail-columns { display: grid; grid-template-columns: 280px 1fr; gap: 40px; align-items: start; }
  .detail-section-title {
    font-family: var(--font-head); font-size: 1rem; font-weight: 700; color: var(--text);
    margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid var(--accent); display: inline-block;
  }
  .ing-group-title {
    font-size: 0.75rem; font-weight: 700; color: var(--text-dim); text-transform: uppercase;
    letter-spacing: 0.6px; margin: 14px 0 6px;
  }
  .ing-item {
    display: flex; align-items: baseline; gap: 5px; padding: 6px 0;
    border-bottom: 1px solid var(--border-light); font-size: 0.9rem;
  }
  .ing-item:last-child { border-bottom: none; }
  .ing-mengde { font-weight: 700; color: var(--accent); min-width: 52px; font-size: 0.88rem; }
  .ing-enhet { color: var(--text-muted); font-size: 0.82rem; }
  .ing-navn { color: var(--text); }

  .step-item { display: flex; gap: 14px; margin-bottom: 18px; }
  .step-num {
    flex-shrink: 0; width: 28px; height: 28px; background: var(--accent); border-radius: 50%;
    display: flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 700;
    color: #fff; margin-top: 2px; font-family: var(--font-head);
  }
  .step-tekst { font-size: 0.93rem; line-height: 1.75; color: var(--text); flex: 1; }

  .naering-wrap {
    margin-top: 28px; padding: 18px 20px; background: var(--bg-warm);
    border: 1px solid var(--border); border-radius: var(--radius);
  }
  .naering-title {
    font-family: var(--font-head); font-size: 1rem; font-weight: 700; color: var(--text);
    margin-bottom: 14px; padding-bottom: 8px; border-bottom: 2px solid var(--accent); display: inline-block;
  }
  .naering-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; }
  .naering-card {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius-sm);
    padding: 12px; text-align: center; box-shadow: var(--shadow-sm);
  }
  .naering-icon { font-size: 1.3rem; margin-bottom: 4px; }
  .naering-val { font-family: var(--font-head); font-size: 1.15rem; font-weight: 700; color: var(--text); line-height: 1; }
  .naering-unit { font-size: 0.7rem; color: var(--text-muted); }
  .naering-lbl { font-size: 0.72rem; color: var(--text-muted); margin-top: 3px; }
  .naering-disclaimer { margin-top: 10px; font-size: 0.72rem; color: var(--text-dim); text-align: center; font-style: italic; }
  .naering-unavailable { text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 8px 0; font-style: italic; }

  .pris-wrap {
    margin-top: 1rem;
    padding: 1rem 1.25rem;
    background: var(--bg-warm);
    border-radius: var(--radius);
    border: 1px solid var(--border);
  }
  .pris-title { font-weight: 600; margin-bottom: 0.35rem; color: var(--text); }
  .pris-tall { font-size: 1.15rem; color: var(--accent-dark); }
  .pris-dekning {
    font-size: 0.85rem;
    color: var(--text-dim);
    margin-top: 0.25rem;
  }

  #loader {
    position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
    background: rgba(250,246,239,0.7); z-index: 200; pointer-events: none;
  }
  .spinner {
    width: 36px; height: 36px; border: 3px solid var(--border); border-top-color: var(--accent);
    border-radius: 50%; animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg) } }
</style>
