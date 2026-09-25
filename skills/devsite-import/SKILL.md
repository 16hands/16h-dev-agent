---
name: devsite-import
description: Use when someone wants a site that runs on their own machine put onto a 16h devsite — "put this on a devsite", "put this WordPress on a devsite", "give me a staging URL for this", "host this so the client can look at it" — or wants to push a later change to one they already made, as in "push my changes", "send the fix to the devsite", "redeploy the devsite". Covers finding the real site root, collecting the local facts, the plan → confirm questions, building the upload parts, and the push, with site_plan, site_create, site_push and site_status.
---

# Put a local site on a devsite

```
new:    site root → local_facts → site_plan → questions → site_create → build → upload → site_push → poll
later:  site_plan(…, site_key) → questions → build → upload → site_push(…, answers) → poll
```

Read `references/wordpress.md` or `references/laravel.md` before step 1.

## Doctrine — the part people get wrong

- **Never call a write tool without asking.** `site_create` and `site_push`
  change hosting; `site_plan` and `site_status` are reads.
- **Defaults first** — you are confirming, not interviewing.
- **One question per message**, in `questions[]` order, showing the default.
- **Ask every question the plan returns** — one skipped is refused, one invented is a lie in the audit record.
- **One plan, one confirmation.** On `expired` or `defaults changed`, call
  `site_plan` again; never retry a spent `plan_id`.
- **A refusal is the truth about your access** and names the next move.

## Step 1 — find the RUNNING site root, not the repo

| Setup | Site root |
|---|---|
| Classic WordPress | the directory holding `wp-config.php` and `wp-content/` |
| Bedrock | `web/` beside a `composer.json` that requires `roots/wordpress` |
| Local (by WP Engine) | `~/Local Sites/<name>/app/public` |
| Herd / Valet / DDEV | the linked or parked dir (`herd links`), or `docroot` in `.ddev/config.yaml` |
| Laravel | the directory holding `artisan` (the app root, not `public/`) |

The upload takes this folder, not the repo. Say which one you picked.

## Step 2 — classify the git state of that folder

`git rev-parse --show-toplevel`, `git remote get-url origin`, then:

| Shape (`git.shape`) | Spot it by | Pull-deployable | What you may offer |
|---|---|---|---|
| `whole_tree` | `wp-config.php` + `wp-content/` + `.git` at the root | yes | git question, default no |
| `bedrock` | `composer.json` requires `roots/wordpress`, `web/app/` exists | yes, once builds land | git question — say the build step is wave 2 |
| `wp_content_only` / `theme_only` | `themes/` + `plugins/`, or a `Theme Name:` `style.css`, with no `wp-config.php` above | no | **do not mention git** — upload only |

Git is never required and the first push is always an upload; with no `.git`
(`none`) or no `origin` (`no_remote`), say nothing about git at all.

## Step 3 — collect `local_facts`

WordPress, from the site root (Laravel equivalents are in its reference):

```bash
folder_name="$(basename "$PWD")"
siteurl="$(wp option get siteurl)"
php_version="$(wp --info --format=json | jq -r .php_version | cut -d. -f1,2)"
db_size_bytes="$(wp db size --size_format=b)"
uploads_size_bytes=$(( $(du -sk wp-content/uploads | cut -f1) * 1024 ))
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

Keys, exactly: `folder_name`, `siteurl`, `php`, `db_size_bytes`,
`uploads_size_bytes`, `code_size_bytes`, `git` = {`present`, `remote_url`,
`branch`, `shape`}; what you could not measure goes as `null`, never a guess.
Then `site_plan(client?, app, local_facts)`, `app` = `wordpress`|`laravel`.

## Step 4 — ask the plan's questions, then create

- `site_name` — `<slug>.devsite.co.nz`, and `php` — the pool
- `include_database`, and `include_uploads` — `wp-content/uploads`, size shown
- `rewrite_urls` — the local URL → the devsite URL
- `git_pull` — deploy from the remote on push? (only when step 2 allows)

`site_create(plan_id, answers)` returns `site_key`, `url` and an `uploads` map
of presigned POSTs (`code`, `database`, `uploads`).

## Step 5 — `.deployignore`, then build the parts

Write `.deployignore` in the site root if it is absent, and show it.

- WordPress: `wp-content/uploads/`, `wp-content/cache/`, `wp-content/upgrade/`, `node_modules/`, `.git/`, `.env`, `wp-config.php`
- Laravel: `vendor/`, `node_modules/`, `storage/`, `.env`, `.git/`

`wp-config.php` and `.env` are excluded on purpose — the platform writes its
own. Build only the parts answered yes.

```bash
zip -r -q code.zip . -x@.deployignore
wp db export - | gzip > database.sql.gz
zip -r -q uploads.zip wp-content/uploads
```

## Step 6 — upload to the presigned POSTs

Each entry has `url` and `fields`. **One `-F name=value` per returned field, and `-F file=@<part>` LAST** — S3 ignores anything after `file`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$upload_url" \
  -F key="$field_key" -F policy="$field_policy" -F ... -F file=@code.zip
```

`204` is success. URLs live one hour; caps are code 2 GiB, database 1 GiB, uploads 2 GiB — over cap, answer no to that part and re-plan.

## Step 7 — push, then poll

**Whenever `parts` includes `database` on a site that exists, say this first and wait for a yes:**

> This replaces the whole database on `<site>`. If it is WooCommerce that includes
> orders, product changes and customer data. The previous database is kept as a restore point.

`site_push(site_key, plan_id, parts)` returns a `task_id`. Then
`site_status(site_key, task_id?)` **every 10 seconds** (not `curl` — see the 16h-dev-agent skill's HTTP rule):

| `state` | Means | Do |
|---|---|---|
| `planned` | plan made, not confirmed | call `site_create` |
| `requested` | the site is being created | wait |
| `accepted` | site and database exist | upload, then `site_push` |
| `refused` | creation was refused | read `message`; re-plan or stop |
| `pushing` | the deploy lane is running | keep polling |
| `applied` | live on the devsite URL | hand back `url` + `wp_admin_login_url` |
| `failed` | the lane stopped | read `message` verbatim; fix; push again |

`wp_admin_login_url` appears only after `applied` and is one-shot — hand it over, do not open it yourself.

## Push a later change to a devsite that exists

Same verbs, one more argument. **Never plan by folder name for a site that is
already there** — that refuses `name … is taken`, which is true and useless.

1. `site_plan(app, local_facts, site_key="<the devsite>")` → a plan with
   `kind: "update"` and its own `uploads` map. The name and the PHP version
   are the site's and are not asked.
2. Ask what it asks. `include_database` defaults to **no** and its text
   carries the warning above — read it out. `include_uploads` appears only
   when you have uploads; `rewrite_urls` only when your local URL differs.
3. Build and upload the parts answered yes (steps 5 and 6) — the POSTs came
   back with the plan, and `site_create` here is refused with
   `plan … updates an existing site — call site_push`.
4. `site_push(site_key, plan_id, parts, answers)` — **every** answer, or it
   refuses and names the missing one; `database` in `parts` needs
   `include_database: true`. Then poll `site_status` exactly as above.

## Going live

Never from here — no tool does it, by design. Say the devsite is ready, and that going live is a click in the 16h panel.
