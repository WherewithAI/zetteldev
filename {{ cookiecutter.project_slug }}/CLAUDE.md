@.zetteldev/agents/zetteldev.md
@.zetteldev/agents/harness.md
@.zetteldev/agents/solveit.md
@.zetteldev/agents/della.md
@.zetteldev/agents/mo.md
@.zetteldev/agents/setup.md

# {{ cookiecutter.project_name | upper }}, THIS REPO IN PARTICULAR

- The hosts this repository uses are named in `[tool.zetteldev]` of `pyproject.toml`; what differs per person lives in `~/.config/zetteldev/config.toml`. `just doctor` says what is still missing (the setup guide above).
- Models served from the cluster are blocks of `.zetteldev/della/targets.yaml`; long-lived services are blocks of `.zetteldev/services.yaml`.
- Add here what an agent must know about this repository alone: the project module's name, where the main corpus lives, which models and services the experiments lean on.

## THE REQUEST BEGINS
