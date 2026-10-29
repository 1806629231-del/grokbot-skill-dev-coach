#!/usr/bin/env python3
"""Validate and package a Skill without caches, local secrets or build output.

Usage: python scripts/package_skill.py <skill-directory> [output-directory]
       [--exclude 'assets/private/*']
Requires PyYAML. Existing archives are never overwritten; inspect members before sharing.
"""

import argparse
import fnmatch
import os
import zipfile
from pathlib import Path

from quick_validate import validate_skill


EXCLUDED_DIRS = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "node_modules", ".idea", ".vscode", "dist", "build"}
EXCLUDED_PATTERNS = ("*.pyc", "*.pyo", "*.log", "*.tmp", "*.temp", "*.bak", "*.swp", "*~", "*.skill", ".DS_Store", "Thumbs.db", ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "credentials*.json", "secrets*.json", "token*.json", ".npmrc", ".pypirc")


def excluded(relative, extra_patterns=()):
    """Match both basenames and portable, Skill-relative paths."""
    path = relative.as_posix().lower()
    name = relative.name.lower()
    return any(fnmatch.fnmatchcase(path, pattern.lower()) or fnmatch.fnmatchcase(name, pattern.lower()) for pattern in (*EXCLUDED_PATTERNS, *extra_patterns))


def package_files(root, extra_patterns=()):
    """Walk without following symlinks/junctions or entering excluded directories."""
    def linked(path):
        return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())

    def walk_error(error):
        raise error

    for current, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        current = Path(current)
        dirs[:] = sorted(name for name in dirs if name.lower() not in EXCLUDED_DIRS and not linked(current / name) and not excluded((current / name).relative_to(root), extra_patterns))
        for name in sorted(files):
            path = current / name
            relative = path.relative_to(root)
            if linked(path) or excluded(relative, extra_patterns):
                continue
            if path.is_file() and path.resolve().is_relative_to(root):
                yield path


def package_skill(skill_path, output_dir=None, exclude=()):
    root = Path(skill_path).resolve()
    if not root.is_dir():
        print(f"Error: Skill directory not found: {root}")
        return None
    valid, message = validate_skill(root)
    print(message)
    if not valid:
        return None
    destination = Path(output_dir).resolve() if output_dir else Path.cwd().resolve()
    if destination.is_relative_to(root):
        print("Error: Output directory must be outside the Skill directory")
        return None

    archive = destination / f"{root.name}.skill"
    created = False
    try:
        files = list(package_files(root, exclude))
        if root / "SKILL.md" not in files:
            print("Error: Exclusion rules removed SKILL.md")
            return None
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as package:
            created = True
            for path in files:
                package.write(path, path.relative_to(root.parent).as_posix())
        with zipfile.ZipFile(archive) as package:
            bad_member = package.testzip()
            if bad_member:
                raise ValueError(f"Archive verification failed: {bad_member}")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        if created:
            archive.unlink(missing_ok=True)
        print(f"Error: Could not package Skill: {exc}")
        return None
    print(f"Packaged {len(files)} files: {archive}")
    print("Default exclusions are filename-based, not a content secret scan. Review archive members before sharing.")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_path")
    parser.add_argument("output_dir", nargs="?")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob matched against basenames and Skill-relative paths; repeatable")
    args = parser.parse_args()
    return 0 if package_skill(args.skill_path, args.output_dir, args.exclude) else 1


if __name__ == "__main__":
    raise SystemExit(main())
