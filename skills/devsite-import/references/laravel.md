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
| `.git`, no `origin` (`no_remote`) | one offer: create a repo on your GitHub? default no |
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
  under `storage/app/public` is not moved by this flow; say so if the app has
  any, and move it separately.
- `db_size_bytes`: only if you can get it cheaply, e.g.
  `php artisan db:show --json` (Laravel 10+) or a
  `SELECT SUM(data_length+index_length)` against `information_schema.TABLES`.
  Otherwise `null` — a `null` makes the plan ask; a wrong number does not.

## `.deployignore`

```
vendor/
node_modules/
storage/
.env
.git/
```

| Line | Why |
|---|---|
| `vendor/` | a build product of `composer install` |
| `node_modules/` | build input only |
| `storage/` | runtime state — logs, cache, sessions, uploaded files. The platform keeps its own, shared across releases |
| `.env` | **never travels.** The platform writes the app's environment from the database row and the client's secrets |
| `.git/` | history is not a deploy artifact |

Keep built front-end assets **in** the zip (`public/build`, `public/css`,
`public/js`) — run `npm run build` locally before zipping.

**Until the lane runs `composer install` (wave 2), an app with no committed
`vendor/` will not boot on the devsite.** If that is your case, say so, remove
the `vendor/` line from `.deployignore` before zipping, and check the result
against the 2 GiB code cap. Note it when you hand the site over.

## Building the parts

```bash
npm run build                                # if the app has a front-end build
zip -r -q code.zip . -x@.deployignore
```

The `database` part is `database.sql.gz` as for WordPress — a gzipped mysqldump
of the local schema:

```bash
mysqldump --single-transaction "$local_database_name" | gzip > database.sql.gz
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
- Later changes: rebuild `code.zip` and `push_devsite(parts=["code"])`, or, if
  the dev said yes to `git_pull`, let the pull lane serve it.
- Going live is never reachable from these tools — it is a click in the panel.
