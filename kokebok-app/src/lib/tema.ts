// Tema-valg persisteres via Tauri Store (som favoritter.ts). Ren logikk ligger
// i tema-logikk.ts (node-testbar); denne fila legger Store-persistering oppå.
import { load, type Store } from "@tauri-apps/plugin-store";
import { type Lagret, type TemaId, aktivtTema, gjeldendeTema, TEMAER, erGyldigTema } from "./tema-logikk";

export { aktivtTema, gjeldendeTema, TEMAER, erGyldigTema };
export type { Lagret, TemaId };

const FIL = "tema.json";
const NOKKEL = "valg";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last lagret tema-valg. Default auto ved feil/ingenting. */
export async function temaLast(): Promise<Lagret> {
  try {
    const store = await hentStore();
    const v = await store.get<Lagret>(NOKKEL);
    if (v && (v.modus === "auto" || v.modus === "manuell")) return v;
  } catch (err) {
    console.error("temaLast feilet:", err);
  }
  return { modus: "auto", tema: null };
}

/** Lagre tema-valg. Best effort. */
export async function temaSett(modus: "auto" | "manuell", tema: TemaId | null): Promise<Lagret> {
  const valg: Lagret = { modus, tema };
  try {
    const store = await hentStore();
    await store.set(NOKKEL, valg);
    await store.save();
  } catch (err) {
    console.error("temaSett feilet:", err);
  }
  return valg;
}
