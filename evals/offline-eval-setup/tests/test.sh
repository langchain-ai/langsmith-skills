#!/usr/bin/env bash
# Translate the verifier result into a Harbor reward. Binary: every check must pass.
#
# Exit 2 from verify.py means the evidence was unobtainable -- a LangSmith
# outage, an auth failure, or ingestion still incomplete at the deadline. That
# is an infrastructure fault, not failed agent work. Harbor still needs a
# reward file, so we write 0 and leave invalid.txt behind; evals/run.py reads
# that marker and reports infra (exit 3) rather than a reward regression.
set -uo pipefail

mkdir -p /logs/verifier
cd /workspace || exit 1

python3 /tests/verify.py
status=$?

if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi

if [ "$status" -eq 2 ] && [ ! -s /logs/verifier/invalid.txt ]; then
  echo "verifier exited 2 without a reason" > /logs/verifier/invalid.txt
fi
exit 0
