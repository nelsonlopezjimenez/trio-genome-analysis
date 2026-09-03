#!/usr/bin/env bash
# Deploy-side prep for Phase 2 (the real population-scale batch) onto an already-running
# instance. NOT the full batch orchestrator -- that still needs its own design (sample
# enumeration, parallelization strategy, per-chromosome S3 fetch loop) and its own
# explicit go-ahead before Phase 2 actually runs. This script covers what's already
# decided and ready: transferring the pipeline code, the genome-wide reference data and
# CDS-region BED files, and the salt -- safely.
#
# SALT HANDLING: the salt file's argument here is a PATH, never the salt's contents --
# this script only ever moves the file, it doesn't read or print what's inside it. Create
# the salt file yourself, directly in your own terminal (nano, or `read -s`), BEFORE
# running this -- see HANDOFF.md's "Salt handling hardened" section for why (echo/history
# exposure). The file is scp'd over SSH (encrypted in transit) and chmod 600'd on the
# instance; it's destroyed along with everything else when the instance is terminated
# after the run -- no separate cleanup step needed.
#
# Usage: ./scripts/aws/phase2_deploy.sh <public-ip> <key-pair-name> <salt-file-path>

set -euo pipefail

PUBLIC_IP="${1:?Usage: $0 <public-ip> <key-pair-name> <salt-file-path>}"
KEY_NAME="${2:?Usage: $0 <public-ip> <key-pair-name> <salt-file-path>}"
SALT_FILE="${3:?Usage: $0 <public-ip> <key-pair-name> <salt-file-path>}"
KEY_PATH="$HOME/.ssh/${KEY_NAME}.pem"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH="ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new ec2-user@$PUBLIC_IP"
SCP="scp -i $KEY_PATH -o StrictHostKeyChecking=accept-new"

if [ ! -f "$SALT_FILE" ]; then
    echo "!!! Salt file not found: $SALT_FILE" >&2
    echo "    Create it yourself first (nano \"$SALT_FILE\", or a 'read -s' one-liner --" >&2
    echo "    see HANDOFF.md's salt-handling section). This script only moves the file," >&2
    echo "    it never creates or reads its contents." >&2
    exit 1
fi

echo "==> Transferring pipeline code"
$SSH "mkdir -p ~/trio-genome/data/reference/cds_regions ~/trio-genome/scripts"
$SCP "$REPO/scripts/gencode_cds_extract.py" "$REPO/scripts/batch_haplotype_hash.py" \
    "$REPO/scripts/load_individual_hashes.py" \
    "ec2-user@$PUBLIC_IP:~/trio-genome/scripts/"

echo "==> Transferring genome-wide reference data (GENCODE v46)"
$SCP "$REPO"/data/reference/gencode.v46.*.gz "ec2-user@$PUBLIC_IP:~/trio-genome/data/reference/"

echo "==> Transferring CDS-region BED files (all 24 chromosomes, 201,612 regions)"
$SCP "$REPO"/data/reference/cds_regions/*.bed "ec2-user@$PUBLIC_IP:~/trio-genome/data/reference/cds_regions/"

echo "==> Transferring the salt file (path only ever appears here -- not its contents)"
$SCP "$SALT_FILE" "ec2-user@$PUBLIC_IP:~/trio-genome/.salt"
$SSH "chmod 600 ~/trio-genome/.salt"
echo "    salt available on-instance at ~/trio-genome/.salt (600 perms, ec2-user only)"

echo
echo "==> Deploy-side prep done. NOT yet built: the actual batch loop (per-individual"
echo "    S3 fetch + hash + load, across all 2,504 individuals and 24 chromosomes) --"
echo "    that's separate, undesigned work needing its own go-ahead before Phase 2 runs"
echo "    for real. This only gets the instance ready for it."
echo
echo "    Once the batch loop exists, invoke batch_haplotype_hash.py on-instance with:"
echo "      --salt-file ~/trio-genome/.salt"
