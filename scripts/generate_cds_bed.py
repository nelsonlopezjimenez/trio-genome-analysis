"""Generate merged, sorted CDS-region BED files for all chromosomes, extending the
one-off chr22 BED file used in the impostor test (data/giab/impostor_test/
chr22_cds_regions.bed, 4,186 regions) to the rest of the genome for Phase 2.

Restricted to VALIDATED transcripts only -- i.e. exactly the set gencode_cds_extract.py's
build_catalog() keeps, not every CDS-bearing transcript in the raw GTF. A transcript
only counts as validated if it passes all five checks build_catalog() applies, in order:
  1. Present in BOTH reference FASTAs (pc_transcripts.fa AND pc_translations.fa) --
     drops anything not fully represented across GENCODE's own files.
  2. Has a parseable `CDS:start-end` span in the FASTA header (else "no_cds_span").
  3. GTF CDS-exon-block lengths sum to (FASTA CDS span length - 3) -- reconciles the
     documented "#1 silent error": GTF's CDS features exclude the stop codon, the
     FASTA's CDS: span includes it (else "length_mismatch").
  4. Extracted nucleotide length is exactly 3*(protein_length+1) with stop, or
     3*protein_length without (else "unexpected_length_ratio").
  5. Literal codon-table translation matches the annotated protein exactly, with one
     narrow exception: non_ATG_start-tagged transcripts where only residue 0 differs
     (else "translate_mismatch").
Using the same validated set this pipeline already hashes keeps the BED file's scope
consistent with what batch_haplotype_hash.py actually processes -- pulling a region for
a transcript that would just get excluded downstream anyway wastes bandwidth, not just
a correctness risk.

**Mistake made and caught while building this** (2026-09-03): the first version parsed
CDS blocks straight from the raw GTF (gencode_cds_extract.parse_gtf_chrom) without
applying the five checks above -- for chr22 that gives 1,404 transcripts / 4,300 merged
regions. That's *more* than the existing, already-used chr22 BED file (4,186 regions),
which was the tell that something was wrong -- a superset should never have fewer
regions than the file it's supposed to reproduce. Caught by regenerating chr22 with the
draft logic and diffing byte-for-byte against data/giab/impostor_test/
chr22_cds_regions.bed before trusting it for any other chromosome: the diff showed 114
extra regions matching exactly the transcripts build_catalog() flags and excludes (57
chr22 transcripts, some contributing 2+ CDS blocks each). Fixed by calling
extract_chrom() to get the actual validated transcript_id set and filtering
chrom_transcripts down to it *before* merging -- re-verified afterward with the same
byte-for-byte diff, this time exact.

Usage: python3 scripts/generate_cds_bed.py [--out-dir DIR]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gencode_cds_extract import extract_chrom, parse_gtf_chrom

GTF_PATH = "data/reference/gencode.v46.basic.annotation.gtf.gz"
TRANSCRIPTS_FA_PATH = "data/reference/gencode.v46.pc_transcripts.fa.gz"
TRANSLATIONS_FA_PATH = "data/reference/gencode.v46.pc_translations.fa.gz"

# chrM excluded: 1000 Genomes' per-chromosome joint-VCF releases (the source Phase 2
# reads from) don't include a chrM file in the same format -- mitochondrial variant
# calling uses a separate pipeline. Included in the GTF, but not relevant here.
CHROMS = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]


def merge_regions(regions):
    """regions: list of (start, end), BED-style 0-based half-open. Sorted + merged."""
    regions = sorted(regions)
    merged = []
    for start, end in regions:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="data/reference/cds_regions")
    ap.add_argument("--gtf", default=GTF_PATH)
    ap.add_argument("--transcripts-fa", default=TRANSCRIPTS_FA_PATH)
    ap.add_argument("--translations-fa", default=TRANSLATIONS_FA_PATH)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    total_regions = 0

    for chrom in CHROMS:
        chrom_transcripts = parse_gtf_chrom(args.gtf, chrom)
        catalog, flagged = extract_chrom(args.gtf, args.transcripts_fa, args.translations_fa, chrom)
        validated_ids = {entry["transcript_id"] for entry in catalog}
        raw = [(s - 1, e) for tid, t in chrom_transcripts.items() if tid in validated_ids
               for s, e in t["cds"]]  # GTF 1-based -> BED 0-based
        merged = merge_regions(raw)
        out_path = os.path.join(args.out_dir, f"{chrom}_cds_regions.bed")
        with open(out_path, "w", newline="") as fh:
            for start, end in merged:
                fh.write(f"{chrom}\t{start}\t{end}\n")
        total_regions += len(merged)
        print(f"{chrom}: {len(validated_ids)}/{len(chrom_transcripts)} validated transcripts "
              f"({len(flagged)} flagged), {len(raw)} raw CDS blocks -> "
              f"{len(merged)} merged regions -> {out_path}")

    print(f"\nTotal merged regions across {len(CHROMS)} chromosomes: {total_regions}")


if __name__ == "__main__":
    main()
