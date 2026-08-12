# HOWTO — build a knowledge base for any project

The step-by-step method used to build a real project vault (~130 shards distilled from ~1.1 GB of
agent transcripts). Reusable for any project. The *why* is in `research/`; this is the *how*.

## 0. Decide it's the right tool (30 seconds)
Plain-markdown two-tier wiki is the right call when the KB is **single-curator** and fits in
**≲ 150–200 pages / ≲ 50–100k tokens**. Larger / multi-tenant / heavily time-varying → still build
the wiki, but plan to add vector or graph retrieval *on top* later. See
`research/plain-markdown-vs-vector-rag.md`.

## 1. Scaffold the vault
```bash
cp -R ~/Projects/kb-template/template  /path/to/project/_knowledge
cp ~/Projects/kb-template/tooling/*.py /path/to/project/_meta/   # or ./tooling
```
Edit `_knowledge/README.md`: replace `{PROJECT}` and `TODO`. Add the two LIVE sync-block markers to
your project-root `CLAUDE.md` (see step 6).

## 2. Gather the raw sources (Karpathy layer 1)
Two kinds, both high-value:
- **Already-distilled docs** — PRDs, architecture docs, prior codebase analyses, per-component
  distillates. Copy them into `_knowledge/reference/`. **These are your skeleton backbone** — far
  higher signal-per-token than raw transcripts. Build the skeleton from these first.
- **Agent transcripts** — Codex (`~/.codex/sessions`) + Claude Code (`~/.claude/projects`). These
  *fill gaps* (gotchas, decisions, security findings, remaining work) the docs don't have.

## 3. Pre-filter the transcripts (cheap, no LLM tokens)
```bash
python3 tooling/prefilter.py --match <project-keyword> --out ./digests
```
Strips ~95–98% tool-call noise → provenance-tagged per-session digests, bucketed by cwd. Prints a
size table. **Measure before you fan out.**

## 4. Distill — skeleton first, then gap-fill (fan-out)
- **Skeleton (from `reference/`):** one agent per repo/component writes a `repos/<name>.md` shard;
  one writes `architecture.md`; one seeds `security/` + `decisions/` + `tasks/`. **Have agents
  verify against current code and correct stale doc claims.**
- **Gap-fill (from digests):** chunk the digests (~300–400 KB each), fan out one extractor agent per
  chunk returning structured items `{type, area, title, body, volatility, provenance, confidence}`,
  then one synthesis agent per collection dedupes/merges and writes atomic shards — **reading the
  existing skeleton shards first so it doesn't duplicate them.**
- **Recency-weight.** Fully distill recent sessions; skip/sample old analysis runs whose output is
  already in `reference/`. **Log what you skip — no silent caps.**
- Use cheaper models (e.g. Sonnet, not the frontier tier) for the fan-out — it's the token-dominant
  part. Reserve the strong model for hard verify/judge stages.

## 5. Verify the load-bearing claims (don't enshrine fiction)
Spot-check the striking findings against current code (a claimed backdoor, a "system of record", a
port). The distillation *will* surface real, non-obvious things — but confirm before they land in
the always-loaded tier.

## 6. Wire the two tiers + generate navigation
Add to your project-root `CLAUDE.md`:
```markdown
### 🔴 LIVE — open security findings
<!-- BEGIN:sync:live-security -->
<!-- END:sync:live-security -->
### 🟠 LIVE — open work
<!-- BEGIN:sync:open-work -->
<!-- END:sync:open-work -->
```
Then:
```bash
python3 _meta/kb-sync.py     # generates MOCs + INDEX.md + MEMORY.md + fills the CLAUDE.md blocks
```

### Install the hook (required once per clone)
```bash
# 1. Copy the hook into your project's .githooks/ dir:
cp ~/Projects/kb-template/repos/kb-template/tooling/hooks/pre-commit /path/to/project/.githooks/pre-commit
chmod +x /path/to/project/.githooks/pre-commit
# 2. Tell git to use that dir (required once per clone):
git config core.hooksPath .githooks
```
The hook runs kb-fix → kb-lint → kb-links → kb-sync --check whenever `_knowledge/*.md` files are staged. There is no `init.sh` in the kit; run the two commands above manually after each clone.

### Loading semantics (verified against Claude Code docs) {#loading-semantics}
- **`CLAUDE.md` loads hierarchically** — from cwd *up* the tree. A workspace-root `CLAUDE.md` loads
  even when you start a session inside a subdir/repo. → the LIVE sync blocks reach per-repo work.
- **Auto-memory (`MEMORY.md`) is git-repo-keyed**, shared across a repo's subdirs/worktrees but
  **not** across sibling repos. So a workspace-root `MEMORY.md` auto-loads only for root sessions;
  the `CLAUDE.md` LIVE blocks are what reach the individual repos. (This is why we mirror the LIVE
  tier into `CLAUDE.md`, not only `MEMORY.md`.)
- HTML comments (`<!-- … -->`) are stripped from `CLAUDE.md` before it enters context, so the
  `BEGIN/END:sync` markers cost nothing and the content between two markers still loads.

## 7. Maintain
The loop after editing shards (see `tooling/README.md`):
```bash
python3 _meta/kb-sync.py       # regenerate MOCs + INDEX + MEMORY.md + CLAUDE.md LIVE blocks
python3 _meta/kb-fix.py        # quote frontmatter values that break Obsidian's strict YAML
python3 _meta/kb-lint.py       # gate: schema valid + no dialect drift + no Obsidian-breakers
python3 _meta/kb-links.py      # gate: broken [[wikilinks]] / dead file refs
python3 _meta/kb-staleness.py  # the re-verify queue: volatile shards overdue for a code re-check
```
Append to `log.md` per session. Cap the always-loaded core (~30 items). Keep the taxonomy flat.
**The rule everyone skips is `decays-with-code` re-verification — so `kb-staleness.py` exists to make
that backlog visible; wire it into a pre-session or weekly nudge, and `kb-fix` + `kb-lint` +
`kb-sync.py --check` into a pre-commit hook.** Put the volatility discipline on a timer, not on willpower.

**Browse it as a database:** the scaffold ships `knowledge-map.base` — open the vault in Obsidian
(1.7+) for filtered table views per `type`. It's purely additive: Obsidian users get the view layer,
everyone else ignores one file, and the plain-markdown core stays greppable/diff-able.

## Drift smells to avoid (harvested from 5 real vaults)
- **Never hand-write counts or totals** in INDEX/CLAUDE.md — `kb-sync.py` owns them. Hand-written
  "173 shards" goes stale the next commit. `kb-sync.py --check` (wired into the hook) warns when any
  generated file drifts from the shards.
- **Don't leave `updated:` unset** — the kit stamps today's date by default; only override `KB_TODAY`
  for reproducible builds. An `updated: unset` INDEX is a young-vault tell that kills the freshness signal.
- **`KB_SKIP_LINT=1` invites dialect drift** — once the schema gate is off, frontmatter forks into
  incompatible dialects (as one mature vault did). Keep lint on unless you've deliberately left the
  template schema.
- **For `decays-with-code`, git-anchor provenance** — `verified vs main@<sha> DATE` — so re-verification
  can diff against the exact code state, not just a date.

## Gotchas from building a real vault (from ~1.1 GB of transcripts)
- **UUIDv7 session ids share date-ordered prefixes** — hash the *source path* for digest filenames,
  not `id[:8]`, or ~half your sessions silently overwrite each other.
- **Codex and Claude Code JSONL schemas differ** — Codex: `response_item.payload.message`; Claude:
  top-level `type:user/assistant`, `message.content[]`. `prefilter.py` handles both.
- **The giant transcripts are often codebase-analysis runs** whose output already exists as
  distillates — detect (they open with an `AGENTS.md`/analysis preamble) and skip them.
- **A workflow can die mid-synthesis** and only journal some return values — check the on-disk
  result (shard counts, dedup ratios) before assuming it failed or re-running (re-running can
  duplicate).
