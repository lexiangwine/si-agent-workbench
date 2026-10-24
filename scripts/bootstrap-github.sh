#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git rev-parse --is-inside-work-tree >/dev/null
branch=$(git branch --show-current)
if [[ "$branch" == main || -z "$branch" ]]; then
  echo 'Use a named feature branch before preparing changes for GitHub.' >&2
  exit 2
fi
bash scripts/check.sh
python3 tools/quality_gate.py --scan
echo 'Checks complete. Inspect git diff, commit only intended files, and push this feature branch.'
echo 'Open a PR linked to the task issue; human review and authorization are required before merge.'
echo 'This helper does not create repositories, commit, push, merge, or change protection settings.'
