import { load } from "@tauri-apps/plugin-store";

export type Aktivitetsnivå = "stillesittende" | "lett" | "moderat" | "aktiv" | "veldig_aktiv";
export type Mål = "nedgang" | "vedlikehold" | "oppgang";

export interface Brukerprofil {
  id: string;
  navn: string;
  kjønn: "mann" | "kvinne";
  alder: number;
  høyde: number;
  vekt: number;
  aktivitet: Aktivitetsnivå;
  mål: Mål;
}

export interface ProfilStore {
  profiler: Brukerprofil[];
  aktivId: string | null;
}

export interface Dagsbehov {
  kcal: number;
  protein: number;
  fett: number;
  karbo: number;
}

const AKTIVITETSFAKTOR: Record<Aktivitetsnivå, number> = {
  stillesittende: 1.2,
  lett: 1.375,
  moderat: 1.55,
  aktiv: 1.725,
  veldig_aktiv: 1.9,
};

const MÅLSJUSTERING: Record<Mål, number> = {
  nedgang: -500,
  vedlikehold: 0,
  oppgang: 500,
};

function bmr(p: Brukerprofil): number {
  const base = 10 * p.vekt + 6.25 * p.høyde - 5 * p.alder;
  return p.kjønn === "mann" ? base + 5 : base - 161;
}

export function tdee(p: Brukerprofil): number {
  return Math.round(bmr(p) * AKTIVITETSFAKTOR[p.aktivitet] + MÅLSJUSTERING[p.mål]);
}

export function dagsbehov(p: Brukerprofil): Dagsbehov {
  const t = tdee(p);
  return {
    kcal: t,
    protein: Math.round((t * 0.15) / 4),
    fett: Math.round((t * 0.30) / 9),
    karbo: Math.round((t * 0.55) / 4),
  };
}

export function dekningsProsent(næring: number, behov: number): number {
  if (!behov) return 0;
  return Math.round((næring / behov) * 100);
}

export async function profilLast(): Promise<ProfilStore> {
  const store = await load("profiler.json");
  const data = await store.get<ProfilStore>("profiler");
  return data ?? { profiler: [], aktivId: null };
}

async function _lagre(ps: ProfilStore): Promise<void> {
  const store = await load("profiler.json");
  await store.set("profiler", ps);
  await store.save();
}

export async function profilSettAktiv(id: string | null): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.aktivId = id;
  await _lagre(ps);
  return ps;
}

export async function profilOpprett(felt: Omit<Brukerprofil, "id">): Promise<ProfilStore> {
  const ps = await profilLast();
  const ny: Brukerprofil = { id: crypto.randomUUID(), ...felt };
  ps.profiler.push(ny);
  if (!ps.aktivId) ps.aktivId = ny.id;
  await _lagre(ps);
  return ps;
}

export async function profilOppdater(oppdatert: Brukerprofil): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.profiler = ps.profiler.map((p) => (p.id === oppdatert.id ? oppdatert : p));
  await _lagre(ps);
  return ps;
}

export async function profilSlett(id: string): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.profiler = ps.profiler.filter((p) => p.id !== id);
  if (ps.aktivId === id) ps.aktivId = ps.profiler[0]?.id ?? null;
  await _lagre(ps);
  return ps;
}
