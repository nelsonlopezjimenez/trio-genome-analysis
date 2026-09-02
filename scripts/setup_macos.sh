#!/usr/bin/env bash
# One-time macOS environment setup for the sequence-hashing POC
# (HANDOFF.md). Run on each machine (Mac mini, MacBook).
#
# Prerequisite: Homebrew must already be installed (requires an interactive
# sudo password, so it isn't done by this script):
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#
# Usage: ./scripts/setup_macos.sh

set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Install it first (see comment at top of this script)." >&2
    exit 1
fi

echo "==> Installing CLI tools via Homebrew"
# mash is NOT in homebrew-core (removed from the old brewsci/bio tap, which is
# deprecated) -- installed separately below from upstream GitHub releases.
# awscli: for population-scale batch processing against public data mirrored on AWS
# Open Data (e.g. s3://1000genomes) -- see HANDOFF.md's "Scaling to genome-wide and
# population scale" section. Installing the CLI does NOT configure credentials or
# provision any AWS resources; run `aws configure` separately with your own account's
# access keys when you're ready to use it.
brew install samtools bcftools htslib blast python@3.12 awscli

echo "==> Installing mash (no homebrew-core formula; upstream release binary)"
if command -v mash >/dev/null 2>&1; then
    echo "mash already on PATH, skipping"
elif [[ "$(uname -m)" == "arm64" ]] && ! /usr/bin/pgrep -q oahd; then
    echo "SKIPPED: mash upstream only ships Intel (OSX64) binaries, and Rosetta 2" >&2
    echo "  isn't installed. Run: softwareupdate --install-rosetta, then re-run this script." >&2
else
    mkdir -p "$HOME/bin"
    tmpdir="$(mktemp -d)"
    curl -fsSL "https://github.com/marbl/Mash/releases/download/v2.3/mash-OSX64-v2.3.tar" \
        -o "$tmpdir/mash.tar"
    tar -xf "$tmpdir/mash.tar" -C "$tmpdir"
    cp "$tmpdir"/mash-OSX64-v2.3/mash "$HOME/bin/mash"
    chmod +x "$HOME/bin/mash"
    rm -rf "$tmpdir"
    if ! grep -q '\$HOME/bin' "$HOME/.zprofile" 2>/dev/null; then
        echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.zprofile"
    fi
    export PATH="$HOME/bin:$PATH"
    echo "installed mash to ~/bin/mash (Intel binary via Rosetta 2)"
fi

echo "==> Creating Python venv (~/venvs/trio-genome)"
mkdir -p "$HOME/venvs"
"$(brew --prefix python@3.12)/bin/python3.12" -m venv "$HOME/venvs/trio-genome"

echo "==> Installing Python packages"
"$HOME/venvs/trio-genome/bin/pip" install --upgrade pip
"$HOME/venvs/trio-genome/bin/pip" install jupyter ipykernel pyfaidx biopython

echo "==> Registering Jupyter kernel"
"$HOME/venvs/trio-genome/bin/python" -m ipykernel install --user \
    --name trio-genome-macos --display-name "Python (trio-genome, macOS)"

echo "==> Versions"
samtools --version | head -1
bcftools --version | head -1
bgzip --version | head -1
tabix --version | head -1
command -v mash >/dev/null 2>&1 && mash --version || echo "mash: not installed (see above)"
dustmasker -version-full
segmasker -version-full
"$HOME/venvs/trio-genome/bin/python" --version
sqlite3 --version
aws --version

echo
echo "Done. In VS Code / Jupyter, select kernel: 'Python (trio-genome, macOS)'"
echo "To activate the venv in a shell: source ~/venvs/trio-genome/bin/activate"
