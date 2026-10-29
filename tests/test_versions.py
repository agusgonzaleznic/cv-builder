"""A release states its version in three places: the package, the plugin manifest and the
cv-ingest skill's pinned install line. They must agree, or the plugin installs another release."""

from __future__ import annotations

import json
from pathlib import Path

from cvcite import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_matches_the_package():
    manifest = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())
    assert manifest["version"] == __version__


def test_skill_installs_this_release():
    skill = (ROOT / "plugin/skills/cv-ingest/SKILL.md").read_text()
    assert f"uv tool install cvcite=={__version__}" in skill
    assert f"pipx install cvcite=={__version__}" in skill
