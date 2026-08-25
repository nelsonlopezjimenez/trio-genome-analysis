# Session Record — 2026-07-04

Record of this working session on the sequence-hashing POC, kept separately from
[`CHANGELOG.md`](CHANGELOG.md) (which tracks the project's technical state) because this file also
covers session mechanics — commands run, environment/auth checks, and recommendations — not just
project artifacts. Model used throughout: **Claude Sonnet 5** (`claude-sonnet-5`), continuing as the
model for this project going forward per explicit request.

---

## 1. What was done, in order

### 1.1 Picked up from the handoff document
Read `seq-hashing-project-handoff.md` and audited the existing repo (`scripts/trio_analysis.sh`, a v3.0
gene-level SHA256 pipeline against 1000 Genomes NA12878 trio) against the handoff's revised CDS-anchored
design. Found the two are fundamentally different approaches, not incremental — documented the delta
(anchor unit, digest scheme, normalization, per-exon hashing, dataset) before writing any new code.

### 1.2 Verified the handoff's worked example
Fetched the cited accession directly from NCBI eutils to check it before trusting it:
```
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&id=NP_000207.1&rettype=fasta&retmode=text"
```
Output showed `NP_000207.1` is **Kallmann syndrome 1 protein (ANOS1)**, not human preproinsulin as the
handoff claimed. Found the correct accession (`NP_000198.1`) the same way; its sequence reproduced the
handoff's stated MD5 (`12e9c9e4e2835c302e8ba615115edda3`) and SQ (`SQ.W3vopEox9qIpHK2i2i8f_YnHXK-GZOwv`)
exactly — the hash *formulas* were right, only the accession label was wrong.

### 1.3 Built notebooks 01–03 (reference proteome, chr22)
- `notebooks/01_hash_functions.ipynb` — MD5 + ga4gh SQ digest functions, verified against 1.2 above.
- Downloaded GENCODE v46 chr22-relevant files:
  ```
  curl -sS -o gencode.v46.basic.annotation.gtf.gz "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_46/gencode.v46.basic.annotation.gtf.gz"
  curl -sS -o gencode.v46.pc_transcripts.fa.gz    ".../gencode.v46.pc_transcripts.fa.gz"
  curl -sS -o gencode.v46.pc_translations.fa.gz   ".../gencode.v46.pc_translations.fa.gz"
  md5sum <file> # verified against data/reference/md5sum.txt for all three -> all OK
  ```
- `notebooks/02_cds_extraction.ipynb` — CDS-anchored extraction + validation. Output:
  ```
  chr22 transcripts with CDS entries: 1404
  chr22 CDS-transcripts present in both FASTAs: 1398 / 1404
  length invariant OK: 1357/1398   translate invariant OK: 1341/1398
  mismatch categories: 47 incomplete CDS (NF tags, IG/TR gene segments), 10 selenoprotein (TXNRD2)
  ```
  Reproduced the handoff's own documented "off-by-3" pitfall empirically (GTF `CDS` excludes stop codon,
  `pc_transcripts.fa` header span includes it). Promoted the validated logic to
  `scripts/gencode_cds_extract.py` once settled (`python scripts/gencode_cds_extract.py` →
  `validated: 1341  flagged: 57`, matching the notebook exactly).
- `notebooks/03_sqlite_catalog.ipynb` — built `data/derived/chr22/hash_catalog.db` (SQLite) + FASTA blob
  store (`pyfaidx`-indexed). Output: `total rows inserted: 16176` (1341 AA + 1341 CDS + 13494 exon).
  Round-trip check (SQLite hash → FASTA lookup → re-hash) passed.

### 1.4 WSL2 environment setup
Checked and used the existing WSL2 (Ubuntu) install:
```
wsl --status                     # Ubuntu, already installed
wsl -e bash -c "which samtools bcftools bgzip tabix mash dustmasker segmasker"   # initially: none installed
wsl -e bash -c "sudo -n true"    # confirmed sudo needs a password -> could not run apt install myself
```
Gave the user the install command to run themselves (interactive password required):
```
wsl -e sudo apt update
wsl -e sudo apt install -y samtools bcftools tabix ncbi-blast+ mash python3-pip python3-venv
```
After the user confirmed installation, verified:
```
samtools 1.19.2, bcftools 1.19, bgzip, tabix, mash 2.3, dustmasker, segmasker  -- all present
```
Then set up a Python venv without needing further sudo access:
```
wsl -e bash -c "python3 -m venv ~/venvs/trio-genome && source ~/venvs/trio-genome/bin/activate && \
  pip install jupyter ipykernel biopython pyfaidx && \
  python -m ipykernel install --user --name trio-genome-wsl --display-name 'Python (trio-genome, WSL)'"
```
Result: `Bio 1.87`, `ipykernel 7.3.0`, `pyfaidx ok`, kernel `trio-genome-wsl` registered.
(In the end, notebook 04's approach avoided needing bcftools/WSL for execution — see 1.6.)

### 1.5 GIAB trio data acquisition
Confirmed via web search + direct FTP directory browsing (not assumption) that GIAB publishes phased
trio data, then downloaded only the chr22 slice remotely (not the ~140-150MB whole-genome files per
sample):
```
bcftools view -r chr22 "<GIAB FTP URL>/HG002_..._benchmark.vcf.gz" -Oz -o HG002_chr22.vcf.gz
```
Finding: the **standard** GIAB v4.2.1 benchmark VCF is fully **unphased** (checked empirically —
`grep -o '[/|]'` on the GT field showed 0 `|` separators across 50,284 HG002 variants). Located the
actual phased file by browsing the FTP `SupplementaryFiles/` directory rather than guessing a filename:
`HG002_GRCh38_1_22_v4.2.1_benchmark_phased_MHCassembly_StrandSeqANDTrio.vcf.gz` — 43.6% phased
(21,944/50,284 chr22 variants). Wrote `data/giab/manifest.tsv` recording source URLs, release, and
phasing status per file.

### 1.6 Notebook 04 — trio inheritance (Track 1)
Built `notebooks/04_trio_inheritance.ipynb`: overlaid VCF variants directly onto the already-validated
reference exon sequences (avoiding an ~845MB same-release whole-genome FASTA download and
`bcftools consensus`), using a per-site parent-allele-membership check instead of parent-haplotype
enumeration (needs no parental phasing at all). REF-base sanity check passed (0 mismatches, 1311
SNV-only transcripts) before trusting any results. Output:
```
=== classification summary ===
    681  no_variants_in_child        675  uninformative_shared
    230  maternal_origin             201  paternal_origin
     75  phase_incomplete             30  has_indel
      4  no_parental_match
```
Investigated the 4 `no_parental_match` cases rather than leaving them unexplained — all four traced to
one locus (gene `ENSG00000100033`, seen across 4 transcript isoforms). Corrected an initial
mischaracterization ("both parents homozygous C/C") after checking the raw VCF: neither parent has *any*
record at that position (implied homozygous-reference), and the site carries GIAB's own
`difficultregion=hg38.segdups_sorted_merged,lowmappabilityall` INFO tag — added as per-haplotype
metadata generally, showing confident calls touch a difficult region ~8% of the time vs. **100%** (4/4)
for `no_parental_match` — strong evidence of a mapping artifact, not real de novo. Persisted 1110 rows
into the existing SQLite schema (no schema change needed).

**Dead end, documented rather than hidden:** originally planned to download and apply GIAB's
`_benchmark_noinconsistent.bed` to resolve the 4 cases above. Checked GIAB's own README
(`README_v4.2.1.txt`, line 7) and found this BED is just the primary high-confidence region file already
implicit in the benchmark VCF's PASS filter, not a trio-consistency filter — confirmed empirically too
(the known-artifact site falls *inside* this BED's intervals, which would be impossible if it excluded
Mendelian violations). Dropped this approach in favor of the `difficultregion` tag.

### 1.7 Documentation
Updated `README.md` (new "Sequence-Hashing POC" section: status, an ASCII diagram explaining genotype
phasing, remaining steps) and created `CHANGELOG.md` (full decision/finding/TODO log), then kept both in
sync as notebook 04 and its correction landed.

### 1.8 Environment / account questions (this conversation, not the genome project)
- Confirmed current model: **Claude Sonnet 5** (`claude-sonnet-5`).
- Explained `/model` as the way to switch models (e.g. to try Fable 5), and that availability depends on
  plan/rollout — not something changeable from within a running session.
- Checked auth mode without exposing secrets:
  ```
  echo "ANTHROPIC_API_KEY set: $([ -n "$ANTHROPIC_API_KEY" ] && echo yes || echo no)"   # -> no
  echo "ANTHROPIC_AUTH_TOKEN set: ..."                                                    # -> no
  ```
  Then inspected `~/.claude.json` for non-secret account fields only (see Privacy section below).
  Confirmed the session runs on the user's Claude subscription (OAuth login), not a pay-per-token API key.
- Recommendation given: don't switch to Fable mid-project (no comparative data on its fitness for this
  kind of structured/technical work, and this session has an established, validated track record on it);
  try Fable separately on a low-stakes task if curious about the trial window (expires 2026-07-07).
- Recommendation given: get an API key at console.anthropic.com only if building a separate
  agent/application — not needed to keep using Claude Code, which is already covered by the subscription.
- User confirmed: continue the genome project on the current model (Sonnet 5); API key exploration and
  Fable trial to happen separately, not folded into this project.

---

## 2. Privacy protections observed

- **No secrets printed or transmitted.** When checking auth mode, only non-sensitive fields were read
  from `~/.claude.json` (`accountUuid`, `emailAddress`, `subscriptionCreatedAt`, rate-limit tier labels).
  Any key containing `token`/`key`/`secret` was explicitly redacted before printing, and
  `~/.claude/.credentials.json` (the actual credential store) was never opened or read.
- **No API keys or tokens were ever generated, stored, or exposed** in this session — only their
  *absence* was checked (via environment variable presence, not value).
- **Genomic data used is public, de-identified reference material.** HG002/HG003/HG004 (GIAB Ashkenazi
  trio) and the underlying GENCODE annotations are published, consented benchmark datasets distributed
  by NIST specifically for research and methods-development use — not private clinical or patient data.
  No real-world individual's private genomic data was accessed.
- **Nothing sensitive was committed to git.** `data/`, `*.db`, and `*.gz` remain gitignored; the only
  tracked files describing downloaded data (`manifest.tsv` in `data/reference/` and `data/giab/`) contain
  only public source URLs, release names, dates, and checksums — no credentials, no raw sequence data.
- **User's own email** (from session context) was referenced only internally for the auth-mode check
  above; not shared externally or written to any file in this repo.

---

## 3. Recommendations on record

1. **Digest scheme:** MD5 as primary (samtools/refget-aligned), ga4gh SQ alongside — confirmed by user.
2. **Trio dataset:** GIAB HG002/HG003/HG004, not 1000G NA12878 — chosen after confirming GIAB's phased
   trio data actually exists and is reachable, rather than assuming.
3. **Workflow:** build incrementally in notebooks, promote validated/settled logic to `scripts/` — per
   user's explicit preference.
4. **Avoid unnecessary heavy downloads:** used remote range-fetch (`bcftools view -r chr22 <url>`) for
   VCFs and direct variant-overlay instead of `bcftools consensus` + whole-genome FASTA, avoiding an
   ~845MB download that wasn't actually necessary for this scope.
5. **Flag, don't guess, on ambiguous/artifact-shaped results** — applied consistently: `phase_incomplete`,
   `has_indel`, and now `difficultregion` are all kept as visible metadata rather than silently resolved
   one way or the other.
6. **Model choice:** stay on Sonnet 5 for this project (accepted); evaluate Fable separately, outside
   this project, before the 2026-07-07 trial window closes, so a possibly-worse fit doesn't cost project
   progress.
7. **API key:** only needed if building a separate agent/application outside Claude Code; get it at
   console.anthropic.com under a separate (metered) billing relationship from the Claude.ai subscription.

---

## 4. Open items carried forward (see `CHANGELOG.md` § TODO / Next for full detail)

1. Extend variant handling to indels (currently 30/1341 transcripts flagged `has_indel` and excluded).
2. Low-complexity flagging (`dustmasker`/`segmasker`) → populate `low_complexity_frac` (still `NULL`).
3. Spot-check a handful of the 431 confident parent-of-origin calls by hand against raw VCF records.
4. *(Deferred, Track 2)* Mash/sourmash MinHash population-distance demo.
