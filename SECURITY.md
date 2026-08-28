# Security

## Vault hygiene (users of this kit)

A knowledge vault can be sensitive: it may catalog internal systems, prod topology, and security
findings. A few rules regardless of whether your vault is public or private:

- **Keep real vaults in private repositories.** Never push a project vault to a public remote.
- **Never commit secrets.** Tokens, keys, and credentials belong in a secret manager — never in a
  shard, never in `reference/` distillates. Redact values (`sk-…`, `TOKEN=…`) when a finding must
  reference one.
- **Treat `reference/` distillates carefully** — they concentrate the most sensitive knowledge.
- **Scope git to the vault** when a workspace holds secrets or nested repos: `git init` at the root
  with a whitelist `.gitignore` that tracks the vault, its wiring, and the generated agent-context
  files — excluding `_meta/`, `repos/`, and heavy dirs.
  [setup/workspace.gitignore](setup/workspace.gitignore) is the canonical list (don't restate it);
  see also [tooling/README.md](tooling/README.md).

## What the tooling does (and doesn't) protect

- `kb-fix` / `kb-lint` / `kb-links` gate **schema, Obsidian-safety, and link rot** — they do **not**
  scan for secrets. Secret hygiene is your responsibility; review every diff.
- The impact eval keeps secret-bearing traps in a git-ignored `tooling/kb-eval/traps.local.jsonl`,
  and `tooling/kb-eval/results/` is git-ignored. Only a redacted `traps.jsonl` example is committed.
- Before publishing or sharing any vault derivative, scan for prod identifiers, tokens, and absolute
  paths (e.g. `grep -rIE 'sk-[A-Za-z0-9]{20}|ghp_|AKIA|PRIVATE KEY|TOKEN='`).
- `tooling/pii-scan.py` is a mechanical guard for kit contributors — run it before pushing to this
  repo to catch session URLs, home paths, and common secret patterns.

## Reporting a vulnerability in this kit

If you find a security issue in the carryover tooling itself, please **open a GitHub Security
Advisory** (the "Report a vulnerability" button on the Security tab) rather than a public issue.
Include steps to reproduce and the impact. We'll respond as quickly as we can.

If that button isn't available to you, don't stop there and don't post the details publicly: open a
regular issue saying only that you have a security report and asking for a private channel — no
exploit details, no reproduction steps — and we'll open one from our side.
