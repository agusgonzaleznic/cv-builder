"""`cv-builder init`: create a CV repository. It writes files only; making it a git repository
and a private GitHub repository is left to the person (the commands are printed at the end)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import __version__

TEMPLATES = Path(__file__).parent / "templates"
ACTION_REPO = "agusgonzaleznic/cv-builder"

DEPENDABOT = """\
# Proposes updates for the pinned actions, cv-builder's included, once a week.
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
"""


def action_ref() -> str:
    """The `uses:` value for cv-builder's action: this version's release tag resolved to a full
    commit SHA, with the release in a comment. A tag can be moved; a commit cannot. Falls back to
    the tag when offline, and to main for a development version, which has no release."""
    if "dev" in __version__:
        return f"{ACTION_REPO}@main # a development build; pin a release SHA before relying on it"
    tag = f"v{__version__}"
    try:
        out = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{ACTION_REPO}", f"refs/tags/{tag}",
             f"refs/tags/{tag}^{{}}"], capture_output=True, text=True, timeout=20, check=True,
        ).stdout.split("\n")
    except (OSError, subprocess.SubprocessError):
        return f"{ACTION_REPO}@{tag}"
    shas = {ref: sha for sha, _, ref in (line.partition("\t") for line in out if line)}
    sha = shas.get(f"refs/tags/{tag}^{{}}") or shas.get(f"refs/tags/{tag}")
    return f"{ACTION_REPO}@{sha} # {tag}" if sha else f"{ACTION_REPO}@{tag}"


def init(target: Path, sample: bool = False, force: bool = False) -> int:
    target.mkdir(parents=True, exist_ok=True)
    existing = [p.name for p in target.iterdir() if p.name != ".git"]
    if existing and not force:
        print(f"{target} already holds files ({', '.join(sorted(existing)[:5])}): "
              "use an empty folder, or --force to write over matching files")
        return 1

    repo = TEMPLATES / "repo"
    for name in ("AGENTS.md", "cv.yaml", "facts.yaml", "cv-builder.toml"):
        shutil.copy2(repo / name, target / name)
    (target / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    shutil.copy2(repo / "gitignore", target / ".gitignore")
    (target / "variants").mkdir(exist_ok=True)
    shutil.copy2(repo / "variants" / "general.yaml", target / "variants" / "general.yaml")

    workflows = target / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    ref = action_ref()
    for src in sorted((repo / "github" / "workflows").glob("*.yml")):
        text = src.read_text(encoding="utf-8").replace("{{ACTION_REF}}", ref)
        (workflows / src.name).write_text(text, encoding="utf-8")
    (target / ".github" / "dependabot.yml").write_text(DEPENDABOT, encoding="utf-8")

    if sample:
        for name in ("cv.yaml", "facts.yaml", "cv-builder.toml"):
            shutil.copy2(TEMPLATES / "sample" / name, target / name)
        (target / "variants" / "general.yaml").unlink()
        for overlay in sorted((TEMPLATES / "sample" / "variants").glob("*.yaml")):
            shutil.copy2(overlay, target / "variants" / overlay.name)

    print(f"Created a CV repository in {target}{' with the made-up sample' if sample else ''}.")
    print("Next:")
    print("  1. Keep it private. In that folder:")
    print("       git init -b main && git add -A && git commit -m 'Start my CV'")
    print("       gh repo create <name> --private --source . --push")
    print("  2. Fill in facts.yaml first, then cv.yaml (or let the cv-ingest skill do it with you).")
    print("  3. cv-builder check, then cv-builder build.")
    return 0
