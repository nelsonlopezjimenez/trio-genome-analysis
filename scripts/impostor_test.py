"""Empirical false-positive test for Track 1 parent-of-origin classification.

Question: if you swap the real father (HG003) for a random UNRELATED person, how many
of the haplotypes confidently called `paternal_origin` against the real father would
*also* look consistent with the random impostor, purely by population allele-sharing?
See HANDOFF.md's "Finding: Track 1's classification does NOT confirm paternity" section.

Reuses the classification logic from notebooks/04_trio_inheritance.ipynb verbatim
(load_vcf, build_transcript_variant_map, build_child_haplotypes, parent_allele_set,
explainable_by) so the comparison is apples-to-apples -- not a reimplementation.

Requires an impostor VCF at data/giab/impostor_test/<SAMPLE>_chr22_cds.vcf.gz, fetched
via a CDS-region BED file (see the region-fetch note in HANDOFF.md's download-strategy
TODO item -- a whole-chromosome fetch from a large multi-sample panel is impractically
slow; restrict to just the needed regions first). Example fetch, given
data/giab/impostor_test/chr22_cds_regions.bed already built from the reference catalog:

    bcftools view -R chr22_cds_regions.bed -s <SAMPLE> \\
        "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz" \\
        -Oz -o <SAMPLE>_chr22_cds.vcf.gz
"""
import gzip
import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gencode_cds_extract as cds

REF = os.path.join(REPO, "data/reference")
GIAB = os.path.join(REPO, "data/giab")
CHROM = "chr22"

COMPLEMENT = str.maketrans("ACGT", "TGCA")
def revcomp(s):
    return s.translate(COMPLEMENT)[::-1]


def load_vcf(path):
    """Verbatim from notebook 04 (minus the difficultregion field, not needed here)."""
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
            variants[int(pos)] = {
                "ref": ref, "alt": alt.split(","), "gt": gt, "phased": phased,
                "ps": ps if ps not in (None, ".") else None,
            }
    return variants


def variants_in_range(sample_vcf, start, end):
    return [(pos, v) for pos, v in sample_vcf.items() if start <= pos <= end]


def build_transcript_variant_map(entry, chrom_transcripts, vcf_dict):
    t = chrom_transcripts[entry["transcript_id"]]
    strand, blocks = t["strand"], t["cds"]
    block_offsets, running = [], 0
    for s, e in blocks:
        block_offsets.append(running)
        running += e - s + 1
    has_indel = False
    per_sample_offsets = {name: {} for name in vcf_dict}
    for (s, e), block_offset in zip(blocks, block_offsets):
        for sample_name, sample_vcf in vcf_dict.items():
            for pos, v in variants_in_range(sample_vcf, s, e):
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
                per_sample_offsets[sample_name][coding_pos] = {
                    "ref": ref_c, "alt": alt_c, "gt": v["gt"], "phased": v["phased"], "ps": v["ps"],
                }
    return per_sample_offsets, has_indel


def build_child_haplotypes(cds_seq, child_offsets):
    het_sites = {p: v for p, v in child_offsets.items() if v["gt"][0] != v["gt"][1]}
    if len(het_sites) >= 2:
        ps_values = {v["ps"] for v in het_sites.values()}
        all_phased = all(v["phased"] for v in het_sites.values())
        if not all_phased or len(ps_values) != 1 or None in ps_values:
            return None, None, "phase_incomplete"
    hap0, hap1 = list(cds_seq), list(cds_seq)
    for p, v in child_offsets.items():
        alleles = (v["ref"], v["alt"])
        hap0[p] = alleles[v["gt"][0]]
        hap1[p] = alleles[v["gt"][1]]
    return "".join(hap0), "".join(hap1), "ok"


def parent_allele_set(parent_offsets, pos, ref_base):
    if pos not in parent_offsets:
        return {ref_base}
    v = parent_offsets[pos]
    alleles = (v["ref"], v["alt"])
    return {alleles[v["gt"][0]], alleles[v["gt"][1]]}


def explainable_by(parent_offsets, hap_seq, cds_seq, variant_positions):
    return all(hap_seq[p] in parent_allele_set(parent_offsets, p, cds_seq[p]) for p in variant_positions)


def run(impostor_sample, impostor_vcf_path):
    print(f"Loading trio + impostor ({impostor_sample}) VCFs...")
    real_vcf = {
        "HG002": load_vcf(os.path.join(GIAB, "HG002_chr22_phased.vcf.gz")),
        "HG003": load_vcf(os.path.join(GIAB, "HG003_chr22.vcf.gz")),
        "HG004": load_vcf(os.path.join(GIAB, "HG004_chr22.vcf.gz")),
    }
    impostor_vcf = load_vcf(impostor_vcf_path)
    for name, v in {**real_vcf, "IMPOSTOR": impostor_vcf}.items():
        print(f"  {name}: {len(v)} PASS variants")

    print("\nRebuilding validated reference catalog (chr22)...")
    chrom_transcripts = cds.parse_gtf_chrom(os.path.join(REF, "gencode.v46.basic.annotation.gtf.gz"), CHROM)
    tx_seqs, tx_meta = cds.load_transcripts_fasta(os.path.join(REF, "gencode.v46.pc_transcripts.fa.gz"))
    prot_seqs, protein_ids = cds.load_translations_fasta(os.path.join(REF, "gencode.v46.pc_translations.fa.gz"))
    catalog, flagged = cds.build_catalog(chrom_transcripts, tx_seqs, tx_meta, prot_seqs, protein_ids)
    print(f"  validated reference transcripts: {len(catalog)}")

    # IMPORTANT: has_indel scoping uses ONLY the real trio (HG002/3/4), matching notebook 04
    # exactly. The impostor's own indels are checked separately, after, so they can't skew
    # which transcripts count toward the baseline.
    print("\nClassifying with the REAL trio (baseline -- should match documented 431/675/etc.)...")
    counts = defaultdict(int)
    paternal_calls = []
    for entry in catalog:
        per_sample, has_indel = build_transcript_variant_map(entry, chrom_transcripts, real_vcf)
        if has_indel:
            continue
        cds_seq = entry["cds_seq"]
        hap0, hap1, status = build_child_haplotypes(cds_seq, per_sample["HG002"])
        if status != "ok" or not per_sample["HG002"]:
            continue
        positions = sorted(set(per_sample["HG002"]) | set(per_sample["HG003"]) | set(per_sample["HG004"]))
        for hap_name, hap_seq in [("hap0", hap0), ("hap1", hap1)]:
            by_father = explainable_by(per_sample["HG003"], hap_seq, cds_seq, positions)
            by_mother = explainable_by(per_sample["HG004"], hap_seq, cds_seq, positions)
            if by_father and not by_mother:
                cat = "paternal_origin"
            elif by_mother and not by_father:
                cat = "maternal_origin"
            elif by_father and by_mother:
                cat = "uninformative_shared"
            else:
                cat = "no_parental_match"
            counts[cat] += 1
            if cat == "paternal_origin":
                paternal_calls.append((entry["transcript_id"], entry["gene_id"], hap_name, hap_seq, cds_seq, positions))

    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {cat}")

    print(f"\nSubstituting {impostor_sample} for HG003 -- testing the {len(paternal_calls)} real paternal_origin haplotypes...")
    matches, genes_tested, genes_matched = 0, set(), set()
    for tid, gid, hap_name, hap_seq, cds_seq, positions in paternal_calls:
        genes_tested.add(gid)
        impostor_offsets, _ = build_transcript_variant_map(
            {"transcript_id": tid}, chrom_transcripts, {"IMPOSTOR": impostor_vcf}
        )
        if explainable_by(impostor_offsets["IMPOSTOR"], hap_seq, cds_seq, positions):
            matches += 1
            genes_matched.add(gid)

    n = len(paternal_calls)
    rate = matches / n if n else 0
    print(f"\n=== RESULT ===")
    print(f"{matches}/{n} ({rate:.1%}) also explainable by {impostor_sample} -- single-locus false-match.")
    print(f"{n - matches}/{n} ({1 - rate:.1%}) correctly exclude the impostor.")
    print(f"Spans {len(genes_tested)} distinct genes -- the effective (LD-corrected) sample size,")
    print(f"not {n}. If independent, joint miss probability ~ {rate:.3f}^{len(genes_tested)}.")


if __name__ == "__main__":
    SAMPLE = "NA19240"
    VCF = os.path.join(GIAB, "impostor_test", f"{SAMPLE}_chr22_cds.vcf.gz")
    run(SAMPLE, VCF)
