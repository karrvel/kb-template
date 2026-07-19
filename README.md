# kb-template

A reusable kit for giving any project a **durable, agent-maintained knowledge base** — plain
markdown, git-versioned, two-tier memory. It's the thing that lets an AI coding agent *remember*
across sessions: the gotchas, decisions, security findings, and prod caveats that die with the
context window and that grep can never recover.

Distilled from a fact-checked research pass on agent memory (Karpathy's *LLM wiki* + MemGPT/Letta
two-tier memory) and battle-tested building real project vaults (~130 shards from ~1.1 GB of
Codex/Claude-Code transcripts). Measured impact: in a controlled A/B, an agent *with* the vault
surfaced the right project-specific fact **~100% vs ~31% without it** — see `tooling/kb-eval/`.

> **Reading this as an agent?** Jump to [For agents — initialization prompt](#for-agents--initialization-prompt).
> **Reading as a human?** Start with [Quick start](#quick-start-humans).

## What's here
```
kb-template/
├── research/     WHY  — the verified research on agent-memory design (portable to any project)
├── template/     WHAT — the vault scaffold to copy into a project as _knowledge/
├── tooling/      HOW  — the scripts: build, sync, lint, fix, link-check, staleness, impact-eval
│   ├── prefilter.py     transcripts → digests      kb-sync.py     shards → navigation + memory
│   ├── kb-lint.py       schema gate                kb-fix.py      Obsidian-safe frontmatter
│   ├── kb-links.py      link-rot gate              kb-staleness.py  the re-verify queue
│   ├── hooks/pre-commit the fix→lint→links gate    kb-eval/       measure KB impact (A/B)
└── HOWTO.md      the step-by-step playbook for building a vault from scratch
```

## The design in one picture
```
        Karpathy layer 1          Karpathy layer 2            Karpathy layer 3
        RAW SOURCES         →      THE WIKI (compiled)    ←   THE SCHEMA
   reference/, transcripts        _knowledge/ shards          README.md + CLAUDE.md

   MemGPT tiers:   CORE (always-loaded)  = MEMORY.md + CLAUDE.md LIVE blocks   (tiny, pointers)
                   ARCHIVAL (on-demand)  = the vault, browsed via INDEX.md     (all the detail)

   kb-sync.py compiles shard frontmatter → MOCs + INDEX + both memory tiers.
```
The one-line answer from the research: *build a two-tier plain-markdown wiki; skip vector RAG below
~150–200 pages / ~50–100k tokens.* The why is in [`research/`](research/README.md).

## Quick start (humans)
```bash
# 1. scaffold the vault + tooling into your project
cp -R  kb-template/template        /path/to/project/_knowledge
mkdir -p /path/to/project/_meta && cp kb-template/tooling/*.py /path/to/project/_meta/

# 2. edit _knowledge/README.md (replace {PROJECT} / TODO) and add the two LIVE markers to
#    your project-root CLAUDE.md (see HOWTO.md step 6)

# 3. build + gate + measure
cd /path/to/project
python3 _meta/kb-sync.py       # MOCs + INDEX + MEMORY.md + CLAUDE.md LIVE blocks
python3 _meta/kb-fix.py        # quote Obsidian-breaking frontmatter
python3 _meta/kb-lint.py       # schema gate
python3 _meta/kb-links.py      # broken-link gate
python3 _meta/kb-staleness.py  # what volatile knowledge is overdue for re-verification
```
Full method (incl. distilling a brownfield codebase + transcripts): **[HOWTO.md](HOWTO.md)**.
Tooling reference + the pre-commit hook install: **[tooling/README.md](tooling/README.md)**.

## For agents — initialization prompt

Give this prompt to an agent (Claude Code / Codex) **working inside the project you want to give a
knowledge base**. It handles empty/fresh *and* brownfield projects.

````text
Set up a durable, agent-maintained knowledge base in THIS project using the kb-template kit.

1. Clone the kit and copy its parts in (use SSH if the repo is private):
     git clone --depth 1 git@github.com:karrvel/kb-template.git /tmp/kb-template
     cp -R /tmp/kb-template/template ./_knowledge
     mkdir -p ./_meta && cp /tmp/kb-template/tooling/*.py ./_meta/
     mkdir -p ./.githooks && cp /tmp/kb-template/tooling/hooks/pre-commit ./.githooks/ \
       && chmod +x ./.githooks/pre-commit

2. Read /tmp/kb-template/HOWTO.md and ./_knowledge/README.md — that is the method and the schema.
   Follow them. Read /tmp/kb-template/research/README.md if you need the rationale.

3. Edit ./_knowledge/README.md: replace {PROJECT} and TODO markers with this project's name + date.

4. Ensure a project-root CLAUDE.md exists (create it if missing) with, at the top,
   "First action every session: read _knowledge/INDEX.md", and these two marker pairs:
     ### 🔴 LIVE — open security findings
     <!-- BEGIN:sync:live-security -->
     <!-- END:sync:live-security -->
     ### 🟠 LIVE — open work
     <!-- BEGIN:sync:open-work -->
     <!-- END:sync:open-work -->

5. Seed the vault according to what this project IS:
   • EMPTY / FRESH (little or no code yet): create a MINIMAL skeleton — an architecture.md stub, one
     repos/ shard per planned component, and decisions/ shards for choices already made. Keep it
     tiny; grow it as the project grows. Do NOT invent detail that doesn't exist yet.
   • BROWNFIELD (existing code): build the skeleton FIRST from existing docs (PRDs, READMEs,
     architecture docs) into reference/ + repos/ shards, VERIFYING every claim against the current
     code and correcting stale docs. THEN gap-fill from past agent transcripts with
     ./_meta/prefilter.py (HOWTO.md steps 2–5). Recency-weight; log what you skip — no silent caps.

6. Write ATOMIC shards (one fact each) with full frontmatter (see ./_knowledge/_SHARD_TEMPLATE.md):
   name, type, title, area, tags, status, updated, volatility, provenance. Tag volatility honestly
   (durable | decays-with-code | one-shot). Prefer 0 shards over noise. NEVER put secrets in the
   vault (tokens/keys → a secret manager). Verify load-bearing facts against code before enshrining.

7. Generate navigation + the two memory tiers, then gate quality:
     python3 ./_meta/kb-sync.py       # MOCs + INDEX + MEMORY.md + CLAUDE.md LIVE blocks
     python3 ./_meta/kb-fix.py        # make frontmatter Obsidian-safe
     python3 ./_meta/kb-lint.py       # schema gate (must pass)
     python3 ./_meta/kb-links.py      # broken-link gate (must pass)
     python3 ./_meta/kb-staleness.py  # the re-verify queue

8. If this project is a git repo, enable the pre-commit health gate:
     git config core.hooksPath .githooks

Then report: shards created per collection (gotchas/decisions/security/tasks/repos), what you
verified against code, and what you deliberately skipped. Keep the always-loaded core tiny (~30
items); push detail into the vault.
````

There is also an [`AGENTS.md`](AGENTS.md) at the repo root for agents that land *inside this kit*.

## Maintain
After editing shards, run the loop: `kb-sync → kb-fix → kb-lint → kb-links → kb-staleness`. Put
`kb-fix` + `kb-lint` + `kb-links` in a pre-commit hook (`tooling/hooks/pre-commit`); put
`kb-staleness` on a pre-session / weekly nudge — the `decays-with-code` re-verification is the rule
everyone skips. **Measuring whether it helps:** `tooling/kb-eval/` runs a with-KB vs without-KB A/B.

## Provenance
Research: a deep, fact-checked pass (98 agents, 80 falsifiable claims, 3-vote adversarial
verification, 21 sources). Method + tooling validated on real project vaults. Full audit trail in
[`research/claims-verified.md`](research/claims-verified.md). Impact measured in
[`tooling/kb-eval/`](tooling/kb-eval/README.md).

## Note on privacy
A knowledge vault is sensitive — it can catalog how to attack your own production. Keep real vaults
in **private** repos, never commit secrets, and treat `reference/` distillates as confidential. The
`kb-eval` harness keeps real, secret-bearing traps in a git-ignored `traps.local.jsonl`; only a
redacted `traps.jsonl` example is committed.
