import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RECON = Path(__file__).resolve().parents[1] / "hooks" / "recon.py"
DEFAULT_REMOTE = "git@github.com:ake/site.git"
REPO_KEYS = ["remote_url", "root_commit", "branch", "hostnames", "folder_name", "app"]


def run_git(repository, *arguments):
    subprocess.run(
        [
            "git", "-C", str(repository),
            "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
            "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}",
            *arguments,
        ],
        check=True, capture_output=True, text=True, timeout=10,
    )


def init_git_repository(repository, remote):
    run_git(repository, "init", "-q")
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-q", "-m", "first commit")
    if remote is not None:
        run_git(repository, "remote", "add", "origin", remote)


def make_wordpress(site_folder, *, git=True, remote=DEFAULT_REMOTE, env=None, wp_config_defines=None):
    (site_folder / "wp-content" / "themes").mkdir(parents=True, exist_ok=True)
    (site_folder / "wp-content" / "index.php").write_text("<?php\n")
    (site_folder / "wp-includes").mkdir(exist_ok=True)
    wp_config_lines = ["<?php", "define('DB_NAME', 'local');", "define('DB_PASSWORD', 'wp-config-secret');"]
    for key, value in (wp_config_defines or {}).items():
        wp_config_lines.append(f"define('{key}', '{value}');")
    (site_folder / "wp-config.php").write_text("\n".join(wp_config_lines) + "\n")
    if env is not None:
        (site_folder / ".env").write_text(env)
    if git:
        init_git_repository(site_folder, remote)


def make_laravel(site_folder, *, git=True, remote=DEFAULT_REMOTE, env=None):
    site_folder.mkdir(parents=True, exist_ok=True)
    (site_folder / "artisan").write_text("#!/usr/bin/env php\n<?php\n")
    (site_folder / "composer.json").write_text('{"require": {"laravel/framework": "^11.0"}}\n')
    if env is not None:
        (site_folder / ".env").write_text(env)
    if git:
        init_git_repository(site_folder, remote)


def make_bedrock(site_folder, *, git=True, remote=DEFAULT_REMOTE):
    (site_folder / "web" / "app" / "mu-plugins").mkdir(parents=True, exist_ok=True)
    (site_folder / "web" / "app" / "mu-plugins" / ".gitkeep").write_text("")
    (site_folder / "composer.json").write_text('{"require": {"roots/wordpress": "6.5.0"}}\n')
    if git:
        init_git_repository(site_folder, remote)


def make_theme_only(site_folder, *, git=True, remote=DEFAULT_REMOTE):
    site_folder.mkdir(parents=True, exist_ok=True)
    (site_folder / "style.css").write_text("/*\nTheme Name: Fixture Theme\nVersion: 1.0\n*/\n")
    (site_folder / "functions.php").write_text("<?php\n")
    if git:
        init_git_repository(site_folder, remote)


def make_not_a_site(repository):
    repository.mkdir(parents=True, exist_ok=True)
    (repository / "README.md").write_text("# Not a site\n")
    init_git_repository(repository, DEFAULT_REMOTE)


def recon(cwd, environment=None):
    completed = subprocess.run([sys.executable, str(RECON), str(cwd)], capture_output=True, text=True, timeout=5,
                               env=environment)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def load_recon_module():
    specification = importlib.util.spec_from_file_location("recon", RECON)
    recon_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(recon_module)
    return recon_module


def test_a_classic_wordpress_repo_gives_remote_branch_root_and_shape(tmp_path):
    make_wordpress(tmp_path)
    facts = recon(tmp_path)
    assert facts["is_site"] is True
    assert list(facts) == ["is_site", "repo", "shape", "dirty", "php"]
    assert list(facts["repo"]) == REPO_KEYS
    assert facts["repo"]["remote_url"] == "git@github.com:ake/site.git"
    assert facts["repo"]["branch"] in ("main", "master")
    assert len(facts["repo"]["root_commit"]) == 40
    assert facts["repo"]["folder_name"] == tmp_path.name
    assert facts["repo"]["app"] == "wordpress" and facts["shape"] == "whole_tree"


def test_hostnames_come_from_the_four_keys_and_nothing_else_leaks(tmp_path):
    make_wordpress(tmp_path, env="APP_URL=http://my-site.test:8080/app\nWP_HOME=https://Www.Example.co.nz\nDB_PASSWORD=hunter2\n",
                   wp_config_defines={"WP_SITEURL": "https://www.example.co.nz/wp", "DOMAIN_CURRENT_SITE": "example.co.nz"})
    facts = recon(tmp_path)
    assert facts["repo"]["hostnames"] == ["my-site.test:8080", "www.example.co.nz", "example.co.nz"]
    assert "hunter2" not in json.dumps(facts)
    assert "wp-config-secret" not in json.dumps(facts)


def test_quotes_comments_and_look_alike_keys_in_dot_env_and_double_quoted_defines(tmp_path):
    dot_env = (
        "# APP_URL=http://commented-out.test\n"
        'APP_URL="http://quoted.test:8000" # trailing comment\n'
        "WP_HOME='https://single-quoted.example.co.nz'\n"
        "APP_URL_PREFIX=http://wrong-key.test\n"
        "MY_APP_URL=http://also-wrong.test\n"
    )
    make_wordpress(tmp_path, env=dot_env)
    wp_config = tmp_path / "wp-config.php"
    wp_config.write_text(wp_config.read_text() + 'define( "WP_SITEURL", "http://Double.Quoted.test/wp" );\n'
                         "define('WP_HOME', 'http://' . $_SERVER['HTTP_HOST']);\n")
    assert recon(tmp_path)["repo"]["hostnames"] == [
        "quoted.test:8000", "single-quoted.example.co.nz", "double.quoted.test"]


def test_user_info_inside_a_hostname_key_value_never_reaches_the_output(tmp_path):
    make_wordpress(tmp_path, env="APP_URL=https://admin:s3cret@my-site.test/\n")
    facts = recon(tmp_path)
    assert facts["repo"]["hostnames"] == ["my-site.test"]
    assert "s3cret" not in json.dumps(facts)


def test_a_token_in_the_remote_is_stripped(tmp_path):
    make_wordpress(tmp_path, remote="https://x:ghp_y@github.com/o/r.git")
    facts = recon(tmp_path)
    assert facts["repo"]["remote_url"] == "https://github.com/o/r.git"
    assert "ghp_y" not in json.dumps(facts)


def test_a_shallow_clone_has_no_root_commit_and_no_error(tmp_path):
    origin = tmp_path / "origin"
    make_wordpress(origin)
    (origin / "second.txt").write_text("a second commit, so a depth-1 clone really is shallow\n")
    run_git(origin, "add", "second.txt")
    run_git(origin, "commit", "-q", "-m", "second commit")
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(shallow)],
                   check=True, capture_output=True, text=True, timeout=10)
    facts = recon(shallow)
    assert facts["is_site"] is True
    assert facts["repo"]["root_commit"] is None
    assert facts["repo"]["remote_url"] == origin.as_uri()
    assert facts["repo"]["branch"] in ("main", "master")
    assert facts["repo"]["folder_name"] == "shallow"
    assert facts["shape"] == "whole_tree"


def test_no_git_is_shape_none_and_a_remote_less_repo_is_no_remote(tmp_path):
    no_git_folder = tmp_path / "no-git"
    make_wordpress(no_git_folder, git=False)
    no_git_facts = recon(no_git_folder)
    assert no_git_facts["shape"] == "none"
    assert no_git_facts["dirty"] is False
    assert [no_git_facts["repo"][key] for key in ("remote_url", "root_commit", "branch")] == [None, None, None]
    assert no_git_facts["repo"]["app"] == "wordpress"
    assert no_git_facts["repo"]["folder_name"] == "no-git"

    no_remote_folder = tmp_path / "no-remote"
    make_wordpress(no_remote_folder, remote=None)
    no_remote_facts = recon(no_remote_folder)
    assert no_remote_facts["shape"] == "no_remote"
    assert no_remote_facts["repo"]["remote_url"] is None
    assert len(no_remote_facts["repo"]["root_commit"]) == 40


def test_bedrock_laravel_and_theme_only_are_told_apart(tmp_path):
    make_bedrock(tmp_path / "bedrock")
    bedrock_facts = recon(tmp_path / "bedrock")
    assert (bedrock_facts["repo"]["app"], bedrock_facts["shape"]) == ("wordpress", "bedrock")

    make_laravel(tmp_path / "laravel", env="APP_URL=http://laravel.test\n")
    laravel_facts = recon(tmp_path / "laravel")
    assert (laravel_facts["repo"]["app"], laravel_facts["shape"]) == ("laravel", "whole_tree")
    assert laravel_facts["repo"]["hostnames"] == ["laravel.test"]

    make_theme_only(tmp_path / "theme")
    theme_facts = recon(tmp_path / "theme")
    assert (theme_facts["repo"]["app"], theme_facts["shape"]) == ("wordpress", "theme_only")


def test_a_style_css_without_a_theme_name_in_its_first_twenty_lines_is_not_a_theme(tmp_path):
    (tmp_path / "style.css").write_text("body { color: red; }\n" * 25 + "/* Theme Name: too late */\n")
    init_git_repository(tmp_path, DEFAULT_REMOTE)
    assert recon(tmp_path) == {"is_site": False}


def test_a_folder_that_is_not_a_site_says_so(tmp_path):
    make_not_a_site(tmp_path)
    assert recon(tmp_path) == {"is_site": False}


def test_a_site_two_folders_down_is_found_but_named_by_the_folder_given(tmp_path):
    local_sites_folder = tmp_path / "my-local-site"
    make_wordpress(local_sites_folder / "app" / "public", git=False)
    init_git_repository(local_sites_folder, DEFAULT_REMOTE)
    facts = recon(local_sites_folder)
    assert facts["is_site"] is True
    assert facts["repo"]["folder_name"] == "my-local-site"
    assert facts["repo"]["app"] == "wordpress" and facts["shape"] == "whole_tree"
    assert facts["repo"]["remote_url"] == "git@github.com:ake/site.git"


def test_a_site_three_folders_down_is_not_looked_for(tmp_path):
    make_wordpress(tmp_path / "one" / "two" / "three", git=False)
    assert recon(tmp_path) == {"is_site": False}


def test_dirty_reads_the_working_tree(tmp_path):
    make_wordpress(tmp_path)
    assert recon(tmp_path)["dirty"] is False
    (tmp_path / "unsaved-change.txt").write_text("not committed\n")
    assert recon(tmp_path)["dirty"] is True


def test_php_is_major_dot_minor_or_null(tmp_path):
    make_wordpress(tmp_path)
    php_version = recon(tmp_path)["php"]
    assert php_version is None or (len(php_version.split(".")) == 2 and all(part.isdigit() for part in php_version.split(".")))


def test_a_folder_that_does_not_exist_is_not_a_site_and_not_an_error(tmp_path):
    assert recon(tmp_path / "missing") == {"is_site": False}


def test_strip_user_info_strips_url_credentials_and_leaves_scp_remotes_alone():
    recon_module = load_recon_module()
    assert recon_module.strip_user_info("git@github.com:ake/site.git") == "git@github.com:ake/site.git"
    assert recon_module.strip_user_info("ssh://git@host.example/o/r.git") == "ssh://host.example/o/r.git"
    assert recon_module.strip_user_info("https://user:p@ss@host.example/o/r.git") == "https://host.example/o/r.git"


def test_wp_content_only_is_a_themes_and_plugins_folder_with_no_wp_config(tmp_path):
    recon_module = load_recon_module()
    (tmp_path / "themes").mkdir()
    (tmp_path / "plugins").mkdir()
    assert recon_module.detect_app_and_shape(tmp_path, has_git=True, has_remote=True) == ("wordpress", "wp_content_only")
    assert recon_module.detect_app_and_shape(tmp_path, has_git=True, has_remote=False) == ("wordpress", "no_remote")
    assert recon_module.detect_app_and_shape(tmp_path, has_git=False, has_remote=False) == ("wordpress", "none")
    (tmp_path / "wp-config.php").write_text("<?php\n")
    assert recon_module.detect_app_and_shape(tmp_path, has_git=True, has_remote=True) == ("wordpress", "whole_tree")


def test_a_gitless_site_inside_an_unrelated_parent_repo_reports_no_git(tmp_path):
    dotfiles_home = tmp_path / "dotfiles-home"
    dotfiles_home.mkdir()
    (dotfiles_home / ".zshrc").write_text("export EDITOR=vim\n")
    init_git_repository(dotfiles_home, "git@github.com:carl/dotfiles.git")
    blog_folder = dotfiles_home / "Sites" / "blog"
    make_wordpress(blog_folder, git=False)
    facts = recon(blog_folder)
    assert facts["is_site"] is True
    assert [facts["repo"][key] for key in ("remote_url", "root_commit", "branch")] == [None, None, None]
    assert facts["shape"] == "none"
    assert facts["dirty"] is False
    assert "dotfiles" not in json.dumps(facts)


def test_a_repo_that_starts_at_the_folder_given_still_owns_a_site_below_it(tmp_path):
    site_repository = tmp_path / "monorepo"
    make_wordpress(site_repository / "sites" / "blog", git=False)
    init_git_repository(site_repository, DEFAULT_REMOTE)
    facts = recon(site_repository)
    assert facts["repo"]["remote_url"] == DEFAULT_REMOTE
    assert len(facts["repo"]["root_commit"]) == 40


def test_a_theme_folder_opened_inside_a_wordpress_repo_keeps_the_repos_git(tmp_path):
    make_wordpress(tmp_path)
    theme_folder = tmp_path / "wp-content" / "themes" / "foo"
    theme_folder.mkdir(parents=True)
    (theme_folder / "style.css").write_text("/*\nTheme Name: Foo\n*/\n")
    run_git(tmp_path, "add", "-A")
    run_git(tmp_path, "commit", "-q", "-m", "add the theme")
    facts = recon(theme_folder)
    assert facts["repo"]["remote_url"] == DEFAULT_REMOTE
    assert len(facts["repo"]["root_commit"]) == 40
    assert facts["repo"]["folder_name"] == "foo"
    assert (facts["repo"]["app"], facts["shape"]) == ("wordpress", "theme_only")


def test_a_repo_of_themes_and_plugins_with_no_wp_config_is_wp_content_only(tmp_path):
    wp_content_repository = tmp_path / "client-wp-content"
    for theme_name in ("alpha", "beta"):
        (wp_content_repository / "themes" / theme_name).mkdir(parents=True)
        (wp_content_repository / "themes" / theme_name / "style.css").write_text(f"/*\nTheme Name: {theme_name}\n*/\n")
    (wp_content_repository / "plugins").mkdir()
    (wp_content_repository / "plugins" / "index.php").write_text("<?php\n")
    init_git_repository(wp_content_repository, DEFAULT_REMOTE)
    facts = recon(wp_content_repository)
    assert facts["is_site"] is True
    assert facts["repo"]["app"] == "wordpress"
    assert facts["shape"] == "wp_content_only"
    assert facts["repo"]["folder_name"] == "client-wp-content"
    assert facts["repo"]["remote_url"] == DEFAULT_REMOTE


def test_a_themes_folder_without_plugins_is_found_as_the_theme_alone(tmp_path):
    (tmp_path / "themes" / "alpha").mkdir(parents=True)
    (tmp_path / "themes" / "alpha" / "style.css").write_text("/*\nTheme Name: alpha\n*/\n")
    init_git_repository(tmp_path, DEFAULT_REMOTE)
    facts = recon(tmp_path)
    assert (facts["repo"]["app"], facts["shape"]) == ("wordpress", "theme_only")
    assert facts["repo"]["folder_name"] == tmp_path.name


def test_the_home_directory_is_never_walked(tmp_path):
    make_wordpress(tmp_path / "Sites" / "blog", git=False)
    with_tmp_path_as_home = {**os.environ, "HOME": str(tmp_path)}
    assert recon(tmp_path, environment=with_tmp_path_as_home) == {"is_site": False}
    with_another_home = {**os.environ, "HOME": str(tmp_path / "somebody-else")}
    assert recon(tmp_path, environment=with_another_home)["is_site"] is True


def test_the_home_directory_and_the_filesystem_root_are_not_listed_at_all(tmp_path, monkeypatch):
    recon_module = load_recon_module()

    def fail_if_looked_at(folder):
        raise AssertionError(f"looked inside {folder}")

    monkeypatch.setattr(recon_module, "list_child_folders", fail_if_looked_at)
    monkeypatch.setattr(recon_module, "holds_site_marker", fail_if_looked_at)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert recon_module.find_site_root(tmp_path) is None
    assert recon_module.find_site_root(Path(tmp_path.anchor)) is None


def test_a_parent_of_several_sites_is_not_a_site(tmp_path):
    sites_folder = tmp_path / "Sites"
    make_wordpress(sites_folder / "blog", git=False)
    make_wordpress(sites_folder / "shop", git=False)
    assert recon(sites_folder) == {"is_site": False}


def test_the_shallowest_site_wins_over_a_deeper_one(tmp_path):
    sites_folder = tmp_path / "Sites"
    make_wordpress(sites_folder / "blog", git=False, env="APP_URL=http://blog.test\n")
    make_wordpress(sites_folder / "archive" / "old-shop", git=False, env="APP_URL=http://old-shop.test\n")
    facts = recon(sites_folder)
    assert facts["repo"]["hostnames"] == ["blog.test"]
    assert facts["repo"]["folder_name"] == "Sites"


def test_a_repo_local_fsmonitor_command_is_never_run(tmp_path):
    site_folder = tmp_path / "site"
    make_wordpress(site_folder)
    marker_file = tmp_path / "fsmonitor-ran"
    hook_script = tmp_path / "fsmonitor-hook.sh"
    hook_script.write_text(f"#!/bin/sh\ntouch '{marker_file}'\n")
    hook_script.chmod(0o755)
    run_git(site_folder, "config", "core.fsmonitor", str(hook_script))
    subprocess.run(["git", "-C", str(site_folder), "status", "--porcelain"], capture_output=True, timeout=10)
    assert marker_file.exists(), "fixture is wrong: a plain git status should have run the hook"
    marker_file.unlink()
    recon(site_folder)
    assert not marker_file.exists()


def test_recon_is_fast(tmp_path):
    make_wordpress(tmp_path)
    started = time.monotonic(); recon(tmp_path)
    assert time.monotonic() - started < 1.0
