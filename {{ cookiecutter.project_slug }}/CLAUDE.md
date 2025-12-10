# Project Structure & Philosophy

This is an academic repository using the Zetteldev framework, whose tagline is "Literate Programming for Reproducible Research in the Era of LLMs". This repository will correspond to a published paper; as such, our goal is maximizing interpretability and reproducibility while making exploration easy. 

There are three modes of work within this repo.

1. Gambols: exploration and play. It needn't be rigorous, it should be loose, fast, and inspired. This happens within the `gambols` folder, mostly within jupyter notebooks and throwaway scripts. If your current path includes 'gambols', you are in this mode. Have fun. YOU MUST NOW read the gambols/gambols.md file for further instructions.
2. Experiments: reproducible, spec-driven research programming. If your path includes 'experiments', you are in this mode. You must now read the experiments/experiments.md file for further instructions.
3. Infrastructure: you are building something important which will be used by downstream experiments and gambols. Spend the time to build it properly. Iterate with the researcher to understand his compute constraints. If your path includes 'infra', you are in infrastructure mode. You must now read the infra/infra.md file for further instructions.

Before you read the specific instructions for your role, here are the general expectations.

# Conventions

## Environment & Package Management
This project uses **uv** for Python package management and **just** as a task runner.

### uv basics
- `uv sync` - Install all dependencies from pyproject.toml
- `uv sync --group dev` - Also install dev dependencies
- `uv run python script.py` - Run a script in the virtual environment
- `uv add package` - Add a new dependency
- `uv add --dev package` - Add a dev dependency
- `uv pip install package` - pip-compatible interface for one-off installs
- `uv pip compile` / `uv pip sync` - pip-tools compatible workflow

Dependencies are defined in `pyproject.toml`. If you need a package not listed, please ask.

### just task runner
Common tasks are defined in `justfile`. Run `just` to see all available commands:
- `just test` - Run pytest
- `just notebooks` - Launch Jupyter Lab
- `just nbsync` - Export notebooks to Python modules
- `just create-experiment` - Create a new experiment

See the full list with `just --list`. 

## Code Style Guidelines

- **Python Version**: 3.11+
- **Imports**: Standard library first, third-party packages, local modules
- **Type Annotations**: Use typing for function parameters and returns
- **Documentation**: Google-style docstrings with params and returns
- **Error Handling**: Specific exceptions with proper logging
  - Don't allow things to silently fail. If something critical to the experiment (i.e. a specified model, a necessary API key) is missing, the researcher needs to be informed immediately.

Now go read the next set of instructions for your role.