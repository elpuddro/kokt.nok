import { load, type Store } from "@tauri-apps/plugin-store";

export type MåltidTidspunkt = "frokost" | "lunsj" | "middag" | "kveldsmat" | "annet";

export interface LoggpostOppskrift {
  id: string; dato: string; tidspunkt: MåltidTidspunkt;
  type: "oppskrift"; oppskriftId: number; porsjoner: number;
}
export interface LoggpostFri {
  id: string; dato: string; tidspunkt: MåltidTidspunkt;
  type: "fri"; beskrivelse: string;
  kcal: number; protein: number; fett: number; karbo: number;
}
export type Loggpost = LoggpostOppskrift | LoggpostFri;

const FIL = "matvarelogg.json";
const NOKKEL = "poster";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(poster: Loggpost[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, poster);
    await store.save();
  } catch (err) {
    console.error("matvarelogg lagring feilet:", err);
  }
}

export async function loggLast(): Promise<Loggpost[]> {
  try {
    const store = await hentStore();
    return (await store.get<Loggpost[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("loggLast feilet:", err);
    return [];
  }
}

export async function loggLeggTil(post: Loggpost): Promise<Loggpost[]> {
  const poster = await loggLast();
  const ny = [...poster, post];
  await lagre(ny);
  return ny;
}

export async function loggFjern(id: string): Promise<Loggpost[]> {
  const poster = await loggLast();
  const ny = poster.filter(p => p.id !== id);
  await lagre(ny);
  return ny;
}
