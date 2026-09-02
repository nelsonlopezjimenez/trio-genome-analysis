# Project Map — read this first after any break

Purpose: reload the mental model in two minutes, before diving into the detail files. This file
doesn't try to be complete or current down to the day — that's what the other two are for:

- **[`HANDOFF.md`](HANDOFF.md)** — detailed current state (design decisions, known gaps, active
  TODO). Edited in place.
- **[`CHANGELOG.md`](CHANGELOG.md)** — full dated history, append-only, newest first.

---

## TL;DR

This repo hashes genomic sequences to compare people. There are **two unrelated efforts** living
in the same repo — don't mix them up:

1. **v1→v3 gene-level SHA256 pipeline** — the *original* effort (2025). Whole genes, SHA256,
   1000 Genomes NA12878 trio. Still runs, not being developed further.
2. **CDS-anchored sequence-hashing POC** — the *active* effort (2026–). Coding-sequence-only,
   MD5 + a GA4GH-standard digest, GIAB HG002/HG003/HG004 trio. Everything below is about this one.

Within effort #2, there have been **two pivots** in what the hashes are *for*:

> build reference hash catalog → **demonstrate inheritance** (done) → **pivot to ancestry** (active)

---

## Data sources — which one are we actually using, and why it matters

| Source | Used for | ID namespace |
|---|---|---|
| **GENCODE v46** (= **Ensembl 112** for human — confirmed from the GTF header, not assumed) | **The pipeline's actual source of truth** — GTF + transcript/protein FASTA, everything in the diagram below starts here | `ENSG`/`ENST`/`ENSP` |
| **Ensembl** (release 112, release-matched to GENCODE v46) | External validation only (2026-09-01) — cross-hashed all 1341 chr22 transcripts, exact match on protein *and* CDS layers | `ENSG`/`ENST`/`ENSP` — same as GENCODE, expected: GENCODE co-produces Ensembl's own human annotation, so this checks *pipeline correctness*, not independent *annotation content* |
| **NCBI RefSeq** | One worked-example accession only (`NP_000198.1`, notebook 01) — **never** a bulk data source here | `NM_`/`NP_`/`XM_`/`XP_` — **different namespace, not interchangeable** |
| **GIAB** (NIST) | Trio variant calls — HG002 (son) / HG003 (father) / HG004 (mother), the active effort's trio | Sample IDs, not sequence IDs |
| **1000 Genomes** | Impostor false-positive test (`NA19240`); also the *older*, unrelated v1→v3 pipeline's trio (`NA12878`) | Sample IDs, not sequence IDs |

**Three things that genuinely differ between GENCODE/Ensembl and NCBI RefSeq — don't assume any of
these are the same:**
1. **Accession IDs aren't interchangeable**, and RefSeq's own NM/NP aren't even paired by matching
   digits (`NM_000207` pairs with `NP_000198`, *not* `NP_000207` — see `HANDOFF.md`'s Known Gaps).
2. **Stop-codon inclusion differs by *file*, not by organization** — GENCODE's own GTF `CDS`
   feature excludes it, while GENCODE's `pc_transcripts.fa` header span, NCBI RefSeq CDS, *and*
   Ensembl's CDS sequence all include it. This pipeline's canonical `cds_seq` excludes it —
   mismatching this is the documented "#1 silent error" (full table in `HANDOFF.md`).
3. **Evidence/confidence tiers use different vocabularies**: GENCODE uses `level` 1/2/3 + TSL +
   tags (`MANE_Select`); NCBI RefSeq uses the `NM_` (curated) vs. `XM_` (Gnomon-predicted) prefix
   distinction. Different axes — don't conflate a GENCODE `level` with a RefSeq prefix.

**Release-pinning is the other trap**: GENCODE v46 = Ensembl 112 *specifically* — pulling an
Ensembl file from a different release would silently drift IDs/coordinates against the GENCODE
data already in this repo, even though both are nominally "Ensembl."

---

## Timeline

```
  2025-07-26
  │  v1 → v2 → v3 gene-level SHA256 pipeline (1000G NA12878 trio)
  │  chromosome-by-chromosome, then protein-coding-only filter (~65% fewer genes)
  │
  2026-07-02 – 07-03                                              ★ PIVOT #1 ★
  │  New, separate effort starts: CDS-anchored sequence-hashing POC
  │  New trio: GIAB HG002 (son) / HG003 (father) / HG004 (mother), chr22
  │  Track 1 (inheritance) built and proven on real data:
  │  431 confident parent-of-origin calls out of 1341 chr22 transcripts
  │
  2026-08-17 – 08-30
  │  Environment migration: Windows/WSL2 → native macOS (Mac mini + MacBook "Neo")
  │  Scattered handoff/session docs consolidated into HANDOFF.md + CHANGELOG.md
  │
  2026-08-29 – 08-30                                              ★ PIVOT #2 ★
  │  Primary goal flips: Track 2 (population/ancestry) over Track 1 (inheritance)
  │  Track 1 kept complete, as reference — not being extended further
  │
  2026-08-31
  │  Full repo cleanup (stale/duplicate docs retired); notebooks 01→04 rerun on the Mac mini —
  │  exact byte-for-byte reproduction of the original Windows/WSL2 run confirmed
  │
  2026-09-01
  │  Empirical false-positive test on Track 1 (confirms it does NOT establish paternity — see
  │  HANDOFF.md's Finding section); external validation against Ensembl (1341/1341 exact match,
  │  chr22, both protein and CDS layers) — the two open "Not yet done" validation TODOs, closed
  │
  2026-09-02  (today)
  ▼  Genome-wide scale measured for real: whole-genome reference catalog builds in 13s, but
     per-individual processing has a real bottleneck (~11.76s/individual on chr22 alone, a linear
     variant scan) — now being fixed and refactored for parallel AWS batch processing
```

---

## How the active pipeline fits together

```
   GENCODE v46 GTF + pc_transcripts.fa + pc_translations.fa   (data/reference/)
                              │
                              │  notebook 02 / scripts/gencode_cds_extract.py
                              │  splice CDS from exons, translate, validate:
                              │  translate(CDS) == protein, splice-length invariant
                              ▼
        Reference catalog: 1341/1398 chr22 transcripts validated
        3 sequence types per transcript — protein, whole-CDS, per-exon
                              │
                              │  notebook 01 (MD5 + ga4gh SQ digest functions)
                              │  notebook 03 (FASTA blob store + SQLite catalog)
                              ▼
      ┌────────────────────────────┐        ┌───────────────────────────┐
      │ FASTA blob store            │◄───────┤ SQLite hash_catalog.db     │
      │ (plain-text, pyfaidx)       │  fetch  │ hash_md5, hash_sq,         │
      │ chr22_{proteins,cds,exons}  │  seq    │ accession, gene_id, ...    │
      └────────────────────────────┘        └──────────────┬──────────────┘
                                                             │
                          ┌──────────────────────────────────┴──────────────────────────────────┐
                          │                                                                       │
                          ▼  Track 1 — COMPLETE, kept as reference                                ▼  Track 2 — ACTIVE, design only so far
           ┌───────────────────────────────┐                                       ┌───────────────────────────────────┐
           │ notebook 04: overlay GIAB      │                                       │ Not yet built:                      │
           │ HG002/3/4 chr22 VCFs onto the  │                                       │ Mash/sourmash MinHash distance vs.  │
           │ catalog via per-site allele-   │                                       │ a 1000G/HGDP chr22 panel;           │
           │ membership → 431 confident     │                                       │ coding-vs-genome-wide PCA demo      │
           │ parent-of-origin calls         │                                       │ (see HANDOFF.md Track 2 for detail) │
           └───────────────────────────────┘                                       └───────────────────────────────────┘
```

---

## Things that are easy to forget after a break

- **Exact-match hashing (MD5/SQ) cannot measure distance** — one base changed = a totally
  different hash (avalanche effect). That's *why* Track 2 needs a different tool family
  (MinHash/Mash, not the hashes already built for Track 1) — it's not a small addition, it's a
  different kind of hash entirely.
- **Ancestry signal is mostly non-coding.** Track 2 will eventually need whole-genome SNPs, not
  just the CDS-only catalog Track 1 built — coding-region-only ancestry signal exists but is
  shallow (continental resolution only, see `HANDOFF.md`).
- **`data/derived/` is gitignored and machine-local.** A fresh clone (or a clone that hasn't run
  the notebooks yet) has the raw reference/GIAB downloads but no hash catalog until notebooks
  02→04 are rerun. Don't assume it exists just because it's referenced in the docs.
- The selenocysteine bug (3 genes, not just the one originally noted) and the stop-codon
  in/exclusion convention are both easy to re-trip over — see `HANDOFF.md`'s Known Gaps before
  touching `scripts/gencode_cds_extract.py`.

## Resuming after a long break — read in this order

1. This file, for the shape of the project.
2. `HANDOFF.md`'s **Goal** and **Current state** sections, for what's true *right now*.
3. `HANDOFF.md`'s **Active TODO**, for what to actually do next.
4. `CHANGELOG.md`'s most recent entries, only if you need the *why* behind a recent decision.
