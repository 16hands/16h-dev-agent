# Triage — a client emailed about an error

The recipe, in order. Do not skip to the code: the logs say which of the
plausible causes actually happened, and there is usually more than one.

## 1. Turn the email into a site and a time window

Two things have to come out of the email before any tool runs.

**Which site.** The client key is what `logs_read` takes; a client with more
than one site says which site in the same breath. If the email names neither,
ask — reading the wrong client's logs is both useless and recorded.

**What window.** Ask for it if it is not there — "this morning" is not a
window. Convert to minutes back from now and add slack on both sides:

- "just now" → `minutes: 30`
- "at 2pm" → count back from now to 2pm, then add an hour either side
- "this morning" → `minutes: 480`
- "since yesterday" → `minutes: 1440` (the maximum)

A window that is too wide costs nothing but reading. A window that is too
narrow returns nothing and looks like "no error".

## 2. Read the errors

```
logs_read(client: "<client key>", kind: "errors", minutes: <window>)
```

Entries come back newest first with `summary` (the first line), `message` (the
full trace, truncated) and `node`. Read every `summary` first and count them —
one exception ten thousand times and ten exceptions once are different
problems. The same error on every node is code or data; on one node it is that
machine, and that is a 16 Hands job, not a code change.

## 3. The access log — not available yet, so say so

```
logs_read(client: "<client key>", kind: "access", minutes: <window>)
```

refuses today: the only implemented kind is `errors`. `access` (which URL,
which status, how often), `mail` (a bounce) and `cron` are named by the tool
and will land later. So "the site is slow" and "our emails are bouncing" can
only be answered as far as the application's own errors go — say that plainly
instead of inferring traffic or mail from a stack trace.

## 4. Form ONE hypothesis and say it out loud

Name the error, the code path and why the client's action would reach it.
If the logs do not support a hypothesis, say so and ask for a reproduction —
do not fix the most likely-looking thing.

## 5. Fix it locally

Work in the repo, run the tests, confirm the fix addresses the error in the
log rather than something adjacent.

## 6. Push the fix to a devsite, never to their live site

`site_push` deploys to a **dev** site. If the client's site is production,
make a devsite from the local copy first (the `devsite-import` skill), push
the fix there, and give the client the URL to check. Pushing to production is
not something this agent can do.

```
site_push(site_key: "<devsite>", plan_id: "<plan>", parts: ["code"])
site_status(site_key: "<devsite>")   # every 10 s until applied or failed
```

## 7. Tell the client, with evidence

The error's summary, how many times it happened, which nodes it hit, what
caused it, what changed, and the devsite URL to look at. Not "should be fixed".
