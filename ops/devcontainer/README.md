# WherewithAI Dev Container Parent Image

This directory contains the assets required to build and publish the
WherewithAI `zdev` dev container images. Two flavours are produced:

- `ghcr.io/wherewithai/zdev:cpu`
- `ghcr.io/wherewithai/zdev:cuda-12.4`

Both images share identical tooling; the CUDA variant layers on top of
`nvidia/cuda:12.4.0-runtime-ubuntu22.04` and expects the host runtime to
provide the NVIDIA container toolkit.

## Quick Start

```bash
# CPU image
docker build \
  -f ops/devcontainer/Dockerfile.cpu \
  -t ghcr.io/wherewithai/zdev:cpu .

# CUDA image
docker build \
  -f ops/devcontainer/Dockerfile.cuda-12.4 \
  -t ghcr.io/wherewithai/zdev:cuda-12.4 .
```

To test locally:

```bash
docker run --rm -it \
  -v "$(pwd)":/workspaces/$(basename "$(pwd)") \
  ghcr.io/wherewithai/zdev:cpu \
  zdev shell
```

## Image Features

- Non-root `dev` user with [`fixuid`](https://github.com/boxboat/fixuid)
  remapping on container start.
- Core build tools (`gcc`, `cmake`, `ninja`) plus runtime utilities
  (`git`, `gh`, `ripgrep`, `fd`, `fzf`, `bat`, `delta`, etc.).
- Node.js 20 + npm to install the `claude-code` and `openai` CLIs.
- [Pixi](https://pixi.sh) installed system-wide; per-repo envs live
  under the workspace.
- Helper script `zdev` (see `scripts/zdev`) that manages cache env vars,
  proxy logging, agent CLI shims, docs sync, and diagnostics.
- Canonical agent docs baked at `/opt/zetteldev/docs`.

## Release Conventions

- Immutable tags: `vYY.MM-<sha7>-cpu` and `vYY.MM-<sha7>-cuda-12.4`
- Moving aliases: `cpu`, `latest-cpu`, `cuda-12.4`, `latest-cuda`
- Registry: `ghcr.io/wherewithai/zdev`

CI should build both flavours on pushes to `main` and when cutting a
release, optionally emitting SBOMs (syft) and signing with cosign.

## Runtime Expectations

- Workspace mounted at `/workspaces/<repo>`
- Shared caches mounted under `/caches/*` (pixi, pip, uv, jupyter,
  huggingface). See the `.devcontainer/devcontainer.json` template for
  volume names.
- Optional network logging proxy toggled via `zdev net log-on`.
- Jupyter Lab started with `zdev jupyter` to honour pixi & proxy setup.

## Extending the Image

Projects should *not* modify this parent image. Add project-specific
dependencies through Pixi inside each repository instead. If the parent
image needs new capabilities, submit a change here, bump the version
stamp in `docs/VERSION`, rebuild, and publish a new tag.
