---
name: devsite-import
description: Use when someone wants a site that runs on their own machine put onto a 16h devsite — "put this WordPress on a devsite", "give me a staging URL for this", "host this so the client can look at it" — or wants to push a later change to a devsite they already made. Covers finding the real site root, collecting the local facts, the plan → confirm questions, building the upload parts, and the push.
---

# Put a local site on a devsite

```
site root → local_facts → plan_devsite → ask the questions → create_devsite
→ build the parts → upload → push_devsite → poll site_status → hand back the URL
```

Read `references/wordpress.md` or `references/laravel.md` before step 1.

## Doctrine — the part people get wrong

- **Never call a write tool without asking.** `create_devsite` and
  `push_devsite` change hosting; `plan_devsite` and `site_status` are reads.
- **Defaults first** — the plan fills every answer in; you are confirming, not
  interviewing.
- **One question per message**, in `questions[]` order, showing the default.
- **Ask every question the plan returns.** Skipping one makes `create_devsite`
  refuse; inventing an answer puts a lie in the audit record.
- **One `create_devsite` per `plan_id`, ever.** On `plan expired (30 min)` or
  `defaults changed since the plan`, call `plan_devsite` again and re-ask what
  changed — never retry the old `plan_id`.
- **A refusal is the truth about your access** and names the next move.

## Step 1 — find the RUNNING site root, not the repo

| Setup | Site root |
|---|---|
| Classic WordPress | the directory holding `wp-config.php` and `wp-content/` |
| Bedrock | `web/` beside a `composer.json` that requires `roots/wordpress` |
| Local (by WP Engine) | `~/Local Sites/<name>/app/public` |
| Herd / Valet | the linked or parked directory — `herd links` |
| DDEV | the `docroot` in `.ddev/config.yaml` (usually `web/`) |
| Laravel | the directory holding `artisan` (the app root, not `public/`) |

The upload takes this folder, not the repo. Say which one you picked.

## Step 2 — classify the git state of that folder

`git rev-parse --show-toplevel`, `git remote get-url origin`, then:

| Shape (`git.shape`) | Spot it by | Pull-deployable | What you may offer |
|---|---|---|---|
| `whole_tree` | `wp-config.php` + `wp-content/` + `.git` at the root | yes | git question, default no |
| `bedrock` | `composer.json` requires `roots/wordpress`, `web/app/` exists | yes, once builds land | git question — say the build step is wave 2 |
| `wp_content_only` | `themes/` + `plugins/` at the repo root, no `wp-config.php` | no | **do not mention git** — upload only |
| `theme_only` | `style.css` with `Theme Name:`, no `wp-content/` above it | no | **do not mention git** — upload only |
| `no_remote` | `.git` present, no `origin` | — | one offer: create a repo on your GitHub? default no |
| `none` | no `.git` | — | **say nothing about git** |

Git is never required. The first push is always an upload.

## Step 3 — collect `local_facts`

WordPress, from the site root (Laravel equivalents are in its reference):

```bash
folder_name="$(basename "$PWD")"
siteurl="$(wp option get siteurl)"
php_version="$(wp --info --format=json | jq -r .php_version | cut -d. -f1,2)"
db_size_bytes="$(wp db size --size_format=b)"
uploads_size_bytes=$(( $(du -sk wp-content/uploads | cut -f1) * 1024 ))
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
```

Keys, exactly: `folder_name`, `siteurl`, `php`, `db_size_bytes`,
`uploads_size_bytes`, `code_size_bytes`, `git` = {`present`, `remote_url`,
`branch`, `shape`}. What you could not measure goes as `null`, never a guess.
Then `plan_devsite(client?, app, local_facts)`, `app` = `wordpress`|`laravel`.

## Step 4 — ask the plan's questions, then create

| id | Asks |
|---|---|
| `client` | which client (only when you have more than one) |
| `site_name` | `<slug>.devsite.co.nz` |
| `php` | PHP version |
| `include_database` | send the database? |
| `include_uploads` | send `wp-content/uploads` (size shown)? |
| `rewrite_urls` | rewrite the local URL to the devsite URL? |
| `protect` | password-protect it? |
| `git_pull` | deploy from the remote on push? (only when step 2 allows) |

`create_devsite(plan_id, answers)` returns `site_key`, `url`, an `uploads` map
of presigned POSTs (`code`, `database`, `uploads`), and `httpauth` **once** —
show those credentials now; they are not retrievable later.

## Step 5 — `.deployignore`, then build the parts

Write `.deployignore` in the site root if it is absent, and show it.

| App | Default contents |
|---|---|
| WordPress | `wp-content/uploads/`, `wp-content/cache/`, `wp-content/upgrade/`, `node_modules/`, `.git/`, `.env`, `wp-config.php` |
| Laravel | `vendor/`, `node_modules/`, `storage/`, `.env`, `.git/` |

`wp-config.php` and `.env` are excluded on purpose: the platform writes its
own, so local credentials never travel. Build only the parts answered yes.

```bash
zip -r -q code.zip . -x@.deployignore
wp db export - | gzip > database.sql.gz
zip -r -q uploads.zip wp-content/uploads
```

## Step 6 — upload to the presigned POSTs

Each entry has `url` and `fields`. **One `-F name=value` per returned field,
and `-F file=@<part>` LAST** — S3 ignores anything after `file`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$upload_url" \
  -F key="$field_key" -F policy="$field_policy" -F ... -F file=@code.zip
```

`204` is success. URLs live one hour; caps are code 2 GiB, database 1 GiB,
uploads 2 GiB. Over cap → answer no to that part and re-plan.

## Step 7 — push, then poll

**Whenever `parts` includes `database` and the devsite already exists, say this
first and wait for a yes:**

> This replaces the whole database on `<site>`. If it is WooCommerce that includes
> orders, product changes and customer data. The previous database is kept as a restore point.

`push_devsite(site_key, plan_id, parts)` returns a `task_id`. Then
`site_status(site_key, task_id?)` **every 10 seconds**:

| `state` | Means | Do |
|---|---|---|
| `planned` | plan made, not confirmed | call `create_devsite` |
| `requested` | the site is being created | wait |
| `accepted` | site and database exist | upload, then `push_devsite` |
| `refused` | creation was refused | read `message`; re-plan or stop |
| `pushing` | the deploy lane is running | keep polling |
| `applied` | live on the devsite URL | hand back `url` + `wp_admin_login_url` |
| `failed` | the lane stopped | read `message` verbatim; fix; push again |

`wp_admin_login_url` appears only after `applied`, and is one-shot — hand it
over, do not open it yourself.

## Going live

Never from here — no tool does it, by design. Say the devsite is ready, and that going live is a click in the 16h panel.
