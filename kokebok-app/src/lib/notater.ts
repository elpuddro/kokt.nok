// Notater persisteres i en JSON-fil i appens data-katalog via Tauri Store
// (samme mønster som favoritter.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";

const FIL = "notater.json";
const NOKKEL = "notater";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last alle notater (oppskriftId → tekst). Tomt objekt ved feil. */
export async function notaterLast(): Promise<Record<number, string>> {
  try {
    const store = await hentStore();
    return (await store.get<Record<number, string>>(NOKKEL)) ?? {};
  } catch (err) {
    console.error("notaterLast feilet:", err);
    return {};
  }
}

/**
 * Sett (eller fjern) notat for en oppskrift. Returnerer NYTT objekt (Svelte 5
 * $state reagerer ikke på mutasjon). Tom/whitespace tekst fjerner nøkkelen, så
 * et tømt notat ikke etterlater et kort-merke. Best effort på lagring.
 */
export async function notatSett(
  id: number, tekst: string, alle: Record<number, string>,
): Promise<Record<number, string>> {
  const nytt: Record<number, string> = { ...alle };
  if (tekst.trim() === "") delete nytt[id];
  else nytt[id] = tekst;
  try {
    const store = await hentStore();
    await store.set(NOKKEL, nytt);
    await store.save();
  } catch (err) {
    console.error("notatSett lagring feilet:", err);
  }
  return nytt;
}
