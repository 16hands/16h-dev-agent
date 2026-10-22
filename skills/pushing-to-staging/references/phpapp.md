# Plain PHP app — devsite import detail

Read with `SKILL.md`. An app with an `index.php` and none of the frameworks
the hook names is pushed with `app: "phpapp"`. The platform unpacks it and
serves it: it writes no `.env` or config file into it, takes no env part, and
runs nothing after the unpack.

## Finding the app root

The zip root is the folder that **holds** the docroot — for `.`, the docroot
itself:

| `index.php` sits in | `docroot` answer | Zip from |
|---|---|---|
| the folder itself | `.` | that folder: it is the docroot |
| `public/` | `public` | the folder holding `public/` |
| `web/` | `web` | the folder holding `web/` |
| `htdocs/`, `www/`, any other name | not offered | move it, or rename the folder `public` (and every path in the code that names it), then push |

The platform looks for `<docroot>/index.php` in the zip and refuses
`refused: code.zip has no index.php — is this the phpapp root?` when it is not
there — the usual cause is zipping from inside `public/`.

With `.`, every file in the zip is served: `vendor/`, `composer.json`, any
config file. When the app has code or settings that must not be downloadable,
a `public/` docroot keeps them above it.

## The docroot question

The plan asks `docroot` — `.`, `public` or `web` — with the hook's
`docroot_guess` as its default. Offer that default first. When you see an
`index.php` in two of those places, the docroot is the one the browser should
reach: say what you found and ask once. The answer is fixed at create; every
later push keeps it.

## Local facts

From the zip root:

```bash
folder_name="$(basename "$PWD")"
php_version="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
code_size_bytes=$(( $(du -sk . | cut -f1) * 1024 ))
```

- `siteurl`: the URL you open locally, or `null`. Nothing is rewritten.
- `db_size_bytes` and `uploads_size_bytes`: `null`.
- `docroot_guess`: copied from the project block (`.`, `public` or `web`);
  `null` when the block has none.

## `.deployignore`

```
node_modules/*
.env
.env.16h
.git/*
docs/16h/*
*.sql
*.sql.gz
*.zip
```

| Line | Why |
|---|---|
| `node_modules/*` | build input only |
| `.env`, `.env.16h` | local values; the platform reads neither for a plain PHP app |
| `.git/*` | history is not a deploy artifact, and `.git/config` can hold a token |
| `docs/16h/*` | the developer's records; under a `.` docroot they would be served |
| `*.sql`, `*.sql.gz`, `*.zip` | a dump or an archive left in the tree is one anyone can download |

Write every folder as `dir/*`: `dir/` leaves out only the folder's own entry.
Add any other file that holds local credentials (a `config.local.php`).
**`vendor/` travels** — the lane runs no `composer install`.

The platform hands a plain PHP app no database credentials, so an app that
needs a database cannot reach one through this lane yet. Say so before the
push rather than after it.

## Building the parts

From the zip root, in a fresh folder outside it; print the path for the
upload, and delete it once the part has answered `204` (`rm -rf "$parts_folder"`):

```bash
parts_folder="$(mktemp -d)"; echo "$parts_folder"
zip -r -q "$parts_folder/code.zip" . -x@.deployignore
```

`parts` is `["code"]`. An env part is refused (`an env part is for laravel,
statamic and symfony — this is a phpapp site`), and so is a database part.

## After `applied`

- The release is served as it is; nothing runs after the unpack.
- No `wp_admin_login_url` — that is WordPress-only.
- Later changes: the *later* path in `SKILL.md`. Its plan asks nothing; the
  docroot is the one chosen at create.
- Rolling back a devsite is pushing the previous code again.
- Production pushes are WordPress-only in this wave.
