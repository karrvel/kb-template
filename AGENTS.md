# AGENTS.md — for an agent working inside kb-template

This repo is a **kit**, not a project to build. It gives *other* projects a durable, agent-maintained
knowledge base (plain-markdown, git-versioned, two-tier memory). Two jobs bring you here:

## Job A — initialize this kit into a target project
The user wants a knowledge base set up in some *other* project. Follow the
**[initialization prompt in README.md](README.md#for-agents--initialization)** verbatim — it handles
empty/fresh and brownfield projects. In short: copy `template/` → the project's `_knowledge/`,
`tooling/*.py` → its `_meta/`, wire the `CLAUDE.md` LIVE markers, mine all three raw sources below
(skeleton-first, verify against code), then run `kb-sync → kb-fix → kb-lint → kb-links`.

### Raw sources to mine at init (in priority order)

**1. Git commit history — do this first, it's free and fast.**
Run these in the target project's repo root before touching agent transcripts:
```bash
# overview — scope and cadence
git log --oneline | head -100

# detailed recent history — decisions, gotchas, incident responses
git log --format="%ad %h %s%n%b" --date=short --since="6 months ago"

# files that change together most — reveals coupling and hot spots
git log --pretty=format: --name-only | sort | uniq -c | sort -rn | head -30

# biggest single-commit churn — often marks a rewrite or incident fix
git log --shortstat --since="1 year ago" | grep -E "files? changed"
```
Look specifically for: commit messages mentioning "fix", "bug", "revert", "hotfix", "do not",
"workaround", "broken" → these are gotcha candidates. Messages mentioning "decision", "choose",
"switch", "replace", "instead of" → decision candidates. Subjects describing a refactor or
incident response → architecture/security candidates. Write each finding as its own shard with
`provenance: git:<short-hash> <date>`.

**2. Agent transcripts — highest-value for off-code tribal knowledge.**
`prefilter.py` against `~/.claude/projects/<encoded-cwd>/` + `~/.codex/sessions/` — strips ~95–98%
tool-call noise. Mine after the git pass so you don't duplicate what commits already say.

**3. Reference docs — PRDs, architecture docs, prior analyses.**
Copy into `_knowledge/reference/`. These are the skeleton backbone; distill them before gap-filling
from transcripts.

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
- **This repo is public — a mechanical PII guard enforces it.** `tooling/pii-scan.py` (codified
  regexes: Claude session URLs, `/Users/…` paths, tokens, emails) blocks pushes via a **pre-push**
  hook. Enable per-clone: `ln -sf ../../tooling/hooks/pre-push .git/hooks/pre-push` (or
  `git config core.hooksPath tooling/hooks`). User/project-specific literals (other private repo
  names, personal emails) go in a **git-ignored** `.pii-denylist.local` at the repo root — never
  commit it. Run manually anytime: `python3 tooling/pii-scan.py [--range origin/main..HEAD]`.
  False positive? Add the safe substring to `ALLOW` in `pii-scan.py`.
- **The research is fact-checked.** `research/` claims were adversarially verified; don't add claims
  without a primary source, and preserve the "hedges / refuted claims" honesty.
- After changing `template/`, validate it by pointing the vault at the template (the scripts default
  `KB_VAULT` to `$KIT/_knowledge`, which doesn't exist in the kit — you must override it):
  `KB_VAULT="$PWD/template" python3 tooling/kb-lint.py && KB_VAULT="$PWD/template" python3 tooling/kb-links.py`.
  Both must exit 0. The unfilled `architecture.md` scaffold warns (fill-or-delete) rather than errors.

## Layout
`research/` = why · `template/` = the vault scaffold · `tooling/` = the scripts · `HOWTO.md` = the
build playbook. `README.md` is the human+agent entry point.
