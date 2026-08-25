# macOS Setup Handoff — Mac mini

Pick-up-here doc for finishing the environment migration off WSL2/Windows onto native macOS. Full
rationale and verified tool versions are logged in [`CHANGELOG.md`](CHANGELOG.md) under "Environment
migration: WSL2 (Windows) → native macOS" — this file is just the next steps.

**Status:** MacBook Neo is fully set up and verified. Mac mini is not yet done — that's this machine.

## Steps

1. **Install Homebrew** (needs your admin password typed interactively — can't be scripted):
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   Do **not** run this with `sudo` in front — the installer refuses to run as root and invokes `sudo`
   itself only for the one step that needs it.

   If a new terminal window doesn't pick up `brew` automatically, load it into the current shell:
   ```
   eval "$(/opt/homebrew/bin/brew shellenv)"
   ```

2. **Run the setup script** from the repo root:
   ```
   ./scripts/setup_macos.sh
   ```
   This installs `samtools`/`bcftools`/`htslib`/`blast`/`python@3.12` via Homebrew, installs `mash`
   separately (see gotcha below), creates the `~/venvs/trio-genome` venv, and registers the Jupyter
   kernel `trio-genome-macos` ("Python (trio-genome, macOS)").

3. **Gotcha — `mash`:** it has no `homebrew-core` formula. The script downloads the upstream `v2.3`
   Intel (`OSX64`) release binary to `~/bin/mash` and runs it via Rosetta 2. If Rosetta isn't installed
   yet, the script detects that and skips `mash` with a message — run `softwareupdate --install-rosetta`
   first, then re-run `./scripts/setup_macos.sh` (safe to re-run; it skips what's already installed).

4. **Select the kernel** in VS Code / Jupyter: `Python (trio-genome, macOS)`.

5. **Re-download the data.** `data/reference/`, `data/giab/`, and `data/derived/` are gitignored, so this
   clone has none of the actual sequence/VCF/hash-catalog files yet — only the manifests
   (`data/reference/manifest.tsv`, `data/giab/manifest.tsv`) describing what to fetch and their MD5s.
   Re-run the download + verification steps documented in `seq-hashing-project-handoff.md` and the
   `CHANGELOG.md` "Added" entries for `data/reference/` and `data/giab/`, then re-run notebooks
   `01` → `04` in order to regenerate `data/derived/chr22/hash_catalog.db` and reproduce the prior
   results (1341/1398 chr22 transcripts validated; 431 confident parent-of-origin calls).

## Quick sanity check once done

```bash
source ~/venvs/trio-genome/bin/activate
python -c "import pyfaidx; print(pyfaidx.__version__)"
samtools --version | head -1
mash --version
```
