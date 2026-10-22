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
defaults to yes. A tree that also holds `please` and requires `statamic/cms`
is Statamic: read `statamic.md` instead.

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
- `db_size_bytes`: `null`. The plan asks nothing about the database here.
- `docroot_guess`: `public`, from the project block.

## .env.16h

The platform owns the app's `.env`. `.env.16h` at the app root holds the keys
only this app knows — a Stripe key, a third-party API URL — and travels as its
own part, `env`, never in the zip. It is optional: the platform's keys alone
boot a fresh app. On first use, create it from `.env.example` without the keys
the platform writes (and ignores in the part, naming each in the push report),
and keep it out of git:

```bash
platform_keys='APP_NAME|APP_ENV|APP_KEY|APP_DEBUG|APP_URL|LOG_CHANNEL|LOG_LEVEL|DB_CONNECTION|DB_HOST|DB_PORT|DB_DATABASE|DB_USERNAME|DB_PASSWORD|SESSION_DRIVER|CACHE_STORE|QUEUE_CONNECTION|FILESYSTEM_DISK|BROADCAST_CONNECTION|MAIL_MAILER|MAIL_HOST|MAIL_PORT|MAIL_USERNAME|MAIL_PASSWORD|MAIL_ENCRYPTION|MAIL_FROM_ADDRESS|MAIL_FROM_NAME'
test -f .env.16h || grep -Ev "^(export[[:space:]]+)?(${platform_keys})=" .env.example > .env.16h
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
.env
.env.16h
.env.*
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
| `.env` | never travels in the zip. The platform writes `.env` on every push from the site row, the app key it keeps for the site, the database it made, and the mail catcher; keys only this app knows go in `.env.16h` (above) |
| `.env.16h` | travels as the `env` part, never inside the release |
| `.env.*` | `.env.local`, `.env.testing`: one machine's values. `.env.example` goes too; its keys reach the site through `.env.16h`, which starts as a copy of it |
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
if [ -f .env.16h ]; then cp .env.16h "$parts_folder/env.16h"; fi
```

`parts` is `["code"]`, plus `"env"` when `env.16h` was built and uploaded.
There is no `database` part: a database import is WordPress-only in this wave.
The devsite's database starts empty and `migrate --force` builds the schema;
no seeder runs, so seed data the site needs arrives through a migration.

## After `applied`

- No `wp_admin_login_url` — that is WordPress-only. `site_status` returns the
  URL and, when the deploy failed, the lane's own message.
- The platform runs `migrate --force` and `storage:link` inside the release before the flip; a failing migration stops the push and the report carries its output.
- Mail never reaches a real inbox: the platform points it at its mail
  catcher (or at the log, until the catcher is live).
- Later changes: the *later* path in `SKILL.md` — `site_plan` with
  `site_key`, rebuild `code.zip` and `env.16h` in a fresh parts folder, and
  `site_push(parts, answers)` with `parts` as above; or,
  if the dev said yes to `git_pull`, let the pull lane serve it.
- Rolling back a devsite is pushing the previous code again.
- Production pushes are WordPress-only in this wave.
