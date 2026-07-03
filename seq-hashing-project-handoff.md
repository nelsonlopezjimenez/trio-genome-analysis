# Sequence-to-Hash Pipeline — Project Handoff

**Goal:** Hash reference proteome sequences (AA, cDNA/CDS, per-exon), then hash individual
proteomes from a **chr22 trio** to (1) demonstrate parent-of-origin inheritance and
(2) explore population/ancestry distance. Scope: **proof-of-concept / teaching demo.**

**Environment:** macOS (Apple Silicon), VS Code. bash-first + samtools/bcftools;
Python for exploration; Perl/Java optional. SQLite for the hash catalog.

---

## Core design decisions

### Anchor unit = CDS
- Protein/gene **genomic** boundaries are annotation-defined and fuzzy — do NOT detect de novo.
- CDS boundaries ARE locally defined (start codon -> stop codon, known frame).
- Cross-level invariants to validate against:
  - `translate(CDS) == protein`
  - `splice(coding exons, strand-corrected) == CDS`

### Reference download
- Human/mouse -> **GENCODE** (matched release: genome FASTA + GTF + transcript FASTA + translations).
- Other mammals -> Ensembl. Proteins w/ evidence -> UniProt or RefSeq. Canonical anchor -> **MANE Select**.
- Pin ONE release for the whole matched set. Download provided **MD5SUMS** and verify.
- **#1 silent error:** mixing releases -> ID/coordinate drift.

### Hash schemes (refget-compatible)
- **MD5** of normalized residues = SAM/BAM `M5` tag (samtools-aligned).
- **ga4gh SQ** = base64url( SHA-512(seq)[:24] ), no padding -> `SQ.<32 chars>`; VRS form `ga4gh:SQ.<...>`.
- The two digests are independent (SQ is not derived from MD5). Keep both as columns.
- **DECISION PENDING:** MD5 (samtools-aligned) vs SHA-256 (stronger) as primary digest.

### Normalization (MANDATORY before hashing)
- Uppercase; residues only; strip whitespace/newlines.
- **Protein:** keep initiator Met; NO trailing stop.
- **CDS nucleotide:** decide stop-codon inclusion and DOCUMENT it.
  - GENCODE/Ensembl **GTF `CDS` features EXCLUDE** the stop (separate `stop_codon` feature).
  - Ensembl/NCBI **CDS FASTA usually INCLUDES** the stop. Mismatch => silent off-by-3.

### Why no stop codon (protein layer)
1. Stop encodes no amino acid -> not part of a protein sequence.
2. UniProt/GENCODE translations + refget protein hashes exclude it; a trailing `*` mismatches every public hash.

### Start codon / initiator Met
- Keep Met in the hashed bytes (translated CDS + UniProt canonical both start with Met even if cleaved in vivo).
- Use experimental evidence to FLAG N-terminal processing / start confidence as metadata — do not edit bytes.
- Predicted (`XP_`) models: the start is the least reliable part; let the evidence column carry that.

### Repeat / low-complexity flagging
- Store as SEPARATE metadata, never by lowercasing (uppercasing before hashing erases soft-masking).
- Nucleotide: `dustmasker` / `tantan`. Protein: `segmasker` (BLAST+) / SEG.
- Why: low-complexity/repeat regions are error-prone, cause homoplasy + spurious matches, inflate distance.

### Evidence flag (experimental vs predicted)
- **RefSeq prefix (cleanest):** `NM_/NP_` = curated/experimental; `XM_/XP_` = Gnomon prediction.
- **UniProt:** PE1 (protein evidence) .. PE4 (predicted) .. PE5; reviewed (Swiss-Prot) vs unreviewed (TrEMBL).
- **GENCODE:** transcript `level` 1/2/3, TSL 1-5, tags (e.g. `MANE_Select`).

### Storage
- Raw downloads: read-only, gzipped as-downloaded, + `manifest.tsv` (source URL, release, date, md5).
- Working FASTA: **bgzip (not plain gzip)** + `samtools faidx` (.fai/.gzi). Plain gzip breaks random access.
- Hash catalog: **SQLite** — one row per sequence:
  `hash_md5, hash_sq, seq_type(AA|CDS|cDNA|exon), accession, gene_id, source, release, evidence, length, low_complexity_frac`.
  Index on hash_* and gene_id. Don't store sequence bytes twice (FASTA is the blob store; retrieve by faidx).

### Notebook / tracking
- Hybrid: Jupyter Python kernel + `%%bash` cell magic (run samtools/bcftools in cells; thoughts + outputs inline; git the .ipynb).
- Reproducibility: notebook for exploration only; promote settled steps to numbered scripts + Makefile. Log tool versions.

---

## Counts & expectations
- Human protein-coding genes ≈ **19,400** (GENCODE v47 = 19,433) — NOT 35k (that's coding + lncRNA).
- Hashes per seq type per reference proteome: **~20k (canonical/MANE) up to ~100k (all isoforms + predicted).**
- Per-exon hashing multiplies by ~exon count (~10x): canonical ~**180-200k** distinct exon hashes.
- **cDNA hashes >= AA hashes** always (collapse happens cDNA -> AA: synonymous codons + UTR-only diffs).
- Theoretical synonymous cDNA space for ONE protein ≈ **3^L** (10^140 for 300 aa) — NEVER enumerate; hash only observed.
- Two human genomes differ at ~a few thousand proteins (~10-11k missense, ~100-150 protein-truncating variants/genome).

---

## Two tracks (they need DIFFERENT tools)

### Track 1 — Exact identity (inheritance / trio)  [your current approach]
- Cryptographic hashes (refget SQ / MD5) of protein + per-exon CDS.
- Use for parent-of-origin demo on **GIAB trio: HG002 son / HG003 father / HG004 mother**, chr22.
- Caveats:
  - **Zero error tolerance:** 1 base error in a CDS flips the whole hash -> false "de novo". Per-exon hashing localizes this (fixes it).
  - Protein-level signal is **sparse** (most proteins identical across trio); cDNA/CDS level is more informative.
  - Needs **haplotype-resolved** input (2 alleles/gene) or the 2nd allele is invisible.
  - **Mendelian rule:** can only assign origin where a parental allele is unique; shared alleles are uninformative.
  - "Matches neither parent" is mostly artifact, not de novo (true coding de novos ≈ 1-2/genome). Treat as QC flag.
  - Exon hashes only comparable if exon boundaries identical — anchor to annotation exon IDs (alt-splicing shifts boundaries).

### Track 2 — Distance / population (ancestry, geographic origin)
- **Cryptographic hashes CANNOT do distance** (avalanche: 1 change -> totally different hash).
- Use **MinHash / locality-sensitive hashing** instead: **Mash** or **sourmash** (FracMinHash), k ≈ 21-31.
  - Sketch = smallest hashes of k-mers; shared-hash fraction (Jaccard) -> Mash distance ≈ ANI/mutation distance.
- Reference panel: **1000 Genomes chr22** (and/or HGDP).
- Reality check: sketch-based pop-gen is emerging, not standard for humans. Mainstream ancestry = SNP-based
  PCA / ADMIXTURE vs 1000G/HGDP. Good for a teaching demo; not a solved standard.

### Key literature
- Ondov et al. 2016, *Mash: fast genome and metagenome distance estimation using MinHash* (Genome Biology).
- Brown & Irber 2016, *sourmash* (JOSS). FracMinHash.
- Trio binning (Koren et al. 2018) + yak/meryl parental k-mers + hifiasm --trio = the "proper" parent-of-origin-by-hash at k-mer granularity.
- Standards: GA4GH **refget** (sequence checksums) + **VRS / vrs-python** (variant hashing) + **HGVS** (c./p./g.).

---

## Worked example (verified)
Human preproinsulin `NP_000207.1`, 110 aa. Hash of the normalized 110-char string:
- MD5: `12e9c9e4e2835c302e8ba615115edda3`
- SQ:  `SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`  (verify against NCBI/Ensembl record; residues typed from memory)

---

## Open decisions / next steps
1. Digest choice: **MD5 vs SHA-256**.
2. POC scope: **both tracks**, or exact-identity trio first with distance deferred.
3. Then build (code pending go-ahead): fetch chr22 GENCODE subset -> normalize -> emit protein + per-exon CDS
   hashes (MD5 + SQ) -> SQLite catalog with evidence + low-complexity columns.
4. Started: initial tests on **chromosome 22**.

## Toolchain checklist
- samtools, bcftools, bgzip, tabix
- sqlite3
- dustmasker / segmasker (BLAST+), optional tantan
- mash and/or sourmash (Track 2 only)
- Python (Biopython, pyfaidx) for exploration; Jupyter + bash kernel/%%bash
