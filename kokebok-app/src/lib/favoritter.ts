// Favoritter persisteres i en JSON-fil i appens data-katalog via Tauri Store.
// kokt.db er read-only, så favoritter kan ikke skrives dit.
import { load, type Store } from "@tauri-apps/plugin-store";

const FIL = "favoritter.json";
const NOKKEL = "ids";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last favoritt-IDer. Returnerer tomt Set ved feil (favoritter er ikke kritiske). */
export async function favorittLast(): Promise<Set<number>> {
  try {
    const store = await hentStore();
    const ids = (await store.get<number[]>(NOKKEL)) ?? [];
    return new Set(ids);
  } catch (err) {
    console.error("favorittLast feilet:", err);
    return new Set();
  }
}

/**
 * Toggle favoritt-status for en oppskrift. Muterer ikke `settet` direkte —
 * returnerer et NYTT Set (Svelte 5 $state<Set> reagerer ikke på .add/.delete).
 * Best effort: ved lagringsfeil beholdes endringen i minnet for økten.
 */
export async function favorittToggle(
  id: number,
  settet: Set<number>,
): Promise<Set<number>> {
  const nytt = new Set(settet);
  if (nytt.has(id)) nytt.delete(id);
  else nytt.add(id);
  try {
    const store = await hentStore();
    await store.set(NOKKEL, [...nytt]);
    await store.save();
  } catch (err) {
    console.error("favorittToggle lagring feilet:", err);
  }
  return nytt;
}
