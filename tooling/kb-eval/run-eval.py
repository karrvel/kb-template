#!/usr/bin/env python3
# © 2026 karrvel — proprietary. No use or distribution without consent; see LICENSE.md.
"""run-eval.py — measure the KB's real impact: known-trap A/B (KB-ON vs KB-OFF).

The rigorous "using vs not using" number. Each trap in traps.jsonl is a task whose correct answer
is a documented, OFF-CODE fact that lives only in the vault (a gotcha, a prod caveat, a security
rule). We ask the same question twice, same model, same prompt:

  KB-ON  — run from the real workspace: CLAUDE.md + tier-1 MEMORY.md auto-load, the agent can read
           the vault. This is "using the KB."
  KB-OFF — run from a bare temp dir: no project CLAUDE.md, no project memory, no vault. Same model,
           same prompt. This is "not using the KB." (The global ~/.claude/CLAUDE.md loads in BOTH,
           so it's held constant and isn't the variable.)

A blinded grader (fresh session, given only prompt + criterion + one answer, NOT the condition)
decides whether each answer surfaced the documented fact. Attribution is clean because we KNOW the
vault contains the answer — so a gap between ON and OFF is the KB earning (or not earning) its keep.

Nothing is mutated: KB-OFF is isolation-by-cwd, not by editing your vaults. Read-only against repos.

  python3 run-eval.py --dry-run                 # validate manifest + print exact commands, no calls
  python3 run-eval.py --limit 3                  # smoke: first 3 traps, both conditions + grade
  python3 run-eval.py --only example-single-fact
  python3 run-eval.py --traps traps.local.jsonl        # your real (git-ignored) traps
  python3 run-eval.py --model claude-sonnet-5 --grader-model claude-sonnet-5
  python3 run-eval.py --skip-grade               # run agents only; grade later with --grade-only
  python3 run-eval.py --grade-only               # (re)grade an existing results.jsonl

Outputs (in --out, default ./results): results.jsonl (raw), report.md (the delta table).
"""
import argparse, json, os, subprocess, sys, tempfile, shutil, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# read-only tools; bypassPermissions because it's headless recall in the user's own workspace.
AGENT_TOOLS = ["Read", "Grep", "Glob", "Bash"]
# --max-budget-usd is a RUNAWAY SAFETY NET, not a normal-run bound: hitting it aborts the session
# with NO result, so set it well above a real recall run (KB-ON legitimately costs more — it loads
# CLAUDE.md + tier-1 memory and reads shards). The real bound is CALL_TIMEOUT.
PER_CALL_BUDGET = "1.00"       # agent call safety net
GRADER_BUDGET = "0.50"         # grader safety net — Opus grading a long answer needs headroom
                               # (0.05 then 0.20 both aborted mid-grade → None). Real bound = timeout.
CALL_TIMEOUT = 300             # subprocess seconds


def load_traps(path):
    traps = []
    for ln in open(path, errors="ignore"):
        ln = ln.strip()
        if ln:
            traps.append(json.loads(ln))
    return traps


def claude_cmd(prompt, model, tools=None, budget=PER_CALL_BUDGET):
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--permission-mode", "bypassPermissions", "--max-budget-usd", budget]
    if model:
        cmd += ["--model", model]
    if tools:
        cmd += ["--allowedTools", *tools]
    return cmd


def run_claude(cmd, cwd):
    """Run a claude -p call, return the parsed JSON envelope (or an {error} dict)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"_error": "timeout"}
    except Exception as e:
        return {"_error": str(e)[:120]}
    out = p.stdout.strip()
    if not out:
        return {"_error": "empty stdout", "_stderr": p.stderr.strip()[:200]}
    try:
        return json.loads(out)
    except Exception:
        for ln in reversed(out.splitlines()):        # tolerate leading noise
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    return json.loads(ln)
                except Exception:
                    continue
        return {"_error": "unparseable json", "_raw": out[:200]}


def metrics(env):
    u = env.get("usage") or {}
    return {
        "result": env.get("result", ""),
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read": u.get("cache_read_input_tokens", 0),
        "num_turns": env.get("num_turns"),
        "cost_usd": env.get("total_cost_usd"),
        "duration_ms": env.get("duration_ms"),
        "is_error": env.get("is_error", False),
        "error": env.get("_error"),
    }


def openai_chat(endpoint, model, prompt, api_key=None):
    """Call an OpenAI-compatible /v1/chat/completions endpoint (LM Studio :1234, OLLM, etc.).
    Enables a genuine CROSS-FAMILY judge (e.g. a local Qwen grading Claude answers) — the research
    on LLM-judge self-preference/family bias says the judge should differ from the generator."""
    url = endpoint.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"]["content"], None
    except Exception as e:
        return "", str(e)[:140]


def grade(prompt, criterion, answer, grader_model, endpoint=None, api_key=None):
    gp = (
        "You are grading whether an assistant's answer surfaced a specific piece of project "
        "knowledge. Be strict: the criterion must be genuinely satisfied, not vaguely gestured at.\n\n"
        f"QUESTION ASKED:\n{prompt}\n\nCRITERION (what a correct, KB-informed answer must contain):\n"
        f"{criterion}\n\nTHE ASSISTANT'S ANSWER:\n{answer}\n\n"
        'Respond with ONLY strict JSON, no prose: {"applied": true|false, "evidence": "<short quote '
        'from the answer, or none>"}'
    )
    if endpoint:                                   # cross-family judge via OpenAI-compatible API
        txt, err = openai_chat(endpoint, grader_model, gp, api_key)
        if err:
            return {"applied": None, "evidence": f"grader-endpoint-error: {err}"}
    else:                                          # default: Claude judge
        env = run_claude(claude_cmd(gp, grader_model, tools=None, budget=GRADER_BUDGET),
                         cwd=tempfile.gettempdir())
        txt = env.get("result", "") if "_error" not in env else ""
    verdict = {"applied": None, "evidence": env.get("_error", "grader-parse-fail")}
    for cand in (txt, txt[txt.find("{"):txt.rfind("}") + 1] if "{" in txt else ""):
        try:
            j = json.loads(cand)
            verdict = {"applied": bool(j.get("applied")), "evidence": str(j.get("evidence", ""))[:160]}
            break
        except Exception:
            continue
    if verdict["applied"] is None:      # last-ditch keyword fallback
        low = txt.lower()
        if '"applied": true' in low or '"applied":true' in low:
            verdict = {"applied": True, "evidence": "kw-fallback"}
        elif '"applied": false' in low or '"applied":false' in low:
            verdict = {"applied": False, "evidence": "kw-fallback"}
    return verdict


def pct(xs):
    xs = [x for x in xs if x is not None]
    return (sum(1 for x in xs if x) / len(xs) * 100) if xs else 0.0


def rate(xs):
    """% applied, or None if nothing in this bucket was successfully graded (→ show n/a, not 0%)."""
    xs = [x for x in xs if x is not None]
    return (sum(1 for x in xs if x) / len(xs) * 100) if xs else None


def fmt(r):
    return f"{r:.0f}%" if r is not None else "n/a"


def write_report(results, out_dir):
    on_app = [r["on"]["applied"] for r in results if r.get("on")]
    off_app = [r["off"]["applied"] for r in results if r.get("off")]
    on_rate, off_rate = pct(on_app), pct(off_app)

    def avg(cond, key):
        vs = [r[cond]["m"].get(key) for r in results if r.get(cond) and r[cond]["m"].get(key) is not None]
        return sum(vs) / len(vs) if vs else 0

    lines = []
    lines.append(f"# KB impact — known-trap A/B\n")
    lines.append(f"_Generated {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')} · "
                 f"{len(results)} traps · blinded grading_\n")
    lines.append(f"## Headline\n")
    lines.append(f"| | KB-ON | KB-OFF | Δ |")
    lines.append(f"|---|---:|---:|---:|")
    lines.append(f"| **Documented fact surfaced** | **{on_rate:.0f}%** | **{off_rate:.0f}%** | "
                 f"**{on_rate-off_rate:+.0f} pts** |")
    lines.append(f"| avg output tokens | {avg('on','output_tokens'):.0f} | {avg('off','output_tokens'):.0f} | |")
    lines.append(f"| avg input tokens (context cost) | {avg('on','input_tokens'):.0f} | {avg('off','input_tokens'):.0f} | |")
    lines.append(f"| avg turns | {avg('on','num_turns'):.1f} | {avg('off','num_turns'):.1f} | |")
    lines.append(f"| avg cost USD | {avg('on','cost_usd'):.4f} | {avg('off','cost_usd'):.4f} | |")
    lines.append(f"\n_KB-ON surfaced the documented fact **{on_rate-off_rate:+.0f} points** more often. "
                 f"That gap is the KB earning its keep — knowledge the agent cannot get from the code alone._\n")

    # per-type breakdown — an aggregate hides large variance across question types (Know-Your-RAG, COLING 2025)
    types = {}
    for r in results:
        types.setdefault(r.get("type", "single-fact"), []).append(r)
    lines.append(f"## By question type\n")
    lines.append(f"| type | n | KB-ON | KB-OFF | Δ |")
    lines.append(f"|---|--:|--:|--:|--:|")
    for ty in sorted(types):
        rs = types[ty]
        o = rate([r["on"]["applied"] for r in rs if r.get("on")])
        f_ = rate([r["off"]["applied"] for r in rs if r.get("off")])
        d = f"{o-f_:+.0f}" if (o is not None and f_ is not None) else "—"
        lines.append(f"| {ty} | {len(rs)} | {fmt(o)} | {fmt(f_)} | {d} |")
    lines.append("")
    lines.append(f"## Per trap\n")
    lines.append(f"| trap | project | type | KB-ON | KB-OFF | verdict |")
    lines.append(f"|---|---|---|:---:|:---:|---|")
    def cell(c):
        if not r.get(c):
            return "—", None
        ap = r[c]["applied"]
        if ap is None:                       # errored or ungraded — NOT a KB failure
            return "•", None
        return ("✅" if ap else "❌"), bool(ap)
    n_na = 0
    for r in results:
        on, onb = cell("on"); off, offb = cell("off")
        if onb is None or offb is None:
            v = "n/a (run/grade error)"; n_na += 1
        elif onb and not offb:
            v = "KB-only win"
        elif onb and offb:
            v = "both knew"
        elif not onb and not offb:
            v = "neither"
        else:
            v = "OFF>ON (check)"
        lines.append(f"| `{r['id']}` | {r['project']} | {r.get('type','single-fact')} | {on} | {off} | {v} |")
    if n_na:
        lines.append(f"\n_{n_na} trap(s) had a run/grade error (`•`) and are excluded from the rates "
                     f"above — re-run them._")
    body = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(body)
    return body, on_rate, off_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traps", default=os.path.join(HERE, "traps.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--model", default=None, help="agent-under-test model (default: claude default)")
    ap.add_argument("--grader-model", default="claude-opus-4-8",
                    help="judge model. Default differs from the sonnet agent to reduce self-preference. "
                         "For a true cross-family judge, set --grader-endpoint + a local model here.")
    ap.add_argument("--grader-endpoint", default=os.environ.get("KB_GRADER_ENDPOINT"),
                    help="OpenAI-compatible base URL for a cross-family judge, e.g. "
                         "http://localhost:1234/v1 (LM Studio) — genuinely non-Claude, dodges family bias.")
    ap.add_argument("--grader-key", default=os.environ.get("KB_GRADER_KEY"),
                    help="bearer key for --grader-endpoint (optional; LM Studio needs none)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-grade", action="store_true")
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    res_path = os.path.join(a.out, "results.jsonl")

    # self-preference guard: a Claude judge grading the SAME Claude model it's judging inflates scores
    if not a.grader_endpoint and a.grader_model == (a.model or "claude-sonnet-5"):
        print(f"⚠️  grader-model == agent model ({a.grader_model}). LLM judges over-score their own "
              f"family (self-preference bias). Use a different tier, or --grader-endpoint for a "
              f"cross-family judge.\n", file=sys.stderr)
    if a.grader_endpoint:
        print(f"ℹ️  cross-family judge: {a.grader_endpoint} (model={a.grader_model})\n")

    traps = load_traps(a.traps)
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        traps = [t for t in traps if t["id"] in want]
    if a.limit:
        traps = traps[:a.limit]

    # validate workspaces exist
    bad = [t["id"] for t in traps if not os.path.isdir(t["workspace"])]
    if bad:
        print(f"⚠️  workspaces missing for: {bad}", file=sys.stderr)

    if a.dry_run:
        print(f"DRY RUN — {len(traps)} trap(s). No calls made.\n")
        off_dir = "<fresh temp dir>"
        for t in traps:
            print(f"● {t['id']}  ({t['project']})")
            print(f"   KB-ON  cwd={t['workspace']}")
            print(f"          {' '.join(claude_cmd('<prompt>', a.model, AGENT_TOOLS)[:8])} …")
            print(f"   KB-OFF cwd={off_dir} (no CLAUDE.md/memory/vault)")
            print(f"   grade  blinded, model={a.grader_model}, criterion len={len(t['criterion'])}\n")
        print(f"Run for real: python3 run-eval.py --limit {min(3,len(traps))}   "
              f"(then scale up). Per-call budget cap ${PER_CALL_BUDGET}.")
        return 0

    if a.grade_only:
        rows = [json.loads(l) for l in open(res_path)] if os.path.exists(res_path) else []
        for r in rows:
            for cond in ("on", "off"):
                if r.get(cond):
                    t = next((x for x in traps if x["id"] == r["id"]), None) or {}
                    r[cond]["applied"] = grade(r.get("prompt", ""), r.get("criterion", ""),
                                               r[cond]["m"].get("result", ""), a.grader_model,
                                               a.grader_endpoint, a.grader_key)["applied"]
        with open(res_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        body, on_rate, off_rate = write_report(rows, a.out)
        print(body)
        return 0

    results = []
    off_base = tempfile.mkdtemp(prefix="kb-off-")
    try:
        for i, t in enumerate(traps, 1):
            print(f"[{i}/{len(traps)}] {t['id']} …", flush=True)
            row = {"id": t["id"], "project": t["project"], "type": t.get("type", "single-fact"),
                   "prompt": t["prompt"], "criterion": t["criterion"]}
            # KB-ON
            env_on = run_claude(claude_cmd(t["prompt"], a.model, AGENT_TOOLS), cwd=t["workspace"])
            row["on"] = {"m": metrics(env_on), "applied": None}
            # KB-OFF — fresh empty cwd so nothing auto-loads
            off_dir = tempfile.mkdtemp(prefix="t-", dir=off_base)
            env_off = run_claude(claude_cmd(t["prompt"], a.model, AGENT_TOOLS), cwd=off_dir)
            row["off"] = {"m": metrics(env_off), "applied": None}
            if not a.skip_grade:
                row["on"]["applied"] = grade(t["prompt"], t["criterion"], row["on"]["m"]["result"],
                                             a.grader_model, a.grader_endpoint, a.grader_key)["applied"]
                row["off"]["applied"] = grade(t["prompt"], t["criterion"], row["off"]["m"]["result"],
                                              a.grader_model, a.grader_endpoint, a.grader_key)["applied"]
                print(f"     ON={'✅' if row['on']['applied'] else '❌'}  "
                      f"OFF={'✅' if row['off']['applied'] else '❌'}")
            results.append(row)
            with open(res_path, "w") as f:      # checkpoint each trap
                for r in results:
                    f.write(json.dumps(r) + "\n")
    finally:
        shutil.rmtree(off_base, ignore_errors=True)

    if not a.skip_grade:
        body, on_rate, off_rate = write_report(results, a.out)
        print("\n" + body)
    else:
        print(f"\nAgents run, grading skipped. Grade later: python3 run-eval.py --grade-only")
    print(f"raw → {res_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
