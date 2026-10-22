# Static site — devsite import detail

Read with `SKILL.md`. A static site is a folder of HTML, CSS, scripts and
images, served as files, and is pushed with `app: "files"`. The hook never
names it — every front-end repo has an `index.html`, and most are not sites —
so use this only when the developer asks for a static site ("put the build on
a devsite", "host this folder").

## Finding the app root

Ask one question: which folder is the site? Offer `dist`, `build`, `public`
and `.`, the default first: the first of them holding an `index.html`. Run the
project's build first (`npm run build`) so the folder is current.

The zip is that folder's **contents**: its `index.html` sits at the zip root,
and the zip is the docroot. A zip of the folder itself (`dist/index.html`) is
refused: `refused: code.zip has no index.html — is this the files root?`.

## Local facts

From the repo root:

```bash
site_folder="dist"                           # the answer to the folder question
folder_name="$(basename "$PWD")"             # the repo's name, never the build folder's
code_size_bytes=$(( $(du -sk "$site_folder" | cut -f1) * 1024 ))
git_present="$(git rev-parse --is-inside-work-tree 2>/dev/null || echo false)"
git_remote_url="$(git remote get-url origin 2>/dev/null)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
```

- `folder_name` names the devsite, so it comes from the repo: a site named
  `dist.devsite.co.nz` names nothing.
- `git`: `present`, `remote_url` and `branch` as measured, `shape: null` — the
  build folder is not the repo, so there is nothing to pull.
- Leave `docroot_guess` out of `local_facts`: the zip is the docroot.
- Every other key is `null`.
- `site_plan(app: "files", local_facts)`.

## `.deployignore`

It sits in the repo root, as for every app; the zip reads it from there.

```
.git/*
docs/16h/*
*.sql
*.sql.gz
*.zip
```

| Line | Why |
|---|---|
| `.git/*` | under a `.` site folder, the history and `.git/config` would be served |
| `docs/16h/*` | the developer's records; in the zip they are served at a guessable URL |
| `*.sql`, `*.sql.gz`, `*.zip` | a dump or an archive in the folder is one anyone can download |

The zip is the chosen folder's contents, so `node_modules` is never inside it —
unless the folder is `.`: then add `node_modules/*`, and any source the site
should not serve.

## Building the parts

Build outside the repo, print the folder's path for the upload, and delete it
once the part has answered `204` (`rm -rf "$parts_folder"`). Set `site_folder`
again here: the next command may run in a new shell, and an empty one would
zip the repo root, whose source `index.html` the platform cannot tell apart:

```bash
npm run build                                # if the site has a build
site_folder="dist"                           # the answer to the folder question
[ -n "$site_folder" ] && [ -f "$site_folder/index.html" ] || { echo "site_folder must name the built folder holding index.html"; exit 1; }
repo_folder="$PWD"
parts_folder="$(mktemp -d)"; echo "$parts_folder"
(cd "$site_folder" && zip -r -q "$parts_folder/code.zip" . -x@"$repo_folder/.deployignore")
```

`parts` is `["code"]`. Nothing runs on the platform, so the plan asks no `php`
question, and an env or database part is refused.

## After `applied`

- `/` answers with the folder's `index.html`. Open a deep link too: a
  single-page app's routes are not files, so check one before handing the URL
  over.
- No `wp_admin_login_url` — that is WordPress-only.
- Later changes: rebuild, zip the folder's contents into a fresh parts folder,
  and take the *later* path in `SKILL.md`. Its plan asks nothing.
- Production pushes are WordPress-only in this wave.
