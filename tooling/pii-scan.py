#!/usr/bin/env python3
# © 2026 karrvel — proprietary. No use or distribution without consent; see LICENSE.md.
"""pii-scan.py — mechanical PII / private-context guard for a repo that goes PUBLIC.

Codified, not inferred: a fixed list of regexes. Exits non-zero (blocks) on any match, so it can
gate a pre-push hook. Generic patterns only live here (safe to publish). User/project-specific
literals (other private project names, personal emails) live in a LOCAL denylist that is gitignored
and NEVER committed — pass it via --denylist or $PII_DENYLIST, or drop a `.pii-denylist.local` at the
repo root (one entry per line; `#` comments; a line is a regex if it starts with `re:` else literal).

Scans, in order of what leaks:
  files    tracked file contents           (default: `git ls-files`)
  commits  commit messages in a range      (--range BASE..HEAD, or via the pre-push hook)
  staged   staged diff added lines         (--staged)

Usage:
  python3 tooling/pii-scan.py                      # scan all tracked files
  python3 tooling/pii-scan.py --staged             # scan staged additions (pre-commit)
  python3 tooling/pii-scan.py --range origin/main..HEAD   # scan commit messages too
  PII_DENYLIST=~/kb.pii python3 tooling/pii-scan.py --range ...
Exit 0 = clean, 1 = matches found, 2 = usage/error.
"""
import os, re, subprocess, sys

# ── Codified generic patterns (public-safe). (label, compiled regex). ────────────────────────────
PATTERNS = [
    ("claude-session-url",   re.compile(r"claude\.ai/code/session[_/][A-Za-z0-9._-]+")),
    ("claude-session-trailer", re.compile(r"(?im)^\s*Claude-Session\s*:")),
    ("home-path-users",      re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("home-path-home",       re.compile(r"/home/[A-Za-z0-9._-]+/")),
    ("private-key-block",    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("aws-access-key",       re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token",         re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("openai-key",           re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("slack-token",          re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key",       re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("generic-secret-assign", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("email",                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]
# Known-safe substrings that suppress a match on the SAME line (avoid false positives). Extend freely.
ALLOW = [
    # generic no-reply / example addresses
    "noreply@anthropic.com", "noreply@github.com", "@example.com", "@example.org",
    "user@host", "you@example", "name@example", "<email>", "example@",
    # git SSH host (public, appears in clone commands)
    "git@github.com", "git@gitlab.com",
    # documentation placeholder home paths (real usernames stay blocked)
    "/Users/me/", "/Users/you/", "/Users/name/", "/Users/<", "/home/me/", "/home/you/",
]
# Binary/vendored paths never worth scanning.
SKIP_PATH = re.compile(r"(?:^|/)(?:\.git/|__pycache__/|\.png$|\.jpg$|\.jpeg$|\.gif$|\.pdf$|\.ico$|\.woff2?$|\.lock$)")

def load_denylist():
    """Extra user/project literals or regexes from a LOCAL, gitignored source."""
    pats, path = [], (opt("--denylist") or os.environ.get("PII_DENYLIST"))
    if not path:
        default = os.path.join(repo_root(), ".pii-denylist.local")
        path = default if os.path.exists(default) else None
    if not path or not os.path.exists(os.path.expanduser(path)):
        return pats
    for raw in open(os.path.expanduser(path), errors="ignore"):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("re:"):
            pats.append(("denylist-regex", re.compile(s[3:], re.I)))
        else:
            pats.append(("denylist-literal", re.compile(re.escape(s), re.I)))
    return pats

def opt(flag):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    return None

def repo_root():
    try:
        return subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    except subprocess.CalledProcessError:
        return os.getcwd()

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout

def scan_text(text, patterns, where, hits):
    for n, ln in enumerate(text.splitlines(), 1):
        if any(a in ln for a in ALLOW):
            continue
        for label, rx in patterns:
            m = rx.search(ln)
            if m:
                snip = m.group(0)
                if len(snip) > 60: snip = snip[:57] + "…"
                hits.append((where, n, label, snip))

def main():
    patterns = PATTERNS + load_denylist()
    root = repo_root()
    hits = []

    # 1. tracked files (default surface)
    for rel in git("ls-files").splitlines():
        if SKIP_PATH.search(rel):
            continue
        p = os.path.join(root, rel)
        try:
            with open(p, "rb") as fh:
                raw = fh.read()
            if b"\x00" in raw[:4096]:
                continue  # binary
            scan_text(raw.decode("utf-8", "ignore"), patterns, rel, hits)
        except OSError:
            continue

    # 2. commit messages in a range (history is permanent once public)
    rng = opt("--range")
    if rng:
        for sha in git("rev-list", rng).splitlines():
            body = git("show", "-s", "--format=%B", sha)
            scan_text(body, patterns, f"commit {sha[:9]} (message)", hits)

    # 3. staged additions
    if "--staged" in sys.argv:
        diff = git("diff", "--cached", "--unified=0")
        added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        scan_text(added, patterns, "staged diff", hits)

    if hits:
        print(f"✗ pii-scan: {len(hits)} potential leak(s) — BLOCKED (this repo goes public):\n")
        for where, n, label, snip in hits:
            print(f"    {where}:{n}  [{label}]  {snip}")
        print("\n  Scrub them, or if a hit is a false positive add the safe substring to ALLOW in")
        print("  tooling/pii-scan.py. Bypass once (last resort): git push/commit --no-verify.")
        return 1
    print("✓ pii-scan: no PII / private-context patterns found.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
