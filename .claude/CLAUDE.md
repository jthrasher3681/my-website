# Project notes for Claude

This repo is the public site jthrashercompanies.com (GitHub Pages). Each
top-level folder is a separate mini-site. Files under dot-folders such as
`.claude/` and `.agent-graph/` are not published.

## Public site safety (John, 2026-11-25)

This repo, every branch and every past commit are public. Nothing published
here may compromise John's local machines or accounts:

- No local machine details: absolute paths (`/Users/…`, `/Volumes/…`),
  computer or drive names, local script names, or links to files that exist
  only on John's computers. Publish the file into the repo or leave it out.
- No account numbers, balances, positions, orders, private emails, API keys,
  tokens or passwords, and nothing from the private alpha-screener repo.
- No `.DS_Store`, `.env`, key or password files (`.gitignore` blocks them).
- Run `bash tools/public-check.sh` before every push to `main`. CI runs it on
  every push (`.github/workflows/public-check.yml`) and fails on a hit.
- Pages generated on John's Mac (such as the Quest tracker) get the same check
  before they are pushed.

## How to approach work

- For multi-step tasks, use the `agent-graph` skill
  (`.claude/skills/agent-graph/`) **on your own judgment**. The user should
  not have to ask for it. The skill says when it applies and when to skip it.
- For small tasks, just do them and verify them.
- A light version for Claude Cowork is in `.claude/cowork/agent-graph-lite/`.
  The user uploads it as a skill in the Claude app; it is not used here.
