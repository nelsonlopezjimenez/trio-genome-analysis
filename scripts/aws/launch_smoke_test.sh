#!/usr/bin/env bash
# Launch ONE small EC2 instance for an initial smoke test of batch_haplotype_hash.py
# on AWS, colocated with the public 1000 Genomes data. This is deliberately NOT the
# full population-scale batch run -- see HANDOFF.md's "Scaling to genome-wide and
# population scale" section. Validate end-to-end on one instance/one individual
# first, per this project's established "small sample first" pattern, before
# committing to the larger (~64 vCPU) batch instance the cost estimate was based on.
#
# SAFETY: this script does not run automatically as part of any other tooling. It
# creates real, billable AWS resources when you run it. Read it before running it.
# Nothing here provisions anything by itself just by existing in the repo.
#
# Prerequisites (not done by this script):
#   - AWS credentials configured (`aws configure`), ideally an IAM user scoped to
#     EC2 + S3 read, not root account credentials.
#   - An EC2 key pair for SSH access. Create one if you don't have one:
#       aws ec2 create-key-pair --key-name trio-genome-aws --query 'KeyMaterial' \
#           --output text --region us-east-1 > ~/.ssh/trio-genome-aws.pem
#       chmod 400 ~/.ssh/trio-genome-aws.pem
#
# Usage: ./scripts/aws/launch_smoke_test.sh <key-pair-name>

set -euo pipefail

KEY_NAME="${1:?Usage: $0 <key-pair-name> -- the EC2 key pair to SSH in with}"
REGION="us-east-1"   # verified colocated with s3://1000genomes (x-amz-bucket-region header, 2026-09-02)
INSTANCE_TYPE="c6i.xlarge"   # 4 vCPU -- smoke test scale, NOT the ~64 vCPU batch estimate
SG_NAME="trio-genome-smoke-test"

echo "==> Region: $REGION | Instance type: $INSTANCE_TYPE (smoke test, not the full batch)"

echo "==> Finding your current public IP (to scope SSH access to just you, not 0.0.0.0/0)"
MY_IP="$(curl -fsS https://checkip.amazonaws.com)"
echo "    $MY_IP"

echo "==> Finding the latest Amazon Linux 2023 AMI (has python3 preinstalled)"
AMI_ID="$(aws ec2 describe-images --region "$REGION" \
    --owners amazon \
    --filters "Name=name,Values=al2023-ami-*-x86_64" "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)"
echo "    $AMI_ID"

echo "==> Creating security group (SSH from $MY_IP/32 only), if it doesn't already exist"
SG_ID="$(aws ec2 describe-security-groups --region "$REGION" \
    --filters "Name=group-name,Values=$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")"
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    SG_ID="$(aws ec2 create-security-group --region "$REGION" \
        --group-name "$SG_NAME" \
        --description "SSH-only, single-IP, trio-genome AWS smoke test" \
        --query 'GroupId' --output text)"
    aws ec2 authorize-security-group-ingress --region "$REGION" \
        --group-id "$SG_ID" --protocol tcp --port 22 --cidr "${MY_IP}/32" >/dev/null
    echo "    created $SG_ID, SSH open to ${MY_IP}/32 only"
else
    echo "    reusing existing $SG_ID"
fi

echo "==> Launching instance (on-demand -- spot capacity for $INSTANCE_TYPE was unavailable"
echo "    in $REGION at smoke-test time, 2026-09-03; on-demand trades a few cents for reliability)"
INSTANCE_ID="$(aws ec2 run-instances --region "$REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=trio-genome-smoke-test}]' \
    --query 'Instances[0].InstanceId' --output text)"
echo "    $INSTANCE_ID (on-demand instance)"

echo "==> Waiting for it to be running..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

PUBLIC_IP="$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"

echo
echo "==> Instance running: $INSTANCE_ID at $PUBLIC_IP"
echo "    SSH in with:"
echo "      ssh -i ~/.ssh/${KEY_NAME}.pem ec2-user@${PUBLIC_IP}"
echo
echo "    Next: scripts/aws/deploy_and_test.sh $PUBLIC_IP $KEY_NAME"
echo
echo "    !!! REMEMBER TO TERMINATE WHEN DONE (this costs money while running):"
echo "      aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCE_ID"
echo "$INSTANCE_ID" > /tmp/trio-genome-smoke-test-instance-id.txt
