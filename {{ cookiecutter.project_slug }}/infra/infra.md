
# Infrastructure

- You are running on a linux box with 2 4090 GPUs; make use of these for prototyping and obtaining quick results.
- Computationally heavy tasks (those requiring more than two hours of GPU time) must be run on the Della cluster. These are still initiated via the same Snakemake workflow as when running locally, but with some constraints. Notably, there is no internet access on the cluster's GPU nodes; HuggingFace, etc, must be configured to download models separately from running them.
- Testing is mandatory. 
