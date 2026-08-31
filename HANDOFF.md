# Handoff — Trio Genome Analysis

**Last updated: 2026-08-31**

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
- **`data/derived/` is currently EMPTY on this (Mac mini) checkout.** The SQLite hash catalog
  (`hash_catalog.db`) and FASTA blob store described below were built on the original
  Windows/WSL2 machine on 2026-07-03 and are gitignored — they do **not** exist here yet.
  Notebooks 02→04 need to be rerun on this machine to regenerate them before any further work
  on Track 1 can proceed here.
- **Notebook 01** (hash functions) has been rerun and kernel-verified on the Mac mini
  (2026-08-29) — MD5/SQ outputs reproduce exactly.
- Notebooks 02–04 have **not** been rerun on the Mac mini yet (no evidence in `data/derived/`
  or git history of it happening).
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
- Working FASTA: `pyfaidx`-indexed (plain-text, not bgzip — chosen originally because the
  Windows dev machine had neither `samtools` nor `bgzip` natively; revisit now that both Macs
  have Homebrew `samtools`).
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
- SQLite catalog (built 2026-07-03, on the original Windows/WSL2 machine — not present in this
  Mac mini's `data/derived/`, see [Current state](#current-state-verified-against-the-filesystem-not-just-prose)):
  **16,176 rows** = 1341 AA + 1341 CDS + 13,494 exon hashes, across 443 chr22 genes. Round-trip
  verified (SQLite hash → FASTA lookup → re-hash → matches).
- **Track 1 result** (notebook 04, run 2026-07-03, of 1341 validated transcripts):
  - **431 confident parent-of-origin calls** (201 paternal + 230 maternal haplotypes).
  - 675 uninformative (variant shared by both parents — the Mendelian-uniqueness caveat).
  - 681 trivial (no variants in the child for that CDS).
  - 75 flagged `phase_incomplete`; 30 flagged `has_indel` (SNV-only scope this round).
  - 4 flagged `no_parental_match`, all four tracing to **one** locus (gene `ENSG00000100033`,
    across 4 transcript isoforms): neither parent has any VCF record at that position (implied
    homozygous-reference), child is heterozygous, and the site carries GIAB's own
    `difficultregion=hg38.segdups_sorted_merged,lowmappabilityall` tag — a mapping-artifact
    signature, not a real de novo call. Confident calls touch a difficult region ~7.5–8.7% of
    the time vs. **100%** (4/4) for `no_parental_match`.
- Counts/expectations (design-time estimates, not all re-verified against chr22 data above):
  human protein-coding genes ≈ 19,400 genome-wide; chr22 protein-coding genes ~495 (Ensembl
  115/GENCODE v49) → ~490 MANE transcripts; reference baseline (protein + CDS + per-exon)
  ≈ ~5,000 distinct sequences; full GIAB trio POC total ≈ 7,000–8,000 distinct hashes
  (~15k rows) — trivial for SQLite.

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
- Optional side layer (not built), originally scoped for Track 1 but now the leading candidate
  for Track 2's own unphased-representation question (see Active TODO #4): IUPAC
  genotype-fingerprint collapse (phase-free, detects heterozygosity presence without phasing) —
  separate namespace, nucleotide-only, biallelic SNVs only, never compared to reference hashes.

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

1. Validate the MD5/sha512t24u hashing pipeline against a known-good external reference before
   building further on it — hash a full GRCh38 reference chromosome and confirm it reproduces a
   published refget/`.dict`-file MD5, and/or hash a known Ensembl CDS and confirm it matches
   Ensembl's own refget-retrievable checksum. Not yet done (see Hash schemes note above).
2. Mash/sourmash MinHash distance demo against a 1000 Genomes chr22 panel.
3. 1000G+HGDP chr22 PCA/ADMIXTURE + coding-vs-genome-wide resolution-collapse demo (see
   [Track 2](#track-2--distance--population-ancestry--active-current-focus-design-only-so-far)).
4. Resolve the still-open representation question for unphased heterozygous CDS: default to one
   IUPAC-ambiguity sequence per CDS per person (phase-free, single hash) rather than enumerating
   all `2^n` allele combinations (intractable past a handful of het sites, and the extra
   combinations add no ancestry signal). Genotype-set hash (unordered allele pair per site) is
   the fallback if exact genotypes are needed instead of the IUPAC collapse.

**Shared reference-catalog fixes — both tracks depend on `gencode_cds_extract.py`'s output, do
these before/alongside Track 2 work rather than only as Track-1 cleanup:**

5. Fix the selenocysteine categorization gap: add
   `elif "seleno" in t["tags"]: flagged.append((tid, "selenoprotein")); continue` to
   `build_catalog` (see Known gaps #1 — root cause verified, the tag is already parsed
   correctly, the branch just doesn't exist yet). Acceptance check: `translate_mismatch` count
   should drop from 10 to 0, all 10 recategorized as `selenoprotein`.
6. Add a `cds_nt_withstop` hash variant + `cds_stop_included` boolean column to the SQLite
   schema, so `cds_md5`/`cds_sq` become comparable to external NCBI/Ensembl CDS checksums
   without changing the existing stop-excluded canonical form (see the stop-codon table above).

**Track 1 (inheritance) — done, cleanup only, not being actively pursued:**

7. **Regenerate `data/derived/chr22/hash_catalog.db` on the Mac mini** — `data/reference/` and
   `data/giab/` are already present here; just rerun notebooks 02→04 in order. (Only needed if
   revisiting Track 1 output; not required to start Track 2 work.)
8. **Confirm `samtools`/`bcftools`/`mash` are actually installed on the Mac mini** — run
   `scripts/setup_macos.sh` if not, then the sanity checks in
   `docs/python-env-cheatsheet.md`.
9. Extend variant handling to indels (currently 30/1341 transcripts flagged `has_indel` and
   excluded) — needs position-ordered, coordinate-shift-aware handling per variant.
10. Low-complexity flagging (`dustmasker` for CDS, `segmasker` for protein) → populate the
    `low_complexity_frac` column (schema already has it, `NULL` for all rows currently).
11. Spot-check a handful of the 431 confident parent-of-origin calls by hand against the raw VCF
    records.
12. *(Parked, low priority)* Theoretical-vs-observed codon usage (dNdScv/SnpEff/PAML) and
    possible-vs-observed synonymous SNVs on chr22 vs. gnomAD v4 — raise at the cDNA synonymous
    layer if/when relevant.

**Repo hygiene (open, low priority, not resolved this pass):**

13. `claude-out.sh` (repo root, untouched since 2025-07-26) is a scaffold/playbook script from
    the original repo setup — same kind of stale, fully-superseded artifact as
    `v3_commit_guide.md` (retired 2026-08-31) and `data/README.md`/`scripts/README.md`'s old
    contents (also retired/rewritten 2026-08-31, see `CHANGELOG.md`). Not acted on in this
    consolidation.

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
