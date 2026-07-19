---
title: Karpathy's "LLM Wiki" pattern — compile, don't re-derive
updated: 2026-07-05
provenance: Karpathy gist 442a6bf… (primary, verbatim-verified) + tweet 2039805659525644595 + secondaries
status: durable
---

# Karpathy's LLM Wiki pattern

**Primary source:** Andrej Karpathy, GitHub gist `karpathy/442a6bf555914893e9891c11519de94f`
("LLM Wiki", 2026-04-04), announced in tweet `2039805659525644595` (2026-04-02, "LLM Knowledge
Bases — Something I'm finding very useful recently: using LLMs to build personal knowledge bases for
various topics of research"). Verified verbatim via the raw gist endpoint and Twitter's syndication
CDN (multiple independent fetches).

## The core thesis (his framing)
- **The problem with query-time RAG:** the LLM is "rediscovering knowledge from scratch on every
  question. There's no accumulation."
- **The fix:** "the wiki is a persistent, compounding artifact" — "knowledge is compiled once" and
  "good answers can be filed back into the wiki." Cross-references and flagged contradictions
  accumulate across sessions.
- **Storage:** "The wiki is just a git repo of markdown files. You get version history, branching,
  and collaboration for free." Not a database, not a vector store.
- **Scope:** explicitly scoped to the **individual researcher** — single-curator, no multi-user
  merge/access-control concerns.

## The three layers (verbatim)
1. **Raw sources** — immutable originals (articles, papers, transcripts, notes, images).
2. **The wiki** — a directory of LLM-generated markdown: summaries, concept/entity pages,
   cross-references, a master `index.md`, and often a `log.md`.
3. **The schema** — "a document (e.g. `CLAUDE.md` for Claude Code or `AGENTS.md` for Codex) that
   tells the LLM how the wiki is structured" — i.e. editorial conventions, ingestion + maintenance
   workflows, conflict-resolution rules.

> ⚠️ Secondary retellings mangle layer 3 into "a JSON schema that defines the page universe."
> **Wrong** — verified against the gist: it is a **markdown** instruction doc, not JSON. This
> template's `template/README.md` + the project `CLAUDE.md` *are* layer 3.

## The compiler analogy — attribute carefully
Karpathy uses "compiled once" in passing. The fuller **"RAG = interpreted execution vs wiki =
compiled execution"** framing (every query re-parses raw sources at runtime; the wiki is compiled
ahead of time) is from a **secondary** source (particula.tech), not the gist. Other secondaries push
it further ("Obsidian is the IDE, the LLM is the programmer, the wiki is the codebase"). Useful
intuition — just don't attribute the strong version to Karpathy.

## The maintenance loop (from practitioner implementations)
A cyclical, agent-run loop (dair.ai's "Wiki Builder" Claude Code plugin operationalizes it):
1. **Ingest** — drop raw material into `raw/`.
2. **Compile** — the LLM synthesizes index files + concept articles and maintains the link graph.
3. **Query & Enhance** — browse/ask; **file answers back** into the wiki (`wiki/questions/`), so
   explorations compound rather than being discarded.
4. **Lint & Maintain** — detect thin pages, missing backlinks, uncompiled notes; suggest new
   articles. The upkeep is delegated to the agent, not the human.

## The honest limits
- ❌ Do not claim the wiki "**beats RAG**" categorically or that "**RAG never retains** synthesized
  knowledge." That's a strawman of naive vector RAG — GraphRAG/RAPTOR persist synthesized summaries
  at index time. The wiki is the better *fit at small/personal scale*. (See [[plain-markdown-vs-vector-rag]].)
- **Scale ceiling:** the pattern is a fit up to ~**50k–100k tokens / ~150–200 pages**. Above it,
  add semantic search.

## Why we adopt it
It is empirically validated by real project vaults (461 MB of transcripts → a working plain-markdown
wiki; and ~1.1 GB → ~130 shards on another). The pattern maps cleanly onto Claude Code's
existing `CLAUDE.md` + auto-memory machinery — no new infrastructure.
