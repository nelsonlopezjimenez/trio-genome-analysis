# Changelog

Append-only, dated history — newest entries at the top. For current project state (design
decisions, known gaps, active TODO), see [`HANDOFF.md`](HANDOFF.md), which is edited in place
rather than appended to.

Dates are pulled from `git log` where a commit exists for the work; entries pulled from prose
(handoff docs, session notes) rather than a commit are marked **(approx)**.

---

## 2026-08-31 — Retired v3_commit_guide.md; README's v1→v3 section brought current

- `v3_commit_guide.md` (root, untouched since 2025-07-26) removed (`git rm`). It was a one-time
  release playbook for the v3.0 commit — a `cat > README.md`/`cat > docs/data_sources.md`
  heredoc script plus commit/tag instructions — not living documentation. Confirmed nothing in
  it was unique: its outputs already exist as `README.md` and `docs/data_sources.md` (both
  produced by literally running it on 2025-07-26), its version-history and performance figures
  are already in this file's 2025-07-26 entry, and its planned `docs/performance_comparison.md`
  was never actually created — further sign it was a half-executed scaffold, not a reference.
- `README.md`'s v1→v3 pipeline section was stale and incomplete (the old heredoc's `cat`
  truncated partway through "Quick Start," and the Directory Structure block still named
  `scripts/trio_analysis.sh`, which no longer exists — consolidated into
  `scripts/trio_genome_script.sh` on 2026-08-30). Rewritten against the actual current script
  (read in full to confirm): correct filename, correct config variables
  (`REFERENCE`/`VCF_DIR`/`GTF_FILE`/`PROTEIN_CODING_ONLY`/`CHILD`/`MOTHER`/`FATHER`), correct
  output layout (`trio_analysis/{genomes,genes,hashes}/`, `analysis_summary.txt`). Trimmed the
  duplicated version-history/citation/support boilerplate in favor of pointing at this file and
  `docs/data_sources.md`, consistent with the single-source-of-truth pattern from the
  2026-08-30 consolidation.
- Noted but not acted on: `scripts/README.md` and `claude-out.sh` are the same kind of
  same-day (2025-07-26), fully-superseded playbook artifact — recorded as an open repo-hygiene
  TODO in `HANDOFF.md` rather than touched in this pass.

## 2026-08-30 — Consolidated handoff docs; script cleanup

- Merged four overlapping documents — `seq-hashing-project-handoff.md`,
  `seq-hashing-project-handoff-7.3.2026.md`, `macos-setup-handoff.md`, `TODO.md` (a session-
  mechanics record, despite the filename) — into one living [`HANDOFF.md`](HANDOFF.md) and
  restructured this file into append-only dated entries. The four originals are removed
  (`git rm`); their content is preserved in git history.
- Verified two claims against actual code/filesystem rather than trusting the prose, per the
  consolidation's own ground rule:
  - `scripts/gencode_cds_extract.py` does **not** preserve notebook 02's `"seleno"` tag
    categorization for the 10 selenoprotein exceptions — they fall into the generic
    `translate_mismatch` flagged reason instead. Recorded as an open gap in `HANDOFF.md`, not
    fixed in this pass. (Root cause refined later the same day — see below.)
  - `data/reference/` and `data/giab/` already hold the 2026-07-02 downloads on this machine,
    but `data/derived/` is empty — notebooks 02–04 have not been rerun on the Mac mini yet.
- `python-env-cheatsheet.md` moved to `docs/python-env-cheatsheet.md` (setup reference doc,
  same treatment as `docs/data_sources.md`).
- Separate same-day commit: `scripts/trio_genome_script.sh` consolidated with
  `scripts/trio_analysis.sh` and a stray root-level duplicate — three copies of the old
  gene-level pipeline reduced to one canonical script under `scripts/`.
- **Scope pivot, confirmed:** the project's primary goal is now Track 2 (population/ancestry
  signal), not Track 1 (parent-of-origin inheritance). Surfaced from `handoff-2026-08-29.md`, a
  handoff written from a separate browser session that did not have repo access at the time (its
  own checklist noted "couldn't be read from chat" / "reconcile against the repo") — confirmed
  as an intentional, real pivot rather than a stale note written blind. Track 1's existing
  results (431 confident parent-of-origin calls) are kept as completed/reference work, not
  discarded; `HANDOFF.md`'s Goal, TODO, and "two tracks" sections were reordered/relabeled
  accordingly. `handoff-2026-08-29.md` also contributed: refget v2 terminology
  (`sha512t24u` = the ga4gh SQ digest; `TRUNC512` deprecated, don't add it), a not-yet-done TODO
  to validate the hashing pipeline against a known-good external reference (GRCh38 chromosome or
  Ensembl CDS refget checksum) rather than only the internal invariants checked so far, and a
  note that an earlier AWS Lightsail instance has been wound down (no cloud compute currently in
  use). `handoff-2026-08-29.md` removed (`git rm`) once folded in; history preserved in git.
- **Second browser-session handoff reconciled** (`handoff-2026-08-30-v1.md`, saved to disk as
  `handoff-2026-08-30v1.md`; a duplicate `handoff-2026-08-30.md` with identical content was also
  removed). Unlike the first, this one is repo-aware and its technical claims were checked
  directly against the real chr22 GENCODE v46 data on disk before being trusted:
  - **Selenocysteine bug, root cause corrected.** Confirmed by parsing the GTF directly: there
    are 10 selenoprotein transcripts on chr22 across **three** genes — `SELENOM`, `SELENOO`,
    `TXNRD2` — not just `TXNRD2` as every earlier note in this repo (including this
    consolidation's own first pass) implied. The handoff's proposed root cause (the `"seleno"`
    tag is missing because GENCODE marks it via a separate `Selenocysteine` GTF feature instead
    of a transcript tag) was **checked and found incorrect**: all 10 transcripts do carry a
    `seleno` tag on their `transcript` line, and `parse_gtf_chrom` already parses it into
    `t["tags"]` via the same generic path used for `non_ATG_start`. The real, verified gap is
    simpler — `build_catalog` just never checks for it. Fix recorded in `HANDOFF.md` accordingly
    (one added `elif` branch, no parser changes). The separate `Selenocysteine` GTF feature does
    genuinely exist (verified) and does carry the exact recoded-codon position, kept as a note
    for a *future* enhancement (recode to `U` and include these in the catalog), not as the
    cause of the current bug.
  - Verified the stop-codon convention table's added rows (NCBI RefSeq CDS, Ensembl REST CDS
    both include the stop codon) and the "store both `cds_nt` and `cds_nt_withstop`" design idea
    — not yet implemented, added to TODO.
  - Verified the "per-exon chunks are not codon-aligned" caution by inspecting several real
    multi-exon chr22 transcripts directly (confirmed: codons routinely span exon-exon
    junctions) — added as a standing caution in `HANDOFF.md`.
  - Verified and fixed a real repo-hygiene bug this handoff flagged: `scripts/__pycache__/
    gencode_cds_extract.cpython-314.pyc` was tracked in git with no `__pycache__/` gitignore
    entry. Untracked it (`git rm --cached`) and added `__pycache__/`/`*.pyc` to `.gitignore`.
  - The handoff's "file version discrepancy" concern (`trio_genome_script.sh` duplicated at
    root and under `scripts/`) was already resolved earlier the same day, before this handoff
    surfaced — no action needed.
  - Its NM/NP RefSeq accession-pairing guardrail (don't infer one from the other; insulin's
    `NM_000207` pairs with `NP_000198`, not `NP_000207`) folded into `HANDOFF.md` alongside the
    existing worked-example correction it generalizes from.
  - Flagged but not acted on: whether `v3_commit_guide.md` / `claude-out.sh` (root, untouched
    since 2025-07-26) have drifted from the actual `scripts/` contents — out of scope for this
    consolidation, recorded as an open repo-hygiene TODO instead.

## 2026-08-29 — Mac mini: notebook 01 verified on native kernel

- Reran `notebooks/01_hash_functions.ipynb` against the `trio-genome-macos` Jupyter kernel on
  the Mac mini — MD5/SQ output for the corrected `NP_000198.1` worked example reproduced exactly
  (`12e9c9e4e2835c302e8ba615115edda3` / `SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`).
- Added `python-env-cheatsheet.md`, documenting the Mac mini's Homebrew + Anaconda coexistence
  (two unrelated conda envs already present: `base`, `catalog`) and the "activate the venv last"
  rule — conda auto-activates `base` in every new shell on this machine.
- `data/reference/manifest.tsv` and `data/giab/manifest.tsv` unchanged from the 2026-07-02
  download; `data/derived/` still empty on this machine at this point.

## 2026-08-25 — macOS migration handoff + expanded design doc merged

- Added `scripts/setup_macos.sh` — idempotent Homebrew-based installer (`samtools`, `bcftools`,
  `htslib`, `blast`, `python@3.12`; venv at `~/venvs/trio-genome`; registers Jupyter kernel
  `trio-genome-macos`). `mash` has no `homebrew-core` formula — script pulls the upstream `v2.3`
  Intel (`OSX64`) release binary into `~/bin/mash`, run under Rosetta 2; checks for Rosetta first
  and skips with an explicit message if missing.
- Added `macos-setup-handoff.md` (Mac mini next-steps at the time) — since folded into
  `HANDOFF.md`.
- Added `seq-hashing-project-handoff-7.3.2026.md`, an expanded revision of the original design
  doc — same core decisions (CDS anchor, MD5+SQ, normalization) plus new sections since folded
  into `HANDOFF.md`: a Track 2 population/ancestry data plan (1000G/HGDP/SGDP panels, Kidd
  AISNPs, ascertainment-bias caution), an optional IUPAC/genotype-fingerprint layer for Track 1,
  a feasibility analysis of ethnicity-from-coding-only (shallow — continental resolution only),
  a coding-vs-genome-wide PCA demo plan, and a chr22 hash-count estimate (~5,000–8,000 distinct
  sequences for reference + trio baseline).
- Added `TODO.md` — despite the name, a session-mechanics record (commands run, environment/auth
  checks, recommendations) for the 2026-07-04 working session, kept separate from this file at
  the time because it covered session mechanics, not just project state. Its project-relevant
  content is folded into `HANDOFF.md`/this file; its account/model/privacy notes were
  session-specific and not carried forward, as they don't describe project state.
- MacBook "Neo" confirmed fully set up and verified as of 2026-08-17 (see that date's context
  below) — `samtools` 1.24, `bcftools` 1.24, `htslib` 1.24, `blast` 2.17.0, `mash` 2.3 (Intel via
  Rosetta), Python 3.12.14 venv, kernel `trio-genome-macos`, smoke-tested against
  `scripts/gencode_cds_extract.py`.
- Environment migration context: development moved off a Windows/WSL2 machine onto two Macs
  (Mac mini, MacBook "Neo") so Homebrew could provide `samtools`/`bcftools`/`bgzip`/`tabix`/
  `blast` natively, without a WSL2 VM layer.

## 2026-07-03 — Trio inheritance (Track 1) demonstrated on real GIAB data

- `notebooks/04_trio_inheritance.ipynb`: built HG002's two haplotype CDS sequences per
  transcript by overlaying phased VCF variants directly onto the already-validated reference
  exon sequences (via GTF genomic CDS-exon coordinates), instead of `bcftools consensus` against
  a whole-genome FASTA — avoided an ~845MB same-release GRCh38 genome download and reused 100%
  of the notebook 02/03 validation. Classified each haplotype against HG003/HG004 by a per-site
  allele-membership test, which needs no parental phasing at all (only the child needs to be
  phased).
- REF-base sanity check (strand-aware coordinate mapping) passed with 0 mismatches across all
  1311 SNV-only transcripts before trusting any classification result.
- Result, of 1341 validated chr22 transcripts:
  ```
  681  no_variants_in_child        675  uninformative_shared
  230  maternal_origin             201  paternal_origin
   75  phase_incomplete             30  has_indel
    4  no_parental_match
  ```
  **431 confident parent-of-origin calls** (201 paternal + 230 maternal).
- Investigated all 4 `no_parental_match` cases rather than leaving them unexplained: all four
  trace to one locus (gene `ENSG00000100033`, across 4 transcript isoforms). Corrected an initial
  mischaracterization ("both parents homozygous C/C") after checking the raw VCF directly:
  neither parent has *any* record at that position (implied homozygous-reference by absence),
  while the child is heterozygous — and the site carries GIAB's own
  `difficultregion=hg38.segdups_sorted_merged,lowmappabilityall` INFO tag, the signature of a
  mapping artifact (reads from a paralogous locus), not a real de novo call.
  `difficultregion` adopted as per-haplotype metadata generally from this point: confident calls
  touch a difficult region ~7.5–8.7% of the time vs. **100%** (4/4) for `no_parental_match`.
- Persisted 1110 rows into the existing SQLite schema — no schema change needed (child haplotype
  rows distinguished by `accession = "{transcript_id}.HG002.{hap}"`, `source = "GIAB"`,
  classification recorded in `evidence`).
- Abandoned approach: originally planned to download and apply GIAB's
  `_benchmark_noinconsistent.bed` to resolve the 4 `no_parental_match` cases. GIAB's own
  `README_v4.2.1.txt` (line 7) shows this BED is just the primary high-confidence region file
  already implicit in the main benchmark VCF's PASS filter, not a separate trio-Mendelian-
  consistency filter — confirmed empirically too (the known-artifact site falls *inside* this
  BED's intervals, which would be impossible if it excluded Mendelian-inconsistent sites).
  Dropped in favor of the `difficultregion` tag.
- Chose GIAB HG002/HG003/HG004 (Ashkenazi trio) over the older pipeline's 1000 Genomes NA12878
  trio specifically because Track 1 (exact-identity inheritance) needs real haplotype-resolved
  input, and GIAB publishes a trio+StrandSeq phased VCF for the child.
- Documentation: updated `README.md` (new "Sequence-Hashing POC" section, incl. an ASCII diagram
  explaining genotype phasing) and created this `CHANGELOG.md`.

## 2026-07-02 to 2026-07-03 (approx) — Reference proteome, CDS extraction, hash catalog, GIAB data acquired

- Pivoted to the **CDS-anchored sequence-hashing POC**, a new and separate effort from the
  existing v1–v3 gene-level SHA256 pipeline (`scripts/trio_genome_script.sh` lineage). Anchor
  unit = CDS (start codon → stop codon), not gene genomic span, because gene boundaries are
  annotation-fuzzy while CDS boundaries are locally exact.
- **Digest choice decided**: MD5 as primary (samtools/refget-aligned), ga4gh SQ kept alongside
  as the independent, stronger digest.
- `notebooks/01_hash_functions.ipynb`: defined and verified `normalize_protein`, `md5_digest`,
  `ga4gh_sq_digest`. Corrected the design doc's worked example in the process: fetched
  `NP_000207.1` live from NCBI eutils expecting human preproinsulin, found it is actually
  Kallmann syndrome 1 protein (ANOS1, 787 aa). The correct accession, `NP_000198.1` (110 aa),
  reproduces the originally-stated MD5 (`12e9c9e4e2835c302e8ba615115edda3`) and SQ
  (`SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`) exactly — the hash *formulas* were right, only the
  accession label was wrong.
- Downloaded and MD5-verified GENCODE v46 chr22-relevant files into `data/reference/`
  (`gencode.v46.basic.annotation.gtf.gz`, `gencode.v46.pc_transcripts.fa.gz`,
  `gencode.v46.pc_translations.fa.gz`) against `data/reference/md5sum.txt`.
- `notebooks/02_cds_extraction.ipynb`, promoted to `scripts/gencode_cds_extract.py` once
  validated: chr22 transcripts with CDS entries: 1404; present in both FASTAs: 1398;
  **1341/1398 (96%) pass both the splice-length invariant and `translate(CDS) == protein`**.
  Reproduced the design doc's documented "#1 silent error" empirically — GTF `CDS` features
  exclude the stop codon, but `pc_transcripts.fa`'s `CDS:` header span includes it — as a
  consistent 3nt offset across all 1398 chr22 CDS-transcripts checked. All 57 exceptions
  explained, none unexplained: 47 incomplete CDS annotations (`cds_start_NF`/`cds_end_NF`/
  `mRNA_start_NF`/`mRNA_end_NF` tags, mostly IG/TR immune-receptor gene segments awaiting later
  V(D)J joining) and 10 from `TXNRD2` (tagged `seleno` — an internal in-frame UGA recoded to
  selenocysteine biologically, read as a premature stop by a naive codon-table translation). One
  further transcript, `YPEL1-204` (tagged `non_ATG_start`), uses a near-cognate start codon whose
  literal translation disagrees with the canonical protein only at position 0 — accepted as a
  documented override.
- `notebooks/03_sqlite_catalog.ipynb`: built the SQLite hash catalog (`data/derived/chr22/
  hash_catalog.db`) + `pyfaidx`-indexed FASTA blob store (`chr22_proteins.fa`, `chr22_cds.fa`,
  `chr22_exons.fa`). **16,176 rows inserted** (1341 AA + 1341 CDS + 13,494 exon), across 443
  chr22 genes. Round-trip check (SQLite hash → FASTA lookup → re-hash) passed.
- GIAB HG002 (phased)/HG003/HG004 chr22 VCFs downloaded into `data/giab/` via remote range-fetch
  (`bcftools view -r chr22 <url>`), not full-genome downloads. Finding: the **standard** GIAB
  v4.2.1 benchmark VCF is fully **unphased** (0/50,284 chr22 HG002 variants carry a `|`
  separator, checked empirically). The actual phased file, found by browsing GIAB's FTP
  `SupplementaryFiles/` directory rather than guessing a filename, is
  `HG002_GRCh38_1_22_v4.2.1_benchmark_phased_MHCassembly_StrandSeqANDTrio.vcf.gz` — only 43.6%
  phased on chr22 (21,944/50,284 variants).
- Set up a WSL2 (Ubuntu) environment for tools not natively available on the Windows dev machine
  at the time: `samtools` 1.19.2, `bcftools` 1.19, `bgzip`, `tabix`, `mash` 2.3, `dustmasker`/
  `segmasker`; Python venv `~/venvs/trio-genome` (`jupyter`, `ipykernel` 7.3.0, `biopython` 1.87,
  `pyfaidx`); registered Jupyter kernel `trio-genome-wsl`.
- `.gitignore`: added `data/derived/` and `*.db`.

## 2025-07-26 (approx grouping of same-day commits) — v1→v3 gene-level SHA256 pipeline; pivot to protein-coding focus

- Initial script (v1.0) generated per-sample haplotype genome FASTAs from 1000 Genomes
  high-coverage VCFs for the **NA12878 trio** (child NA12878, mother NA12891, father NA12892),
  extracted genes, and computed SHA256 hashes per gene — the pipeline that predates and is
  unrelated to the CDS-anchored work above.
- v2.0: chromosome-by-chromosome processing, to handle 1000 Genomes high-coverage VCF file
  sizes (chr22 alone observed at ~26GB compressed before this rewrite).
- v3.0 ("Major release"): added protein-coding-only GTF filtering against GENCODE v46 basic
  annotations — **~65% fewer genes processed** (~20,000 protein-coding vs. ~60,000 total
  genomic features), reducing storage and processing time accordingly. This SHA256/gene-level
  approach uses a different trio, anchor unit, and digest scheme than the later CDS-anchored
  MD5/SQ work — the two are not incremental versions of each other.
- `data/reference/md5sum.txt` added for GENCODE download verification; `.gitignore` updated for
  large data files (`*.fa`, `*.vcf.gz`, etc.).
