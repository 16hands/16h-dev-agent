# Statamic — devsite import detail

Read with `SKILL.md`. Statamic is a Laravel app whose content lives in files,
pushed with `app: "statamic"`. What differs from Laravel is the content, two
platform keys and one more command after the unpack.

## Finding the app root

The directory holding **`artisan` and `please`**, whose `composer.json`
requires `statamic/cms` — not `public/`, which is only the docroot. Herd,
Valet, Sail and DDEV put it where they put any Laravel app.

The repo **is** the app, so git is offered as for Laravel: with an `origin`,
the plan asks `git_pull`, default yes; with no `.git` or no `origin`, say
nothing about git.

## Local facts

From the app root:

```bash
folder_name="$(basename "$PWD")"
siteurl="$(php artisan tinker --execute='echo config("app.url");' 2>/dev/null)"
php_version="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

- `siteurl` is `APP_URL`; without tinker, read it from `.env` — **never upload it**.
- `db_size_bytes` and `uploads_size_bytes`: leave them out. Entries, users and
  globals are files in the zip, not database rows.
- `docroot_guess`: `public`, from the project block.
- `git`: from the project block (`remote_url`, `branch`, `Shape:`); without
  the block, run the three git lines in `laravel.md`'s *Local facts*.
- Leave out any key you could not measure, never a guess; `git.present` is
  always sent, `true` or `false`.

## Content and users

`content/` and `users/` travel in `code.zip`, and the platform keeps a shared
copy of each across releases. The plan asks **`include_content`** — replace
the site's `content/` and `users/` with the release's? — default **yes** on a
devsite: your content is the site's. Answer no when someone has been editing
in the devsite's control panel; the release's copies are then discarded.

Assets uploaded in the devsite's control panel land in the default `assets`
container, `public/assets`, inside the release: the next push replaces them
with the zip's. Say so when the client has been uploading.

## .env.16h

The platform owns `.env`: the site row, the app key it keeps for the site,
the database it made, the mail catcher, plus `STATAMIC_STACHE_WATCHER=false`
and `STATAMIC_STATIC_CACHING_STRATEGY=null`. `.env.16h` at the app root holds
the keys only this app knows — `STATAMIC_LICENSE_KEY`, `STATAMIC_PRO_ENABLED`,
a third-party API key — and travels as the `env` part, never in the zip. It is
optional. On first use, create it from `.env.example` without the platform's
keys (the platform ignores them in the part and names each in the push report):

```bash
platform_keys='APP_NAME|APP_ENV|APP_KEY|APP_DEBUG|APP_URL|LOG_CHANNEL|LOG_LEVEL|DB_CONNECTION|DB_HOST|DB_PORT|DB_DATABASE|DB_USERNAME|DB_PASSWORD|SESSION_DRIVER|CACHE_STORE|QUEUE_CONNECTION|FILESYSTEM_DISK|BROADCAST_CONNECTION|MAIL_MAILER|MAIL_HOST|MAIL_PORT|MAIL_USERNAME|MAIL_PASSWORD|MAIL_ENCRYPTION|MAIL_FROM_ADDRESS|MAIL_FROM_NAME|MAIL_URL|DB_URL|DATABASE_URL|STATAMIC_STACHE_WATCHER|STATAMIC_STATIC_CACHING_STRATEGY'
[ -f .env.example ] && [ ! -f .env.16h ] && grep -Ev "^(export[[:space:]]+)?(${platform_keys})=" .env.example > .env.16h
grep -qxF '.env.16h' .gitignore 2>/dev/null || printf '\n.env.16h\n' >> .gitignore
```

Show the file and ask which values the devsite needs; the developer's answers
go in this file and nowhere else. Copy it into the parts folder on **every**
push: the platform rewrites `.env` each time, so a push without it drops its keys.

## `.deployignore`

```
node_modules/*
storage/logs/*.log
bootstrap/cache/*.php
public/hot
public/storage/*
.env
.env.16h
.env.*
auth.json
.git/*
docs/16h/*
*.sql
*.sql.gz
*.zip
```

| Line | Why |
|---|---|
| `node_modules/*` | build input only |
| `storage/logs/*.log` | local logs; the folder itself travels |
| `bootstrap/cache/*.php` | a `config:cache` file is the local `.env` frozen into PHP, and it would win over the platform's |
| `public/hot` | laravel-vite-plugin writes it while `npm run dev` runs and `npm run build` does not remove it; in the release, `Vite::isRunningHot()` points every asset at `localhost:5173` and the devsite has no CSS or JS |
| `public/storage/*` | the `storage:link` symlink: zip follows it and packs a real folder, which the platform's `storage:link --force` cannot replace, so the devsite serves the old local copies and new uploads 404 |
| `.env` | never travels in the zip: the platform writes its own on every push |
| `.env.16h` | travels as the `env` part, never inside the release |
| `.env.*` | every other env file in the tree: `.env.production`, `.env.backup` and `.env.staging` hold real secrets, and `.env.local` is one machine's values. `.env.example` matches too: it travels by the add-back line in *Building the parts*, since the platform reads it to show which keys are still blank |
| `auth.json` | composer's tokens for private packages |
| `.git/*` | history is not a deploy artifact, and `.git/config` can hold a token |
| `docs/16h/*` | the developer's records, not the site's |
| `*.sql`, `*.sql.gz`, `*.zip` | a dump or an archive left in the tree must never ship with the code |

Write every folder as `dir/*`: `dir/` leaves out only the folder's own entry.
Four folders travel on purpose; take out any line for them: `content/` and
`users/` (above), `vendor/` (the lane runs no `composer install`; run it first
if `vendor/` is missing) and `storage/` (the first push seeds the shared copy).
Run `npm run build` first so `public/build` is in the zip.

## Building the parts

Build outside the app root, print the folder's path for the upload, and delete
it once every part has answered `204` (`rm -rf "$parts_folder"`):

```bash
npm run build                                # if the site has a front-end build
parts_folder="$(mktemp -d)"; echo "$parts_folder"
zip -r -q "$parts_folder/code.zip" . -x@.deployignore
[ -f .env.example ] && zip -q "$parts_folder/code.zip" .env.example
if [ -f .env.16h ]; then cp .env.16h "$parts_folder/env.16h"; fi
```

`parts` is `["code"]`, plus `"env"` when `env.16h` was built and uploaded.
There is no `database` part: a database import is WordPress-only in this wave.

## After `applied`

- Inside the release, before the flip, the platform runs `migrate --force`,
  `storage:link` and `please stache:refresh`; a failing command stops the push
  and the report carries its output.
- The control panel is `/cp` on the devsite. With file users (Statamic's
  default) the accounts are the `users/` you pushed, with their local passwords.
- No `wp_admin_login_url` — that is WordPress-only.
- Mail never reaches a real inbox: the platform points it at its mail catcher
  (or at the log, until the catcher is live).
- Later changes: the *later* path in `SKILL.md`. Its plan asks
  `include_content` again on every push; read it out.
- Rolling back a devsite is pushing the previous code again.
- Production pushes are WordPress-only in this wave.
