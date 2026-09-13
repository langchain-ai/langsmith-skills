#!/usr/bin/env bash
# Translate the verifier result into a Harbor reward. Binary: every check must pass.
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
exit 0
