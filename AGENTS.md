# Multi-Agent Engineering Contract

## Mission
Deliver small, testable changes aligned to documented requirements. No agent may unilaterally deploy production changes.

## Sources of truth
- README.md: repository setup
- docs/PRD.md: product requirements
- docs/ARCHITECTURE.md: technical boundaries
- docs/tasks/: task contracts
- docs/adr/: architecture decisions
- GitHub Issues and PRs: execution and review status

## Agent rules
1. Read the task contract and relevant docs before modifying code.
2. Work only on your assigned branch / Git worktree and declared file scope.
3. If required inputs are missing or scope overlaps with another agent, stop and flag a blocker.
4. Do not edit secrets, real production data, deployment credentials, or protected CI settings.
5. Do not introduce a dependency or change a public API without documenting the decision.
6. Run applicable formatting, linting, typechecks, tests and build before requesting review.
7. Report exact commands and outputs; do not claim tests passed when not run.
8. Avoid unrelated refactors; preserve backwards compatibility unless explicitly authorized.
9. All changes go through a PR with a linked issue and human review.
10. Never push directly to main; never automatically merge or deploy production.

## Done means
- Acceptance criteria from the task contract are met
- Relevant tests exist or a documented reason is supplied
- CI passed on the PR's final commit
- Security, secrets, and dependency review complete
- Reviewer approves and owner authorizes merge

## Handoff format
**Summary:** what was done
**Files:** files changed
**Evidence:** commands, test outputs, links
**Risks:** unresolved issues
**Next action:** exact follow-up
