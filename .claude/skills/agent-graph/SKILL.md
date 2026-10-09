---
name: agent-graph
description: Run multi-step work as a graph of small, checked nodes, with graph.md, checks.md and progress.md so any session can resume it. Use on your own initiative, without being asked, when a task has 3+ distinct steps, touches more than one sub-site or several files, produces a deliverable that needs verification (build, render, data pipeline, video timeline), or is likely to span sessions. Do NOT use for questions, single-file edits, copy fixes or other quick changes.
---

# Agent graph

The full prompt this skill is built from is in `template.md` next to this
file. Read it when you start a graph. This file covers when to use it and
how to run it in this repo.

## When to use it (decide yourself, don't wait to be asked)

Use it when **any** of these is true:
- 3 or more distinct steps, or parts that could run in parallel
- Changes span more than one sub-site (`calorie-tracker`, `daily-market-brief`,
  `perkpoints`, `quest`, `tobacco-briefing`, root `index.html`) or many files
- The output needs real verification (pages render, a pipeline produces
  the right files, a timeline matches the takes)
- The work probably won't finish in one session

Skip it for questions, one-file edits, copy or typo fixes, and anything you
could finish and verify in a few minutes. If unsure, use the light form:
a completion checklist plus `checks.md`, with no subagents.

When you use it, tell the user in one line ("Running this as an agent
graph: N nodes, plan below.").

## How to run it here

1. **Fill the inputs** (TASK, OUTPUT, CHECKS, SOURCES, SCOPE, LIMIT) from the
   request and the repo. Ask one focused question only if a missing detail
   changes the outcome.
2. **Baseline first.** Record the current state before changing anything
   (what renders, what's broken, existing file counts).
3. **Write the graph** to `.agent-graph/<task-slug>/graph.md`: nodes, edges,
   which nodes run in parallel, and the code nodes. Show it to the user and
   **pause for approval**. This is the only stop the framework requires;
   after approval, run to completion.
4. **Run nodes.** Judgment nodes go to subagents (Agent tool) with only the
   node spec, its inputs and its check. Deterministic steps (link checks,
   counting, sorting, diffing, file manifests) are scripts, not subagents.
   No two nodes edit the same file.
5. **Gate on evidence** in `.agent-graph/<task-slug>/checks.md`:
   `node | requirement | verdict | evidence`. Deterministic checks first.
   For pages, the standard gate is: load in headless Chromium
   (Playwright, `/opt/pw-browsers/chromium`), no console errors, screenshot
   saved as evidence.
6. **Correction edge:** a failed node goes back with the reason and "fix this
   node only", at most 3 attempts, then it's reported as unresolved.
   **Learning edge:** write any rule an accepted result proves into graph.md.
7. **Handoff:** update `.agent-graph/<task-slug>/progress.md` after each
   stage (done/running/blocked, output paths, decisions, open issues, next
   node). Commit these files with the work. Cloud sessions are ephemeral,
   so uncommitted state is lost.
8. **Deliver:** the output plus the three files. Say plainly what passed and
   what remains unresolved. Never weaken a gate to get a pass, and never
   make up time or cost savings.

## Guardrails

- Ask before publishing, sending, spending, or pushing anything that
  goes live on jthrashercompanies.com outside the agreed scope.
- Commit a recoverable version before risky merges.
- On resume, read graph.md and progress.md first and continue from the
  recorded next node.
- `.agent-graph/` starts with a dot, so GitHub Pages won't publish it.
