// Ren tema-logikk — INGEN Tauri-/Svelte-import, så den kan node-testes direkte.

export type TemaId =
  | "varm" | "dark" | "vinter" | "vaar" | "sommer" | "host"
  | "17mai" | "halloween" | "valentines" | "paske" | "singles";

export type Lagret = { modus: "auto" | "manuell"; tema: TemaId | null };

// Visningsnavn for Innstillinger-velgeren (rekkefølge = visningsrekkefølge).
export const TEMAER: { id: TemaId; navn: string }[] = [
  { id: "varm", navn: "Varm (standard)" },
  { id: "dark", navn: "Mørk (dark mode)" },
  { id: "vaar", navn: "Vår" },
  { id: "sommer", navn: "Sommer" },
  { id: "host", navn: "Høst" },
  { id: "vinter", navn: "Vinter / jul" },
  { id: "paske", navn: "Påske" },
  { id: "17mai", navn: "17. mai" },
  { id: "halloween", navn: "Halloween" },
  { id: "valentines", navn: "Valentines" },
  { id: "singles", navn: "Singles Day" },
];

const GYLDIGE = new Set(TEMAER.map((t) => t.id));
export function erGyldigTema(id: unknown): id is TemaId {
  return typeof id === "string" && GYLDIGE.has(id as TemaId);
}

/** Påskedag (søndag) for et år, via Gauss/Computus (gregoriansk). */
export function paaskedag(aar: number): Date {
  const a = aar % 19;
  const b = Math.floor(aar / 100);
  const c = aar % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const maaned = Math.floor((h + l - 7 * m + 114) / 31); // 3=mars, 4=april
  const dag = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(aar, maaned - 1, dag);
}

// Hjelper: dato uten klokkeslett, som dagnummer for sammenligning.
function somDag(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Auto-tema for en gitt dato: høytidsvindu → sesong → "varm". */
export function gjeldendeTema(dato: Date): TemaId {
  const aar = dato.getFullYear();
  const md = (m: number, d: number) => new Date(aar, m - 1, d);
  const n = somDag(dato);
  const mellom = (fra: Date, til: Date) => n >= somDag(fra) && n <= somDag(til);

  // Høytider (mest spesifikke først).
  if (mellom(md(2, 7), md(2, 14))) return "valentines";
  const paske = paaskedag(aar);
  const palmesondag = new Date(paske); palmesondag.setDate(paske.getDate() - 7);
  const andrePaskedag = new Date(paske); andrePaskedag.setDate(paske.getDate() + 1);
  if (mellom(palmesondag, andrePaskedag)) return "paske";
  if (mellom(md(5, 10), md(5, 18))) return "17mai";
  if (mellom(md(10, 24), md(10, 31))) return "halloween";
  if (n === somDag(md(11, 11))) return "singles";
  // Jul/vinter-vindu: 1. des–6. jan
  if (n >= somDag(md(12, 1)) || n <= somDag(md(1, 6))) return "vinter";

  // Sesong ellers, etter måned (1-indeksert).
  const m = dato.getMonth() + 1;
  if (m >= 3 && m <= 5) return "vaar";
  if (m >= 6 && m <= 8) return "sommer";
  if (m >= 9 && m <= 11) return "host";
  return "vinter"; // jan/feb utenom valentines
}

/** Faktisk tema gitt lagret valg + dato. Manuell overstyrer auto. */
export function aktivtTema(lagret: Lagret | null, dato: Date): TemaId {
  if (lagret && lagret.modus === "manuell" && erGyldigTema(lagret.tema)) {
    return lagret.tema;
  }
  return gjeldendeTema(dato);
}
