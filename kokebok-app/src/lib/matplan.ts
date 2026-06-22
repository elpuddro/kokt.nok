// Aktiv ukemeny persisteres i matplan.json via Tauri Store (samme mønster som
// lager.ts / handleliste.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";
import type { Slot, SlotType } from "$lib/matplan-logikk";

export type Dag = {
  frokost: Slot; lunsj: Slot; middag: Slot; kveldsmat: Slot;
  kcalDag: number | null;
};
export type Uke = {
  dager: Dag[]; // alltid 7
  dagsmaal: number;
  personer: number;
  generert: string; // ISO
};

const FIL = "matplan.json";
const NOKKEL = "uke";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last lagret uke, eller null. */
export async function matplanLast(): Promise<Uke | null> {
  try {
    const store = await hentStore();
    return (await store.get<Uke>(NOKKEL)) ?? null;
  } catch (err) {
    console.error("matplanLast feilet:", err);
    return null;
  }
}

/** Lagre aktiv uke (best-effort). */
export async function matplanLagre(uke: Uke): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, uke);
    await store.save();
  } catch (err) {
    console.error("matplanLagre feilet:", err);
  }
}

/** Slett lagret uke. */
export async function matplanTøm(): Promise<void> {
  try {
    const store = await hentStore();
    await store.delete(NOKKEL);
    await store.save();
  } catch (err) {
    console.error("matplanTøm feilet:", err);
  }
}

export type { Slot, SlotType };
