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

## Track 2 — population / ancestry data plan
- Ethnicity signal is overwhelmingly **non-coding** (neutral drift genome-wide), NOT coding — so the
  population track needs whole-genome SNPs, not the CDS hashes from Track 1.
- Reference genotype panels (open): **1000 Genomes** (~2,504 indiv, 26 pops, 5 super-pops),
  **HGDP** (~950, 54 pops, better fine-scale), **SGDP** (~300, 142 pops, deep). AF-only: **gnomAD**.
  Gap-fillers: GenomeAsia 100K, H3Africa, GGVP.
- Curated Ancestry-Informative Marker (AIM) panels: **Kidd Lab AISNPs** (55-SNP & 128-SNP, via
  **FROG-kb** frog.med.yale.edu and **ALFRED**); **Seldin/Kosoy ~128 AIMs**; EUROFORGEN / Precision ID.
- POC plan for chr22: extract 1000G + HGDP chr22 -> LD-prune -> PCA/ADMIXTURE; cross-check against
  Kidd chr22 AISNPs as a labeled sanity set.
- Commercial context: 23andMe & Ancestry DO use public data (1000G, HGDP, HapMap) but only as a MINORITY
  ingredient / backbone for under-represented pops. 23andMe patent: one classifier = ~14,400 indiv
  (~11,800 customers + ~600 internal + 2,000 public 1000G/HGDP); current product compares to >21,000 known-
  ancestry people across 78 pops. Ancestry similar, ~185k mostly proprietary. Public data is the seed;
  customer scale provides European sub-region depth. => 1000G+HGDP gives you the SAME foundation they start
  from; you only lack the customer European-enrichment layer (affects fine within-Europe resolution, not
  continental/broad-regional).
- Common errors:
  - **Ascertainment bias** (#1): AIM/array panels chosen from mostly-European samples distort diversity
    and underperform on under-represented pops. WGS-derived SNPs (1000G/HGDP) avoid this; AIMs don't.
  - **Don't pre-pick AIMs** for the POC -> circularity. Run genome-wide first, rank chr22 SNPs by F_ST after.
  - **LD pruning** required (`plink --indep-pairwise`) or a few haplotype blocks dominate.
  - **Build/strand** consistency when merging panels; A/T & C/G SNPs are the classic silent strand bug.

## chr22 hash-count estimate (MANE Select, one haploid reference)
- chr22 protein-coding genes ~495 (Ensembl 115 / GENCODE v49) -> ~490 MANE transcripts.
- Reference baseline (distinct sequences): protein ~490 + CDS ~490 + per-exon ~4,200 = **~5,000**.
  - Per-exon layer is ~85% of the catalog and is the cost driver (all-isoforms would ~10x it to ~50k).
  - Storing BOTH digests (MD5 + SQ) = ~10k rows but still ~5k distinct sequences.
- Individuals add only CHANGED sequences (~250-350 coding variants/person on chr22 -> a few hundred new hashes each).
- **Full GIAB trio POC total ≈ ~7,000-8,000 distinct hashes (~15k rows).** Trivial for SQLite / fits in memory.

## IUPAC / genotype fingerprint (Track 1 ONLY)
- Optional phase-free layer: collapse a locus's genotype to IUPAC codes (R={A,G} etc.) -> one canonical
  hash invariant to phase and ref/alt order. Detects HETEROZYGOSITY PRESENCE without phasing.
- Reality: the two per-haplotype hashes are UNDEFINED unphased when a locus has >=2 het sites. So it's
  ~1 new hash per heterozygous locus (not 3, not a doubling) -> a few hundred/individual on chr22.
- Constraints: separate namespace (`iupac_collapsed=true`, never compare to refget/reference hashes);
  NUCLEOTIDE layer only (IUPAC in a codon = ambiguous AA, do not propagate to protein hashes);
  biallelic SNVs only (indels/multiallelic corrupt it); still exact-match => Track 1 only.
- More robust general alternative: hash the SORTED normalized VCF genotype string per locus (handles
  indels + multiallelic, tool-safe). IUPAC is the FASTA-friendly biallelic-SNV special case.
- Does NOT bridge to ethnicity: wrong region (coding) AND wrong operation (exact-match vs frequency/distance).

## Ethnicity from coding-only regions? (feasibility)
- Possible but SHALLOW. Continental super-pop (AFR/EUR/EAS/SAS/AMR) resolvable; sub-continental/country collapses.
- Why weak: coding ~1.5% of genome (less signal); purifying selection + convergent adaptation (homoplasy)
  violate the neutral-drift assumption ancestry methods rely on.
- If done anyway: restrict to synonymous / 4-fold-degenerate (least selected); LD-prune; PCA/ADMIXTURE vs
  1000G+HGDP; report super-pop only + uncertainty. Common error: reading pigmentation/adaptation coding AIMs
  (SLC24A5, SLC45A2, HERC2/OCA2, EPAS1, LCT) as ancestry markers — they track selection/environment, not history.
- Verdict: good TEACHING demo of information loss; a dead end as a real tool.

## Demo: coding-only vs genome-wide PCA (resolution collapse)
- Goal: visually show how much ancestry signal survives when restricted to protein-coding SNPs.
- PCA = principal component analysis: reduce the per-SNP high-dim space to a few axes (PC1, PC2...);
  people cluster by ancestry with no labels/model. Standard first look for population structure.
- Plan (same samples, two marker sets, side-by-side):
  1. 1000G + HGDP chr22 genotypes (GRCh38), PASS biallelic SNVs.
  2. Set A = genome-wide/chr22 ALL SNPs; Set B = coding-only (intersect with GENCODE CDS), ideally
     synonymous/4-fold subset.
  3. LD-prune each (`plink --indep-pairwise`), run PCA (plink/EIGENSOFT smartpca or scikit-allel).
  4. Plot PC1xPC2 for A vs B, colored by super-pop -> expect tight clusters in A, blurred/merged in B.
- Expected teaching point: continental clusters persist in coding-only; sub-continental structure dissolves.
- Common errors: build/strand mismatch when merging panels (A/T,C/G SNPs); skipping LD prune (few blocks
  dominate); comparing across different SNP counts without noting marker-count as the driver.

## Parked items (raise at the right juncture)
- **Theoretical vs actual amino-acid / codon usage** — raise at the cDNA synonymous layer (observed codon
  frequency vs uniform expectation). Tools: dNdScv (trinucleotide model), SnpEff, PAML/KaKs_Calculator.
- **Possible-vs-observed synonymous SNVs on chr22** (secondary): enumerate CDS opportunity (3xL, classify by
  codon table, tag trinucleotide/CpG context) -> intersect with gnomAD v4 chr22 (PASS, norm -m -, VEP synonymous)
  -> fraction observed stratified by CpG. Watch: build match (v4=GRCh38), coverage!=absence, CpG=genomic context.

## Open decisions / next steps
1. Digest choice: **MD5 vs SHA-256**.
2. POC scope: **both tracks**, or exact-identity trio first with distance deferred.
3. Then build (code pending go-ahead): fetch chr22 GENCODE subset -> normalize -> emit protein + per-exon CDS
   hashes (MD5 + SQ) -> SQLite catalog with evidence + low-complexity columns.
4. Started: initial tests on **chromosome 22**.
5. Language: bash orchestration + Python (Biopython/pyfaidx) for enumeration; JS/Perl/Java as fits.

## Toolchain checklist
- samtools, bcftools, bgzip, tabix
- sqlite3
- dustmasker / segmasker (BLAST+), optional tantan
- mash and/or sourmash (Track 2 only)
- Python (Biopython, pyfaidx) for exploration; Jupyter + bash kernel/%%bash
