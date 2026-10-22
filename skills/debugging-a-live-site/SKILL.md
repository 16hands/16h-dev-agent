---
name: debugging-a-live-site
description: Use when a 16h-hosted site is misbehaving — "it's erroring", "the site is down", "slow", "500", "customers can't check out", "a client emailed", "why is the site 500ing" — before any code is changed.
---

# Debugging a live site

**No code change until the error is named from `logs_read`.** An error you cannot find in the logs is one you have not reproduced, and fixing the most likely-looking thing is a guess.

`references/triage.md` is the whole recipe — email to fix, in order. In short:

1. **Site and window.** Get both out of the report, and ask for whichever is missing. `minutes` counts back from now, with slack on both sides (triage §1).
2. **Read the errors.** `logs_read` with the client key, `site=<site_key>`, `kind: "errors"` and that window. Read the `summary` lines first and count them; pull `message` for a full stack trace once you know which error matters. The first call's `errors_last_hour` points the way but is not the evidence: with `at_cap: true` its count is only a floor.
3. **Read the `node` field before concluding.** The same error on every node is a code or data problem; on one node it is that machine, and that is a 16Hands job, not a code change.
4. **Read the kind the report is about.** "Slow", "down", "our emails are bouncing", "the import didn't run": `access`, `mail` or `cron` as well (triage §3, and `reading-traffic`), never inferred from a stack trace. `site_status`'s `http` says whether the site answers at all.
5. **One hypothesis, out loud.** Name the error, the code path and why the client's action reaches it. If the logs do not support one, say so and ask for a reproduction.
6. **Fix it locally**, then `pushing-to-staging` for the client to check — never straight to their live site. Production is `releasing-to-production`, when the developer says so.

## When the error is named, write it down

Write `docs/16h/investigations/<YYYY-MM-DD>-<site_key>-<slug>.md` — today's date, the site the error is on, a few words of the error as the slug (`2026-10-22-shop.example.co.nz-checkout-null-cart.md`) — and tell the developer its path. Fill in *What changed / ruled out* once the fix is in.

```markdown
# <the error, in one line> — <site_key>

## Report
Who reported what, and when; the window you read.

## Evidence
The `logs_read` lines: each `summary`, how many times, which nodes, first and last seen.

## Hypothesis
The error, the code path, and why the client's action reaches it.

## What changed / ruled out
The fix and where it was pushed, or what was ruled out and how.
```

A glance at the logs that names nothing writes nothing.
