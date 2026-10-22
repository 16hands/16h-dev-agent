#!/usr/bin/env python3
"""Print what identifies the 16h site in a folder, as one JSON object.

Local and read-only: no network, no prompt, no file written, and the only
values read out of .env and wp-config.php are the host parts of four URL keys.
Prints {"is_site": false} when the folder holds no site, prints nothing when
anything fails or the deadline passes, and always exits 0 so a hook calling it
can never block a session.
"""
from __future__ import annotations

import functools
import json
import os
import re
import signal
import stat
import subprocess
import sys
from pathlib import Path

# The whole recon, armed with signal.alarm in main: one bound for every git
# call and file read together, far under any harness timeout. Not 1 s: a
# whole-tree WordPress repo whose index is stat-stale (4,000 files after a
# copy, a branch switch or a build tool) takes git status 1.2 s to refresh, and
# --no-optional-locks never writes that refresh back, so a 1 s deadline dropped
# the project block on every session start in such a repo (re-review,
# 2026-10-22). The fixtures still finish in well under a second.
RECON_DEADLINE_SECONDS = 5
SUBPROCESS_TIMEOUT_SECONDS = 2
FILE_READ_CAP_BYTES = 256 * 1024
WORDPRESS_HEADER_CHARACTER_COUNT = 8 * 1024
THEME_HEADER_LINE_COUNT = 20
HOSTNAME_KEYS = ("APP_URL", "WP_HOME", "WP_SITEURL", "DOMAIN_CURRENT_SITE")
FOLDERS_NOT_WORTH_WALKING = ("node_modules", "vendor")
SUBFOLDER_DOCROOTS = ("public", "web")
# Root first: a plain PHP app's docroot guess is the first of these holding an index.php.
INDEX_PHP_DOCROOTS = (".",) + SUBFOLDER_DOCROOTS
APPS_SERVED_FROM_PUBLIC = ("laravel", "statamic", "symfony")
WORDPRESS_CONTENT_FOLDER_NAMES = ("wp-content", "plugins", "themes", "mu-plugins")

HOSTNAME_KEY_ALTERNATIVES = "|".join(HOSTNAME_KEYS)
DOT_ENV_HOSTNAME_LINE = re.compile(rf"^\s*(?:{HOSTNAME_KEY_ALTERNATIVES})\s*=\s*(?P<raw_value>.*?)\s*$")
WP_CONFIG_HOSTNAME_DEFINE = re.compile(
    rf"""define\(\s*(?P<key_quote>['"])(?:{HOSTNAME_KEY_ALTERNATIVES})(?P=key_quote)\s*,"""
    rf"""\s*(?P<value_quote>['"])(?P<value>[^'"]*)(?P=value_quote)\s*\)"""
)
URL_AUTHORITY = re.compile(r"^(?:(?:[a-z][a-z0-9+.\-]*:)?//)?(?:[^/?#]*@)?(?P<host_and_port>[^/?#\s]+)", re.IGNORECASE)
HOST_AND_PORT = re.compile(r"[a-z0-9._\-]+(?::\d+)?|\[[0-9a-f:.]+\](?::\d+)?")
URL_WITH_USER_INFO = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.\-]*://)[^/]*@", re.IGNORECASE)
ROOT_COMMIT_HASH = re.compile(r"[0-9a-f]{40,64}")
PHP_VERSION_LINE = re.compile(r"^PHP (\d+\.\d+)", re.MULTILINE)


def run_quietly(command: list[str], working_directory: Path) -> str | None:
    """Stdout of a command that succeeded, or None for any failure at all."""
    try:
        completed = subprocess.run(
            command,
            cwd=working_directory,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def is_regular_file(file_path: Path) -> bool:
    """Only a regular file is ever opened: opening a named pipe waits for a writer (1Password mounts .env as one)."""
    try:
        return stat.S_ISREG(file_path.stat().st_mode)
    except OSError:
        return False


def is_directory(folder_path: Path) -> bool:
    """is_regular_file's twin: Path.is_dir raises PermissionError under a folder that cannot be looked into."""
    try:
        return stat.S_ISDIR(folder_path.stat().st_mode)
    except OSError:
        return False


def read_text_or_empty(file_path: Path) -> str:
    """A regular file's text, or "" for anything else and for a file over the read cap."""
    try:
        file_status = file_path.stat()
        if not stat.S_ISREG(file_status.st_mode) or file_status.st_size > FILE_READ_CAP_BYTES:
            return ""
        with file_path.open(encoding="utf-8", errors="replace") as text_file:
            return text_file.read(FILE_READ_CAP_BYTES)
    except OSError:
        return ""


def list_child_folders(folder: Path) -> list[Path]:
    child_folders = []
    try:
        for child in sorted(folder.iterdir()):
            is_worth_walking = not child.name.startswith(".") and child.name not in FOLDERS_NOT_WORTH_WALKING
            if is_worth_walking and is_directory(child):
                child_folders.append(child)
    except OSError:
        pass
    return child_folders


@functools.lru_cache(maxsize=None)
def read_composer_requirements(folder: Path) -> frozenset[str]:
    """The package names under composer.json's require and require-dev; empty for a missing or unreadable file.

    Cached, since every marker check asks the same folders and recon runs once. RecursionError
    too: a composer.json nested thousands deep must cost the hook nothing.
    """
    try:
        composer_manifest = json.loads(read_text_or_empty(folder / "composer.json"))
    except (ValueError, RecursionError):
        return frozenset()
    required_package_names = set()
    if isinstance(composer_manifest, dict):
        for section_name in ("require", "require-dev"):
            requirements_section = composer_manifest.get(section_name)
            if isinstance(requirements_section, dict):
                required_package_names.update(requirements_section)
    return frozenset(required_package_names)


def requires_package(folder: Path, package_name: str) -> bool:
    return package_name in read_composer_requirements(folder)


def requires_roots_wordpress(folder: Path) -> bool:
    return requires_package(folder, "roots/wordpress")


def read_wordpress_header(file_path: Path) -> str:
    """A regular file's first 8 KiB, where WordPress reads theme and plugin headers; "" for anything else."""
    if not is_regular_file(file_path):
        return ""
    try:
        with file_path.open(encoding="utf-8", errors="replace") as header_file:
            return header_file.read(WORDPRESS_HEADER_CHARACTER_COUNT)
    except OSError:
        return ""


def has_artisan(folder: Path) -> bool:
    return is_regular_file(folder / "artisan")


def has_bin_console(folder: Path) -> bool:
    return is_regular_file(folder / "bin" / "console")


def has_index_php(folder: Path) -> bool:
    """index.php at the folder itself, under public/ or under web/; index.html is never a marker."""
    return any(is_regular_file(folder / docroot / "index.php") for docroot in INDEX_PHP_DOCROOTS)


def is_symfony(folder: Path) -> bool:
    return has_bin_console(folder) and (
        requires_package(folder, "symfony/framework-bundle") or is_regular_file(folder / "symfony.lock")
    )


def is_drupal(folder: Path) -> bool:
    return (
        is_regular_file(folder / "core" / "lib" / "Drupal.php")
        or is_regular_file(folder / "web" / "core" / "lib" / "Drupal.php")
        or requires_package(folder, "drupal/core-recommended")
    )


def is_joomla(folder: Path) -> bool:
    return is_directory(folder / "administrator") and is_directory(folder / "libraries" / "src")


def has_bedrock_web_app_folder(folder: Path) -> bool:
    return is_directory(folder / "web" / "app")


def is_wordpress_theme(folder: Path) -> bool:
    """A `Theme Name:` in style.css's first 20 lines, read from its first 8 KiB as WordPress reads theme headers."""
    header_text = read_wordpress_header(folder / "style.css")
    return any("Theme Name:" in line for line in header_text.splitlines()[:THEME_HEADER_LINE_COUNT])


def is_wordpress_plugin(folder: Path) -> bool:
    """A `Plugin Name:` in the first 8 KiB of a PHP file at the folder's top, where WordPress reads plugin headers."""
    try:
        top_level_php_files = list(folder.glob("*.php"))
    except OSError:
        return False
    return any("Plugin Name:" in read_wordpress_header(php_file) for php_file in top_level_php_files)


def has_wp_content_folders(folder: Path) -> bool:
    return is_directory(folder / "themes") and is_directory(folder / "plugins")


def holds_wordpress_marker(folder: Path) -> bool:
    return (
        is_regular_file(folder / "wp-config.php")
        or requires_roots_wordpress(folder)
        or has_bedrock_web_app_folder(folder)
        or is_wordpress_theme(folder)
    )


def is_wordpress(folder: Path) -> bool:
    """A WordPress marker, or themes/ and plugins/ side by side: a wp-content repo, reached by walking to a theme."""
    return holds_wordpress_marker(folder) or has_wp_content_folders(folder)


def holds_app_marker(folder: Path) -> bool:
    """A marker of a named app. index.php is not one: it is how a plain PHP app is found, at the folder given only."""
    return (
        holds_wordpress_marker(folder)
        or has_artisan(folder)
        or has_bin_console(folder)
        or requires_package(folder, "statamic/cms")
        or requires_package(folder, "symfony/framework-bundle")
        or is_drupal(folder)
        or is_joomla(folder)
    )


def is_inside_wordpress_content(folder: Path) -> bool:
    """The folder or one of its first two parents is wp-content, plugins, themes or mu-plugins."""
    resolved_folder = folder.resolve()
    nearest_folder_names = (resolved_folder.name, resolved_folder.parent.name, resolved_folder.parent.parent.name)
    return any(folder_name in WORDPRESS_CONTENT_FOLDER_NAMES for folder_name in nearest_folder_names)


def has_root_index_php_of_its_own(folder: Path) -> bool:
    """An index.php at the folder's root, unless WordPress put it there: a "Silence is golden" file in
    wp-content/, plugins/ or themes/, or the one beside a standalone plugin's header."""
    return (
        is_regular_file(folder / "index.php")
        and not is_inside_wordpress_content(folder)
        and not is_wordpress_plugin(folder)
    )


def has_docroot_index_php_of_its_own(folder: Path) -> bool:
    """An index.php under public/ or web/, unless that folder holds an app marker of its own.

    WordPress ships an index.php. Local installs it at <site>/app/public and agencies keep it
    in public/ beside their build tools; neither app/ nor that root is a plain PHP app.
    """
    return any(
        is_regular_file(folder / docroot / "index.php") and not holds_app_marker(folder / docroot)
        for docroot in SUBFOLDER_DOCROOTS
    )


def holds_site_marker(folder: Path) -> bool:
    return (
        holds_app_marker(folder)
        or has_root_index_php_of_its_own(folder)
        or has_docroot_index_php_of_its_own(folder)
    )


def is_home_or_filesystem_root(folder: Path) -> bool:
    resolved_folder = folder.resolve()
    if resolved_folder.parent == resolved_folder:
        return True
    try:
        return resolved_folder == Path.home().resolve()
    except (OSError, RuntimeError):
        return False


def promote_to_wp_content_root(candidate: Path, cwd: Path) -> Path:
    """<root>/themes/<name> with a plugins/ beside themes/ is one wp-content repo: its site root is <root>."""
    wp_content_root = candidate.parent.parent
    is_inside_given_folder = wp_content_root == cwd or cwd in wp_content_root.parents
    is_theme_of_wp_content_root = (
        candidate.parent.name == "themes"
        and is_wordpress_theme(candidate)
        and is_directory(wp_content_root / "plugins")
    )
    return wp_content_root if is_theme_of_wp_content_root and is_inside_given_folder else candidate


def promote_to_framework_root(folder: Path) -> Path:
    """A public/ opened on its own under artisan or bin/console is a framework's docroot: the outer marker wins."""
    resolved_folder = folder.resolve()
    app_root = resolved_folder.parent
    is_framework_docroot = (
        resolved_folder.name == "public"
        and not is_home_or_filesystem_root(app_root)
        and (has_artisan(app_root) or has_bin_console(app_root))
    )
    return app_root if is_framework_docroot else folder


def find_site_root(cwd: Path) -> Path | None:
    """The folder itself, else the one site one or two levels down; a parent of several sites is not a site.

    A Laravel, Statamic or Symfony public/ opened on its own gives the app root above it.
    Below the folder given only app markers count: WordPress leaves an index.php in
    wp-content/, plugins/ and themes/, so a plain PHP app is found only as the folder itself.

    Home and the filesystem root are never looked into: listing ~/Documents or ~/Desktop
    raises a macOS file-access prompt, and a hook must never prompt.
    """
    if is_home_or_filesystem_root(cwd):
        return None
    if holds_site_marker(cwd):
        return promote_to_framework_root(cwd)
    folders_one_level_down = list_child_folders(cwd)
    candidates = [folder for folder in folders_one_level_down if holds_app_marker(folder)]
    if not candidates:
        candidates = [
            folder
            for folder_one_level_down in folders_one_level_down
            for folder in list_child_folders(folder_one_level_down)
            if holds_app_marker(folder)
        ]
    site_roots = []
    for candidate in candidates:
        site_root = promote_to_wp_content_root(candidate, cwd)
        if site_root not in site_roots:
            site_roots.append(site_root)
    return site_roots[0] if len(site_roots) == 1 else None


def detect_app(site_root: Path) -> str | None:
    """Statamic before Laravel, since both carry artisan; a plain PHP app only when nothing more particular matches."""
    if has_artisan(site_root):
        return "statamic" if requires_package(site_root, "statamic/cms") else "laravel"
    if is_symfony(site_root):
        return "symfony"
    if is_wordpress(site_root):
        return "wordpress"
    if is_drupal(site_root):
        return "drupal"
    if is_joomla(site_root):
        return "joomla"
    if has_index_php(site_root):
        return "phpapp"
    return None


def detect_tree_shape(site_root: Path) -> str:
    if has_artisan(site_root) or has_bin_console(site_root):
        return "whole_tree"
    if requires_roots_wordpress(site_root) or has_bedrock_web_app_folder(site_root):
        return "bedrock"
    if is_regular_file(site_root / "wp-config.php"):
        return "whole_tree"
    if has_wp_content_folders(site_root):
        return "wp_content_only"
    if is_wordpress_theme(site_root):
        return "theme_only"
    return "none"


def detect_app_and_shape(site_root: Path, has_git: bool, has_remote: bool) -> tuple[str | None, str]:
    """The app, and the devsite-import git shape: no git and no origin outrank what the tree looks like.

    Only WordPress has partial-tree shapes (Bedrock, wp-content, a theme); any other app's repo is
    the whole tree, so "none" keeps meaning "no .git" for the skills that read it.
    """
    app = detect_app(site_root)
    if not has_git:
        return app, "none"
    if not has_remote:
        return app, "no_remote"
    if app is not None and app != "wordpress":
        return app, "whole_tree"
    return app, detect_tree_shape(site_root)


def detect_docroot_guess(site_root: Path, app: str | None) -> str:
    """The plan's docroot default: public/ for the frameworks, where index.php sits for a plain PHP app, else ""."""
    if app in APPS_SERVED_FROM_PUBLIC:
        return "public"
    if app == "phpapp":
        for docroot in INDEX_PHP_DOCROOTS:
            if is_regular_file(site_root / docroot / "index.php"):
                return docroot
    return ""


def strip_user_info(remote_url: str) -> str:
    """Drop user[:password]@ from scheme:// URLs; an scp-style git@host:path remote is returned unchanged."""
    return URL_WITH_USER_INFO.sub(r"\g<scheme>", remote_url)


def read_root_commit(site_root: Path) -> str | None:
    """A shallow clone reports its cut-off commit as a root, so a shallow clone has none."""
    is_shallow_answer = run_quietly(["git", "rev-parse", "--is-shallow-repository"], site_root)
    if is_shallow_answer is None or is_shallow_answer.strip() != "false":
        return None
    root_commit_lines = run_quietly(["git", "rev-list", "--max-parents=0", "HEAD"], site_root)
    if root_commit_lines is None:
        return None
    root_commits = root_commit_lines.split()
    if len(root_commits) != 1 or not ROOT_COMMIT_HASH.fullmatch(root_commits[0]):
        return None
    return root_commits[0]


def is_repository_of_this_site(repository_root: Path, cwd: Path) -> bool:
    """git searches upward, so a gitless site inside someone else's repo would borrow that repo's identity.

    A repo found above the folder given is the site's own only when it is itself a site
    (a theme folder opened inside a WordPress repo); otherwise it is an unrelated parent.
    """
    resolved_repository_root = repository_root.resolve()
    resolved_cwd = cwd.resolve()
    if resolved_repository_root == resolved_cwd or resolved_cwd in resolved_repository_root.parents:
        return True
    return holds_site_marker(resolved_repository_root)


def git_facts(site_root: Path, cwd: Path | None = None) -> dict:
    no_git_facts = {"has_git": False, "remote_url": None, "branch": None, "root_commit": None, "is_dirty": False}
    repository_root_answer = run_quietly(["git", "rev-parse", "--show-toplevel"], site_root)
    if repository_root_answer is None or not repository_root_answer.strip():
        return no_git_facts
    if not is_repository_of_this_site(Path(repository_root_answer.rstrip("\r\n")), cwd or site_root):
        return no_git_facts
    origin_url = (run_quietly(["git", "remote", "get-url", "origin"], site_root) or "").strip()
    branch_name = (run_quietly(["git", "symbolic-ref", "--short", "-q", "HEAD"], site_root) or "").strip()
    porcelain_status = run_quietly(
        ["git", "-c", "core.fsmonitor=false", "--no-optional-locks", "status", "--porcelain"], site_root
    )
    return {
        "has_git": True,
        "remote_url": strip_user_info(origin_url) if origin_url else None,
        "branch": branch_name or None,
        "root_commit": read_root_commit(site_root),
        "is_dirty": bool(porcelain_status and porcelain_status.strip()),
    }


def unquote_dot_env_value(raw_value: str) -> str:
    if raw_value[:1] in ("'", '"'):
        quote = raw_value[0]
        closing_quote_index = raw_value.find(quote, 1)
        return raw_value[1:] if closing_quote_index == -1 else raw_value[1:closing_quote_index]
    return re.split(r"\s+#", raw_value, maxsplit=1)[0].strip()


def host_and_port_from(url_value: str) -> str | None:
    authority = URL_AUTHORITY.match(url_value.strip())
    if authority is None:
        return None
    host_and_port = authority.group("host_and_port").lower()
    return host_and_port if HOST_AND_PORT.fullmatch(host_and_port) else None


def hostnames_from(site_root: Path) -> list[str]:
    """host[:port] of APP_URL, WP_HOME, WP_SITEURL and DOMAIN_CURRENT_SITE; no other value is ever kept."""
    url_values = []
    for line in read_text_or_empty(site_root / ".env").splitlines():
        hostname_line = DOT_ENV_HOSTNAME_LINE.match(line)
        if hostname_line:
            url_values.append(unquote_dot_env_value(hostname_line.group("raw_value")))
    for hostname_define in WP_CONFIG_HOSTNAME_DEFINE.finditer(read_text_or_empty(site_root / "wp-config.php")):
        url_values.append(hostname_define.group("value"))
    hostnames = []
    for url_value in url_values:
        host_and_port = host_and_port_from(url_value)
        if host_and_port is not None and host_and_port not in hostnames:
            hostnames.append(host_and_port)
    return hostnames


def read_php_version(site_root: Path) -> str | None:
    php_banner = run_quietly(["php", "-v"], site_root)
    version_line = PHP_VERSION_LINE.search(php_banner) if php_banner else None
    return version_line.group(1) if version_line else None


def choose_folder_name(site_root: Path, cwd: Path) -> str:
    """The folder given names the project (Local's <site>/app/public is named <site>), except a framework's
    public/ promoted to its app root: "public" names nothing, so the app root's name is used."""
    resolved_cwd = cwd.resolve()
    resolved_site_root = site_root.resolve()
    return resolved_site_root.name if resolved_site_root in resolved_cwd.parents else resolved_cwd.name


def collect_facts(cwd: Path) -> dict:
    site_root = find_site_root(cwd)
    if site_root is None:
        return {"is_site": False}
    facts_from_git = git_facts(site_root, cwd)
    app, shape = detect_app_and_shape(
        site_root,
        has_git=facts_from_git["has_git"],
        has_remote=facts_from_git["remote_url"] is not None,
    )
    return {
        "is_site": True,
        "repo": {
            "remote_url": facts_from_git["remote_url"],
            "root_commit": facts_from_git["root_commit"],
            "branch": facts_from_git["branch"],
            "hostnames": hostnames_from(site_root),
            "folder_name": choose_folder_name(site_root, cwd),
            "app": app,
        },
        "shape": shape,
        "docroot_guess": detect_docroot_guess(site_root, app),
        "dirty": facts_from_git["is_dirty"],
        "php": read_php_version(site_root),
    }


def give_up_silently(signal_number, interrupted_frame) -> None:
    """Exit 0 with nothing printed. SystemExit, not os._exit, so a running git is killed on the way out."""
    sys.exit(0)


def deadline_seconds() -> int:
    """RECON_DEADLINE_SECONDS, unless the environment names a shorter positive
    number — the tests' knob for proving the alarm fires, since every git call
    ends at its own timeout long before five seconds."""
    try:
        override_seconds = int(os.environ.get("RECON_DEADLINE_SECONDS", ""))
    except ValueError:
        return RECON_DEADLINE_SECONDS
    if 0 < override_seconds < RECON_DEADLINE_SECONDS:
        return override_seconds
    return RECON_DEADLINE_SECONDS


def arm_deadline() -> None:
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, give_up_silently)
        signal.alarm(deadline_seconds())


def disarm_deadline() -> None:
    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)


def main(argv: list[str]) -> int:
    arm_deadline()
    try:
        cwd = Path(argv[1]) if len(argv) > 1 else Path.cwd()
        facts_json = json.dumps(collect_facts(cwd))
        disarm_deadline()
        print(facts_json)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
