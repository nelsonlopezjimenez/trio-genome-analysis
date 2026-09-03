#!/usr/bin/env bash
# Deploy the minimal files needed and run a smoke test on the instance launched by
# launch_smoke_test.sh. Scoped deliberately narrow: prove the actual compute pipeline
# (scripts/gencode_cds_extract.py + scripts/batch_haplotype_hash.py) runs correctly
# on real AWS Linux and reproduces the SAME hashes already verified locally --
# extending this project's established cross-platform reproduction pattern
# (Windows/WSL2 -> Mac mini, 2026-08-31) to Mac mini -> AWS.
#
# Deliberately does NOT yet test fetching from S3 -- that's the next, separate step,
# once this baseline (does the compute pipeline work at all on AWS) is confirmed. See
# scripts/aws/README.md.
#
# Usage: ./scripts/aws/deploy_and_test.sh <public-ip> <key-pair-name>

set -euo pipefail

PUBLIC_IP="${1:?Usage: $0 <public-ip> <key-pair-name>}"
KEY_NAME="${2:?Usage: $0 <public-ip> <key-pair-name>}"
KEY_PATH="$HOME/.ssh/${KEY_NAME}.pem"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH="ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new ec2-user@$PUBLIC_IP"
SCP="scp -i $KEY_PATH -o StrictHostKeyChecking=accept-new"

echo "==> Transferring the minimal file set (~92MB: reference data + one real individual + scripts)"
$SSH "mkdir -p ~/trio-genome/data/reference ~/trio-genome/data/giab ~/trio-genome/scripts"
$SCP "$REPO/scripts/gencode_cds_extract.py" "$REPO/scripts/batch_haplotype_hash.py" \
    "ec2-user@$PUBLIC_IP:~/trio-genome/scripts/"
$SCP "$REPO"/data/reference/gencode.v46.*.gz "ec2-user@$PUBLIC_IP:~/trio-genome/data/reference/"
$SCP "$REPO/data/giab/HG002_chr22_phased.vcf.gz" "ec2-user@$PUBLIC_IP:~/trio-genome/data/giab/"

echo "==> Confirming python3 is present (Amazon Linux 2023 ships it; verifying, not assuming)"
$SSH "python3 --version"

echo "==> Running the actual pipeline on the instance"
$SSH "cd ~/trio-genome && python3 scripts/batch_haplotype_hash.py \
    --chrom chr22 --vcf data/giab/HG002_chr22_phased.vcf.gz --sample-id HG002 \
    --out /tmp/aws_smoke_test.tsv.gz --mode iupac"

echo
echo "==> Pulling the result back for comparison against the already-verified local run"
$SCP "ec2-user@$PUBLIC_IP:/tmp/aws_smoke_test.tsv.gz" /tmp/aws_smoke_test_result.tsv.gz

echo "==> Spot-checking the known-verified transcript (ENST00000319363.11, expect hash_md5=3bbd34fa...)"
zcat < /tmp/aws_smoke_test_result.tsv.gz | grep "ENST00000319363.11" || echo "NOT FOUND -- investigate"
echo
echo "Expected (from the Mac mini run, independently verified 2026-09-02):"
echo "  ENST00000319363.11  hash_md5=3bbd34faba73bc134825f8f07a296436  het_count=5"
echo
echo "If those match: the compute pipeline is confirmed correct on real AWS infrastructure."
echo "Next: test fetching from s3://1000genomes directly on the instance (not yet scripted --"
echo "deliberately left as a manual/separate step until this baseline is confirmed)."
echo
echo "!!! Remember to terminate the instance when done:"
echo "  aws ec2 terminate-instances --region us-east-1 --instance-ids \$(cat /tmp/trio-genome-smoke-test-instance-id.txt)"
