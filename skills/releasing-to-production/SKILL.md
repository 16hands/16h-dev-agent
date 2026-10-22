---
name: releasing-to-production
description: Use when the developer says the change should go live — "deploy to prod", "go live", "ship it", "push to production", "release this".
---

# Releasing to production

A production push replaces what the client's customers are using. The gate: **no production push until the developer has heard every line of `what_will_change` and said yes to it.**

```
toggle → site_plan(type=production) → read what_will_change → questions → their yes → build → upload → site_push(confirm, digest) → verifying-a-deploy → release note
```

## 1. The site and its toggle

The site is the `production` that `site_status` named, or the one the developer names; say which. Its `agent_production_pushes: false` means agent pushes to it are off: say so — the site's owner turns them on in the panel — and stop without planning.

## 2. Plan

`site_plan(client?, type: "production", site_key, app, local_facts)`, with `local_facts` collected as `pushing-to-staging` step 3 does. It returns `plan_id`, `what_will_change`, `questions`, `defaults`, `refusals` and `digest`. A plan lives 30 minutes.

A refusal here names the gate, and the push stops until someone else moves it:

- `agent pushes to <site> are off — the site's owner turns them on in the panel`
- `production needs the agent:production scope — ask the client's owner`

## 3. Read it to the developer

Every line of `what_will_change`, in words:

- `parts` — what the push carries at the plan's defaults: `code`, and `database` only after a yes below.
- `current_release` — the release serving now; `null` means the platform cannot say, never that there is none.
- `restore_point` — `true`: the platform keeps a restore point of what is live now.
- `database_replaced` — whether the live database is replaced.

Then the plan's questions, in order:

- **`include_database`** (WordPress only), default **no**. Read its text, and say what yes means on a live site: every order, customer and form entry made since your local copy was taken is replaced by that copy; the current database is kept as a restore point. A yes adds `database` to `parts` and makes `database_replaced` true — say both back.
- **`confirm`**, default no. Only the developer's own yes to what you just read answers it.

## 4. Build, upload, push

Build the parts answered yes and upload them to the plan's `uploads`, as `pushing-to-staging` steps 5 and 6 do. A plan with no `uploads` cannot carry a part yet, and `site_push` refuses it (`part code is not in plan`): say that this is a gap to report to 16Hands, and stop.

`site_push(site_key, plan_id, parts, confirm: true, digest, include_database)`, with `digest` exactly as the plan returned it, and `include_database` only when the plan asked it — on a Laravel plan it is refused as a question the plan never asked. It returns a `task_id`; then `verifying-a-deploy`, five-minute look included.

Refused at push time:

- the plan changed since the developer read it, or it expired — `site_plan` again and read the new `what_will_change`; never send an old digest.
- no `confirm` or no `digest` — send them, with `confirm: true` only on the yes you already have.
- the toggle or the scope — they can be switched off between plan and push: say so and stop.

## 5. The release note

After `applied`, write `docs/16h/releases/<YYYY-MM-DD>-<site_key>.md` from `references/release-note.md` and tell the developer its path. It records the digest, the `what_will_change` the developer heard and `verifying-a-deploy`'s `http` and `errors_last_hour` answers; never a credential or a pasted secret. A push that ends `failed` leaves the previous release serving and writes no note: read its `message` out.
