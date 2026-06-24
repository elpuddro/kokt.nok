// Versjonering av oppskrifter — Tauri Store I/O.
// kokt.db er read-only; all brukerdata lagres i versjoner.json.
import { load, type Store } from "@tauri-apps/plugin-store";
import type { OppskriftEntry, OppskriftKopi, VersjonSnapshot } from "./versjoner-logikk.ts";

const FIL = "versjoner.json";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

// Intern type for hele store-strukturen
type VersjonerStore = Record<string, Record<number, OppskriftEntry>>;

async function hentAlle(): Promise<VersjonerStore> {
  try {
    const store = await hentStore();
    return (await store.get<VersjonerStore>("v")) ?? {};
  } catch {
    return {};
  }
}

async function lagreAlle(data: VersjonerStore): Promise<void> {
  const store = await hentStore();
  await store.set("v", data);
  await store.save();
}

/** Last kladd og historikk for én oppskrift under én profil. */
export async function versjonerLast(
  profilId: string,
  oppskriftId: number,
): Promise<OppskriftEntry | null> {
  try {
    const alle = await hentAlle();
    return alle[profilId]?.[oppskriftId] ?? null;
  } catch (err) {
    console.error("versjonerLast feilet:", err);
    return null;
  }
}

/** Oppdater kladd (autolaging — debounce i kallende kode). */
export async function kladd_sett(
  profilId: string,
  oppskriftId: number,
  kopi: OppskriftKopi,
): Promise<void> {
  try {
    const alle = await hentAlle();
    if (!alle[profilId]) alle[profilId] = {};
    const entry = alle[profilId][oppskriftId] ?? { kladd: null, historikk: [] };
    alle[profilId][oppskriftId] = { ...entry, kladd: kopi };
    await lagreAlle(alle);
  } catch (err) {
    console.error("kladd_sett feilet:", err);
  }
}

/** Fjern kladd (ved avbryt uten eksisterende versjon). */
export async function kladd_fjern(
  profilId: string,
  oppskriftId: number,
): Promise<void> {
  try {
    const alle = await hentAlle();
    const entry = alle[profilId]?.[oppskriftId];
    if (!entry) return;
    alle[profilId][oppskriftId] = { ...entry, kladd: null };
    await lagreAlle(alle);
  } catch (err) {
    console.error("kladd_fjern feilet:", err);
  }
}

/** Lagre en navngitt versjon. Returnerer oppdatert historikk (nyeste først). */
export async function versjon_lagre(
  profilId: string,
  oppskriftId: number,
  label: string,
  kopi: OppskriftKopi,
): Promise<VersjonSnapshot[]> {
  try {
    const alle = await hentAlle();
    if (!alle[profilId]) alle[profilId] = {};
    const entry = alle[profilId][oppskriftId] ?? { kladd: null, historikk: [] };
    const snapshot: VersjonSnapshot = {
      id: crypto.randomUUID(),
      lagretTidspunkt: new Date().toISOString(),
      label: label.trim(),
      kopi,
    };
    const historikk = [snapshot, ...entry.historikk];
    alle[profilId][oppskriftId] = { kladd: kopi, historikk };
    await lagreAlle(alle);
    return historikk;
  } catch (err) {
    console.error("versjon_lagre feilet:", err);
    return [];
  }
}

/** Slett én versjon. Returnerer oppdatert historikk. */
export async function versjon_slett(
  profilId: string,
  oppskriftId: number,
  versjonId: string,
): Promise<VersjonSnapshot[]> {
  try {
    const alle = await hentAlle();
    const entry = alle[profilId]?.[oppskriftId];
    if (!entry) return [];
    const historikk = entry.historikk.filter((v) => v.id !== versjonId);
    alle[profilId][oppskriftId] = { ...entry, historikk };
    await lagreAlle(alle);
    return historikk;
  } catch (err) {
    console.error("versjon_slett feilet:", err);
    return [];
  }
}
