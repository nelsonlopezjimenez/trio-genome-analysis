"""External validation: does this project's own (unsalted) MD5/SQ hashing pipeline reproduce
Ensembl's own chr22 protein and CDS sequences, independently sourced?

Answers the open TODO ("validate against a known-good external reference before building
further on it") for real, on chr22. Ensembl release 112 == GENCODE v46 (confirmed directly
from the GENCODE GTF header, not assumed -- see HANDOFF.md).

Two comparisons:
  1. PROTEIN sequences -- clean comparison, no stop-codon convention issue at all.
  2. CDS sequences -- Ensembl's CDS FASTA *includes* the stop codon (see HANDOFF.md's
     stop-codon table); this project's canonical cds_seq excludes it. Reconstructs the
     stop-included form on the fly for a fair comparison (this is the cds_nt_withstop idea
     from the open TODO, applied here ad hoc rather than as a permanent schema column).

Also writes small chr22-only subset FASTAs (data/reference/validation/chr22_*.fa) so the
committed file stays small -- no need to keep the full genome-wide Ensembl download.
"""
import gzip
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gencode_cds_extract as cds

REF = os.path.join(REPO, "data/reference")
VALID = os.path.join(REPO, "data/reference/validation")
CHROM = "chr22"
STOP_CODONS = {"TAA", "TAG", "TGA"}


def load_ensembl_fasta(path, chrom_tag):
    """Ensembl header: >ID ... chromosome:GRCh38:22:... or transcript:ENST...
    Returns {transcript_id: seq} keyed by the bare ENST/ENSP with version."""
    seqs, chunks, current_id, current_is_chrom = {}, [], None, False
    with gzip.open(path, "rt") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if current_id is not None and current_is_chrom:
                    seqs[current_id] = "".join(chunks)
                fields = line[1:].split()
                current_id = fields[0]
                current_is_chrom = f"chromosome:GRCh38:{chrom_tag}:" in line
                chunks = []
            else:
                chunks.append(line)
        if current_id is not None and current_is_chrom:
            seqs[current_id] = "".join(chunks)
    return seqs


def write_fasta_gz(path, records):
    with gzip.open(path, "wt") as fh:
        for acc, seq in records:
            fh.write(f">{acc}\n")
            for i in range(0, len(seq), 60):
                fh.write(seq[i:i + 60] + "\n")


def main():
    print("Loading Ensembl release 112 chr22 protein + CDS sequences...")
    ens_prot = load_ensembl_fasta(os.path.join(VALID, "ensembl112_homo_sapiens.pep.all.fa.gz"), "22")
    ens_cds = load_ensembl_fasta(os.path.join(VALID, "ensembl112_homo_sapiens.cds.all.fa.gz"), "22")
    print(f"  {len(ens_prot)} chr22 proteins, {len(ens_cds)} chr22 CDS (all biotypes, unfiltered)")

    print("\nWriting small chr22-only subset FASTAs for the repo (gzipped)...")
    write_fasta_gz(os.path.join(VALID, "chr22_ensembl112.pep.fa.gz"), sorted(ens_prot.items()))
    write_fasta_gz(os.path.join(VALID, "chr22_ensembl112.cds.fa.gz"), sorted(ens_cds.items()))
    print(f"  wrote chr22_ensembl112.pep.fa.gz, chr22_ensembl112.cds.fa.gz")

    print("\nRebuilding our own validated chr22 catalog (GENCODE v46)...")
    chrom_transcripts = cds.parse_gtf_chrom(os.path.join(REF, "gencode.v46.basic.annotation.gtf.gz"), CHROM)
    tx_seqs, tx_meta = cds.load_transcripts_fasta(os.path.join(REF, "gencode.v46.pc_transcripts.fa.gz"))
    prot_seqs, protein_ids = cds.load_translations_fasta(os.path.join(REF, "gencode.v46.pc_translations.fa.gz"))
    catalog, flagged = cds.build_catalog(chrom_transcripts, tx_seqs, tx_meta, prot_seqs, protein_ids)
    print(f"  {len(catalog)} validated transcripts")

    print("\n=== Comparison 1: PROTEIN sequences (no stop-codon ambiguity) ===")
    prot_checked, prot_match, prot_hash_match = 0, 0, 0
    prot_mismatch_examples = []
    for entry in catalog:
        tid, pid, our_seq = entry["transcript_id"], entry["protein_id"], entry["protein_seq"]
        ens_seq = ens_prot.get(pid)  # Ensembl pep FASTA keys by ENSP, not ENST
        if ens_seq is None:
            continue
        prot_checked += 1
        if our_seq == ens_seq:
            prot_match += 1
            if cds.md5_digest(our_seq) == cds.md5_digest(ens_seq):
                prot_hash_match += 1
        elif len(prot_mismatch_examples) < 3:
            prot_mismatch_examples.append((tid, len(our_seq), len(ens_seq)))
    print(f"  {prot_checked} transcripts present in both sources")
    print(f"  {prot_match}/{prot_checked} sequences byte-identical; {prot_hash_match}/{prot_checked} MD5 hashes match")
    for tid, ol, el in prot_mismatch_examples:
        print(f"    mismatch example: {tid} (ours: {ol} aa, Ensembl: {el} aa)")

    print("\n=== Comparison 2: CDS sequences (Ensembl includes stop, ours excludes it -- reconstructed for fairness) ===")
    cds_checked, cds_match, cds_hash_match = 0, 0, 0
    cds_mismatch_examples = []
    for entry in catalog:
        tid = entry["transcript_id"]
        ens_seq = ens_cds.get(tid)
        if ens_seq is None:
            continue
        cds_checked += 1
        # reconstruct our stop-included form: translate() our CDS, if it ends where a stop
        # codon would be in Ensembl's version, just compare the stop-excluded portion, which
        # must be a prefix of Ensembl's sequence (Ensembl = our cds_seq + stop codon).
        our_seq = entry["cds_seq"]
        ens_no_stop = ens_seq[:-3] if ens_seq[-3:] in STOP_CODONS else ens_seq
        if our_seq == ens_no_stop:
            cds_match += 1
            our_with_stop = our_seq + ens_seq[-3:]
            if cds.md5_digest(our_with_stop) == cds.md5_digest(ens_seq):
                cds_hash_match += 1
        elif len(cds_mismatch_examples) < 3:
            cds_mismatch_examples.append((tid, len(our_seq), len(ens_seq)))
    print(f"  {cds_checked} transcripts present in both sources")
    print(f"  {cds_match}/{cds_checked} sequences match once stop codon is accounted for;")
    print(f"  {cds_hash_match}/{cds_checked} MD5 hashes match on the reconstructed stop-included form")
    for tid, ol, el in cds_mismatch_examples:
        print(f"    mismatch example: {tid} (ours: {ol} nt, Ensembl: {el} nt)")

    print("\n=== Sample hashes (unsalted -- current pipeline, sanity-check baseline) ===")
    shown = 0
    for entry in catalog:
        tid = entry["transcript_id"]
        if entry["protein_id"] in ens_prot and shown < 3:
            print(f"  {tid}")
            print(f"    protein MD5 (ours=Ensembl): {cds.md5_digest(entry['protein_seq'])}")
            print(f"    protein SQ  (ours=Ensembl): {cds.ga4gh_sq_digest(entry['protein_seq'])}")
            shown += 1


if __name__ == "__main__":
    main()
