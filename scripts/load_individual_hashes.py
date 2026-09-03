"""Create/load the per-individual hash catalog -- individual_hash_catalog.db -- from
batch_haplotype_hash.py's .tsv.gz output. Kept as a SEPARATE database from
hash_catalog.db (reference-only, unsalted) per explicit instruction: never merged in.

Schema decided 2026-09-03 (see HANDOFF.md's "Phase 2 output catalog schema" section):
one flat table, not split into unsalted/salted tables -- the real usage model is one
salt at a time, not multiple coexisting salt-versions per individual, so the added
complexity of a two-table split isn't earned. UNIQUE(transcript_id, sample_id,
representation) doubles as a re-run guard: INSERT OR REPLACE makes it safe to rerun
this loader as many times as needed (after an interrupted Phase 2 batch, or a
deliberate re-salt) without manually clearing tables first -- a re-salted reload simply
overwrites the old salted_hash_md5/salted_hash_sq/salt_label for that identity, which
is the intended "old salted values become obsolete" behavior, not an accident.

Usage:
    python3 scripts/load_individual_hashes.py --db data/derived/individual_hash_catalog.db \\
        --salt-label "phase2-2026-09" \\
        data/derived/chr22/HG002_chr22_iupac.tsv.gz [more .tsv.gz files...]
"""

import argparse
import gzip
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS individual_hashes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id   TEXT NOT NULL,
    gene_id         TEXT NOT NULL,
    sample_id       TEXT NOT NULL,
    representation  TEXT NOT NULL,
    hash_md5        TEXT NOT NULL,
    hash_sq         TEXT NOT NULL,
    salted_hash_md5 TEXT,
    salted_hash_sq  TEXT,
    length          INTEGER NOT NULL,
    het_count       INTEGER,
    salt_label      TEXT,
    UNIQUE(transcript_id, sample_id, representation)
);
"""

EXPECTED_HEADER = ["transcript_id", "gene_id", "sample_id", "representation", "hash_md5",
                   "hash_sq", "salted_hash_md5", "salted_hash_sq", "length", "het_count"]


def load_tsv(conn, tsv_path, salt_label):
    with gzip.open(tsv_path, "rt") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        if header != EXPECTED_HEADER:
            raise ValueError(f"{tsv_path}: unexpected header {header}, expected {EXPECTED_HEADER} "
                              f"-- was this produced by an older batch_haplotype_hash.py?")
        rows = []
        for line in fh:
            f = line.rstrip("\n").split("\t")
            transcript_id, gene_id, sample_id, representation, hash_md5, hash_sq, \
                salted_hash_md5, salted_hash_sq, length, het_count = f
            rows.append((
                transcript_id, gene_id, sample_id, representation, hash_md5, hash_sq,
                salted_hash_md5 or None, salted_hash_sq or None, int(length),
                int(het_count) if het_count else None, salt_label,
            ))
    conn.executemany(
        """INSERT OR REPLACE INTO individual_hashes
           (transcript_id, gene_id, sample_id, representation, hash_md5, hash_sq,
            salted_hash_md5, salted_hash_sq, length, het_count, salt_label)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/derived/individual_hash_catalog.db")
    ap.add_argument("--salt-label", default=None,
                     help="tag for this load's salted values, e.g. a date or run name "
                          "(NEVER the raw salt itself). Omit for unsalted-only loads.")
    ap.add_argument("tsv_files", nargs="+", help=".tsv.gz files from batch_haplotype_hash.py")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.execute(SCHEMA)

    total = 0
    for tsv_path in args.tsv_files:
        n = load_tsv(conn, tsv_path, args.salt_label)
        total += n
        print(f"{tsv_path}: {n} rows loaded/replaced")
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM individual_hashes").fetchone()[0]
    sample_count = conn.execute("SELECT COUNT(DISTINCT sample_id) FROM individual_hashes").fetchone()[0]
    conn.close()

    print(f"\n{total} rows processed across {len(args.tsv_files)} file(s).")
    print(f"{args.db} now has {row_count} total rows, {sample_count} distinct sample_id(s).")


if __name__ == "__main__":
    main()
