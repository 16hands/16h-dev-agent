# Symfony — devsite import detail

Read with `SKILL.md`. Symfony is pushed with `app: "symfony"`. It commits its
`.env` as the app's defaults and boots only with one, so here the env part is
not optional: the committed `.env` rides inside it.

## Finding the app root

The directory holding **`bin/console`**, whose `composer.json` requires
`symfony/framework-bundle` — not `public/`, which is only the docroot. With
the Symfony CLI, DDEV or Docker it is the project root.

The repo **is** the app, so git is offered as for Laravel: with an `origin`,
the plan asks `git_pull`, default yes; with no `.git` or no `origin`, say
nothing about git.

## Local facts

From the app root:

```bash
folder_name="$(basename "$PWD")"
php_version="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

- `siteurl`: the URL you open locally (`symfony server:status` prints it), or
  `null`. Nothing is rewritten.
- `db_size_bytes` and `uploads_size_bytes`: `null`.
- `docroot_guess`: `public`, from the project block.

## .env.16h

The platform owns `APP_ENV APP_DEBUG APP_SECRET DATABASE_URL MAILER_DSN LOCK_DSN`:
`APP_ENV=prod`, `APP_DEBUG=0`, the secret it keeps for the site, the MySQL 8.0
database it made, the mail catcher, `LOCK_DSN=flock`. From them it writes the
one `.env` Symfony boots from.

The env part is the committed `.env` followed by `.env.16h`, and a key set
twice takes its last value, so `.env.16h` wins over the defaults. `.env.16h`
is optional; the part is not — a push without it is refused with `a symfony
push needs its env part — the app's committed .env rides in it`.

Create `.env.16h` when the devsite needs a value the committed `.env` lacks,
and keep it out of git (`printf '\n.env.16h\n' >> .gitignore` if it is not
listed). What belongs in it:

- the keys a committed `.env.prod` sets that this site needs — the file
  itself never ships;
- the values this site needs from `.env.local`, one at a time, asked of the
  developer — never the file wholesale: it is one machine's;
- `MESSENGER_TRANSPORT_DSN=sync://` when the app uses Messenger: nothing
  consumes a queue on a devsite.

The committed `.env` carries its own `APP_SECRET` and `DATABASE_URL`, so every
push report names them `platform-owned, ignored`. That is expected.

## `.deployignore`

```
node_modules/*
var/cache/*
var/log/*
.env
.env.16h
.env.local
.env.*.local
.env.prod
.git/*
docs/16h/*
*.sql
*.sql.gz
*.zip
```

| Line | Why |
|---|---|
| `node_modules/*` | build input only |
| `var/cache/*` | built for this machine's paths and env; the platform's `cache:clear` builds the site's |
| `var/log/*` | local logs; the folder itself travels |
| `.env` | rides in the env part, never the zip: a release holding a `.env` is refused |
| `.env.16h` | rides in the env part, never inside the release |
| `.env.local`, `.env.*.local` | one machine's values |
| `.env.prod` | Symfony loads it after `.env`, so in the release it would override the platform's keys; it never ships. `.env.test` and its kind may travel: `APP_ENV=prod` never loads them |
| `.git/*` | history is not a deploy artifact, and `.git/config` can hold a token |
| `docs/16h/*` | the developer's records, not the app's |
| `*.sql`, `*.sql.gz`, `*.zip` | a dump or an archive left in the tree must never ship with the code |

Write every folder as `dir/*`: `dir/` leaves out only the folder's own entry.
Delete a `.env.local.php` left by `composer dump-env` before zipping: Symfony
reads it instead of every `.env` file. **`vendor/` travels on purpose** — the lane runs no `composer install`; run it
first if `vendor/` is missing, and take out any `vendor/` line.

## Building the parts

Build the front end first: `npm run build` for Encore, or
`php bin/console asset-map:compile` for AssetMapper (then delete `public/assets`
after zipping, or the local dev server keeps serving the compiled copies).
Build outside the app root, print the folder's path for the upload, and delete
it once every part has answered `204` (`rm -rf "$parts_folder"`):

```bash
parts_folder="$(mktemp -d)"; echo "$parts_folder"
zip -r -q "$parts_folder/code.zip" . -x@.deployignore
if [ -f .env.16h ]; then
  cat .env .env.16h > "$parts_folder/env.16h"
else
  cp .env "$parts_folder/env.16h"
fi
```

`.env` must end with a newline, or `cat` runs its last line into the first of
`.env.16h`. `parts` is always `["code", "env"]`. There is no `database` part: a
database import is WordPress-only in this wave.

## After `applied`

- Inside the release, before the flip, the platform runs
  `php bin/console cache:clear` with `APP_ENV=prod`; a failure stops the push
  and the report carries its output. `APP_ENV=prod php bin/console cache:clear`
  locally shows a prod-only error first.
- No Doctrine migration runs: the database the platform made starts empty. If
  the app needs its schema, say so before the push.
- No `wp_admin_login_url` — that is WordPress-only.
- Mail never reaches a real inbox: `MAILER_DSN` is the mail catcher, or
  `null://null` until the catcher is live.
- Later changes: the *later* path in `SKILL.md`, both parts every time.
- Rolling back a devsite is pushing the previous code again.
- Production pushes are WordPress-only in this wave.
