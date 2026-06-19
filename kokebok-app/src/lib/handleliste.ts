// Handlelista persisteres i en JSON-fil i appens data-katalog via Tauri Store
// (samme mønster som favoritter.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";

const FIL = "handleliste.json";
const NOKKEL = "poster";

export type HandlelistePost = { id: number; porsjoner: number };

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(poster: HandlelistePost[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, poster);
    await store.save();
  } catch (err) {
    console.error("handleliste lagring feilet:", err);
  }
}

/** Last handlelista. Tom liste ved feil (ikke kritisk). */
export async function handlelisteLast(): Promise<HandlelistePost[]> {
  try {
    const store = await hentStore();
    return (await store.get<HandlelistePost[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("handlelisteLast feilet:", err);
    return [];
  }
}

/** Legg til (eller oppdater porsjoner hvis id finnes). Returnerer ny liste. */
export async function handlelisteLeggTil(
  id: number, porsjoner: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const finnes = liste.some((p) => p.id === id);
  const ny = finnes
    ? liste.map((p) => (p.id === id ? { id, porsjoner } : p))
    : [...liste, { id, porsjoner }];
  await lagre(ny);
  return ny;
}

/** Fjern én oppskrift. Returnerer ny liste. */
export async function handlelisteFjern(
  id: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const ny = liste.filter((p) => p.id !== id);
  await lagre(ny);
  return ny;
}

/** Endre porsjoner for én post. Returnerer ny liste. */
export async function handlelisteSettPorsjoner(
  id: number, porsjoner: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const ny = liste.map((p) => (p.id === id ? { id, porsjoner } : p));
  await lagre(ny);
  return ny;
}

/** Tøm hele lista. Returnerer tom liste. */
export async function handlelisteTøm(): Promise<HandlelistePost[]> {
  await lagre([]);
  return [];
}
