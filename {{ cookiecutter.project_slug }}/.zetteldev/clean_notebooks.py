"""Run nbdev-clean over the notebooks we author, and nothing else.

`nbdev-clean` with no arguments walks the whole working tree, which here means it
descends into the submodules (paprika, scaling-forecasting-training, verl, HoH) and
rewrites notebooks that belong to other repositories. It also reaches the vendored
third-party tree under 30-tenenbaum-battleship/upstream, which we track but did not
write and would rather leave as upstream left it.

So the file list comes from `git ls-files`, which never descends into a submodule,
minus the vendored paths.

What cleaning removes is churn, not content: cell ids, cell and output metadata,
kernelspec, execution counts, and the memory addresses inside object reprs
(`<Legend at 0x7ef9ad095190>` -> `<Legend>`) that differ on every execution. Cell
source and rendered outputs are untouched -- these notebooks are computational
essays, and their figures and tables are the deliverable.

    python .zetteldev/clean_notebooks.py            # clean in place
    python .zetteldev/clean_notebooks.py --check    # fail if anything was unclean

`--check` is what CI runs. Locally, `nbdev-install-hooks` cleans on commit so it
never comes up.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

#: Tracked, but authored elsewhere: normalizing it only creates noise against upstream.
VENDORED = ("/upstream/",)


def authored_notebooks() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "*.ipynb"],
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0")
            if p and not any(mark in f"/{p}" for mark in VENDORED)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if cleaning changed anything (leaves the changes in place).")
    args = parser.parse_args()

    notebooks = authored_notebooks()
    if not notebooks:
        print("no authored notebooks found — is this a git checkout?")
        return 1

    # Call nbdev's own CLI entry point, once per file, in this one process. Going through
    # clean_nb + fastcore.nbio directly is NOT equivalent: read_nb rewrites an empty
    # `"source": ""` to `[]`, so it would disagree with `nbdev-clean` and with the git
    # hook on 34 notebooks, forever. CI must apply exactly what a developer's hook applies.
    from nbdev.clean import nbdev_clean

    for path in notebooks:
        nbdev_clean(fname=path)

    print(f"cleaned {len(notebooks)} authored notebooks "
          f"(submodules and vendored trees excluded)")
    if not args.check:
        return 0

    dirty = subprocess.run(["git", "diff", "--name-only", "--", "*.ipynb"],
                           capture_output=True, text=True, check=True).stdout.split()
    if not dirty:
        print("all clean")
        return 0
    print(f"\n{len(dirty)} notebook(s) were not clean:")
    for path in dirty:
        print(f"    {path}")
    print("\nRun `python .zetteldev/clean_notebooks.py` and commit the result.")
    print("To stop this recurring, run `nbdev-install-hooks` once — it cleans on commit.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
