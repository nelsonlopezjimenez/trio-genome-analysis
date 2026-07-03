"""CDS-anchored extraction, splice/translation validation, and MD5+SQ hashing for a
single chromosome of a GENCODE release. Promoted from notebooks/02_cds_extraction.ipynb
once the extraction logic was validated (1341/1398 chr22 transcripts, 0 unexplained
exclusions -- see that notebook for the derivation and worked example).

Anchors on CDS, not gene genomic span, per seq-hashing-project-handoff.md.
"""

import base64
import gzip
import hashlib
import re
from collections import defaultdict

CODON_TABLE = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L', 'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
    'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M', 'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
    'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S', 'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T', 'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*', 'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K', 'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W', 'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R', 'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}

_ATTR_RE = re.compile(r'(\w+) "([^"]*)"')


def translate(nt: str) -> str:
    codons = (nt[i:i + 3] for i in range(0, len(nt) - len(nt) % 3, 3))
    return "".join(CODON_TABLE.get(c, "X") for c in codons)


def md5_digest(seq: str) -> str:
    return hashlib.md5(seq.encode("ascii")).hexdigest()


def ga4gh_sq_digest(seq: str) -> str:
    digest = hashlib.sha512(seq.encode("ascii")).digest()[:24]
    return "SQ." + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def parse_gtf_chrom(gtf_path: str, chrom: str) -> dict:
    """Parse transcript + CDS features for one chromosome. CDS blocks are ordered into
    transcript (5'->3') order using strand, matching pc_transcripts.fa's mRNA-sense sequence."""
    transcripts = defaultdict(lambda: {"strand": None, "cds": [], "gene_id": None, "tags": set(), "level": None})
    with gzip.open(gtf_path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if f[0] != chrom or f[2] not in ("CDS", "transcript"):
                continue
            attrs = dict(_ATTR_RE.findall(f[8]))
            tid = attrs["transcript_id"]
            t = transcripts[tid]
            t["strand"] = f[6]
            t["gene_id"] = attrs["gene_id"]
            if f[2] == "CDS":
                t["cds"].append((int(f[3]), int(f[4])))
            else:
                t["level"] = attrs.get("level")
                t["tags"] = set(v for k, v in _ATTR_RE.findall(f[8]) if k == "tag")
    for t in transcripts.values():
        t["cds"].sort(key=lambda se: se[0], reverse=(t["strand"] == "-"))
    return {tid: t for tid, t in transcripts.items() if t["cds"]}


def load_transcripts_fasta(path: str):
    """pc_transcripts.fa: header field 0 = ENST id; header carries CDS:start-end (1-based)."""
    seqs, meta = {}, {}
    tid, chunks = None, []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if tid is not None:
                    seqs[tid] = "".join(chunks)
                fields = line[1:].split("|")
                tid = fields[0]
                meta[tid] = fields
                chunks = []
            else:
                chunks.append(line)
        if tid is not None:
            seqs[tid] = "".join(chunks)
    return seqs, meta


def load_translations_fasta(path: str):
    """pc_translations.fa: header field 0 = ENSP (protein) id, field 1 = ENST id."""
    seqs, protein_ids = {}, {}
    tid, pid, chunks = None, None, []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if tid is not None:
                    seqs[tid] = "".join(chunks)
                fields = line[1:].split("|")
                pid, tid = fields[0], fields[1]
                protein_ids[tid] = pid
                chunks = []
            else:
                chunks.append(line)
        if tid is not None:
            seqs[tid] = "".join(chunks)
    return seqs, protein_ids


def _extract_cds_span(fields):
    for f in fields:
        if f.startswith("CDS:"):
            s, e = f[4:].split("-")
            return int(s), int(e)
    return None


def build_catalog(chrom_transcripts: dict, tx_seqs: dict, tx_meta: dict, prot_seqs: dict, protein_ids: dict):
    """Returns (catalog, flagged). catalog entries hold validated protein/CDS/per-exon
    sequences + MD5/SQ hashes. flagged entries are (transcript_id, reason) exclusions --
    kept as metadata, not discarded, per the handoff's "treat as QC flag" rule.

    Two things are accepted as expected categories, not bugs:
    - the off-by-3 between GTF CDS spans (stop excluded) and pc_transcripts.fa CDS: spans
      (stop included) -- the handoff's documented "#1 silent error".
    - non_ATG_start transcripts, where the literal codon-table translation of a near-cognate
      start codon differs from the canonical Met at position 0 only.
    """
    catalog, flagged = [], []
    present_ids = [tid for tid in chrom_transcripts if tid in tx_seqs and tid in prot_seqs]

    for tid in present_ids:
        t = chrom_transcripts[tid]
        span = _extract_cds_span(tx_meta[tid])
        if span is None:
            flagged.append((tid, "no_cds_span"))
            continue
        start, end = span
        cds_with_stop_maybe = tx_seqs[tid][start - 1:end].upper()

        exon_lens = [e - s + 1 for s, e in t["cds"]]
        if sum(exon_lens) != len(cds_with_stop_maybe) - 3:
            flagged.append((tid, "length_mismatch"))
            continue

        protein = prot_seqs[tid].upper()
        if len(cds_with_stop_maybe) == 3 * (len(protein) + 1):
            coding_part = cds_with_stop_maybe[:-3]
        elif len(cds_with_stop_maybe) == 3 * len(protein):
            coding_part = cds_with_stop_maybe
        else:
            flagged.append((tid, "unexpected_length_ratio"))
            continue

        translated = translate(coding_part)
        non_atg = "non_ATG_start" in t["tags"]
        if translated != protein:
            if non_atg and protein[0] == "M" and translated[1:] == protein[1:]:
                pass
            else:
                flagged.append((tid, "translate_mismatch"))
                continue

        exon_chunks, pos = [], 0
        for s, e in t["cds"]:
            n = e - s + 1
            exon_chunks.append(coding_part[pos:pos + n])
            pos += n

        catalog.append({
            "transcript_id": tid,
            "protein_id": protein_ids[tid],
            "gene_id": t["gene_id"],
            "protein_seq": protein,
            "protein_md5": md5_digest(protein),
            "protein_sq": ga4gh_sq_digest(protein),
            "cds_seq": coding_part,
            "cds_md5": md5_digest(coding_part),
            "cds_sq": ga4gh_sq_digest(coding_part),
            "exon_seqs": exon_chunks,
            "exon_hashes": [(md5_digest(c), ga4gh_sq_digest(c), len(c)) for c in exon_chunks],
            "level": t["level"],
            "tags": sorted(t["tags"]),
        })

    return catalog, flagged


def extract_chrom(gtf_path: str, transcripts_fa_path: str, translations_fa_path: str, chrom: str):
    chrom_transcripts = parse_gtf_chrom(gtf_path, chrom)
    tx_seqs, tx_meta = load_transcripts_fasta(transcripts_fa_path)
    prot_seqs, protein_ids = load_translations_fasta(translations_fa_path)
    return build_catalog(chrom_transcripts, tx_seqs, tx_meta, prot_seqs, protein_ids)


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    ref = os.path.join(here, "..", "data", "reference")
    catalog, flagged = extract_chrom(
        os.path.join(ref, "gencode.v46.basic.annotation.gtf.gz"),
        os.path.join(ref, "gencode.v46.pc_transcripts.fa.gz"),
        os.path.join(ref, "gencode.v46.pc_translations.fa.gz"),
        "chr22",
    )
    print(f"validated: {len(catalog)}  flagged: {len(flagged)}")
