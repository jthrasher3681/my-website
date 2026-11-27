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

## Business card QR code (John, 2026-11-27)

John: "add a qr code to the business card that takes them to our website, and
remember to update this if/when we change to a different website".

- The QR code on the printed card points to `https://jthrashercompanies.com/card/`.
  That page (`card/index.html`) only forwards the visitor to the current website.
- Printed cards cannot be changed. Never delete, rename or move `card/`.
- **Whenever the business website moves** (a new page, a new domain, a rename of
  `local/`), update the forward target in `card/index.html` in the same change,
  then scan-test it. Tell John if the domain jthrashercompanies.com itself is
  ever to be dropped: every printed card would stop working.

## How to approach work

- For multi-step tasks, use the `agent-graph` skill
  (`.claude/skills/agent-graph/`) **on your own judgment**. The user should
  not have to ask for it. The skill says when it applies and when to skip it.
- For small tasks, just do them and verify them.
- A light version for Claude Cowork is in `.claude/cowork/agent-graph-lite/`.
  The user uploads it as a skill in the Claude app; it is not used here.
