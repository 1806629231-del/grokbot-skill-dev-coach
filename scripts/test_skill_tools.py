#!/usr/bin/env python3
"""Regression tests for the engineering helpers, isolated from installed Skills."""

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

from init_skill import init_skill
from package_skill import package_skill
from quick_validate import inspect_skill, validate_name, validate_skill


SCRIPTS = Path(__file__).resolve().parent


class SkillToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xinghe-skill-tools-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.skill = self.root / "sample-skill"
        self.skill.mkdir()
        self.write_skill()

    def write_skill(self, metadata=None, body="## 工作流\n\n读取输入，生成结果并验证。\n", encoding="utf-8"):
        if metadata is None:
            metadata = {"name": "sample-skill", "description": "处理示例输入并生成报告。当用户请求示例处理时使用。"}
        content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body
        (self.skill / "SKILL.md").write_text(content, encoding=encoding)

    def quiet(self, function, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args, **kwargs)

    def resource(self, relative, text="fixture"):
        path = self.skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_skill_and_compatibility_api(self):
        self.assertTrue(inspect_skill(self.skill).valid)
        valid, message = validate_skill(self.skill)
        self.assertTrue(valid)
        self.assertIn("behavioral", message)

    def test_name_boundaries_and_invalid_names(self):
        for name in ("a", "a" * 64, "skill-2"):
            with self.subTest(name=name):
                self.assertIsNone(validate_name(name))
        for name in (None, 42, "", " ", "a" * 65, "Bad", "a_b", "a--b", "-a", "a-", "../escape", "con", "lpt1"):
            with self.subTest(name=name):
                self.assertIsNotNone(validate_name(name))

    def test_empty_or_wrong_field_types_fail(self):
        for field in ("name", "description"):
            for value in (None, "", " ", 42, []):
                with self.subTest(field=field, value=value):
                    metadata = {"name": "sample-skill", "description": "Process files when requested."}
                    metadata[field] = value
                    self.write_skill(metadata)
                    self.assertFalse(inspect_skill(self.skill).valid)

    def test_description_boundaries(self):
        for value, expected in (("x" * 1024, True), ("x" * 1025, False), ("use <value>", False), ("[TODO: fill]", False)):
            with self.subTest(length=len(value), expected=expected):
                self.write_skill({"name": "sample-skill", "description": value})
                self.assertEqual(inspect_skill(self.skill).valid, expected)

    def test_display_name_belongs_in_agent_metadata(self):
        self.write_skill({"name": "sample-skill", "description": "Process sample input when asked.", "display_name": "示例"})
        self.assertFalse(inspect_skill(self.skill).valid)
        self.write_skill()
        self.resource("agents/openai.yaml", 'interface:\n  display_name: "示例"\n')
        self.assertTrue(inspect_skill(self.skill).valid)

    def test_missing_and_malformed_skill_fail(self):
        self.assertFalse(inspect_skill(self.root / "missing").valid)
        for text in ("no frontmatter", "---\n[not, mapping]\n---\ntext", "---\nname: [\n---\ntext"):
            with self.subTest(text=text):
                (self.skill / "SKILL.md").write_text(text, encoding="utf-8")
                self.assertFalse(inspect_skill(self.skill).valid)

    def test_bom_crlf_supported(self):
        self.write_skill(encoding="utf-8-sig")
        self.assertTrue(inspect_skill(self.skill).valid)
        path = self.skill / "SKILL.md"
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertTrue(inspect_skill(self.skill).valid)

    def test_line_limit(self):
        self.write_skill()
        path = self.skill / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        text += "detail\n" * (499 - len(text.splitlines()))
        path.write_text(text, encoding="utf-8")
        self.assertTrue(inspect_skill(self.skill).valid)
        path.write_text(text + "one more\n", encoding="utf-8")
        self.assertFalse(inspect_skill(self.skill).valid)

    def test_body_and_scaffold_checks(self):
        for body in ("", "## 工作流\n[TODO: complete]"):
            self.write_skill(body=body)
            self.assertFalse(inspect_skill(self.skill).valid)
        self.write_skill()
        self.resource("scripts/example.py", "# This is a placeholder script")
        self.assertFalse(inspect_skill(self.skill).valid)

    def test_links_include_resources_but_ignore_examples_and_urls(self):
        self.resource("references/详细 说明.md", "# Instructions\n")
        self.resource("assets/logo.svg", "<svg/>")
        self.resource("scripts/run.py", "pass\n")
        self.write_skill(body='## 工作流\n[文档](<references/详细 说明.md>)\n![图](assets/logo.svg)\n[脚本][run]\n[run]: scripts/run.py\n[网络](https://example.com/a)\n[本页](#anchor)\n```markdown\n[示例](missing.md)\n[TODO: 示例]\n```\n')
        self.assertTrue(inspect_skill(self.skill).valid)
        self.write_skill(body="## 工作流\n[缺失](references/missing.md)\n")
        self.assertFalse(inspect_skill(self.skill).valid)

    def test_nested_links_and_legacy_names_warn(self):
        self.resource("references/first.md", "[Second](second.md)\n")
        self.resource("references/second.md", "# More\n")
        self.write_skill(body="## 工作流\n[First](references/first.md)\n")
        report = inspect_skill(self.skill)
        self.assertTrue(report.valid)
        self.assertTrue(any("Nested reference" in item for item in report.warnings))
        self.write_skill({"name": "legacy-name", "description": "Process sample input when requested."})
        report = inspect_skill(self.skill)
        self.assertTrue(report.valid)
        self.assertTrue(any("differs" in item for item in report.warnings))

    def test_minimal_initializer_and_unfinished_draft(self):
        created = self.quiet(init_skill, "new-skill", self.root)
        self.assertEqual({p.name for p in created.iterdir()}, {"SKILL.md"})
        self.assertFalse(inspect_skill(created).valid)

    def test_optional_resources_without_example_files(self):
        created = self.quiet(init_skill, "resources-skill", self.root, "scripts,assets,scripts")
        self.assertEqual({p.name for p in created.iterdir()}, {"SKILL.md", "scripts", "assets"})
        self.assertEqual(list((created / "scripts").iterdir()), [])

    def test_initializer_rejects_before_writes_and_preserves_existing(self):
        before = set(self.root.iterdir())
        self.assertIsNone(self.quiet(init_skill, "../escape", self.root))
        self.assertIsNone(self.quiet(init_skill, "new-skill", self.root, "unsupported"))
        self.assertEqual(set(self.root.iterdir()), before)
        original = (self.skill / "SKILL.md").read_bytes()
        self.assertIsNone(self.quiet(init_skill, "sample-skill", self.root))
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), original)

    def test_packaging_excludes_unwanted_files_and_keeps_assets(self):
        unwanted = (".git/config", "__pycache__/a.pyc", ".venv/config", "node_modules/x/a.js", "dist/a.txt", "debug.log", "file.tmp", ".env", ".env.local", "assets/key.pem", "credentials.json", "old.skill", "assets/private/note.txt")
        for relative in unwanted:
            self.resource(relative)
        self.resource("assets/keep.txt", "required asset")
        archive = self.quiet(package_skill, self.skill, self.root / "output", ["assets/private/*"])
        self.assertIsNotNone(archive)
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()), {"sample-skill/SKILL.md", "sample-skill/assets/keep.txt"})
            self.assertIsNone(package.testzip())

    def test_packaging_never_overwrites_and_rejects_internal_output(self):
        archive = self.quiet(package_skill, self.skill, self.root / "output")
        original = archive.read_bytes()
        self.assertIsNone(self.quiet(package_skill, self.skill, self.root / "output"))
        self.assertEqual(archive.read_bytes(), original)
        self.assertIsNone(self.quiet(package_skill, self.skill, self.skill / "output"))
        self.assertFalse((self.skill / "output").exists())

    def test_invalid_skill_and_excluded_entrypoint_cannot_package(self):
        self.assertIsNone(self.quiet(package_skill, self.skill, self.root / "out", ["SKILL.md"]))
        self.write_skill(body="[TODO: incomplete]")
        self.assertIsNone(self.quiet(package_skill, self.skill, self.root / "out"))
        self.assertFalse((self.root / "out").exists())

    def test_cli_end_to_end(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        commands = (
            (["init_skill.py", "cli-skill", "--path", str(self.root), "--resources", "references"], 0),
            (["quick_validate.py", str(self.root / "cli-skill")], 1),
            (["quick_validate.py", str(self.skill)], 0),
            (["package_skill.py", str(self.skill), str(self.root / "cli-output")], 0),
        )
        for args, expected in commands:
            with self.subTest(command=args[0]):
                run = subprocess.run([sys.executable, "-B", str(SCRIPTS / args[0]), *args[1:]], capture_output=True, text=True, encoding="utf-8", env=env)
                self.assertEqual(run.returncode, expected, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
