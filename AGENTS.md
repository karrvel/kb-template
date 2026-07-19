# AGENTS.md — for an agent working inside kb-template

This repo is a **kit**, not a project to build. It gives *other* projects a durable, agent-maintained
knowledge base (plain-markdown, git-versioned, two-tier memory). Two jobs bring you here:

## Job A — initialize this kit into a target project
The user wants a knowledge base set up in some *other* project. Follow the
**[initialization prompt in README.md](README.md#for-agents--initialization)** verbatim — it handles
empty/fresh and brownfield projects. In short: copy `template/` → the project's `_knowledge/`,
`tooling/*.py` → its `_meta/`, wire the `CLAUDE.md` LIVE markers, **mine the project's own local
Claude/Codex session history with `prefilter.py`** (`~/.claude/projects/<encoded-cwd>/` +
`~/.codex/sessions/` — the highest-value source of off-code knowledge), seed shards (skeleton-first,
verify against code), then run `kb-sync → kb-fix → kb-lint → kb-links`.

## Job B — improve the kit itself
You're editing the template, tooling, or research here. Rules:
- **Tooling is stdlib-only Python 3** (no deps) and idempotent. Keep it that way. Each script derives
  `KB_ROOT` as two dirs up from itself and honors `KB_*` env overrides.
- **The scripts are the contract.** Frontmatter schema lives in `template/_SHARD_TEMPLATE.md` +
  `template/README.md`; `kb-lint.py` enforces it; `kb-sync.py` reads it to generate navigation. Change
  one, change all three consistently.
- **Never commit secrets or real project data.** `tooling/kb-eval/traps.jsonl` is a *redacted example*;
  real traps live in the git-ignored `traps.local.jsonl`, and `tooling/kb-eval/results/` is git-ignored.
  Before committing, scan for prod identifiers, tokens, and absolute user paths.
- **The research is fact-checked.** `research/` claims were adversarially verified; don't add claims
  without a primary source, and preserve the "hedges / refuted claims" honesty.
- Run `python3 tooling/kb-lint.py` and `python3 tooling/kb-links.py` against `template/` after changes.

## Layout
`research/` = why · `template/` = the vault scaffold · `tooling/` = the scripts · `HOWTO.md` = the
build playbook. `README.md` is the human+agent entry point.
