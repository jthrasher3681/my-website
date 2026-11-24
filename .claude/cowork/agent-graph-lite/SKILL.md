---
name: agent-graph-lite
description: Plan-check-track method for multi-step knowledge work (research briefs, reports built from several sources, batches of drafts, data cleanup). Use on your own initiative, without being asked, when a task has 3+ distinct steps, pulls from several sources, produces something John will send, publish or rely on, or is likely to take more than one session. Skip it for quick questions, single edits and short replies.
---

# Agent graph (lite)

A light version of a Claude Code "agent graph" method (adapted from
Karpathy's autoresearch ideas): define done first, split the work, check
every piece against evidence, and keep a progress file so the work can be
resumed.

## When to use it (decide yourself)

Use it when the task has 3+ distinct steps, draws on several sources or
files, produces something that will be sent, published or acted on, or
won't finish in one sitting. Say so in one line when you start
("Treating this as a multi-step job: plan below.").

Skip it for quick questions, single edits and short replies.

## Steps

1. **Define done.** Before working, write a short completion checklist.
   Each item must point to something observable (a file exists, every
   figure has a cited source, every draft has a recipient and subject).
2. **Split the work** into small pieces, each with one input, one output
   and one check. Note which pieces don't depend on each other; use
   subagents for those if available. For larger jobs (5+ pieces), show the
   plan and wait for approval before starting.
3. **Use code for exact steps.** Counting, sorting, deduping, merging and
   comparing are done with a script or formula, not by eye.
4. **Check each piece on evidence** in a `checks.md` table:
   `piece | requirement | pass / fail / unresolved | evidence`.
   Evidence means a source link, file path or actual output, not "looks
   right". Leave missing evidence visible.
5. **Fix only what failed.** Rework the failed piece only, at most 3
   tries, then report it as unresolved.
6. **Keep `progress.md`** in the working folder: what's done, what's
   left, decisions made, open issues, next step. When resuming, read it
   first.
7. **Deliver honestly:** the output, plus what was checked, what passed
   and what's still unresolved. Don't make up time or cost savings.

## Guardrails

- Drafts only: ask before sending, publishing, sharing, spending or
  deleting anything.
- Keep a copy of any file before making large changes to it.
- Anything waiting on John goes on the open-decisions ledger if that
  skill is available.
