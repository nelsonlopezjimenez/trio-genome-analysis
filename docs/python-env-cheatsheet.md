# Python / environment cheat sheet — Mac mini

Quick reference for checking what's active and what's installed on this machine. Written after
finding this Mac mini already has Homebrew (used for Docker/Tailscale) *and* Anaconda (`base` +
a `catalog` env for the unrelated sequence-hashing project) — see the note at the bottom on why
that matters for `trio-genome`.

## What's actually active right now

```bash
# Which python3 wins on PATH, and where it actually lives
which python3
python3 -c "import sys; print(sys.executable)"
python3 --version

# Conda: is a conda env active, and which one
echo "$CONDA_DEFAULT_ENV"       # empty if none active
conda info --envs               # * marks the active one

# venv: is a plain venv active
echo "$VIRTUAL_ENV"             # empty if none active
```

**Gotcha on this machine:** `conda config --show auto_activate_base` → `True`, and `conda init` is
wired into `~/.zshrc`. That means every new shell starts with conda's `base` already active and
`python3` pointing at `/opt/anaconda3/bin/python3` — *before* you've done anything. If you then
`source ~/venvs/trio-genome/bin/activate`, the venv's `bin/` gets prepended on top and takes over
correctly (last-activated wins). But if you ever run `conda activate <something>` *after*
activating the venv, conda wins back. Rule of thumb: activate the venv last, and if `which python3`
ever looks wrong, check `echo $CONDA_DEFAULT_ENV` before anything else.

## Conda (Anaconda at `/opt/anaconda3`)

```bash
conda --version
conda info --envs                    # list all envs, base = /opt/anaconda3
conda list -n <env-name>             # packages in a specific env
conda list -n <env-name> <package>   # check one package's version in an env
conda activate <env-name>
conda deactivate                     # drops back to base (not "off" — base is still active)
```

Current envs on this machine: `base` (Python 3.13.5) and `catalog` (Python 3.12.13, has `blake3` —
belongs to the sequence-hashing project, unrelated to `trio-genome`).

## venv (`~/venvs/trio-genome`, once created by `scripts/setup_macos.sh`)

```bash
source ~/venvs/trio-genome/bin/activate
python --version
pip list
pip show <package>                   # version + install location of one package
deactivate
```

## Homebrew

```bash
brew --version
brew list --formula                  # everything installed via brew
brew list --versions samtools bcftools htslib blast   # check specific genomics tools
brew info <formula>                  # where it lives, caveats, dependents
brew --prefix                        # /opt/homebrew on Apple Silicon
brew --prefix python@3.12            # exact path the setup script builds the venv from
```

## Genomics CLI tools (installed by `scripts/setup_macos.sh`)

```bash
samtools --version | head -1
bcftools --version | head -1
bgzip --version | head -1
tabix --version | head -1
dustmasker -version-full
segmasker -version-full
mash --version                       # ~/bin/mash — Intel binary run via Rosetta 2, not a brew formula
```

If `mash` isn't found, check Rosetta is installed (`pgrep oahd` should print a PID) and that
`$HOME/bin` is on `PATH` (the setup script appends it to `~/.zprofile`).

## Jupyter kernels

```bash
jupyter kernelspec list
```

Expect to see **two** `python3`-flavored kernels once setup finishes: conda's `python3`
(`/opt/anaconda3/share/jupyter/kernels/python3`, unrelated) and the one you actually want,
`trio-genome-macos` (display name **"Python (trio-genome, macOS)"**). Always pick the latter for
this project's notebooks — picking the wrong one silently runs code against conda `base` or
`catalog` instead of the project venv.

```bash
jupyter kernelspec uninstall <name>   # remove a stale/duplicate kernel if needed
```

## Why Homebrew, not conda, for this project

Homebrew is already installed on this machine (it's what runs Docker/Tailscale), so "install
Homebrew" from `HANDOFF.md`'s new-machine setup steps is already done here — nothing new to set
up for that. The genomics tools (`samtools`/`bcftools`/`htslib`/`blast`) get installed as a few more brew
formulae on top of that existing install; `mash` is the one exception (upstream binary, no brew
formula — see above).

Conda *could* also provide these via bioconda, but this Mac mini's conda `base`/`catalog` envs
already belong to a different project (sequence hashing). Keeping `trio-genome` on Homebrew + a
plain venv — exactly as `scripts/setup_macos.sh` already does, and exactly as MacBook Neo was
already set up — means:
- the two Macs stay identical for this project (same script, same steps, same doc to follow again
  next time),
- `trio-genome`'s dependencies never touch or share a channel with the unrelated `catalog` conda
  env,
- nothing about the existing conda setup needs to change.

Net effect: brew is "necessary" only in the trivial sense that it's already there and the project
already depends on it — there's no separate "should I install Homebrew" decision left to make here.
