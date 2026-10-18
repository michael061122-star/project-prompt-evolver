# 项目提示词沉淀与迭代

`project-prompt-evolver` 是一个 Codex skill：为新项目检索并复用提示词，在已完成项目中提炼通用方法，基于实际使用版本进行迭代，再按用户配置自动提交到 GitHub 提示词库。

- **仓库 A，本仓库**：skill 指令、本地辅助脚本、模板、规范及测试。
- **[仓库 B](https://github.com/michael061122-star/project-prompt-library)**：提示词原文及每个版本的变更说明。

日常沉淀更新 B；不会自动修改本 skill。开源许可为 MIT。

## 安装

把本仓库的 `skills/project-prompt-evolver` **整个目录**安装到 `$CODEX_HOME/skills/`。未设置 CODEX_HOME 时，通常为 `~/.codex/skills/`。也可在 Codex 中让 skill-installer 从本仓库的该目录安装。安装后，在新聊天中调用 `$project-prompt-evolver`；尚未重新发现技能的聊天可指定 SKILL.md 的实际路径。

辅助工具只依赖 Python 3.10+ 标准库。GitHub 连接须具备实际读取和原子写入能力；skill 不提供额外权限，也不要求另装特定 github-mcp。发布通过现有 GitHub 插件/MCP/Git 工具完成，不保存访问令牌。

## 首次配置

告诉 Codex：

```text
使用 $project-prompt-evolver。
将 owner/my-prompt-library 设为提示词库，允许在 prompts/ 下维护提示词及版本变更说明。
检查通过后自动提交到 main，保存在个人配置中，后续同类沉淀沿用此设置。
```

替换为你有权限且明确愿意公开内容的实际仓库。模板见 `skills/project-prompt-evolver/assets/config.example.json`。个人配置保存到 `$CODEX_HOME/project-prompt-evolver/config.json`；默认 CODEX_HOME 为 `~/.codex`。项目内 `.prompt-evolver/config.json` 可提供项目配置。仓库内分发的示例不携带个人发布授权。

支持 `direct` 自动提交、`pr` 自动创建 PR。PR 模式不会自动合并。首次人类授权确定目标和策略后，同一范围的后续调用无需反复确认；平台审批和仓库权限仍然有效。

## 日常使用

项目开始：

```text
使用 $project-prompt-evolver，从提示词库查找适合季度经营汇报 PPT 的提示词，
记录实际使用版本，并根据本次提供的数据完成制作。
```

项目验收后：

```text
使用 $project-prompt-evolver，当前汇报 PPT 已验收。
提炼本次有效经验，基于实际使用的提示词迭代，并按配置发布。
```

只要本地草稿：

```text
使用 $project-prompt-evolver，为当前已完成目标生成沉淀预览。
```

## 迭代规则

- 每次复用记录仓库、路径、完整提交 SHA、ID、版本和完整原文哈希，保存本地原文快照。
- 通用缺漏和错误修正更新原条目；受众、流程或验收实质不同则建立关联变体。
- 只有参数变化或无新增可复用经验时保持原版。
- 同时比较实际使用原版、最新远端和本次经验，远端变化时保留来源并整合。
- 新提炼原文未经独立执行时如实标注，项目成功不自动代表新提示词已验证。
- 发布前完成内容与隐私复查；正文和变更说明以同一次提交发布。超时先查询远端，避免重复提交。

提示词使用 `---` 中的 JSON 元数据加 Markdown 正文。此格式便于参数、版本、来源的确定性检查，并保持复制使用方便。格式及命令见 [formats.md](skills/project-prompt-evolver/references/formats.md)，原子发布及恢复见 [publishing.md](skills/project-prompt-evolver/references/publishing.md)。

## 验证

从仓库根目录运行：

```text
python -m unittest discover -s tests -v
python skills/project-prompt-evolver/scripts/prompt_library.py --help
```

测试仅使用临时本地文件、合成提交标识和合成验收证据，不写真实 GitHub。受限环境可以把 `PROMPT_EVOLVER_TEST_DIR` 设为可写的临时测试目录。辅助工具不联网，远端读取、权限及最终发布状态由真实 GitHub 工具核实。

## 使用范围

skill 在被调用时执行，不在后台监控所有项目；仅能处理实际可读取的上下文与资料。第一版自动发布提示词和脱敏变更说明两个文本文件，素材以依赖声明。自动扫描覆盖常见令牌、私有路径及本地禁用词，仍需要对待公开内容进行语义复查。

参考 [OpenAI Skills 文档](https://developers.openai.com/plugins/concepts/skills) 与 [创建技能指南](https://developers.openai.com/plugins/build/skills)。
