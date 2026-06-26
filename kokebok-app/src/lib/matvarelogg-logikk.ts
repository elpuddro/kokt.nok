import type { Loggpost, MåltidTidspunkt } from "./matvarelogg.ts";

export function loggForDato(poster: Loggpost[], dato: string): Loggpost[] {
  return poster.filter(p => p.dato === dato);
}

export function tidspunktFraKlokkeslett(time: number): MåltidTidspunkt {
  if (time >= 6 && time < 10) return "frokost";
  if (time >= 10 && time < 14) return "lunsj";
  if (time >= 14 && time < 18) return "middag";
  if (time >= 18 && time < 22) return "kveldsmat";
  return "annet";
}

type Næringmap = Record<number, { kcal: number; protein: number; fett: number; karbo: number }>;
type Næringsum = { kcal: number; protein: number; fett: number; karbo: number };

export function loggSumNæring(poster: Loggpost[], næring: Næringmap): Næringsum {
  return poster.reduce((sum, p) => {
    if (p.type === "fri") {
      return { kcal: sum.kcal + p.kcal, protein: sum.protein + p.protein,
               fett: sum.fett + p.fett, karbo: sum.karbo + p.karbo };
    }
    const n = næring[p.oppskriftId];
    if (!n) return sum;
    const f = p.porsjoner;
    return { kcal: sum.kcal + n.kcal * f, protein: sum.protein + n.protein * f,
             fett: sum.fett + n.fett * f, karbo: sum.karbo + n.karbo * f };
  }, { kcal: 0, protein: 0, fett: 0, karbo: 0 });
}

export function loggKcalPerDag(poster: Loggpost[], næring: Næringmap, antallDager: number): { dato: string; kcal: number }[] {
  const result: { dato: string; kcal: number }[] = [];
  const idag = new Date();
  for (let i = antallDager - 1; i >= 0; i--) {
    const d = new Date(idag);
    d.setDate(d.getDate() - i);
    const pad = (n: number) => String(n).padStart(2, "0");
    const dato = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    const dagPoster = loggForDato(poster, dato);
    result.push({ dato, kcal: loggSumNæring(dagPoster, næring).kcal });
  }
  return result;
}
