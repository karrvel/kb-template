# kb-eval — measure the KB's real impact (KB-ON vs KB-OFF)

The empirical companion to the audit. The audit could only measure the **write side** (the vault
grows, gets logged, regenerates). This measures the **read side**: does having the KB actually change
what the agent does? It produces the "using vs not using" number.

## The design (why it's honest)

Each line in `traps.jsonl` is a task whose correct answer is a **documented, off-code fact** that
lives only in the vault — a gotcha, a prod caveat, a security rule (a config trap, a "this check is
cosmetic" warning, a "don't reuse the v1 app" caveat). The agent can't get these from the
source, so attribution is clean: if the KB helps, this is where it shows.

Same model, same prompt, run twice:
- **KB-ON** — from the real workspace: `CLAUDE.md` + tier-1 `MEMORY.md` auto-load, the agent can read
  the vault.
- **KB-OFF** — from a bare temp dir: no project `CLAUDE.md`, no project memory, no vault. (Your global
  `~/.claude/CLAUDE.md` loads in *both*, so it's held constant — not the variable.) **Nothing is
  mutated** — the OFF condition is isolation-by-cwd, not by editing your vaults.

A **blinded grader** (fresh session, given only the question + criterion + one answer, never the
condition) decides whether each answer surfaced the fact. The gap between ON and OFF is the number.

In practice KB-ON surfaces the exact documented value while KB-OFF replies "the working directory is
empty… I have no prior memory about this project" — a clean per-trap win. (Real, secret-bearing traps
are kept in `traps.local.jsonl`, which is git-ignored; the committed `traps.jsonl` is a redacted
example.)

## Run it

```bash
python3 run-eval.py --dry-run                 # validate manifest + show exact commands, no calls
python3 run-eval.py --limit 3 --model claude-sonnet-5     # smoke: first 3 traps end-to-end
python3 run-eval.py --model claude-sonnet-5    # run every trap in the file → results/report.md
python3 run-eval.py --only example-single-fact         # one trap by id
python3 run-eval.py --traps traps.local.jsonl          # your real, git-ignored traps
python3 run-eval.py --skip-grade               # run agents only …
python3 run-eval.py --grade-only               # … then grade an existing results.jsonl
```

Cost: each trap is ~2 agent calls + 2 grader calls. On Sonnet, budget ~**$0.30–0.60 per trap**
(~$4–7 for the full 12). `--max-budget-usd` is wired as a runaway safety net per call; the real
bound is the subprocess timeout. Scale with `--limit`. Outputs: `results/results.jsonl` (raw,
checkpointed per trap) + `results/report.md` (the delta table).

## Reading the result

- **Documented-fact-surfaced %, ON vs OFF** — the headline. A large positive Δ = the KB is
  load-bearing; a small Δ = either the facts are already common-knowledge or the KB isn't being
  consulted (check that `CLAUDE.md` points the agent at the vault and that the fact actually lives in
  a shard — read the KB-ON answer in `results.jsonl` to see whether it opened the vault at all).
- **input-tokens ON vs OFF** — the KB's *cost* (context it adds every session). Shown honestly so
  you weigh benefit against price.
- `•` in a cell = a run or grade errored; it's excluded from the rates, re-run it.

## Typed traps (read per-type, not just the aggregate)

Each trap has a `type`; the report breaks scores down by it. This is the key lesson from *Know Your
RAG* (IBM, COLING 2025): retrieval quality varies 4.8–42% **by question type**, so an aggregate
hides the truth, and naive single-prompt Q&A generation over-produces single-fact questions (~95%).
The seeded types:
- **single-fact** — one documented fact (a config trap, a "this is live in prod" caveat).
- **summary** — synthesis across shards ("summarize the open security findings").
- **reasoning** — multi-hop across ≥2 shards (which host is prod *and* what 503 means).
- **abstention** — a plausible-but-undocumented question; `applied=true` means the agent correctly
  **refused to fabricate** (not "surfaced a fact"). Here a **high KB-ON % is the goal, Δ≈0 is fine** —
  it measures hallucination-resistance, i.e. the KB doesn't make the agent make things up.

## Judge bias — use a cross-family judge

LLM judges over-score their own model family (self-preference bias, empirically ~0.52 for GPT-4).
So the grader defaults to a **different tier** than the sonnet agent (Opus), and the runner **warns**
if judge == agent model. For a *true* cross-family judge (the robust fix), point the grader at a
local, non-Claude model via any OpenAI-compatible endpoint:
```bash
python3 run-eval.py --grader-endpoint http://localhost:1234/v1 --grader-model qwen2.5-14b-instruct
# (LM Studio / OLLM / any OpenAI-compatible server; --grader-key if it needs a bearer token)
```
Binary pass/fail judging (what this uses) is more reproducible than 0–100 numeric scores — also per
the research. Spot-check ~5 verdicts by hand to calibrate the judge against your own judgment.

## Extend it

Add traps: one JSONL line each — `{id, project, type, workspace, prompt, criterion, shard}`. Best
traps are **off-code and project-specific** (tribal knowledge), because that's exactly what a KB
captures and a codebase can't tell you. Keep `criterion` strict and checkable, and spread across the
four types.

**Scope caveat:** this measures knowledge-recall (does the KB surface the right fact). It's a strong
proxy for everyday impact but not identical to full task-completion time on real coding work — for
that, layer a naturalistic randomized on/off log over real sessions (turns, tokens, rework) on top.
