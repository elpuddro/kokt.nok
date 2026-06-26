interface OppskriftDetalj {
  navn: string;
  tid?: number;
  porsjoner?: number;
  ingredienser?: Array<{ mengde?: number; enhet?: string; navn: string }>;
  trinn?: Array<{ nummer?: number; tekst: string }>;
}

export function formaterOppskrift(oppskrift: OppskriftDetalj): string {
  const linjer: string[] = [];

  linjer.push(oppskrift.navn);

  const meta: string[] = [];
  if (oppskrift.tid) meta.push(`${oppskrift.tid} min`);
  if (oppskrift.porsjoner) meta.push(`${oppskrift.porsjoner} porsjoner`);
  if (meta.length > 0) linjer.push(meta.join(" | "));

  if (oppskrift.ingredienser && oppskrift.ingredienser.length > 0) {
    linjer.push("");
    linjer.push("INGREDIENSER");
    for (const ing of oppskrift.ingredienser) {
      const del: string[] = [];
      if (ing.mengde) del.push(String(ing.mengde));
      if (ing.enhet) del.push(ing.enhet);
      del.push(ing.navn);
      linjer.push(`- ${del.join(" ")}`);
    }
  }

  if (oppskrift.trinn && oppskrift.trinn.length > 0) {
    linjer.push("");
    linjer.push("FREMGANGSMÅTE");
    oppskrift.trinn.forEach((trinn, i) => {
      linjer.push(`${trinn.nummer ?? i + 1}. ${trinn.tekst}`);
    });
  }

  linjer.push("");
  linjer.push("— Delt fra Steike bra");

  return linjer.join("\n");
}
