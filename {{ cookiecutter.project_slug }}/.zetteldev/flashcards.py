"""Draft-then-commit flashcards to Anki with fastanki: a list of (front, back) pairs becomes Basic cards in a deck, synced to AnkiWeb.

The workflow the author asked for (CRAFT, "Flashcards, and learning the craft"): when a conversation has crossed
difficult new terrain, draft several Matuschak-style cards on it, let the author choose, then commit the chosen
few. `commit` is that last step in one call; `fastanki.skill` (also a pyskill) holds the full API and the
principles for writing good cards.

    from zetteldev.flashcards import commit, recent
    commit([("What is the successor measure?", "The discounted distribution of future states from a state under a policy."),
            ("Why does the Bellman-gap FB loss have a direction of unbounded descent on tiny data?",
             "F·B can scale up while the off-diagonal gap shrinks; with few transitions F can make B near-orthogonal, so the diagonal term dominates.")],
           deck="Default", tags="<repo> fb")
    recent(days=7)          # what was added lately, to avoid duplicates

Credentials: the first `sync` needs AnkiWeb `user` and `passw` (or ANKI_USER / ANKI_PASS in the environment);
fastanki keeps a host key afterwards. Nothing is uploaded without a sync, so `commit(..., sync=False)` stages.
"""
from __future__ import annotations
import os

__all__ = ["commit", "recent", "sync_now"]


def commit(cards: list[tuple[str, str]], deck: str = "Default", tags: str | None = None, sync: bool = True) -> list[int]:
    "Add Basic cards (front, back) to `deck` with `tags`, then sync to AnkiWeb unless `sync=False`; returns the new note ids."
    from fastanki import add_fb_card
    ids = [add_fb_card(front=f, back=b, deck=deck, tags=tags) for f, b in cards]
    if sync: sync_now()
    return ids


def recent(days: int = 7, deck: str | None = None) -> list:
    "Notes added in the last `days` days (optionally in one deck), so a new batch can avoid repeating them."
    from fastanki import find_notes
    return find_notes(deck=deck, added_days=days)


def sync_now() -> dict:
    "Sync with AnkiWeb; on a first-ever sync uses ANKI_USER / ANKI_PASS from the environment, ~/.env, or the repo .env."
    from fastanki import sync
    from dotenv import load_dotenv
    for f in (os.path.expanduser("~/.env"), ".env"): load_dotenv(f)
    u, p = os.environ.get("ANKI_USER"), os.environ.get("ANKI_PASS")
    return sync(user=u, passw=p) if u and p else sync()
