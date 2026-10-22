import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "16h-dev-agent"
PLUGIN_VERSION = "2.0.0"


def read_json(relative_path):
    return json.loads((PLUGIN_ROOT / relative_path).read_text())


def marketplace_entry():
    return read_json(".claude-plugin/marketplace.json")["plugins"][0]


def test_the_three_manifests_agree_on_name_and_version():
    claude_manifest = read_json(".claude-plugin/plugin.json")
    codex_manifest = read_json(".codex-plugin/plugin.json")
    entry = marketplace_entry()
    assert claude_manifest["version"] == codex_manifest["version"] == entry["version"] == PLUGIN_VERSION
    assert claude_manifest["name"] == codex_manifest["name"] == entry["name"] == PLUGIN_NAME


def test_the_marketplace_entry_carries_what_codex_requires():
    entry = marketplace_entry()
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert entry["category"] == "Productivity"


def test_codex_finds_the_skills_folder():
    assert read_json(".codex-plugin/plugin.json")["skills"] == "./skills/"


def test_mcp_json_is_unchanged():
    assert read_json(".mcp.json") == {"mcpServers": {"16h": {"type": "http", "url": "https://mcp.16h.io/mcp"}}}
