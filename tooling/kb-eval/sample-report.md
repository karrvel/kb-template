# KB impact — sample A/B report (scrubbed)

A worked, PII-scrubbed excerpt of a real known-trap A/B run. The full run used **private** vaults, so
project names and the documented facts themselves are redacted here — that confidential off-code
knowledge is exactly what the kit exists to preserve. Reproduce the method on your own vault with the
scripts in this directory (`run-eval.py`, `traps.jsonl`).

## Method
A "trap" is a question whose correct answer is a documented, off-code fact that lives **only** in the
vault (a gotcha, a prod caveat, a security rule). Each trap runs the same agent twice — once **with**
the vault (KB-ON), once **without** (KB-OFF) — and an LLM judge, blind to which arm produced which
answer, grades only whether the answer surfaced the documented fact.

## Headline — n = 16 traps, three real private codebases (one operator)
| | KB-ON | KB-OFF | Δ |
|---|---:|---:|---:|
| **Documented fact surfaced** | **100%** | **31%** | **+69 pts** |
| avg output tokens | 1189 | 2089 | |
| avg turns | 3.7 | 4.2 | |
| avg cost (USD) | 0.23 | 0.31 | |

## By question type
| type | n | KB-ON | KB-OFF | Δ |
|---|--:|--:|--:|--:|
| single-fact | 12 | 100% | 33% | +67 |
| multi-hop reasoning | 2 | 100% | 0% | +100 |
| synthesis / summary | 1 | 100% | 0% | +100 |
| abstention (no hallucination) | 1 | 100% | 100% | +0 |

Verdict distribution: **11 KB-only wins**, 5 both-arms-already-knew, **0** KB-off-only, **0** hallucinations.

> **Honest caveats.** Small sample (16 traps), one operator's three codebases, a single judge model.
> This is *directional* evidence that a vault surfaces off-code knowledge the code alone can't — not a
> universal benchmark. The numbers reproduce the **method**, not a guaranteed effect size on your data.

## One trap, redacted (what a single row looks like)
**Question (single-fact):** "Is there a non-obvious constraint on how a certain service's base URL
must be formatted?" — the answer is a documented gotcha that lives only in the vault, not in the code.

- **KB-OFF:** *"I don't have prior memory of this project…"* → assumed the common convention →
  **missed the constraint** ❌
- **KB-ON:** read the vault, surfaced the documented caveat (a formatting rule that silently breaks
  requests if violated) → **correct** ✅
- **Judge (blind):** `applied=true` for KB-ON, `applied=false` for KB-OFF.

The specific constraint is redacted — it's precisely the project-specific, off-code knowledge the kit
compiles so a future agent doesn't have to rediscover it the hard way.
