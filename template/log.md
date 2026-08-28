---
type: log
title: "{PROJECT} knowledge — append-only build/session log"
updated: TODO
---

# log

**Append-only** chronological record. One line per session/event:
`## [YYYY-MM-DD] <kind> | <summary>`. Recent last. Find recent: `grep '^## \[' log.md | tail`.

## [YYYY-MM-DD] kb-init | Vault created from agent-kb
Seeded structure from the agent-kb kit. Next: distill raw sources into shards, then run
`kb-sync.py`.
