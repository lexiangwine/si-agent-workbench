#!/usr/bin/env bash
set -euo pipefail
# Usage: bash scripts/new-agent-worktree.sh feature-name
name="${1:?Usage: bash scripts/new-agent-worktree.sh task-name}"
if [[ ! "$name" =~ ^[a-zA-Z0-9_-]+$ ]]; then echo 'Use letters, numbers, _ and - only' >&2; exit 1; fi
git fetch origin main
git worktree add "../$(basename "$PWD")-$name" -b "agent/$name" origin/main
printf 'Created worktree: %s\n' "../$(basename "$PWD")-$name"
