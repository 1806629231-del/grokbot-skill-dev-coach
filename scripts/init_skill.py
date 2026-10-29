#!/usr/bin/env python3
"""Create a minimal Skill; resource directories are opt-in.

Usage: python scripts/init_skill.py <name> --path <parent> --resources scripts,references
Requires PyYAML through quick_validate. Existing directories are never overwritten.
"""

import argparse
from pathlib import Path

from quick_validate import validate_name


RESOURCE_TYPES = {"scripts", "references", "assets"}
SKILL_TEMPLATE = """---
name: {skill_name}
description: "[TODO: 描述这个 Skill 做什么，以及什么时候触发。]"
---

# {skill_title}

## 工作流

[TODO: 写明输入、关键步骤、输出和完成条件；完成后删除占位内容。]
"""


def init_skill(skill_name, path, resources=()):
    """Return the new directory, or None on failure; never overwrite a Skill."""
    error = validate_name(skill_name)
    if error:
        print(f"Error: {error}")
        return None
    if isinstance(resources, str):
        resources = [part.strip() for part in resources.split(",") if part.strip()]
    resources = tuple(dict.fromkeys(resources))
    invalid = set(resources) - RESOURCE_TYPES
    if invalid:
        print(f"Error: Unknown resources: {', '.join(sorted(invalid))}")
        return None

    skill_dir = Path(path).resolve() / skill_name
    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"Error: Cannot create {skill_dir}: {exc}")
        return None
    try:
        (skill_dir / "SKILL.md").write_text(
            SKILL_TEMPLATE.format(
                skill_name=skill_name,
                skill_title=" ".join(word.capitalize() for word in skill_name.split("-")),
            ),
            encoding="utf-8",
        )
        for resource in resources:
            (skill_dir / resource).mkdir()
    except OSError as exc:
        print(f"Error: Initialization incomplete at {skill_dir}: {exc}")
        return None

    print(f"Created draft: {skill_dir}")
    print("Complete the TODO fields before validation. No example files were created.")
    return skill_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_name", help="1-64 lowercase letters/digits with single internal hyphens")
    parser.add_argument("--path", required=True, help="Parent directory for the new Skill")
    parser.add_argument("--resources", default="", help="Comma-separated scripts,references,assets (optional)")
    args = parser.parse_args()
    return 0 if init_skill(args.skill_name, args.path, args.resources) else 1


if __name__ == "__main__":
    raise SystemExit(main())
