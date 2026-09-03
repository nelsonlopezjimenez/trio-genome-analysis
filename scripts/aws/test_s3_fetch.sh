#!/usr/bin/env bash
# Test fetching directly from s3://1000genomes on an EC2 instance -- the one thing
# Phase 1 (deploy_and_test.sh) deliberately left untested. Answers two real questions:
#   1. Is the bucket reachable and public (no credentials) from inside AWS, same as from
#      the Mac mini?
#   2. Is a same-region instance actually faster for this data than home internet -- the
#      real premise behind the Phase 2 cost/timing estimates in HANDOFF.md, which have
#      been estimates only until now.
#
# Reuses the exact S3 URL and BED-restriction technique already verified during the
# impostor test (data/giab/impostor_test/chr22_cds_regions.bed, 4,186 CDS regions,
# 0.7 Mb vs. chr22's 40.3 Mb) -- see HANDOFF.md's "Data acquisition for population-scale
# sources" section.
#
# Usage: ./scripts/aws/test_s3_fetch.sh <public-ip> <key-pair-name>

set -euo pipefail

PUBLIC_IP="${1:?Usage: $0 <public-ip> <key-pair-name>}"
KEY_NAME="${2:?Usage: $0 <public-ip> <key-pair-name>}"
KEY_PATH="$HOME/.ssh/${KEY_NAME}.pem"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH="ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new ec2-user@$PUBLIC_IP"
SCP="scp -i $KEY_PATH -o StrictHostKeyChecking=accept-new"

VCF_URL="https://1000genomes.s3.amazonaws.com/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz"
SAMPLE="NA19240"   # same sample used in the earlier impostor test, for continuity

echo "==> Transferring the CDS-region BED file (4,186 regions, 0.7 Mb of chr22)"
$SSH "mkdir -p ~/trio-genome/data"
$SCP "$REPO/data/giab/impostor_test/chr22_cds_regions.bed" "ec2-user@$PUBLIC_IP:~/trio-genome/data/"

echo
echo "==> Step 1: bucket reachability (no credentials -- confirming public access from inside AWS too)"
$SSH "curl -sI '$VCF_URL' | head -5"

echo
echo "==> Step 2: raw throughput -- first 100MB byte-range, timed"
$SSH "time curl -sr 0-104857600 -o /tmp/chr22_sample.bin '$VCF_URL' && ls -la /tmp/chr22_sample.bin && rm -f /tmp/chr22_sample.bin"

echo
echo "==> Step 3: attempting the real technique -- BED-restricted single-sample slice via bcftools"
echo "    (installing bcftools on-instance; Amazon Linux 2023 does not ship it by default)"
if $SSH "sudo dnf install -y bcftools" 2>&1 | tail -5; then
    echo "    bcftools installed -- running the actual BED-restricted fetch (sample $SAMPLE)"
    $SSH "cd ~/trio-genome && time bcftools view -s $SAMPLE -R data/chr22_cds_regions.bed -Oz \
        -o /tmp/${SAMPLE}_chr22_cds.vcf.gz '$VCF_URL' && \
        echo 'variant count:' \$(bcftools view -H /tmp/${SAMPLE}_chr22_cds.vcf.gz | wc -l) && \
        ls -la /tmp/${SAMPLE}_chr22_cds.vcf.gz"
else
    echo "    !!! bcftools not available via default dnf repos on this AMI -- skipping Step 3."
    echo "    Step 1/2 above (raw reachability + throughput) still stand on their own; the"
    echo "    BED-restricted technique itself was already proven correct on the Mac mini during"
    echo "    the impostor test -- this only leaves the on-AWS timing number unmeasured, not the"
    echo "    correctness. Alternate install path (source build / conda / pysam+pip) would be"
    echo "    needed to get that number -- not attempted here, deliberately kept this test light."
fi

echo
echo "==> Done. Remember to terminate the instance when done:"
echo "  aws ec2 terminate-instances --region us-east-1 --instance-ids \$(cat /tmp/trio-genome-smoke-test-instance-id.txt)"
