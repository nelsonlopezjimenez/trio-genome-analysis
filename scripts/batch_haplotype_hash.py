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

SALT HANDLING: no salt is hardcoded here, deliberately -- see HANDOFF.md's salt
evaluation section (2026-09-01/02) for why a salt committed to a public script is not
a secret at all. Pass one via --salt or the HASH_SALT environment variable; omitting
both computes unsalted hashes only.

Usage:
    python3 batch_haplotype_hash.py \\
        --chrom chr22 \\
        --vcf data/giab/HG002_chr22_phased.vcf.gz \\
        --sample-id HG002 \\
        --out /tmp/HG002_chr22_hashes.tsv.gz \\
        [--salt "..." | env HASH_SALT=...]
"""
import argparse
import bisect
import gzip
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gencode_cds_extract as cds

REF = os.path.join(REPO, "data/reference")

COMPLEMENT = str.maketrans("ACGT", "TGCA")


def revcomp(s):
    return s.translate(COMPLEMENT)[::-1]


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


def process_individual(chrom, vcf_path, sample_id, salt, out_path):
    t0 = time.perf_counter()
    chrom_transcripts = cds.parse_gtf_chrom(os.path.join(REF, "gencode.v46.basic.annotation.gtf.gz"), chrom)
    tx_seqs, tx_meta = cds.load_transcripts_fasta(os.path.join(REF, "gencode.v46.pc_transcripts.fa.gz"))
    prot_seqs, protein_ids = cds.load_translations_fasta(os.path.join(REF, "gencode.v46.pc_translations.fa.gz"))
    catalog, flagged = cds.build_catalog(chrom_transcripts, tx_seqs, tx_meta, prot_seqs, protein_ids)
    t1 = time.perf_counter()

    raw_vcf = load_vcf(vcf_path)
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
        hap0, hap1, status = build_haplotypes(cds_seq, offsets)
        if status != "ok":
            categories[status] = categories.get(status, 0) + 1
            continue
        for hap_name, hap_seq in (("hap0", hap0), ("hap1", hap1)):
            md5 = cds.md5_digest(hap_seq)
            sq = cds.ga4gh_sq_digest(hap_seq)
            salted_md5 = cds.md5_digest(salt + hap_seq) if salt else ""
            rows.append((entry["transcript_id"], entry["gene_id"], sample_id, hap_name,
                         md5, sq, salted_md5, len(hap_seq)))
    t3 = time.perf_counter()

    with gzip.open(out_path, "wt") as fh:
        fh.write("transcript_id\tgene_id\tsample_id\thaplotype\thash_md5\thash_sq\tsalted_hash_md5\tlength\n")
        for row in rows:
            fh.write("\t".join(str(x) for x in row) + "\n")
    t4 = time.perf_counter()

    print(f"catalog build: {t1-t0:.2f}s | vcf load+index: {t2-t1:.2f}s | "
          f"haplotype extraction+hashing: {t3-t2:.2f}s | write: {t4-t3:.2f}s | total: {t4-t0:.2f}s")
    print(f"{len(rows)} haplotype hashes written to {out_path}")
    print(f"categories skipped: {categories}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chrom", required=True, help="e.g. chr22")
    ap.add_argument("--vcf", required=True, help="path to the individual's chromosome VCF (bgzipped)")
    ap.add_argument("--sample-id", required=True, help="e.g. HG002, NA19240")
    ap.add_argument("--out", required=True, help="output path, .tsv.gz")
    ap.add_argument("--salt", default=os.environ.get("HASH_SALT", ""),
                     help="salt for salted_hash_md5 column; also read from HASH_SALT env var; "
                          "omit both for unsalted-only output (salted_hash_md5 left empty)")
    args = ap.parse_args()
    process_individual(args.chrom, args.vcf, args.sample_id, args.salt, args.out)


if __name__ == "__main__":
    main()
