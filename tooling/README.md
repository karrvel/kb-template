# tooling

Portable scripts (stdlib Python 3 only — no deps). Copy the ones you use into your project's `_meta/`.

## The maintenance loop (run in this order after editing shards)
```bash
python3 _meta/kb-sync.py       # 1. regenerate MOCs + INDEX + MEMORY.md + CLAUDE.md LIVE blocks
python3 _meta/kb-fix.py        # 2. make frontmatter Obsidian-safe (quote hazardous values)
python3 _meta/kb-lint.py       # 3. gate: schema valid? (exit 1 on error)  — CI / pre-commit
python3 _meta/kb-links.py      # 4. gate: broken [[wikilinks]] / dead file refs? — CI / pre-commit
python3 _meta/kb-staleness.py  # 5. what volatile knowledge is overdue for re-verification?
```
`kb-fix`, `kb-lint --check`, and `kb-links` are the three you want in a pre-commit hook; `kb-staleness`
is the one you want in a pre-session / weekly nudge — it surfaces the `decays-with-code` backlog
everyone skips. **Measuring impact** (does the KB change what the agent does): see `kb-eval/`.

### Pre-commit hook (git vaults)
A ready hook lives at `hooks/pre-commit`. It fires only when `_knowledge/*.md` is staged, then:
kb-fix (auto-quotes Obsidian-breakers + re-stages), kb-lint (blocks on schema errors), kb-links
(blocks on broken internal links). Install (one-time, per clone):
```bash
cp kb-template/tooling/*.py       /path/to/project/_meta/
mkdir -p /path/to/project/.githooks
cp kb-template/tooling/hooks/pre-commit /path/to/project/.githooks/
chmod +x /path/to/project/.githooks/pre-commit
git -C /path/to/project config core.hooksPath .githooks
```
The hook reads scripts from `_meta/` and finds the repo root itself, so it's project-agnostic.
Bypass a single commit with `git commit --no-verify`. (Needs a git repo — a plain-folder vault has
no commit to gate; run the loop manually there.)

**Advisory variant** (`hooks/pre-commit-advisory`): for a vault with pre-existing rot you haven't
cleaned yet, this auto-fixes Obsidian frontmatter but only *reports* lint/link counts — it never
blocks. Swap in the hard `pre-commit` once the vault is clean. It sources `.githooks/kb.env` if
present, so per-repo settings live there — e.g. `KB_VOLATILITY="durable,decays-with-code,decays-with-prs,one-shot"`
for a non-standard dialect, or `KB_SKIP_LINT=1` for a vault that predates this frontmatter schema.

**Versioning only the vault** (workspace has nested git repos or secrets in `_meta/`): `git init` at
the workspace root, then a whitelist `.gitignore` that tracks only the vault:
```gitignore
/*
!/.gitignore
!/.githooks/
!/_knowledge/
!/CLAUDE.md
_knowledge/.obsidian/
```
This keeps `_meta/` (secret backups), `repos/` (nested repos), and heavy dirs untracked while
versioning the knowledge. Verify with `git diff --cached --name-only` that nothing sensitive is
staged before the first commit.

---

## prefilter.py — transcripts → digests
Distills Codex + Claude Code JSONL transcripts into compact, provenance-tagged per-session digests
(strips ~95–98% tool-call noise). Handles both schemas; buckets by cwd.
```bash
python3 prefilter.py --match <project-keyword> --out ./digests
# optional: --buckets "backend=api,web=frontend"  --codex ~/.codex/sessions  --claude ~/.claude/projects
```

## kb-sync.py — shards → navigation + memory
Regenerates the MOC index files, `INDEX.md`, the always-loaded `MEMORY.md`, and the `CLAUDE.md`
LIVE sync blocks, from shard frontmatter. Idempotent.
```bash
python3 kb-sync.py
KB_ROOT=/path/to/project KB_PROJECT=myproj KB_TODAY=2026-07-05 python3 kb-sync.py
```
Env: `KB_ROOT`, `KB_VAULT`, `KB_MEMORY_DIR`, `KB_PROJECT`, `KB_TODAY`, `KB_AREAS`. Requires the two
`<!-- BEGIN:sync:live-security -->…` / `open-work` marker pairs in the project-root `CLAUDE.md`.

## kb-lint.py — enforce the schema (so a vault can't drift into dialects)
Validates every shard's frontmatter: required fields present; `type`/`status`/`volatility` values
canonical (catches `decays-with-prs` vs `decays-with-code`, off-schema `done`/`complete`); dates
well-formed; names unique + kebab-case; no unfilled template placeholders; **and no unquoted values
that break Obsidian's YAML** (see `kb-fix`). Exit 1 on any ERROR — wire into pre-commit / CI.
```bash
python3 kb-lint.py                                            # report + gate
KB_STRICT=1 python3 kb-lint.py                                # warnings fail too
KB_VOLATILITY=durable,decays-with-code,decays-with-prs,one-shot python3 kb-lint.py   # allow a dialect
```
Env: `KB_ROOT`, `KB_VAULT`, `KB_VOLATILITY`, `KB_STATUS`, `KB_TYPES`, `KB_MAX_LINES`, `KB_STRICT`.

## kb-fix.py — repair Obsidian-breaking frontmatter
Obsidian's Properties parser is strict YAML; it errors ("mapping values are not allowed here") when a
value is an **unquoted scalar containing `: `, a leading reserved char (`@ ! & * ? | > % # , [ {` `` ` ``),
or ` #`** — which creep in constantly via `provenance:`/`title:` (`Path: /Users/...`, `Trigger #2`,
`title: Repo: orgn`). This double-quotes exactly those values (escaped), leaving everything else
byte-for-byte. Idempotent; run it after `kb-sync` / on save.
```bash
python3 kb-fix.py                # repair in place
python3 kb-fix.py --dry-run      # preview, write nothing
python3 kb-fix.py --check        # exit 1 if anything needs fixing (CI / pre-commit)
```
Env: `KB_ROOT`, `KB_VAULT`.

## kb-links.py — link-rot checker
The non-LLM doc-health signal that has no off-the-shelf tool for a markdown vault. Flags broken
`[[wikilinks]]` (a shard linking to a target that doesn't exist — classic forward-ref rot),
dead local file references, and optionally dead external URLs. Resolves wikilinks the Obsidian way
(by basename; `[[dir/foo]]`, `[[foo.md]]`, `[[foo|alias]]`, `[[foo#anchor]]` all → `foo`). Exit 1 on
broken internal links → pre-commit / CI.
```bash
python3 kb-links.py            # internal links only (fast, offline)
python3 kb-links.py --urls     # also HEAD-check external URLs (slow, network; advisory-only)
```
Env: `KB_ROOT`, `KB_VAULT`.

## kb-staleness.py — the re-verify queue
Surfaces the one discipline every vault skips: volatile (`decays-*`) shards whose `updated:` is older
than the threshold (they must be re-checked against code before an agent trusts them), plus
backtick-quoted source paths that no longer exist under `repos/` (code that moved out from under a
shard). Read-only.
```bash
python3 kb-staleness.py                          # report the backlog, newest-overdue last
KB_STALE_DAYS=7 python3 kb-staleness.py --fail-on-stale   # gate a pre-session hook
python3 kb-staleness.py --age-only               # skip the anchor check
```
Env: `KB_ROOT`, `KB_VAULT`, `KB_REPOS`, `KB_STALE_DAYS`, `KB_TODAY`. A project with a GitHub-PR
convention can layer a `gh pr view` drift check on top in its own `_meta/`.
