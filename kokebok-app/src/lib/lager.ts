// Lageret persisteres i lager.json via Tauri Store (samme mønster som
// handleliste.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";

export type LagerVare = { navn: string; utloper: string | null };

const FIL = "lager.json";
const NOKKEL = "varer";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(varer: LagerVare[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, varer);
    await store.save();
  } catch (err) {
    console.error("lager lagring feilet:", err);
  }
}

/** Last lageret. Tom liste ved feil. */
export async function lagerLast(): Promise<LagerVare[]> {
  try {
    const store = await hentStore();
    return (await store.get<LagerVare[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("lagerLast feilet:", err);
    return [];
  }
}

/** Legg til en vare (dedup på navn, case-insensitivt). Returnerer ny liste. */
export async function lagerLeggTil(
  navn: string, utloper: string | null, liste: LagerVare[],
): Promise<LagerVare[]> {
  const rent = navn.trim();
  if (!rent) return liste;
  const finnes = liste.some((v) => v.navn.toLowerCase() === rent.toLowerCase());
  const ny = finnes
    ? liste.map((v) => (v.navn.toLowerCase() === rent.toLowerCase() ? { navn: rent, utloper } : v))
    : [...liste, { navn: rent, utloper }];
  await lagre(ny);
  return ny;
}

/** Fjern én vare (på navn, case-insensitivt). Returnerer ny liste. */
export async function lagerFjern(navn: string, liste: LagerVare[]): Promise<LagerVare[]> {
  const ny = liste.filter((v) => v.navn.toLowerCase() !== navn.toLowerCase());
  await lagre(ny);
  return ny;
}

/** Tøm lageret. Returnerer tom liste. */
export async function lagerTøm(): Promise<LagerVare[]> {
  await lagre([]);
  return [];
}
