# Changelog

Append-only, dated history — newest entries at the top. For current project state (design
decisions, known gaps, active TODO), see [`HANDOFF.md`](HANDOFF.md), which is edited in place
rather than appended to.

Dates are pulled from `git log` where a commit exists for the work; entries pulled from prose
(handoff docs, session notes) rather than a commit are marked **(approx)**.

---

## 2026-09-03 — Phase 2 salt transfer wired

- **`scripts/aws/phase2_deploy.sh`** (new): deploy-side prep for Phase 2 on an already-running
  instance — transfers the pipeline scripts, full genome-wide GENCODE reference, all 24
  chromosomes' CDS-region BED files, and the salt file. The salt file is `scp`'d over (encrypted
  in transit) and `chmod 600`'d on arrival, matching `deploy_and_test.sh`'s existing file-transfer
  pattern; the script's argument is a path, so the salt's contents never appear in a tool call,
  `ps aux`, or shell history. Verified the missing-file guard fails fast before any SSH attempt.
- Explicitly scoped as deploy-side prep only — the actual batch loop (per-individual S3 fetch +
  hash + load across all individuals/chromosomes, parallelized) is separate, undesigned work,
  flagged clearly in the script's own output and in `scripts/aws/README.md`.

## 2026-09-03 — Catalog schema built; salt-file handling added; golden AMI baked

- **`batch_haplotype_hash.py`**: added `salted_hash_sq` (previously only MD5 got salted, not the
  stronger SQ hash), renamed `haplotype` column to `representation`. Re-verified against the
  known-good `ENST00000319363.11` value after the change (unchanged), plus a `--mode haplotypes`
  smoke test (1,112 rows, consistent with the prior count).
- **`scripts/load_individual_hashes.py`** (new): creates and loads `individual_hash_catalog.db`
  per the schema decided earlier this session (flat table, `UNIQUE(transcript_id, sample_id,
  representation)`, `INSERT OR REPLACE`). Verified with real data: fresh load, idempotent reload
  (no duplicate rows), re-salt correctness (unsalted hash stays identical, salted hash + label
  update cleanly, no duplicates), NULL handling for both `het_count` and the salted columns, and
  `iupac`/`hap0`/`hap1` rows for the same individual coexisting without conflict.
- **`--salt-file` added** to `batch_haplotype_hash.py`: reads the salt from a file instead of a
  command-line value — avoids the salt appearing in `ps aux` or shell history, and means it never
  needs to be typed into this chat either. Takes precedence over `--salt`/`HASH_SALT`.
- **Custom AMI baked**: `ami-020985bb7982d427b` (`trio-genome-bcftools-20260903`) — Amazon Linux
  2023 with `micromamba`/`bcftools 1.24` pre-installed, removing the ~1 minute install step from
  future launches. `launch_smoke_test.sh` gained an optional `--golden` flag to use it. Verified
  by launching an instance with `--golden` and confirming `bcftools` runs immediately with no
  install step, then terminated.

## 2026-09-03 — bcftools solved via micromamba; real BED-restricted fetch timing measured

- **`scripts/aws/test_s3_fetch.sh` updated**: replaced the failed `dnf install bcftools` attempt
  (not in AL2023's default repos) with `micromamba` (bioconda's static package manager) — clean
  install, `bcftools 1.24`, well under a minute of actual install time.
- **Real snag hit and fixed**: AL2023's `tar` shells out to an external `bzip2` binary not
  installed by default, so extracting micromamba's release archive failed
  (`tar (grandchild): bzip2: Cannot exec`). Fixed by using Python's `tarfile` module instead
  (bzip2 support is built into the standard library — no external binary needed).
  Also caught the same `${1:?...}`-apostrophe-in-double-quotes bash parsing quirk hit earlier
  this project in a different script — avoided by not using a contraction in the error message.
- **Real BED-restricted single-sample fetch timing, finally measured**: ran the actual technique
  (`bcftools view -s NA19240 -R chr22_cds_regions.bed <S3 URL>`) directly on a colocated `us-east-1`
  instance — **~8 minutes wall-clock**, producing a valid 3.2MB `.vcf.gz` with 27,876 variants.
  Compare to the ~40 minutes previously measured for the same individual/chromosome *without*
  region restriction — confirms BED-restriction is still doing real, necessary work even at
  AWS-colocated network speed, consistent with the earlier CPU-bound-parsing diagnosis (not a
  bandwidth problem). This replaces an extrapolation with a real number for Phase 2's
  per-individual fetch cost.
- Instance ran longer than the earlier smoke tests (~15 min total including the install), still
  a few cents; terminated and confirmed stopped immediately after.

## 2026-09-03 — Phase 2 scope clarified; genome-wide CDS BED files generated; catalog schema decided

- **Real inconsistency caught and fixed**: `scripts/aws/README.md`'s Phase 2 plan literally said
  "chr22 CDS-region slice," while `HANDOFF.md`'s cost/timing estimates were genome-wide
  extrapolations — the two didn't describe the same amount of work. Clarified with the user:
  Phase 2 is **scaling the existing coding-region hash pipeline to all 2,504 individuals AND all
  chromosomes**, still coding-only by design — explicitly *not* the separate whole-genome
  ancestry pipeline (Mash/sourmash, PCA/ADMIXTURE) that Track 2's own design section says the
  real ancestry signal actually needs. `scripts/aws/README.md` updated to state this precisely.
- **`scripts/generate_cds_bed.py`**: generates one merged, sorted CDS-region BED file per
  chromosome (`data/reference/cds_regions/{chrom}_cds_regions.bed`), extending the one-off chr22
  BED file used in the impostor test to all 24 chromosomes (chr1–22, X, Y; chrM excluded — not
  present in 1000 Genomes' per-chromosome joint-VCF releases). **201,612 merged regions total**,
  restricted to the same *validated* transcript set the hashing pipeline actually processes, not
  just any CDS-bearing transcript in the raw GTF (raw GTF parsing alone gives 4,300 chr22 regions
  vs. the correct 4,186 — confirmed by a first, wrong attempt, then fixed by reusing
  `gencode_cds_extract.extract_chrom`'s validation). **Verified, not assumed**: regenerated chr22
  and diffed byte-for-byte against the original, already-used
  `data/giab/impostor_test/chr22_cds_regions.bed` — exact match.
- Reaffirmed BED-restriction is still necessary even with fast colocated S3 access (today's
  measured ~62 MB/s): the original bottleneck was `bcftools` parsing every one of 2,504 samples'
  columns per site before discarding unwanted ones — a CPU cost independent of network speed.
- **`individual_hash_catalog.db` schema decided**: one flat table (not split into
  unsalted/salted tables), after confirming the real usage model is one salt at a time, not
  multiple coexisting salt-versions per individual. `UNIQUE(transcript_id, sample_id,
  representation)` constraint pairs with `INSERT OR REPLACE` as a re-run guard — safe to rerun
  the batch loader after an interrupted run or a deliberate re-salt without manual cleanup. Two
  small fixes flagged for `batch_haplotype_hash.py` alongside this: rename `haplotype` column to
  `representation` (it's not always a haplotype post-IUPAC-decision), and add `salted_hash_sq`
  (currently only MD5 gets salted, not the stronger SQ hash) — not yet implemented.

## 2026-09-03 — S3 fetch tested directly on an instance

- **`scripts/aws/test_s3_fetch.sh`**: launched a second `c6i.xlarge` instance to test the one
  thing Phase 1 deliberately deferred — fetching from `s3://1000genomes` on the instance itself,
  not just from the Mac mini.
- **Bucket reachability confirmed from inside AWS**: `200 OK`, no credentials needed, same as
  the earlier Mac mini check.
- **Real throughput measured, not estimated**: 100MB byte-range fetch in 1.62s ≈ **~62 MB/s
  (~500 Mbps)**, colocated in `us-east-1`. First actual data point behind the "colocated instance
  is fast" reasoning the Phase 2 cost/timing estimates in `HANDOFF.md` were resting on.
- **BED-restricted single-sample slice technique (the actual per-individual fetch method used in
  the impostor test) could not be timed on-instance**: `bcftools` isn't in Amazon Linux 2023's
  default `dnf` repos (`No match for argument: bcftools`). Correctness of the technique itself
  isn't in question (already proven on the Mac mini); only its on-AWS wall-clock time remains
  unmeasured, pending an alternate install path (source build / conda / `pysam` via pip).
- Instance terminated immediately after, confirmed stopped.

## 2026-09-03 — Phase 1 AWS smoke test: passed

- **AWS credentials configured and verified** on the Mac mini: IAM user `nelson-admin` (not
  root), region corrected from a stray `us-west-2` default to `us-east-1` (colocated with
  `s3://1000genomes`, verified 2026-09-02). New EC2 key pair `trio-genome-aws` created.
- **`scripts/aws/` smoke test run end-to-end for real**: launched one `c6i.xlarge` instance,
  deployed the minimal file set (~92MB: `gencode_cds_extract.py`, `batch_haplotype_hash.py`,
  GENCODE v46 reference, HG002's chr22 phased VCF), ran `batch_haplotype_hash.py --mode iupac`
  on the instance, pulled the result back, and diffed against the already-verified local hash.
  **Result: byte-identical** — `ENST00000319363.11` → `hash_md5=3bbd34faba73bc134825f8f07a296436`,
  `het_count=5`, matching the Mac mini exactly. 631 hashes written, 687 no-variant + 23
  indel-containing transcripts correctly skipped, full run took 7.76s on-instance (Amazon Linux
  2023, Python 3.9.25 preinstalled, no setup needed). Instance terminated immediately after,
  confirmed stopped — total wall time ~10 minutes, cost a few cents.
- **Real deviation from plan, now fixed in the script**: requested spot capacity for
  `c6i.xlarge` in `us-east-1` was unavailable (`InsufficientInstanceCapacity`) at test time.
  `launch_smoke_test.sh` was changed to launch **on-demand** by default rather than spot — a
  small cost increase (~$0.17/hr vs. ~$0.05/hr) traded for launch reliability, acceptable at
  smoke-test scale; worth reconsidering for Phase 2 (retry/fallback logic) where wall-clock
  hours are non-trivial.
- Confirms the compute pipeline — not just the algorithm — runs correctly on real AWS
  infrastructure, extending the project's established cross-platform reproduction pattern
  (Windows/WSL2 → Mac mini, 2026-08-31) one hop further: Mac mini → AWS.
- Still deliberately untested: fetching data directly from `s3://1000genomes` on an instance
  (see `scripts/aws/README.md`); Phase 2 (the real population-scale batch) remains un-started,
  needs its own explicit go-ahead and a freshly-generated salt.

## 2026-09-02 — Genome-wide scaling measured; per-individual bottleneck diagnosed; AWS options verified

- **Real (not simulated) genome-wide timing**: ran the actual extraction+hashing pipeline against
  the genome-wide GENCODE v46 files already on disk (never chr22-only, just chr22-filtered by the
  existing code) — 64,414 validated transcripts, all isoforms, whole genome, unsalted *and*
  salted, in **13.2 seconds total**. Measurement only, not persisted — no database was written to;
  `data/derived/chr22/hash_catalog.db` is unchanged. Confirms hashing was never the bottleneck.
- **Real per-individual timing, and the actual bottleneck found by inspection**: 11.76s to process
  one individual (HG002) on chr22 alone — slower than building the *entire genome's* reference
  catalog with zero individuals. Root cause: `variants_in_range()` linearly scans every variant in
  the chromosome for every exon of every transcript (~670 million comparisons per individual on
  chr22 alone) — a fixable software inefficiency, not an inherent cost. Extrapolated (with a
  stated likely-underestimate caveat) to ~9.4 min/individual genome-wide, ~16.4 days for all 2,504
  1000 Genomes individuals sequential/single-threaded/unoptimized.
- **Data acquisition for population-scale sources, verified against the actual hosts**: 1000
  Genomes high-coverage data has no per-sample genotype VCFs for this release (confirmed by
  browsing the real FTP structure — only joint multi-sample files, chr1 alone 130GB); the same
  joint VCFs are mirrored on AWS S3 Open Data (`s3://1000genomes`, confirmed by listing the bucket
  directly) — zero egress cost, high throughput from a colocated EC2 instance; Aspera/FASP support
  for this specific mirror checked and left unconfirmed (a documentation URL didn't resolve to
  real content) rather than asserted either way.
- **EC2 cost estimate for a full 1000-Genomes batch run**: ~$6–20 with today's unoptimized code
  (spot pricing, colocated instance), likely under $5 once the indexing fix lands — noted as
  approximate/typical pricing, not fetched live, but robust as an order-of-magnitude figure.
- All of the above recorded in `HANDOFF.md` under a new "Scaling to genome-wide and population
  scale" section.
- **The fix landed and was verified the same day.** Added `scripts/batch_haplotype_hash.py`,
  replacing `variants_in_range()`'s linear scan with a sorted-position index + `bisect` (sort each
  individual's variants once per chromosome, binary-search per exon instead of rescanning every
  variant every time). Measured on real HG002 chr22 data: the haplotype-extraction-and-hashing
  phase dropped from ~11.7s to **0.03s — a ~390x speedup**. Correctness verified, not assumed:
  cross-checked all 1,110 overlapping accessions against the existing, already-verified SQLite
  catalog — **1,110/1,110 exact MD5 matches, zero mismatches** (2 extra rows in the new output are
  expected and understood: parent-only-indel cases the old trio-wide check excluded that this
  single-individual version correctly includes). Script is CLI-driven, writes an isolated
  per-individual `.tsv.gz`, no shared-database writes — safe to run many in parallel. No salt
  hardcoded, by design (see the earlier salt-secrecy discussion); pass one via `--salt`/
  `HASH_SALT` or omit for unsalted-only output.
- **Double-checked the AWS S3 data-access URL before relying on it further**: verified
  `https://1000genomes.s3.amazonaws.com/1000G_2504_high_coverage/working/
  20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.
  recalibrated_variants.vcf.gz` with a real `bcftools view -h` call (not just a bucket listing) —
  works end-to-end, same as the EBI FTP mirror.
- Remaining before an actual EC2 run: provisioning/running on a real instance (today's
  cost/timing figures are still estimates until one actually runs); the reference-catalog rebuild
  (~3.1s) is now the dominant per-individual cost since the real bottleneck is fixed, and is
  currently redundantly rebuilt on every invocation — a batch orchestrator should build it once
  and reuse it across all individuals.
- **AWS CLI installed** (`brew install awscli`, v2.36.37) and added to `scripts/setup_macos.sh`
  for future machines. Explicitly not the same as provisioning anything: no AWS account or
  credentials are connected to this environment, `aws configure` hasn't been run, and nothing has
  been requested/authorized to spin up billable resources — that stays a separate, explicitly
  confirmed step whenever it actually happens.
- **IUPAC-collapsed genotype representation decided (over paternal/maternal-separated haplotypes)
  for Track 2, and implemented the same day.** Reasoning: most population ancestry panels
  (1000 Genomes, HGDP, gnomAD) have no parent samples to derive paternal/maternal from in the
  first place; ancestry methods (PCA/ADMIXTURE/F_ST) never use phase; genotype is universal while
  phase isn't (75/1,341 chr22 transcripts are lost to `phase_incomplete` in the phased approach,
  recoverable with IUPAC collapse); and two arbitrarily-labeled haplotype hashes create a
  label-swap comparison problem across individuals that a single IUPAC value doesn't have. Full
  reasoning, including the honest counter-case for population-phased haplotypes in
  haplotype-sharing methods, recorded in `HANDOFF.md`.
  - Implemented in `scripts/batch_haplotype_hash.py` as `--mode iupac` (new default); the
    original phased behavior stays available as `--mode haplotypes` for Track 1 compatibility.
  - **Verified two independent ways, not just run once**: `--mode haplotypes` re-checked against
    the existing verified SQLite catalog after the refactor (still 1,110/1,110 exact matches,
    confirming no regression); the IUPAC output cross-validated by reconstructing the expected
    sequence directly from the two already-published-correct haplotype hashes
    (`ENST00000319363.11`) via a completely independent code path — both derivations produced the
    identical MD5. On chr22: 631 transcripts get a usable IUPAC hash with zero phase-related
    exclusions, vs. 556 in haplotype mode (which still loses 75 to `phase_incomplete`).
- **Exploratory salted IUPAC run saved, deliberately kept separate from the catalog.**
  `data/derived/chr22/HG002_chr22_iupac.tsv.gz` (631 rows, real `salted_hash_md5` values using a
  local-exploration-only salt) and `data/derived/chr22/SALT_DO_NOT_COMMIT.txt` — both confirmed
  gitignored (`data/derived/` is unconditional) before writing, not assumed after. No merge into
  `hash_catalog.db` was done or attempted; the schema doesn't even support it yet (`seq_type`
  `CHECK` constraint has no IUPAC value, no `salted_hash` column) — that stays future work.
- **`het_count` column verified against the actual sequence**, not just the code: reconstructed
  `ENST00000319363.11`'s real hashed sequence and counted literal IUPAC letters by position —
  exactly 5, matching the reported `het_count=5`. Confirmed it counts heterozygous positions
  specifically (homozygous-alt sites are in the underlying variant set but don't increment it).
- **Row ordering confirmed**: genomic position along the chromosome (inherited from GENCODE's
  own pre-sorted GTF, never re-sorted anywhere in this code), not transcript ID — verified against
  real coordinates, not inferred from appearance.
- **Clarified and documented: zygosity (hom/het) needs no parental data, unlike phasing.**
  Recorded the distinction plainly in `HANDOFF.md` since it's easy to conflate given how much of
  this project is about phasing specifically — hom/het is ordinary single-individual genotype
  calling (already the `GT` field in every VCF here), phasing is the separate, harder problem.
  Also recorded why homozygous-alt sites carry distinct ancestry signal (genotype dosage weighting
  in PCA/ADMIXTURE, runs-of-homozygosity as a founder-effect signal directly relevant to the
  Ashkenazi GIAB trio's own population, and a representation-specific note that hom-alt/hom-ref
  positions stay fully specific in the hashed sequence while het positions fold into a coarser
  IUPAC code).
- **Two new parked research questions added** (continuing the 2026-09-01 list): whether protein
  (AA) sequences offer any ancestry-inference advantage over nucleotide/CDS level, or a path
  toward functional-significance mapping once ancestry is AA-derived; and whether hashing AA
  instead of nucleotide sequences gives any real speed advantage, for both the reference catalog
  and per-individual batch processing — with a preliminary caveat noted for each (protein hashing
  collapses synonymous-site variation that ancestry work relies on; today's actual bottlenecks at
  both layers, GTF parsing and reference-catalog rebuilds, aren't sequence-hashing cost in the
  first place) but neither actually measured yet.
- **Reminder recorded** in `HANDOFF.md`'s AWS TODO item: the exploration salt
  (`TodayI$Miercole$`) must not be reused for the real population-scale AWS run — generate a
  fresh one when that happens.

## 2026-09-01 — Empirical false-positive test for Track 1; salt-hashing evaluated; TODO expanded

- **Documented finding: Track 1's classification does not confirm paternity, verified
  empirically, not just argued.** Substituted `NA19240` (unrelated 1000 Genomes YRI sample) for
  the real father (HG003) and reran `explainable_by()` against the 201 real `paternal_origin`
  haplotypes. Result: 71 (35.3%) still look "consistent" with the random impostor at the
  single-locus level; 130 (64.7%) correctly exclude him. Those 201 haplotypes span only 64
  distinct genes (linkage disequilibrium means they aren't 201 independent tests — haplotypes
  from the same gene share the same underlying DNA). Treating the 64 genes as roughly
  independent, the joint miss probability is `0.353^64 ≈ 10⁻²⁹`. Full writeup, including
  explanations of linkage disequilibrium and likelihood-ratio-based paternity analysis (and why
  this pipeline computes neither), added to `HANDOFF.md`.
  - Method note: the first attempt (whole-chromosome remote fetch of one sample from the
    2,504-sample 1000G high-coverage VCF) was abandoned after ~40 minutes for only 0.57% of
    chr22 — sample-subsetting via `bcftools -s` doesn't reduce network transfer, since every
    sample's INFO/FORMAT fields still have to be streamed and decompressed before unwanted
    columns are discarded. Switched to a BED file of just the 4,186 CDS-exon blocks (0.7 Mb vs.
    chr22's 40.3 Mb), which completed in a reasonable time. Files kept at
    `data/giab/impostor_test/` (gitignored via the existing `*.vcf.gz` pattern).
- **Evaluated (not adopted) salting hashes with a private secret**, combined with the
  already-planned IUPAC-collapse layer. Full pros/cons analysis added to `HANDOFF.md`'s Hash
  schemes section: the core tension is that salting is fundamentally incompatible with this
  project's refget-compatibility goal (a salted hash can never match a public checksum), and the
  current dataset (GIAB/1000G, already public) has nothing private to protect yet. Recommended:
  revisit only if/when real private individuals' sequences are hashed, and then as a separate
  column alongside the unsalted one, using a real keyed-hash construction (HMAC) rather than
  naive concatenation.
- **Active TODO expanded** with 5 items from this session: building the IUPAC-collapsed
  representation on already-downloaded data (not just resolving the design question), a
  download-strategy writeup for scaling past chr22 (informed directly by the slow-fetch problem
  above), an expanded indel-handling writeup (the actual coordinate-math problem, not just "do
  it"), a combined indels/segmental-duplication/difficult-regions strategy item (prompted by the
  `ENSG00000100033` case), and a pointer to the salt evaluation.
- **External validation against Ensembl — the open "validate against a known-good external
  reference" TODO, done for real, chr22, full match.** No bulk-downloadable refget checksum
  database exists (refget is a query API, not a static dump) — instead, pulled Ensembl release
  112's own CDS + protein FASTA (confirmed as the correct release match by reading GENCODE v46's
  own GTF header: `version 46 (Ensembl 112)`, not assumed), verified both downloads against
  Ensembl's published `CHECKSUMS`, and cross-hashed against this project's own GENCODE-derived
  chr22 catalog. **1341/1341 protein sequences byte-identical; 1341/1341 CDS sequences match**
  once the already-documented stop-codon convention difference is accounted for (Ensembl's CDS
  FASTA includes the stop, this project's canonical form excludes it) — hashes match on both
  layers, zero mismatches. This validates the hash formulas *and* the extraction/translation
  logic simultaneously, against a fully independent source.
  - `scripts/validate_against_ensembl.py` added (reusable — rerun for any other chromosome by
    changing one argument, no new design needed, since the genome-wide Ensembl downloads already
    cover the whole genome).
  - `data/reference/validation/chr22_ensembl112.{cds,pep}.fa.gz` (~1.1 MB combined) committed —
    small chr22-only subsets, kept via a `.gitignore` exception so this check can be rerun
    without re-fetching the full 23+15 MB genome-wide Ensembl downloads. Those genome-wide files
    stay gitignored, machine-local; `data/reference/validation/manifest.tsv` records their source
    URLs and MD5s.
  - One `.gitignore` lesson worth recording: the exception was first added *before* the file's
    later blanket `*.gz` rule and got silently overridden — gitignore applies rules in order, so
    a negation has to come after every rule that would otherwise match. Fixed and commented in
    place so it doesn't get re-broken by a future edit.
- **`PROJECT_MAP.md` updated**: added a "Data sources" table up front (GENCODE v46 = Ensembl 112
  as the pipeline's actual source of truth; Ensembl used only for external validation; NCBI
  RefSeq used only for one worked-example accession, never a bulk source) plus the three concrete
  ways GENCODE/Ensembl and NCBI RefSeq genuinely differ (ID namespace, stop-codon inclusion,
  evidence-tier vocabulary) — meant to prevent silently mixing sources after a break. Also fixed
  the timeline's stale endpoint (still said "about to run notebooks" after that had already
  happened) to reflect today's two closed validation TODOs.
- **Cross-platform `.fai` inconsistency found and fixed.** Diffing `chr22_cds.fa.fai` between the
  Mac mini and the original Windows-generated file showed `LINEWIDTH` = 61 vs. 62 for the same
  60-base line width. Root cause: `write_fasta()` used plain `open(path, "w")`, and Python
  translates outgoing `\n` to the OS's native line separator on write (`\n` on macOS/Linux,
  `\r\n` on Windows) unless `newline=""` is passed. Verified this was cosmetic, not a
  sequence-correctness bug — zero `\r` bytes found in the Mac file, and `.fai`-based random access
  already accounts for however many terminator bytes a given file actually has, which is exactly
  why every cross-platform hash comparison this session matched despite the quirk existing the
  whole time. Fixed anyway for portability: added `newline=""` to both
  `notebooks/03_sqlite_catalog.ipynb`'s `write_fasta()` and `scripts/validate_against_ensembl.py`'s
  `write_fasta_gz()`. No-op on the Mac (already LF); only matters if Windows is used again. Not
  yet regenerated on disk — takes effect on the next notebook 03 rerun.
- **Seven Track 2 research questions parked** (raised, not yet investigated, per explicit
  request): CDS-restricted SNP relevance-ranking for ethnicity; existing public AIM-SNP
  databases (plus a concrete finding — the 1000 Genomes VCFs already downloaded for the impostor
  test already carry per-population AC/AF breakdowns, partial raw material for this already on
  hand); SNP-hash window sizing (confirmed the >20nt uniqueness intuition matches the math behind
  Mash's existing k≈21–31 choice); why sequence content alone can't resolve genomic
  duplications (tied to the already-documented `ENSG00000100033` difficultregion case);
  microarray/CNV data as a separate ingestion path, not a hash-catalog extension; short- vs.
  long-read tradeoffs for ancestry specifically (vs. SV/CNV work); and two future directions —
  hash-based population classification, and a new not-yet-scoped functional-significance
  extension. Recorded in `HANDOFF.md` with enough context to act on later.
- **Client-lookup service architecture for salted hashes — evaluated, decision deliberately left
  open.** Extended the earlier salt evaluation with a concrete design for letting a client check
  their own DNA against a published salted-hash catalog without exposing the private
  gene/accession mapping. Two-database structure (public salted-hash-only list + private mapping
  table) is settled. The protocol for how the client computes a matching salted hash is not: salt
  embedded in client-side software (raw sequence never leaves the client's machine, but the salt
  itself is only weakly secret against reverse-engineering) vs. server issues a per-session salt
  and the client hashes-and-sends-back (analyzed in detail — this fails to protect client data,
  because the server already knows its own salt and can run a candidate/dictionary attack using
  publicly cataloged human variation, which is small and enumerable per locus; only genuinely
  novel, uncataloged variants stay protected this way, which is a minority of any real genome).
  Recorded in `HANDOFF.md` as a real, non-obvious finding — unique-per-client salting does not
  fix this, since it only raises the cost for a third-party eavesdropper, not the server itself.
  No protocol was found that gives both "a third party computes and compares correctly" and "raw
  sequence known only to the client" without heavier machinery (Private Set Intersection,
  homomorphic encryption, trusted-execution enclave) — named as the real answer if this property
  turns out to be a hard requirement, not pursued further for now.

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
  TODO in `HANDOFF.md` rather than touched in this pass. (`scripts/README.md` addressed later
  the same day — see below.)
- **Second pass, same day: `scripts/README.md` rewritten, `data/README.md` retired.**
  Comparing the three README-shaped files at root/`scripts/`/`data/` found `data/README.md` was
  a genuine duplicate — its "Run analysis"/"Configuration Options"/"File Outputs"/"Version
  History" content is a garbled copy of the same `v3_commit_guide.md` heredoc retired above
  (it even had a stray literal `EOF` line left over from the heredoc), and its download commands
  duplicated `scripts/README.md`'s. Removed (`git rm`).
  One finding changed the plan, though: `docs/data_sources.md` (the file that's supposed to be
  the authoritative download-instructions doc) actually had *placeholder* URLs
  (`wget "ftp://...chr22.recalibrated_variants.vcf.gz"`, literal ellipsis), while
  `scripts/README.md` and `data/README.md` both had the real, working URLs (1000 Genomes chr22
  VCF, GRCh38 GCA reference, GENCODE v46 GTF). So instead of just deleting the duplicates, the
  real URLs and the validation commands (`bcftools view -h`, `samtools faidx`, GTF grep count)
  were moved into `docs/data_sources.md`, making it actually authoritative for the first time.
  `scripts/README.md` was then rewritten as a short index pointing to `README.md` (usage),
  `docs/data_sources.md` (downloads), and `HANDOFF.md` (POC design/setup) instead of holding its
  own copy of any of that.
- **Third pass, same day: full repo sweep for remaining stale/duplicate content**, ahead of
  running notebooks 02–04 on the Mac mini to (re)generate real results.
  - `claude-out.sh` (root, untouched since the very first commit) removed (`git rm`) — the
    original repo-bootstrap playbook (`git init`, `.gitignore`, `README.md`, `docs/
    data_sources.md` scaffolding, version tagging, Git LFS setup, branch strategy). Confirmed
    fully superseded before deleting: the repo already exists with all of that in place, no git
    tags were ever created (`git tag -l` is empty), and Git LFS/the suggested branch workflow
    were never adopted — nothing in it reflects what actually happened.
  - `scripts/trio_genome_script.sh`'s header comment still said "Version 2.0" despite already
    having the v3.0 `PROTEIN_CODING_ONLY` filter built in — corrected to "Version 3.0."
  - `notebooks/01_hash_functions.ipynb`: its first markdown cell named the now-deleted
    `seq-hashing-project-handoff.md` by filename — updated to `HANDOFF.md`. (Other notebooks'
    generic "per the handoff" phrasing left as-is — it doesn't name a specific dead file, and
    still reads correctly now that `HANDOFF.md` *is* "the handoff.") Also fixed a harmless typo
    in the same notebook's worked-example cell — a stray space inside the literal
    `preproinsulin` sequence constant (`"...LLAL LALWG..."` instead of `"...LLALLALWG..."`).
    Verified this doesn't change any result: `normalize_protein` already strips whitespace
    before hashing, so the cell's assertions passed before and after — pure source cleanup, not
    a behavior change.
  - Confirmed via repo-wide search: no remaining references anywhere to any of the retired
    files, and no other stale `scripts/trio_analysis.sh` mentions outside this file's own
    historical entries (which correctly describe what existed at the time).
- **Root cause clarified for the plain-text-FASTA-instead-of-bgzip decision.** Previously
  documented only as "the Windows dev machine had neither `samtools` nor `bgzip`" — true, but
  incomplete. The fuller story (from direct recollection): VS Code on that machine had briefly
  auto-linked to a WSL-hosted Python interpreter/kernel, so WSL tools looked reachable at first,
  then the link broke — a known failure mode of picking a WSL interpreter path from
  Windows-native VS Code without the Remote-WSL extension actually mediating the connection,
  which leaves shell/`%%bash` subprocess calls resolving against the wrong PATH even while the
  Python kernel itself still runs. Recorded in `HANDOFF.md`'s Storage section, along with the
  recommendation (Remote-WSL, project files on the WSL filesystem) for if a Windows/WSL machine
  is ever used for this project again — moot on the current native-macOS setup, but worth having
  the accurate history. Also recorded there: an evaluated (not yet acted on) bgzip+`samtools
  faidx` vs. plain-text+`pyfaidx` tradeoff for the FASTA blob store, concluding it's not worth
  switching at chr22 scope.
- Added `PROJECT_MAP.md` (root) — a short, diagram-heavy orientation doc distinct from
  `HANDOFF.md` (detailed current state) and this file (full dated history): a project-evolution
  timeline and a data-flow diagram, meant to be read first after any break to reload the mental
  model before diving into the detail files. Linked from `README.md`.
- **First full notebook run on the Mac mini: notebooks 01→04 all rerun, `data/derived/chr22/`
  populated for the first time on this machine, and verified to reproduce the original
  2026-07-03 Windows/WSL2 run exactly.** Evidence chain, checked directly rather than trusted:
  file timestamps on `data/derived/chr22/` confirm genuine fresh execution today (FASTA + `.fai`
  files at 11:41, `hash_catalog.db` updated to 11:51 — exactly the sequence notebook 03 then
  notebook 04 would produce), and the live SQLite catalog was queried directly:
  - Row counts identical: 16,176 GENCODE rows (1341 AA + 1341 CDS + 13,494 exon), 1110 GIAB
    haplotype rows.
  - A spot-checked accession's hash is **byte-for-byte identical** across platforms:
    `ENST00000332987.5.exon1` → `hash_md5 = e5b224e6fc070e352dc20de89222b13d` on both the
    original Windows/WSL2 run and the fresh Mac mini run. Expected, since hashing is
    deterministic on identical input bytes regardless of OS — but confirmed rather than assumed.
  - Full Track 1 classification breakdown reproduced exactly: 681 no_variants_in_child, 675
    uninformative_shared, 230 maternal_origin, 201 paternal_origin (431 confident total), 75
    phase_incomplete, 30 has_indel, 4 no_parental_match (all four still carrying
    `difficultregion=True`, 100%).
  - Obtained a more precise difficult-region breakdown than previously documented (the original
    entries only gave a "~7.5–8.7%" range for confident calls as a whole): `uninformative_shared`
    59/675 (8.7%), `maternal_origin` 18/230 (7.8%), `paternal_origin` 15/201 (7.5%),
    `no_parental_match` 4/4 (100%) — now recorded per-category in `HANDOFF.md`.
  - **Housekeeping, not yet resolved:** neither `notebooks/03_sqlite_catalog.ipynb` nor
    `notebooks/04_trio_inheritance.ipynb` has actually been saved in VS Code — both files on
    disk are still byte-identical to the old 2026-07-03-era git-committed version (confirmed via
    `diff` against `git show HEAD:...`), even though the kernel genuinely executed their cells
    and wrote real new data to `data/derived/`. (Notebook 04's old committed text happens to
    already show matching numbers with forward-slash paths — that's the original 2026-07-03 run
    coincidentally not using Windows path separators, not evidence of today's run; only the file
    timestamps and the live database query are.) Save both notebooks (Cmd+S) so the tracked
    `.ipynb` files show today's real macOS-native output instead of stale text.

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
