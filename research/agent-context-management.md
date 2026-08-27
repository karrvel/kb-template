---
title: Context management in agent harnesses — patterns worth stealing
updated: 2026-08-27
provenance: source-verified read of two public projects (pi-coding-agent 0.84.3 TypeScript recovered from npm source maps; TencentDB Agent Memory README/config on both branches). Mechanism audit — no benchmark was run.
status: durable
---

# Context management in agent harnesses — patterns worth stealing

The rest of this research corpus is about **durable** memory: what a knowledge base should look like and when it needs retrieval. This page is about the other half of the problem — the **in-session** context that a coding agent burns through in a single long task, and what harness authors have converged on to keep it small without losing the ability to recover detail.

It is here because the two problems keep producing the same answers, and because a KB design that ignores in-task context pressure solves only half of what an agent actually needs.

**The two subjects.** Both are public, so every claim below can be checked:

- **Pi** — [`earendil-works/pi`](https://github.com/earendil-works/pi), npm `@earendil-works/pi-coding-agent`. Source read at **0.84.3** (published 2026-08-24), with **0.79.0** checked where the two differ.
- **TencentDB Agent Memory** — [`TencentCloud/TencentDB-Agent-Memory`](https://github.com/TencentCloud/TencentDB-Agent-Memory), MIT. Read at **v2.0.1**; note its default branch is the feature branch `feat/server_team` (the team-hub product), while `main` holds the older local plugin. Config values cited are from its published defaults.

**Method.** Read from source, not from marketing. For a published npm package the tarball usually ships `dist/**/*.js.map` with full `sourcesContent`, so `npm pack` plus a short extractor recovers the original TypeScript — that is how Pi's sources were obtained here (205 files). Vendor docs describe intent; the code describes behaviour, and the two drift. Version-stamp everything — see the caveat at the end for what happens when you don't.

## 1. Offload the bulk, keep a retrievable pointer

The single most transferable idea, and three independent projects arrived at it:

- **Pi 0.84.3** truncates large shell output in context to 2000 lines or 50 KB (whichever hits first), writes the **full** output to a temp file, and leaves the path inline: `[Showing lines X-Y of N. Full output: <fullOutputPath>]`. The model gets a handle it can `grep`, not the payload. `read` truncates head-first, `bash` tail-first — you want the top of a file and the end of a run.
- **TencentDB Agent Memory v2.0.1** offloads verbose tool logs to `refs/*.md` and keeps only a dense Mermaid symbol graph in context, with `node_id`s that map back to the raw text.
- The two-tier KB in this repo does the same thing at a slower timescale: a tiny always-loaded core of pointers over a browse-on-demand vault.

The invariant is: **never destroy evidence to save context; replace it with an address.** Compression that loses the path back to ground truth is the failure mode all three are avoiding.

Corollary for a KB: a summary that cannot be traced to its source is a liability, not an asset. Keep provenance on every shard.

## 2. Layer both the writing and the reading

Layered memory is not just a storage scheme — it changes what gets read. TencentDB Agent Memory's four-level pyramid — L0 Conversation → L1 Atom → L2 Scenario → L3 Persona — means normal operation touches only the top, and lower layers are paged in when a specific fact is needed. Its own framing is *"lower layers preserve evidence; upper layers preserve structure"*, with lower layers in a database and upper layers as human-readable Markdown. That is the tiered-memory idea from [[memgpt-letta-tiered-memory]] applied to conversation rather than to documents, and it independently reproduces [[karpathy-llm-wiki]]'s compile-don't-re-derive.

Worth noting what that design *misses*, because it is the same gap this corpus flagged in the literature: it has consolidation (lower layers distil upward) but **no decay, staleness, or link-rot machinery**, and it ships `capture.l0l1RetentionDays: 0` — "never clean up" — as the default. Compaction without expiry is a ratchet. If you build layered memory, build the pruning loop at the same time — see the `tooling/` scripts in this repo for the non-LLM version.

## 3. Anchor token accounting on what the provider actually billed

A harness needs to know how full the context is on every turn. The naive options are both bad: run a tokenizer over the whole history (expensive, and still an approximation of the provider's own counting), or estimate everything with a chars/4 heuristic (cheap, drifts).

The better pattern, from Pi's `estimateContextTokens()`: walk back to the most recent assistant message that carries **usage reported by the provider**, take that as ground truth, and estimate only the messages after it with a deliberately conservative chars/4 heuristic. Cost is proportional to messages since the last response rather than to history length, and the number is exact wherever it has been billed. Skip aborted, errored, and zero-usage messages when looking for the anchor.

## 4. Auxiliary LLM calls should not write to the prompt cache

A summarization call is a one-off: its prompt will never be seen again. Writing it into the provider's prompt cache costs money and can displace the real conversation's cached prefix.

Pi 0.84.3 forces exactly this on every compaction and branch-summary call (`completeSummarization()`): `cacheRetention: "none"`, a **fresh routing `sessionId`** so it does not share the main conversation's cache lineage, and `toolChoice: "none"`. Note this is **0.84-only** — 0.79.0 does not do it. Cheap to implement, easy to forget, and it applies to any agent that makes side calls — summarizers, classifiers, judges, embedders.

## 5. Separate "persisted" from "injected"

Pi's session format distinguishes two kinds of extension-written record: `type: "custom"` entries, **persisted but never entering the model's context**, and `custom_message` entries, **persisted and injected** (with a `display` flag for TUI visibility). Most formats conflate them, so anything worth storing costs tokens forever.

Same lesson for a KB: "in the vault" and "in the always-loaded core" must be different decisions, made explicitly. That is exactly what the core/vault split in this template is for — the discipline only holds if the format makes the distinction representable.

## 6. Session history as a tree, not a log

Pi stores session entries as JSONL with `id` / `parentId` parent pointers rather than as a flat list (format v3), which lets it branch in place: jump back to an earlier point, try a different approach, and keep both paths in the same file with no copy-on-branch. Abandoned branches can be summarized and the summary attached at the new position, so context from the path not taken is not simply lost.

For KB purposes the transferable part is smaller but real: **an append-only structure with explicit parentage beats rewriting**, because it preserves the audit trail that makes re-verification possible.

## 7. Make summarization pluggable — and run it on a cheaper model

The best cost lever found in this pass: Pi fires `session_before_compact` before compacting and lets an extension cancel it or supply the summary outright (0.84.3 also adds a `reason` — `manual` / `threshold` / `overflow` — and a `session_compact_failed` event for telemetry). Summarization is bulk text reduction. It does **not** need the frontier model that is doing the actual engineering.

Routing summarization to a small local or cheap hosted model, while the main loop runs on something capable, is a structural saving rather than a tuning one. If your harness does not expose that seam, that is a reason to prefer one that does.

Two details that make summaries better regardless of which model runs them:

- **Serialize, don't replay.** Pi's `serializeConversation()` flattens messages into a labelled transcript (`[User]:`, `[Assistant tool calls]:`, `[Tool result]:`), truncates each tool result to 2000 characters, and pairs it with a system prompt that says *"Do NOT continue the conversation."* Handing a model a raw conversation invites it to answer the last question instead.
- **Update, don't re-derive.** Feed the previous summary back in and ask for an updated one. This is the same compile-once-and-file-it-back discipline as [[karpathy-llm-wiki]], applied per-turn — and it lets cumulative facts (which files were read, which were modified) survive an unbounded number of compactions.

## 8. ⚠️ Check the arithmetic of your compaction budget

A portable trap, found in Pi's shipped defaults (identical in **0.79.0 and 0.84.3**) and worth checking in any harness you adopt.

Compaction typically has two knobs: **reserve** (tokens held back for the response, and therefore the trigger point) and **keep-recent** (how much recent conversation is never summarized). The trigger is:

```
compact when  contextTokens > contextWindow − reserveTokens
```

If `keepRecentTokens >= contextWindow − reserveTokens`, then at the moment compaction fires the keep-recent budget is **larger than the entire context**. The cut-point search walks backwards accumulating tokens, never reaches its threshold, and falls through to its initial value — the oldest entry. Nothing is selected for summarization, so compaction returns empty and does nothing. It fails silently. Cheaply, if the implementation short-circuits before calling the model — but the context still grows until the provider rejects the request.

Pi's defaults are `reserveTokens: 16384` / `keepRecentTokens: 20000` — tuned for a large-context frontier model (against a 200k window: triggers at 184k, summarizes ~164k — fine). Point the same harness at a 32k local model and the arithmetic inverts: the trigger fires at 16384, `findCutPoint()` never reaches its threshold, `cutIndex` keeps its `cutPoints[0]` initialiser, and `prepareCompaction()` returns `undefined`. **There is no guard for this case.**

**Rule: `keepRecentTokens` must sit comfortably below `contextWindow − reserveTokens`.** Scale both to the window rather than inheriting the defaults. For a 32k window, reserve ~4k and keep-recent ~8k leaves ~20k of genuinely reclaimable history.

Check this before blaming the model for "forgetting" on a small-context setup.

## The caveat that applies to all of the above

**None of this was benchmarked.** This is a mechanism audit: the patterns are read from source and are real, and several are things a naive harness genuinely gets wrong. But "harness X is more efficient" claims circulating in communities are not measured numbers, and neither is this page.

Two specific discipline notes, both learned the hard way in this pass:

- **Version-stamp every claim.** Between Pi 0.79.0 and 0.84.3, the compaction event gained a reason code, summaries started reporting their own token usage, `session_compact_failed` appeared, and cache retention was forced off on auxiliary calls. A claim without a version attached will not match what a reader has installed.
- **Docs describe the build the author was thinking about.** Pi's `session-format.md` documents `retainedTail` — self-contained compaction checkpoints that let context rebuild skip everything older — unconditionally. In 0.84.3 it exists only in `dist/bundle/chunks/` (the compiled-binary / SDK bundle): the source-mapped `dist/core/**` tree that `dist/cli.js` actually loads has **zero** occurrences of `retainedTail` and six of the legacy `firstKeptEntryId`. So the npm CLI does not have the documented behaviour. Grep the entry point you actually run.

If you want a number rather than a mechanism, the honest route is the same one this repo uses for KBs: typed tasks, an A/B with and without the feature, per-type reporting, and a grader from a different model family. See `tooling/kb-eval/`.

## Related

[[agent-memory-landscape]] — the durable-memory synthesis this page complements ·
[[karpathy-llm-wiki]] — compile, don't re-derive ·
[[memgpt-letta-tiered-memory]] — the tiered core/archival model ·
[[plain-markdown-vs-vector-rag]] — the scale ceiling
