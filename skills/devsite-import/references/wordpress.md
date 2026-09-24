# WordPress — devsite import detail

Read with `SKILL.md`. This is the WordPress half: where the site actually
lives, how to run WP-CLI against it, what each part contains, and what the
platform does to it once it lands.

## Finding the site root

| Setup | Site root | Tell-tale |
|---|---|---|
| Classic (MAMP, XAMPP, a plain vhost) | the directory with `wp-config.php` | `wp-content/`, `wp-includes/` beside it |
| Bedrock (Roots) | `web/` | `composer.json` requires `roots/wordpress`; config in `config/`, plugins in `web/app/plugins` |
| Local (WP Engine) | `~/Local Sites/<name>/app/public` | `~/Local Sites/<name>/conf/`, `logs/` |
| Herd / Valet | the parked or linked directory | `herd links`, `valet links` |
| DDEV | project root + the `docroot` in `.ddev/config.yaml` | `.ddev/` |
| Studio (Automattic) | `~/Studio/<name>` or the path Studio shows | `.studio/` or Studio's site list |

Two rules that save a wasted upload:

- **`wp-config.php` above the docroot** is legal WordPress. If the docroot has
  `wp-content/` but no `wp-config.php`, look one level up; the site root for
  our purposes is still the docroot, but read the config from where it is.
- **A repo is not a site.** A repo containing only `wp-content/`, or only a
  theme, still needs the whole running docroot uploaded on the first push.

## Running WP-CLI

| Setup | How |
|---|---|
| Herd, Valet, plain PHP | `wp` in the site root |
| DDEV | `ddev wp <args>` |
| Local | Local's own shell, or `wp --path=~/Local\ Sites/<name>/app/public` |
| Studio | `studio_wp` if the Studio MCP is present |
| No WP-CLI at all | fall back below |

**No WP-CLI fallback.** Do not guess. Read `siteurl` from the database with the
credentials in `wp-config.php`, take `php` from `php -v`, and pass
`db_size_bytes: null`. A `null` makes the plan ask; a wrong number does not.

## Local facts

```bash
siteurl="$(wp option get siteurl)"           # NOT home — siteurl is what gets rewritten
php_version="$(wp --info --format=json | jq -r .php_version | cut -d. -f1,2)"
db_size_bytes="$(wp db size --size_format=b)"
uploads_size_bytes=$(( $(du -sk wp-content/uploads | cut -f1) * 1024 ))
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

- `du -sk` then ×1024, because macOS `du` has no `-b`.
- `php` is `major.minor` only (`8.3`, not `8.3.14`). The plan matches it to a
  fleet pool and falls back to `8.3`.
- If `siteurl` and `home` differ, say so when you ask `rewrite_urls` — only
  `siteurl` is rewritten by the lane.
- **Multisite** (`wp core is-installed --network`) is not supported by the
  import lane. Say so and stop rather than uploading it.

## Git shapes, with the command that decides

```bash
test -f wp-config.php && test -d wp-content && echo whole_tree_candidate
grep -q 'roots/wordpress' composer.json 2>/dev/null && echo bedrock_candidate
test -d themes && test -d plugins && ! test -f wp-config.php && echo wp_content_only
grep -qs 'Theme Name:' style.css && echo theme_only
git remote get-url origin >/dev/null 2>&1 || echo no_remote_or_no_git
```

Only `whole_tree` and `bedrock` are pull-deployable, and Bedrock needs a
`composer install` the lane does not run yet — offer the git question, but say
the build step is wave 2 and that the upload is what works today.

For `wp_content_only` and `theme_only`, **do not mention git at all**. There is
no core-install step behind it, so raising it only produces a dead end.

## `.deployignore`

```
wp-content/uploads/
wp-content/cache/
wp-content/upgrade/
node_modules/
.git/
.env
wp-config.php
```

| Line | Why |
|---|---|
| `wp-content/uploads/` | travels as its own part, and is shared across releases on the platform |
| `wp-content/cache/`, `upgrade/` | regenerated; pure weight |
| `node_modules/` | build input, never runtime |
| `.git/` | history is not a deploy artifact, and it can be large |
| `.env`, `wp-config.php` | the platform writes its own config from the database row it created — local DB credentials must not travel |

Add to it freely (`*.sql`, `wp-content/backups/`, a local `mu-plugins` debug
drop-in). Show the final file before zipping.

## Building the parts

```bash
zip -r -q code.zip . -x@.deployignore
wp db export - | gzip > database.sql.gz
zip -r -q uploads.zip wp-content/uploads
```

- `-x@.deployignore` reads the patterns from the file; keep the trailing `/` on
  directory entries.
- `wp db export -` writes to stdout, so nothing lands on disk unencrypted
  twice. Add `--single-transaction` on a busy local DB.
- `uploads.zip` keeps the `wp-content/uploads` prefix on purpose — the lane
  unpacks it into the shared uploads directory.
- Check sizes against the caps (code 2 GiB, database 1 GiB, uploads 2 GiB)
  **before** uploading. Over cap on uploads is the common one: answer no to
  `include_uploads`, get the site up, and move the media afterwards.

## What the platform does with them

In order, in a new release directory, as the client user:

1. Refuses outright if `code.zip` has no `wp-content/`, or ships a
   `wp-config.php` that is not WordPress's shape. Nothing is touched.
2. Unpacks the code; unpacks uploads into the **shared** `wp-content/uploads`
   so it survives later releases.
3. Drops any shipped `wp-config.php` and writes its own.
4. If `database` was pushed: dumps the current schema to a restore point first,
   then imports.
5. `wp search-replace "<local siteurl>" "https://<site_key>" --all-tables
   --skip-columns=guid`, then `wp cache flush`.
6. Flips the release symlink and restarts the pool.

So: a failed push leaves the previous release serving, and a replaced database
has a restore point behind it. Say that when the `database` warning lands.

## After `applied`

- `site_status` carries `wp_admin_login_url` — **one-shot**. Hand it to the
  person; do not open it, and do not repeat it in a later message.
- The devsite is `noindex` and password-protected by default. If they cannot
  reach it, check the `httpauth` credentials from `site_create` first.
- Later changes: rebuild `code.zip`, upload it to the same part, and
  `site_push(parts=["code"])`. Code-only pushes take about twenty seconds
  and do not touch the database.
