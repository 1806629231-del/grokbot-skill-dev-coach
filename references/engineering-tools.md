# 工程脚本与校验边界

在 Phase 3 自检、Phase 4 脚本回归或需要打包分发时阅读。命令中的 `scripts/` 指本 Skill 的脚本目录；在其他目录工作时使用脚本绝对路径。

## 运行环境

- Python 3.10+，以及 `PyYAML`（导入名 `yaml`）。先检查当前运行环境；缺失时报告依赖，再按已授权的环境配置方式处理。
- Windows 建议 Python 3.12+，用于识别并排除 junction 目录链接。
- 主文件使用 UTF-8；校验支持 UTF-8 BOM 与 CRLF。
- 名称统一为 1–64 字符，小写字母/数字与单个内部连字符；不能首尾带连字符，不能使用 Windows 保留设备名。
- 外显名称写入 `agents/openai.yaml` 的 `interface.display_name`，不要放入 SKILL.md frontmatter。

## 初始化

```text
python scripts/init_skill.py my-skill --path <parent-directory>
python scripts/init_skill.py my-skill --path <parent-directory> --resources scripts,references
```

默认只创建 `SKILL.md`；可选资源为 `scripts,references,assets`，仅创建指定目录，不生成占位示例文件。新目录名与内部名称一致；已有目标目录直接报错，不覆盖。主文件草稿仍含 TODO，必须补全后才能验收。

## 静态校验

```text
python scripts/quick_validate.py <skill-directory>
```

| 检查项 | 处理方式 |
|---|---|
| 主文件可读取、YAML 格式及字段、非空 name/description | 错误时退出码 1 |
| 名称格式与长度、description 长度及尖括号 | 错误时退出码 1 |
| 整个 SKILL.md 少于 500 行、正文非空 | 错误时退出码 1 |
| description TODO、正文中的 `[TODO: ...]`、旧脚手架占位资源 | 错误时退出码 1；正文代码围栏中的教学示例忽略 |
| 主文件与链接到的 Markdown 中的本地文件链接 | 缺失时报错；支持内联链接和引用式链接定义；不验证锚点 |
| 目录与 name 不一致 | 警告；兼容既有中文目录，不自动重命名 |
| 未识别工作流标题、多层 Markdown 引用、包外依赖 | 警告，人工核对 |

保留 `validate_skill(path) -> (bool, message)` 接口。警告不改变退出码；错误会阻止打包。

自动检查不证明描述语义完整、触发准确、工作流可执行或引用资料无规则冲突。这些仍由实现自检和正常/边缘/不应触发三类测试覆盖。Markdown 检查针对真实文件链接，示例围栏、纯文本路径和运行时动态拼接路径需人工核对。

## 打包

```text
python scripts/package_skill.py <skill-directory> <output-directory>
python scripts/package_skill.py <skill-directory> <output-directory> --exclude "assets/private/*"
```

先校验，再创建 ZIP 格式的 `.skill`，最后检查压缩包完整性。输出目录必须在 Skill 外部；同名压缩包不覆盖。额外排除规则可重复传入，匹配文件名或相对路径，统一使用正斜杠。

默认排除版本库、Python 缓存、虚拟环境、node_modules、编辑器本地设置、构建输出，以及日志、临时文件、备份、旧 `.skill`、`.env*`、常见私钥和凭据文件；不跟随符号链接或可识别的 junction。准确规则见 `scripts/package_skill.py` 中的常量。

这些规则依据文件名，不能识别任意文件中的密钥。分发前查看文件清单，确认需要的资源仍在包内，并检查项目特有的本地配置是否需要额外排除。

## 回归测试

```text
python -B scripts/test_skill_tools.py
```

测试使用独立临时目录，覆盖真实初始化、有效与无效 Skill 校验、资源链接、压缩包成员及不覆盖已有文件。测试结束清理本次临时目录；不会修改用户已有 Skill。
