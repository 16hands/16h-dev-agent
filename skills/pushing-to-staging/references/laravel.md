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
defaults to yes. A tree that also holds `please` or requires `statamic/cms`
is Statamic: read `statamic.md` instead.

## Git

| Shape | Whether the plan asks |
|---|---|
| `.git` with an `origin` | asks `git_pull`, **default yes** — Laravel deploys are a code pull, the way everyone already runs them |
| `.git`, no `origin` (`no_remote`) | never asks: upload only, and say nothing about git |
| no `.git` | never asks: upload only, and say nothing about git |

A yes to `git_pull` puts `git_repo_url` and the branch on the site row and
returns the public half of the client's deploy key to add to the repo. The first
upload still runs: it gets the app going, and the pull lane serves the rest.

## Local facts

There is no WP-CLI, so measure directly from the app root:

```bash
folder_name="$(basename "$PWD")"
siteurl="$(php artisan tinker --execute='echo config("app.url");' 2>/dev/null)"
php_version="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
git_present="$(git rev-parse --is-inside-work-tree 2>/dev/null || echo false)"
git_remote_url="$(git remote get-url origin 2>/dev/null)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
```

- `siteurl` is `APP_URL`; without tinker, read it from `.env` — **never upload it**.
- `uploads_size_bytes` has no Laravel meaning: leave it out. Public user media
  under `storage/app/public` travels once, inside `storage/` on the first
  push; after that the platform keeps its own copy. Say so if the app has any.
- `db_size_bytes`: leave it out. The plan asks nothing about the database here.
- `docroot_guess`: `public`, from the project block.
- `git`: `present`, `remote_url` and `branch` from the three git lines above;
  `shape` from the project block's `Shape:`.
- Leave out any key you could not measure, never a guess; `git.present` is
  always sent, `true` or `false`.

## .env.16h

The platform owns the app's `.env`. `.env.16h` at the app root holds the keys
only this app knows — a Stripe key, a third-party API URL — and travels as its
own part, `env`, never in the zip. It is optional: the platform's keys alone
boot a fresh app. On first use, create it from `.env.example` without the keys
the platform writes (and ignores in the part, naming each in the push report),
and keep it out of git:

```bash
platform_keys='APP_NAME|APP_ENV|APP_KEY|APP_DEBUG|APP_URL|LOG_CHANNEL|LOG_LEVEL|DB_CONNECTION|DB_HOST|DB_PORT|DB_DATABASE|DB_USERNAME|DB_PASSWORD|SESSION_DRIVER|CACHE_STORE|QUEUE_CONNECTION|FILESYSTEM_DISK|BROADCAST_CONNECTION|MAIL_MAILER|MAIL_HOST|MAIL_PORT|MAIL_USERNAME|MAIL_PASSWORD|MAIL_ENCRYPTION|MAIL_FROM_ADDRESS|MAIL_FROM_NAME|MAIL_URL|DB_URL|DATABASE_URL'
[ -f .env.example ] && [ ! -f .env.16h ] && grep -Ev "^(export[[:space:]]+)?(${platform_keys})=" .env.example > .env.16h
grep -qxF '.env.16h' .gitignore 2>/dev/null || printf '\n.env.16h\n' >> .gitignore
```

Show the file and ask which values the devsite needs; the developer's answers
go in this file and nowhere else. Copy it into the parts folder on **every**
push: the platform rewrites `.env` each time, so a push without it drops its keys.
`LOG_LEVEL` is one of the platform's keys: `debug` on a devsite, `warning` on production
by design. To keep `info` lines on production, log them to a channel of your own in
`config/logging.php` (`'driver' => 'single'`, `'level' => 'info'`, `'path' => storage_path('logs/laravel.log')`,
the one log file every server can write), never by raising `LOG_LEVEL`.

## `.deployignore`

```
node_modules/*
storage/logs/*.log
bootstrap/cache/*.php
database/*.sqlite*
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
| `storage/logs/*.log` | local logs: weight, and whatever the app wrote to them. The folder itself travels |
| `bootstrap/cache/*.php` | a `config:cache` file is the local `.env` frozen into PHP, and it would win over the platform's. Laravel rebuilds the manifests; the folder itself travels |
| `database/*.sqlite*` | a local SQLite database and its `-wal`/`-shm` files (Laravel's default since 11): the platform's database is MySQL, so the file is only local data riding along. `database/migrations` travels |
| `public/hot` | laravel-vite-plugin writes it while `npm run dev` runs and `npm run build` does not remove it; in the release, `Vite::isRunningHot()` points every asset at `localhost:5173` and the devsite has no CSS or JS |
| `public/storage/*` | the `storage:link` symlink: zip follows it and packs a real folder, which the platform's `storage:link --force` cannot replace, so the devsite serves the old local copies and new uploads 404 |
| `.env` | never travels in the zip. The platform writes `.env` on every push from the site row, the app key it keeps for the site, the database it made, and the mail catcher; keys only this app knows go in `.env.16h` (above) |
| `.env.16h` | travels as the `env` part, never inside the release |
| `.env.*` | every other env file in the tree: `.env.production`, `.env.backup` and `.env.staging` hold real secrets (Laravel's own `.gitignore` lists them for that), and `.env.local` is one machine's values. `.env.example` matches too: it travels by the add-back line in *Building the parts*, since the platform reads it to show which keys are still blank |
| `auth.json` | composer's tokens for private packages |
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
[ -f .env.example ] && zip -q "$parts_folder/code.zip" .env.example
if [ -f .env.16h ]; then cp .env.16h "$parts_folder/env.16h"; fi
```

`parts` is `["code"]`, plus `"env"` when `env.16h` was built and uploaded.
There is no `database` part: a database import is WordPress-only in this wave.
The devsite's database starts empty and `migrate --force` builds the schema;
no seeder runs, so seed data the site needs arrives through a migration.

## After `applied`

- No `wp_admin_login_url` — that is WordPress-only.
- The platform runs `migrate --force` and `storage:link` inside the release before the flip; a failing migration stops the push and the report carries its output.
- Mail never reaches a real inbox: the platform points it at its mail
  catcher (or at the log, until the catcher is live).
- Later changes: the *later* path in `SKILL.md`, with `code.zip` and `env.16h`
  rebuilt in a fresh parts folder; or, after a yes to `git_pull`, the pull lane.
- Rolling back: `site_plan` with `rollback=true`, as `SKILL.md`'s *Roll back* says.
- Production pushes are WordPress-only in this wave.
