#!/bin/sh
# kb-session-start.sh — print gotcha titles for quick orientation at session start.
# Usage: sh _meta/kb-session-start.sh   (or add to AGENTS.md as "First action")
# Reads _knowledge/gotchas/*.md and prints name + title of each, plus any active tasks.
# No dependencies beyond sh and grep.

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
VAULT="${KB_VAULT:-$ROOT/_knowledge}"

if [ ! -d "$VAULT/gotchas" ]; then
    echo "No gotchas vault found at $VAULT/gotchas — run kb-sync.py first."
    exit 0
fi

echo "=== Active gotchas ($(ls "$VAULT/gotchas/"*.md 2>/dev/null | wc -l | tr -d ' ') shards) ==="
for f in "$VAULT/gotchas/"*.md; do
    [ -f "$f" ] || continue
    name="$(grep '^name:' "$f" | head -1 | sed 's/name: *//')"
    title="$(grep '^title:' "$f" | head -1 | sed 's/title: *//' | tr -d '"')"
    status="$(grep '^status:' "$f" | head -1 | sed 's/status: *//')"
    [ "$status" = "superseded" ] || [ "$status" = "resolved" ] && continue
    printf "  [[%s]] — %s\n" "$name" "$title"
done

echo ""
echo "=== Active tasks ==="
for f in "$VAULT/tasks/"*.md; do
    [ -f "$f" ] || continue
    status="$(grep '^status:' "$f" | head -1 | sed 's/status: *//')"
    [ "$status" = "active" ] || continue
    name="$(grep '^name:' "$f" | head -1 | sed 's/name: *//')"
    title="$(grep '^title:' "$f" | head -1 | sed 's/title: *//' | tr -d '"')"
    printf "  [[%s]] — %s\n" "$name" "$title"
done
