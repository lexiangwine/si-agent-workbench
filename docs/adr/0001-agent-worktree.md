# ADR-0001: One coding agent per worktree
Status: Accepted

## Decision
Assign each simultaneous implementation task its own Git branch and worktree. Give each task an explicit file scope and acceptance criteria. Integrate through PRs. Branch protection must be configured and verified separately; this scaffold does not enable it.

## Why
Prevents simultaneous edits to the same working directory, makes review and rollback straightforward.

## Caveats
Separate branches can still conflict at merge time. Worktree isolation does not replace architecture coordination or CI.
