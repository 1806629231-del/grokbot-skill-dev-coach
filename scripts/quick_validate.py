#!/usr/bin/env python3
"""Static Skill checks. Requires PyYAML; semantic quality still needs review.

Usage: python scripts/quick_validate.py <skill-directory>
Errors fail validation; warnings identify manual review items and legacy layouts.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_LINES = 499  # The complete SKILL.md must contain fewer than 500 lines.
ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata"}
SCAFFOLD_FILES = ("scripts/example.py", "references/api_reference.md", "assets/example_asset.txt")


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self):
        return not self.errors

    def message(self):
        lines = [f"ERROR: {item}" for item in self.errors]
        lines += [f"WARNING: {item}" for item in self.warnings]
        if self.valid:
            lines.append("Static validation passed; behavioral and semantic review still required.")
        return "\n".join(lines)


def validate_name(name):
    """Shared naming contract used before creating files and during validation."""
    if not isinstance(name, str) or not name.strip():
        return "Name must be a non-empty string"
    if len(name) > MAX_NAME_LENGTH:
        return f"Name exceeds {MAX_NAME_LENGTH} characters"
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return "Name must use lowercase letters/digits and single internal hyphens"
    if name.lower() in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}:
        return "Name is a reserved Windows device name"
    return None


def prose_only(text):
    """Ignore fenced examples when checking instructions and actual file links."""
    result = []
    fence_char, fence_length = None, 0
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(\x60{3,}|~{3,})(.*)$", line)
        if marker:
            run, tail = marker.groups()
            if fence_char is None:
                fence_char, fence_length = run[0], len(run)
                continue
            if run[0] == fence_char and len(run) >= fence_length and not tail.strip():
                fence_char = None
                continue
        if fence_char is None:
            result.append(line)
    return "\n".join(result)


def local_links(text):
    """Yield local Markdown targets, including angle-wrapped paths with spaces."""
    prose = prose_only(text)
    inline = r"\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)"
    definitions = r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)"
    for pattern in (inline, definitions):
        for match in re.finditer(pattern, prose, re.MULTILINE):
            target = match.group(1).strip("<>")
            parts = urlsplit(target)
            if not parts.scheme and not parts.netloc and parts.path:
                yield unquote(parts.path)


def inspect_skill(skill_path):
    report = ValidationReport()
    root = Path(skill_path).resolve()
    skill_md = root / "SKILL.md"
    try:
        content = skill_md.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        report.errors.append(f"Cannot read SKILL.md: {exc}")
        return report
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if not match:
        report.errors.append("Missing or invalid YAML frontmatter")
        return report
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        report.errors.append(f"Invalid YAML: {exc}")
        return report
    if not isinstance(metadata, dict):
        report.errors.append("Frontmatter must be a YAML dictionary")
        return report
    unexpected = set(metadata) - ALLOWED_PROPERTIES
    if unexpected:
        report.errors.append("Unsupported frontmatter keys: " + ", ".join(sorted(map(str, unexpected))) + ". Grok Bot skills only need name and description.")
    name = metadata.get("name")
    name_error = validate_name(name)
    if name_error:
        report.errors.append(name_error)
    elif root.name != name:
        report.warnings.append(f"Directory '{root.name}' differs from name '{name}'; preserve established legacy paths, use matching names for new Skills.")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        report.errors.append("Description must be a non-empty string")
    else:
        if len(description) > MAX_DESCRIPTION_LENGTH:
            report.errors.append(f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters")
        if "<" in description or ">" in description:
            report.errors.append("Description cannot contain angle brackets")
        if re.search(r"\bTODO\b", description, re.IGNORECASE):
            report.errors.append("Description contains an unfinished TODO placeholder")
    body = content[match.end():]
    if not body.strip():
        report.errors.append("Instruction body is empty")
    if len(content.splitlines()) > MAX_SKILL_LINES:
        report.errors.append(f"SKILL.md must contain fewer than 500 lines (found {len(content.splitlines())})")
    if re.search(r"\[TODO(?:\s|:|：|\])", prose_only(body), re.IGNORECASE):
        report.errors.append("Instruction body contains an unfinished scaffold placeholder")
    if not re.search(r"(?im)^#{1,6}\s+.*(?:工作流|流程|步骤|workflow|steps?|instructions?|procedure|tasks?|capabilities)", body):
        report.warnings.append("No recognizable workflow heading; manually check that actionable instructions are present.")

    for relative in SCAFFOLD_FILES:
        candidate = root / relative
        if candidate.is_file():
            try:
                sample = candidate.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                continue
            if re.search(r"placeholder|\[TODO", sample, re.IGNORECASE):
                report.errors.append(f"Unfinished scaffold resource: {relative}")

    pending = [(skill_md, body, 0)]
    visited = {skill_md.resolve()}
    root_markdown_targets = set()
    while pending:
        source, text, depth = pending.pop(0)
        try:
            targets = list(local_links(text))
        except ValueError as exc:
            report.errors.append(f"Malformed link in {source.name}: {exc}")
            continue
        for target in targets:
            resolved = (source.parent / target).resolve()
            if not resolved.is_relative_to(root):
                report.warnings.append(f"External local dependency in {source.name}: {target}; not included in this Skill package.")
                continue
            if not resolved.exists():
                report.errors.append(f"Broken local reference in {source.name}: {target}")
                continue
            if resolved.suffix.lower() != ".md" or not resolved.is_file():
                continue
            if depth == 0:
                root_markdown_targets.add(resolved)
            elif resolved != skill_md and resolved not in root_markdown_targets:
                report.warnings.append(f"Nested reference: {source.name} -> {target}; link required instructions directly from SKILL.md.")
            if resolved in visited:
                continue
            visited.add(resolved)
            try:
                reference_text = resolved.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                report.errors.append(f"Cannot read reference {target}: {exc}")
                continue
            pending.append((resolved, reference_text, depth + 1))
    return report


def validate_skill(skill_path):
    """Preserve the existing (valid, message) API for callers and packagers."""
    report = inspect_skill(skill_path)
    return report.valid, report.message()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/quick_validate.py <skill-directory>")
        raise SystemExit(1)
    valid, message = validate_skill(sys.argv[1])
    print(message)
    raise SystemExit(0 if valid else 1)
