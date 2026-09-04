"""Optimized, CLI-invocable per-individual haplotype extraction + hashing.

Refactor of the logic duplicated across notebooks/04_trio_inheritance.ipynb and
scripts/impostor_test.py, with the diagnosed bottleneck fixed: the original
`variants_in_range()` linearly scanned every variant in the chromosome for every exon
of every transcript (~670 million comparisons for one individual on chr22 alone,
measured 2026-09-02). This version sorts each individual's variant positions ONCE per
chromosome and binary-searches into that sorted list per exon block instead --
O(log n + k) per lookup instead of O(n), where k is the (typically tiny) number of
variants actually in that exon. See HANDOFF.md's "Scaling to genome-wide and
population scale" section for the diagnosis and the timing this fixes.

Designed for parallel batch use (one process per individual, e.g. via GNU parallel or
a job array on a multi-core/multi-instance AWS run): each invocation processes ONE
individual's VCF against the reference catalog for ONE chromosome and writes a
self-contained TSV.gz of results -- safe to run many of these concurrently without any
shared-database write contention. Merge the outputs afterward.

TWO MODES:
  --mode iupac (default): one phase-free hash per person per CDS. Heterozygous
    biallelic SNV positions collapse to the IUPAC ambiguity code (R/Y/S/W/K/M);
    homozygous positions keep the actual base. DECIDED 2026-09-02 as the right
    representation for Track 2 (ancestry) -- see HANDOFF.md's IUPAC-collapse decision
    for the full reasoning (short version: ancestry doesn't use phase at all, most
    population panels have no parent samples to derive paternal/maternal from in the
    first place, and this needs no phase resolution -- unlike --mode haplotypes,
    nothing here is ever excluded as phase_incomplete).
  --mode haplotypes: the original Track 1 behavior (two separately-phased hap0/hap1
    hashes per CDS, requires a phased VCF and excludes phase-incomplete sites). Kept
    for Track 1 compatibility and for the correctness verification this script's
    optimization was checked against -- not the recommended mode for new work.

SALT HANDLING: no salt is hardcoded here, deliberately -- see HANDOFF.md's salt
evaluation section (2026-09-01/02) for why a salt committed to a public script is not
a secret at all. Pass one via --salt/--salt-file or the HASH_SALT environment variable;
omitting all three computes unsalted hashes only.

TWO-STAGE BULK-FETCH ARCHITECTURE (--bulk-vcf, added 2026-09-03): tested and measured
~44x faster per individual than a fresh remote fetch per person (see HANDOFF.md's
"bulk-fetch architecture" section) -- fetch each chromosome's CDS-restricted region
ONCE for all samples (`bcftools view -R <bed> <S3 URL>`, not done by this script), then
pass that one local file via --bulk-vcf instead of --vcf. This script slices the named
--sample-id out of it locally (measured ~10.7s, vs. ~8 min for a fresh remote
single-sample fetch of the same regions) before running the existing pipeline
unchanged. --vcf (an already single-sample VCF) still works as before, for local
testing or GIAB trio data that was never multi-sample to begin with.

Usage:
    # Original: single-sample VCF already on disk
    python3 batch_haplotype_hash.py \\
        --chrom chr22 \\
        --vcf data/giab/HG002_chr22_phased.vcf.gz \\
        --sample-id HG002 \\
        --out /tmp/HG002_chr22_hashes.tsv.gz \\
        [--mode iupac|haplotypes] \\
        [--salt "..." | --salt-file PATH | env HASH_SALT=...]

    # Two-stage: slice one sample locally out of a bulk multi-sample VCF
    python3 batch_haplotype_hash.py \\
        --chrom chr22 \\
        --bulk-vcf /tmp/chr22_cds_ALL_SAMPLES.vcf.gz \\
        --sample-id NA19240 \\
        --out /tmp/NA19240_chr22_hashes.tsv.gz
"""
import argparse
import bisect
import gzip
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gencode_cds_extract as cds

REF = os.path.join(REPO, "data/reference")

COMPLEMENT = str.maketrans("ACGT", "TGCA")


def revcomp(s):
    return s.translate(COMPLEMENT)[::-1]


def slice_individual_vcf(bulk_vcf_path, sample_id, bcftools_cmd):
    """The local half of the tested two-stage bulk-fetch pattern: extract one sample
    from an already-local, region-restricted, multi-sample VCF via bcftools -- measured
    ~10.7s (2026-09-03, three real samples), vs. ~8 min for a fresh remote per-individual
    fetch of the same regions. See HANDOFF.md's "bulk-fetch architecture" section.
    Returns a path to a temporary single-sample VCF.gz; caller is responsible for
    deleting it once load_vcf() has consumed it."""
    fd, tmp_path = tempfile.mkstemp(suffix=f".{sample_id}.vcf.gz")
    os.close(fd)
    subprocess.run(
        [*bcftools_cmd.split(), "view", "-s", sample_id, bulk_vcf_path, "-Oz", "-o", tmp_path],
        check=True,
    )
    return tmp_path


def load_vcf(path):
    """Same parsing as notebook 04 / impostor_test.py -- unchanged, not the bottleneck."""
    variants = {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            chrom, pos, _id, ref, alt, qual, flt, info, fmt, sample = f[:10]
            if flt not in ("PASS", "."):
                continue
            fmt_fields = fmt.split(":")
            sample_fields = sample.split(":")
            gt_raw = sample_fields[fmt_fields.index("GT")]
            ps = sample_fields[fmt_fields.index("PS")] if "PS" in fmt_fields else None
            phased = "|" in gt_raw
            sep = "|" if phased else "/"
            try:
                a, b = gt_raw.split(sep)
                gt = (int(a), int(b))
            except ValueError:
                continue
            difficultregion = None
            for kv in info.split(";"):
                if kv.startswith("difficultregion="):
                    difficultregion = kv[len("difficultregion="):]
            variants[int(pos)] = {
                "ref": ref, "alt": alt.split(","), "gt": gt, "phased": phased,
                "ps": ps if ps not in (None, ".") else None,
                "difficultregion": difficultregion,
            }
    return variants


class IndexedVCF:
    """The actual fix: sort variant positions once per individual, then binary-search into
    that sorted list per exon range instead of scanning every variant every time."""

    def __init__(self, variants):
        self.variants = variants
        self.sorted_positions = sorted(variants.keys())

    def in_range(self, start, end):
        lo = bisect.bisect_left(self.sorted_positions, start)
        hi = bisect.bisect_right(self.sorted_positions, end)
        return [(p, self.variants[p]) for p in self.sorted_positions[lo:hi]]


def build_transcript_variant_map_indexed(entry, chrom_transcripts, indexed_vcf):
    t = chrom_transcripts[entry["transcript_id"]]
    strand, blocks = t["strand"], t["cds"]
    block_offsets, running = [], 0
    for s, e in blocks:
        block_offsets.append(running)
        running += e - s + 1

    offsets = {}
    has_indel = False
    for (s, e), block_offset in zip(blocks, block_offsets):
        for pos, v in indexed_vcf.in_range(s, e):
            ref, alts = v["ref"], v["alt"]
            if len(alts) != 1 or len(ref) != 1 or len(alts[0]) != 1:
                has_indel = True
                continue
            alt = alts[0]
            if strand == "+":
                coding_pos, ref_c, alt_c = block_offset + (pos - s), ref, alt
            else:
                coding_pos = block_offset + (e - pos)
                ref_c, alt_c = revcomp(ref), revcomp(alt)
            offsets[coding_pos] = {"ref": ref_c, "alt": alt_c, "gt": v["gt"],
                                    "phased": v["phased"], "ps": v["ps"],
                                    "difficultregion": v["difficultregion"]}
    return offsets, has_indel


def build_haplotypes(cds_seq, offsets):
    het_sites = {p: v for p, v in offsets.items() if v["gt"][0] != v["gt"][1]}
    if len(het_sites) >= 2:
        ps_values = {v["ps"] for v in het_sites.values()}
        all_phased = all(v["phased"] for v in het_sites.values())
        if not all_phased or len(ps_values) != 1 or None in ps_values:
            return None, None, "phase_incomplete"
    hap0, hap1 = list(cds_seq), list(cds_seq)
    for p, v in offsets.items():
        alleles = (v["ref"], v["alt"])
        hap0[p] = alleles[v["gt"][0]]
        hap1[p] = alleles[v["gt"][1]]
    return "".join(hap0), "".join(hap1), "ok"


# Standard IUPAC ambiguity codes for biallelic heterozygous nucleotide pairs. Only the
# 2-base codes are needed -- build_transcript_variant_map_indexed already guarantees
# every offset here is a biallelic single-nucleotide substitution (multiallelic sites
# and indels are filtered upstream, flagged has_indel).
IUPAC_HET = {
    frozenset("AG"): "R", frozenset("CT"): "Y", frozenset("GC"): "S",
    frozenset("AT"): "W", frozenset("GT"): "K", frozenset("AC"): "M",
}


def iupac_code(base0, base1):
    if base0 == base1:
        return base0
    code = IUPAC_HET.get(frozenset((base0, base1)))
    if code is None:
        raise ValueError(f"Unexpected base pair for IUPAC collapse: {base0!r}, {base1!r}")
    return code


def build_iupac_collapsed(cds_seq, offsets):
    """One phase-free sequence per person per CDS -- see HANDOFF.md's 2026-09-02 IUPAC-collapse
    decision. No phasing needed at all: unlike build_haplotypes, there is no phase_incomplete
    exclusion here, since a heterozygous site's IUPAC code is well-defined regardless of which
    physical chromosome copy each allele sits on. Returns (sequence, het_count)."""
    seq = list(cds_seq)
    het_count = 0
    for p, v in offsets.items():
        alleles = (v["ref"], v["alt"])
        b0, b1 = alleles[v["gt"][0]], alleles[v["gt"][1]]
        if b0 != b1:
            het_count += 1
        seq[p] = iupac_code(b0, b1)
    return "".join(seq), het_count


def process_individual(chrom, vcf_path, sample_id, salt, out_path, mode="iupac",
                        bulk_vcf=None, bcftools_cmd="bcftools"):
    t0 = time.perf_counter()
    chrom_transcripts = cds.parse_gtf_chrom(os.path.join(REF, "gencode.v46.basic.annotation.gtf.gz"), chrom)
    tx_seqs, tx_meta = cds.load_transcripts_fasta(os.path.join(REF, "gencode.v46.pc_transcripts.fa.gz"))
    prot_seqs, protein_ids = cds.load_translations_fasta(os.path.join(REF, "gencode.v46.pc_translations.fa.gz"))
    catalog, flagged = cds.build_catalog(chrom_transcripts, tx_seqs, tx_meta, prot_seqs, protein_ids)
    t1 = time.perf_counter()

    sliced_tmp_path = None
    if bulk_vcf:
        sliced_tmp_path = slice_individual_vcf(bulk_vcf, sample_id, bcftools_cmd)
        vcf_path = sliced_tmp_path
    t1b = time.perf_counter()

    try:
        raw_vcf = load_vcf(vcf_path)
    finally:
        if sliced_tmp_path:
            os.remove(sliced_tmp_path)
    indexed_vcf = IndexedVCF(raw_vcf)  # sort ONCE, not per transcript -- the actual fix
    t2 = time.perf_counter()

    rows = []
    categories = {}
    for entry in catalog:
        offsets, has_indel = build_transcript_variant_map_indexed(entry, chrom_transcripts, indexed_vcf)
        if has_indel:
            categories["has_indel"] = categories.get("has_indel", 0) + 1
            continue
        if not offsets:
            categories["no_variants"] = categories.get("no_variants", 0) + 1
            continue
        cds_seq = entry["cds_seq"]

        if mode == "iupac":
            seq, het_count = build_iupac_collapsed(cds_seq, offsets)
            md5 = cds.md5_digest(seq)
            sq = cds.ga4gh_sq_digest(seq)
            salted_md5 = cds.md5_digest(salt + seq) if salt else ""
            salted_sq = cds.ga4gh_sq_digest(salt + seq) if salt else ""
            rows.append((entry["transcript_id"], entry["gene_id"], sample_id, "iupac",
                         md5, sq, salted_md5, salted_sq, len(seq), het_count))
        else:  # mode == "haplotypes"
            hap0, hap1, status = build_haplotypes(cds_seq, offsets)
            if status != "ok":
                categories[status] = categories.get(status, 0) + 1
                continue
            for hap_name, hap_seq in (("hap0", hap0), ("hap1", hap1)):
                md5 = cds.md5_digest(hap_seq)
                sq = cds.ga4gh_sq_digest(hap_seq)
                salted_md5 = cds.md5_digest(salt + hap_seq) if salt else ""
                salted_sq = cds.ga4gh_sq_digest(salt + hap_seq) if salt else ""
                rows.append((entry["transcript_id"], entry["gene_id"], sample_id, hap_name,
                             md5, sq, salted_md5, salted_sq, len(hap_seq), ""))
    t3 = time.perf_counter()

    with gzip.open(out_path, "wt") as fh:
        fh.write("transcript_id\tgene_id\tsample_id\trepresentation\thash_md5\thash_sq\t"
                  "salted_hash_md5\tsalted_hash_sq\tlength\thet_count\n")
        for row in rows:
            fh.write("\t".join(str(x) for x in row) + "\n")
    t4 = time.perf_counter()

    slice_str = f"local slice: {t1b-t1:.2f}s | " if bulk_vcf else ""
    print(f"mode: {mode} | catalog build: {t1-t0:.2f}s | {slice_str}"
          f"vcf load+index: {t2-t1b:.2f}s | "
          f"extraction+hashing: {t3-t2:.2f}s | write: {t4-t3:.2f}s | total: {t4-t0:.2f}s")
    print(f"{len(rows)} hashes written to {out_path}")
    print(f"categories skipped: {categories}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chrom", required=True, help="e.g. chr22")
    ap.add_argument("--vcf", default=None,
                     help="path to the individual's already-single-sample chromosome VCF "
                          "(bgzipped). Mutually exclusive with --bulk-vcf.")
    ap.add_argument("--bulk-vcf", default=None,
                     help="path to a LOCAL, region-restricted, multi-sample VCF (e.g. one "
                          "produced by a one-time bulk `bcftools view -R <bed> <S3 URL>` fetch "
                          "covering all individuals) -- --sample-id is sliced out of it locally "
                          "via bcftools, measured ~44x faster per individual than a fresh remote "
                          "fetch (see HANDOFF.md's 2026-09-03 'bulk-fetch architecture' section). "
                          "Mutually exclusive with --vcf.")
    ap.add_argument("--bcftools", default="bcftools",
                     help="command to invoke bcftools for --bulk-vcf slicing, e.g. a micromamba-"
                          "wrapped invocation on AWS ('~/bin/micromamba run -n bcf bcftools'). "
                          "Defaults to 'bcftools' on PATH. Ignored without --bulk-vcf.")
    ap.add_argument("--sample-id", required=True, help="e.g. HG002, NA19240")
    ap.add_argument("--out", required=True, help="output path, .tsv.gz")
    ap.add_argument("--mode", choices=("iupac", "haplotypes"), default="iupac",
                     help="iupac (default, recommended for Track 2/ancestry, see HANDOFF.md) "
                          "or haplotypes (Track 1-style phased hap0/hap1, requires a phased VCF)")
    ap.add_argument("--salt", default=os.environ.get("HASH_SALT", ""),
                     help="salt for salted_hash_md5/salted_hash_sq columns; also read from "
                          "HASH_SALT env var. Avoid this flag for a real salt -- it's visible to "
                          "other users on the same machine via `ps aux`. Prefer --salt-file.")
    ap.add_argument("--salt-file", default=None,
                     help="path to a file containing only the salt (first line, trailing "
                          "newline stripped). Safer than --salt: only the path appears in "
                          "`ps aux`, never the value. Takes precedence over --salt/HASH_SALT.")
    args = ap.parse_args()
    if bool(args.vcf) == bool(args.bulk_vcf):
        ap.error("exactly one of --vcf or --bulk-vcf is required")
    salt = args.salt
    if args.salt_file:
        with open(args.salt_file) as fh:
            salt = fh.readline().rstrip("\n")
    process_individual(args.chrom, args.vcf, args.sample_id, salt, args.out, args.mode,
                        bulk_vcf=args.bulk_vcf, bcftools_cmd=args.bcftools)


if __name__ == "__main__":
    main()
