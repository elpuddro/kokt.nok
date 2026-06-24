#!/usr/bin/env python3
"""Rekomprimer kokebok-bildene: skaler lengste side til 400px, WebP q75.

In-place over kokebok-app/src-tauri/data/bilder/*.webp. Idempotent: hopper over
filer som allerede er <= 400px slik at gjentatte kjoringer ikke forringer videre.
Krever Pillow (pip install Pillow).
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow mangler. Kjor: pip install Pillow")

SIDE = 400
KVALITET = 75
BILDER = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "bilder"


def main() -> None:
    if not BILDER.is_dir():
        sys.exit(f"Fant ikke bildekatalog: {BILDER}")
    filer = sorted(BILDER.glob("*.webp"))
    if not filer:
        sys.exit(f"Ingen .webp i {BILDER}")

    endret = hoppet = 0
    for f in filer:
        with Image.open(f) as src:
            im = src.convert("RGB")
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
