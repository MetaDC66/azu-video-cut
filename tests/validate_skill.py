#!/usr/bin/env python3
"""Validate the public Skill package without reading any user secrets."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
frontmatter = re.match(r"\A---\n(.*?)\n---\n", skill_text, re.S)
if not frontmatter:
    fail("SKILL.md frontmatter is missing")

metadata = {}
for line in frontmatter.group(1).splitlines():
    key, separator, value = line.partition(":")
    if not separator:
        fail("invalid SKILL.md frontmatter line")
    metadata[key.strip()] = value.strip().strip('"')
if set(metadata) != {"name", "description"}:
    fail("SKILL.md frontmatter must contain only name and description")
if metadata["name"] != "azu-video-cut":
    fail("skill name must be azu-video-cut")
if not isinstance(metadata["description"], str) or len(metadata["description"]) < 40:
    fail("description must explain capability and trigger contexts")

openai_yaml = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
if "default_prompt:" not in openai_yaml or "$azu-video-cut" not in openai_yaml:
    fail("agents/openai.yaml default_prompt must mention $azu-video-cut")

required = [
    "references/workflow.md",
    "references/setup.md",
    "references/checklist.md",
    "references/cover-style-guide.md",
    "scripts/init_video.sh",
    "scripts/mix_finalize.py",
    "scripts/review_gen/generate.py",
    "templates/project-profile.json",
    ".env.example",
]
for relative in required:
    if not (ROOT / relative).is_file():
        fail(f"required file missing: {relative}")

for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    if path.resolve() == pathlib.Path(__file__).resolve():
        continue
    if path.suffix.lower() not in {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".example"}:
        continue
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)
    if "/Users/" in text or "/home/" in text:
        fail(f"private absolute path found in {relative}")
    if "Key 发给我" in text or "显示前 4 位" in text:
        fail(f"unsafe secret-handling instruction found in {relative}")

print("skill validation passed")
