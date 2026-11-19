---
name: pushing-to-staging
description: Use when the developer wants their change somewhere they can look at it before it goes live — "put this on staging", "push my changes", "give me a devsite", "I want to see it before it goes live", "send the fix to the devsite". Also when a push failed or flipped back, or the developer says "roll it back", "undo that push".
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

Read `references/<app>.md` for the app the hook named (wordpress, laravel, statamic, symfony, phpapp, files). Read it before step 1.

| The hook's `app` | Read |
|---|---|
| `wordpress` | `references/wordpress.md` |
| `laravel` | `references/laravel.md` |
| `statamic` | `references/statamic.md` |
| `symfony` | `references/symfony.md` |
| `phpapp` | `references/phpapp.md` |
| `files` | `references/files.md` — only when the developer asks for a static site; the hook never names it |
| `drupal` | no reference: plan it; the platform answers with the wave it arrives in — say that sentence and stop |
| `joomla` | no reference: plan it; the platform answers with the wave it arrives in — say that sentence and stop |
| `null`, or no project block | find the root with step 1's table and take the row it matches; ask when none does |

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
| Statamic | the directory holding `artisan` and `please` |
| Symfony | the directory holding `bin/console` |
| Plain PHP app | the folder that holds the docroot (`.`, `public/` or `web/`) |
| Static site | the repo; the zip is the chosen build folder's contents |

The upload takes this folder, not the repo. Say which one you picked.

**When two layouts fit**, ask one question, the default first, never a menu of everything you found: a plain PHP app's docroot as `phpapp.md`'s *The docroot question* says, a static site's folder as `files.md` says. When the hook's `app` disagrees with what you see (a WordPress tree inside a Laravel `public/`) or with what the developer tells you (they call it Statamic, the hook said laravel), say what the hook found and ask which one the site is before `site_plan`: the app a site is created as is the app of every later push.

## Step 2 — classify the git state of that folder

`git rev-parse --show-toplevel`, `git remote get-url origin`. Whether to offer git is the plan's rule, not yours: ask `git_pull` only when the plan returns it. For laravel, statamic and symfony it comes whenever the repo has an `origin`, default yes — the repo is the app. For WordPress it comes only on the shapes the table marks pull-deployable, default no:

| Shape (`git.shape`) | Spot it by | Pull-deployable | Whether the plan asks |
|---|---|---|---|
| `whole_tree` | `wp-config.php` + `wp-content/` + `.git` at the root | yes | asks `git_pull`, default no |
| `bedrock` | `composer.json` requires `roots/wordpress`, `web/app/` exists | yes, once builds land | asks `git_pull`, default no, noting the build step is wave 2 — say so |
| `wp_content_only` / `theme_only` | `themes/` + `plugins/`, or a `Theme Name:` `style.css`, with no `wp-config.php` above | no | never asks: upload only, and say nothing about git |

Git is never required and the first push is always an upload; with no `.git` (`none`) or no `origin` (`no_remote`), say nothing about git at all.

## Step 3 — collect `local_facts`

WordPress, from the site root (every other app's are in its reference):

```bash
folder_name="$(basename "$PWD")"
siteurl="$(wp option get siteurl)"
php_version="$(wp --info --format=json | jq -r .php_version | cut -d. -f1,2)"
db_size_bytes="$(wp db size --size_format=b)"
uploads_size_bytes=$(( $(du -sk wp-content/uploads | cut -f1) * 1024 ))
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

Keys, exactly: `folder_name`, `siteurl`, `php`, `db_size_bytes`, `uploads_size_bytes`, `code_size_bytes`, `git` = {`present`, `remote_url`, `branch`, `shape`}, `docroot_guess` (copied from the project block's `docroot_guess` line; leave it out of `local_facts` when the block has no such line). Leave out any key you could not measure, never a guess; `git.present` is always sent, `true` or `false`. On WordPress, always send `siteurl`, `db_size_bytes` and `uploads_size_bytes`: the commands above measure all three, and one is left out only when its command failed, said to the developer. Without `siteurl` the plan asks no `rewrite_urls` question, and a database push imports the local URLs as they are. Then `site_plan(client?, app, local_facts)`, `app` = `wordpress`|`laravel`|`statamic`|`symfony`|`phpapp`|`files` — the hook's `app`, or `files` for a static site the developer asked for. For `drupal` or `joomla`, plan once with that `app`, read the refusal to the developer, and stop.

The name comes from `folder_name`. A taken one is refused with two others — `name X.devsite.co.nz is taken — try X2.devsite.co.nz or X-<client>.devsite.co.nz`. If the taken name is one of `site_status`'s `devsites`, or the project itself with `type: dev`, it is the developer's own site: take the *later* path with that `site_key`, never a second devsite. Only otherwise offer the two names, the first as the default, ask once, and plan again with `folder_name` set to the label they chose (`X2`). `site_key` on `site_plan` means a site that already exists, so it cannot pick a new name.

## Step 4 — ask the plan's questions, then create

**Show the tree.** `site_plan` returns `tree`, the steps this push will run in order. Show it to the developer once, verbatim, in a code block, before the questions: it is the plan, the way plan mode shows one. `steps` is the same list as data; a `gate` always runs.

- `site_name` — `<slug>.devsite.co.nz`, and `php` — the pool (not asked for `files`)
- WordPress: `include_database`, and `include_uploads` — `wp-content/uploads`, size shown
- WordPress: `rewrite_urls` — the local URL → the devsite URL
- Statamic: `include_content` — replace the site's `content/` and `users/` with the release's, default yes on a devsite
- phpapp: `docroot` — `.`, `public` or `web`, the plan's default (from `docroot_guess`) first
- `git_pull` — deploy from the remote on push? (only when the plan returns it, step 2)

`site_create(plan_id, answers)` returns `site_key`, `url` and an `uploads` map of presigned POSTs: `code` for every app, `database` and `uploads` for WordPress, `env` for laravel, statamic and symfony.

## Step 5 — `.deployignore`, then build the parts outside the site root

Write `.deployignore` in the site root if it is absent; if it is there, add each line below that it lacks and rewrite any `dir/` line as `dir/*`. Take out a line that leaves out the whole of `vendor/` on every app but WordPress and a static site, and the whole of `storage/`, `content/` or `users/` on laravel, statamic and symfony: those folders travel, as each reference says. Show it.

- WordPress: `wp-content/uploads/*`, `wp-content/cache/*`, `wp-content/upgrade/*`, `node_modules/*`, `.git/*`, `.env`, `wp-config.php`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip`
- Laravel and Statamic: `node_modules/*`, `storage/logs/*.log`, `bootstrap/cache/*.php`, `database/*.sqlite*`, `public/hot`, `public/storage/*`, `.env`, `.env.16h`, `.env.*`, `auth.json`, `.git/*`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip`, and on Statamic `storage/forms/*` — `vendor/` and `storage/` travel (and Statamic's `content/` and `users/`), for the reasons in its reference
- Symfony: `node_modules/*`, `var/cache/*`, `var/log/*`, `.env`, `.env.16h`, `.env.*`, `.env.local.php`, `auth.json`, `.git/*`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip` — `vendor/` travels
- phpapp: `node_modules/*`, `.env`, `.env.16h`, `.env.*`, `auth.json`, `.git/*`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip`
- files: `.git/*`, `docs/16h/*`, `*.sql`, `*.sql.gz`, `*.zip` — the zip is the chosen folder's contents

Write a folder as `dir/*`: zip matches each pattern against file paths, so `dir/` leaves out only the folder's own entry and every file in it still goes in. `wp-config.php` and `.env` are excluded on purpose — for WordPress and the framework apps the platform writes its own, and a framework app's own keys travel as the env part, built from `.env.16h` as its reference says; a plain PHP app gets no config from the platform at all. On the framework apps `.env.*` keeps every other env file out (`.env.production` and `.env.backup` hold real secrets) and `auth.json` holds composer's tokens; Laravel and Statamic add `.env.example` back after the zip, as their references build it, since the platform reads it to show which keys are still blank. The site serves whatever `code.zip` carries, so `docs/16h/*`, dumps and archives stay out: a dump in the tree is a dump anyone can download.

Build only the parts answered yes (WordPress below; every other app as its reference's *Building the parts* says), in a fresh folder outside the site root — a part built in the site root rides in the next `code.zip`, and production serves it. Print the folder's path and use it in step 6, since the next command may run in a new shell:

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

The env part (laravel, statamic, symfony) goes to `uploads.env` the same way, its fields first and the file last:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$env_upload_url" \
  -F key="$env_field_key" -F policy="$env_field_policy" -F ... -F file=@"$parts_folder/env.16h"
```

`204` is success. URLs live one hour; caps are code 2 GiB, database 1 GiB, uploads 2 GiB, env 64 KiB — over cap, answer no to that part and re-plan. Once every part has answered `204`, delete the folder: `rm -rf "$parts_folder"`.

**Secrets never go in `.env.16h`.** A key that is a secret — an API key, a token, a licence, a DSN with a password in it — goes into the platform's secret store with `env_set(site_key, key, value)` (or `16h env set` at a terminal), once, and the platform writes it into the site's `.env` within seconds and on every push after that; `env_unset` removes it and `env_list` shows names and fingerprints, never a value. `.env.16h` is for the non-secret keys the app needs (feature flags, a public URL, a mail from-name). A value you pass to `env_set` is in this conversation because the developer typed it here: say so before asking for one, and never read a value out of a file into that call unless they asked you to. The push report names any `.env.16h` key that looks like a secret, and any key a stored secret shadowed — move the first with `env_set` and delete it from `.env.16h`; the second is already the store's.

## Step 7 — push, then verify

A new site takes a push once `site_status(site_key)` says `accepted`. `requested` means the site and its database are still being made; `refused` means they will not be — read `message`, re-plan or stop.

**Whenever `parts` includes `database` on a site that exists, say this first and wait for a yes:**

> This replaces the whole database on `<site>`. If it is WooCommerce that includes
> orders, product changes and customer data. The previous database is kept as a restore point.

`site_push(site_key, plan_id, parts)` — `parts` names what reached its POST: `code`, plus `env` when you built one (Symfony always does), and `database` or `uploads` only on WordPress. It returns a `task_id`. Then `verifying-a-deploy`: it polls with that `task_id`, reads every `state`, and hands back the URL and, for WordPress, the one-shot wp-admin login.

When it comes back `failed` with `deploy_state: flipped_back`, or the developer says the site broke after it: *Roll back the last change* below.

## Push a later change to a devsite that exists

Same verbs, one more argument. **Never plan by folder name for a site that is already there** — that refuses `name … is taken`, which is true and useless.

1. `site_plan(app, local_facts, site_key="<the devsite>")` → a plan with `kind: "update"` and its own `uploads` map. The name and the PHP version are the site's and are not asked.
2. Show its `tree` as step 4 says, then ask what it asks. On WordPress, `include_database` defaults to **no** and its text carries the warning above — read it out; `include_uploads` appears only when you have uploads; `rewrite_urls` only when your local URL differs. Statamic asks `include_content` again; the other apps ask nothing.
3. Build and upload the parts answered yes (steps 5 and 6), and a framework app's env part on every push, since the platform rewrites `.env` each time. The POSTs came back with the plan, and `site_create` here is refused with `plan … updates an existing site — call site_push`.
4. `site_push(site_key, plan_id, parts, answers)` — **every** answer, or it refuses and names the missing one; `database` in `parts` needs `include_database: true`. Then `verifying-a-deploy`, as above.

**Going live** is `releasing-to-production`, never this skill.

## Roll back the last change

When a push comes back `failed` with `deploy_state: flipped_back`, or the developer says the site broke after a push: read the error with `logs_read`, then offer the three moves in plain words — push a fix, roll back the code, or roll back code, database and files.

**After a flip-back the code is already back** on the release before; the push's database, files and config are as it left them. A rollback undoes the site's last change: `site_plan(site_key, rollback=true)` offers that push's database and files when it changed them, and when it changed neither, the push before it, its code included. Say which before the questions. On production, plan with `type: "production"` too.

Read `what_will_change` to the developer:

- `live_release` → `back_to`: the release serving now, and the one that comes back. `undoes` is there when the last change was itself a rollback.
- `database.tables_with_new_rows`: each table's `rows_added`, the rows written since the change, which a database rollback takes away. `rows_added: null` means the platform cannot count that table's new rows (it has no counter, or the restore point is from before 19 Nov 2026), not "no rows": say "can't count", and treat them as rows that may be lost. `rows_may_be_lost: true` marks a log or cache table, whose rows are safe to lose. `could_not_count` means no table could be counted.
- `files`: what the files part puts back.
- `if_the_database_stays`: what a code-only rollback leaves. Read it before asking `roll_back_database`.

Then ask `roll_back_code`, `roll_back_database` and `roll_back_files` (each defaults to yes; only the parts the restore point holds are asked), and on production `confirm`. `site_push(site_key, plan_id, parts=[], answers)`, on production with `confirm: true` and `digest` as `releasing-to-production` sends them, then `verifying-a-deploy`. A production database rollback is refused while rows may be lost; code and files still go back. A rollback mints no wp-admin login; only a push does. When the plan refuses, read its sentence: pushing the previous code again still rolls the code back.
