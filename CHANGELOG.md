# Changelog

Detailed log for the **CDS-anchored sequence-hashing POC** (design doc:
[`seq-hashing-project-handoff.md`](seq-hashing-project-handoff.md)). This is a separate effort from the
older v3.0 gene-level SHA256 pipeline (`scripts/trio_analysis.sh`), which this file does not cover.

## [Unreleased] — Sequence-hashing POC

### Decisions made
- **Digest choice:** MD5 as primary (samtools/refget-aligned), ga4gh SQ kept alongside as the stronger
  digest. No third digest.
- **Trio dataset:** GIAB HG002/HG003/HG004 (Ashkenazi trio), not the 1000 Genomes NA12878 trio the old
  v3.0 pipeline uses — chosen because Track 1 (exact-identity inheritance) needs real haplotype
  resolution, and GIAB publishes a trio+StrandSeq phased VCF for the child; confirmed available before
  committing to it.
- **FASTA blob store:** plain-text FASTA + `pyfaidx` instead of the handoff's bgzip + `samtools faidx`,
  because this Windows machine has neither samtools nor bgzip natively. Revisit once the pipeline needs
  WSL anyway (see below) — bgzip/samtools are available there.
- **Trio haplotype construction:** overlay variants directly onto the already-validated reference exon
  sequences (using GTF genomic CDS-exon coordinates to map VCF positions to coding-relative offsets),
  instead of `bcftools consensus` against a whole-genome FASTA. Avoids an ~850MB same-release GRCh38
  genome download and reuses 100% of the notebook 02/03 validation; keeps this step in plain Windows
  Python (WSL not needed here after all, since the chr22 VCF slices are small enough for pure-Python
  `gzip` parsing).
- **Parent-of-origin check:** implemented as a per-site allele-membership test against each parent's
  genotype, not by enumerating parent haplotype combinations. This needs no parental phasing at all —
  only the child needs to be phased, since presence/absence of an allele at a site doesn't require
  knowing which parental chromosome copy it's on.

### Environment migration: WSL2 (Windows) → native macOS
- Development moved off the Windows/WSL2 machine onto two Macs (Mac mini, MacBook "Neo", both Apple
  Silicon) for the remainder of the POC. Native macOS gives Homebrew access to samtools/bcftools/bgzip/
  tabix/blast directly (no VM layer needed, unlike the Windows setup that required WSL2 for these).
- Added `scripts/setup_macos.sh` — idempotent Homebrew-based installer: `samtools`, `bcftools`, `htslib`
  (`bgzip`/`tabix`), `blast` (`dustmasker`/`segmasker`), `python@3.12`; creates a venv at
  `~/venvs/trio-genome` (`jupyter`, `ipykernel`, `pyfaidx`, `biopython`); registers Jupyter kernel
  `trio-genome-macos` ("Python (trio-genome, macOS)"). Same script runs on both Macs.
- **Gotcha found:** `mash` has no `homebrew-core` formula (it only ever lived in the now-archived
  `brewsci/bio` tap). Worked around by having the script pull the upstream `v2.3` `OSX64` release binary
  straight from GitHub into `~/bin/mash` and run it under Rosetta 2 (no arm64 build exists upstream).
  Script checks for Rosetta first and skips with an explicit message (`softwareupdate --install-rosetta`)
  if it's missing, rather than failing silently.
- **MacBook Neo:** fully set up and verified 2026-08-17 — `samtools` 1.24, `bcftools` 1.24, `htslib` 1.24,
  `blast` 2.17.0, `mash` 2.3 (Intel binary via Rosetta), Python 3.12.14 venv, kernel `trio-genome-macos`.
  Smoke-tested: `scripts/gencode_cds_extract.py` imports and translates correctly under the new venv.
- **Mac mini:** not yet set up as of this entry — see [`macos-setup-handoff.md`](macos-setup-handoff.md)
  for the exact steps to resume there.
- Reminder for whichever machine runs the notebooks next: `data/reference/`, `data/giab/`, and
  `data/derived/` are all gitignored, so a fresh clone has none of the actual downloaded/derived data —
  re-download per the manifests before expecting notebooks 01–04 to reproduce prior results.

### Added
- `notebooks/01_hash_functions.ipynb` — defines and verifies `normalize_protein`, `md5_digest`,
  `ga4gh_sq_digest` against a corrected worked example.
- `notebooks/02_cds_extraction.ipynb` — chr22 CDS extraction from GENCODE v46, splice/translation
  invariant validation, per-exon hashing.
- `notebooks/03_sqlite_catalog.ipynb` — SQLite hash catalog + FASTA blob store, with round-trip
  validation.
- `notebooks/04_trio_inheritance.ipynb` — Track 1 (exact-identity inheritance) on real GIAB trio data:
  builds HG002's two haplotype CDS sequences per transcript, classifies each against HG003/HG004 by
  per-site allele membership, and persists results into the existing `sequences` SQLite table (no
  schema change — child haplotype rows distinguished by `accession = "{transcript_id}.HG002.{hap}"`,
  `source = "GIAB"`, classification recorded in `evidence`).
- `scripts/gencode_cds_extract.py` — CDS extraction logic promoted out of notebook 02 once validated;
  reused by notebook 03; runnable standalone (`python scripts/gencode_cds_extract.py`).
- `data/reference/` — GENCODE v46 chr22-relevant files (`gencode.v46.basic.annotation.gtf.gz`,
  `gencode.v46.pc_transcripts.fa.gz`, `gencode.v46.pc_translations.fa.gz`) + `manifest.tsv` (source URL,
  release, date, MD5).
- `data/giab/` — GIAB HG002 (phased)/HG003/HG004 (unphased) chr22 VCFs, fetched as remote range-slices
  (not full-genome downloads) + `manifest.tsv`.
- `data/derived/chr22/` — generated FASTA blob store (`chr22_proteins.fa`, `chr22_cds.fa`,
  `chr22_exons.fa` + `.fai`) and `hash_catalog.db` (SQLite). Gitignored (derived output).
- WSL2 (Ubuntu) environment: `samtools` 1.19.2, `bcftools` 1.19, `bgzip`, `tabix`, `mash` 2.3,
  `dustmasker`/`segmasker` (via apt); Python venv `~/venvs/trio-genome` with `jupyter`, `ipykernel`
  7.3.0, `biopython` 1.87, `pyfaidx`; registered Jupyter kernel `trio-genome-wsl`
  ("Python (trio-genome, WSL)").
- Windows-side Python: `ipykernel`, `pyfaidx` installed for running notebooks 01–03 (these don't need
  samtools/bcftools).
- `.gitignore`: added `data/derived/` and `*.db`.

### Fixed / corrected
- Handoff's worked example cited accession `NP_000207.1` for human preproinsulin. That accession is
  actually Kallmann syndrome 1 protein (ANOS1, 787 aa) — confirmed live against NCBI eutils. The correct
  accession is `NP_000198.1` (110 aa); its sequence reproduces the handoff's MD5
  (`12e9c9e4e2835c302e8ba615115edda3`) and SQ (`SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`) exactly — the hash
  *formulas* were right, only the accession label was wrong.
- Prior assumption (from initial web research) that the standard GIAB v4.2.1 benchmark VCF carries
  trio+read-based phasing was wrong for that specific file: verified empirically that
  `HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz` has 0/50,284 chr22 variants phased. The actual phased file
  is a separate supplementary release, `HG002_GRCh38_1_22_v4.2.1_benchmark_phased_MHCassembly_StrandSeqANDTrio.vcf.gz`,
  found by browsing GIAB's FTP directory listing rather than assuming a filename.

### Findings (empirical, from real chr22 data)
- The handoff's documented "#1 silent error" — GTF `CDS` features exclude the stop codon, but
  `pc_transcripts.fa`'s `CDS:` header coordinate span includes it — reproduced exactly as a consistent
  3nt offset across all 1398 chr22 CDS-transcripts checked.
- 1341/1398 (96%) chr22 protein-coding transcripts pass both the splice-length invariant
  (`sum(GTF CDS-exon lengths) == len(pc_transcripts CDS span) - 3`) and the `translate(CDS) == protein`
  invariant.
- Of the 57 exceptions, 0 are unexplained:
  - 47 are incomplete CDS annotations tagged `cds_start_NF`/`cds_end_NF`/`mRNA_start_NF`/`mRNA_end_NF`
    (mostly IG/TR immune-receptor gene segments, e.g. `IGLV4-69`, which genuinely lack a stop codon in
    this annotation because V(D)J recombination joins them to a J segment later).
  - 10 are from `TXNRD2` (tagged `seleno`) — an internal in-frame UGA is recoded to selenocysteine
    biologically, which a naive codon-table translation reads as a premature stop.
- One transcript (`YPEL1-204`, tagged `non_ATG_start`) uses a near-cognate start codon; the literal
  codon-table translation disagrees with the canonical protein only at position 0 (Met by convention).
  Accepted as a documented biological override, not silently patched.
- HG002 (child) chr22: only 43.6% of variants (21,944/50,284) are phased (trio + StrandSeq combined).
  The rest are unphased and cannot be assigned to a specific haplotype without guessing.
- `sudo` on the WSL install requires a password (no passwordless sudo configured) — package installs
  needed to be run interactively by the user, not from an automated tool call.
- **Track 1 result (notebook 04), of 1341 validated chr22 transcripts:**
  - **431 confident parent-of-origin calls** (201 paternal + 230 maternal haplotypes).
  - 675 haplotypes uninformative (variant shared by both parents — matches the handoff's own
    Mendelian-uniqueness caveat).
  - 681 trivial (no variants in the child for that CDS at all).
  - 75 flagged `phase_incomplete` (child heterozygous sites not resolvably phased together).
  - 30 flagged `has_indel` (out of scope this round — SNV-only).
  - 4 flagged `no_parental_match`, all four tracing to **one** locus in one gene (`ENSG00000100033`,
    seen across 4 transcript isoforms). **Corrected characterization** (an earlier note here said "both
    parents homozygous C/C" — imprecise; verified against the raw VCF records instead): neither parent
    has *any* VCF record at that position at all (implied homozygous-reference by absence), while the
    child is heterozygous. The site carries GIAB's own `difficultregion=hg38.segdups_sorted_merged,
    lowmappabilityall` INFO tag — the signature of a mapping artifact (reads from a paralogous locus),
    not a real de novo call.
  - REF-base sanity check (strand-aware coordinate mapping) passed with 0 mismatches across all 1311
    SNV-only transcripts before any of the above was trusted.
- **`difficultregion` tracked as per-haplotype metadata** (GIAB's own INFO annotation — segmental
  duplication / low mappability / tandem repeat; no extra download needed, already present in the VCFs
  we have). Confident calls touch a difficult region ~7.5–8.7% of the time; `no_parental_match` cases
  do so **100%** of the time (4/4) — strong enrichment supporting the mapping-artifact explanation above.
  Recorded in `evidence` for the persisted GIAB rows, not used to filter (kept per the "flag, don't
  discard" rule).
- **Abandoned approach:** originally planned to download and apply GIAB's `_benchmark_noinconsistent.bed`
  to resolve the `no_parental_match` cases. Checking GIAB's own README (`README_v4.2.1.txt`, line 7)
  showed this BED is just the primary high-confidence region file already implicit in the main benchmark
  VCF's PASS filter — not a separate trio-Mendelian-consistency filter. Verified empirically too: the
  known-artifact site at chr22:18913237 falls *inside* this BED's intervals, which would be impossible if
  it excluded Mendelian-inconsistent sites. Dropped in favor of the `difficultregion` INFO tag instead.

## TODO / Next

1. Extend variant handling to indels (currently 30/1341 transcripts flagged `has_indel` and excluded) —
   needs position-ordered, coordinate-shift-aware handling per variant, combined with the existing
   strand-complement logic.
2. Low-complexity flagging (`dustmasker` for CDS, `segmasker` for protein) → populate the
   `low_complexity_frac` column (schema already has it, `NULL` for all rows currently).
3. Spot-check a handful of the 431 confident parent-of-origin calls by hand against the raw VCF records.
4. *(Deferred — Track 2)* Mash/sourmash MinHash distance demo against a 1000 Genomes chr22 panel, for
   the population/ancestry-distance exploration goal (separate from Track 1's exact-identity goal above).
