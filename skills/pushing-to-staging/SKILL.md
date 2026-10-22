---
name: pushing-to-staging
description: Use when the developer wants their change somewhere they can look at it before it goes live — "put this on staging", "push my changes", "give me a devsite", "I want to see it before it goes live", "send the fix to the devsite".
---

# Push to staging

## The target

`site_status`'s `before_production` is the site to push to: its `site_key`, `type` and `url`. The developer says "staging"; 16h has two kinds, so read back which one this is:

- **A devsite** — `<name>.devsite.co.nz`, built from your repo with its own database. This is what `before_production` names today.
- **A staging clone of production** — `site_plan` still refuses `type: staging`, so the fallback is a devsite.

`before_production: null` means there is none yet: create a devsite (*new*). A named site takes a later change (*later*).

```
new:    site root → local_facts → site_plan → questions → site_create → build → upload → site_push → verifying-a-deploy
later:  site_plan(…, site_key) → questions → build → upload → site_push(…, answers) → verifying-a-deploy
```

Read `references/wordpress.md` or `references/laravel.md` before step 1.

## Doctrine — the part people get wrong

The rules for every 16h call are in `using-16h`. Two more hold for a push:

- **Ask every question the plan returns** — one skipped is refused, one invented is a lie in the audit record.
- **One plan, one confirmation.** On `expired` or `defaults changed`, call `site_plan` again; never retry a spent `plan_id`.

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

Git is never required and the first push is always an upload; with no `.git` (`none`) or no `origin` (`no_remote`), say nothing about git at all.

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

Keys, exactly: `folder_name`, `siteurl`, `php`, `db_size_bytes`, `uploads_size_bytes`, `code_size_bytes`, `git` = {`present`, `remote_url`, `branch`, `shape`}; what you could not measure goes as `null`, never a guess. Then `site_plan(client?, app, local_facts)`, `app` = `wordpress`|`laravel`.

The name comes from `folder_name`. A taken one is refused with two others — `name X.devsite.co.nz is taken — try X2.devsite.co.nz or X-<client>.devsite.co.nz`. If the taken name is one of `site_status`'s `devsites`, or the project itself with `type: dev`, it is the developer's own site: take the *later* path with that `site_key`, never a second devsite. Only otherwise offer the two names, the first as the default, ask once, and plan again with `folder_name` set to the label they chose (`X2`). `site_key` on `site_plan` means a site that already exists, so it cannot pick a new name.

## Step 4 — ask the plan's questions, then create

- `site_name` — `<slug>.devsite.co.nz`, and `php` — the pool
- `include_database`, and `include_uploads` — `wp-content/uploads`, size shown
- `rewrite_urls` — the local URL → the devsite URL
- `git_pull` — deploy from the remote on push? (only when step 2 allows)

`site_create(plan_id, answers)` returns `site_key`, `url` and an `uploads` map of presigned POSTs (`code`, `database`, `uploads`).

## Step 5 — `.deployignore`, then build the parts outside the site root

Write `.deployignore` in the site root if it is absent; if it is there, add each line below that it lacks and rewrite any `dir/` line as `dir/*` — on Laravel, take a `vendor/` or `storage/` line out instead. Show it.

- WordPress: `wp-content/uploads/*`, `wp-content/cache/*`, `wp-content/upgrade/*`, `node_modules/*`, `.git/*`, `.env`, `wp-config.php`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip`
- Laravel: `node_modules/*`, `storage/logs/*.log`, `.env`, `.git/*`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip` — `vendor/` and `storage/` travel, for the reasons in its reference

Write a folder as `dir/*`: zip matches each pattern against file paths, so `dir/` leaves out only the folder's own entry and every file in it still goes in. `wp-config.php` and `.env` are excluded on purpose — the platform writes its own. The site serves whatever `code.zip` carries, so `docs/16h/*`, dumps and archives stay out: a dump in the tree is a dump anyone can download.

Build only the parts answered yes, in a fresh folder outside the site root — a part built in the site root rides in the next `code.zip`, and production serves it. Print the folder's path and use it in step 6, since the next command may run in a new shell:

```bash
parts_folder="$(mktemp -d)"; echo "$parts_folder"
zip -r -q "$parts_folder/code.zip" . -x@.deployignore
wp db export - | gzip > "$parts_folder/database.sql.gz"
zip -r -q "$parts_folder/uploads.zip" wp-content/uploads
```

## Step 6 — upload to the presigned POSTs, then delete the parts

Each entry has `url` and `fields`. **One `-F name=value` per returned field, and `-F file=@<part>` LAST** — S3 ignores anything after `file`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$upload_url" \
  -F key="$field_key" -F policy="$field_policy" -F ... -F file=@"$parts_folder/code.zip"
```

`204` is success. URLs live one hour; caps are code 2 GiB, database 1 GiB, uploads 2 GiB — over cap, answer no to that part and re-plan. Once every part has answered `204`, delete the folder: `rm -rf "$parts_folder"`.

## Step 7 — push, then verify

A new site takes a push once `site_status(site_key)` says `accepted`. `requested` means the site and its database are still being made; `refused` means they will not be — read `message`, re-plan or stop.

**Whenever `parts` includes `database` on a site that exists, say this first and wait for a yes:**

> This replaces the whole database on `<site>`. If it is WooCommerce that includes
> orders, product changes and customer data. The previous database is kept as a restore point.

`site_push(site_key, plan_id, parts)` returns a `task_id`. Then `verifying-a-deploy`: it polls with that `task_id`, reads every `state`, and hands back the URL and, for WordPress, the one-shot wp-admin login.

## Push a later change to a devsite that exists

Same verbs, one more argument. **Never plan by folder name for a site that is already there** — that refuses `name … is taken`, which is true and useless.

1. `site_plan(app, local_facts, site_key="<the devsite>")` → a plan with `kind: "update"` and its own `uploads` map. The name and the PHP version are the site's and are not asked.
2. Ask what it asks. `include_database` defaults to **no** and its text carries the warning above — read it out. `include_uploads` appears only when you have uploads; `rewrite_urls` only when your local URL differs.
3. Build and upload the parts answered yes (steps 5 and 6) — the POSTs came back with the plan, and `site_create` here is refused with `plan … updates an existing site — call site_push`.
4. `site_push(site_key, plan_id, parts, answers)` — **every** answer, or it refuses and names the missing one; `database` in `parts` needs `include_database: true`. Then `verifying-a-deploy`, as above.

**Going live** is `releasing-to-production`, never this skill.
