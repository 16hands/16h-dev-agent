---
name: verifying-a-deploy
description: Use when a push is running or has finished — after any push, or when asked "is it up?", "did that work?", "is the deploy done?".
---

# Verifying a deploy

A push is done when `site_status` says `applied` and the site answers, not when `site_push` returns.

## 1. Poll the push

`site_status(site_key, task_id)` **every ten seconds**, with the `task_id` that `site_push` returned, until `state` is `applied` or `failed`. The poll returns the push fields alone; a call without `task_id` pays for the whole situation, so keep that for step 2.

| `state` | Means | Do |
|---|---|---|
| `planned` | plan made, not confirmed | not pushed yet — back to `pushing-to-staging`, or `releasing-to-production` for production |
| `requested` | the site is being created | wait |
| `accepted` | site and database exist | upload, then `site_push` |
| `refused` | creation was refused | read `message`; re-plan or stop |
| `pushing` | the deploy lane is running | keep polling; when `message` changes, show it in one line |
| `applied` | live on `url`; `release` names the release it made live | step 2 |
| `failed` | the lane stopped, or the first-minute check put the code back (`deploy_state: flipped_back`); the previous release serves | read `message` verbatim; push a fix, or roll back (`pushing-to-staging`, *Roll back*) |

While `pushing`, the server reports its phases (unpacking, scanning, migrations, switching) in `message`: show each new one to the developer once, in the server's own words, and say nothing when it has not changed. The scan of a big `vendor/` takes about a minute, so a long "Scanning" line is the server working, not stuck.

While `pushing`, `steps` holds each step's state (`waiting`, `started`, `finished`, `failed`, `warned`, `off`). Keep showing `message` as above; when a step turns `failed`, name it beside `message`.

`wp_admin_login_url` comes after a WordPress push has `applied` (a rollback mints none), only to the identity that pushed, and it is one-shot: hand it over, do not open it yourself, and do not repeat it later. While `message` says the login is being minted, ask again in about twenty seconds.

## 2. Read the site

Once `applied`, one `site_status(site_key)` without `task_id`, and read two answers:

- **`http`** — the platform's own GET of `url`: `status`, `final_url`, `milliseconds`.
  - `blocked_at_waf: true` is the WAF's answer, not the site's; say so, and do not call the deploy broken.
  - `error: "timeout"` — no answer within 8 seconds.
  - A `401` from a password-protected devsite means it is up.
  - A production site never pushed to answers `502` until its first push.
  - Any other 4xx or 5xx is the site's own answer: `logs_read` has the reason (`debugging-a-live-site`).
- **`errors_last_hour`** — `count` and `top_summaries`, nginx errors included. It covers the whole hour, errors from before the push too, so compare it with the count before the push; if it moved, `logs_read` with `kind: "errors"` and `minutes` since `applied` shows what is new. With `at_cap: true` the count is a floor.

After a production push, read both again five minutes after `applied`: a fault that needs real traffic shows by then.

Then tell the developer: the URL, the `http` answer, the errors, and the wp-admin link when there is one.

## 3. New content, old code

A page the push added that answers 500 for a template or blueprint it cannot find, or a new route that answers 404, while the new content is there, can mean a server is still running the previous release. Check before calling it your bug: each error's path names the release it ran from (`…/releases/20261110-022817/…`); compare it with the poll's `release`.

- **The release the push applied:** the fault is in the push. `debugging-a-live-site`.
- **An older release, within a minute of `applied`:** the servers are still switching. Read the errors again in thirty seconds.
- **An older release a minute or more after `applied`:** the platform's fault, not the code's. **Do not push again**: a second push lands the same way. Tell the developer in one line: the release the push applied, the release the errors name, the `node`s they came from, and that it is for 16hands to fix.

## Checking over HTTP yourself

`http` is the check. Never a bare `curl`: every 16h site sits behind a WAF that blocks it (Bot Control), so a request with no browser `User-Agent` gets **403 from the load balancer**, and that 403 says nothing about the site. If you curl at all, send a full browser UA and follow redirects:

```bash
curl -sS -L -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15" \
  -o /dev/null -w '%{http_code} %{url_effective}\n' "https://$SITE/"
```

Read the answer with `site_status` beside it: a 403 with a full UA is the site's own (an empty docroot, an allow-list); a 500 is PHP, and `logs_read` has the reason. A short UA such as `Mozilla/5.0` is still blocked.
