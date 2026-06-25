#!/bin/bash
# Kjøres i WSL: bash scripts/build-linux.sh
# Kopierer prosjektet til WSL-filsystem for å unngå /mnt/c kryssfilsystem-problemer.
set -e

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.cargo/bin"
export RUSTFLAGS="--remap-path-prefix=$HOME=/build --remap-path-prefix=/root=/build"

WIN_REPO="/mnt/c/Users/elpud/CODE/kokt.nok"
# Bygg i /tmp/build (nøytral path uten brukernavn) — Tauri embedder CARGO_MANIFEST_DIR i capability-strings
WSL_BUILD="/tmp/build/steike-bra"

echo "=== Rust: $(cargo --version) ==="
echo "=== Node: $(node --version) ==="

# Synk kildekode til WSL-filsystem (ekskluder node_modules, target, data)
echo "=== Synkroniserer kildekode til WSL ==="
mkdir -p "$WSL_BUILD"
rsync -a --delete \
    --exclude='node_modules' \
    --exclude='src-tauri/target' \
    --exclude='src-tauri/data' \
    --exclude='.svelte-kit' \
    --exclude='build' \
    "$WIN_REPO/kokebok-app/" "$WSL_BUILD/kokebok-app/"

# Kopier bygget frontend (fra Windows-siden der det allerede er bygget)
echo "=== Kopierer ferdig frontend ==="
rsync -a "$WIN_REPO/kokebok-app/build/" "$WSL_BUILD/kokebok-app/build/"

# Kopier database (kreves av Tauri build-script som resource)
echo "=== Kopierer database ==="
mkdir -p "$WSL_BUILD/kokebok-app/src-tauri/data"
cp "$WIN_REPO/kokebok-app/src-tauri/data/kokt-bundle.db" "$WSL_BUILD/kokebok-app/src-tauri/data/kokt-bundle.db"

cd "$WSL_BUILD/kokebok-app"

# Installer Linux-native node_modules
echo "=== npm ci (Linux) ==="
npm ci --silent

# Bygg Rust-binær
echo "=== Rust build ==="
cd "$WSL_BUILD/kokebok-app/src-tauri"
cargo build --release 2>&1

BIN="$WSL_BUILD/kokebok-app/src-tauri/target/release/kokebok-app"
echo "=== Sjekker for personspor i binær ==="
if strings "$BIN" | grep -iE "(elpud|elpuddro|frank|simonsen|claude|anthropic)" ; then
    echo "=== ADVARSEL: personspor funnet i binær ==="
fi
if [ -f "$BIN" ]; then
    SIZE=$(du -sh "$BIN" | cut -f1)
    echo "=== BINÆR OK: $SIZE ==="
    # Kopier tilbake til Windows
    cp "$BIN" "$WIN_REPO/kokebok-app/src-tauri/target/release/kokebok-app"
    echo "=== Kopiert til Windows portable-kilde ==="
else
    echo "=== FEIL: binær ikke funnet ==="
    exit 1
fi
