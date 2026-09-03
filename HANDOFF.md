# Handoff — Trio Genome Analysis

**Last updated: 2026-09-03**

This is the one living document for current project state. For dated history, see
[`CHANGELOG.md`](CHANGELOG.md) (append-only, newest first). This file gets edited in place —
when something here goes stale, fix it here rather than adding a new handoff file.

There are **two unrelated efforts** in this repo. Everything below is about the second one
unless a section says otherwise.

1. **v1→v3 gene-level SHA256 pipeline** (`scripts/trio_genome_script.sh`) — 1000 Genomes
   NA12878 trio, whole-gene SHA256 hashes. Superseded in relevance by (2) below but still the
   only code under `scripts/` that runs end-to-end; not being actively developed.
2. **CDS-anchored sequence-hashing POC** (notebooks + `scripts/gencode_cds_extract.py`) — the
   active project. Everything in this file from here on is about this effort.

---

## Goal

**Primary goal (pivoted 2026-08-29, confirmed 2026-08-30): population/ancestry signal from
coding-region hashes** (Track 2 below) — not parent-of-origin inheritance. Hash reference
proteome sequences (AA, cDNA/CDS, per-exon) plus individual proteomes from a **chr22 trio**,
and use them to explore ancestry/ethnicity distance. Scope: **proof-of-concept / teaching
demo**, not a production pipeline.

Parent-of-origin inheritance (Track 1) was the *original* goal and is fully demonstrated on
real chr22 GIAB trio data (431 confident calls — see [Data facts](#data-facts-verified-chr22-gencode-v46)).
That work is complete, validated, and kept as-is for reference; it is **no longer the active
thread** — new effort goes toward Track 2. See [The two tracks](#the-two-tracks-different-tools-different-goals)
for what's active vs. what's done.

**Environment:** macOS (Apple Silicon) — MacBook "Neo" and Mac mini, both native (moved off a
Windows/WSL2 machine in 2026-08). bash-first + samtools/bcftools/bgzip/tabix; Python
(Biopython, pyfaidx) for exploration; SQLite for the hash catalog. See
[Environment / machines](#environment--machines) below for per-machine status.

---

## Current state (verified against the filesystem, not just prose)

- **Reference data**: GENCODE v46 chr22 files (GTF + `pc_transcripts.fa` + `pc_translations.fa`)
  are present in `data/reference/` on this machine, MD5-verified per `data/reference/manifest.tsv`.
- **GIAB trio data**: HG002 (phased)/HG003/HG004 chr22 VCF slices present in `data/giab/`,
  per `data/giab/manifest.tsv`.
- **Notebooks 01→04 have all been rerun on the Mac mini (2026-08-31)** and `data/derived/
  chr22/` is now populated (`hash_catalog.db`, `chr22_{proteins,cds,exons}.fa` +
  `.fai`) — gitignored, so this is machine-local, not committed. **Verified exact reproduction
  of the original 2026-07-03 Windows/WSL2 run**, checked directly against the live SQLite
  catalog, not just re-trusting printed output: same row counts (16,176 GENCODE rows: 1341
  AA + 1341 CDS + 13,494 exon; 1110 GIAB haplotype rows), the same MD5/SQ hash **byte-for-byte**
  for a spot-checked accession (`ENST00000332987.5.exon1` → `e5b224e6fc070e352dc20de89222b13d`,
  identical on both platforms), and an exact match on the full Track 1 classification breakdown
  (see [Data facts](#data-facts-verified-chr22-gencode-v46) below) — expected, since hashing is
  deterministic on identical input bytes regardless of OS, but confirmed rather than assumed.
- **Notebook 01** (hash functions) was rerun and kernel-verified on the Mac mini first, on
  2026-08-29, ahead of the full 02→04 run above — MD5/SQ outputs reproduced exactly then too.
- **Not yet done:** `notebooks/03_sqlite_catalog.ipynb` and `notebooks/04_trio_inheritance.ipynb`
  haven't actually been saved in VS Code — both are still byte-identical on disk to the old
  2026-07-03 git-committed version (verified via `diff` against `git show HEAD:...`), even
  though the kernel genuinely executed their cells and wrote the real data described above.
  Save both (Cmd+S) so the tracked files show today's actual output.
- `scripts/gencode_cds_extract.py` is the promoted, standalone version of notebook 02's
  extraction logic. It has one known fidelity gap vs. the notebook — see
  [Known gaps / bugs](#known-gaps--bugs-verified-against-code) below.

---

## Environment / machines

- **MacBook "Neo"**: fully set up and verified 2026-08-17 — `samtools` 1.24, `bcftools` 1.24,
  `htslib` 1.24, `blast` 2.17.0, `mash` 2.3 (Intel binary via Rosetta 2, no `homebrew-core`
  formula exists). Python 3.12.14 venv, kernel `trio-genome-macos`. Smoke-tested against
  `scripts/gencode_cds_extract.py`.
- **Mac mini** (current dev machine): has **both** Homebrew (pre-existing, used for
  Docker/Tailscale) and Anaconda (`base` + an unrelated `catalog` env). This project uses
  Homebrew + a plain venv (`~/venvs/trio-genome`), **not** conda — see
  [`docs/python-env-cheatsheet.md`](docs/python-env-cheatsheet.md) for the full rationale and
  the "activate the venv last" gotcha (conda auto-activates `base` in every new shell here).
  Notebook 01 confirmed working against the `trio-genome-macos` kernel 2026-08-29; `samtools`/
  `bcftools`/`mash` installation has not been independently re-confirmed on this specific
  machine in this session — run the sanity checks in `docs/python-env-cheatsheet.md` before
  assuming they're present.
- No cloud compute is currently in use — an earlier AWS Lightsail instance was wound down; all
  work happens locally on the Mac mini / MacBook.
- **AWS CLI installed on the Mac mini, 2026-09-02** (`brew install awscli`, v2.36.37; added to
  `scripts/setup_macos.sh`). **No AWS account, credentials, or resources are connected** — this
  is just the CLI tool on the local machine, `aws configure` (needing real account access keys)
  has not been run, and nothing has been provisioned. In place ahead of the AWS batch-processing
  work under [Scaling to genome-wide and population scale](#scaling-to-genome-wide-and-population-scale-2026-09-02).

### Setting up a new machine

1. Install Homebrew (interactive, needs admin password — can't be scripted):
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
   (don't prefix with `sudo`).
2. Run `./scripts/setup_macos.sh` from the repo root — installs `samtools`/`bcftools`/`htslib`/
   `blast`/`python@3.12` via Homebrew, installs `mash` separately (upstream `v2.3` Intel binary
   run under Rosetta 2 — no `homebrew-core` formula exists), creates `~/venvs/trio-genome`, and
   registers Jupyter kernel `trio-genome-macos`. Idempotent — safe to rerun.
3. If `mash` gets skipped, run `softwareupdate --install-rosetta` first, then rerun the script.
4. Select kernel `Python (trio-genome, macOS)` in VS Code / Jupyter.
5. On a genuinely fresh clone (unlike this Mac mini checkout, which already has the data — see
   above): `data/reference/`, `data/giab/`, and `data/derived/` are gitignored, so re-download
   per the manifests (`data/reference/manifest.tsv`, `data/giab/manifest.tsv`, source URLs +
   MD5s included) before rerunning notebooks 01→04.

---

## Core design decisions

### Anchor unit = CDS
- Protein/gene **genomic** boundaries are annotation-defined and fuzzy — do NOT detect de novo.
- CDS boundaries ARE locally defined (start codon → stop codon, known frame).
- Cross-level invariants validated against: `translate(CDS) == protein` and
  `splice(coding exons, strand-corrected) == CDS`.

### Reference download
- Human → **GENCODE** (matched release: genome FASTA + GTF + transcript FASTA + translations).
  Currently pinned to **GENCODE v46**.
- Other mammals → Ensembl. Proteins w/ evidence → UniProt or RefSeq. Canonical anchor → **MANE
  Select**.
- Pin ONE release for the whole matched set; verify against provided MD5SUMS.
  **#1 silent error: mixing releases → ID/coordinate drift.**

### Hash schemes (refget-compatible) — DECIDED
- **MD5** of normalized residues, chosen as **primary digest** (samtools/refget-aligned = SAM/BAM
  `M5` tag). The earlier "MD5 vs SHA-256" open question is resolved in favor of MD5.
- **ga4gh SQ** = `base64url(SHA-512(seq)[:24])`, no padding → `SQ.<32 chars>`; VRS form
  `ga4gh:SQ.<...>`. Refget v2 calls this algorithm **`sha512t24u`** — same digest, that's just
  the spec's name for it. Kept alongside MD5 as the stronger digest (independent, not derived
  from MD5). `TRUNC512` (an older refget digest option) is deprecated in refget v2 — don't add it.
- Both implemented in `scripts/gencode_cds_extract.py` (`md5_digest`, `ga4gh_sq_digest`) and
  `notebooks/01_hash_functions.ipynb`.
- The old v1→v3 pipeline's `grep -v '^>' | tr -d '\n' | sha256sum` approach does **not** conform
  to refget (no uppercasing, wrong algorithm) — this is already moot since that pipeline is a
  separate, unrelated effort (see top of this file), not something being migrated.
- **Not yet done:** validating the pipeline against a known-good external reference (e.g.
  hashing a full GRCh38 reference chromosome and confirming it reproduces a published refget/
  `.dict`-file MD5, or hashing a known Ensembl CDS and confirming it matches Ensembl's own
  refget-retrievable checksum). What *has* been validated is one specific protein accession
  (`NP_000198.1`, see Known gaps #4) plus internal invariants (`translate(CDS) == protein`) on
  1341 real chr22 transcripts — a different, narrower kind of check. See TODO.

### Private salt on IUPAC-collapsed hashes — evaluated 2026-09-01, NOT adopted, decision open

Idea raised: hash the IUPAC-collapsed (phase-free, see Track 2) sequence with a secret salt known
only to the user (`hash(salt + iupac_seq)`), so that even someone with the full hash catalog file
couldn't use it to look anything up without also knowing the salt.

**What this would actually defend against.** For genomic sequences, brute-forcing the *original*
sequence back out of an unsalted hash is already infeasible regardless of salting — the search space
of possible sequences is astronomically larger than any realistic rainbow table. The real threat a
salt addresses is narrower and more realistic: an adversary with a *small closed set of candidates*
(reference alleles, gnomAD/ClinVar-cataloged variants, another person's already-known genome) testing
each candidate's hash against your catalog. A secret salt blocks exactly that — without it, nobody
can precompute `hash(salt + candidate)` to compare.

**Pros:**
- Blocks candidate-matching attacks (re-identification against public variant catalogs) for hashes
  of **private, real individuals' data** — this doesn't apply to the GIAB/1000G data currently in
  this repo, since that's already public; it would matter if this pipeline is ever pointed at actual
  private samples.
- Combines naturally with the IUPAC layer already planned for Track 2 (phase-free, single hash per
  person per CDS) — same place in the pipeline, same motivation (don't expose more than necessary).

**Cons:**
- **Directly conflicts with this project's own refget-compatibility goal.** The entire reason MD5 +
  `sha512t24u` was chosen (see above) was to be comparable with samtools/refget/Ensembl/NCBI public
  checksums. A salted hash can never match a public checksum, by design — salting and
  refget-interoperability are mutually exclusive for the *same* hash column. (Could keep both: an
  unsalted refget-compatible column for validation, plus a separate salted column for
  access-controlled sharing — real added complexity, and the unsalted column still leaks everything
  if it's ever shared alongside the salted one.)
- **The salt becomes a single point of failure.** Lose it, and the *entire* catalog becomes
  permanently unverifiable and unreproducible — including for legitimate future use by the same
  person. This directly undercuts the exact property this project relied on all through
  2026-08-31/09-01: reproducing the same hash across machines to confirm correctness. A leaked salt,
  unlike a per-record random salt in password systems, compromises the *whole* catalog at once, not
  one record.
- **MD5/truncated-SHA512 were never chosen as security primitives** — they were chosen for
  refget-alignment and content-addressing, not resistance to a determined attacker. Naive
  `hash(salt + seq)` concatenation is weaker than it feels; a real security-grade construction would
  need HMAC-SHA256 or similar, a different primitive from what's used here.
- **Doesn't obviously add protection beyond what IUPAC-collapse already provides.** IUPAC collapse
  already removes phase information (a different concern) — salting addresses *lookup* resistance,
  a separate threat. Worth being explicit about which specific threat is actually being defended
  against before adding the complexity.

**Recommendation, not yet actioned:** don't adopt for the current GIAB/1000G-only dataset (nothing
private to protect yet, and it would break refget interop for no benefit). Revisit specifically if/
when real private individuals' sequences are ever hashed — and if so, keep unsalted + salted as
separate columns rather than replacing the refget-compatible one, and use a real keyed-hash
construction (HMAC) rather than concatenation.

#### Follow-up, 2026-09-01: a client-lookup service built on this — two open protocol questions

Extending the idea into an actual service: publish the salted hashes so a client can check their
own DNA sample against them, while keeping the mapping from salted hash → gene/accession private.
Worked through the architecture and a specific protocol variant; **neither is decided, both
recorded here so the tradeoffs don't have to be re-derived later.**

**Database structure (this part has a clean answer): two databases, not one.**
1. **Public**: bare list of salted hash values only — `(salted_hash_md5, salted_hash_sq)`. No
   accession, no `gene_id`, no `evidence`, no `source`. The only thing ever published.
2. **Private**: mapping table — `(salted_hash_md5 → accession, gene_id, source, ...)` —
   essentially today's schema, keyed by the salted hash instead of the plain one. Never
   committed anywhere public; the salt itself lives here too (or better, in a separate secrets
   store, not even in this DB).

**The unavoidable tension: for the client to compute a matching salted hash at all, whoever runs
that computation has to know the salt** — it cannot stay purely server-side if the client is doing
the matching. Two variants, evaluated:

**Variant A — salt embedded in client-side software, matching happens entirely locally.** The
client's raw sequence never leaves their machine. Real limitation: a secret embedded in
distributed software is only *weakly* secret — extractable via reverse-engineering or memory
inspection by a sufficiently motivated party, the same limitation every DRM scheme and every API
key embedded in a mobile app hits. This raises the bar against casual snooping; it does not make
the salt cryptographically unrecoverable. Once someone has the salt this way, they're in the same
position as an attacker in variant B below (see the candidate-attack paragraph) — they can test
known candidate sequences against the public list, but still can't reverse an arbitrary published
hash back into an unknown sequence.

**Variant B — server sends the client a unique per-session salt; client hashes locally and sends
the result back; server looks it up.** Analyzed in detail 2026-09-01 — **this does not achieve the
"client's data known only to the client" goal**, and the reason is more concrete than "the server
has to be trusted" in the abstract:

- This is not hash inversion — knowing the salt gives no mathematical shortcut to invert MD5 or
  SHA-512. What it enables is a **candidate/dictionary attack**: the server (which generated the
  salt, so always knows it) computes `hash(salt + candidate)` for every candidate sequence it can
  enumerate, and checks for a match against what the client sent.
- **Human genetic variation makes that candidate list small and realistic, not astronomical.**
  dbSNP/gnomAD/1000 Genomes already catalog essentially every common variant at nearly every
  locus. For one gene's CDS, "reference + every combination of known cataloged variants at that
  gene's variant positions" is often a few hundred candidates, not billions — entirely tractable
  to hash and check, per gene, per client.
- **The client's own novel-vs-cataloged distinction is the exact right boundary.** A genuinely
  novel variant (not in any public catalog) has no enumerable candidate list, so it stays
  protected — hashing is effectively one-way there. But most of any real individual's genome
  *is* reference or already-cataloged common variation; what makes a person's genome distinctive
  is the *combination* of many common variants, not that each one is individually rare. So this
  variant leaks the majority of a real genome's content to the server, protecting only the
  minority that's genuinely novel.
- **Unique-per-client salting doesn't fix this and it's easy to think it does.** A fresh salt per
  session raises the cost for a third-party eavesdropper on the wire (can't reuse one precomputed
  table across every client) — a real, worth-keeping benefit. It does nothing against the server
  itself, which always knows its own salt by construction, no matter how often it's rotated.

**Net assessment:** variant A (local, embedded salt) keeps raw sequences off any server, at the
cost of the salt itself being only weakly secret against reverse-engineering. Variant B (server
salt, client sends hash back) keeps the salt genuinely secret from outsiders, but hands the server
almost everything it needs to reconstruct the non-novel majority of the client's sequence via
candidate attack — trading one trust problem for a different, arguably worse one. **Neither is a
free lunch; there is no protocol here that gives "a third party can correctly compute and compare"
and "the raw sequence is seen by no one but the client" simultaneously without materially heavier
machinery** — Private Set Intersection, homomorphic encryption, or a genuine trusted-execution
enclave. Worth naming as the real answer if this property turns out to be a hard requirement, but
it's a substantially bigger build than salting, and not warranted unless variant A's weaker
guarantee proves insufficient in practice.

### Normalization (mandatory before hashing)
- Uppercase; residues only; strip whitespace/newlines.
- **Protein:** keep initiator Met; NO trailing stop.
- **CDS nucleotide:** stop-codon inclusion must be explicit — see the table below.

### Stop-codon convention table — READ BEFORE CATALOGING (three conventions in play; pick deliberately)

| Source | CDS includes the stop codon? |
|---|---|
| GENCODE/Ensembl GTF `CDS` feature | **No** — stop is a separate `stop_codon` feature |
| GENCODE `pc_transcripts.fa` `CDS:` header span | **Yes** |
| NCBI RefSeq CDS (GenBank CDS feature) | **Yes** |
| Ensembl CDS sequence (REST `type=cds`) | **Yes** |
| **Our current hash** (`cds_seq`/`cds_md5`/`cds_sq` in `gencode_cds_extract.py`) | **No** — stop excluded, `len(cds_nt) == 3*len(protein)` (verified) |

Mismatching this assumption causes a silent 3-nucleotide offset. `scripts/gencode_cds_extract.py`
(`build_catalog`) handles both GENCODE-side cases explicitly: it compares the raw span length
against `3*(len(protein)+1)` (stop included) vs. `3*len(protein)` (stop excluded) and slices
accordingly. Confirmed empirically on chr22: reproduces the documented off-by-3 as a consistent
3nt offset across all 1398 chr22 CDS-transcripts checked.

**Consequence, not yet acted on:** because our stored `cds_md5`/`cds_sq` are stop-excluded, they
will **not** match an external NCBI/Ensembl CDS checksum out of the box (those include the stop).
Protein hashes are unaffected and do match external protein digests. To be comparable to the
standards without changing our internal canonical form, the plan (not yet built — see TODO) is
to store **both**: `cds_nt` (stop-excluded, our internal canonical) and `cds_nt_withstop`
(stop-included, for external cross-checks), with an explicit `cds_stop_included` boolean column
in the SQLite schema so the convention travels with every row.

**Also verified, a standing caution:** per-exon chunks are individually **not codon-aligned** —
confirmed by inspecting several real multi-exon chr22 transcripts (codons routinely span an
exon-exon junction; only the whole spliced CDS is guaranteed to be a multiple of 3). Never
`translate()` a lone exon chunk on its own.

### Why no stop codon in the protein layer
1. Stop encodes no amino acid → not part of a protein sequence.
2. UniProt/GENCODE translations and refget protein hashes exclude it; a trailing `*` mismatches
   every public hash.

### Start codon / initiator Met
- Keep Met in the hashed bytes (translated CDS + UniProt canonical both start with Met even if
  cleaved in vivo).
- Flag N-terminal processing / start confidence as metadata — never edit the hashed bytes.
- One confirmed case on chr22: `YPEL1-204` (`non_ATG_start` tag) — a near-cognate start codon
  translates differently only at position 0; accepted as a documented override, not patched.
  Handled explicitly in `scripts/gencode_cds_extract.py`.

### Repeat / low-complexity flagging — NOT YET IMPLEMENTED
- Design: store as separate metadata, never by lowercasing (uppercasing before hashing erases
  soft-masking). Nucleotide: `dustmasker`/`tantan`. Protein: `segmasker`/SEG.
- Current state: the SQLite schema already has a `low_complexity_frac` column, but it is `NULL`
  for every row — this step has not been built yet. See [Active TODO](#active-todo).

### Evidence flag (experimental vs. predicted)
- RefSeq prefix: `NM_/NP_` = curated; `XM_/XP_` = Gnomon prediction.
- UniProt: PE1 (evidence) .. PE4 (predicted) .. PE5; Swiss-Prot (reviewed) vs. TrEMBL.
- GENCODE: transcript `level` 1/2/3, TSL 1–5, tags (e.g. `MANE_Select`).

### Storage
- Raw downloads: read-only, gzipped as-downloaded, + `manifest.tsv` (source URL, release, date,
  MD5) — see `data/reference/manifest.tsv`, `data/giab/manifest.tsv`.
- Working FASTA: `pyfaidx`-indexed (plain-text, not bgzip). Chosen originally because the
  Windows dev machine had neither `samtools` nor `bgzip` natively — but the fuller root cause
  (clarified 2026-08-31, from direct recollection, not previously documented): VS Code on that
  machine had briefly auto-linked to a WSL-hosted Python interpreter/kernel early on, so it
  looked briefly like WSL tools were reachable, then stopped working when that implicit link
  broke — a known failure mode of picking a WSL interpreter path (`\\wsl$\...`) from
  Windows-native VS Code without the actual **Remote-WSL** extension mediating the connection.
  In that half-connected state the Python kernel can still run, but shell/`%%bash` subprocess
  calls resolve against the wrong PATH, so WSL-only binaries like `samtools`/`bcftools` become
  invisible even though "the kernel" nominally still works — plain Python (pyfaidx, no
  subprocess calls) was what kept working regardless. **Recommendation if a Windows/WSL machine
  is ever used for this project again:** use the Remote-WSL extension properly (`code .` from a
  WSL terminal, or "Reopen in WSL"), which runs the whole dev environment as one persistent
  process inside WSL instead of an opportunistic cross-boundary link — and keep project files on
  the WSL filesystem (`~/...`), not `/mnt/c/...`, since that's the main performance cost of that
  approach. Moot on the current native-macOS setup (no Windows/WSL boundary exists), but
  documented here since it's the real reason this workaround exists, not just "no samtools
  installed." Revisit the plain-text choice itself now that both Macs have Homebrew `samtools`/
  `bgzip` natively — see the bgzip-vs-pyfaidx tradeoff note below.
- **bgzip+`samtools faidx` vs. the current plain-text+`pyfaidx` blob store — not yet switched,
  evaluated 2026-08-31.** Advantages of switching: ~4x disk savings via BGZF (compressed, but
  keeps random access, unlike plain gzip) — negligible at chr22 scope, real at whole-genome/
  many-individual scale; consistency with the rest of the pipeline (raw downloads and VCFs are
  already gzip/bgzip-family, handled via `samtools`/`bcftools` — the derived blob store is
  currently the one place bypassing those tools for a bespoke Python writer); matches the
  original design intent (bgzip+samtools was the original spec; plain-text was purely the
  Windows-workaround above, which no longer applies); and it's the native input format for
  `bcftools consensus`, likely needed for personalized whole-genome FASTAs later. Advantages of
  keeping plain-text/pyfaidx: zero subprocess dependency (pure Python, nothing to go missing
  across machines), trivially greppable/diffable. **Verdict:** not worth switching for chr22-
  scope work — revisit specifically when/if this scales past a single chromosome or starts
  generating personalized whole-genome FASTAs.
- **Line-ending consistency fix, 2026-09-01.** Noticed by diffing `chr22_cds.fa.fai`'s `LINEWIDTH`
  column across machines: 61 on the Mac mini, 62 in the original Windows-generated file (same
  `LINEBASES`=60 both times). Root cause: `write_fasta()` used plain `open(path, "w")`, and Python
  translates outgoing `\n` to the OS's native line separator on write unless `newline=""` is
  passed — `\n` (1 byte) on macOS/Linux, `\r\n` (2 bytes) on Windows. **Not a sequence-correctness
  bug** — `.fai`-based random access already accounts for however many terminator bytes are
  actually present in a given file (that's what `LINEWIDTH` is *for*), confirmed by this session's
  many cross-platform hash matches despite this quirk existing the whole time — but worth fixing
  for portability/diff-cleanliness before it causes real confusion. Fixed in both
  `notebooks/03_sqlite_catalog.ipynb`'s `write_fasta()` and `scripts/validate_against_ensembl.py`'s
  `write_fasta_gz()` by adding `newline=""` to the `open()`/`gzip.open()` calls — LF-only
  regardless of OS from now on. No-op on the Mac (already LF); matters only if this project ever
  runs on Windows again. Not yet regenerated on disk — takes effect next time notebook 03 is rerun.
- Hash catalog: SQLite, one row per sequence: `hash_md5, hash_sq, seq_type(AA|CDS|cDNA|exon),
  accession, gene_id, source, release, evidence, length, low_complexity_frac`. Indexed on
  `hash_*` and `gene_id`. Sequence bytes are not duplicated — FASTA is the blob store, retrieved
  by `faidx`.

### Notebook / tracking workflow
- Hybrid: Jupyter Python kernel + `%%bash` cell magic. Notebook for exploration; promote settled
  steps to numbered scripts under `scripts/` once validated (as done for
  `gencode_cds_extract.py`). Log tool versions.

---

## Known gaps / bugs (verified against code)

1. **Selenocysteine categorization gap (notebook vs. promoted script) — root cause verified
   directly against the chr22 GTF, corrected from an initial mis-diagnosis.**
   There are **10 selenoprotein transcripts on chr22, across 3 genes — `SELENOM`, `SELENOO`,
   `TXNRD2`** (confirmed by parsing `data/reference/gencode.v46.basic.annotation.gtf.gz`
   directly; earlier notes in this repo only ever named `TXNRD2`, undercounting the gene list).
   An internal in-frame UGA in each is biologically recoded to selenocysteine, which a naive
   codon-table translation reads as a premature stop.
   - All 10 of these transcripts **do** carry a `seleno` tag on their GTF `transcript` line
     (verified directly — e.g. `TXNRD2` transcript `ENST00000400521.7` has tags
     `[..., 'MANE_Select', ..., 'seleno']`), and `parse_gtf_chrom` already parses transcript
     tags generically into `t["tags"]` for every transcript, same code path used for the
     `non_ATG_start` check. So an initial guess that the tag "doesn't exist" / is sourced from
     the wrong GTF column was **wrong** — checked and ruled out.
   - The actual, verified gap: **`build_catalog` simply has no branch that checks
     `"seleno" in t["tags"]`** — unlike `non_ATG_start`, which does get an explicit override.
     All 10 selenoprotein transcripts fall through to the generic `"translate_mismatch"`
     flagged reason (confirmed by running the script: all 10 known selenoprotein transcript IDs
     map to `translate_mismatch`, and it's exactly 10/10 of that bucket). Fix is a one-branch
     addition to `build_catalog`, no `parse_gtf_chrom` changes needed:
     `elif "seleno" in t["tags"]: flagged.append((tid, "selenoprotein")); continue`.
   - Separately (confirmed real, but not the cause of this bug): GENCODE also emits a distinct
     `Selenocysteine` GTF feature line (column 3) at the exact genomic position of the recoded
     codon, for the same 10 transcripts. `parse_gtf_chrom` currently discards it (only keeps
     `f[2] in ("CDS", "transcript")`). Not needed to fix the categorization bug above (the tag
     already suffices), but useful for a **future** enhancement: recoding that specific codon to
     `U` before translation so these 10 could be promoted *into* the catalog instead of merely
     excluded-with-a-reason. Not fixed — flagged as an open gap (see TODO).
2. **Off-by-3 stop codon** — handled correctly (see table above), not a live bug.
3. **`non_ATG_start` (YPEL1-204)** — handled correctly as a documented override in
   `gencode_cds_extract.py`.
4. **Wrong worked-example accession in the original design doc.** The original handoff cited
   `NP_000207.1` for human preproinsulin — that accession is actually Kallmann syndrome 1
   protein (ANOS1, 787 aa), confirmed live against NCBI eutils. Corrected accession:
   `NP_000198.1` (110 aa); its sequence reproduces the originally-stated MD5
   (`12e9c9e4e2835c302e8ba615115edda3`) and SQ (`SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`) exactly —
   only the accession label was wrong, not the hash formulas. Fixed and reverified in
   `notebooks/01_hash_functions.ipynb` on the Mac mini kernel, 2026-08-29.
   **General guardrail from this incident:** NM (mRNA) and NP (protein) RefSeq numbers are
   **not** paired by their digits — e.g. insulin mRNA is `NM_000207` but its protein is
   `NP_000198`, not `NP_000207` (which is the unrelated ANOS1 gene above). Never infer one
   accession from the other; resolve the actual pairing from the live record (NCBI eutils or
   equivalent) every time.
5. **GIAB "standard" benchmark VCF is not phased.** An early assumption that
   `HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` carries trio/StrandSeq phasing was wrong for that
   specific file (0/50,284 chr22 variants phased, checked empirically). The actual phased file is
   a separate supplementary release,
   `HG002_GRCh38_1_22_v4.2.1_benchmark_phased_MHCassembly_StrandSeqANDTrio.vcf.gz`, found by
   browsing GIAB's FTP directory rather than guessing a filename — and even that file is only
   43.6% phased on chr22 (21,944/50,284 variants).
6. **`_benchmark_noinconsistent.bed` approach abandoned.** Originally planned to use this BED to
   resolve `no_parental_match` cases; GIAB's own `README_v4.2.1.txt` (line 7) shows it's just the
   primary high-confidence region file already implicit in the benchmark VCF's PASS filter, not a
   trio-Mendelian-consistency filter — confirmed empirically too (the known-artifact site falls
   *inside* this BED's intervals, which would be impossible if it excluded Mendelian
   inconsistencies). Dropped in favor of the `difficultregion` INFO tag instead.

---

## Data facts (verified, chr22, GENCODE v46)

- chr22 transcripts with CDS entries: **1404**; present in both FASTAs: **1398**.
- **1341/1398 (96%)** pass both the splice-length invariant and `translate(CDS) == protein`.
- All 57 exceptions explained, none unexplained (flagged-reason breakdown in
  `scripts/gencode_cds_extract.py` terms: 41 `length_mismatch` + 6 `unexpected_length_ratio` = 47
  incomplete-CDS cases + 10 `translate_mismatch` = selenoprotein cases):
  - 47 incomplete CDS annotations (`cds_start_NF`/`cds_end_NF`/`mRNA_start_NF`/`mRNA_end_NF`
    tags — mostly IG/TR immune-receptor gene segments, e.g. `IGLV4-69`, which genuinely lack a
    stop codon pre-V(D)J-recombination).
  - 10 selenoprotein transcripts across `SELENOM`, `SELENOO`, `TXNRD2` (see gap #1 above).
- SQLite catalog: **16,176 rows** = 1341 AA + 1341 CDS + 13,494 exon hashes, across 443 chr22
  genes. Round-trip verified (SQLite hash → FASTA lookup → re-hash → matches). Originally built
  2026-07-03 on the Windows/WSL2 machine; **reproduced exactly on the Mac mini 2026-08-31** (see
  [Current state](#current-state-verified-against-the-filesystem-not-just-prose) — same counts,
  byte-for-byte identical hash spot-checked directly).
- **Track 1 result** (notebook 04; originally run 2026-07-03 on Windows/WSL2, **reproduced
  exactly on the Mac mini 2026-08-31** — every number below matched on both platforms, checked
  directly against the live SQLite catalog, not just re-trusting old printed output — of 1341
  validated transcripts):
  - **431 confident parent-of-origin calls** (201 paternal + 230 maternal haplotypes).
  - 675 uninformative (variant shared by both parents — the Mendelian-uniqueness caveat).
  - 681 trivial (no variants in the child for that CDS).
  - 75 flagged `phase_incomplete`; 30 flagged `has_indel` (SNV-only scope this round).
  - 4 flagged `no_parental_match`, all four tracing to **one** locus (gene `ENSG00000100033`,
    across 4 transcript isoforms): neither parent has any VCF record at that position (implied
    homozygous-reference), child is heterozygous, and the site carries GIAB's own
    `difficultregion=hg38.segdups_sorted_merged,lowmappabilityall` tag — a mapping-artifact
    signature, not a real de novo call.
  - Difficult-region overlap by category (precise per-category figures, from the Mac mini run):
    `uninformative_shared` 59/675 (8.7%), `maternal_origin` 18/230 (7.8%), `paternal_origin`
    15/201 (7.5%), `no_parental_match` **4/4 (100%)** — confident calls (maternal+paternal)
    combined: 33/431 (7.7%). The gap between ~7.7% background and 100% for `no_parental_match`
    is the actual evidence for "mapping artifact, not real de novo," not just the single-digit
    count.
- Counts/expectations (design-time estimates, not all re-verified against chr22 data above):
  human protein-coding genes ≈ 19,400 genome-wide; chr22 protein-coding genes ~495 (Ensembl
  115/GENCODE v49) → ~490 MANE transcripts; reference baseline (protein + CDS + per-exon)
  ≈ ~5,000 distinct sequences; full GIAB trio POC total ≈ 7,000–8,000 distinct hashes
  (~15k rows) — trivial for SQLite.

---

## Finding: Track 1's classification does NOT confirm paternity (empirical false-positive test, 2026-09-01)

Prompted by the direct question "does this confirm 100% paternity?" — answer: **no**, and this was
verified empirically, not just argued structurally.

**Why not, structurally:** `explainable_by()` in notebook 04 is a binary per-site allele-membership
test — it already *assumes* HG003/HG004 are the parents and asks "is the child's allele consistent
with this assumed parent." It has no concept of population allele frequency and never combines
evidence across sites into a single statistic. That's fundamentally different from what real
paternity/forensic testing computes (see LR-based analysis, below).

**Empirical test:** substituted `NA19240` (a 1000 Genomes YRI sample — different population, zero
family relation to the Ashkenazi GIAB trio) for HG003 (the real father), and reran the *exact same*
`explainable_by()` logic against the 201 haplotypes that notebook 04 confidently calls
`paternal_origin` with the real father. Fetched via `bcftools view -R <CDS-region BED file> -s
NA19240 <1000G high-coverage chr22 URL>` — full method note: a whole-chromosome single-sample
remote fetch from this particular 2,504-sample file was tried first and was far too slow (~40 minutes
for 0.57% of chr22 — see [Active TODO](#active-todo), item on download strategy); restricting to a
BED file of just the 4,186 CDS-exon blocks (0.7 Mb vs. chr22's 40.3 Mb) made it tractable. Both
`NA19240_chr22_cds.vcf.gz` and the BED file are in `data/giab/impostor_test/` (gitignored via the
existing `*.vcf.gz` pattern — machine-local, not committed). The classification logic itself is
saved as a reusable script, `scripts/impostor_test.py` (reuses notebook 04's functions verbatim,
committed and runnable — verified to reproduce the numbers below exactly), so this test can be
rerun against a different impostor sample or after any pipeline change without hand-copying code
into an ad-hoc script again.

**Result:**
- Of the 201 real `paternal_origin` haplotypes, **71 (35.3%) are ALSO "explainable by" the random,
  unrelated impostor** — a coincidental allele match at that single locus. **130 (64.7%) correctly
  exclude the impostor.**
- Those 201 haplotypes span only **64 distinct genes** — the real effective sample size is much
  smaller than 201, because haplotypes from the same gene aren't independent evidence (see LD, below).
- Treating the 64 genes as roughly independent (a simplification — see caveat below) and using the
  35.3% single-locus miss rate, the joint probability of an unrelated person passing at *all* 64
  gives `0.353^64 ≈ 10⁻²⁹` — vanishingly small, even though any single locus is weak evidence alone.

**Linkage disequilibrium (LD) — why 201 isn't 201 independent tests.** LD is the non-random
association between alleles at two positions because they're physically close on a chromosome and
therefore usually inherited together — recombination (the process that shuffles alleles between
generations) rarely lands between two nearby positions in any given meiosis, so whatever allele
combination existed on that chromosome generations ago tends to still travel together as a block
("haplotype"). Multiple transcripts of the *same* gene share the same underlying genomic stretch by
definition (this is exactly why two isoforms of `ENSG00000177663` independently agreed on
maternal/paternal assignment in notebook 04's own worked example) — so collapsing to distinct genes
(64) is a rough correction, and even that's generous: nearby *different* genes on chr22 can still
share some LD that a gene-level count doesn't capture. A rigorous number would need actual
recombination-distance data between loci, which hasn't been computed.

**LR-based analysis — what real paternity testing computes that this pipeline doesn't.** For one
marker: `LR = P(child's genotype | this man IS the father) / P(child's genotype | a random unrelated
man)`. The denominator is where population allele frequency enters — a common allele (e.g. 30%
frequency) gives a weak LR even on a true match, because random people carry it often anyway
(exactly what the 35.3% single-locus miss rate demonstrates); a rare allele (e.g. 0.1%) gives a
strong LR, since almost no random person would carry it by chance. Real forensic panels (CODIS STRs,
curated SNP panels) are deliberately chosen on *different chromosomes or far apart* specifically so
LD between markers is negligible — genuine independence, unlike the 64-genes-on-one-chromosome
situation here. Under real independence, the **Combined Paternity Index** is the *product* of each
locus's LR, and with ~15–20 well-chosen markers that product routinely reaches billions or trillions;
standard Bayesian math (`posterior odds = CPI × prior odds`, prior conventionally 50% absent other
evidence) then converts that into the "99.99%+ probability of paternity" figure forensic labs report.
`explainable_by()` computes neither piece — no allele-frequency weighting, no product across loci, no
posterior probability. It's a useful binary consistency check for tracing inheritance *given* an
assumed relationship; it cannot produce a real paternity-confidence number as implemented.

---

## External validation against Ensembl (2026-09-01)

**Question that prompted this: is there a public "database" of reference checksums to just
download and compare against, instead of hashing something ourselves?** Short answer: **no, not
as a bulk-downloadable file.** GA4GH refget is an *API* spec — refget servers (NCBI, Ensembl,
others) let you query "does this checksum exist" one sequence at a time; there's no static dump of
"every checksum for every human transcript" to fetch. The practical alternative, and what was
actually done here: pull the *reference sequences themselves* from a second independent,
authoritative source, and hash-compare against what this pipeline independently derives from
GENCODE. If they match, the hash formulas *and* the extraction logic are both validated at once —
this is a **stronger** check than comparing precomputed checksums would have been, since it also
re-validates `translate(CDS) == protein` against an independent implementation, not just our own.

**Release matching, confirmed not assumed:** GENCODE v46's own GTF header states
`version 46 (Ensembl 112)` directly — checked in the file, not looked up externally. Used Ensembl
release 112's own CDS and protein FASTA downloads (`https://ftp.ensembl.org/pub/release-112/
fasta/homo_sapiens/{cds,pep}/`), each ~15–23 MB compressed genome-wide, verified against Ensembl's
published `CHECKSUMS` file (BSD `sum` format) before use.

**Result — full match, 1341/1341 both ways:**
- **Protein layer** (no stop-codon ambiguity at all): all 1341 chr22 protein sequences
  byte-identical to Ensembl's independently-sourced protein FASTA; MD5 hashes match.
- **CDS layer**: Ensembl's CDS FASTA includes the stop codon (per the documented convention
  table above); this project's canonical `cds_seq` excludes it. Reconstructed the stop-included
  form on the fly (`cds_seq + last 3 nt of Ensembl's sequence`, i.e. exactly the `cds_nt_withstop`
  idea from the open TODO, applied ad hoc rather than as a schema column yet) — all 1341 match
  exactly, hashes included.
- Zero mismatches on either layer. This is the external validation the "Not yet done" note under
  Hash schemes was waiting on.

**Reusable script:** `scripts/validate_against_ensembl.py` — downloads nothing itself (points at
the already-fetched files in `data/reference/validation/`), rebuilds the chr22 catalog, and reruns
both comparisons. Also writes small chr22-only subset FASTAs
(`data/reference/validation/chr22_ensembl112.{cds,pep}.fa.gz`, ~1.1 MB combined) so the full
23+15 MB genome-wide downloads don't need to be committed or re-fetched to rerun this check —
those stay gitignored (`data/reference/validation/manifest.tsv` records their source URLs/MD5s if
they're ever needed again).

**Answering "best way to collect these, starting with chr22, going forward":** this
per-chromosome extract-and-cross-validate pattern *is* the recommended approach — there's no
better shortcut than a real second source. To extend past chr22: rerun
`load_ensembl_fasta(..., chrom_tag="<N>")` for whichever chromosome, no new design needed, since
the genome-wide Ensembl files already cover everything — only the chr22-filtering step needs the
chromosome argument changed. The same genome-wide Ensembl downloads already on disk can validate
every other chromosome too, at zero extra download cost.

---

## Scaling to genome-wide and population scale (2026-09-02)

Real (not simulated) measurements, taken to answer "would precomputed hashes actually help, and
what would it cost to build the full thing" before committing engineering time to it.

### Genome-wide reference catalog: fast, already proven

Ran the real extraction+hashing pipeline (reused `scripts/gencode_cds_extract.py` verbatim, just
without the chr22 filter) against the actual genome-wide GENCODE v46 files already on disk — no
new download needed, they were never chr22-only, only chr22-*filtered* by the existing code:

| Phase | Time |
|---|---|
| Parse GTF, all chromosomes | 5.6s |
| Load transcript FASTA | 1.2s |
| Load protein FASTA | 0.3s |
| Build catalog (extract, translate, validate, hash MD5+SQ) | 5.6s |
| Salted MD5 pass (protein+CDS+exon, 790,842 additional hashes) | 0.5s |
| **Total** | **13.2s** |

**64,414 validated transcripts, all isoforms, whole genome, unsalted *and* salted, in 13 seconds.**
Confirms hashing itself was never the bottleneck anywhere in this pipeline — the salted pass adds
half a second on top of 12.7s of real work. This was a timing measurement only; nothing was
written to any database (verified directly — no `sqlite3`/`INSERT` calls in the script that ran
this). The real `hash_catalog.db` is unchanged, still chr22-only.

### Per-individual processing: the real bottleneck, found and diagnosed

Timed the actual per-individual haplotype-extraction-and-hashing code (the logic notebook 04 and
`scripts/impostor_test.py` both use) against real HG002 chr22 data:

- **11.76s for ONE individual, chr22 only** (1,341 transcripts) — compare to 5.6s to build the
  *entire genome's* reference catalog with zero individuals. One person on one small chromosome
  costs more than the whole-genome reference build.
- **Root cause, found by inspection, not guessed**: `variants_in_range()` does a linear scan of
  *every* variant in the chromosome, for *every* exon, of *every* transcript —
  `[(pos, v) for pos, v in sample_vcf.items() if start <= pos <= end]`. For chr22 alone that's
  roughly 1,341 transcripts × ~10 exons × 50,284 variants ≈ **670 million comparisons per
  individual**. A real, fixable software inefficiency (no sorted/interval index on variant
  positions) — not an inherent cost of the problem.
- Extrapolated to genome-wide (× 48, by transcript count): **~9.4 min/individual** — flagged as
  likely an *underestimate*, since the bottleneck scales with variants-in-chromosome too, not
  transcript count alone, and chr22 is one of the sparser chromosomes on both counts.
- All 1000 Genomes (2,504 individuals), sequential, single-threaded, unoptimized: **~16.4 days**
  — a rough order-of-magnitude floor for *this exact code as written*, not a statement about the
  problem's real difficulty. The workload is embarrassingly parallel across individuals (fully
  independent, no shared state), and the linear-scan fix below is expected to cut per-individual
  cost by 100–1000x on its own.

### Data acquisition for population-scale sources — verified, not assumed

Checked directly against the actual hosts rather than assumed:
- **1000 Genomes high-coverage data does NOT publish per-sample genotype VCFs** for this release
  — confirmed by browsing the actual FTP directory structure (`20201028_3202_raw_GT_with_annot/`,
  `20190425_NYGC_GATK/`): only joint multi-sample VCFs per chromosome exist there (chr1 alone is
  130GB compressed). Per-sample *CRAM* alignment files do exist (e.g. for the 698-sample
  expansion) but using them means running variant calling from scratch per person — trades a
  data-transfer bottleneck for a much bigger compute one, not a shortcut for genotypes.
- **The same joint VCFs are also mirrored on AWS S3 Open Data** (`s3://1000genomes` /
  `https://1000genomes.s3.amazonaws.com/`) — confirmed by listing the bucket directly, same
  filenames as the EBI FTP mirror. This matters because AWS Open Data buckets have zero egress
  cost for reads, and an EC2 instance in the same region gets far higher throughput than
  internet-routed FTP/HTTPS — the exact bottleneck hit during the impostor-test fetch (streaming
  all 2,504 samples' columns to extract one) gets cheaper per byte, even though the problem's
  *shape* doesn't change.
- **Aspera/FASP support for this specific 1000 Genomes/IGSR mirror: checked, inconclusive.** EBI's
  ENA/SRA infrastructure supports Aspera generally, but a documentation page believed to confirm
  it for this specific resource didn't resolve to real content when fetched (looked like a stale
  URL or client-side-routed page that doesn't serve to a plain `curl`). Recorded as unconfirmed
  rather than asserted either way — worth checking directly in a browser if this ends up mattering.
- The CDS-region BED-restriction technique already used for the impostor test (0.7 Mb vs. chr22's
  40.3 Mb, ~57x smaller) remains useful regardless of which host serves the data.

### Cost estimate for an AWS batch run — CORRECTED 2026-09-03, fetch time dominates

**The estimate below this line is superseded — it only ever counted compute time.** Every
compute benchmark behind it (11.76s, ~9.4 min/individual) ran against
`data/giab/HG002_chr22_phased.vcf.gz`, a file already sitting on local disk. Real 1000 Genomes
individuals aren't local — they have to be fetched from `s3://1000genomes` first via the
BED-restricted `bcftools` technique, and that fetch is now **measured**, not assumed: **~8
minutes per individual for chr22 alone** (`scripts/aws/test_s3_fetch.sh`, 2026-09-03, real
colocated `us-east-1` run). Compute is 0.02–0.04s per individual by comparison — fetch is
roughly **10,000–20,000× the cost of compute**, and the old estimate never included it.

**Genome-wide fetch, extrapolated from two independent real measurements that converge closely**
(not one shaky guess): scaling chr22's 8 minutes by CDS-region count (201,612 ÷ 4,186 = 48.16×)
and by actual base-pair coverage computed directly from the generated BED files (34,756,320 ÷
712,750 bp = 48.76×) — both land within 1% of each other, giving real confidence in **~48×** as
the scaling factor. That's **~6.5 hours of fetch time per individual, genome-wide**.

**Compute + catalog-loading, genome-wide (same ×48 scaling from real chr22 numbers, this time
also measured for the loader, not just extraction/hashing)**: ~10.6s/individual (vcf load+index
+ extraction/hashing + `load_individual_hashes.py`, catalog build amortized as a one-time ~13.2s
cost shared across all individuals) — **confirms this part is still a rounding error**: ~7.4
hours sequential across all 2,504 individuals, or **under 7 minutes** parallelized on a 64-vCPU
instance. Directly answers "how many days for calculations and storing in the catalog": none —
minutes, not days, even without parallelization being especially efficient.

**Total time and cost, per-individual-remote-fetch architecture — SUPERSEDED below by the
bulk-fetch architecture (see further down), kept as the honest fallback comparison, not deleted.**
Range, not a point estimate, since parallel fetch efficiency on a 64-vCPU instance hasn't
actually been measured for this architecture (only one fetch has ever been run at a time):

| Scenario | Effective parallel fetches | Wall-clock | Cost (~$2.7/hr on-demand `c6i.16xlarge`†) |
|---|---|---|---|
| Sequential, chr22-only (reference point, not the real target) | 1 | 13.9 days | — |
| Sequential, genome-wide (no parallelization at all) | 1 | 674 days (~1.85 years) | — |
| **Minimum** (optimistic: near-linear scaling — plausible, since each fetch is latency/CPU-bound on many small HTTP range requests, not bandwidth-bound: only 3.2MB transferred over 8 minutes for chr22, far below the ~62 MB/s raw throughput measured separately) | 64 | **~10.5 days** | **~$680** |
| **Maximum** (conservative: real-world contention — EC2 packets-per-second limits, S3-side overhead, imperfect scheduling — cuts effective parallelism to 1/4) | 16 | **~42 days** | **~$2,730** |

† Back-calculated from the old estimate's implied rate (~$15–20 ÷ 6.5 hrs), not fetched live from
AWS's pricing API — treat as order-of-magnitude, verify before committing real spend.

**This is a dramatically different picture from the old "$6–20, hours not days" conclusion** —
that conclusion was true, just only about the part that was never the bottleneck. Parallelization
was always described as "the workload is embarrassingly parallel," but it was previously optional
for convenience; it's now the difference between ~1.85 years and ~10–42 days, i.e. no longer
optional for feasibility at all.

**TESTED AND CONFIRMED, 2026-09-03 — bulk-fetch architecture is dramatically better, not just
theoretically appealing.** Real test on a live instance: one bulk fetch of chr22's CDS regions
across **all 2,504 samples** (`bcftools view -R chr22_cds_regions.bed <S3 URL>`, no `-s` sample
restriction) took **~9 minutes**, producing a 359MB file (gzip-verified intact, 27,876 variants —
same site count as the single-sample fetch, as expected). From that one **local** file, extracting
individual samples via `bcftools view -s <sample>` took **~10.7s average**, measured across three
different real samples (NA19240, NA12878, HG00096) — remarkably consistent regardless of which
individual. **Per-individual, chr22-only: 480s (old, one remote fetch per person) vs 10.93s (new,
amortized bulk fetch + local slice) — a measured 43.9× speedup**, not an estimate.

The reason this works so well: the earlier diagnosis (region *count* drives cost, not data
volume, since each fetch is CPU/latency-bound on ~4,186 small HTTP range requests, not
bandwidth-bound) predicted this — the bulk fetch pulled 112× more bytes (359MB vs 3.2MB) for
essentially the same wall-clock time (~9 min vs ~8 min), because the number of regions, not
sample count, is what actually costs time remotely. Local slicing afterward has no network
round-trips at all, so it's governed by local disk I/O + decompression, which is fast and — more
importantly — doesn't scale with 2,504 *separate* S3 interactions, just 2,504 *local* ones.

**Genome-wide, extrapolated with the same ×48.46 scaling factor used throughout** (not
independently re-measured for other chromosomes — same caveat as elsewhere: chr1's much larger
underlying file could scale differently than region-count alone predicts):
- One-time bulk fetch, all chromosomes: **~7.3 hours** (not yet tested whether this can itself be
  parallelized per-chromosome across cores — plausible, would shrink this further, not evaluated)
- Local slicing, all 2,504 individuals, parallelized 64×: **~5.6 hours**
- **Total wall-clock: ~12.9 hours (~0.5 days)** — vs. the ~10.5–42 day range above
- **Total cost: ~$35** — vs. the ~$680–$2,730 range above
- **20–78× faster**, and disk space for all chromosomes' bulk files: only **~17.4GB**, trivially
  provisioned

**This changes the recommended Phase 2 architecture, not just its cost estimate.** The
per-individual-remote-fetch numbers above are kept for the record and as the honest fallback if
this doesn't hold up at full genome-wide scale, but bulk-fetch-then-local-slice is now the clear
default plan pending that confirmation. **Not yet built**: neither `batch_haplotype_hash.py` nor
`phase2_deploy.sh` currently implement this two-stage pattern — both still assume a per-individual
remote VCF path. Adapting them (accept a local bulk VCF + sample ID instead of triggering a fresh
remote fetch per invocation) is real, if straightforward, work still ahead of Phase 2.

---

**Original (compute-only) estimate below, kept for the record — superseded by the above:**

Using the real numbers above, spot pricing, and an instance colocated with `s3://1000genomes`:
- **Unoptimized code**: ~392 core-hours total (2,504 × 9.4 min). One `c6i.16xlarge`-class instance
  (64 vCPU) running ~60 individuals concurrently: ~6.5 hours wall-clock. At typical spot pricing
  for that class (~$0.80–1.10/hr) → **roughly $6–10 total**; even fully on-demand, ~$15–20.
- **Optimized code** (after the linear-scan fix): likely low single-digit core-hours across all
  2,504 individuals — **under $5**, probably finishing in well under an hour on one modest
  instance.
- **Caveat**: these are typical/approximate current-ish AWS rates from general knowledge, not
  fetched live from AWS's pricing API. The order of magnitude (single-digit-to-low-double-digit
  dollars, hours not days) is robust to normal price drift; exact current pricing should be
  checked before actually committing spend.
- **Headline conclusion (SUPERSEDED — see above)**: ~~at this scale, cloud compute cost is a
  rounding error next to engineering time.~~ True for compute, not for fetch — fetch dominates
  total cost/time by 3–4 orders of magnitude.

---

## The two tracks (different tools, different goals)

### Track 2 — Distance / population (ancestry) — ACTIVE, current focus (design only so far)
- Cryptographic hashes cannot do distance (avalanche effect). Use MinHash/LSH instead: **Mash**
  or **sourmash** (FracMinHash), k ≈ 21–31. Reference panel: 1000 Genomes chr22 and/or HGDP.
- Reality check: sketch-based pop-gen is emerging for humans, not the mainstream standard
  (mainstream = SNP-based PCA/ADMIXTURE vs. 1000G/HGDP). Good teaching demo, not a solved
  standard.
- **Ethnicity signal is overwhelmingly non-coding** — this track needs whole-genome SNPs, not
  the CDS hashes from Track 1. Reference panels: 1000 Genomes (~2,504 indiv), HGDP (~950),
  SGDP (~300), gnomAD (AF-only). Curated AIM panels: Kidd Lab AISNPs (via FROG-kb/ALFRED),
  Seldin/Kosoy ~128 AIMs.
- POC plan for chr22: extract 1000G+HGDP chr22 → LD-prune → PCA/ADMIXTURE → cross-check against
  Kidd chr22 AISNPs. Common errors to avoid: ascertainment bias (don't pre-pick AIMs — circular;
  run genome-wide first), skipping LD pruning, build/strand mismatches when merging panels.
- Feasibility of ethnicity-from-coding-only (if attempted): shallow — continental super-pop
  (AFR/EUR/EAS/SAS/AMR) resolvable, sub-continental collapses (coding is ~1.5% of genome, plus
  purifying selection/convergent adaptation break the neutral-drift assumption ancestry methods
  rely on). Watch for pigmentation/adaptation genes (SLC24A5, SLC45A2, HERC2/OCA2, EPAS1, LCT)
  being misread as ancestry markers — they track selection, not history. Good teaching point
  about information loss; not a real tool.
- Demo idea (not built): same 1000G+HGDP chr22 samples, PCA on genome-wide/chr22-all SNPs vs.
  coding-only (ideally synonymous/4-fold) SNPs, side by side — expect tight super-pop clusters
  in the first, blurred in the second.
- **DECIDED, 2026-09-02: IUPAC-collapsed genotype representation, not paternal/maternal-separated
  haplotypes, for Track 2.** One phase-free sequence per person per CDS (heterozygous positions
  become the IUPAC ambiguity code — R/Y/S/W/K/M for biallelic SNVs — homozygous positions keep
  the actual base), instead of two separately-hashed haplotypes. Reasoning, not just preference:
  1. **Paternal/maternal labeling mostly doesn't exist for the data ancestry work actually
     needs.** It requires trio genotyping (both parents sequenced); 1000 Genomes/HGDP/gnomAD are
     overwhelmingly unrelated individuals with no parent samples to derive it from. GIAB's trio
     (Track 1) is the special case, not the norm for population panels.
  2. **Ancestry signal doesn't use phase at all.** PCA/ADMIXTURE/F_ST operate on allele
     frequencies or genotype dosage, never on which physical chromosome copy an allele sits on —
     carrying phase into the catalog carries data no downstream ancestry method will ever read.
  3. **Genotype is universal; phase isn't, and this project already measured the real gap it
     causes**: 75/1,341 chr22 transcripts are excluded as `phase_incomplete` in the phased
     approach (see Data facts) — every one of those is usable with IUPAC collapse, which needs no
     phase resolution at all.
  4. **Two arbitrarily-labeled hashes create a label-swap comparison problem IUPAC has no
     version of.** Even where population-level statistical phasing exists (1000 Genomes provides
     it), "haplotype 1" and "haplotype 2" are arbitrary algorithm output, not parent-of-origin —
     comparing person A's hash-1 against person B's hash-1 has no guaranteed correspondence
     without also checking the swapped pairing. One IUPAC value per person per locus has no such
     ambiguity.
  - **Honest counter-case, not ignored**: population-*phased* haplotypes (correctly ordered, not
    parent-labeled) do carry more signal for haplotype-sharing methods (chromosome painting,
    local ancestry inference like RFMix) that detect shared ancestry through identical-by-descent
    haplotype blocks. Not pursued here for two reasons: it needs population-level statistical
    phasing infrastructure this project doesn't have, and — the larger issue — exact-match
    hashing can't do partial haplotype-sharing comparison at all regardless of phasing quality,
    the same avalanche-effect limitation that's already the reason Track 2 is planned around
    MinHash/Mash rather than exact hashes for distance work.
  - Design constraints carried over from the original scoping: separate namespace (never compared
    to the canonical unsalted GENCODE reference hashes — naturally true anyway, since a sequence
    containing R/Y/S/W/K/M isn't valid ACGT and would never collide with the pure-ACGT reference
    catalog, but labeled explicitly rather than left as an accident of the hash space);
    nucleotide-only (not applied to protein sequences); biallelic SNVs only (already guaranteed
    by the existing multiallelic/indel exclusion upstream of this step).
  - **Implemented and verified same day** in `scripts/batch_haplotype_hash.py` (`--mode iupac`,
    now the default; `--mode haplotypes` keeps the original Track 1 behavior available).
    Verified two ways on real HG002 chr22 data, not just run once and trusted:
    (a) `--mode haplotypes` re-checked against the already-verified SQLite catalog after this
    refactor — still 1,110/1,110 exact MD5 matches, confirming the mode split didn't regress the
    existing behavior; (b) the IUPAC output was independently cross-validated by reconstructing
    the expected IUPAC sequence directly from the two already-verified, previously-published
    haplotype hashes (`ENST00000319363.11`, hap0=`186a8719...`/hap1=`1584973f...`, matching the
    notebook 04 worked example exactly) — comparing them position-by-position and applying the
    IUPAC table independently of `build_iupac_collapsed()` produced an identical MD5
    (`3bbd34fa...`) to what the actual function computed. Two independent derivation paths, same
    answer. On chr22: 631 transcripts get a usable IUPAC hash with **zero** phase-related
    exclusions (vs. 556 in `--mode haplotypes`, which still loses 75 to `phase_incomplete`).
  - **Exploratory run kept as a separate file, deliberately not merged into the catalog**:
    `data/derived/chr22/HG002_chr22_iupac.tsv.gz` (631 rows, `--salt 'TodayI$Miercole$'` — a
    local-exploration salt only, see the AWS TODO below) and
    `data/derived/chr22/SALT_DO_NOT_COMMIT.txt`. Both confirmed gitignored before creation, not
    assumed (`data/derived/` is unconditionally excluded). No merge-into-`hash_catalog.db` step
    exists yet — the schema doesn't even have a `seq_type` value for this (`CHECK` constraint
    only allows `'AA','CDS','cDNA','exon'`) or a `salted_hash` column; that stays a deliberate,
    separate future step, not done here.
  - **Row ordering, confirmed against real coordinates**: genomic position along the chromosome,
    not transcript ID — verified by cross-referencing the first several rows' genomic start
    positions in the real GTF (strictly increasing: 16,590,751 → 16,783,412 → ... → 17,085,000).
    Traced to the source: GENCODE ships its GTF pre-sorted by coordinate;
    `parse_gtf_chrom()`/`build_catalog()`/`process_individual()` all just iterate in that same
    order without ever re-sorting, so the ordering is inherited from the reference file, not
    something chosen in this code.
  - **`het_count` column, verified against the actual sequence, not just the code**: count of
    positions that became an IUPAC ambiguity code (heterozygous sites), *not* total variant
    count — homozygous-alt sites are counted in the underlying variant set but get the plain ALT
    base, not a code, so they don't increment `het_count`. Confirmed by reconstructing
    `ENST00000319363.11`'s actual hashed sequence and counting literal `R`/`Y`/`S`/`W`/`K`/`M`
    letters by position: exactly 5, matching the reported `het_count=5` one-for-one.
  - **Clarified: zygosity (hom/het) needs no parental data at all — a different problem from
    phasing.** Easy to conflate given how much of this project is about phasing, so worth being
    precise: hom/het status is ordinary genotype calling from an individual's own sequencing
    reads (allele balance at each site) against the reference — it needs no relatives' data
    whatsoever, and is already present as the `GT` field in every VCF this project uses (`0/0`
    hom-ref, `0/1` het, `1/1` hom-alt), computed by the original data providers before reaching
    this repo. What genuinely *does* need family or population-reference data is **phasing** —
    knowing which physical chromosome copy carries which allele across multiple het sites — a
    fundamentally harder, separate problem. This distinction is exactly why IUPAC collapse works
    at population scale where phasing often doesn't: zygosity is universal, phase isn't.
  - **Why homozygous-alt sites carry real, distinct ancestry signal, not just "more of the same
    heterozygous signal"**:
    1. Standard ancestry methods (PCA/ADMIXTURE) encode genotypes as *dosage* (0/1/2 copies of
       the alt allele), not presence/absence — hom-alt (dosage 2) carries more weight than het
       (dosage 1). Under Hardy-Weinberg, for an allele at population frequency *q*, hom-alt
       occurs at rate *q²* vs. heterozygotes at *2q(1−q)* — for a rare, population-differentiating
       allele, being hom-alt is a much lower-probability, more informative event (both parental
       lineages carried it), not a redundant doubling of the het signal.
    2. **Runs of homozygosity (ROH)** are their own distinct demographic/ancestry signal — long
       stretches of consecutive homozygous genotypes reflect identical-by-descent regions, more
       common in populations with smaller effective population size or founder effects.
       Concretely relevant to data already in this repo: Ashkenazi Jewish populations (HG002/3/4's
       own background) are a documented example of measurably elevated ROH from a founder effect,
       a signal additional to and distinct from standard continental-ancestry PCA.
    3. Specific to this project's own representation: hom-alt/hom-ref positions keep a fully
       specific plain base in the hashed sequence, while het positions fold into a coarser IUPAC
       code — so homozygous positions preserve slightly cleaner per-position signal in this exact
       encoding than heterozygous ones do.

### Parked research questions (raised 2026-09-01, not yet investigated)

Captured with enough context to be actionable later, not just as reminders — deliberately not
answered in depth yet, per explicit request to park them.

1. **Can the most ethnicity-relevant SNPs be estimated/extracted from CDS alone?** Related to the
   already-documented "ethnicity from coding-only regions" feasibility note above (shallow,
   continental-only) — this asks the narrower question of specifically *ranking* coding SNPs by
   population-differentiation power (e.g. F_ST) rather than using the whole CDS panel
   undifferentiated. Methodologically doable (any SNP set can be F_ST-ranked); the open question
   is whether a CDS-restricted top-N set meaningfully outperforms using all CDS SNPs unranked, or
   whether it still hits the same coding-region ceiling regardless of ranking.
2. **Is there a public database of ethnicity-relevant SNPs already, or does one need to be built?**
   Partial answer already on hand, not fully chased down: the AIM panels already named under
   Track 2 above (Kidd Lab 55-SNP/128-SNP via FROG-kb/ALFRED, Seldin/Kosoy ~128) are exactly this,
   genome-wide not CDS-restricted. Also worth checking: EUROFORGEN's Global AIMs panel (forensic
   ancestry inference, ~128 SNPs) — not yet looked into. And notably, **this project already has
   partial access to the raw material for building one**: the 1000 Genomes high-coverage VCF INFO
   fields (seen directly in the NA19240 impostor-test data) already carry per-population
   AC/AF/HWE breakdowns (`AC_EUR`, `AF_EAS`, `AC_AFR`, etc.) — the same kind of per-population
   frequency data an AIM panel is built from, already downloaded, no new source needed to at
   least prototype an F_ST-based ranking.
3. **Hash window size around a SNP — is >20 nt enough for near-uniqueness?** The stated intuition
   is right and already has a name in this project: this is the same reasoning behind Mash's
   k≈21–31 choice (already the Track 2 design, above) — for a ~3×10⁹ bp genome, a random 20-mer's
   expected occurrence count elsewhere is `genome_size / 4^20 ≈ 0.003`, i.e. usually unique.
   **The stated exception (repetitive sequence) is also already a named, tracked gap in this
   project**: low-complexity/repeat flagging (`dustmasker`/`segmasker`) is designed for but not
   yet implemented (see Active TODO). Worth separating two different reasons a window might need
   to be longer than the bare uniqueness minimum, though: mapping-uniqueness (what the k≈20 math
   above answers) vs. capturing enough haplotype-block/LD context around the SNP to carry real
   ancestry signal — those are different constraints that could suggest different window sizes.
4. **Genomic duplications can't be resolved from sequence content alone.** Correct, and this
   project has already run into a real instance of exactly this: the `ENSG00000100033`
   `no_parental_match` case (see Data facts) is tagged `difficultregion=...segdups...` — reads
   from a duplicated/paralogous copy mismapping onto "the" reference copy, which is precisely why
   sequence content alone (what every hash in this catalog is built from) can't distinguish one
   true copy from three. Copy number needs a different signal entirely: read *depth*/coverage
   relative to a diploid baseline, not variant/allele content — a fundamentally different
   measurement from anything this pipeline currently computes.
5. **Interfacing with microarray-based CNV/duplication-deletion data.** This is a genuinely
   different data modality, not an extension of the current pipeline — SNP/CGH arrays measure
   probe hybridization *intensity* (log R ratio, B-allele frequency) at fixed positions, not
   sequence content, and CNV calls derived from them (e.g. PennCNV/QuantiSNP-style output) aren't
   something a sequence-hashing catalog can naturally absorb. Would need its own ingestion path,
   not a hash-catalog extension.
6. **Short reads vs. long reads for ethnicity analysis specifically.** Worth noting the GIAB data
   already in this repo is itself multi-platform — real VCF INFO fields already seen this session
   include `platforms=3;platformnames=Illumina,PacBio,10X` per site. For *ancestry* specifically
   (as opposed to SV/CNV/repeat-resolution work, where long reads matter a lot more): short-read
   data is what essentially all standard population-genetics ancestry work is actually built on
   (1000 Genomes, HGDP, gnomAD are all primarily short-read), because common-SNP-based ancestry
   signal doesn't require long-range phasing or repeat-spanning the way structural-variant or
   de-novo-assembly work does. Long reads would matter far more for items 4/5 above than for the
   SNP-based ancestry work Track 2 is actually planning.
7. **Future direction: classify individuals by population using the hash catalog itself, then
   extend toward functional significance.** Two distinct future extensions worth keeping
   separate: (a) a classifier trained on hash-catalog data across individuals/populations for
   ancestry inference — a further step beyond the already-planned PCA/ADMIXTURE demo above; (b) a
   genuinely new direction not yet named anywhere in this doc — linking hash-identified variants
   to *functional* significance (e.g. ClinVar, gnomAD constraint scores, VEP-style consequence
   prediction), which is a different question from ancestry entirely and would need its own
   design pass when picked up.
8. **Would protein (AA) sequences offer any advantage over CDS/nucleotide for ethnicity work —
   or a path to functional significance once ancestry is determined from AA alone?** Two
   sub-questions, raised together, worth separating: (a) does hashing/comparing at the protein
   level give any *ancestry-inference* advantage over nucleotide level — plausible caveat before
   investigating: protein sequences collapse synonymous codon variation (the same reason
   `cDNA hashes >= AA hashes` always, per the reference-catalog design notes), which likely
   *reduces* available population-differentiating signal rather than adding any, since much
   neutral/near-neutral variation used for ancestry work sits exactly in the synonymous sites
   protein-level hashing throws away — but not yet checked empirically; (b) separately, if
   ancestry/population membership were ever determined using AA-only data, could that same
   AA-level catalog then be reused to map toward *functional* consequence (missense/nonsense
   calls, connecting to item 7b's ClinVar/constraint-score direction) more directly than a
   nucleotide-level catalog would, since protein change is closer to functional consequence than
   the underlying codon is. Not investigated.
9. **Speed advantage of hashing protein sequences instead of nucleotide — for both the reference
   catalog *and* per-individual batch processing, not just the reference.** Two separate
   measurements worth taking, not yet done: (a) reference-catalog build — already have a data
   point suggesting the win is small: proteins are ~3x shorter than CDS (no UTRs, 3nt→1aa), but
   the genome-wide reference build (13.2s total, see above) is dominated by GTF parsing (5.6s)
   and FASTA loading, not by the hashing step itself (the whole salted pass over the full genome
   was only 0.5s) — so a 3x-shorter sequence to hash likely doesn't move the total much; (b)
   per-individual batch processing — genuinely not measured yet, and less obviously small: the
   now-dominant per-individual cost is the ~3.1s reference-catalog rebuild (see the "not yet done"
   note on batch orchestration above), not sequence-level hashing, so switching to AA wouldn't
   address today's actual bottleneck at that layer either. Worth measuring directly rather than
   assuming either way before deciding whether this is worth pursuing.

### Key literature
- Ondov et al. 2016, *Mash* (Genome Biology). Brown & Irber 2016, *sourmash* (JOSS).
- Trio binning (Koren et al. 2018) + yak/meryl parental k-mers + `hifiasm --trio` — the "proper"
  parent-of-origin-by-hash at k-mer granularity.
- Standards: GA4GH **refget** (sequence checksums), **VRS**/`vrs-python` (variant hashing),
  **HGVS** (c./p./g.).

### Track 1 — Exact identity (inheritance / trio) — COMPLETE, kept for reference, not active
- Cryptographic hashes (refget SQ / MD5) of protein + per-exon CDS.
- GIAB trio: HG002 son / HG003 father / HG004 mother, chr22. Chosen over the older pipeline's
  1000G NA12878 trio specifically because this track needs real haplotype-resolved data, and
  GIAB publishes one.
- Caveats: zero error tolerance (per-exon hashing localizes single-base errors); protein-level
  signal is sparse (cDNA/CDS level more informative); needs haplotype-resolved input; Mendelian
  rule only assigns origin where a parental allele is unique; "matches neither parent" is mostly
  artifact (true coding de novo ≈ 1–2/genome) — treat as a QC flag, confirmed above; exon hashes
  only comparable when exon boundaries are identical (anchor to annotation exon IDs).
- Parent-of-origin implemented as a per-site allele-membership test against each parent's
  genotype (not by enumerating parent haplotype combinations) — needs no parental phasing, only
  the child needs to be phased.
- **Status:** fully demonstrated on real chr22 GIAB data (see
  [Data facts](#data-facts-verified-chr22-gencode-v46) — 431 confident calls). This was the
  project's original goal; as of the 2026-08-29/30 pivot it is done and not being extended
  further (indels, low-complexity flagging, spot-checks below are cleanup items, not active
  development).

---

## Active TODO

**Track 2 (ancestry) — active priority, per the 2026-08-29/30 pivot:**

~~0. Fix the per-individual linear-scan bottleneck, refactor for AWS batch processing.~~ —
**core fix done and verified 2026-09-02.** `scripts/batch_haplotype_hash.py` replaces
`variants_in_range()`'s linear scan with a sorted-position index + `bisect` per individual
(sort once per chromosome, binary-search per exon instead of scanning every variant every time).
Measured on real HG002 chr22 data: the haplotype-extraction-and-hashing phase — the part that took
~11.7s before — now takes **0.03s, a ~390x speedup**, exceeding the earlier 100–1000x estimate at
the low end. **Correctness verified, not just speed**: cross-checked all 1,110 overlapping
accessions against the existing, already-verified SQLite catalog — **1,110/1,110 exact MD5
matches, zero mismatches** (the 2 extra rows in the new output are expected: transcripts where
only a *parent* had an indel, which the old trio-wide check excluded but this single-individual
version correctly includes). The script is CLI-driven and writes an isolated per-individual
`.tsv.gz` (no shared-database writes), making it safe to run many in parallel — one process per
individual, e.g. via GNU parallel or a job array. No salt is hardcoded (see the salt-secrecy
discussion above for why that would defeat the point) — pass one via `--salt` or `HASH_SALT`.
**Verified, not assumed**: the AWS S3 mirror URL (`https://1000genomes.s3.amazonaws.com/...`) was
checked end-to-end with a real `bcftools view -h` call, not just a bucket listing.
**Not yet done**: the reference-catalog rebuild (currently ~3.1s locally, ~7.3s on the smoke-test
instance, now the dominant cost per individual since the real bottleneck is fixed) is redundantly
rebuilt on every invocation — a batch orchestrator should build it once and reuse it across all
individuals rather than have each process rebuild it independently.

**Phase 1 AWS smoke test: done and passed, 2026-09-03.** `scripts/aws/` (`launch_smoke_test.sh`,
`deploy_and_test.sh`, `terminate.sh`, `README.md`) launches one instance, deploys the minimal
file set (~92MB: both scripts + GENCODE reference + one real individual's chr22 VCF), runs
`batch_haplotype_hash.py --mode iupac` on it, and diffs the result against the already-verified
local hash. Result: **byte-identical** — `ENST00000319363.11` → `hash_md5=3bbd34fa...`,
`het_count=5`, matching the Mac mini run exactly. 631 hashes written, 687 no-variant + 23
indel-containing transcripts correctly skipped, full pipeline ran in 7.76s on-instance. This
confirms the pipeline is correct on real AWS Linux (Amazon Linux 2023, Python 3.9.25
preinstalled), not just locally. Instance terminated immediately after, confirmed stopped.
**One real deviation from plan**: `c6i.xlarge` **spot** capacity was unavailable in `us-east-1`
at test time (`InsufficientInstanceCapacity`) — `launch_smoke_test.sh` now launches **on-demand**
by default (~$0.17/hr vs. spot's ~$0.05/hr; irrelevant at smoke-test scale, worth revisiting for
Phase 2 where wall-clock hours are non-trivial and retrying spot or falling back across AZs may
be worth the complexity).

**S3 fetch tested directly on an instance, 2026-09-03** (`scripts/aws/test_s3_fetch.sh`):
bucket reachability confirmed (public, no credentials needed, `200 OK`, same as from the Mac
mini); real throughput measured at **~62 MB/s (~500 Mbps)** for a 100MB byte-range fetch,
colocated in `us-east-1` — the first *measured* number behind the "colocated instance is fast"
reasoning the cost/timing estimates above were resting on. **Not measured**: the actual
BED-restricted single-sample slice technique's on-AWS timing — `bcftools` isn't available via
Amazon Linux 2023's default `dnf` repos (`No match for argument: bcftools`), so Step 3 of that
test script was skipped. This doesn't cast doubt on the technique itself (already proven correct
on the Mac mini during the impostor test), just leaves its on-AWS wall-clock number open. Needs
an alternate install path (source build, conda, or `pip install pysam` with build deps) before
that specific number can be measured — not attempted yet, deliberately kept this test light.

**bcftools install path solved, and the real BED-restricted fetch timing measured, 2026-09-03**:
`micromamba` (bioconda's official static package manager, no compilation needed) installs
`bcftools 1.24` cleanly on Amazon Linux 2023 in well under a minute of actual install time. One
real snag hit and fixed along the way: this AMI's `tar` shells out to an external `bzip2` binary
that isn't installed by default, so extracting micromamba's `.tar.bz2` release failed
(`tar (grandchild): bzip2: Cannot exec`) — worked around by using Python's `tarfile` module
instead (bzip2 support built into the standard library, no external binary dependency). With
`bcftools` working, ran the actual technique — BED-restricted, single-sample chr22 CDS fetch
(sample NA19240, same as the impostor test, `-R data/reference/cds_regions/chr22_cds_regions.bed
-s NA19240`) directly against the S3 URL: **~8 minutes wall-clock** (started 18:23, finished
18:31 UTC, confirmed via the `bcftools` process's accumulated CPU time and the output file's
completion), producing a valid 3.2MB `.vcf.gz` with **27,876 variants**. Compare to the ~40
minutes previously measured for the *unrestricted* full-chr22 fetch of the same
individual/chromosome (same 0.57%-of-chromosome target) — BED-restriction is still doing real
work even at AWS-colocated speed, consistent with the CPU-bound-not-bandwidth-bound diagnosis
above. This is now a real number, not an extrapolation, backing Phase 2's per-individual fetch
cost estimate.

**Phase 2 output catalog schema, DECIDED 2026-09-03**: per-individual output loads into a new
`individual_hash_catalog.db`, kept separate from the existing `hash_catalog.db` (reference-only,
unsalted) per earlier instruction — not merged into it. One flat table, not split across
unsalted/salted tables:

```sql
CREATE TABLE individual_hashes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id   TEXT NOT NULL,
    gene_id         TEXT NOT NULL,
    sample_id       TEXT NOT NULL,
    representation  TEXT NOT NULL,   -- 'iupac' | 'hap0' | 'hap1' (renamed from 'haplotype' --
                                      -- not always a haplotype anymore, post the IUPAC decision)
    hash_md5        TEXT NOT NULL,   -- unsalted
    hash_sq         TEXT NOT NULL,   -- unsalted, GA4GH sha512t24u
    salted_hash_md5 TEXT,            -- NULL if run unsalted
    salted_hash_sq  TEXT,            -- new: the current .tsv.gz only salts MD5, not SQ -- add
                                      -- this column for symmetry with the unsalted pair
    length          INTEGER NOT NULL,
    het_count       INTEGER,         -- NULL for haplotypes mode, 0+ for iupac mode
    salt_label      TEXT,            -- e.g. "phase2-2026-09" -- NEVER the raw salt value itself
    UNIQUE(transcript_id, sample_id, representation)
);
```

Chose flat/wide over splitting unsalted (stable "ground truth") from salted (access-control
variant) into two separate tables, after confirming the actual usage model: **one salt at a
time** — a Phase 2 re-run under a fresh salt is meant to replace old salted values, not keep
multiple salt-versions coexisting per individual. The two-table split (with a `salts` lookup
table and `salt_id` as part of the key) would only earn its complexity if multiple salt-versions
ever needed to coexist (e.g. different salts issued to different downstream consumers) — not the
case here, so kept simple per this project's own "no premature abstraction" norm.

The `UNIQUE(transcript_id, sample_id, representation)` constraint doubles as a re-run guard for
the loader: **`INSERT OR REPLACE`** is the intended load strategy — safe to rerun the whole batch
loader as many times as needed (e.g. after an interrupted Phase 2 batch, or a deliberate re-salt)
without manually clearing tables or worrying about duplicate/stale rows. `INSERT OR IGNORE` would
instead be the right choice if idempotent *resume* (skip what's already loaded, never overwrite)
were the goal instead of clean replacement — not chosen here, since re-salting is expected to
supersede old salted values, not coexist with them. Note this only guards against duplicate
*identity*, not corrupt data within a row (e.g. a truncated `.tsv.gz` transfer) — worth a basic
row-count sanity check per file before loading if that's a real risk for the transfer method
Phase 2 ends up using.

**Built and verified, 2026-09-03**: `salted_hash_sq` added to `batch_haplotype_hash.py` (both
modes), `haplotype` column renamed to `representation` in the `.tsv.gz` output — re-verified
against the known-good `ENST00000319363.11` value (`hash_md5=3bbd34fa...`, `het_count=5`
unchanged) after the change, plus a `--mode haplotypes` smoke test (1,112 rows, matching the
prior count). `scripts/load_individual_hashes.py` implements the schema exactly as designed
above and creates `data/derived/individual_hash_catalog.db` on first use (kept genome-wide, not
nested under `chr22/`, since Phase 2 spans all chromosomes). Verified with real data, not just
inspected: (a) fresh load — 631 rows for one individual; (b) idempotent reload — reloading the
identical file leaves row count unchanged (631, not 1,262); (c) re-salt correctness — reloading
under a *different* salt/salt_label leaves the unsalted `hash_md5` identical but updates
`salted_hash_md5`/`salted_hash_sq`/`salt_label`, with row count still unchanged (`INSERT OR
REPLACE` doing exactly the intended "old salted values become obsolete" behavior, not
accumulating duplicates); (d) NULL handling — `het_count` correctly NULL for `--mode haplotypes`
rows, `salted_hash_md5`/`salted_hash_sq` correctly NULL for unsalted loads; (e) coexistence — the
same individual's `iupac` and `hap0`/`hap1` rows load into the same table without conflict
(556+556+631 = 1,743 rows, no collisions), confirming `representation` is doing its job as part
of the `UNIQUE` key.

**Salt handling hardened**: added `--salt-file <path>` to `batch_haplotype_hash.py`, safer than
`--salt <value>` for a real salt — the value never appears in `ps aux` or shell history, only the
file path does. Takes precedence over `--salt`/`HASH_SALT` when given. Recommended pattern for
the real Phase 2 salt: write it to a file outside the repo (or under `data/derived/`, already
unconditionally gitignored) directly in your own terminal, then pass `--salt-file` — the value
never needs to appear in this chat or any log of it.

**Custom "golden" AMI baked, 2026-09-03**: `ami-020985bb7982d427b`
(`trio-genome-bcftools-20260903`, private to this AWS account, `us-east-1`) — Amazon Linux 2023
with `micromamba` + `bcftools 1.24` (bioconda) pre-installed, removing the ~1 minute install step
from every future instance launch. Built by launching a base instance, installing via the same
micromamba path proven in the S3-fetch test, running `aws ec2 create-image`, and terminating the
source instance once the AMI reached `available`. `scripts/aws/launch_smoke_test.sh` now accepts
an optional `--golden` flag to use this AMI instead of resolving the latest stock AL2023 image —
**verified working**: launched an instance with `--golden`, confirmed `bcftools 1.24` runs
immediately with no install step, terminated. Worth using for Phase 2 or repeated dev/test
cycles; not needed for a plain mechanics-only smoke test where the AMI doesn't matter.

**Phase 2 salt transfer wired, 2026-09-03**: the Mac mini holds the salt file, but Phase 2 runs
on an AWS instance — `scripts/aws/phase2_deploy.sh <public-ip> <key-pair-name> <salt-file-path>`
`scp`s it over (SSH-encrypted in transit, `chmod 600` on arrival), the same pattern
`deploy_and_test.sh` already uses for other files. The script's argument is always a *path*, so
even when driving this from here, the salt's contents never need to appear in a tool call, `ps
aux`, or shell history — only the file path does. Verified the missing-file guard fails fast
before attempting any SSH connection. Also transfers the pipeline scripts, full genome-wide
GENCODE reference, and all 24 chromosomes' CDS-region BED files — everything an instance needs
before the actual batch loop can run. **Not yet built**: the batch loop itself (per-individual
S3 fetch + hash + load across all 2,504 individuals × 24 chromosomes, parallelized) — separate,
undesigned work (needs a sample-enumeration source and a parallelization strategy decided) with
its own go-ahead required before Phase 2 runs for real.

> ⚠️ **REMINDER before the real AWS run**: `TodayI$Miercole$` (used in
> `data/derived/chr22/HG002_chr22_iupac.tsv.gz`/`SALT_DO_NOT_COMMIT.txt`, 2026-09-02) was a
> local-exploration salt only. Generate a fresh salt for the actual population-scale AWS batch
> run — don't reuse the exploration one for real output. The Phase 1 smoke test above used no
> salt at all (mechanics test only, not real output).
~~1. Validate the MD5/sha512t24u hashing pipeline against a known-good external reference~~ —
**done 2026-09-01, chr22, full match.** See
[External validation against Ensembl](#external-validation-against-ensembl-2026-09-01) below for
the result and the answer to "is there a checksum database to just download" (short answer: no —
here's what to do instead, and it's now proven out on chr22).
2. Mash/sourmash MinHash distance demo against a 1000 Genomes chr22 panel.
3. 1000G+HGDP chr22 PCA/ADMIXTURE + coding-vs-genome-wide resolution-collapse demo (see
   [Track 2](#track-2--distance--population-ancestry--active-current-focus-design-only-so-far)).
~~4. Build the IUPAC-collapsed representation on the data already downloaded.~~ — **done and
   verified 2026-09-02.** `scripts/batch_haplotype_hash.py --mode iupac` (now the default); see
   the DECIDED writeup above for the reasoning and the two independent verification methods used.
   631/1341 chr22 transcripts get a usable hash with zero phase-related exclusions, run against
   real HG002 data already local (`data/giab/`) — no new downloads needed, as anticipated.
   Genotype-set hash (unordered allele pair per site) remains the documented fallback if exact
   genotypes are ever needed instead of the IUPAC collapse, not currently pursued. See also the
   salt-on-IUPAC-hashes evaluation under [Hash schemes](#hash-schemes-refget-compatible--decided)
   — separate decision, not yet adopted.
5. **Download strategy for scaling past chr22 to all chromosomes.** The current remote
   `bcftools view -r/-R -s <url>` approach hits a real limit: fetching one sample's full chr22
   from the 2,504-sample 1000G high-coverage file took ~40 minutes for 0.57% of the chromosome
   before being restricted to a BED file of just the needed regions — `bcftools` still has to
   stream and decompress every sample's INFO/FORMAT fields per line before discarding unwanted
   columns, so sample-subsetting alone doesn't reduce network transfer, only output size. This
   holds regardless of network speed: the same-region S3 throughput test below (~62 MB/s) doesn't
   remove the CPU-bound parsing cost, so region-restriction remains necessary, not just a
   workaround for a slow home connection.
   **Region-restriction now extended to all chromosomes, 2026-09-03**:
   `scripts/generate_cds_bed.py` generates one merged, sorted BED file per chromosome at
   `data/reference/cds_regions/{chrom}_cds_regions.bed` — 201,612 merged CDS regions across all
   24 chromosomes (chr1–22, X, Y; chrM excluded, since 1000 Genomes' per-chromosome joint-VCF
   releases don't include a chrM file in the same format), restricted to the same *validated*
   transcript set `gencode_cds_extract.py` actually hashes (not just any CDS-bearing transcript
   in the raw GTF) — confirmed necessary and correct by regenerating chr22 and diffing
   byte-for-byte against the original, already-used `data/giab/impostor_test/
   chr22_cds_regions.bed`: exact match, 1,341/1,404 validated transcripts, 4,186 merged regions.
   Remaining options if this still isn't fast enough at full population scale, not yet needed:
   (b) a lighter-weight source than the heavily-annotated NYGC high-coverage callset — e.g. 1000G
   phase 3 (GRCh38 liftover), far fewer population-stratified INFO fields per line; (c)
   sites-only VCFs (gnomAD or similar) if allele frequency is ever the actual need instead of
   per-sample genotypes — dramatically smaller, but not applicable to Track 1/2's per-individual
   hash catalog as currently scoped; (d) download once per chromosome and cache locally rather
   than repeated narrow remote slices, if many different region/sample queries are expected
   across a session.

**Shared reference-catalog fixes — both tracks depend on `gencode_cds_extract.py`'s output, do
these before/alongside Track 2 work rather than only as Track-1 cleanup:**

6. Fix the selenocysteine categorization gap: add
   `elif "seleno" in t["tags"]: flagged.append((tid, "selenoprotein")); continue` to
   `build_catalog` (see Known gaps #1 — root cause verified, the tag is already parsed
   correctly, the branch just doesn't exist yet). Acceptance check: `translate_mismatch` count
   should drop from 10 to 0, all 10 recategorized as `selenoprotein`.
7. Add a `cds_nt_withstop` hash variant + `cds_stop_included` boolean column to the SQLite
   schema, so `cds_md5`/`cds_sq` become comparable to external NCBI/Ensembl CDS checksums
   without changing the existing stop-excluded canonical form (see the stop-codon table above).

**Track 1 (inheritance) — done, cleanup only, not being actively pursued:**

~~8. Regenerate `data/derived/chr22/hash_catalog.db` on the Mac mini~~ — **done 2026-08-31**,
notebooks 02→04 rerun on the Mac mini and verified to reproduce the original Windows/WSL2 run
exactly (see [Current state](#current-state-verified-against-the-filesystem-not-just-prose) and
[Data facts](#data-facts-verified-chr22-gencode-v46)).

9. **Confirm `samtools`/`bcftools`/`mash` are actually installed on the Mac mini** — run
   `scripts/setup_macos.sh` if not, then the sanity checks in
   `docs/python-env-cheatsheet.md`. (Notebooks 01–04 ran successfully without needing this
   confirmed — none of them shell out to samtools/bcftools/mash directly — but still open for
   when Track 2's Mash/sourmash work or `bcftools consensus` are actually needed.)
10. **Indels — the coordinate-math problem, worked out but not yet implemented.** Currently
    30/1341 transcripts are flagged `has_indel` and excluded entirely (any transcript with an
    indel or multiallelic site in *any* of the individuals in scope). Why this needs real design,
    not a quick patch: `build_transcript_variant_map`'s coding-position mapping is computed once
    per transcript from a fixed genomic→coding offset table, which assumes every variant is a
    pure substitution (net length change zero). An indel of net length *N* shifts every
    downstream coding-relative position by *N* — and that shift can differ **per individual**
    (different people can have different-length indels at the same locus) and even **per
    haplotype within one person**. To handle this correctly: (a) apply variants in genomic-
    position order per haplotype, accumulating the offset shift as you go, rather than computing
    offsets once from a static table; (b) each individual's/haplotype's CDS becomes its own
    coordinate space once an indel is applied — can't share one `cds_seq` reference across
    people anymore downstream of the indel; (c) decide what a frameshift indel (length not a
    multiple of 3) actually *means* for hashing — the protein sequence changes completely
    downstream of a frameshift, which is a real biological consequence, not a bug, so "compare
    hashes downstream of a frameshift" may not even be a meaningful operation, separate from
    getting the coordinate math right; (d) multiallelic indel sites (already excluded together
    with plain multiallelic SNVs via the `len(alts) != 1` check) compound this further.
11. **Indels, gene/segmental duplication, and "difficult regions" — these need one coherent
    strategy, not three separate patches.** All three showed up together in the one
    `no_parental_match` locus (gene `ENSG00000100033`, difficultregion=segdups+lowmappability) —
    that's not a coincidence: segmental duplications are exactly where short-read mapping
    produces spurious-looking variant calls (reads from a paralogous copy mismapping to the
    "wrong" gene copy), which is a mapping-layer problem, not something the hashing/
    classification layer can fix after the fact. Options to weigh, not yet decided: (a) exclude
    `difficultregion`-tagged loci from confident-call totals entirely (coarse, safe, loses real
    data); (b) keep the current "track as metadata, don't discard" approach but formalize it into
    explicit **confidence tiers** in the catalog/classification output (e.g.
    `high_confidence` / `flagged_difficult_region` as a queryable column, not just a string inside
    `evidence`) so downstream Track 2 work can choose to include or exclude by tier per-analysis;
    (c) for segmental duplications specifically, a real fix needs alignment-layer tools this
    project doesn't currently use (graph-based realignment, or a T2T-CHM13-aware caller) — out of
    scope for a hash-comparison pipeline, but worth naming as the actual root fix vs. what
    metadata-tagging can paper over. The `difficultregion` tag GIAB already provides (segdups +
    low-mappability + tandem-repeats) is doing real work here already (100% overlap for
    `no_parental_match` vs. ~7.7% background, see Data facts) — the gap is that it's not yet used
    for anything beyond passive annotation.
12. Low-complexity flagging (`dustmasker` for CDS, `segmasker` for protein) → populate the
    `low_complexity_frac` column (schema already has it, `NULL` for all rows currently).
13. Spot-check a handful of the 431 confident parent-of-origin calls by hand against the raw VCF
    records.
14. *(Parked, low priority)* Theoretical-vs-observed codon usage (dNdScv/SnpEff/PAML) and
    possible-vs-observed synonymous SNVs on chr22 vs. gnomAD v4 — raise at the cDNA synonymous
    layer if/when relevant.

No open repo-hygiene items as of 2026-08-31 — the last stale scaffold files
(`v3_commit_guide.md`, `data/README.md`, `claude-out.sh`) have all been retired; see
`CHANGELOG.md`.

---

## Toolchain checklist

- `samtools`, `bcftools`, `bgzip`, `tabix`
- `sqlite3`
- `dustmasker`/`segmasker` (BLAST+), optional `tantan`
- `mash` and/or `sourmash` (Track 2 only)
- Python (Biopython, `pyfaidx`) for exploration; Jupyter

## References

- [`CHANGELOG.md`](CHANGELOG.md) — dated history of this project.
- [`docs/python-env-cheatsheet.md`](docs/python-env-cheatsheet.md) — Mac mini Homebrew/
  Anaconda/venv reference.
- [`docs/data_sources.md`](docs/data_sources.md) — data sourcing for the **older, unrelated**
  v1–v3 gene-level pipeline (1000 Genomes NA12878 trio), not this CDS POC.
