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
    assert (SKILLS / "releasing-to-production" / "references" / "release-note.md").exists()
    verifying = (SKILLS / "verifying-a-deploy" / "SKILL.md").read_text()
    assert "blocked_at_waf" in verifying and "Mozilla/5.0 (Macintosh" in verifying


def test_debugging_names_the_gate_and_the_investigation_note():
    body = (SKILLS / "debugging-a-live-site" / "SKILL.md").read_text()
    assert "no code change until the error is named" in body.lower()
    assert "docs/16h/investigations/" in body
    triage = (SKILLS / "debugging-a-live-site" / "references" / "triage.md").read_text()
    assert "not available yet" not in triage


def test_the_old_skills_are_gone():
    assert not (SKILLS / "16h-dev-agent").exists() and not (SKILLS / "devsite-import").exists()
