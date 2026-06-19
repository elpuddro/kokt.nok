// Aktive kostholdsfiltre persisteres via Tauri Store (som tema.ts). Filter-IDene
// må matche Rust-mappingen `tagger_for` i src-tauri/src/lib.rs.
import { load, type Store } from "@tauri-apps/plugin-store";

export type DiettFilter = { id: string; navn: string; beskrivelse: string };

/** Én kilde til sannhet for UI. Tagg-mappingen ligger i Rust (tagger_for). */
export const DIETT_FILTRE: DiettFilter[] = [
  { id: "halal", navn: "Halal-vennlig (uten åpenbart haram)",
    beskrivelse: "Skjuler svin, alkohol, blod og gelatin. Ikke halal-sertifisering — vanlig kjøtt vises." },
  { id: "vegetar", navn: "Vegetar", beskrivelse: "Skjuler kjøtt og fisk/skalldyr." },
  { id: "vegansk", navn: "Vegansk", beskrivelse: "Skjuler alt animalsk: kjøtt, fisk, egg, melk, gelatin, honning." },
  { id: "glutenfri", navn: "Glutenfri", beskrivelse: "Skjuler hvete, bygg, rug, brød, pasta o.l." },
  { id: "laktosefri", navn: "Laktosefri / melkefri", beskrivelse: "Skjuler melk, fløte, smør, ost o.l." },
  { id: "nott", navn: "Uten nøtter", beskrivelse: "Skjuler mandel, hasselnøtt, peanøtt o.l." },
];

const FIL = "diett.json";
const NOKKEL = "aktive";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last aktive filter-IDer. Tom liste ved feil. */
export async function diettLast(): Promise<string[]> {
  try {
    const store = await hentStore();
    const v = await store.get<string[]>(NOKKEL);
    return Array.isArray(v) ? v : [];
  } catch (err) {
    console.error("diettLast feilet:", err);
    return [];
  }
}

/** Lagre aktive filter-IDer. Best effort. Returnerer lista (uendret kopi). */
export async function diettSett(aktive: string[]): Promise<string[]> {
  const nytt = [...aktive];
  try {
    const store = await hentStore();
    await store.set(NOKKEL, nytt);
    await store.save();
  } catch (err) {
    console.error("diettSett lagring feilet:", err);
  }
  return nytt;
}
