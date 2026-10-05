"""Write an `AGENTS.md` for Codex from a `CLAUDE.md`, inlining its `@path` imports, which Codex does not follow.

    python3 .zetteldev/agents/build_agents_md.py                                   # CLAUDE.md -> AGENTS.md here
    python3 .zetteldev/agents/build_agents_md.py ~/.claude/CLAUDE.md ~/.codex/AGENTS.md

An import is a line holding only `@<path>`; a relative path resolves against the importing file, `~` against
home, as Claude Code does. Imports nest up to five deep.
"""
import re, sys
from pathlib import Path

_IMPORT = re.compile(r'^@(\S+)\s*$')

def expand(path: Path, depth: int = 0) -> str:
    "The text of `path` with each import line replaced by the expanded text it names"
    if depth > 5: sys.exit(f'imports nest deeper than five at {path}')
    out = []
    for line in path.read_text().splitlines():
        m = _IMPORT.match(line)
        out.append(expand((path.parent / Path(m[1]).expanduser()).resolve(), depth + 1).rstrip('\n') if m else line)
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    src = Path(sys.argv[1] if len(sys.argv) > 1 else 'CLAUDE.md').expanduser()
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else src.parent / 'AGENTS.md').expanduser()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(f'<!-- Generated from {src.name} by .zetteldev/agents/build_agents_md.py; edit that file, then `just agents-md`. -->\n\n' + expand(src))
    print(f'{src} -> {dst}')
