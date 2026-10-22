from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "skills"
EXPECTED = {"using-16h", "debugging-a-live-site", "reading-traffic", "pushing-to-staging", "releasing-to-production", "verifying-a-deploy"}


def frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    assert text.startswith("---\n"), f"{skill_dir.name}/SKILL.md does not open with a --- block"
    after_opening_fence = text[len("---\n"):]
    assert "\n---\n" in after_opening_fence, f"{skill_dir.name}/SKILL.md never closes its --- block"
    block = after_opening_fence.split("\n---\n", 1)[0]
    fields = {}
    for line in block.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def test_the_skills_are_the_six_by_moment():
    assert {skill_folder.name for skill_folder in SKILLS.iterdir() if skill_folder.is_dir()} == EXPECTED


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_each_skill_has_a_name_matching_its_folder_and_a_use_when_description(skill):
    meta = frontmatter(SKILLS / skill)
    assert meta["name"] == skill
    assert meta["description"].startswith("Use when")
    assert len(meta["description"]) <= 1024


def test_using_16h_fits_the_budget_and_carries_the_out_of_bounds_rule():
    text = (SKILLS / "using-16h" / "SKILL.md").read_text()
    assert len(text) < 3600
    assert "the platform's hosts are out of bounds for me" in text
    assert "when the repo has a git remote, the platform remembers it" in text
    for skill in EXPECTED - {"using-16h"}:
        assert skill in text


def test_using_16h_never_contains_the_hooks_project_block_marker():
    assert "## This project" not in (SKILLS / "using-16h" / "SKILL.md").read_text()


def test_no_skill_lists_the_tools_as_a_menu():
    for skill in EXPECTED:
        body = (SKILLS / skill / "SKILL.md").read_text()
        assert "| `logs_read` |" not in body and "## Tools" not in body


def test_pushing_to_staging_opens_with_the_target_and_keeps_the_recipes():
    body = (SKILLS / "pushing-to-staging" / "SKILL.md").read_text()
    assert "before_production" in body.split("## Doctrine")[0]
    assert (SKILLS / "pushing-to-staging" / "references" / "wordpress.md").exists()
    assert "curl -sS -L -A" not in body


def test_releasing_writes_the_release_note_and_verifying_owns_the_http_rule():
    releasing = (SKILLS / "releasing-to-production" / "SKILL.md").read_text()
    assert "docs/16h/releases/" in releasing and "what_will_change" in releasing
    assert releasing.index("A Laravel push runs no migrations") < releasing.index("`site_plan(client?")
    assert (SKILLS / "releasing-to-production" / "references" / "release-note.md").exists()
    verifying = (SKILLS / "verifying-a-deploy" / "SKILL.md").read_text()
    assert "blocked_at_waf" in verifying and "Mozilla/5.0 (Macintosh" in verifying


def test_debugging_names_the_gate_and_the_investigation_note():
    body = (SKILLS / "debugging-a-live-site" / "SKILL.md").read_text()
    assert "no code change until the error is named" in body.lower()
    assert "docs/16h/investigations/" in body
    assert '`site=<site_key>`, `kind: "errors"`' in body
    triage = (SKILLS / "debugging-a-live-site" / "references" / "triage.md").read_text()
    assert "not available yet" not in triage
    assert 'site: "<site_key>", kind: "errors"' in triage


def test_the_old_skills_are_gone():
    assert not (SKILLS / "16h-dev-agent").exists() and not (SKILLS / "devsite-import").exists()


PUSHING_REFERENCES = SKILLS / "pushing-to-staging" / "references"
PARTS = ("code.zip", "database.sql.gz", "uploads.zip", "env.16h")
REFERENCES = ("wordpress.md", "laravel.md", "statamic.md", "symfony.md", "phpapp.md", "files.md")


def deployignore_patterns(reference_path):
    """The lines of the fenced block under a reference's `.deployignore` heading."""
    section = reference_path.read_text().split("## `.deployignore`", 1)[1]
    fenced_block = section.split("```", 2)[1]
    return [line.strip() for line in fenced_block.splitlines() if line.strip()]


def test_the_references_cover_the_wave_a_apps_and_nothing_else():
    assert sorted(path.name for path in PUSHING_REFERENCES.glob("*.md")) == sorted(REFERENCES)


@pytest.mark.parametrize("reference", REFERENCES)
def test_each_deployignore_keeps_out_records_dumps_and_archives_and_whole_folders(reference):
    patterns = deployignore_patterns(PUSHING_REFERENCES / reference)
    for required_pattern in ("docs/16h/*", "*.sql", "*.sql.gz", "*.zip"):
        assert required_pattern in patterns, required_pattern
    # zip matches a pattern against file paths: `dir/` drops only the folder's own entry, never its files.
    assert [pattern for pattern in patterns if pattern.endswith("/")] == []


def test_pushing_to_staging_step_5_lists_every_pattern_its_references_list():
    body = (SKILLS / "pushing-to-staging" / "SKILL.md").read_text()
    step_5 = body.split("## Step 5", 1)[1].split("## Step 6", 1)[0]
    for reference in REFERENCES:
        for pattern in deployignore_patterns(PUSHING_REFERENCES / reference):
            assert f"`{pattern}`" in step_5, (reference, pattern)


def test_no_build_command_writes_a_part_into_the_site_root():
    for skill_file in SKILLS.rglob("*.md"):
        text = skill_file.read_text()
        for part in PARTS:
            assert f"zip -r -q {part}" not in text and f"> {part}" not in text, (skill_file.name, part)


def test_laravel_ships_vendor_and_the_storage_skeleton():
    # The lane runs no composer install, and seeds the shared storage from the first release.
    patterns = deployignore_patterns(PUSHING_REFERENCES / "laravel.md")
    assert [pattern for pattern in patterns if pattern.startswith(("vendor", "storage/*", "storage/framework"))] == []


@pytest.mark.parametrize("reference", ("laravel.md", "statamic.md", "symfony.md"))
def test_each_framework_reference_keeps_every_env_file_out_of_the_zip(reference):
    patterns = deployignore_patterns(PUSHING_REFERENCES / reference)
    assert {".env", ".env.16h", ".env.*"} <= set(patterns)
    assert "## .env.16h" in (PUSHING_REFERENCES / reference).read_text()


def test_laravel_no_longer_claims_the_platform_writes_env_from_secrets():
    text = (PUSHING_REFERENCES / "laravel.md").read_text()
    assert "from the database row and the client's secrets" not in text
    assert "bootstrap/cache/*.php" in deployignore_patterns(PUSHING_REFERENCES / "laravel.md")
    assert "Migrations are not run by the import" not in text


def test_symfony_ships_its_committed_env_inside_the_env_part():
    assert 'cat .env .env.16h > "$parts_folder/env.16h"' in (PUSHING_REFERENCES / "symfony.md").read_text()


def test_files_zips_the_chosen_folders_contents_and_asks_no_php():
    text = (PUSHING_REFERENCES / "files.md").read_text()
    assert "dist" in text and "build" in text and "index.html" in text and "php" not in text.lower().split("## building")[0]


def test_pushing_to_staging_names_every_app_the_hook_can_emit_and_the_env_part():
    body = (SKILLS / "pushing-to-staging" / "SKILL.md").read_text()
    for app in ("wordpress", "laravel", "statamic", "symfony", "phpapp", "files", "drupal", "joomla"):
        assert app in body
    assert "env.16h" in body and "include_content" in body and "docroot" in body and "When two layouts fit" in body


def test_releasing_says_production_is_wordpress_only():
    assert "WordPress-only in this wave" in (SKILLS / "releasing-to-production" / "SKILL.md").read_text()
