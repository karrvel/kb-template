---
title: Plain markdown vs vector/graph RAG — when do you actually need embeddings?
updated: 2026-07-05
provenance: deep-research 2026-07-05 — benchmark + scale claims, verified
status: durable
---

# When do you actually need a vector database?

The decision this whole template rests on. Short answer: **not until you outgrow ~150–200 pages /
~50–100k tokens.** Below that line, plain files + an index + the context window win on reliability,
cost, and maintainability. Above it, add semantic/graph retrieval.

## The scale ceiling (concrete numbers)
- **~50k–100k tokens / ~150–200 pages** is the repeatedly-cited sweet spot for plain files. Below
  it, file-reading is "simpler, more reliable, and cheaper" than RAG; only above it does semantic
  search become necessary.
- **If the working set fits in context, retrieval reliability ≈ 100%** — versus RAG's dependence on
  embedding quality, chunking, and top-k. No chunk-boundary misses, no embedding drift.
- **"No vector DB needed at ~100 articles (~400k words)"** — index files + context window suffice
  (dair.ai / Elvis Saravia). Karpathy scoped his pattern to a single researcher for the same reason.

## Benchmarks: simple is competitive
- **Letta's plain-filesystem memory: 74% on LoCoMo** vs vector-based **Mem0: 68.5%**. "Simple
  filesystems beat complex retrieval pipelines" at this scale.
- **The extraction-vs-verbatim gap is collapsing:** Mem0's Apr-2026 algorithm jumped LongMemEval
  from ~49% → **93.4%**. A heavyweight extraction/spatial pipeline is *not* required for competitive
  recall — weakening any "you must use our fancy memory system" pitch.

## Context rot: bigger windows don't fix memory
- **Claude Sonnet 4: 99% → 50%** accuracy on basic tasks as input length grows. Larger context
  windows *delay* the memory problem; they don't solve it. This is why you curate a small
  always-loaded tier rather than dumping everything in.
- Corollary: **cap the always-loaded memory file (~30 items, prune regularly).** A focused 30-item
  file beats a sprawling 300-item one.

## Where the honesty line is (do NOT overclaim)
The refuted claims from verification, kept here so we don't repeat them:
- ❌ **"RAG never retains synthesized knowledge / every query restarts from zero."** False as stated.
  Advanced RAG persists synthesized knowledge at index time:
  - **Microsoft GraphRAG** — clusters entities into communities with **pre-computed summaries**.
  - **RAPTOR** — builds a **recursive tree of LLM summaries** reused at query time.
  The markdown wiki wins on *fit at small scale and human-legibility*, not on a categorical
  impossibility of RAG.
- ⚠️ **Temporal knowledge graphs** genuinely add something vectors can't: representing how facts
  change over time (validity/supersession). On LongMemEval, temporal-graph **Zep 63.8%** vs
  vector **Mem0 49.0%** (~15 pts). If your domain is heavily time-varying and large, a graph may
  earn its keep — but that's above this template's target scale.

## Decision rule
```
KB fits in ≲ 150–200 pages / ≲ 50–100k tokens, single-curator, human-legible?
   → plain-markdown two-tier wiki (this template). No embeddings.
KB is large, multi-tenant, or heavily time-varying, with fuzzy semantic recall needs?
   → add vector (GraphRAG/RAPTOR) or temporal-graph (Zep) retrieval ON TOP of the wiki,
     not instead of it. The wiki stays the human-legible source of truth.
```
The vault is the compiled artifact either way; vectors, if ever added, are an index over it — not a
replacement for it.
