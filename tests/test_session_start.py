import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

RECON = Path(__file__).resolve().parents[1] / "hooks" / "recon.py"
HOOK = Path(__file__).resolve().parents[1] / "hooks" / "session-start"
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
    (site_folder / "public").mkdir(exist_ok=True); (site_folder / "public" / "index.php").write_text("<?php\n")
    if env is not None:
        (site_folder / ".env").write_text(env)
    if git:
        init_git_repository(site_folder, remote)


def make_statamic(site_folder, *, git=True, remote=DEFAULT_REMOTE):
    make_laravel(site_folder, git=False)
    (site_folder / "please").write_text("#!/usr/bin/env php\n<?php\n")
    (site_folder / "composer.json").write_text('{"require": {"laravel/framework": "^11.0", "statamic/cms": "^5.0"}}\n')
    (site_folder / "content").mkdir(exist_ok=True)
    if git: init_git_repository(site_folder, remote)


def make_symfony(site_folder, *, git=True, remote=DEFAULT_REMOTE):
    (site_folder / "bin").mkdir(parents=True, exist_ok=True)
    (site_folder / "bin" / "console").write_text("#!/usr/bin/env php\n<?php\n")
    (site_folder / "composer.json").write_text('{"require": {"symfony/framework-bundle": "^7.0"}}\n')
    (site_folder / "public").mkdir(exist_ok=True); (site_folder / "public" / "index.php").write_text("<?php\n")
    (site_folder / ".env").write_text("APP_ENV=dev\nMESSENGER_TRANSPORT_DSN=doctrine://default\n")
    if git: init_git_repository(site_folder, remote)


def make_phpapp(site_folder, docroot, *, git=True, remote=DEFAULT_REMOTE):
    target = site_folder if docroot == "." else site_folder / docroot
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.php").write_text("<?php echo 'hi';\n")
    if git: init_git_repository(site_folder, remote)


def make_static_site(site_folder, *, git=True, remote=DEFAULT_REMOTE):
    (site_folder / "dist").mkdir(parents=True, exist_ok=True)
    (site_folder / "dist" / "index.html").write_text("<!doctype html>\n")
    (site_folder / "package.json").write_text('{"scripts": {"build": "vite build"}}\n')
    if git: init_git_repository(site_folder, remote)


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
    assert list(facts) == ["is_site", "repo", "shape", "docroot_guess", "dirty", "php"]
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


def test_statamic_is_told_from_laravel_by_its_composer_requirement(tmp_path):
    make_statamic(tmp_path / "brand")
    facts = recon(tmp_path / "brand")
    assert facts["repo"]["app"] == "statamic" and facts["docroot_guess"] == "public" and facts["shape"] == "whole_tree"


def test_a_laravel_repo_with_an_unreadable_composer_json_is_still_laravel(tmp_path):
    make_laravel(tmp_path / "shop"); (tmp_path / "shop" / "composer.json").write_text("{not json")
    assert recon(tmp_path / "shop")["repo"]["app"] == "laravel"


def test_symfony_is_found_by_bin_console_and_its_bundle(tmp_path):
    make_symfony(tmp_path / "api")
    facts = recon(tmp_path / "api")
    assert facts["repo"]["app"] == "symfony" and facts["docroot_guess"] == "public"


@pytest.mark.parametrize("docroot, guess", [(".", "."), ("public", "public"), ("web", "web"), ("htdocs", "")])
def test_a_plain_php_app_is_phpapp_with_its_docroot_guess(tmp_path, docroot, guess):
    make_phpapp(tmp_path / "tools", docroot)
    facts = recon(tmp_path / "tools")
    if docroot == "htdocs":
        assert facts == {"is_site": False}        # htdocs/index.php is not a marker: the hook stays quiet
    else:
        assert facts["repo"]["app"] == "phpapp" and facts["docroot_guess"] == guess
        assert facts["shape"] == "whole_tree"


def test_a_static_site_does_not_fire_the_hook(tmp_path):
    make_static_site(tmp_path / "brochure")
    assert recon(tmp_path / "brochure") == {"is_site": False}


def test_a_statamic_site_opened_inside_public_is_found_above(tmp_path):
    make_statamic(tmp_path / "brand")
    facts = recon(tmp_path / "brand" / "public")
    assert facts["repo"]["app"] == "statamic" and facts["repo"]["folder_name"] == "brand"


def test_a_laravel_app_with_wordpress_under_public_is_named_laravel_by_the_hook(tmp_path):
    make_laravel(tmp_path / "shop")
    (tmp_path / "shop" / "public" / "wp-content").mkdir(parents=True)
    (tmp_path / "shop" / "public" / "wp-config.php").write_text("<?php\n")
    assert recon(tmp_path / "shop")["repo"]["app"] == "laravel"


def test_drupal_and_joomla_are_named_so_the_platform_can_refuse_them(tmp_path):
    drupal_site_folder = tmp_path / "drupal-site"
    (drupal_site_folder / "web" / "core" / "lib").mkdir(parents=True)
    (drupal_site_folder / "web" / "core" / "lib" / "Drupal.php").write_text("<?php\n")
    init_git_repository(drupal_site_folder, DEFAULT_REMOTE)
    joomla_site_folder = tmp_path / "joomla-site"
    (joomla_site_folder / "administrator").mkdir(parents=True)
    (joomla_site_folder / "libraries" / "src").mkdir(parents=True)
    (joomla_site_folder / "index.php").write_text("<?php\n")
    init_git_repository(joomla_site_folder, DEFAULT_REMOTE)
    drupal_facts, joomla_facts = recon(drupal_site_folder), recon(joomla_site_folder)
    assert (drupal_facts["repo"]["app"], drupal_facts["shape"]) == ("drupal", "whole_tree")
    assert (joomla_facts["repo"]["app"], joomla_facts["shape"]) == ("joomla", "whole_tree")


def test_the_repo_keys_are_still_exactly_six_and_docroot_guess_sits_beside_shape(tmp_path):
    make_laravel(tmp_path / "shop")
    facts = recon(tmp_path / "shop")
    assert list(facts["repo"]) == REPO_KEYS and "docroot_guess" in facts and "docroot_guess" not in facts["repo"]


def test_a_wordpress_in_public_lends_its_index_php_to_no_plain_php_app_above_it(tmp_path):
    # WordPress ships its own index.php. Local keeps the install at <site>/app/public, and an
    # agency repo keeps it in public/ beside its build tools: either way it is WordPress, not a phpapp.
    local_site_folder = tmp_path / "my-local-site"
    make_wordpress(local_site_folder / "app" / "public", git=False)
    (local_site_folder / "app" / "public" / "index.php").write_text("<?php\n")
    init_git_repository(local_site_folder, DEFAULT_REMOTE)
    for opened_folder in (local_site_folder, local_site_folder / "app"):
        facts = recon(opened_folder)
        assert (facts["repo"]["app"], facts["docroot_guess"]) == ("wordpress", ""), opened_folder
    agency_repository = tmp_path / "agency-site"
    make_wordpress(agency_repository / "public", git=False)
    (agency_repository / "public" / "index.php").write_text("<?php\n")
    (agency_repository / "package.json").write_text('{"scripts": {"build": "gulp"}}\n')
    init_git_repository(agency_repository, DEFAULT_REMOTE)
    agency_facts = recon(agency_repository)
    assert (agency_facts["repo"]["app"], agency_facts["shape"]) == ("wordpress", "whole_tree")


SILENCE_IS_GOLDEN = "<?php\n// Silence is golden.\n"
HELLO_DOLLY_HEADER = "<?php\n/*\nPlugin Name: Hello Dolly\nVersion: 1.7.2\n*/\n"


def test_wordpress_folders_opened_directly_are_never_a_plain_php_app(tmp_path):
    # WordPress ships a "Silence is golden" index.php in wp-content/, plugins/ and themes/, and most plugins carry one.
    blog_folder = tmp_path / "blog"
    make_wordpress(blog_folder, git=False)
    wp_content_folder = blog_folder / "wp-content"
    theme_folder = wp_content_folder / "themes" / "twentytwentyfour"
    plugin_folder = wp_content_folder / "plugins" / "hello-dolly"
    theme_folder.mkdir(parents=True); plugin_folder.mkdir(parents=True)
    (theme_folder / "style.css").write_text("/*\nTheme Name: Twenty Twenty-Four\n*/\n")
    (plugin_folder / "hello.php").write_text(HELLO_DOLLY_HEADER)
    folders_with_silence = (wp_content_folder / "themes", wp_content_folder / "plugins", theme_folder, plugin_folder)
    for folder_with_silence in folders_with_silence:
        (folder_with_silence / "index.php").write_text(SILENCE_IS_GOLDEN)
    init_git_repository(blog_folder, DEFAULT_REMOTE)
    themes_facts = recon(wp_content_folder / "themes")
    assert (themes_facts["repo"]["app"], themes_facts["shape"]) == ("wordpress", "theme_only")
    wp_content_facts = recon(wp_content_folder)
    assert (wp_content_facts["repo"]["app"], wp_content_facts["shape"]) == ("wordpress", "wp_content_only")
    assert recon(wp_content_folder / "plugins") == {"is_site": False}
    assert recon(plugin_folder) == {"is_site": False}


def test_a_standalone_wordpress_plugin_repo_stays_quiet(tmp_path):
    plugin_repository = tmp_path / "hello-dolly"
    plugin_repository.mkdir()
    (plugin_repository / "hello.php").write_text(HELLO_DOLLY_HEADER)
    (plugin_repository / "index.php").write_text(SILENCE_IS_GOLDEN)
    init_git_repository(plugin_repository, DEFAULT_REMOTE)
    assert recon(plugin_repository) == {"is_site": False}


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root reads a chmod-000 folder anyway")
def test_an_unreadable_public_or_web_folder_does_not_blank_the_project_block(tmp_path):
    make_phpapp(tmp_path / "tools", ".")
    locked_folders = [tmp_path / "tools" / "public", tmp_path / "tools" / "web"]
    for locked_folder in locked_folders:
        locked_folder.mkdir(); locked_folder.chmod(0)
    try:
        facts = recon(tmp_path / "tools")
    finally:
        for locked_folder in locked_folders:
            locked_folder.chmod(0o755)
    assert (facts["repo"]["app"], facts["docroot_guess"]) == ("phpapp", ".")


def test_composer_json_is_read_once_however_many_markers_ask(tmp_path, monkeypatch):
    recon_module = load_recon_module()
    drupal_site_folder = tmp_path / "drupal-by-composer"
    drupal_site_folder.mkdir()
    (drupal_site_folder / "composer.json").write_text('{"require-dev": {"drupal/core-recommended": "^10.3"}}\n')
    composer_json_reads = []
    read_text_unwatched = recon_module.read_text_or_empty

    def read_text_and_count_composer_json(file_path):
        if file_path.name == "composer.json":
            composer_json_reads.append(file_path)
        return read_text_unwatched(file_path)

    monkeypatch.setattr(recon_module, "read_text_or_empty", read_text_and_count_composer_json)
    site_root = recon_module.find_site_root(drupal_site_folder)
    assert site_root == drupal_site_folder and recon_module.detect_app(site_root) == "drupal"
    assert len(composer_json_reads) == 1


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


needs_mkfifo = pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no named pipes on this platform")


@needs_mkfifo
def test_named_pipes_where_recon_reads_never_block_it(tmp_path):
    # 1Password Environments mounts .env as a named pipe; opening one for reading waits for a writer.
    site_folder = tmp_path / "site"
    make_wordpress(site_folder, wp_config_defines={"WP_HOME": "https://from-wp-config.test"})
    os.mkfifo(site_folder / ".env")
    os.mkfifo(site_folder / "composer.json")
    facts = recon(site_folder)
    assert facts["is_site"] is True
    assert facts["repo"]["hostnames"] == ["from-wp-config.test"]
    pipes_only_folder = tmp_path / "pipes-only"
    pipes_only_folder.mkdir()
    os.mkfifo(pipes_only_folder / "style.css")
    os.mkfifo(pipes_only_folder / "composer.json")
    assert recon(pipes_only_folder) == {"is_site": False}


def test_a_file_over_the_read_cap_is_not_read(tmp_path):
    recon_module = load_recon_module()
    oversized_file = tmp_path / ".env"
    oversized_file.write_text("APP_URL=http://too-big.test\n" + "#" * recon_module.FILE_READ_CAP_BYTES)
    assert recon_module.read_text_or_empty(oversized_file) == ""
    small_file = tmp_path / "small.env"
    small_file.write_text("APP_URL=http://small.test\n")
    assert recon_module.read_text_or_empty(small_file) == "APP_URL=http://small.test\n"


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="no SIGALRM on this platform")
def test_recon_gives_up_silently_at_its_deadline(tmp_path):
    make_wordpress(tmp_path / "site")
    slow_bin_folder = tmp_path / "slow-bin"
    slow_bin_folder.mkdir()
    slow_git = slow_bin_folder / "git"
    slow_git.write_text("#!/bin/sh\nexec sleep 5\n")
    slow_git.chmod(0o755)
    # Every git call hangs. Each would end at its own 2 s timeout, so the
    # overall deadline is lowered to 1 s through its environment knob to prove
    # the alarm itself ends the recon, silently, before any call returns.
    environment = {**os.environ, "PATH": f"{slow_bin_folder}{os.pathsep}{os.environ['PATH']}",
                   "RECON_DEADLINE_SECONDS": "1"}
    started = time.monotonic()
    assert recon(tmp_path / "site", environment=environment) is None
    assert time.monotonic() - started < 1.9


def test_the_deadline_knob_only_ever_shortens(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("recon_under_test", RECON)
    recon_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recon_module)
    for junk_or_long in ("", "junk", "0", "-3", "60"):
        monkeypatch.setenv("RECON_DEADLINE_SECONDS", junk_or_long)
        assert recon_module.deadline_seconds() == recon_module.RECON_DEADLINE_SECONDS
    monkeypatch.setenv("RECON_DEADLINE_SECONDS", "2")
    assert recon_module.deadline_seconds() == 2


PLATFORM_VARIABLES = ("CLAUDE_PLUGIN_ROOT", "CURSOR_PLUGIN_ROOT", "COPILOT_CLI", "MUSE_PLUGIN_ROOT")


def hook_environment(*, with_claude_plugin_root=True):
    environment = {name: value for name, value in os.environ.items() if name not in PLATFORM_VARIABLES}
    if with_claude_plugin_root:
        environment["CLAUDE_PLUGIN_ROOT"] = str(HOOK.parents[1])
    return environment


def run_hook_process(*, stdin_text, environment=None, hook=HOOK, working_directory="/", interpreter="bash"):
    completed = subprocess.run(
        [interpreter, str(hook)], input=stdin_text, capture_output=True, encoding="utf-8",
        env=hook_environment() if environment is None else environment,
        cwd=working_directory, timeout=5,
    )
    assert completed.returncode == 0 and completed.stderr == "", completed.stderr
    return completed


def run_hook(cwd, *, environment=None, hook=HOOK):
    stdin_text = json.dumps({"cwd": str(cwd), "source": "startup"})
    return json.loads(run_hook_process(stdin_text=stdin_text, environment=environment, hook=hook).stdout)


def injected_context(cwd):
    return run_hook(cwd)["hookSpecificOutput"]["additionalContext"]


def copy_plugin(destination, *, with_recon, with_skill):
    (destination / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, destination / "hooks" / "session-start")
    if with_recon:
        shutil.copy(RECON, destination / "hooks" / "recon.py")
    if with_skill:
        shutil.copytree(HOOK.parents[1] / "skills" / "using-16h", destination / "skills" / "using-16h")
    return destination / "hooks" / "session-start"


def test_the_hook_injects_the_intro_and_the_project_block(tmp_path):
    make_wordpress(tmp_path)
    context = injected_context(tmp_path)
    assert "name: using-16h" in context and "## This project" in context
    assert context.index("</EXTREMELY_IMPORTANT>") < context.index("## This project")
    assert '"remote_url": "git@github.com:ake/site.git"' in context
    assert "```json\n{\n" in context
    assert "first tool call on any 16h task is site_status" in context


def test_a_non_site_gets_the_intro_alone(tmp_path):
    make_not_a_site(tmp_path)
    context = injected_context(tmp_path)
    assert "name: using-16h" in context and "## This project" not in context
    assert context.startswith("<EXTREMELY_IMPORTANT>\nYou are working with the 16h platform.")
    assert context.endswith("</EXTREMELY_IMPORTANT>")


def test_the_wrapper_names_no_tool_that_only_one_agent_has(tmp_path):
    make_not_a_site(tmp_path)
    assert "Skill tool" not in injected_context(tmp_path)


def test_the_hook_takes_cwd_from_stdin_not_from_where_it_runs(tmp_path):
    site_folder = tmp_path / "the-site-named-in-stdin"
    make_wordpress(site_folder)
    context = injected_context(site_folder)
    assert '"folder_name": "the-site-named-in-stdin"' in context


def test_the_working_tree_line_says_dirty_or_clean_with_shape_and_php(tmp_path):
    make_wordpress(tmp_path)
    assert "Working tree: clean. Shape: whole_tree. Local PHP: " in injected_context(tmp_path)
    (tmp_path / "unsaved-change.txt").write_text("not committed\n")
    assert "Working tree: dirty. Shape: whole_tree. Local PHP: " in injected_context(tmp_path)


def test_the_output_is_under_budget(tmp_path):
    make_wordpress(tmp_path)
    assert len(injected_context(tmp_path)) < 8000


def test_without_a_plugin_root_variable_the_sdk_shape_is_used(tmp_path):
    make_wordpress(tmp_path)
    output = run_hook(tmp_path, environment=hook_environment(with_claude_plugin_root=False))
    assert list(output) == ["additionalContext"]
    assert "name: using-16h" in output["additionalContext"] and "## This project" in output["additionalContext"]


def test_without_python3_the_intro_still_arrives(tmp_path):
    site_folder = tmp_path / "site"
    make_wordpress(site_folder)
    bin_folder = tmp_path / "bin"
    bin_folder.mkdir()
    for tool in ("bash", "git"):
        (bin_folder / tool).symlink_to(shutil.which(tool))
    assert shutil.which("python3", path=str(bin_folder)) is None
    environment = {**hook_environment(), "PATH": str(bin_folder)}
    completed = run_hook_process(stdin_text=json.dumps({"cwd": str(site_folder)}), environment=environment,
                                 interpreter=str(bin_folder / "bash"))
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "name: using-16h" in context and "## This project" not in context
    assert "Traceback" not in completed.stdout


def test_malformed_stdin_falls_back_to_the_folder_the_hook_runs_in(tmp_path):
    make_wordpress(tmp_path)
    for stdin_text in ("this is not json", "", "[1, 2]", '{"cwd": 7}'):
        completed = run_hook_process(stdin_text=stdin_text, working_directory=tmp_path)
        context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "name: using-16h" in context
        assert f'"folder_name": "{tmp_path.name}"' in context


@needs_mkfifo
def test_a_named_pipe_dot_env_does_not_hold_up_the_session(tmp_path):
    make_wordpress(tmp_path)
    os.mkfifo(tmp_path / ".env")
    assert "## This project" in injected_context(tmp_path)


def test_stdin_left_open_does_not_hold_up_the_session(tmp_path):
    make_wordpress(tmp_path)
    read_end, write_end = os.pipe()
    try:
        os.write(write_end, json.dumps({"cwd": str(tmp_path)}).encode())
        started = time.monotonic()
        completed = subprocess.run(["bash", str(HOOK)], stdin=read_end, capture_output=True, encoding="utf-8",
                                   env=hook_environment(), cwd=tmp_path, timeout=10)
        elapsed_seconds = time.monotonic() - started
    finally:
        os.close(read_end)
        os.close(write_end)
    assert completed.returncode == 0 and completed.stderr == "", completed.stderr
    assert elapsed_seconds < 4
    assert "## This project" in json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]


def test_a_closed_stdin_writes_nothing_to_stderr(tmp_path):
    make_wordpress(tmp_path)
    completed = subprocess.run(["bash", "-c", 'exec bash "$0" <&-', str(HOOK)], capture_output=True,
                               encoding="utf-8", env=hook_environment(), cwd=tmp_path, timeout=5)
    assert completed.returncode == 0 and completed.stderr == "", completed.stderr
    assert "## This project" in json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]


def test_a_json_py_planted_in_the_project_is_never_run_by_a_session_start(tmp_path):
    make_wordpress(tmp_path)
    marker_file = tmp_path.parent / f"{tmp_path.name}-planted-json-ran"
    (tmp_path / "json.py").write_text(f"import pathlib\npathlib.Path({str(marker_file)!r}).touch()\n")
    run_hook_process(stdin_text=json.dumps({"cwd": str(tmp_path)}), working_directory=tmp_path)
    assert not marker_file.exists()


def test_a_plugin_without_recon_py_still_delivers_the_intro(tmp_path):
    make_wordpress(tmp_path / "site")
    hook_without_recon = copy_plugin(tmp_path / "plugin", with_recon=False, with_skill=True)
    context = run_hook(tmp_path / "site", hook=hook_without_recon)["hookSpecificOutput"]["additionalContext"]
    assert "name: using-16h" in context and "## This project" not in context


def test_a_plugin_without_its_skill_file_still_emits_valid_json(tmp_path):
    make_wordpress(tmp_path / "site")
    hook_without_skill = copy_plugin(tmp_path / "plugin", with_recon=True, with_skill=False)
    context = run_hook(tmp_path / "site", hook=hook_without_skill)["hookSpecificOutput"]["additionalContext"]
    assert "Error reading using-16h skill" in context
    assert "## This project" in context


def test_run_hook_cmd_launches_the_hook(tmp_path):
    make_wordpress(tmp_path)
    completed = subprocess.run(
        ["bash", str(HOOK.parent / "run-hook.cmd"), "session-start"],
        input=json.dumps({"cwd": str(tmp_path), "source": "startup"}), capture_output=True, encoding="utf-8",
        env=hook_environment(), cwd="/", timeout=5,
    )
    assert completed.returncode == 0 and completed.stderr == ""
    assert json.loads(completed.stdout) == run_hook(tmp_path)


def test_the_hook_writes_nothing_and_is_fast(tmp_path):
    make_wordpress(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    started = time.monotonic(); run_hook(tmp_path)
    assert time.monotonic() - started < 1.0
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_the_superpowers_licence_travels_with_the_code_copied_from_it():
    licence_text = (HOOK.parent / "LICENSE.superpowers").read_text()
    assert licence_text.startswith("MIT License") and "Copyright (c) 2025 Jesse Vincent" in licence_text
    for copied_file in ("run-hook.cmd", "session-start"):
        assert "MIT licence: hooks/LICENSE.superpowers" in (HOOK.parent / copied_file).read_text(), copied_file


def test_hooks_json_matches_on_resume_and_compact():
    hooks = json.loads((HOOK.parent / "hooks.json").read_text())
    assert hooks["hooks"]["SessionStart"][0]["matcher"] == "startup|resume|clear|compact"
    command_hook = hooks["hooks"]["SessionStart"][0]["hooks"][0]
    assert command_hook == {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
                            "shell": "bash", "async": False}
