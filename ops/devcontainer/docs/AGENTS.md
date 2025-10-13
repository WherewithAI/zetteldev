# WherewithAI Agent Guidance

This document explains how autonomous coding agents should behave when
working inside repositories that inherit from the WherewithAI dev
container image.

## Operating Environment

- Use the `zdev` helper to enter shells, launch Jupyter, and manage
  network logging. Assume the workspace root is `/workspaces/<repo>`.
- All code execution must go through Pixi-managed tasks (for example:
  `pixi run lint`, `pixi run tests`). Do not run tools outside Pixi
  unless explicitly instructed.
- Shared caches live under `/caches`; per-repo environments are under
  `.pixi/` inside the workspace. Never delete cache directories.
- Secrets are provided through environment variables or `.env.local`.
  Never print secret values to stdout or git history.

## Agent Workflow Expectations

1. **Read the Brief First** – For experiment work, review
   `design.md`/`design.org` and associated issues before making any
   changes.
2. **Plan Before Acting** – Draft a concise plan; update it as tasks
   complete. For minor edits, a plan is optional.
3. **Stay in Scope** – Only modify files relevant to the given task.
   If scope creep is discovered, flag it for a human review.
4. **Prefer Determinism** – Use reproducible seeds, deterministic
   pipeline steps, and existing logging conventions.
5. **Testing Is Mandatory** – When changing code, add or update tests
   and run them with `pixi run test` or the task documented in the repo.
6. **Document the Outcome** – Update design documents, READMEs, and
   changelogs that describe behaviour that changed. Summaries must be
   clear but concise.

## Git & Communication

- Commit early and often with descriptive messages; avoid monolithic
  commits that mix unrelated changes.
- Mention open questions or blockers in pull request descriptions using
  GitHub-flavoured markdown.
- When interacting with GitHub issues from the CLI, keep messages brief
  and focused on user-value changes.

## Safety & Compliance Rules

- Do not access external networks beyond what `zdev net log-on` permits.
- Never install global packages system-wide; use Pixi or user-local
  shims (`zdev agents update`).
- Respect the organisation’s coding standards (ruff, black, pyright,
  etc.). If tooling is missing, consult a human before installing.
- When handling datasets, follow the repository’s data usage policies.

## Performance Considerations

- Cache-heavy operations (pip, pixi, huggingface) should rely on the
  shared cache mounts. Do not `pip cache purge` or similar.
- For GPU-enabled containers, always check `zdev doctor` to confirm the
  GPU is visible before starting long jobs.

## Escalation Checklist

Seek human input when:

- A design specification conflicts with existing code.
- Required credentials or data sources are unavailable.
- Proposed changes introduce backwards incompatibilities.
- Runtime errors persist after two remediation attempts.

Keep interactions professional and provide actionable diagnostics.
