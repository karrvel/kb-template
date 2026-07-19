---
title: MemGPT / Letta — tiered memory (core vs archival), the OS analogy
updated: 2026-07-05
provenance: MemGPT paper arXiv 2310.08560 (primary) + Letta blog/docs + DeepLearning.AI course
status: durable
---

# MemGPT / Letta — the two-tier memory model

**Primary sources:** MemGPT paper — *"Towards LLMs as Operating Systems"*, Charles Packer &
Sarah Wooders et al., **arXiv 2310.08560** (2023). Letta blog `letta.com/blog/agent-memory`
(2025-07-07); Letta docs; DeepLearning.AI × Letta course "LLMs as Operating Systems: Agent Memory".

## The idea
Treat the LLM context window like **OS virtual memory**: a fixed, constrained resource (RAM) plus
external storage (disk), paging information in and out to give an *illusion of unlimited memory*
within fixed context limits.

- **Core memory** — always in-context. Small, structured **memory blocks** (label + description +
  value + character limit) holding the agent's persona and key facts about the current user/task.
  The agent **self-edits** these by rewriting specific blocks (`core_memory_append` /
  `core_memory_replace`).
- **Archival memory** — external, searchable store the agent writes to and pages in **on demand**
  via explicit tool calls (`archival_memory_insert` / `archival_memory_search`).
- **(Letta adds) Recall memory** — full conversation history in a searchable DB, decoupling
  long-term recall from the context window.

MemGPT's "main context" = system instructions + writable core-memory blocks + a FIFO conversation
queue; "external context" = everything paged out.

## The load-bearing principle for us
> **"Retrieval (or RAG) is a tool for agent memory — it is not 'memory' in of itself."** (Letta)

The agent is an **active memory manager**: it decides what moves between the always-loaded and
on-demand tiers, via tool calls — *not* a passive recipient of whatever a retrieval pipeline
injects. This is the argument for a **curated, agent-managed** memory over automatic RAG injection.

## Why tiers instead of just a bigger window
- Compute/memory cost scales **quadratically** with context length.
- Longer windows show **diminishing returns** — models can't effectively use the extra context
  ("context rot": Claude Sonnet 4 dropped 99% → 50% accuracy as input grew).
- So: keep a small always-loaded working set + page the rest in on demand.

## How this maps onto the plain-markdown template
| MemGPT/Letta | This template |
|---|---|
| Core memory (always in-context, self-edited) | `MEMORY.md` + hierarchical `CLAUDE.md` LIVE blocks |
| Archival memory (paged in on demand) | the `_knowledge/` vault — but **browsed via `INDEX.md`**, not vector-searched |
| Self-editing via tool calls | the agent appends shards + runs `kb-sync.py` |
| OS "virtual memory" framing | the two-tier discipline in `template/README.md` |

**One deliberate divergence:** Letta's archival tier is a **vector DB**. We replace it with a
**browsable markdown vault** because at project/personal scale (≲150–200 pages) an index + context
window retrieves reliably without embeddings (see [[plain-markdown-vs-vector-rag]]). We keep the
*tiered, self-managed* half of MemGPT and drop the *vector* half.
