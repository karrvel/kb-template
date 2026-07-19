#!/usr/bin/env python3
# © 2026 karrvel — proprietary. No use or distribution without consent; see LICENSE.md.
"""prefilter.py — distill Codex + Claude Code transcripts into compact, provenance-tagged
per-session digests. Strips ~95-98% tool-call noise (keeps only user/assistant messages),
carries provenance (session id + date + cwd), buckets by a project keyword, truncates pasted blobs.

This is Karpathy "layer 1 → layer 2" prep: turn raw transcripts into distillable digests that a
fan-out of agents (or you) can compile into wiki shards.

USAGE
  python3 prefilter.py --match myproject --out ./digests
  python3 prefilter.py --match myproj  --out ./digests \
      --codex ~/.codex/sessions --claude ~/.claude/projects
Options:
  --match   substring that must appear in a transcript's cwd (or content) to include it. Required.
  --out     output dir for digests (default ./digests)
  --codex   Codex sessions root (default ~/.codex/sessions)
  --claude  Claude Code projects root (default ~/.claude/projects)
  --cap     per-message char cap (default 4000) — drops pasted file blobs, keeps the ask/summary
  --buckets optional 'name=substr,name2=substr2' cwd→bucket rules (else everything → 'main'/'other')
"""
import argparse, glob, hashlib, json, os, re, sys

def build_bucketer(spec, match):
    rules = []
    if spec:
        for part in spec.split(","):
            if "=" in part:
                name, sub = part.split("=", 1); rules.append((name.strip(), sub.strip().lower()))
    def bucket(cwd):
        c = (cwd or "").lower()
        for name, sub in rules:
            if sub in c: return name
        return "main" if match.lower() in c else "other"
    return bucket

def clean(txt, cap):
    if not txt: return ""
    txt = txt.strip()
    if txt.startswith(("<environment_context>", "<command-")) or txt.startswith("Caveat:"): return ""
    txt = re.sub(r"\s+\n", "\n", txt)
    if len(txt) > cap: txt = txt[:cap] + f"\n…[truncated {len(txt)-cap} chars]"
    return txt

def extract_text(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text") and b.get("text"):
                out.append(b["text"])
        return "\n".join(out)
    return ""

def process_codex(path, cap):
    cwd = sid = date = ""; msgs = []
    for line in open(path, errors="ignore"):
        try: rec = json.loads(line)
        except: continue
        if rec.get("type") == "session_meta":
            p = rec.get("payload", {}); cwd = p.get("cwd", ""); sid = p.get("id", ""); date = (p.get("timestamp") or "")[:10]
        elif rec.get("type") == "response_item":
            p = rec.get("payload", {})
            if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
                t = clean(extract_text(p.get("content")), cap)
                if len(t) >= 12: msgs.append((p["role"], t))
    return cwd, sid, date, msgs

def process_claude(path, cap):
    cwd = sid = date = ""; msgs = []
    for line in open(path, errors="ignore"):
        try: rec = json.loads(line)
        except: continue
        if not date and rec.get("timestamp"): date = rec["timestamp"][:10]
        if not cwd and rec.get("cwd"): cwd = rec["cwd"]
        if not sid and rec.get("sessionId"): sid = rec["sessionId"]
        if rec.get("type") in ("user", "assistant"):
            m = rec.get("message", {})
            if m.get("role") in ("user", "assistant"):
                t = clean(extract_text(m.get("content")), cap)
                if len(t) >= 12: msgs.append((m["role"], t))
    return cwd, sid, date, msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    ap.add_argument("--out", default="./digests")
    ap.add_argument("--codex", default=os.path.expanduser("~/.codex/sessions"))
    ap.add_argument("--claude", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--cap", type=int, default=4000)
    ap.add_argument("--buckets", default="")
    a = ap.parse_args()
    bucket = build_bucketer(a.buckets, a.match)
    os.makedirs(a.out, exist_ok=True)

    # find candidate files: any transcript whose content mentions --match
    codex_files, claude_files = [], []
    for f in glob.glob(os.path.join(a.codex, "**", "*.jsonl"), recursive=True):
        try:
            if a.match.lower() in open(f, errors="ignore").read(200000).lower(): codex_files.append(f)
        except: pass
    for f in glob.glob(os.path.join(a.claude, "**", "*.jsonl"), recursive=True):
        try:
            if a.match.lower() in open(f, errors="ignore").read(200000).lower(): claude_files.append(f)
        except: pass

    stats, n = {}, 0
    for kind, files, proc in (("codex", codex_files, process_codex), ("claude", claude_files, process_claude)):
        for f in files:
            try: cwd, sid, date, msgs = proc(f, a.cap)
            except Exception as e: print(f"ERR {kind} {f}: {e}", file=sys.stderr); continue
            if not msgs: continue
            b = bucket(cwd)
            short = hashlib.md5(f.encode()).hexdigest()[:10]   # collision-free (source-path hash)
            d = os.path.join(a.out, b); os.makedirs(d, exist_ok=True)
            fn = os.path.join(d, f"{date or 'nodate'}-{kind}-{short}.md")
            with open(fn, "w") as o:
                o.write(f"# session {short} | {kind} | {date} | cwd={cwd}\nsource: {f}\n\n")
                for role, t in msgs: o.write(f"## {role}\n{t}\n\n")
            s = stats.setdefault(b, [0, 0]); s[0] += 1; s[1] += os.path.getsize(fn); n += 1

    print(f"\n=== {n} digests written to {a.out} ===")
    print(f"{'bucket':<18}{'sessions':>10}{'KB':>10}")
    for b in sorted(stats, key=lambda k: -stats[k][1]):
        print(f"{b:<18}{stats[b][0]:>10}{stats[b][1]//1024:>10}")

if __name__ == "__main__":
    main()
