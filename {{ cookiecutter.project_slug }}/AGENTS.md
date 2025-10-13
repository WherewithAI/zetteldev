# Project Structure & Philosophy

This is an academic repository using the Zetteldev framework, whose tagline is "Literate Programming for Reproducible Research in the Era of LLMs". This repository will correspond to a published paper; as such, our goal is maximizing interpretability and reproducibility while making exploration easy. 

There are three modes of work within this repo.

1. Gambols: exploration and play. It needn't be rigorous, it should be loose, fast, and inspired. This happens within the `gambols` folder, mostly within jupyter notebooks and throwaway scripts. If your current path includes 'gambols', you are in this mode. Have fun. YOU MUST NOW read the gambols/gambols.md file for further instructions.
2. Experiments: reproducible, spec-driven research programming. If your path includes 'experiments', you are in this mode. You must now read the experiments/experiments.md file for further instructions.
3. Infrastructure: you are building something important which will be used by downstream experiments and gambols. Spend the time to build it properly. Iterate with the researcher to understand his compute constraints. If your path includes 'infra', you are in infrastructure mode. You must now read the infra/infra.md file for further instructions.

Before you read the specific instructions for your role, here are the general expectations.

# Conventions

## Environment & Package Management
This project uses pixi, a poetry-like package manager. Available packages can be found in `pixi.toml` in the project root. If you require a package not available, please ask. Also ask if you know of a package which would make an implementation substantially easier.

- To execute code in the environment, use `pixi run ...`
- `pixi run python script.py` - Run any Python script within the pixi environment.
- `pixi run snakemake all` - Run the snakemake pipeline for an experiment
- `pixi add conda_package` or `pixi add --pypi pip_package`. 

## Code Style Guidelines

- **Python Version**: 3.11+
- **Imports**: Standard library first, third-party packages, local modules
- **Type Annotations**: Use typing for function parameters and returns
- **Documentation**: Google-style docstrings with params and returns
- **Error Handling**: Specific exceptions with proper logging
  - Don't allow things to silently fail. If something critical to the experiment (i.e. a specified model, a necessary API key) is missing, the researcher needs to be informed immediately.
