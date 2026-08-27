#!/usr/bin/env python3
# © 2026 karrvel — MIT License. See LICENSE.md.
"""kb-update.py — pull the latest kb-template scripts into this project's tooling directory.

Copy this script (with the other tooling/*.py files) into your project's _meta/ dir at init time.
Run it from there whenever you want to pull in new kit versions.

Usage:
  python3 _meta/kb-update.py            # interactive — shows diffs, prompts before each file
  python3 _meta/kb-update.py --yes      # silent — overwrites without prompting (read the warning)
  python3 _meta/kb-update.py --check    # dry-run — show what would change, exit 1 if updates exist
                                        #   (--dry-run / -n are aliases; --check never writes)

Exit codes:
  0  nothing to do, or scripts applied      2  usage error, or git clone failed
  1  updates exist (--check) / aborted      3  interactive run with no terminal on stdin

What gets updated: only the *.py scripts in the same directory as this file (your _meta/ or
tooling/ copy). The template/ scaffold (your _knowledge/ contents) is NEVER touched — it's
init-only and belongs to your project, not the kit.
"""
import difflib, os, re, shutil, subprocess, sys, tempfile, textwrap, time

REPO_URL  = "https://github.com/karrvel/kb-template.git"
REPO_TOOL = "tooling"          # subdirectory inside the kit that holds the scripts
VERSION_FILE = "kb.version"    # written next to this script after a successful update

# ── helpers ──────────────────────────────────────────────────────────────────

def _current_version(script_dir: str) -> str:
    """Read the pinned version written by a previous update, or detect from kb-sync.py."""
    vf = os.path.join(script_dir, VERSION_FILE)
    if os.path.exists(vf):
        return open(vf).read().strip()
    # fallback: parse VERSION = "x.y" from kb-sync.py
    ks = os.path.join(script_dir, "kb-sync.py")
    if os.path.exists(ks):
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)', open(ks).read(), re.M)
        if m:
            return m.group(1)
    return "unknown"

def _remote_version(kit_tool_dir: str) -> str:
    ks = os.path.join(kit_tool_dir, "kb-sync.py")
    if os.path.exists(ks):
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)', open(ks).read(), re.M)
        if m:
            return m.group(1)
    return "unknown"

def _unified_diff(path_a: str, path_b: str, label: str) -> list[str]:
    a = open(path_a).readlines() if os.path.exists(path_a) else []
    b = open(path_b).readlines() if os.path.exists(path_b) else []
    return list(difflib.unified_diff(a, b, fromfile=f"{label} (current)", tofile=f"{label} (new)", n=3))

def _colour(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"

def _print_diff(lines: list[str]) -> None:
    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            print(_colour(line, "32"), end="")
        elif line.startswith("-") and not line.startswith("---"):
            print(_colour(line, "31"), end="")
        elif line.startswith("@@"):
            print(_colour(line, "36"), end="")
        else:
            print(line, end="")

# ── silent-mode warning ───────────────────────────────────────────────────────

SILENT_WARNING = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠  SILENT MODE (--yes)                                                     ║
║                                                                              ║
║  Scripts in this directory will be OVERWRITTEN without review.               ║
║                                                                              ║
║  Before continuing, make sure you understand:                               ║
║  • Any local modifications to these scripts will be lost.                   ║
║  • New scripts may change how your vault scans for secrets or paths.        ║
║  • The PII denylist (.pii-denylist.local) is NOT touched, but script        ║
║    logic that calls it may change — review the diff manually first.         ║
║                                                                              ║
║  Run WITHOUT --yes to review diffs interactively before applying.           ║
║                                                                              ║
║  Proceeding in 8 seconds … Ctrl+C to abort.                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝"""

# ── argument handling ─────────────────────────────────────────────────────────

KNOWN_FLAGS = {"--yes", "-y", "--check", "--dry-run", "-n", "--help", "-h"}
USAGE = "usage: kb-update.py [--yes|-y] [--check|--dry-run|-n] [--help|-h]"
NO_TTY = ("Error: interactive mode needs a terminal, but stdin is not a tty.\n"
          "  Re-run with --yes to apply silently, or --check for a read-only dry-run.")

# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    unknown = [a for a in args if a not in KNOWN_FLAGS]
    if unknown:
        print(_colour(f"Error: unrecognised argument(s): {' '.join(unknown)}", "31"))
        print(USAGE)
        return 2
    if "--help" in args or "-h" in args:
        print(USAGE)
        return 0
    silent  = "--yes" in args or "-y" in args
    dry_run = "--check" in args or "--dry-run" in args or "-n" in args

    # interactive mode needs a real terminal — refuse before cloning or touching anything
    if not silent and not dry_run and not sys.stdin.isatty():
        print(_colour(NO_TTY, "31"))
        return 3

    script_dir = os.path.dirname(os.path.abspath(__file__))
    current_ver = _current_version(script_dir)

    print(f"kb-update  |  current version: {_colour(current_ver, '33')}")
    print(f"           |  directory: {script_dir}")
    print()

    if silent and not dry_run:
        print(_colour(SILENT_WARNING, "33"))
        print()
        try:
            for i in range(8, 0, -1):
                print(f"\r  {i}s …", end="", flush=True)
                time.sleep(1)
            print("\r         ")
        except KeyboardInterrupt:
            print("\nAborted.")
            return 1

    # clone the kit into a temp dir
    tmp = tempfile.mkdtemp(prefix="kb-update-")
    try:
        print("Fetching latest kit …")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", REPO_URL, tmp],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(_colour(f"Error: git clone failed:\n{result.stderr}", "31"))
            return 2

        kit_tool_dir = os.path.join(tmp, REPO_TOOL)
        remote_ver   = _remote_version(kit_tool_dir)
        print(f"           |  remote version:  {_colour(remote_ver, '32')}")
        print()

        # collect *.py files present in the kit's tooling/
        kit_scripts = sorted(
            f for f in os.listdir(kit_tool_dir)
            if f.endswith(".py") and os.path.isfile(os.path.join(kit_tool_dir, f))
        )

        changed, new_files = [], []
        for name in kit_scripts:
            local = os.path.join(script_dir, name)
            remote = os.path.join(kit_tool_dir, name)
            diff = _unified_diff(local, remote, name)
            if diff:
                (new_files if not os.path.exists(local) else changed).append((name, local, remote, diff))

        if not changed and not new_files:
            print(_colour("✓ Already up to date.", "32"))
            if not dry_run:                       # --check is strictly read-only
                _write_version(script_dir, remote_ver)
            return 0

        total = len(changed) + len(new_files)
        print(f"  {total} script(s) would change "
              f"({len(changed)} updated, {len(new_files)} new):\n")
        for name, *_ in changed + new_files:
            tag = _colour("NEW", "32") if (name, *_) in new_files else _colour("UPD", "33")
            print(f"  [{tag}]  {name}")
        print()

        if dry_run:
            # show full diffs then exit
            for name, local, remote, diff in changed + new_files:
                print(_colour(f"── {name} " + "─" * (60 - len(name)), "36"))
                _print_diff(diff)
                print()
            return 1  # exit 1 = updates exist (useful in CI)

        # interactive or silent apply
        applied = 0
        accept_all = silent

        for name, local, remote, diff in changed + new_files:
            print(_colour(f"── {name} " + "─" * (60 - len(name)), "36"))
            _print_diff(diff)
            print()

            if accept_all:
                shutil.copy2(remote, local)
                print(_colour(f"  ✓ applied {name}", "32"))
                applied += 1
                continue

            while True:
                try:
                    choice = input("  Apply? [y]es / [n]o / [a]ll / [q]uit  > ").strip().lower()
                except EOFError:
                    print()
                    print(_colour(NO_TTY, "31"))
                    return 3          # stop here — pin stays at the previous version
                if choice in ("y", "yes"):
                    shutil.copy2(remote, local)
                    print(_colour(f"  ✓ applied", "32"))
                    applied += 1
                    break
                elif choice in ("n", "no"):
                    print("  skipped.")
                    break
                elif choice in ("a", "all"):
                    shutil.copy2(remote, local)
                    print(_colour(f"  ✓ applied (switching to apply-all)", "32"))
                    applied += 1
                    accept_all = True
                    break
                elif choice in ("q", "quit"):
                    print("Quit — no further files applied.")
                    if applied == total and not dry_run:
                        _write_version(script_dir, remote_ver)
                    else:
                        print(f"  Applied {applied}/{total} — version pin left at {current_ver}.")
                    return 0

            print()

        if applied == total:
            if not dry_run:
                _write_version(script_dir, remote_ver)
            print(_colour(f"Done. Applied {applied}/{total} script(s). "
                          f"Version: {current_ver} → {remote_ver}", "32"))
        elif applied:
            # partial apply — the pin would lie about what's on disk, so leave it alone
            print(_colour(f"Done. Applied {applied}/{total} script(s); "
                          f"{total - applied} skipped.", "33"))
            print(f"  Version pin left at {current_ver} (re-run to finish updating).")
        else:
            print("No scripts applied.")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return 0

def _write_version(script_dir: str, version: str) -> None:
    with open(os.path.join(script_dir, VERSION_FILE), "w") as f:
        f.write(version + "\n")

if __name__ == "__main__":
    sys.exit(main())
