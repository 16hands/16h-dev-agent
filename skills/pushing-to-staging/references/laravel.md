# Laravel — devsite import detail

Read with `SKILL.md`. Laravel uses the same four tools with `app: "laravel"`.
The differences are all in what the folder is, what travels, and what does not.

## Finding the app root

The directory holding **`artisan`** — not `public/`, which is only the docroot.

| Setup | App root |
|---|---|
| Herd / Valet | the parked or linked directory (`herd links`) |
| Sail / plain Docker | the repo root beside `docker-compose.yml` |
| DDEV | the project root; `docroot: public` in `.ddev/config.yaml` |

Unlike WordPress, the repo **is** the app here. That is why the git question
defaults to yes.

## Git

| Shape | Offer |
|---|---|
| `.git` with an `origin` | `git_pull` question, **default yes** — Laravel deploys are a code pull, the way everyone already runs them |
| `.git`, no `origin` (`no_remote`) | say nothing about git; upload only |
| no `.git` | say nothing about git; upload only |

Answering yes to `git_pull` puts `git_repo_url` and the branch on the site row
and returns the public half of the client's deploy key for you to add to the
repo. It does not replace this first upload — the upload is what gets the app
running; the pull lane serves the ones after it.

## Local facts

There is no WP-CLI, so measure directly from the app root:

```bash
folder_name="$(basename "$PWD")"
siteurl="$(php artisan tinker --execute='echo config("app.url");' 2>/dev/null)"
php_version="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
git_remote_url="$(git remote get-url origin 2>/dev/null)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
```

- `siteurl` is `APP_URL`. If tinker is unavailable, read `APP_URL` from `.env`
  — **read it, never upload it**.
- `uploads_size_bytes` has no Laravel meaning: pass `null`. Public user media
  under `storage/app/public` travels once, inside `storage/` on the first
  push; after that the platform keeps its own copy. Say so if the app has any.
- `db_size_bytes`: only if you can get it cheaply, e.g.
  `php artisan db:show --json` (Laravel 10+) or a
  `SELECT SUM(data_length+index_length)` against `information_schema.TABLES`.
  Otherwise `null` — a `null` makes the plan ask; a wrong number does not.

## `.deployignore`

```
node_modules/*
storage/logs/*.log
.env
.git/*
docs/16h/*
*.sql
*.sql.gz
*.zip
```

| Line | Why |
|---|---|
| `node_modules/*` | build input only |
| `storage/logs/*.log` | local logs: weight, and whatever the app wrote to them. The folder itself travels |
| `.env` | **never travels.** The platform writes the app's environment from the database row and the client's secrets |
| `.git/*` | history is not a deploy artifact, and `.git/config` can hold a token |
| `docs/16h/*` | the release notes and investigations are the developer's records, not the app's |
| `*.sql`, `*.sql.gz`, `*.zip` | a dump or an archive left in the tree must never ship with the code |

Write every folder as `dir/*`: zip matches each pattern against a file's path,
so `dir/` leaves out only the folder's own entry and packs every file in it.

Two folders travel on purpose; take out any `.deployignore` line for either:

- **`vendor/`** — the lane runs no `composer install` yet (wave 2), so the app
  boots only on the `vendor/` in the zip. Run `composer install` first if it
  is missing, and check the zip against the 2 GiB code cap.
- **`storage/`** — the first push seeds the platform's shared `storage` from
  the zip, `framework/` folders included; every later push links that shared
  copy over the one in the zip.

Keep built front-end assets **in** the zip (`public/build`, `public/css`,
`public/js`) — run `npm run build` locally before zipping.

## Building the parts

Build in a fresh folder outside the app root, print its path for the upload,
and delete it once every part has answered `204` (`rm -rf "$parts_folder"`):
a part left in the app root rides in the next `code.zip`.

```bash
npm run build                                # if the app has a front-end build
parts_folder="$(mktemp -d)"; echo "$parts_folder"
zip -r -q "$parts_folder/code.zip" . -x@.deployignore
```

The `database` part is `database.sql.gz` as for WordPress — a gzipped mysqldump
of the local schema, into the same folder:

```bash
mysqldump --single-transaction "$local_database_name" | gzip > "$parts_folder/database.sql.gz"
```

Only build it if `include_database` was answered yes, and remember the lane's
URL rewrite is WordPress's `wp search-replace`. **Laravel rows are not
rewritten** — anything holding an absolute local URL (seeded content, a CMS
package's tables) arrives pointing at the local host. Say this before the
person answers `rewrite_urls`, and fix it in the app's own data afterwards.

## After `applied`

- No `wp_admin_login_url` — that is WordPress-only. `site_status` returns the
  URL and, when the deploy failed, the lane's own message.
- Migrations are not run by the import. If the app needs them, say so; that is
  a job for the panel or the client's own deploy script today.
- Later changes: the *later* path in `SKILL.md` — `site_plan` with
  `site_key`, rebuild `code.zip` in a fresh parts folder, and
  `site_push(parts=["code"], answers)`; or,
  if the dev said yes to `git_pull`, let the pull lane serve it.
- Going live is the `releasing-to-production` skill.
