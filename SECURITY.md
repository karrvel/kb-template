# Security & handling

This kit produces **knowledge vaults**, and a good vault is sensitive: it can catalog internal
systems, prod topology, and security findings — effectively a map of how to attack your own
production. Treat both the kit and anything built with it as **confidential** (see [LICENSE.md](LICENSE.md)).

## Rules for anyone using this kit

- **Keep real vaults in private repositories.** Never push a project vault to a public remote.
- **Never commit secrets.** Tokens, keys, and credentials belong in a secret manager — never in a
  shard, never in `reference/` distillates. Redact values (`sk-…`, `TOKEN=…`) when a finding must
  reference one.
- **Treat `reference/` distillates as confidential** — they concentrate the most sensitive knowledge.
- **Scope git to the vault** when a workspace holds secrets or nested repos: `git init` at the root
  with a whitelist `.gitignore` that tracks only `_knowledge/` (+ `CLAUDE.md`), excluding `_meta/`,
  `repos/`, and heavy dirs. See [tooling/README.md](tooling/README.md).

## What the tooling does (and doesn't) protect

- `kb-fix` / `kb-lint` / `kb-links` gate **schema, Obsidian-safety, and link rot** — they do **not**
  scan for secrets. Secret hygiene is the author's responsibility; review every diff.
- The impact eval keeps secret-bearing traps in a git-ignored `tooling/kb-eval/traps.local.jsonl`,
  and `tooling/kb-eval/results/` is git-ignored. Only a redacted `traps.jsonl` example is committed.
- Before publishing or sharing any derivative, scan for prod identifiers, tokens, and absolute paths
  (e.g. `grep -rIE 'sk-[A-Za-z0-9]{20}|ghp_|AKIA|PRIVATE KEY|TOKEN='`).

## Reporting

If you find committed secrets, an exposure, or a vulnerability in the tooling, **contact the author
(karrvel) privately**. Do not open a public issue or disclose details publicly.
