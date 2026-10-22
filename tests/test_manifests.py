import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "16h-dev-agent"
PLUGIN_VERSION = "2.1.1"


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


def test_the_codex_manifest_declares_its_mcp_server():
    codex_manifest = read_json(".codex-plugin/plugin.json")
    assert codex_manifest["mcpServers"] == "./.mcp.json"
    assert (PLUGIN_ROOT / codex_manifest["mcpServers"]).is_file()


def test_the_codex_manifest_declares_hooks_and_its_interface():
    codex_manifest = read_json(".codex-plugin/plugin.json")
    # superpowers 7.0.0 RELEASE-NOTES (v6.1.1): Codex reads `hooks: {}` as "no hooks", so the path is spelled out.
    assert codex_manifest["hooks"] == "./hooks/hooks.json"
    assert (PLUGIN_ROOT / codex_manifest["hooks"]).is_file()
    interface = codex_manifest["interface"]
    assert interface["displayName"] == "16h dev agent"
    assert interface["developerName"] == "16hands"
    assert interface["category"] == "Developer Tools"
    assert interface["capabilities"] == ["Interactive", "Read", "Write"]
    assert interface["websiteURL"] == "https://16h.io"


def test_the_codex_manifest_carries_the_claude_manifests_identity():
    claude_manifest = read_json(".claude-plugin/plugin.json")
    codex_manifest = read_json(".codex-plugin/plugin.json")
    for shared_key in ("description", "author", "homepage", "repository", "license", "keywords"):
        assert codex_manifest[shared_key] == claude_manifest[shared_key], shared_key


def test_the_native_marketplace_entry_names_the_plugin_at_the_repo_root():
    native_marketplace = read_json(".agents/plugins/marketplace.json")
    assert native_marketplace["name"] == "16hands"
    assert native_marketplace["interface"] == {"displayName": "16Hands"}
    [native_entry] = native_marketplace["plugins"]
    assert native_entry == {
        "name": PLUGIN_NAME,
        "source": {"source": "url", "url": "./"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools",
    }


def test_the_plugin_is_mit_licensed_in_the_file_and_both_manifests():
    licence_text = (PLUGIN_ROOT / "LICENSE").read_text()
    assert licence_text.startswith("MIT License\n\nCopyright (c) 2026 16hands\n")
    assert read_json(".claude-plugin/plugin.json")["license"] == "MIT"
    assert read_json(".codex-plugin/plugin.json")["license"] == "MIT"
