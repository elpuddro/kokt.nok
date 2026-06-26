import { load, type Store } from "@tauri-apps/plugin-store";

export interface Prispost {
  id: string;
  ingrediens: string;
  pris: number;
  enhet: "kg" | "l" | "stk" | "pakke" | "dl" | "g";
  dato: string;
  butikk?: string;
}

const FIL = "priser.json";
const NOKKEL = "poster";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(poster: Prispost[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, poster);
    await store.save();
  } catch (err) {
    console.error("priser lagring feilet:", err);
  }
}

export async function priserLast(): Promise<Prispost[]> {
  try {
    const store = await hentStore();
    return (await store.get<Prispost[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("priserLast feilet:", err);
    return [];
  }
}

export async function priserLeggTilFlere(nye: Omit<Prispost, "id">[]): Promise<Prispost[]> {
  const poster = await priserLast();
  const med_id: Prispost[] = nye.map(p => ({ ...p, id: crypto.randomUUID() }));
  const ny = [...poster, ...med_id];
  await lagre(ny);
  return ny;
}

export async function prisOppdater(oppdatert: Prispost): Promise<Prispost[]> {
  const poster = await priserLast();
  const ny = poster.map(p => p.id === oppdatert.id ? oppdatert : p);
  await lagre(ny);
  return ny;
}

export async function prisSlett(id: string): Promise<Prispost[]> {
  const poster = await priserLast();
  const ny = poster.filter(p => p.id !== id);
  await lagre(ny);
  return ny;
}
