# scripts/

- **`trio_genome_script.sh`** — v1→v3 gene-level SHA256 pipeline (1000 Genomes NA12878 trio).
  Usage, configuration, and output layout: see the root
  [`README.md`](../README.md#v1v3-gene-level-pipeline-earlier-effort-not-actively-developed).
  Data download/validation commands: [`docs/data_sources.md`](../docs/data_sources.md).
- **`gencode_cds_extract.py`** — CDS-anchored extraction + MD5/ga4gh-SQ hashing for the
  sequence-hashing POC, promoted from `notebooks/02_cds_extraction.ipynb` once validated.
  Design decisions and current status: see [`HANDOFF.md`](../HANDOFF.md).
- **`setup_macos.sh`** — idempotent Homebrew-based environment setup for this project on macOS.
  Usage: see [`HANDOFF.md`](../HANDOFF.md#setting-up-a-new-machine).

This file used to hold one-time v3.0 release/download/validation instructions; those were
folded into the root README and `docs/data_sources.md` on 2026-08-31 (see `CHANGELOG.md`) to
keep a single source of truth instead of duplicated copies drifting apart.
