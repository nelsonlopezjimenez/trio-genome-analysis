#!/usr/bin/env bash
# Terminate the smoke-test instance. Small, deliberately separate script so
# "stop paying for this" is always a single obvious command, not buried in a
# larger script's flags.
#
# Usage: ./scripts/aws/terminate.sh [instance-id]
#   (defaults to the instance ID launch_smoke_test.sh recorded, if omitted)

set -euo pipefail

REGION="us-east-1"
INSTANCE_ID="${1:-$(cat /tmp/trio-genome-smoke-test-instance-id.txt 2>/dev/null || true)}"

if [ -z "$INSTANCE_ID" ]; then
    echo "No instance ID given and none found at /tmp/trio-genome-smoke-test-instance-id.txt" >&2
    echo "Usage: $0 <instance-id>" >&2
    exit 1
fi

echo "==> Terminating $INSTANCE_ID in $REGION"
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"
echo "==> Terminated and confirmed stopped billing."
rm -f /tmp/trio-genome-smoke-test-instance-id.txt
