# Project notes for Claude

This repo is the public site jthrashercompanies.com (GitHub Pages). Each
top-level folder is a separate mini-site. Files under dot-folders such as
`.claude/` and `.agent-graph/` are not published.

## How to approach work

- For multi-step tasks, use the `agent-graph` skill
  (`.claude/skills/agent-graph/`) **on your own judgment**. The user should
  not have to ask for it. The skill says when it applies and when to skip it.
- For small tasks, just do them and verify them.
- A light version for Claude Cowork is in `.claude/cowork/agent-graph-lite/`.
  The user uploads it as a skill in the Claude app; it is not used here.
