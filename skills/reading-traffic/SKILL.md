---
name: reading-traffic
description: Use when the question is about requests, bots, mail or cron — "who's hitting the site", "is it a bot", "what happened at 2pm", "are our emails going out", "did the cron run".
---

# Reading traffic

`logs_read` reads one client at a time, and its `kind` decides which record answers the question. Read the record, then answer: never infer traffic, mail or a job's outcome from a stack trace, or from a request you made yourself.

## Which kind answers which question

- **`access` — "who's hitting the site", "what happened at 2pm", "it's slow", "it's 502ing".** The lake's nginx rows, newest first: `timestamp`, `site`, `host`, `method`, `uri`, `status`, `request_time` (seconds), `client_ip`, `server_node`. Pass `site` to narrow to one site. They are rows, not totals: at most `limit` of them (50 unless you ask, 200 at most), so a wide window shows only its newest rows. Narrow `minutes` to the moment in question, and count what comes back before calling it a pattern.
- **`mail` — "are our emails going out", "they're bouncing".** The delivery outcome of the client's email, newest first: `event`, `from_domain`, `to_domain`, `smtp_status`, `diagnostic`. Addresses are hashed; the domain, the status and the diagnostic are what a bounce is chased with. It is the whole client's mail, not one site's.
- **`cron` — "did the cron run".** The client's last runs, newest first, whatever `minutes` says: `label`, `schedule`, `status`, `started_at`, `exit_code`, `elapsed_seconds`, `output_tail`. An `exit_code` of `null` is a job still running or one that was killed, and neither is a success.
- **`errors`** is the application's own voice. A fault to name is `debugging-a-live-site`.

## Is it a bot

The bot answer comes from `site_status(site_key)`'s `blocked_bots`: the user-agent substrings nginx answers 403 for this site (`fleet`, plus the site's own `site`, less what `site_allowed` lets through) and `bot_policy`, the site's choice per bot. The access rows carry `client_ip` but no user agent, so many requests from one address is a pattern to name, not proof of a bot. A request the WAF stopped never reached nginx and is not in `access` at all.

Never answer it with a bare `curl` from this machine: the WAF blocks that request itself, so the answer says nothing about the site or its bots.

## Windows

`minutes` counts back from now, 1440 at most, with slack on both sides, as `debugging-a-live-site`'s triage says: "just now" is 30, "at 2pm" is from an hour before 2pm to now, "this morning" is 480, "since yesterday" is 1440. A window too narrow returns nothing and reads as "nothing happened".
