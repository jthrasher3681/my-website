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

## Which session is this? (John, 2026-11-27)

John works in three sessions and sometimes starts work in the wrong one. He
asked for a tripwire in each of them:

- **1 · HEDGE FUND (trading)**: investing and markets.
- **2 · LOCAL MOTIVE (Google biz) + website**: the Local Motive service (the
  Google Business Profile work), its business cards and this website. These
  belong together in one session.
- **3 · SALES**: his sales work.

Find out which session you are from the session's own title (ask for this
session's details if you have a tool for it; otherwise ask John once). When
John starts work that belongs in another session, the first line of the reply
says which session it belongs in and asks whether to switch or carry on here;
do the work only after he answers. A quick question that can be answered in a
line or two is simply answered, with the same one-line note.

## Standing reminder: Local Motive (John, 2026-11-25; moved here 2026-11-27)

John: "let's really build on this idea. don't let me forget about this idea.
remind me about it everytime i visit this project unless i specifically tell
you to stop." On 2026-11-27 he asked for the reminder to live with the Local
Motive work instead of the trading project.

In the session titled **2 · LOCAL MOTIVE (Google biz) + website**, open the
first reply of every conversation with John, and the first reply of each new
day he writes, with one or two lines on Local Motive: where it stands and what
is waiting on him. Other sessions do not give this reminder.

The status is kept in the private notes file `ideas/local-audience.md` in the
alpha-screener repository, which that session has attached. Keep that file
current, and never copy its contents into this public repository. Stop only
when John specifically says so; then remove this section and note the date in
that file.

## How to approach work

- For multi-step tasks, use the `agent-graph` skill
  (`.claude/skills/agent-graph/`) **on your own judgment**. The user should
  not have to ask for it. The skill says when it applies and when to skip it.
- For small tasks, just do them and verify them.
- A light version for Claude Cowork is in `.claude/cowork/agent-graph-lite/`.
  The user uploads it as a skill in the Claude app; it is not used here.
