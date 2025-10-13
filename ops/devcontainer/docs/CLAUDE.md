# Claude Code Quickstart

Claude Code runs inside the WherewithAI dev container with the `zdev`
tooling. Follow these norms so your assistance is predictable and safe.

## Environment Basics

- Launch an interactive shell with `zdev shell`. This ensures caches
  and dotenv files load correctly.
- Run project commands via Pixi: `pixi run <task>`. Ask before adding
  new dependencies.
- Logs and artefacts belong inside the repository workspace. Do not
  write to system paths under `/`.

## Editing & Review

- Keep diffs focused. Split large efforts into incremental changes.
- Add docstrings and comments only when the code would otherwise be
  hard to follow.
- Surface potential regressions or missing tests immediately.

## Testing & Validation

- Execute the documented Pixi tasks (`lint`, `test`, `typecheck`) before
  claiming a change is finished.
- Leave breadcrumbs: note any commands executed or assumptions made in
  your summary back to the human collaborator.

## Network Access

- Default mode blocks egress beyond package mirrors baked into the
  image. If networking is required, coordinate with a human and use
  `zdev net log-on`.
- When logging is enabled, assume destinations are recorded; keep
  navigation professional.

## Secrets & Credentials

- Secrets arrive through `.env.local` or SSH agent forwarding. Never
  echo secret values, commit them, or store them in world-readable
  files.
- Use `zdev auth clear` before handing the session back if sensitive
  variables were set.

## Stay Curious, Stay Careful

Clarify ambiguous specs, escalate blockers early, and strive for
reproducible outputs. Your goal is to be a reliable collaborator.
