#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo '[quality-gate] Python syntax and unit tests'
python3 -m compileall -q workbench tools tests
python3 -m unittest discover -s tests -v
echo '[quality-gate] shell syntax'
for script in scripts/*.sh; do bash -n "$script"; done
if command -v node >/dev/null 2>&1; then
  node --check workbench/dashboard.js
  node tests/dashboard-smoke.cjs
fi
python3 -m workbench doctor
echo '[quality-gate] all mandatory checks passed'
