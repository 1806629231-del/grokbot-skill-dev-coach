# grokbot-skill-dev-coach

Grok Bot「Skill 开发教练」（skill-dev-coach）的辅助脚本和参考资料。模板导入后只带 SKILL.md，缺脚本时从本仓库下载。

- `scripts/`：init_skill.py（建骨架）、quick_validate.py（校验）、package_skill.py（打包）、test_skill_tools.py（自检）
- `references/`：写作要点、交互指南、工作流等

## 安装
```bash
D=/workspace/skill-packs/skill-dev-coach; mkdir -p $D
git clone --depth 1 https://github.com/1806629231-del/grokbot-skill-dev-coach /tmp/sdc && cp -r /tmp/sdc/scripts /tmp/sdc/references $D/
python3 $D/scripts/test_skill_tools.py
```
只需 Python 3，无第三方依赖、无账号。
