---
title: Agent memory for coding agents — the landscape, and what to build
updated: 2026-07-05
provenance: deep-research pass 2026-07-05 (80 claims, 68 verified / 7 refuted, 21 sources)
status: durable
---

# Agent memory — the landscape (and the design this template implements)

A portable synthesis of a deep, fact-checked research pass on how to give AI coding agents
(Claude Code / Codex) durable memory. Every load-bearing claim here was adversarially verified
against primary sources; the ones that **failed** verification are recorded in
[[mempalace-and-what-not-to-adopt]] and the "hedges" below so nobody repeats them.

Deep dives: [[karpathy-llm-wiki]] · [[memgpt-letta-tiered-memory]] · [[plain-markdown-vs-vector-rag]] ·
[[mempalace-and-what-not-to-adopt]] · [[claims-verified]] · [[sources]].

## The one-paragraph answer
Build a **two-tier, plain-markdown, git-versioned wiki**, maintained by the agent, governed by a
schema doc (`CLAUDE.md`/`AGENTS.md`). A tiny **always-loaded core** (pointers + LIVE state) sits on
top of a larger **browse-on-demand vault**. At the scale a single project or researcher operates
(≲ 150–200 pages / ≲ 50–100k tokens), **you do not need a vector database** — index files + the
context window are enough, and embeddings are curation tax. Reach for vector/graph retrieval only
above that ceiling.

## Two converging lineages
The research found two independent bodies of work that point at the *same* design:

1. **Karpathy's "LLM Wiki" (Apr 2026)** — the *compile-don't-re-derive* idea. Raw sources are
   "compiled" once by the LLM into a persistent markdown wiki that compounds across sessions,
   instead of RAG re-deriving from raw docs on every query. Three layers: raw sources → wiki →
   a schema doc (`CLAUDE.md`/`AGENTS.md`). Plain markdown in a git repo. See [[karpathy-llm-wiki]].

2. **MemGPT / Letta (2023 →)** — the *tiered memory* idea, framed as an OS managing virtual memory:
   a small always-in-context **core memory** the agent self-edits, plus **archival memory** paged
   in on demand. The agent is an active memory *manager*, not a passive RAG recipient.
   See [[memgpt-letta-tiered-memory]].

This template fuses them: Karpathy's wiki *is* the archival tier; a small `MEMORY.md` (+ hierarchical
`CLAUDE.md` blocks) *is* the core tier; the schema doc is layer 3.

**A third arrival (added 2026-08-27).** [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory)
(MIT, v2.0.1) credits Karpathy's gist directly, by name, as the inspiration for its Wiki layer — and
independently reproduces the tiered model as a four-level pyramid (L0 Conversation → L1 Atom →
L2 Scenario → L3 Persona) under an explicit rule, *"lower layers preserve evidence; upper layers
preserve structure"*, which is the compiled/raw split in different words. Different scale (team
server, SQLite + sqlite-vec or a hosted vector DB), same design. Convergence from a third direction
is the strongest evidence this corpus has that the shape is right.

It also **omits** decay and staleness handling entirely — consolidation distils upward, but
`capture.l0l1RetentionDays: 0` ("never clean up") is the shipped default. That is the gap flagged
under "hedges" below and the reason `tooling/` exists. See [[agent-context-management]] for that
analysis and for the in-session half of the problem.

## Why plain markdown beats reaching for vectors (at this scale)
- **A scale ceiling exists and is concrete.** Multiple practitioners put the plain-file sweet spot
  at **~50k–100k tokens / ~150–200 pages**; below it, file-reading is "simpler, more reliable, and
  cheaper" than a RAG pipeline. If the working set fits in context, retrieval reliability is
  effectively 100% vs RAG's chunking/embedding/top-k lottery. (Karpathy scoped the pattern to
  *individual researchers* / single-curator.)
- **"No vector DB needed at ~100 articles"** — at personal-KB scale, index files + context window
  suffice for retrieval (dair.ai / Elvis Saravia).
- **Simple filesystems are competitive on benchmarks.** Letta's plain-filesystem memory scored
  **74% on LoCoMo vs Mem0's 68.5%**; and verbatim-store approaches are closing the gap fast
  (Mem0's Apr-2026 algorithm jumped LongMemEval ~49% → 93.4%) — so a heavyweight extraction/spatial
  pipeline is *not* required for competitive recall.
- **Markdown stays diff-able, greppable, human-editable, and git-versioned** — an embedding store is
  none of these.

## Why "small and curated" beats "dump everything"
- **Context rot is measurable.** Claude Sonnet 4 fell from **99% → 50%** accuracy on basic tasks as
  input length grew. Bigger context windows *delay* the memory problem, they don't solve it — so
  stuffing everything in-context (or RAG-injecting lots) degrades quality.
- **Cap the always-loaded tier hard.** Practitioners cap agent memory files at **~30 items** with
  regular pruning; a focused 30-item file beats a sprawling 300-item one. Keep the core tier tiny;
  push detail to the on-demand vault.
- **Hierarchical loading is a feature.** Root-level memory applies everywhere; subdirectory files
  load only when the agent works in that directory (Claude Code's directory-based `CLAUDE.md`
  discovery). Use it to scope detail. → see [[../HOWTO#loading-semantics]].

## The hedges (claims that FAILED verification — do not repeat)
- ❌ **"The wiki BEATS RAG / RAG never retains synthesized knowledge / every query restarts from
  zero."** This is a strawman of *naive* vector RAG. Advanced RAG (Microsoft **GraphRAG** community
  summaries, **RAPTOR** recursive summary trees) *does* synthesize and persist knowledge at index
  time. Correct framing: a compiled markdown wiki is the *better fit* at project/personal scale —
  **not** a categorical win over all RAG.
- ❌ **"Layer 3 is a JSON schema that defines the page universe."** Karpathy's own gist says layer 3
  is "a document (e.g. `CLAUDE.md` for Claude Code or `AGENTS.md` for Codex)" — a **markdown**
  instruction file, not JSON.
- ❌ **The strong "compiler analogy" as Karpathy's own words.** He uses "compiled once" in passing;
  the full interpreted-vs-compiled framing is *secondary* elaboration (particula.tech), not the
  gist. Attribute it accordingly.
- ⚠️ **MemPalace's "47k stars / lossless 30x / method-of-loci" claims** — the spatial metaphor adds
  nothing over vector metadata filtering; see [[mempalace-and-what-not-to-adopt]].

## What this template gives you
- `research/` — this synthesis + the verified claim set + sources (portable to any project).
- `template/` — the vault scaffold (schema, dirs, stubs) to copy into a new project's `_knowledge/`.
- `tooling/` — `prefilter.py` (distill Codex+Claude transcripts → digests) and `kb-sync.py`
  (generate the navigation MOCs + INDEX + the two memory tiers from shard frontmatter).
- `../HOWTO.md` — the step-by-step method used to build a real vault from ~1.1 GB of transcripts.
