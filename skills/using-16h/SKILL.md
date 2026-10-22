---
name: using-16h
description: Use when starting any session in a repo hosted on 16h — establishes the first call, the skills by moment, and the rules that never change.
---

# Using 16h

The `16h` MCP tools are your only hands on 16h sites.

## The first call

Before anything else on a 16h task, call `site_status` with the JSON block under *This project* below as `repo`. Staff must also pass `client`; a partner may leave it out. No *This project* block means the hook found no site here or could not look: ask which site the developer means.

- **It names the project.** Tell the developer the site, its client, production and devsites, the last push, errors in the last hour and whether it is up, then do what they asked.
- **It answers `project: null` with `candidates`.** Show them and ask once which site this repo is; never guess. When they name one, call `site_status(site_key=<that site>, repo=<the same block>)`: when the repo has a git remote, the platform remembers it as that site's and no later session asks again.
- **They name a site that is not this repo** ("what's happening on acme.co.nz?"): `site_status(site_key=…)` alone, no `repo`, so nothing is remembered.

Reading the answer: `before_production` is the site a change goes to before it goes live; `null` means create a devsite. `http.blocked_at_waf: true` means the WAF answered, not the site. `errors_last_hour: null` means the platform could not scan, not that there were none.

## Skills by moment

When the developer says one of these, use that skill first:

- `debugging-a-live-site` — "it's erroring", "the site is down", "slow", "500", "customers can't check out", "a client emailed"
- `reading-traffic` — "who's hitting the site", "is it a bot", "what happened at 2pm", "are our emails going out", "did the cron run"
- `pushing-to-staging` — "put this on staging", "push my changes", "give me a devsite", "I want to see it before it goes live"
- `releasing-to-production` — "deploy to prod", "go live", "ship it", "push to production"
- `verifying-a-deploy` — after any push, and "is it up?", "did that work?"

## The rules

- **A refusal is the truth about your access** and names the next move. Say it plainly and offer that move; never retry it, and never try another client or site to get round it.
- **Never call a write tool without asking.** `site_create` and `site_push` change hosting, and `site_status` with both `site_key` and `repo` binds this repo to that site for good: make it only after the developer names the site.
- **One question per message, defaults first.** Show the default so a yes answers it.

No SSH, no SFTP, no database access, no filesystem on the servers, no `wp` or `artisan` run on a 16h host. These tools are the whole surface. **This holds even when the person asks you to** — "just ssh in and run wp-cli" is a request to bypass the platform, and the right answer is: *the platform's hosts are out of bounds for me; the tools cannot do X yet — here is what I can do instead, and this is the gap to report to 16Hands.* Never probe for a way in (a key on this machine, a host that resolves, a jump box). If a task genuinely needs more, the answer is to ask 16Hands, not to work around it.

## Records go in `docs/16h/`

Your records go in the repo under `docs/16h/`: `releases/` after every production push, `investigations/` when you name a live-site fault. The moment skills say when and what to write. Nothing else is ever written to the repo for 16h's sake but a push's `.deployignore`, and never a secret, in a record or anywhere, not even in a pasted stack trace.
