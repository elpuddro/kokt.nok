<script lang="ts">
  import { invoke, convertFileSrc } from "@tauri-apps/api/core";
  import { load } from "@tauri-apps/plugin-store";
  import { onMount, onDestroy } from "svelte";
  import { favorittLast, favorittToggle } from "$lib/favoritter";
  import {
    handlelisteLast, handlelisteLeggTil, handlelisteFjern,
    handlelisteSettPorsjoner, handlelisteTøm, type HandlelistePost,
  } from "$lib/handleliste";
  import { temaLast, temaSett, gjeldendeTema, erGyldigTema, TEMAER, type TemaId, type Lagret } from "$lib/tema";
  import { notaterLast, notatSett } from "$lib/notater";
  import { diettLast, diettSett, DIETT_FILTRE } from "$lib/diett";
  import { lagerLast, lagerLeggTil, lagerFjern, lagerTøm, type LagerVare } from "$lib/lager";
  import { matplanLast, matplanLagre, matplanTøm, type Uke, type Dag } from "$lib/matplan";
  import { utlopsStatus } from "$lib/lager-logikk";
  import { finnTider } from "$lib/tid-parsing";
  import { profilLast, profilSettAktiv, profilOpprett, profilOppdater, profilSlett, tdee, dagsbehov, dekningsProsent, midjeOverGrenje, type Brukerprofil, type ProfilStore } from "$lib/helse";
  import { versjonerLast, kladd_sett, kladd_fjern, versjon_lagre, versjon_slett } from "$lib/versjoner";
  import { kopiFraOppskrift, beregnDiff, type OppskriftKopi, type KopiIngrediens, type KopiTrinn, type VersjonSnapshot } from "$lib/versjoner-logikk";
  import Hoytidspynt from "$lib/Hoytidspynt.svelte";
  import { formaterOppskrift } from "$lib/deling";
  import { loggLast, loggLeggTil, loggFjern, type Loggpost, type MåltidTidspunkt } from "$lib/matvarelogg";
  import { loggForDato, tidspunktFraKlokkeslett, loggSumNæring, loggKcalPerDag } from "$lib/matvarelogg-logikk";

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
  let sorter = $state("navn_asc");
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
  let plan = $state<Uke | null>(null);
  let planDagsmaal = $state(2000);
  let planPersoner = $state(2);
  let planLaster = $state(false);
  let planSesong = $state(false);
  let profilStore = $state<ProfilStore>({ profiler: [], aktivId: null });
  let profilDropdownÅpen = $state(false);
  let profilSkjemaÅpent = $state(false);
  let profilRedigerer = $state<Brukerprofil | null>(null);
  let profilFelt = $state({ navn: "", kjønn: "mann" as "mann"|"kvinne", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat" as Brukerprofil["aktivitet"], mål: "vedlikehold" as Brukerprofil["mål"], midje: undefined as number | undefined, midjeFilter: false });
  let aboutInfo = $state<{ navn: string; epost: string; versjon: string; beskrivelse: string } | null>(null);
  let innstFane = $state<"tema" | "diett" | "profil">("tema");

  // ── Deling ──────────────────────────────────────────────────────────────────
  const erFengsel = import.meta.env.VITE_UTGAVE === 'fengsel';
  let delKopiert = $state(false);

  // ── Versjonering / redigering ────────────────────────────────────────────────
  let redigerModus = $state(false);
  let kladd = $state<OppskriftKopi | null>(null);
  let historikk = $state<VersjonSnapshot[]>([]);
  let sammenlignVersjon = $state<VersjonSnapshot | null>(null);
  let lagreModalApen = $state(false);
  let lagreLabel = $state("");
  let kladdTimer: any = null;

  // ── Dagbok (kaloriregnskap) ───────────────────────────────────────────────────
  let dagbokPoster = $state<Loggpost[]>([]);
  let dagbokValgtDato = $state<string>(new Date().toISOString().slice(0, 10));
  let dagbokTab = $state<"dag" | "uke" | "måned">("dag");
  let loggModalApen = $state(false);
  let loggModalTab = $state<"oppskrift" | "fri">("oppskrift");
  let loggTidspunkt = $state<MåltidTidspunkt>(tidspunktFraKlokkeslett(new Date().getHours()));
  let loggSøk = $state("");
  let loggSøkResultater = $state<any[]>([]);
  let loggValgtOppskrift = $state<any>(null);
  let loggPorsjoner = $state(1);
  let loggFriBesk = $state("");
  let loggFriKcal = $state<number | null>(null);
  let loggFriProtein = $state<number | null>(null);
  let loggFriFett = $state<number | null>(null);
  let loggFriKarbo = $state<number | null>(null);
  let næringMap = $state<Record<number, { kcal: number; protein: number; fett: number; karbo: number }>>({});

  // ── Tidsbasert forside ────────────────────────────────────────────────────────
  interface ForsideOppskrift { id: number; navn: string; tid: string | null; bilde: string | null }

  const TIDSSONER: Array<{ fra: number; til: number; typer: string[]; tittel: string }> = [
    { fra: 6,  til: 10, typer: ["Frokost", "Sandwich/smørbrød", "Snacks"],         tittel: "God morgen 🌅" },
    { fra: 10, til: 14, typer: ["Lunsj", "Tapas/småretter", "Sandwich/smørbrød"],  tittel: "Tid for lunsj 🥗" },
    { fra: 14, til: 18, typer: ["Middag", "Supper", "Gryter"],                      tittel: "Middagstid 🍽️" },
    { fra: 18, til: 22, typer: ["Middag", "Tapas/småretter", "Forretter"],          tittel: "God kveld 🌆" },
    { fra: 22, til: 6,  typer: ["Middag", "Supper", "Snacks"],                      tittel: "Sent på kvelden 🌙" },
  ];

  let forsideOppskrifter = $state<ForsideOppskrift[]>([]);
  let forsideTittel = $state("");

  let aktivHoytid = $state<string | null>(null);
  let pynt = $state(false);

  const HOYTID_BANNER: Record<string, string> = {
    jul:       "🎄 Juleoppskrifter",
    paske:     "🐣 Påskeoppskrifter",
    mai17:     "🇳🇴 17. mai-mat",
    sankthans: "🔥 Sankthansmat",
    farikaal:  "🍲 Fårikålens dag",
    halloween: "🎃 Halloweenmat",
    valentins: "❤️ Valentinsmiddag",
  };

  let cookModeAktiv = $state(false);
  type Timer = { id: number; navn: string; igjen: number; total: number; ferdig: boolean; pauset: boolean };
  let timere = $state<Timer[]>([]);
  let nesteTimerId = 1;
  let timerTikk: any = null;
  let lydCtx: AudioContext | null = null;

  let aktivProfil = $derived(
    profilStore.profiler.find((p) => p.id === profilStore.aktivId) ?? null
  );
  let aktivtMidjeFilter = $derived(aktivProfil ? midjeOverGrenje(aktivProfil) : false);
  let midjeOverGrenjeFelt = $derived(
    profilFelt.midje != null &&
    (profilFelt.kjønn === "mann" ? profilFelt.midje > 94 : profilFelt.midje > 80)
  );

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
          kategori: currentKategori, sok, side, perSide, dietter: aktiveDietter, sorter,
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

  async function onSorterChange() {
    const s = await load("sorter.json");
    await s.set("sorter", sorter);
    await s.save();
    side = 1;
    await fetchGrid();
  }

  function velgKategori(k: string) {
    currentKategori = k;
    side = 1;
    sok = "";
    fetchGrid();
    if (k === "alle") lastForside();
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

  function velgMatplan() {
    currentKategori = "__plan__";
    side = 1;
    sok = "";
    oppskrifter = [];
  }

  function velgDagbok() {
    currentKategori = "__dagbok__";
    side = 1;
    sok = "";
    oppskrifter = [];
  }

  async function oppdaterNæringMap(poster: Loggpost[]) {
    const ids = [...new Set(
      poster.filter(p => p.type === "oppskrift").map(p => (p as any).oppskriftId)
    )];
    for (const id of ids) {
      if (næringMap[id]) continue;
      try {
        const o = await invoke<any>("hent_oppskrift", { id });
        if (o?.naering) {
          næringMap[id] = {
            kcal: o.naering.energi ?? 0,
            protein: o.naering.protein ?? 0,
            fett: o.naering.fett ?? 0,
            karbo: o.naering.karbohydrat ?? 0,
          };
        }
      } catch { /* slettet oppskrift — næring forblir udefinert → 0 */ }
    }
    næringMap = { ...næringMap }; // trigger reaktivitet
  }

  async function velgProfilAktiv(id: string) {
    profilStore = await profilSettAktiv(id);
    profilDropdownÅpen = false;
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
    // Refresh versioning state if a recipe is open under the new profile
    if (currentOppskrift) {
      const nyProfil = profilStore.profiler.find(p => p.id === profilStore.aktivId) ?? null;
      if (nyProfil) {
        const entry = await versjonerLast(nyProfil.id, currentOppskrift.id);
        kladd = entry?.kladd ?? null;
        historikk = entry?.historikk ?? [];
      } else {
        kladd = null;
        historikk = [];
      }
      redigerModus = false;
      sammenlignVersjon = null;
    }
  }

  function startNyProfil() {
    profilRedigerer = null;
    profilFelt = { navn: "", kjønn: "mann", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat", mål: "vedlikehold", midje: undefined, midjeFilter: false };
    profilSkjemaÅpent = true;
  }

  function startRedigerProfil(p: Brukerprofil) {
    profilRedigerer = p;
    profilFelt = {
      navn: p.navn,
      kjønn: p.kjønn,
      alder: p.alder,
      høyde: p.høyde,
      vekt: p.vekt,
      aktivitet: p.aktivitet,
      mål: p.mål,
      midje: p.midje,
      midjeFilter: p.midjeFilter ?? false,
    };
    profilSkjemaÅpent = true;
  }

  async function lagreProfil() {
    if (!profilFelt.navn.trim()) return;
    if (profilRedigerer) {
      profilStore = await profilOppdater({ ...profilRedigerer, ...profilFelt });
    } else {
      profilStore = await profilOpprett(profilFelt);
    }
    profilSkjemaÅpent = false;
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
  }

  async function slettProfil(id: string) {
    if (!confirm("Slett denne profilen?")) return;
    profilStore = await profilSlett(id);
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
  }

  function nåværendeTidssone() {
    const t = new Date().getHours();
    return TIDSSONER.find(s =>
      s.til > s.fra ? t >= s.fra && t < s.til : t >= s.fra || t < s.til
    )!;
  }

  async function lastForside() {
    if (aktivHoytid) {
      forsideTittel = HOYTID_BANNER[aktivHoytid] ?? "Sesongmat";
      forsideOppskrifter = await invoke<ForsideOppskrift[]>("forside_oppskrifter", {
        typer: [],
        nattFilter: false,
        hoytid: aktivHoytid,
      });
    } else {
      const sone = nåværendeTidssone();
      forsideTittel = sone.tittel;
      const t = new Date().getHours();
      const nattFilter = (t >= 22 || t < 6) && aboutInfo === null;
      forsideOppskrifter = await invoke<ForsideOppskrift[]>("forside_oppskrifter", {
        typer: sone.typer,
        nattFilter,
        hoytid: null,
      });
    }
  }

  type LaastSlot = { dag: number; slot: string; id: number };
  function samleLaaste(): LaastSlot[] {
    if (!plan) return [];
    const ut: LaastSlot[] = [];
    plan.dager.forEach((d, dag) => {
      for (const slot of ["frokost", "lunsj", "middag", "kveldsmat"] as const) {
        const s = (d as any)[slot];
        if (s?.kind === "rett" && s.laast) ut.push({ dag, slot, id: s.id });
      }
    });
    return ut;
  }

  async function genererPlan() {
    planLaster = true;
    try {
      const uke = await invoke<Uke>("generer_matplan", {
        dagsmaal: planDagsmaal,
        personer: planPersoner,
        dietter: aktiveDietter,
        laaste: samleLaaste(),
        sunnPlan: aktivtMidjeFilter,
        hoytid: planSesong && aktivHoytid ? aktivHoytid : null,
      });
      plan = uke;
    } catch (e) {
      console.error("generer_matplan feilet:", e);
    } finally {
      planLaster = false;
    }
  }

  async function onPlanSesongChange() {
    const store = await load("plan.json");
    await store.set("sesong", planSesong);
    await store.save();
  }

  async function onPyntChange() {
    const store = await load("innstillinger.json");
    await store.set("pynt", pynt);
    await store.save();
  }

  function toggleLaas(dag: number, slot: string) {
    if (!plan) return;
    const s = (plan.dager[dag] as any)[slot];
    if (s?.kind === "rett") { s.laast = !s.laast; plan = { ...plan }; }
  }
  async function sendUkaTilHandleliste() {
    if (!plan) return;
    let lagtTil = 0;
    for (const d of plan.dager) {
      for (const slot of ["frokost", "lunsj", "middag", "kveldsmat"] as const) {
        const s = (d as any)[slot];
        if (s?.kind === "rett") {
          // porsjoner skaleres på antall personer (gjenbruker eksisterende handleliste-skalering)
          handleliste = await handlelisteLeggTil(s.id, planPersoner, handleliste);
          lagtTil++;
        }
      }
    }
    alert(`La ${lagtTil} retter i handlelista (porsjoner = ${planPersoner}).`);
  }

  async function lagreUka() {
    if (!plan) return;
    await matplanLagre(plan);
    alert("Ukemenyen er lagret.");
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

  function onNyVareInput(e: Event) {
    nyVareNavn = (e.target as HTMLInputElement).value;
    clearTimeout(autoTimer);
    const p = nyVareNavn.trim();
    if (p.length < 2) { autoForslag = []; return; }
    autoTimer = setTimeout(async () => {
      try { autoForslag = await invoke("ingrediens_forslag", { prefiks: p }); }
      catch (e) { console.error(e); autoForslag = []; }
    }, 200);
  }
  async function leggTilVare(navn?: string) {
    const n = (navn ?? nyVareNavn).trim();
    if (!n) return;
    lager = await lagerLeggTil(n, nyVareUtloper || null, lager);
    nyVareNavn = ""; nyVareUtloper = ""; autoForslag = [];
    oppdaterLagerForslag();
  }
  async function lagdeDenne(opp: any) {
    const ings: string[] = (opp.ingredienser ?? []).map((i: any) => (i.navn ?? "").toLowerCase());
    const fjernet: string[] = [];
    let ny = lager;
    for (const v of [...lager]) {
      const vl = v.navn.toLowerCase();
      if (ings.some((il) => il.includes(vl) || vl.includes(il))) {
        ny = await lagerFjern(v.navn, ny);
        fjernet.push(v.navn);
      }
    }
    lager = ny;
    oppdaterLagerForslag();
    if (fjernet.length > 0) alert(`Fjernet fra kjøleskapet: ${fjernet.join(", ")}`);
  }

  // Returner effektivt tema: manuell → direkte; auto → OS-mørkt gir "dark",
  // ellers dato-basert sesong/høytid.
  function effektivtTema(lagret: Lagret): TemaId {
    if (lagret.modus === "manuell" && erGyldigTema(lagret.tema)) return lagret.tema;
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
    return gjeldendeTema(new Date());
  }

  function applyTema(id: TemaId) {
    aktivtTemaId = id;
    const el = document.documentElement;
    if (id === "varm") el.removeAttribute("data-tema");
    else el.setAttribute("data-tema", id);
  }

  let darkModeQuery: MediaQueryList | null = null;
  function onDarkModeChange() {
    if (temaValg.modus === "auto") applyTema(effektivtTema(temaValg));
  }

  async function velgTemaAuto() {
    temaValg = await temaSett("auto", null);
    applyTema(effektivtTema(temaValg));
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
      // Last kladd og historikk for aktiv profil
      if (aktivProfil) {
        const entry = await versjonerLast(aktivProfil.id, id);
        kladd = entry?.kladd ?? null;
        historikk = entry?.historikk ?? [];
      } else {
        kladd = null;
        historikk = [];
      }
      redigerModus = false;
      sammenlignVersjon = null;
      lagreModalApen = false;
      lagreLabel = "";
    } catch (err) {
      console.error("hent_oppskrift failed:", err);
    } finally {
      loading = false;
    }
  }
  async function delOppskrift(opp: any) {
    const tekst = formaterOppskrift({
      navn: opp.navn,
      porsjoner: opp.porsjoner,
      ingredienser: opp.ingredienser,
      trinn: opp.trinn,
    });
    try {
      await navigator.clipboard.writeText(tekst);
      delKopiert = true;
      setTimeout(() => { delKopiert = false; }, 2000);
    } catch {
      alert("Kunne ikke kopiere — prøv å markere teksten manuelt");
    }
  }

  function lukkDetalj() {
    slåAvCookMode();
    currentOppskrift = null;
    portioner = null;
    redigerModus = false;
    kladd = null;
    historikk = [];
    sammenlignVersjon = null;
    lagreModalApen = false;
    lagreLabel = "";
    delKopiert = false;
    if (kladdTimer) { clearTimeout(kladdTimer); kladdTimer = null; }
  }

  function åpneRediger() {
    if (!currentOppskrift || !aktivProfil) return;
    if (!kladd) kladd = kopiFraOppskrift(currentOppskrift);
    redigerModus = true;
  }

  function avbrytRediger() {
    redigerModus = false;
    // Gjenopprett kladd fra store (ikke kast brukers lagrede kladd)
    if (currentOppskrift && aktivProfil) {
      versjonerLast(aktivProfil.id, currentOppskrift.id).then((entry) => {
        kladd = entry?.kladd ?? null;
      });
    }
  }

  async function lagreVersjon() {
    if (!currentOppskrift || !aktivProfil || !kladd) return;
    historikk = await versjon_lagre(aktivProfil.id, currentOppskrift.id, lagreLabel, kladd);
    kladd = null;  // kladd-innholdet er nå lagret som versjon; fjern indikator-dot
    lagreModalApen = false;
    lagreLabel = "";
    redigerModus = false;
  }

  async function slettVersjon(versjonId: string) {
    if (!currentOppskrift || !aktivProfil) return;
    historikk = await versjon_slett(aktivProfil.id, currentOppskrift.id, versjonId);
  }

  function gjenopprettVersjon(versjon: VersjonSnapshot) {
    if (!currentOppskrift || !aktivProfil) return;
    kladd = { ...versjon.kopi };
    sammenlignVersjon = null;
    redigerModus = true;
    // Kladd autolages via debounce ved neste oppdaterKladd-kall
    kladd_sett(aktivProfil.id, currentOppskrift.id, versjon.kopi).catch(console.error);
  }

  function fmtVersjonTid(iso: string): string {
    try {
      return new Intl.DateTimeFormat("nb-NO", {
        day: "numeric", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      }).format(new Date(iso));
    } catch {
      return iso;
    }
  }

  function oppdaterKladd(nyKopi: OppskriftKopi) {
    kladd = nyKopi;
    if (!currentOppskrift || !aktivProfil) return;
    const profilId = aktivProfil.id;
    const oppskriftId = currentOppskrift.id;
    if (kladdTimer) clearTimeout(kladdTimer);
    kladdTimer = setTimeout(() => {
      kladd_sett(profilId, oppskriftId, nyKopi).catch(console.error);
    }, 800);
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
      e: Math.round(n.energi / origP),
      p: Math.round((n.protein / origP) * 10) / 10,
      f: Math.round((n.fett / origP) * 10) / 10,
      k: Math.round((n.karbohydrat / origP) * 10) / 10,
      fi: n.fiber ? Math.round((n.fiber / origP) * 10) / 10 : null,
      treff: n.treff, totalt: n.totalt,
    };
  });

  let aktivtDagsbehov = $derived(aktivProfil ? dagsbehov(aktivProfil) : null);

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
    applyTema(effektivtTema(temaValg));

    // Lytt på OS-tema-endringer (f.eks. systemet bytter til mørkt om kvelden).
    // Bare aktuelt i auto-modus — manuell overstyring er uberørt.
    darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");
    darkModeQuery.addEventListener("change", onDarkModeChange);
    notater = await notaterLast();
    aktiveDietter = await diettLast();
    lager = await lagerLast();
    plan = await matplanLast();
    kategorier = await invoke("get_kategorier", { dietter: aktiveDietter });
    const sorterStore = await load("sorter.json");
    sorter = (await sorterStore.get<string>("sorter")) ?? "navn_asc";
    const planStore = await load("plan.json");
    planSesong = (await planStore.get<boolean>("sesong")) ?? false;
    await fetchGrid();
    profilStore = await profilLast();
    if (profilStore.aktivId) {
      const ap = profilStore.profiler.find(p => p.id === profilStore.aktivId);
      if (ap) planDagsmaal = tdee(ap);
    }
    try {
      aboutInfo = await invoke("about_info");
    } catch {
      // fengselsbygg — about ikke tilgjengelig
      aboutInfo = null;
    }
    aktivHoytid = await invoke<string | null>("hoytid_aktiv");
    const innstStore = await load("innstillinger.json");
    pynt = (await innstStore.get<boolean>("pynt")) ?? false;
    await lastForside();
    dagbokPoster = await loggLast();
    await oppdaterNæringMap(dagbokPoster);
  });

  onDestroy(() => {
    slåAvCookMode();
    if (timerTikk) clearInterval(timerTikk);
    darkModeQuery?.removeEventListener("change", onDarkModeChange);
  });
</script>

<svelte:window on:keydown={onKeydown} />

<aside id="sidebar">
  <div class="sidebar-logo">
    <span class="logo-icon">🍳</span>
    <span class="logo-text">Steike bra</span>
  </div>

  <div class="profil-velger">
    <button
      class="profil-velger-knapp"
      onclick={() => (profilDropdownÅpen = !profilDropdownÅpen)}
    >
      <span class="profil-initialer">
        {aktivProfil ? aktivProfil.navn.slice(0, 2).toUpperCase() : "?"}
      </span>
      <span class="profil-navn-tekst">
        {aktivProfil ? aktivProfil.navn : "Velg profil"}
      </span>
      <span class="profil-chevron">{profilDropdownÅpen ? "▲" : "▼"}</span>
    </button>
    {#if profilDropdownÅpen}
      <div class="profil-dropdown">
        {#each profilStore.profiler as p (p.id)}
          <button
            class="profil-dd-rad"
            class:aktiv={p.id === profilStore.aktivId}
            onclick={() => velgProfilAktiv(p.id)}
          >
            {p.navn} {p.id === profilStore.aktivId ? "✓" : ""}
          </button>
        {/each}
        {#if profilStore.profiler.length === 0}
          <span class="profil-dd-tom">Ingen profiler</span>
        {/if}
        <button class="profil-dd-admin" onclick={() => { profilDropdownÅpen = false; velgInnstillinger(); innstFane = "profil"; }}>
          Administrer profiler →
        </button>
      </div>
    {/if}
  </div>

  {#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__dagbok__"}
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
      class:active={currentKategori === "__plan__"}
      onclick={velgMatplan}
    >
      <span class="kat-emoji">📅</span>
      <span class="kat-navn">Matplan</span>
    </button>
    <button
      class="kat-btn"
      class:active={currentKategori === "__dagbok__"}
      onclick={velgDagbok}
    >
      <span class="kat-emoji">📖</span>
      <span class="kat-navn">Dagbok</span>
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
      {:else if currentKategori === "__plan__"}
        📅 Matplan
      {:else if currentKategori === "__dagbok__"}
        📖 Dagbok
      {:else if currentKategori === "__fav__"}
        ⭐ Favoritter
      {:else if currentKategori === "alle"}
        {sok ? `Søkeresultater for «${sok}»` : "Alle oppskrifter"}
      {:else}
        {currentKategori}
      {/if}
    </h1>
    {#if currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__dagbok__"}
    <span id="header-antall" class="count-badge">
      {#if currentKategori === "__handle__"}
        {handleliste.length} oppskrifter
      {:else}
        {total.toLocaleString("nb-NO")} oppskrifter
      {/if}
    </span>
    {/if}
    {#if aktiveDietter.length > 0 && currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__dagbok__"}
      <button class="diett-pille" onclick={() => (currentKategori = "__innst__")}>
        🍽️ {aktiveDietter.length} {aktiveDietter.length === 1 ? "filter" : "filtre"} aktive
      </button>
    {/if}
    {#if currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__handle__" && currentKategori !== "__fav__" && currentKategori !== "__dagbok__"}
      <select class="sorter-select" bind:value={sorter} onchange={onSorterChange}>
        <option value="navn_asc">Navn A–Å</option>
        <option value="navn_desc">Navn Å–A</option>
        <option value="tid_asc">Tid: kortest først</option>
        <option value="tid_desc">Tid: lengst først</option>
      </select>
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
      <div class="innst-faner">
        <button class:aktiv-fane={innstFane === "tema"} onclick={() => (innstFane = "tema")}>🎨 Temaer</button>
        <button class:aktiv-fane={innstFane === "diett"} onclick={() => (innstFane = "diett")}>🍽️ Kosthold</button>
        <button class:aktiv-fane={innstFane === "profil"} onclick={() => (innstFane = "profil")}>👤 Helseprofil</button>
      </div>
      {#if innstFane === "tema"}
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
        <label class="tema-valg pynt-toggle {!aktivHoytid ? 'deaktivert' : ''}">
          <input
            type="checkbox"
            checked={pynt}
            disabled={!aktivHoytid}
            onchange={() => { pynt = !pynt; onPyntChange(); }}
          />
          <span>Høytidspynt {aktivHoytid ? '' : '(ingen aktiv høytid)'}</span>
        </label>
      </details>
      {/if}
      {#if innstFane === "diett"}
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
      {/if}
      {#if innstFane === "profil"}
      <div class="profil-liste">
        <h2>Helseprofiler</h2>
        {#each profilStore.profiler as p (p.id)}
          <div class="profil-kort" class:aktiv-profil={p.id === profilStore.aktivId}>
            <div class="profil-kort-info">
              <strong>{p.navn}</strong>
              <span>{tdee(p)} kcal/dag {midjeOverGrenje(p) ? "🎯" : ""}</span>
              {#if p.id === profilStore.aktivId}<span class="aktiv-merke">● Aktiv</span>{/if}
            </div>
            <div class="profil-kort-knapper">
              {#if p.id !== profilStore.aktivId}
                <button onclick={() => velgProfilAktiv(p.id)}>Velg</button>
              {/if}
              <button onclick={() => startRedigerProfil(p)}>Rediger</button>
              <button onclick={() => slettProfil(p.id)}>Slett</button>
            </div>
          </div>
        {/each}
        {#if profilStore.profiler.length === 0}
          <p class="lager-tom">Ingen profiler opprettet ennå.</p>
        {/if}
        {#if !profilSkjemaÅpent}
          <button class="profil-ny-knapp" onclick={startNyProfil}>+ Ny profil</button>
        {:else}
          <div class="profil-skjema">
            <h3>{profilRedigerer ? "Rediger profil" : "Ny profil"}</h3>
            <label>Navn <input type="text" bind:value={profilFelt.navn} /></label>
            <label>Kjønn
              <select bind:value={profilFelt.kjønn}>
                <option value="mann">Mann</option>
                <option value="kvinne">Kvinne</option>
              </select>
            </label>
            <label>Alder (år) <input type="number" min="10" max="120" bind:value={profilFelt.alder} /></label>
            <label>Høyde (cm) <input type="number" min="100" max="250" bind:value={profilFelt.høyde} /></label>
            <label>Vekt (kg) <input type="number" min="30" max="300" step="0.5" bind:value={profilFelt.vekt} /></label>
            <label>Midjemål (cm) — valgfritt
              <input type="number" min="50" max="200"
                bind:value={profilFelt.midje}
                placeholder="f.eks. 88" />
            </label>
            {#if profilFelt.midje}
              <label class="midjefilter-label">
                <input type="checkbox" bind:checked={profilFelt.midjeFilter} />
                Filtrer matplan mot sunnere oppskrifter
              </label>
              {#if !midjeOverGrenjeFelt}
                <p class="midjefilter-info">
                  Midjemålet er innenfor normalområdet — filteret er ikke aktivt.
                </p>
              {/if}
            {/if}
            <label>Aktivitetsnivå
              <select bind:value={profilFelt.aktivitet}>
                <option value="stillesittende">Stillesittende (lite/ingen trening)</option>
                <option value="lett">Lett aktiv (1–3 dager/uke)</option>
                <option value="moderat">Moderat aktiv (3–5 dager/uke)</option>
                <option value="aktiv">Aktiv (6–7 dager/uke)</option>
                <option value="veldig_aktiv">Veldig aktiv (hard trening + fysisk jobb)</option>
              </select>
            </label>
            <label>Mål
              <select bind:value={profilFelt.mål}>
                <option value="nedgang">Vektnedgang (−500 kcal)</option>
                <option value="vedlikehold">Vedlikehold</option>
                <option value="oppgang">Vektøkning (+500 kcal)</option>
              </select>
            </label>
            <div class="profil-skjema-knapper">
              <button onclick={lagreProfil}>Lagre</button>
              <button onclick={() => (profilSkjemaÅpent = false)}>Avbryt</button>
            </div>
          </div>
        {/if}
      </div>

      {#if aboutInfo}
        <div class="about-seksjon">
          <hr />
          <div class="about-tittel">Om appen · v{aboutInfo.versjon}</div>
          <p class="about-tekst">{aboutInfo.beskrivelse}</p>
          <div class="about-kontakt">{aboutInfo.navn} · {aboutInfo.epost}</div>
        </div>
      {/if}
      {/if}
    </div>
  {/if}

  {#if currentKategori === "__lager__"}
    <div id="lager-wrap">
      <section class="lager-rediger">
        <h2>Mitt kjøleskap</h2>
        <p class="innst-hint">Legg til varer du har, så foreslår vi oppskrifter under.</p>
        <div class="lager-input-rad">
          <div class="lager-auto">
            <input
              class="lager-input"
              placeholder="Legg til vare (f.eks. kyllingfilet)…"
              value={nyVareNavn}
              oninput={onNyVareInput}
              onkeydown={(e) => { if (e.key === "Enter") leggTilVare(); }}
            />
            {#if autoForslag.length > 0}
              <ul class="lager-auto-liste">
                {#each autoForslag as f}
                  <li><button type="button" onclick={() => leggTilVare(f)}>{f}</button></li>
                {/each}
              </ul>
            {/if}
          </div>
          <input class="lager-dato" type="date" bind:value={nyVareUtloper} title="Utløpsdato (valgfritt)" />
          <button class="lager-legg" onclick={() => leggTilVare()}>Legg til</button>
        </div>
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
        {#if lager.length === 0}
          <p class="lager-tom">Legg til varer over for å se forslag.</p>
        {:else if lagerForslag.length === 0}
          <p class="lager-tom">Ingen treff på det du har registrert.</p>
        {:else}
          {#each [...new Set(lagerForslag.map((f) => f.totalt - f.dekket))].sort((a, b) => a - b) as mangelN}
            <div class="forslag-gruppe-tittel">
              {mangelN === 0 ? "✅ Kan lages nå" : `Mangler ${mangelN}`}
            </div>
            {#each lagerForslag.filter((f) => f.totalt - f.dekket === mangelN) as f (f.id)}
              <button class="forslag-rad" onclick={() => åpneOppskrift(f.id)}>
                {#if imgSrc(f.id)}<img src={imgSrc(f.id)} alt={f.navn} loading="lazy" />{/if}
                <span class="forslag-navn">{f.navn}</span>
                {#if f.mangler.length > 0}
                  <span class="forslag-mangler">mangler: {f.mangler.slice(0, 4).join(", ")}{f.mangler.length > 4 ? "…" : ""}</span>
                {/if}
              </button>
            {/each}
          {/each}
        {/if}
      </section>
    </div>
  {/if}

  {#if currentKategori === "__plan__"}
    <div id="plan-wrap">
      <div class="plan-kontroll">
        <label>Dagsmål (kcal)
          <input type="number" min="800" max="5000" step="50" bind:value={planDagsmaal} />
        </label>
        <label>Personer
          <input type="number" min="1" max="12" step="1" bind:value={planPersoner} />
        </label>
        {#if aktiveDietter.length > 0}
          <span class="plan-filter-merke">🍽️ {aktiveDietter.length} filtre aktive</span>
        {/if}
        <label class="plan-toggle {!aktivHoytid ? 'deaktivert' : ''}">
          <input type="checkbox" bind:checked={planSesong}
                 disabled={!aktivHoytid}
                 onchange={onPlanSesongChange} />
          Sesongmeny
        </label>
        <button class="plan-generer" onclick={genererPlan} disabled={planLaster}>
          {planLaster ? "Genererer…" : "↻ Generer"}
        </button>
      </div>

      {#if !plan}
        <p class="lager-tom">Sett dagsmål og personer, og trykk «Generer».</p>
      {:else}
        <table class="plan-tabell">
          <thead>
            <tr>
              <th></th><th>🍳 Frokost</th><th>🥪 Lunsj</th><th>🍽️ Middag</th><th>🌙 Kveldsmat</th><th>kcal/dag</th>
            </tr>
          </thead>
          <tbody>
            {#each plan.dager as d, dag (dag)}
              {@const dagnavn = ["Man","Tir","Ons","Tor","Fre","Lør","Søn"][dag]}
              {@const avvik = d.kcalDag != null ? Math.abs(d.kcalDag - plan.dagsmaal) / plan.dagsmaal : null}
              <tr>
                <td class="plan-dag">{dagnavn}</td>
                {#each ["frokost","lunsj","middag","kveldsmat"] as slot (slot)}
                  {@const s = (d as any)[slot]}
                  <td class="plan-celle">
                    {#if s.kind === "rett"}
                      <button class="plan-rett" onclick={() => åpneOppskrift(s.id)}>{s.navn}</button>
                      <button class="plan-ikon" class:laast={s.laast} title="Lås/lås opp" onclick={() => toggleLaas(dag, slot)}>{s.laast ? "🔒" : "🔓"}</button>
                    {:else if s.kind === "rester"}
                      <span class="plan-rester">{s.visTekst}</span>
                    {:else if s.kind === "enkel"}
                      <span class="plan-enkel">{s.visTekst}</span>
                    {:else}
                      <span class="plan-tom-celle">{s.grunn}</span>
                    {/if}
                  </td>
                {/each}
                <td class="plan-kcal" class:naer={avvik != null && avvik <= 0.15} class:unna={avvik != null && avvik > 0.15}>
                  {d.kcalDag != null ? `~${Math.round(d.kcalDag)}` : "?"}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
        <div class="plan-knapper">
          <button class="plan-generer" onclick={genererPlan} disabled={planLaster}>↻ Generer ulåste på nytt</button>
          <button class="plan-handle" onclick={sendUkaTilHandleliste}>🛒 Send uka til handleliste</button>
          <button class="plan-lagre" onclick={lagreUka}>💾 Lagre uka</button>
        </div>
      {/if}
    </div>
  {/if}

  {#if currentKategori === "__dagbok__"}
    <div class="dagbok-visning">
      <div class="dagbok-tabs">
        {#each (['dag','uke','måned'] as const) as t}
          <button class:aktiv={dagbokTab===t} onclick={() => dagbokTab=t}>{t.charAt(0).toUpperCase()+t.slice(1)}</button>
        {/each}
      </div>

      {#if dagbokTab === 'dag'}
        <input type="date" bind:value={dagbokValgtDato} />
        {@const dagPoster = loggForDato(dagbokPoster, dagbokValgtDato)}
        {@const sum = loggSumNæring(dagPoster, næringMap)}
        {@const behov = aktivProfil ? dagsbehov(aktivProfil).kcal : null}

        {#each (['frokost','lunsj','middag','kveldsmat','annet'] as const) as tid}
          {@const seksPoster = dagPoster.filter(p => p.tidspunkt === tid)}
          <div class="dagbok-seksjon">
            <h3>{tid.charAt(0).toUpperCase() + tid.slice(1)}</h3>
            {#if seksPoster.length === 0}
              <p class="ingen">Ingen poster</p>
            {:else}
              {#each seksPoster as p}
                <div class="dagbok-post">
                  <span>
                    {#if p.type === 'oppskrift'}
                      {#await invoke('hent_oppskrift', { id: p.oppskriftId }) then o}
                        {(o as any)?.navn ?? 'Ukjent oppskrift'} × {p.porsjoner}
                      {/await}
                    {:else}
                      {p.beskrivelse}
                    {/if}
                  </span>
                  <span class="kcal">
                    {#if p.type === 'fri'}{p.kcal} kcal
                    {:else}{((næringMap[p.oppskriftId]?.kcal ?? 0) * p.porsjoner).toFixed(0)} kcal
                    {/if}
                  </span>
                  <button class="slett-knapp" onclick={async () => {
                    dagbokPoster = await loggFjern(p.id);
                  }}>×</button>
                </div>
              {/each}
            {/if}
          </div>
        {/each}

        <div class="dagbok-sum">
          <strong>Totalt: {sum.kcal.toFixed(0)} kcal</strong>
          | Protein: {sum.protein.toFixed(0)}g
          | Fett: {sum.fett.toFixed(0)}g
          | Karbo: {sum.karbo.toFixed(0)}g
          {#if behov}
            {@const pst = Math.round(sum.kcal / behov * 100)}
            <div class="fremgangsbar-wrap">
              <div class="fremgangsbar"
                style="width:{Math.min(pst,100)}%;background:{pst<100?'var(--farge-ok,green)':pst<=120?'var(--farge-advarsel,orange)':'var(--farge-feil,red)'}">
              </div>
            </div>
            <span>{pst}% av dagsbehov ({behov} kcal)</span>
          {/if}
        </div>
      {/if}

      {#if dagbokTab === 'uke' || dagbokTab === 'måned'}
        {@const dager = dagbokTab === 'uke' ? 7 : 30}
        {@const data = loggKcalPerDag(dagbokPoster, næringMap, dager)}
        {@const behovKcal = aktivProfil ? dagsbehov(aktivProfil).kcal : 0}
        {@const maxKcal = Math.max(...data.map(d => d.kcal), behovKcal, 100)}
        {@const snitt = dagbokTab === 'måned' ? Math.round(data.reduce((s,d)=>s+d.kcal,0)/dager) : null}
        <svg viewBox="0 0 {dager*24} 160" class="kcal-graf">
          {#each data as d, i}
            {@const h = Math.round((d.kcal / maxKcal) * 130)}
            <rect x={i*24+2} y={160-h} width="20" height={h}
              fill="var(--farge-primær, #b5651d)"
              onclick={() => { dagbokTab = 'dag'; dagbokValgtDato = d.dato; }}
              style="cursor:pointer" />
            <title>{d.dato}: {d.kcal} kcal</title>
          {/each}
          {#if aktivProfil}
            {@const behovY = 160 - Math.round((dagsbehov(aktivProfil).kcal / maxKcal) * 130)}
            <line x1="0" y1={behovY} x2={dager*24} y2={behovY}
              stroke="var(--farge-tekst,#333)" stroke-dasharray="4 4" stroke-width="1" />
          {/if}
        </svg>
        {#if snitt != null}<p>Snitt: {snitt} kcal/dag</p>{/if}
      {/if}

      <button class="logg-fab" onclick={() => loggModalApen = true}>+</button>
    </div>
  {/if}

  {#if currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__dagbok__"}
  <div id="grid-wrap">
    {#if currentKategori === "alle" && !sok && forsideOppskrifter.length > 0}
      <div class="forside-wrap">
        <div class="forside-header" style="position:relative;">
          <h2 class="forside-tittel">{forsideTittel}</h2>
          {#if !aktivHoytid}
            <p class="forside-undertekst">Forslag til deg akkurat nå</p>
          {/if}
          {#if pynt && aktivHoytid}
            <Hoytidspynt hoytid={aktivHoytid} />
          {/if}
        </div>
        <div class="forside-grid">
          {#each forsideOppskrifter as o (o.id)}
            <article class="recipe-card" onclick={() => åpneOppskrift(o.id)}>
              <div class="card-img-wrap">
                {#if imgSrc(o.id)}
                  <img src={imgSrc(o.id)} alt={o.navn} loading="lazy" />
                {:else}
                  <div class="card-img-placeholder">🍽️</div>
                {/if}
                {#if o.tid}<div class="card-badge-time">⏱ {o.tid}</div>{/if}
              </div>
              <div class="card-body">
                <div class="card-name">{o.navn}</div>
              </div>
            </article>
          {/each}
        </div>
        <hr class="forside-skille" />
      </div>
    {/if}
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

    {#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && currentKategori !== "__innst__" && currentKategori !== "__lager__" && currentKategori !== "__plan__" && currentKategori !== "__dagbok__" && pages > 1}
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

  {#if loggModalApen}
    <div class="modal-bakgrunn" role="presentation" onclick={() => loggModalApen = false}>
      <div class="logg-modal" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()}>
        <div class="modal-tittel">Logg måltid</div>

        <label>Tidspunkt
          <select bind:value={loggTidspunkt}>
            {#each (['frokost','lunsj','middag','kveldsmat','annet'] as const) as t}
              <option value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
            {/each}
          </select>
        </label>

        <div class="modal-tabs">
          <button class:aktiv={loggModalTab==='oppskrift'} onclick={() => loggModalTab='oppskrift'}>Fra oppskrift</button>
          <button class:aktiv={loggModalTab==='fri'} onclick={() => loggModalTab='fri'}>Fri innføring</button>
        </div>

        {#if loggModalTab === 'oppskrift'}
          <input type="search" placeholder="Søk oppskrift..." bind:value={loggSøk}
            oninput={async () => {
              if (loggSøk.length < 2) { loggSøkResultater = []; return; }
              const res = await invoke<any>("hent_oppskrifter", {
                kategori: null, sok: loggSøk, side: 1, perSide: 8, dietter: [], sorter: "navn_asc"
              });
              loggSøkResultater = res?.oppskrifter ?? [];
            }} />
          {#if loggValgtOppskrift}
            <div class="logg-valgt">
              <strong>{loggValgtOppskrift.navn}</strong>
              <div class="porsjon-kontroll">
                <button onclick={() => loggPorsjoner = Math.max(1, loggPorsjoner - 1)}>−</button>
                <span>{loggPorsjoner} porsjon{loggPorsjoner !== 1 ? 'er' : ''}</span>
                <button onclick={() => loggPorsjoner++}>+</button>
              </div>
            </div>
          {:else}
            <ul class="logg-søk-liste">
              {#each loggSøkResultater.slice(0, 8) as r}
                <li onclick={() => { loggValgtOppskrift = r; loggSøk = r.navn; loggSøkResultater = []; }}>
                  {r.navn}
                </li>
              {/each}
            </ul>
          {/if}
        {:else}
          <input type="text" placeholder="Beskrivelse (f.eks. 2 egg, stekt)" bind:value={loggFriBesk} />
          <input type="number" placeholder="kcal (påkrevd)" bind:value={loggFriKcal} min="0" />
          <input type="number" placeholder="Protein (g, valgfritt)" bind:value={loggFriProtein} min="0" />
          <input type="number" placeholder="Fett (g, valgfritt)" bind:value={loggFriFett} min="0" />
          <input type="number" placeholder="Karbohydrat (g, valgfritt)" bind:value={loggFriKarbo} min="0" />
        {/if}

        <div class="modal-knapper">
          <button onclick={() => loggModalApen = false}>Avbryt</button>
          <button class="primær" onclick={async () => {
            const dato = dagbokValgtDato;
            let nyPost: Loggpost;
            if (loggModalTab === 'oppskrift' && loggValgtOppskrift) {
              nyPost = { id: crypto.randomUUID(), dato, tidspunkt: loggTidspunkt,
                type: 'oppskrift', oppskriftId: loggValgtOppskrift.id, porsjoner: loggPorsjoner };
            } else if (loggModalTab === 'fri' && loggFriKcal != null && loggFriBesk.trim()) {
              nyPost = { id: crypto.randomUUID(), dato, tidspunkt: loggTidspunkt,
                type: 'fri', beskrivelse: loggFriBesk.trim(),
                kcal: loggFriKcal, protein: loggFriProtein ?? 0,
                fett: loggFriFett ?? 0, karbo: loggFriKarbo ?? 0 };
            } else return;
            dagbokPoster = await loggLeggTil(nyPost);
            await oppdaterNæringMap(dagbokPoster);
            loggModalApen = false;
            loggValgtOppskrift = null; loggSøk = ""; loggPorsjoner = 1;
            loggFriBesk = ""; loggFriKcal = null; loggFriProtein = null; loggFriFett = null; loggFriKarbo = null;
          }}>Logg</button>
        </div>
      </div>
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
        {#if aktivProfil}
          {#if redigerModus}
            <button class="detail-rediger" onclick={avbrytRediger}>← Avbryt</button>
            <button class="detail-rediger aktiv" onclick={() => lagreModalApen = true}>💾 Lagre versjon</button>
          {:else}
            <button
              class="detail-rediger"
              class:har-kladd={kladd !== null}
              onclick={åpneRediger}
              title={kladd !== null ? "Du har en redigert versjon" : "Rediger din kopi"}
            >✏️ Rediger{kladd !== null ? " ●" : ""}</button>
          {/if}
        {/if}
        <button
          class="detail-fav"
          class:aktiv={favoritter.has(opp.id)}
          title={favoritter.has(opp.id) ? "Fjern favoritt" : "Legg til favoritt"}
          onclick={() => toggleFavoritt(opp.id)}
        >{favoritter.has(opp.id) ? "⭐ Favoritt" : "☆ Favoritt"}</button>
        {#if !erFengsel}
          <button class="del-knapp" onclick={() => delOppskrift(opp)}>
            {delKopiert ? '✓ Kopiert!' : '📋 Del'}
          </button>
        {/if}
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
        {#if lager.length > 0}
          <button class="detail-handle" title="Fjern matchede varer fra kjøleskapet" onclick={() => lagdeDenne(opp)}>
            ✓ Lagde denne
          </button>
        {/if}
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

        {#if redigerModus && kladd}
          {@const k = kladd}
          <div class="rediger-meta">
            <label class="rediger-label">Navn
              <input class="rediger-input" type="text" value={k.navn}
                oninput={(e) => oppdaterKladd({ ...k, navn: (e.target as HTMLInputElement).value })} />
            </label>
            <label class="rediger-label">Beskrivelse
              <textarea class="rediger-textarea" value={k.beskrivelse ?? ""}
                oninput={(e) => oppdaterKladd({ ...k, beskrivelse: (e.target as HTMLTextAreaElement).value || null })}></textarea>
            </label>
            <div class="rediger-rad">
              <label class="rediger-label">Porsjoner
                <input class="rediger-input rediger-input-sm" type="number" min="1" value={k.porsjoner ?? ""}
                  oninput={(e) => oppdaterKladd({ ...k, porsjoner: parseInt((e.target as HTMLInputElement).value) || null })} />
              </label>
              <label class="rediger-label">Tid
                <input class="rediger-input rediger-input-sm" type="text" value={k.tid ?? ""}
                  oninput={(e) => oppdaterKladd({ ...k, tid: (e.target as HTMLInputElement).value || null })} />
              </label>
            </div>
          </div>

          <div class="detail-columns">
            <div>
              <div class="detail-section-title">Ingredienser</div>
              {#each k.ingredienser as ing, idx}
                <div class="rediger-ing-rad">
                  <input class="rediger-input rediger-input-mengde" type="number" placeholder="mengde"
                    value={ing.mengde ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, mengde: parseFloat((e.target as HTMLInputElement).value) || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <input class="rediger-input rediger-input-enhet" type="text" placeholder="enhet"
                    value={ing.enhet ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, enhet: (e.target as HTMLInputElement).value || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <input class="rediger-input rediger-input-navn" type="text" placeholder="ingrediens"
                    value={ing.navn ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, navn: (e.target as HTMLInputElement).value || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <button class="rediger-slett" title="Slett ingrediens"
                    onclick={() => {
                      const nyIng = k.ingredienser.filter((_, i) => i !== idx);
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }}>🗑</button>
                </div>
              {/each}
              <button class="rediger-legg-til" onclick={() => {
                const nyIng: KopiIngrediens = { gruppe: null, mengde: null, enhet: null, navn: null, sortering: k.ingredienser.length };
                oppdaterKladd({ ...k, ingredienser: [...k.ingredienser, nyIng] });
              }}>＋ Legg til ingrediens</button>
            </div>

            <div>
              <div class="detail-section-title">Fremgangsmåte</div>
              {#each k.trinn as trinn, idx}
                <div class="rediger-trinn-rad">
                  <div class="rediger-trinn-nr">{idx + 1}</div>
                  <textarea class="rediger-textarea rediger-trinn-tekst" value={trinn.tekst}
                    oninput={(e) => {
                      const nyTrinn = [...k.trinn];
                      nyTrinn[idx] = { ...trinn, tekst: (e.target as HTMLTextAreaElement).value };
                      oppdaterKladd({ ...k, trinn: nyTrinn });
                    }}></textarea>
                  <div class="rediger-trinn-knapper">
                    <button class="rediger-pil" disabled={idx === 0} title="Flytt opp"
                      onclick={() => {
                        const t = [...k.trinn];
                        [t[idx - 1], t[idx]] = [t[idx], t[idx - 1]];
                        oppdaterKladd({ ...k, trinn: t.map((x, i) => ({ ...x, nummer: i + 1 })) });
                      }}>↑</button>
                    <button class="rediger-pil" disabled={idx === k.trinn.length - 1} title="Flytt ned"
                      onclick={() => {
                        const t = [...k.trinn];
                        [t[idx], t[idx + 1]] = [t[idx + 1], t[idx]];
                        oppdaterKladd({ ...k, trinn: t.map((x, i) => ({ ...x, nummer: i + 1 })) });
                      }}>↓</button>
                    <button class="rediger-slett" title="Slett trinn"
                      onclick={() => {
                        const nyTrinn = k.trinn.filter((_, i) => i !== idx).map((x, i) => ({ ...x, nummer: i + 1 }));
                        oppdaterKladd({ ...k, trinn: nyTrinn });
                      }}>🗑</button>
                  </div>
                </div>
              {/each}
              <button class="rediger-legg-til" onclick={() => {
                const nyTrinn: KopiTrinn = { nummer: k.trinn.length + 1, tekst: "" };
                oppdaterKladd({ ...k, trinn: [...k.trinn, nyTrinn] });
              }}>＋ Legg til trinn</button>
            </div>
          </div>
        {:else}
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
        {/if}

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
        {#if naeringPerPorsjon && aktivtDagsbehov}
          {@const n = naeringPerPorsjon}
          {@const db = aktivtDagsbehov}
          <div class="dagsbehov-wrap">
            <div class="dagsbehov-title">📈 Andel av dagsbehov – per porsjon</div>
            <div class="dagsbehov-grid">
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.e, db.kcal)}%</span>
                <span class="dagsbehov-lbl">🔥 Energi</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.p, db.protein)}%</span>
                <span class="dagsbehov-lbl">🥩 Protein</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.f, db.fett)}%</span>
                <span class="dagsbehov-lbl">🫙 Fett</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.k, db.karbo)}%</span>
                <span class="dagsbehov-lbl">🌾 Karbo</span>
              </div>
            </div>
            <div class="dagsbehov-profil">
              Basert på profil: {aktivProfil!.navn} · {db.kcal} kcal/dag
            </div>
          </div>
        {/if}
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
        {#if historikk.length > 0}
          <section class="versjon-historikk">
            <div class="versjon-historikk-tittel">📋 Versjonshistorikk ({historikk.length})</div>
            {#each historikk as v (v.id)}
              <div class="versjon-rad">
                <div class="versjon-rad-info">
                  <span class="versjon-tidspunkt">{fmtVersjonTid(v.lagretTidspunkt)}</span>
                  {#if v.label}
                    <span class="versjon-label">{v.label}</span>
                  {:else}
                    <span class="versjon-label ingen">Ingen beskrivelse</span>
                  {/if}
                </div>
                <div class="versjon-rad-knapper">
                  <button class="versjon-btn" onclick={() => sammenlignVersjon = v}>Sammenlign</button>
                  <button class="versjon-btn" onclick={() => gjenopprettVersjon(v)}>Gjenopprett</button>
                  <button class="versjon-btn versjon-btn-slett" onclick={() => slettVersjon(v.id)}>Slett</button>
                </div>
              </div>
            {/each}
          </section>
        {/if}
      </div>
      {#if lagreModalApen}
        <div class="lagre-modal-bakgrunn" role="presentation" onclick={() => lagreModalApen = false}>
          <div class="lagre-modal" role="dialog" onclick={(e) => e.stopPropagation()}>
            <div class="lagre-modal-tittel">💾 Lagre versjon</div>
            <input
              class="rediger-input"
              type="text"
              placeholder="Beskrivelse (valgfri), f.eks. «Med gresskar»"
              bind:value={lagreLabel}
              onkeydown={(e) => { if (e.key === "Enter") lagreVersjon(); }}
            />
            <div class="lagre-modal-knapper">
              <button class="lagre-modal-btn" onclick={lagreVersjon}>Lagre</button>
              <button class="lagre-modal-btn lagre-modal-avbryt" onclick={() => lagreModalApen = false}>Avbryt</button>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if sammenlignVersjon && currentOppskrift}
  {@const origKopi = kopiFraOppskrift(currentOppskrift)}
  {@const diff = beregnDiff(origKopi, sammenlignVersjon.kopi)}
  <div
    id="sammenlign-overlay"
    role="presentation"
    onclick={(e) => { if (e.target === e.currentTarget) sammenlignVersjon = null; }}
  >
    <div id="sammenlign-panel">
      <div class="sammenlign-topbar">
        <span class="sammenlign-tittel">📊 Sammenlign: {sammenlignVersjon.label || fmtVersjonTid(sammenlignVersjon.lagretTidspunkt)}</span>
        <button class="sammenlign-lukk" onclick={() => sammenlignVersjon = null}>✕ Lukk</button>
        <button class="sammenlign-bruk" onclick={() => gjenopprettVersjon(sammenlignVersjon!)}>Bruk denne versjonen</button>
      </div>

      <div class="sammenlign-body">
        <!-- Metadata -->
        {#if diff.navn.endret || diff.beskrivelse.endret || diff.porsjoner.endret || diff.tid.endret}
          <div class="sammenlign-seksjon-tittel">Metadata</div>
          <div class="sammenlign-meta-grid">
            {#if diff.navn.endret}
              <div class="sammenlign-meta-felt">Navn</div>
              <div class="sammenlign-orig">{diff.navn.orig}</div>
              <div class="sammenlign-versjon">{diff.navn.versjon}</div>
            {/if}
            {#if diff.beskrivelse.endret}
              <div class="sammenlign-meta-felt">Beskrivelse</div>
              <div class="sammenlign-orig">{diff.beskrivelse.orig ?? "–"}</div>
              <div class="sammenlign-versjon">{diff.beskrivelse.versjon ?? "–"}</div>
            {/if}
            {#if diff.porsjoner.endret}
              <div class="sammenlign-meta-felt">Porsjoner</div>
              <div class="sammenlign-orig">{diff.porsjoner.orig ?? "–"}</div>
              <div class="sammenlign-versjon">{diff.porsjoner.versjon ?? "–"}</div>
            {/if}
            {#if diff.tid.endret}
              <div class="sammenlign-meta-felt">Tid</div>
              <div class="sammenlign-orig">{diff.tid.orig ?? "–"}</div>
              <div class="sammenlign-versjon">{diff.tid.versjon ?? "–"}</div>
            {/if}
          </div>
        {/if}

        <!-- Ingredienser -->
        <div class="sammenlign-seksjon-tittel">Ingredienser</div>
        <div class="sammenlign-tabell-hdr">
          <div>Original</div><div>Din versjon</div>
        </div>
        {#each diff.ingredienser as d}
          <div
            class="sammenlign-rad"
            class:endret={d.endret && d.orig !== null && d.versjon !== null}
            class:ny={d.orig === null}
            class:slettet={d.versjon === null}
          >
            <div class="sammenlign-celle">
              {#if d.orig}
                {d.orig.mengde ?? ""} {d.orig.enhet ?? ""} {d.orig.navn ?? ""}
              {:else}
                <span class="sammenlign-tom">–</span>
              {/if}
            </div>
            <div class="sammenlign-celle">
              {#if d.versjon}
                {d.versjon.mengde ?? ""} {d.versjon.enhet ?? ""} {d.versjon.navn ?? ""}
              {:else}
                <span class="sammenlign-tom">–</span>
              {/if}
            </div>
          </div>
        {/each}

        <!-- Trinn -->
        <div class="sammenlign-seksjon-tittel">Fremgangsmåte</div>
        <div class="sammenlign-tabell-hdr">
          <div>Original</div><div>Din versjon</div>
        </div>
        {#each diff.trinn as d, i}
          <div
            class="sammenlign-rad"
            class:endret={d.endret && d.orig !== null && d.versjon !== null}
            class:ny={d.orig === null}
            class:slettet={d.versjon === null}
          >
            <div class="sammenlign-celle sammenlign-celle-trinn">
              {#if d.orig}<span class="sammenlign-trinn-nr">{i + 1}.</span> {d.orig.tekst}{:else}<span class="sammenlign-tom">–</span>{/if}
            </div>
            <div class="sammenlign-celle sammenlign-celle-trinn">
              {#if d.versjon}<span class="sammenlign-trinn-nr">{i + 1}.</span> {d.versjon.tekst}{:else}<span class="sammenlign-tom">–</span>{/if}
            </div>
          </div>
        {/each}
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
  .del-knapp {
    padding: 0.4rem 0.8rem;
    border-radius: var(--radius);
    border: 1px solid var(--farge-kant, #ddd);
    background: var(--bg-warm);
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.2s;
  }
  .del-knapp:hover {
    background: var(--farge-kant, #eee);
  }
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
  .sorter-select {
    margin-left: auto;
    font-size: 0.82rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 8px; cursor: pointer; outline: none;
  }
  .sorter-select:focus { border-color: var(--border-focus); }
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
  .lager-input-rad { display: flex; gap: 8px; margin-bottom: 14px; align-items: flex-start; }
  .lager-auto { position: relative; flex: 1; }
  .lager-input { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); font-family: var(--font-ui); }
  .lager-auto-liste {
    position: absolute; top: 100%; left: 0; right: 0; z-index: 20; list-style: none;
    margin: 2px 0 0; padding: 4px; background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: var(--shadow); max-height: 240px; overflow-y: auto;
  }
  .lager-auto-liste button { display: block; width: 100%; text-align: left; border: none; background: none; padding: 6px 8px; cursor: pointer; color: var(--text); border-radius: 4px; }
  .lager-auto-liste button:hover { background: var(--card-hover); }
  .lager-dato { padding: 8px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); }
  .lager-legg { border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: var(--radius); padding: 8px 14px; cursor: pointer; }
  #plan-wrap { flex: 1; overflow-y: auto; padding: 24px 32px; }
  .plan-kontroll { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 18px; }
  .plan-kontroll label { display: flex; flex-direction: column; font-size: 0.82rem; gap: 4px; color: var(--text-muted); }
  .plan-kontroll input { padding: 6px 10px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); width: 110px; }
  .plan-filter-merke { font-size: 0.82rem; color: var(--text-muted); align-self: center; }
  .plan-generer, .plan-handle, .plan-lagre { border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: var(--radius); padding: 8px 14px; cursor: pointer; }
  .plan-handle, .plan-lagre { background: var(--surface); color: var(--text); border-color: var(--border); }
  .plan-generer:disabled { opacity: 0.6; cursor: default; }
  .plan-tabell { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
  .plan-tabell th { text-align: left; padding: 8px; border-bottom: 2px solid var(--border); }
  .plan-celle { border: 1px solid var(--border); padding: 6px 8px; vertical-align: top; }
  .plan-dag { font-weight: 700; padding: 6px 8px; }
  .plan-rett { border: none; background: none; color: var(--text); cursor: pointer; text-align: left; padding: 0; font: inherit; text-decoration: underline; text-decoration-color: var(--border); }
  .plan-rett:hover { text-decoration-color: var(--accent); }
  .plan-ikon { border: none; background: none; cursor: pointer; font-size: 0.9rem; }
  .plan-rester, .plan-enkel { color: var(--text-muted); font-style: italic; }
  .plan-tom-celle { color: #c0392b; font-size: 0.8rem; }
  .plan-kcal { text-align: right; padding: 6px 8px; font-variant-numeric: tabular-nums; }
  .plan-kcal.naer { color: #2a8a4a; }
  .plan-kcal.unna { color: #d8821a; }
  .plan-knapper { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
  .forslag-gruppe-tittel { font-weight: 700; margin: 16px 0 8px; color: var(--text); }
  .forslag-rad {
    display: flex; align-items: center; gap: 12px; width: 100%; text-align: left;
    border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
    padding: 8px 12px; margin-bottom: 6px; cursor: pointer;
  }
  .forslag-rad:hover { border-color: var(--border-focus); }
  .forslag-rad img { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; }
  .forslag-navn { flex: 1; font-weight: 600; color: var(--text); }
  .forslag-mangler { font-size: 0.8rem; color: var(--text-muted); }
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

  .dagsbehov-wrap {
    margin-top: 14px; padding: 14px 16px; background: var(--bg-warm);
    border: 1px solid var(--border); border-radius: var(--radius);
  }
  .dagsbehov-title {
    font-family: var(--font-head); font-size: 0.95rem; font-weight: 700; color: var(--text);
    margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid var(--accent); display: inline-block;
  }
  .dagsbehov-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .dagsbehov-kort {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--radius-sm);
    padding: 10px 6px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 4px;
  }
  .dagsbehov-pst {
    font-family: var(--font-head); font-size: 1.2rem; font-weight: 700; color: var(--accent-dark); line-height: 1;
  }
  .dagsbehov-lbl { font-size: 0.7rem; color: var(--text-muted); }
  .dagsbehov-profil { margin-top: 10px; font-size: 0.72rem; color: var(--text-dim); text-align: center; font-style: italic; }

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

  /* ── Profilvelger ─────────────────────────────────────────── */
  .profil-velger {
    position: relative;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  .profil-velger-knapp {
    display: flex; align-items: center; gap: 8px;
    width: 100%; background: none; border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; cursor: pointer;
    color: var(--text); font-size: 0.85rem;
  }
  .profil-velger-knapp:hover { background: var(--card-hover); }
  .profil-initialer {
    width: 24px; height: 24px; border-radius: 50%;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 700; flex-shrink: 0;
  }
  .profil-navn-tekst { flex: 1; text-align: left; }
  .profil-chevron { font-size: 0.65rem; color: var(--text-muted); }
  .profil-dropdown {
    position: absolute; top: 100%; left: 12px; right: 12px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.15);
    z-index: 100; display: flex; flex-direction: column;
  }
  .profil-dd-rad {
    padding: 8px 12px; text-align: left; background: none;
    border: none; cursor: pointer; color: var(--text); font-size: 0.85rem;
  }
  .profil-dd-rad:hover, .profil-dd-rad.aktiv { background: var(--card-hover); }
  .profil-dd-tom { padding: 8px 12px; color: var(--text-muted); font-size: 0.8rem; }
  .profil-dd-admin {
    padding: 8px 12px; text-align: left; background: none;
    border-top: 1px solid var(--border); border-left: none;
    border-right: none; border-bottom: none;
    cursor: pointer; color: var(--accent); font-size: 0.8rem;
  }
  .profil-dd-admin:hover { text-decoration: underline; }

  /* ── Innstillinger-faner ──────────────────────────────────── */
  .innst-faner {
    display: flex; gap: 4px; margin-bottom: 20px;
    border-bottom: 1px solid var(--border); padding-bottom: 8px;
  }
  .innst-faner button {
    padding: 6px 14px; border: 1px solid var(--border);
    border-radius: 6px 6px 0 0; background: none;
    cursor: pointer; color: var(--text); font-size: 0.85rem;
  }
  .innst-faner button.aktiv-fane {
    background: var(--accent); color: #fff; border-color: var(--accent);
  }

  /* ── Helseprofil-liste og skjema ─────────────────────────── */
  .profil-liste { display: flex; flex-direction: column; gap: 12px; }
  .profil-kort {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--card);
  }
  .profil-kort.aktiv-profil { border-color: var(--accent); }
  .profil-kort-info { display: flex; flex-direction: column; gap: 2px; font-size: 0.9rem; }
  .aktiv-merke { color: var(--accent); font-size: 0.75rem; }
  .profil-kort-knapper { display: flex; gap: 6px; }
  .profil-kort-knapper button {
    padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: none; cursor: pointer;
    color: var(--text); font-size: 0.8rem;
  }
  .profil-kort-knapper button:hover { background: var(--card-hover); }
  .profil-ny-knapp {
    align-self: flex-start; padding: 8px 16px;
    background: var(--accent); color: #fff; border: none;
    border-radius: 6px; cursor: pointer; font-size: 0.9rem;
  }
  .profil-skjema {
    display: flex; flex-direction: column; gap: 10px;
    padding: 16px; border: 1px solid var(--border); border-radius: 8px;
  }
  .profil-skjema label {
    display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem;
  }
  .profil-skjema input, .profil-skjema select {
    padding: 6px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: var(--bg); color: var(--text);
    font-size: 0.9rem;
  }
  .profil-skjema-knapper { display: flex; gap: 8px; margin-top: 4px; }
  .profil-skjema-knapper button {
    padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
  }
  .profil-skjema-knapper button:first-child {
    background: var(--accent); color: #fff; border: none;
  }
  .profil-skjema-knapper button:last-child {
    background: none; border: 1px solid var(--border); color: var(--text);
  }

  /* ── About-seksjon ───────────────────────────────────────── */
  .about-seksjon {
    margin-top: 24px; padding-top: 16px;
    border-top: 1px solid var(--border); color: var(--text-muted);
  }
  .about-tittel { font-weight: 600; margin-bottom: 8px; color: var(--text); }
  .about-tekst { font-size: 0.85rem; line-height: 1.5; margin-bottom: 8px; }
  .about-kontakt { font-size: 0.8rem; }

  /* ── Tidsbasert forside ─────────────────────────────────── */
  .forside-wrap { margin-bottom: 24px; }
  .forside-header { margin-bottom: 16px; }
  .forside-tittel { font-size: 1.3rem; font-weight: 700; margin: 0 0 4px; }
  .forside-undertekst { font-size: 0.85rem; color: var(--text-muted); margin: 0; }
  .forside-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  .forside-skille {
    border: none; border-top: 1px solid var(--border);
    margin: 0 0 24px;
  }
  /* ── Midjefilter ──────────────────────────────────────────── */
  .midjefilter-label { display: flex; align-items: center; gap: 8px; font-weight: normal; cursor: pointer; }
  .midjefilter-info { font-size: 0.8rem; color: var(--text-muted); margin: 2px 0 8px; }

  /* ── Versjonering / redigering ── */
  .detail-rediger {
    font-size: 0.82rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 10px; cursor: pointer;
  }
  .detail-rediger.aktiv { background: var(--card-hover); }
  .detail-rediger.har-kladd { border-color: var(--text-muted); }
  .rediger-meta { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
  .rediger-rad { display: flex; gap: 16px; }
  .rediger-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; color: var(--text-muted); font-family: var(--font-ui); }
  .rediger-input {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 8px; font-size: 0.9rem; font-family: var(--font-ui);
    width: 100%;
  }
  .rediger-input-sm { width: 90px; }
  .rediger-input-mengde { width: 64px; }
  .rediger-input-enhet { width: 60px; }
  .rediger-input-navn { flex: 1; }
  .rediger-textarea {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 6px 8px; font-size: 0.9rem; font-family: var(--font-ui);
    width: 100%; min-height: 56px; resize: vertical;
  }
  .rediger-ing-rad { display: flex; gap: 4px; align-items: center; margin-bottom: 4px; }
  .rediger-slett { background: none; border: none; cursor: pointer; font-size: 1rem; padding: 2px 4px; color: var(--text-muted); }
  .rediger-legg-til {
    margin-top: 8px; font-size: 0.82rem; font-family: var(--font-ui);
    background: none; border: 1px dashed var(--border); border-radius: var(--radius-sm);
    color: var(--text-muted); padding: 4px 10px; cursor: pointer; width: 100%;
  }
  .rediger-trinn-rad { display: flex; gap: 6px; align-items: flex-start; margin-bottom: 8px; }
  .rediger-trinn-nr { min-width: 24px; font-weight: 600; color: var(--text-muted); padding-top: 6px; }
  .rediger-trinn-tekst { flex: 1; min-height: 72px; }
  .rediger-trinn-knapper { display: flex; flex-direction: column; gap: 2px; }
  .rediger-pil {
    background: none; border: 1px solid var(--border); border-radius: var(--radius-sm);
    cursor: pointer; font-size: 0.8rem; padding: 2px 6px; color: var(--text-muted);
  }
  .rediger-pil:disabled { opacity: 0.3; cursor: default; }

  /* ── Lagremodal ── */
  .lagre-modal-bakgrunn {
    position: absolute; inset: 0; background: rgba(0,0,0,0.45);
    display: flex; align-items: center; justify-content: center; z-index: 10;
  }
  .lagre-modal {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; width: min(340px, 90%); display: flex; flex-direction: column; gap: 12px;
  }
  .lagre-modal-tittel { font-weight: 600; font-size: 1rem; }
  .lagre-modal-knapper { display: flex; gap: 8px; justify-content: flex-end; }
  .lagre-modal-btn {
    font-size: 0.85rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 6px 14px; cursor: pointer;
  }
  .lagre-modal-avbryt { color: var(--text-muted); }

  /* ── Historikkpanel ── */
  .versjon-historikk { margin-top: 20px; }
  .versjon-historikk-tittel { font-weight: 600; font-size: 0.9rem; margin-bottom: 8px; color: var(--text); }
  .versjon-rad {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;
    padding: 8px 0; border-bottom: 1px solid var(--border);
  }
  .versjon-rad:last-child { border-bottom: none; }
  .versjon-rad-info { display: flex; flex-direction: column; gap: 2px; }
  .versjon-tidspunkt { font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-ui); }
  .versjon-label { font-size: 0.88rem; }
  .versjon-label.ingen { color: var(--text-muted); font-style: italic; }
  .versjon-rad-knapper { display: flex; gap: 6px; }
  .versjon-btn {
    font-size: 0.78rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 4px 10px; cursor: pointer;
  }
  .versjon-btn-slett { color: var(--text-muted); }

  /* ── Sammenligningsoverlay ── */
  #sammenlign-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: stretch; justify-content: flex-end; z-index: 200;
  }
  #sammenlign-panel {
    background: var(--bg); width: min(720px, 100vw);
    display: flex; flex-direction: column; overflow: hidden;
  }
  .sammenlign-topbar {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
  }
  .sammenlign-tittel { font-weight: 600; flex: 1; font-size: 0.92rem; }
  .sammenlign-lukk, .sammenlign-bruk {
    font-size: 0.82rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 12px; cursor: pointer;
  }
  .sammenlign-body { flex: 1; overflow-y: auto; padding: 16px; }
  .sammenlign-seksjon-tittel { font-weight: 600; font-size: 0.88rem; margin: 16px 0 6px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .sammenlign-meta-grid {
    display: grid; grid-template-columns: auto 1fr 1fr; gap: 4px 12px; margin-bottom: 8px;
    font-size: 0.88rem;
  }
  .sammenlign-meta-felt { color: var(--text-muted); font-family: var(--font-ui); }
  .sammenlign-tabell-hdr {
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
    font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-ui);
    border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-bottom: 4px;
  }
  .sammenlign-rad {
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
    padding: 4px 6px; border-radius: var(--radius-sm); font-size: 0.88rem;
  }
  .sammenlign-rad.endret { background: rgba(255, 200, 0, 0.12); }
  .sammenlign-rad.ny { background: rgba(0, 180, 80, 0.12); }
  .sammenlign-rad.slettet { background: rgba(220, 50, 50, 0.12); }
  .sammenlign-celle { padding: 2px 0; }
  .sammenlign-celle-trinn { white-space: pre-wrap; }
  .sammenlign-trinn-nr { font-weight: 600; color: var(--text-muted); margin-right: 4px; }
  .sammenlign-orig { color: var(--text-muted); }
  .sammenlign-versjon { color: var(--text); }
  .sammenlign-tom { color: var(--text-muted); font-style: italic; }
  .plan-toggle { display: flex; flex-direction: row; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--text-muted); cursor: pointer; }
  .plan-toggle input { width: auto; }
  .plan-toggle.deaktivert { opacity: 0.4; cursor: not-allowed; }
  .pynt-toggle { margin-top: 10px; border-top: 1px solid var(--border-light); padding-top: 10px; }
  .pynt-toggle.deaktivert { opacity: 0.4; cursor: not-allowed; }

  /* ── Dagbok ────────────────────────────────────────────────────────────────── */
  .modal-bakgrunn {
    position: fixed; inset: 0; background: rgba(0,0,0,0.45);
    display: flex; align-items: center; justify-content: center; z-index: 100;
  }
  .dagbok-visning { padding: 1rem; max-width: 700px; }
  .dagbok-tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .dagbok-tabs button.aktiv { font-weight: bold; border-bottom: 2px solid currentColor; }
  .dagbok-seksjon { margin-bottom: 1rem; }
  .dagbok-seksjon h3 { font-size: 0.9rem; text-transform: uppercase; opacity: 0.6; margin-bottom: 0.25rem; }
  .dagbok-post { display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0; }
  .dagbok-post .kcal { margin-left: auto; opacity: 0.7; font-size: 0.9rem; }
  .dagbok-sum { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--farge-kant, #ddd); }
  .fremgangsbar-wrap { height: 8px; background: var(--farge-kant,#eee); border-radius: 4px; margin: 0.5rem 0; }
  .fremgangsbar { height: 8px; border-radius: 4px; transition: width 0.3s; }
  .logg-fab { position: fixed; bottom: 2rem; right: 2rem; width: 3rem; height: 3rem;
    border-radius: 50%; font-size: 1.5rem; background: var(--farge-primær,#b5651d);
    color: white; border: none; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
  .kcal-graf { width: 100%; height: 160px; }
  .logg-modal { background: var(--farge-flate,#fff); padding: 1.5rem; border-radius: 8px;
    max-width: 480px; width: 90%; display: flex; flex-direction: column; gap: 0.75rem; }
  .logg-søk-liste { list-style: none; padding: 0; margin: 0; border: 1px solid var(--farge-kant,#ddd); border-radius: 4px; }
  .logg-søk-liste li { padding: 0.5rem; cursor: pointer; }
  .logg-søk-liste li:hover { background: var(--farge-kant,#eee); }
  .logg-valgt { padding: 0.5rem; border: 1px solid var(--farge-primær,#b5651d); border-radius: 4px; }
  .porsjon-kontroll { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem; }
  .ingen { opacity: 0.5; font-style: italic; font-size: 0.9rem; }
  .modal-tittel { font-size: 1.1rem; font-weight: bold; }
  .modal-tabs { display: flex; gap: 0.5rem; }
  .modal-tabs button.aktiv { font-weight: bold; border-bottom: 2px solid currentColor; }
  .modal-knapper { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.5rem; }
  .modal-knapper button.primær { background: var(--farge-primær,#b5651d); color: white; border: none; border-radius: 4px; padding: 0.4rem 1rem; cursor: pointer; }
  .slett-knapp { margin-left: auto; background: none; border: none; cursor: pointer; opacity: 0.5; font-size: 1rem; }
  .slett-knapp:hover { opacity: 1; }
</style>
