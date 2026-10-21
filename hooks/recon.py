#!/usr/bin/env python3
"""Print what identifies the 16h site in a folder, as one JSON object.

Local and read-only: no network, no prompt, no file written, and the only
values read out of .env and wp-config.php are the host parts of four URL keys.
Prints {"is_site": false} when the folder holds no site, prints nothing when
anything fails, and always exits 0 so a hook calling it can never block a session.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SUBPROCESS_TIMEOUT_SECONDS = 2
THEME_HEADER_LINE_COUNT = 20
HOSTNAME_KEYS = ("APP_URL", "WP_HOME", "WP_SITEURL", "DOMAIN_CURRENT_SITE")
FOLDERS_NOT_WORTH_WALKING = ("node_modules", "vendor")

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


def read_text_or_empty(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def list_child_folders(folder: Path) -> list[Path]:
    child_folders = []
    try:
        for child in sorted(folder.iterdir()):
            is_worth_walking = not child.name.startswith(".") and child.name not in FOLDERS_NOT_WORTH_WALKING
            if is_worth_walking and child.is_dir():
                child_folders.append(child)
    except OSError:
        pass
    return child_folders


def requires_roots_wordpress(folder: Path) -> bool:
    return '"roots/wordpress"' in read_text_or_empty(folder / "composer.json")


def has_bedrock_web_app_folder(folder: Path) -> bool:
    return (folder / "web" / "app").is_dir()


def is_wordpress_theme(folder: Path) -> bool:
    try:
        with (folder / "style.css").open(encoding="utf-8", errors="replace") as stylesheet:
            for line_number, line in enumerate(stylesheet):
                if line_number >= THEME_HEADER_LINE_COUNT:
                    return False
                if "Theme Name:" in line:
                    return True
    except OSError:
        return False
    return False


def has_wp_content_folders(folder: Path) -> bool:
    return (folder / "themes").is_dir() and (folder / "plugins").is_dir()


def holds_site_marker(folder: Path) -> bool:
    return (
        (folder / "wp-config.php").is_file()
        or (folder / "artisan").is_file()
        or requires_roots_wordpress(folder)
        or has_bedrock_web_app_folder(folder)
        or is_wordpress_theme(folder)
    )


def find_site_root(cwd: Path) -> Path | None:
    """The folder itself, else the first folder one or two levels down that holds a site marker."""
    if holds_site_marker(cwd):
        return cwd
    folders_one_level_down = list_child_folders(cwd)
    for folder in folders_one_level_down:
        if holds_site_marker(folder):
            return folder
    for folder_one_level_down in folders_one_level_down:
        for folder in list_child_folders(folder_one_level_down):
            if holds_site_marker(folder):
                return folder
    return None


def detect_app(site_root: Path) -> str | None:
    if (site_root / "artisan").is_file():
        return "laravel"
    is_wordpress = (
        (site_root / "wp-config.php").is_file()
        or requires_roots_wordpress(site_root)
        or has_bedrock_web_app_folder(site_root)
        or is_wordpress_theme(site_root)
        or has_wp_content_folders(site_root)
    )
    return "wordpress" if is_wordpress else None


def detect_tree_shape(site_root: Path) -> str:
    if (site_root / "artisan").is_file():
        return "whole_tree"
    if requires_roots_wordpress(site_root) or has_bedrock_web_app_folder(site_root):
        return "bedrock"
    if (site_root / "wp-config.php").is_file():
        return "whole_tree"
    if has_wp_content_folders(site_root):
        return "wp_content_only"
    if is_wordpress_theme(site_root):
        return "theme_only"
    return "none"


def detect_app_and_shape(site_root: Path, has_git: bool, has_remote: bool) -> tuple[str | None, str]:
    """The app, and the devsite-import git shape: no git and no origin outrank what the tree looks like."""
    app = detect_app(site_root)
    if not has_git:
        return app, "none"
    if not has_remote:
        return app, "no_remote"
    return app, detect_tree_shape(site_root)


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


def git_facts(site_root: Path) -> dict:
    no_git_facts = {"has_git": False, "remote_url": None, "branch": None, "root_commit": None, "is_dirty": False}
    inside_work_tree_answer = run_quietly(["git", "rev-parse", "--is-inside-work-tree"], site_root)
    if inside_work_tree_answer is None or inside_work_tree_answer.strip() != "true":
        return no_git_facts
    origin_url = (run_quietly(["git", "remote", "get-url", "origin"], site_root) or "").strip()
    branch_name = (run_quietly(["git", "symbolic-ref", "--short", "-q", "HEAD"], site_root) or "").strip()
    porcelain_status = run_quietly(["git", "--no-optional-locks", "status", "--porcelain"], site_root)
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


def collect_facts(cwd: Path) -> dict:
    site_root = find_site_root(cwd)
    if site_root is None:
        return {"is_site": False}
    facts_from_git = git_facts(site_root)
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
            "folder_name": cwd.resolve().name,
            "app": app,
        },
        "shape": shape,
        "dirty": facts_from_git["is_dirty"],
        "php": read_php_version(site_root),
    }


def main(argv: list[str]) -> int:
    try:
        cwd = Path(argv[1]) if len(argv) > 1 else Path.cwd()
        facts_json = json.dumps(collect_facts(cwd))
        print(facts_json)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
