from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "skills"
EXPECTED = {"using-16h", "debugging-a-live-site", "reading-traffic", "pushing-to-staging", "releasing-to-production", "verifying-a-deploy"}


def frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    assert text.startswith("---\n"), f"{skill_dir.name}/SKILL.md does not open with a --- block"
    block, closing_fence, _body = text[len("---\n"):].partition("\n---\n")
    assert closing_fence, f"{skill_dir.name}/SKILL.md never closes its --- block"
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


def test_no_skill_lists_the_tools_as_a_menu():
    for skill in EXPECTED:
        body = (SKILLS / skill / "SKILL.md").read_text()
        assert "| `logs_read` |" not in body and "## Tools" not in body
