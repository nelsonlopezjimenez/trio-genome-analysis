# Trio Genome Analysis Project

> Current state: see [HANDOFF.md](HANDOFF.md) · History: see [CHANGELOG.md](CHANGELOG.md)

## Sequence-Hashing POC (chr22, CDS-anchored) — in progress

A second, newer effort in this repo, separate from the v3.0 gene-level pipeline described below.
Full design rationale, environment setup, and current status live in
[`HANDOFF.md`](HANDOFF.md); day-to-day work happens in [`notebooks/`](notebooks/). See
[`CHANGELOG.md`](CHANGELOG.md) for the complete, dated history
(run [`scripts/setup_macos.sh`](scripts/setup_macos.sh) to set up a new machine).

**Goal:** hash reference + trio (GIAB HG002/HG003/HG004) protein and CDS sequences on chr22 to (1)
demonstrate parent-of-origin inheritance via exact-match hashing and (2) explore population distance
via MinHash (deferred). Anchored on **CDS** (not gene genomic span), because gene boundaries are
annotation-defined and fuzzy while CDS boundaries (start codon → stop codon) are locally exact.

### What's done so far

1. **Hash functions verified** ([`notebooks/01_hash_functions.ipynb`](notebooks/01_hash_functions.ipynb)) —
   MD5 (samtools/refget-aligned, chosen as primary digest) + ga4gh SQ (`base64url(SHA-512(seq)[:24])`),
   checked against a corrected worked example (the handoff cited the wrong NCBI accession for human
   preproinsulin — `NP_000207.1` is actually an unrelated protein; the right one, `NP_000198.1`,
   reproduces the handoff's hash values exactly).
2. **GENCODE v46 chr22 reference downloaded and MD5-verified** into `data/reference/` (GTF +
   `pc_transcripts.fa` + `pc_translations.fa`).
3. **CDS extraction validated against real data**
   ([`notebooks/02_cds_extraction.ipynb`](notebooks/02_cds_extraction.ipynb), promoted to
   [`scripts/gencode_cds_extract.py`](scripts/gencode_cds_extract.py)) — 1341/1398 chr22 protein-coding
   transcripts (96%) pass both the splice-length and `translate(CDS) == protein` invariants. The 57
   exceptions are all explained, not bugs: 47 incomplete CDS annotations (immune-receptor gene segments)
   and 10 from one selenoprotein gene (internal recoded stop codon).
4. **SQLite hash catalog + FASTA blob store built**
   ([`notebooks/03_sqlite_catalog.ipynb`](notebooks/03_sqlite_catalog.ipynb)) — 16,176 rows (protein +
   whole-CDS + per-exon hashes) across 443 chr22 genes, with a verified round-trip (hash in SQLite →
   accession → sequence pulled from FASTA → re-hashed → matches).
5. **GIAB HG002/HG003/HG004 chr22 VCFs downloaded** into `data/giab/` (remote range-fetch, not full
   genome downloads). Finding: the standard GIAB benchmark VCF is fully **unphased**; the actually-phased
   file lives at a different path (`..._benchmark_phased_MHCassembly_StrandSeqANDTrio.vcf.gz`), and even
   that one is only 43.6% phased on chr22 (21,944/50,284 variants).
6. **WSL2 (Ubuntu) environment set up** for the tools this project needs that aren't available natively
   on Windows: samtools, bcftools, bgzip, tabix, mash, dustmasker/segmasker, plus a Python venv
   (`~/venvs/trio-genome`) with jupyter/ipykernel/biopython/pyfaidx and a registered kernel
   (`Python (trio-genome, WSL)`).
7. **Trio inheritance (Track 1) demonstrated on real data**
   ([`notebooks/04_trio_inheritance.ipynb`](notebooks/04_trio_inheritance.ipynb)) — variants overlaid
   directly onto the validated reference exons (no `bcftools consensus` / whole-genome FASTA needed),
   using a per-site parent-membership check rather than parental haplotype enumeration. Of 1341 chr22
   transcripts: **431 confident parent-of-origin calls** (201 paternal + 230 maternal), 675 uninformative
   (shared between parents), 681 trivial (no variants in child), 75 flagged `phase_incomplete`, 30
   flagged `has_indel` (SNV-only scope), and 4 `no_parental_match` — all four traced to one locus where
   neither parent has any VCF record (implied homozygous-reference) yet the child is heterozygous, and
   that exact site carries GIAB's own `difficultregion` tag (segmental duplication + low mappability) —
   the signature of a mapping artifact, not real de novo, matching the handoff's own caution about this
   category. `difficultregion` is now tracked as per-haplotype metadata generally (not just for this
   case): confident calls touch a difficult region ~8% of the time vs. **100%** for `no_parental_match`.
   Results persisted into the existing SQLite schema (no schema change needed).

### Why phasing matters here

A **genotype** call only tells you which two alleles a person carries at a site — not which chromosome
copy (maternal or paternal) each one is on. **Phasing** recovers that assignment, and it's the difference
between "these variants exist somewhere in this gene" and "this exact sequence exists on one specific
chromosome copy" — which is what hashing requires.

```
Diploid individual, one gene spanning two heterozygous sites (A and B)

  UNPHASED  (genotype calls only: A=0/1, B=0/1)
  ─────────────────────────────────────────────
    copy 1: ----[A: REF or ALT?]----[B: REF or ALT?]----
    copy 2: ----[the other one ]----[the other one ]----

    Two combinations both fit the genotype calls -- can't tell which is real:
      (a) copy1 = REF-A + ALT-B   copy2 = ALT-A + REF-B
      (b) copy1 = REF-A + REF-B   copy2 = ALT-A + ALT-B
    -> hashing either guess risks hashing a sequence that never existed in this genome.

  PHASED  (same site, phased genotype A=0|1, B=1|0, same phase block)
  ─────────────────────────────────────────────────────────────────
    copy 1 (paternal): ----[A: REF]----[B: ALT]----   confirmed real haplotype
    copy 2 (maternal): ----[A: ALT]----[B: REF]----   confirmed real haplotype

    Only one combination is possible, and it's now known -- each copy can be
    correctly spliced, translated, and hashed on its own.
```

On chr22, this means genes whose heterozygous sites all fall inside a phased block can be split into two
trustworthy haplotype-specific CDS sequences; genes overlapping only unphased sites cannot, and are
flagged as **"phase unknown"** rather than guessed at.

### Remaining steps to reach the POC goal

1. Extend variant handling to indels (currently 30/1341 transcripts flagged `has_indel` and skipped) —
   needs position-ordered, coordinate-shift-aware handling per variant.
2. Low-complexity flagging (`dustmasker`/`segmasker`) to populate the `low_complexity_frac` column
   (schema already has it; currently `NULL`).
3. Spot-check a handful of the 431 confident parent-of-origin calls by hand against the raw VCF records.
4. *(Deferred, Track 2)* Mash/sourmash MinHash distance demo against a 1000 Genomes chr22 population panel.

*(Note: applying GIAB's `_benchmark_noinconsistent.bed` was considered but dropped — checking GIAB's own
README showed that file is just the primary high-confidence region BED already implicit in the benchmark
VCF's PASS filter, not a separate trio-consistency filter. The `difficultregion` INFO tag already present
in the VCF turned out to be the more direct signal, and is now used above instead.)

---

## Overview
Analysis of parent-child trio genomes from 1000 Genomes Project high-coverage data, with optimized focus on protein-coding genes for enhanced biological relevance and computational efficiency.

## Key Features
- **Protein-coding gene focus**: Reduces processing by ~65% while maintaining biological relevance
- **Chromosome-by-chromosome processing**: Handles large 1000 Genomes VCF files efficiently  
- **Separate haplotype extraction**: Tracks maternal vs paternal inheritance
- **SHA256 gene hashing**: Enables rapid comparison across individuals
- **Comprehensive logging**: Detailed progress tracking and error handling

## Goals
- Generate individual genome sequences with separate haplotypes
- Extract protein-coding gene sequences for each individual
- Compute SHA256 hashes for comparative genomic analysis
- Focus on medically and evolutionarily relevant coding regions

## Data Sources
- **1000 Genomes Project high-coverage VCF files** (GRCh38, 30x coverage)
- **NA12878 trio**: child (NA12878), mother (NA12891), father (NA12892)
- **GENCODE v46 basic annotations**: Protein-coding gene definitions

## Performance Improvements (v3.0)
- **~65% fewer genes processed**: 20,000 vs 60,000 total genomic features
- **Faster execution**: Focus on biologically relevant regions only
- **Reduced storage**: Smaller output files and hash collections
- **Enhanced metadata**: Rich gene annotations in output files

## Directory Structure
```md
trio-genome-analysis/
├── scripts/              # Analysis scripts
│   └── trio_analysis.sh  # Main analysis script (v3.0)
├── data/                 # Input data (not tracked)
│   ├── vcf_files/       # Chromosome VCF files (~30GB each)
│   ├── reference/       # GRCh38 reference genome
│   └── annotations/     # GENCODE GTF files
├── docs/                # Documentation
├── results/             # Analysis outputs (not tracked)
└── trio_analysis/       # Generated results directory
├── genomes/         # Individual genome FASTA files
├── genes/           # Extracted protein-coding genes
├── hashes/          # SHA256 gene hashes
└── logs/            # Analysis logs
```
## Quick Start

### Prerequisites
```bash
# Install required tools
sudo apt install bcftools samtools bc  # Ubuntu/Debian
brew install bcftools samtools bc      # macOS
