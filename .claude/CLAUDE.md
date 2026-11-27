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

## Business card addresses (John, 2026-11-27)

John: "add a qr code to the business card that takes them to our website, and
remember to update this if/when we change to a different website". The same
evening he asked for a shorter printed address ending in `/localmotive`.

Two addresses are printed on the card. Printed cards cannot be changed, so both
must keep working:

- **The printed text** ends in `/localmotive`. It is typed by hand and arrives
  here as `/localmotive` (the service page, `localmotive/index.html`).
- **The QR code** ends in `/card/`. It arrives here as `/card/`. That page
  (`card/index.html`) only forwards the visitor to the current page.

Both are printed on a short domain that redirects every address to the same
path on this site.

Rules:

- Never delete, rename or move `card/` or `localmotive/`. `local/` was the page's
  first address and forwards to `/localmotive/`; keep it too.
- `404.html` sends mistyped forms (capital letters, a hyphen, a doubled path) to
  `/localmotive/`. Keep that script if the 404 page is ever redesigned.
- **Whenever the business website moves** (a new page, a new domain), keep
  `/localmotive/` and `/card/` working: make them forward to the new place in the
  same change, then type the printed address and scan the QR code to test.
- Tell John if the short domain printed on the card is ever to be dropped or
  left to expire, or if this site is to move off jthrashercompanies.com before
  the short domain's redirect has been pointed at the new place: the printed
  cards would stop working.

## How to approach work

- For multi-step tasks, use the `agent-graph` skill
  (`.claude/skills/agent-graph/`) **on your own judgment**. The user should
  not have to ask for it. The skill says when it applies and when to skip it.
- For small tasks, just do them and verify them.
- A light version for Claude Cowork is in `.claude/cowork/agent-graph-lite/`.
  The user uploads it as a skill in the Claude app; it is not used here.
