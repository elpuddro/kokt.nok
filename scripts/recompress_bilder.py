#!/usr/bin/env python3
"""Rekomprimer kokebok-bildene: skaler lengste side til 600px, WebP q78.

In-place over kokebok-app/src-tauri/data/bilder/*.webp. Idempotent: hopper over
filer som allerede er <= 600px slik at gjentatte kjoringer ikke forringer videre.
Krever Pillow (pip install Pillow).
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow mangler. Kjor: pip install Pillow")

SIDE = 600
KVALITET = 78
BILDER = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "bilder"


def main() -> None:
    if not BILDER.is_dir():
        sys.exit(f"Fant ikke bildekatalog: {BILDER}")
    filer = sorted(BILDER.glob("*.webp"))
    if not filer:
        sys.exit(f"Ingen .webp i {BILDER}")

    endret = hoppet = 0
    for f in filer:
        # Lukk kildefila med ein gong convert() har laga eit nytt bilete i minnet,
        # so vi ikkje samlar opp opne filhandtak over 4444 filer.
        with Image.open(f) as src:
            im = src.convert("RGB")  # recipe-bilete har ingen alpha; RGB er trygt
        w, h = im.size
        storst = max(w, h)
        if storst <= SIDE:
            hoppet += 1
            continue
        ny = im.resize(
            (round(w * SIDE / storst), round(h * SIDE / storst)),
            Image.LANCZOS,
        )
        ny.save(f, "WEBP", quality=KVALITET, method=6)
        endret += 1

    print(f"Ferdig: {endret} rekomprimert, {hoppet} hoppet over ({len(filer)} totalt).")


if __name__ == "__main__":
    main()
