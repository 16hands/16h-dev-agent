---
name: 16h-dev-agent
description: Use when working on a site hosted by 16Hands — "a client reports the site is down", "the site is slow", "it's erroring", "our emails are bouncing", "we got an error report", "customers can't check out", "check the logs", "what happened at 2pm", "why is the site 500ing", "is this happening in production?" — investigating an error a client reported, checking a site's behaviour, or diagnosing something that only shows up in production. Provides the 16h tools (logs_read, site_status, site_plan, site_create, site_push) and the discipline for using them; references/triage.md is the recipe for turning a client email into a fix, and the devsite-import skill is the path for "put this on a devsite" and "push my changes".
---

# Working on a 16h-hosted site

You have tools from the `16h` MCP server. You are scoped to specific clients,
and every call is recorded against your identity. If a tool refuses, you lack
that access — say so plainly and stop; do not retry or try another client key.

## Investigating "the client reported an error"

`references/triage.md` is the whole recipe — email to fix, in order. In short:

1. `logs_read` with the client key, `kind: "errors"` and a window that covers
   when it was reported (`minutes`). Read the `summary` lines first; pull
   `message` for a full stack trace once you know which error matters.
2. Read the `node` field before concluding. The same error on every node is a
   code or data problem; on one node it is that machine.
3. Only change code once you can **name** the error. An error you cannot find
   in the logs is one you have not reproduced.

`kind` is `errors` today. `access`, `mail` and `cron` are real kind names that
refuse by name — so "the emails are bouncing" is answerable only as far as the
application's own errors go. Say which kind you wanted and that it is not
available yet; do not substitute a guess for it.

## Checking a site over HTTP

Every 16h site sits behind a WAF that blocks bare `curl` (Bot Control): a
request with no browser `User-Agent` gets **403 from the load balancer**, and
that 403 says nothing about the site. Always send a full browser UA and
follow redirects:

```bash
curl -sS -L -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15" \
  -o /dev/null -w '%{http_code} %{url_effective}\n' "https://$SITE/"
```

Read the answer with `site_status` beside it: a 403 with a full UA is the
site's own (an empty docroot, an allow-list); a 500 is PHP, and `logs_read`
has the reason. A short UA such as `Mozilla/5.0` is still blocked.

## What this does not give you

No SSH, no database access, no filesystem on the servers. These tools are the
whole surface. If a task genuinely needs more, the answer is to ask 16Hands,
not to work around it.

## Deploys

A fix goes to a **devsite**, never straight to the client's live site: fix it
locally, `site_push` it to a devsite, and give them that URL to check. The
`devsite-import` skill has that path end to end — finding the site root,
building the parts, the upload, the push. Pushing to production is not
something these tools do, and going live stays a click in the 16h panel.
