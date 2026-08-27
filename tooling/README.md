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
`kb-fix`, `kb-lint`, and `kb-links` are the three *gates* you want in a pre-commit hook (the shipped
hook adds `kb-sync --check` as a fourth, advisory stage); `kb-staleness`
is the one you want in a pre-session / weekly nudge — it surfaces the `decays-with-code` backlog
everyone skips. **Measuring impact** (does the KB change what the agent does): see `kb-eval/`.

### Pre-commit hook (git vaults)
A ready hook lives at `hooks/pre-commit`. It fires only when `_knowledge/*.md` is staged, then runs
four stages: kb-fix (auto-quotes Obsidian-breakers + re-stages), kb-lint (blocks on schema errors),
kb-links (blocks on broken internal links), and kb-sync `--check` (advisory — warns, never blocks,
when the generated nav/MOCs/INDEX have drifted from the shards). Install (one-time, per clone):
```bash
cp kb-template/tooling/*.py kb-template/tooling/*.sh   /path/to/project/_meta/
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
present, so per-repo settings live there — e.g. `export KB_VOLATILITY="durable,decays-with-code,decays-with-prs,one-shot"`
for a non-standard dialect, or `KB_SKIP_LINT=1` for a vault that predates this frontmatter schema.

> **`export` in `kb.env`, or the setting is silently ignored.** The hook *sources* `kb.env` into its
> own shell and then runs the Python scripts as **child processes** — a variable set without `export`
> never reaches them. Symptom: the gate rejects the exact value your config file permits. So every
> `KB_*` var read by the **Python** scripts must be exported: `KB_ROOT`, `KB_VAULT`, `KB_PLATFORMS`,
> `KB_VOLATILITY`, `KB_STATUS`, `KB_TYPES`, `KB_MAX_LINES`, `KB_STRICT`, `KB_STALE_DAYS`, `KB_AREAS`,
> `KB_PROJECT`, `KB_TODAY`, `KB_MEMORY_DIR`, `KB_REPOS`. Vars the hook's own **shell** reads
> (`KB_SKIP_LINT`, `KB_CODE_PATHS`, `KB_META`) work either way — exporting them too is harmless, so
> `export` everything in `kb.env` is the habit that can't bite you.

**Versioning only the vault** (workspace has nested git repos or secrets in `_meta/`): `git init` at
the workspace root, then drop in the ready whitelist — it tracks the vault, its wiring, and the
generated agent-context files, and nothing else:
```bash
cp kb-template/setup/workspace.gitignore /path/to/workspace/.gitignore
```
[`setup/workspace.gitignore`](../setup/workspace.gitignore) is the canonical list — it isn't
restated here so the two can't drift. This keeps `_meta/` (secret backups), `repos/` (nested repos),
and heavy dirs untracked while versioning the knowledge. Verify with `git diff --cached --name-only`
that nothing sensitive is staged before the first commit.

---

## prefilter.py — transcripts → digests
Distills Codex + Claude Code JSONL transcripts into compact, provenance-tagged per-session digests
(strips ~95–98% tool-call noise). Handles both schemas; buckets by cwd.
```bash
python3 prefilter.py --match <project-keyword> --out ./digests
# optional: --buckets "backend=api,web=frontend"  --codex ~/.codex/sessions  --claude ~/.claude/projects
```

## kb-sync.py — shards → navigation + memory
Regenerates the MOC index files, `INDEX.md`, the always-loaded `MEMORY.md`, the `CLAUDE.md`
LIVE sync blocks, and the per-platform context files (see `KB_PLATFORMS`), from shard frontmatter.
Idempotent.
```bash
python3 kb-sync.py
KB_ROOT=/path/to/project KB_PROJECT=myproj KB_TODAY=2026-07-05 python3 kb-sync.py
```
Env: `KB_ROOT`, `KB_VAULT`, `KB_MEMORY_DIR`, `KB_PROJECT`, `KB_TODAY`, `KB_AREAS`, `KB_PLATFORMS`.
`KB_PLATFORMS` (comma-separated; default `claude,codex,gemini,cursor`) picks which context files get
generated — `claude` → `MEMORY.md` + the `CLAUDE.md` LIVE blocks · `codex` → `AGENTS.md` (also read
by Antigravity) · `gemini` → `GEMINI.md` · `cursor` → `.cursor/rules/kb-context.mdc`. The `CLAUDE.md`
LIVE blocks need the two `<!-- BEGIN:sync:live-security -->…` / `open-work` marker pairs in the
project-root `CLAUDE.md`; if there's no `CLAUDE.md` at all, kb-sync **warns** and moves on.

**Collision guard.** For the three project-root files it generates — `AGENTS.md`, `GEMINI.md`,
`.cursor/rules/kb-context.mdc` — kb-sync refuses to overwrite a file that already exists but was
**not** generated by it (i.e. doesn't contain `generated by kb-sync.py`). It prints a warning naming
the file, tells you to remove/rename it or drop that platform from `KB_PLATFORMS`, skips it, and
continues with the rest (exit code stays 0). A hand-written `AGENTS.md` is never clobbered.
`MEMORY.md`, `INDEX.md`, and the MOCs are unaffected.

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

## kb-session-start.sh — the cold-start orientation print
POSIX `sh`, no Python: prints every **active** gotcha (`[[name]] — title`, skipping `resolved` /
`superseded`) plus the open tasks, so a fresh session sees the traps before it touches code. Cheap
enough to run every session.
```bash
sh _meta/kb-session-start.sh                       # run it
KB_VAULT=/path/to/_knowledge sh _meta/kb-session-start.sh
```
Env: `KB_VAULT` (default `$repo-root/_knowledge`). Install it alongside the Python scripts — the
`cp` above copies `tooling/*.sh` too — then wire it wherever your agent reads a first action (a
`SessionStart` hook, or a "First action every session" line in `CLAUDE.md` / `AGENTS.md`).
Note `kb-update.py` only refreshes `*.py`, so re-copy this one by hand when you pull a new kit.

## pii-scan.py — mechanical private-context guard (for a repo that goes public)
A fixed list of codified regexes — session URLs, `/Users/…` home paths, emails, private keys, AWS /
GitHub / OpenAI-style tokens — over tracked file **contents**, **commit messages** in a range, or the
**staged** diff. Exits 1 on any match, so it can gate a push. Project-specific literals belong in a
gitignored local denylist (`.pii-denylist.local` at the repo root, or `--denylist` / `$PII_DENYLIST`)
— never committed.
```bash
python3 tooling/pii-scan.py                             # all tracked files
python3 tooling/pii-scan.py --staged                    # staged additions (pre-commit)
python3 tooling/pii-scan.py --range origin/main..HEAD   # + the commit messages you're about to push
```
Exit 0 = clean, 1 = matches, 2 = aborted because a `git` command failed (e.g. an invalid `--range`)
— it fails closed, so a 2 is never "clean". `hooks/pre-push` runs it automatically over the tree
*and* the commits being pushed (history is permanent once public). In a clone of this kit:
```bash
git config core.hooksPath tooling/hooks      # per clone; bypass once with git push --no-verify
```
To use it in a project that already points `core.hooksPath` at `.githooks/`, copy `hooks/pre-push`
there (`chmod +x`) alongside the KB `pre-commit` — and note it resolves the scanner at
`<repo-root>/tooling/pii-scan.py` and **exits 0 silently if that file is missing**, so put the script
there (or edit the `SCAN=` line to wherever you keep it) or the guard won't actually run.

## kb-update.py — pull new kit versions

Updates the `*.py` scripts in `_meta/` to the latest version from the public repo. Never touches
`_knowledge/`. Writes a `kb.version` pin file after each successful update.

```bash
python3 kb-update.py          # interactive — colored diff per file, [y]es/[n]o/[a]ll/[q]uit
python3 kb-update.py --yes    # silent — prints warning + 8-second countdown, then overwrites
python3 kb-update.py --check  # dry-run — show what would change, exit 1 if updates exist
```

> **Silent mode warning.** New scripts can change how secrets and paths are handled. Run
> interactive at least once on a new version before using `--yes` in automation.
