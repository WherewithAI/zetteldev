"""After generation: build AGENTS.md from the rendered CLAUDE.md, inlining the packs (Codex does not follow @imports)."""
import subprocess, sys
subprocess.run([sys.executable, ".zetteldev/agents/build_agents_md.py"], check=False)
