# project-prompt-evolver · 项目提示词沉淀与迭代

一个 Codex skill：从已完成项目中提炼可复用方法，记录提示词的实际使用来源，并按已授权的策略将新增或迭代后的提示词发布到 GitHub。

本仓库维护 skill 指令、辅助脚本、模板、规范和测试；[project-prompt-library](https://github.com/michael061122-star/project-prompt-library) 保存可复用提示词及版本变更记录。两者独立维护，日常项目沉淀更新提示词库。

## 项目解决什么问题

一个项目经过多轮沟通才完成后，真正有效的需求约束、操作步骤、纠错经验和验收要求往往散落在聊天和文件中。下次执行相似项目，需要重新解释和试错；直接改写旧提示词，又容易丢失来源或覆盖其他改进。

project-prompt-evolver 将这些经验提炼成带输入参数、执行方法、依赖、验收和交付要求的提示词。后续迭代以实际使用版本为依据，帮助减少重复说明，并保留可追踪的变更历史。

## 主要功能与真实能力边界

| 功能 | 实际行为 |
|---|---|
| 检索复用 | 通过现有 GitHub 工具或本地库快照检索候选，读取原文、核对适用条件并填写本次参数。辅助脚本按元数据关键词检索，不提供向量检索服务。 |
| 完成后沉淀 | 在用户要求沉淀、且指定目标有验收依据时，依据实际可读的对话、最终文件和检查结果提炼方法，将一次性数据与偏好参数化。 |
| 来源追踪 | 在本地记录仓库、文件路径、完整提交 SHA、提示词 ID、版本、原文哈希及原文快照，供后续迭代核实。 |
| 有依据地迭代 | 通用修正更新原条目；任务流程或验收实质不同则建立关联变体；没有新增可复用经验时保持原版。远端已有更新时，由 Codex 比较实际使用原版、最新版与候选内容。 |
| 发布与恢复 | 按配置自动提交，或自动创建 PR。发布前准备受限清单，检查远端变化；结果不明时先查询远端，成功后回读核对，减少重复提交与意外覆盖。 |
| 预览 | 用户只要求预览时，生成本地草稿和检查结果，不执行远端发布。 |

必须了解以下边界：

- **skill 提供工作流程，Python 脚本只做本地处理。** 脚本负责格式、参数、哈希、来源记录、快照、发布清单和回执检查，本身不联网、不读取访问令牌、不执行 GitHub 发布。远端操作由 Codex 调用当前可用且已授权的 GitHub 插件、MCP 或 Git 工具完成。
- **不会在后台监控项目。** 普通任务完成、读取提示词或复制文件，不会自行触发公开发布。沉淀需要用户请求或符合已明确授权的调用范围。
- **不能保证读到完整历史。** 只使用实际可访问的上下文与文件；缺失的聊天或精确旧版来源不能编造。关键问题尚未解决、来源无法核实或发布条件不足时，保留草稿并说明原因。
- **第一版的受限发布清单只包含两个 UTF-8 文件：提示词原文和该版本变更说明。** 发布辅助流程针对 github.com；不支持自动跨库导入或 GitHub Enterprise。素材、模板和其他附件作为依赖声明，不自动上传。PR 模式不会自动合并。
- **结果仍需判断与验证。** 常见令牌、个人路径和自定义禁用词扫描不能替代语义复查。原项目成功不代表新提炼提示词已复现，也不能保证一次执行完成新项目或每次升级都更好。

验证级别为 `reviewed`（内容检查）、`single-project`（明确项目实际使用并验收）、`replayed`（代表任务重新执行），并记录真实验证范围。配置记录已有授权，不新增账号权限，也不绕过环境审批或仓库保护。

## 安装方法

### 环境要求

- 支持本地 skills 的 Codex 环境，以及 Python 3.10 或更高版本；辅助脚本只使用标准库。
- 检索远端内容需要相应读取能力；发布需要已授权的写入、分支前提检查和多文件原子提交能力。安装 Git 不等于已配置 GitHub 凭据。

### 从 Release 安装

当前首个发布版本为 **v1.0.0**。到 [Releases](https://github.com/michael061122-star/project-prompt-evolver/releases) 下载 [project-prompt-evolver-v1.0.0.zip](https://github.com/michael061122-star/project-prompt-evolver/releases/download/v1.0.0/project-prompt-evolver-v1.0.0.zip)。

1. 解压，取得完整的 `project-prompt-evolver/` 目录。
2. 将整个目录放到 `$CODEX_HOME/skills/project-prompt-evolver/`。未设置 `CODEX_HOME` 时，使用 `~/.codex/skills/project-prompt-evolver/`。Windows 中 `~` 对应当前用户目录。
3. 确认 `SKILL.md`、`agents/`、`scripts/`、`references/`、`assets/` 与 `LICENSE` 都位于该目录内，避免多嵌套一层同名目录。已有安装时先核对版本，不直接覆盖本地定制。
4. 在新 Codex 聊天中调用 `$project-prompt-evolver`。尚未发现该技能的已有聊天，可以提供 `SKILL.md` 的实际路径，让 Codex 读取并执行。

也可克隆源码，将 `skills/project-prompt-evolver/` 整个目录复制到上述位置：

```sh
git clone https://github.com/michael061122-star/project-prompt-evolver.git
```

安装 skill 不会自动创建提示词库，也不会自动授予发布权限。

## 使用方法

### 1. 首次配置提示词库

目标仓库应已存在。明确仓库、分支、目录、公开规则和发布方式；同一授权范围内的后续沉淀沿用配置。

```text
使用 $project-prompt-evolver。
将 owner/my-prompt-library 设为提示词库，允许在 prompts/ 下维护提示词和版本变更说明。
公开内容只包含经过脱敏和复查的通用方法。
检查通过后自动提交到 main，并将已有授权与这些设置保存在个人配置中。
```

将 `owner/my-prompt-library` 替换为你有写入权限且获准公开内容的仓库。若维护本项目配套库，实际名称为 `michael061122-star/project-prompt-library`。

配置查找顺序为用户指定路径、当前项目 `.prompt-evolver/config.json`、`$CODEX_HOME/project-prompt-evolver/config.json`。未设置 `CODEX_HOME` 时，个人配置为 `~/.codex/project-prompt-evolver/config.json`。模板见 [config.example.json](skills/project-prompt-evolver/assets/config.example.json)，分发模板中的发布授权默认关闭。

`direct` 表示检查通过后自动提交到指定分支；`pr` 表示自动创建 PR，是否合并另行处理。授权范围或目标变化时，需要重新明确相应范围。

### 2. 项目开始时检索复用

```text
使用 $project-prompt-evolver，为当前项目检索合适的提示词。
核对适用范围和依赖，记录实际使用版本，再结合本次需求继续执行项目。
```

找不到适合的候选时，不能强行套用。也可以手动复制完整提示词、保留元数据与固定提交链接，并提供所需输入；后续迭代仍需核实精确来源。

### 3. 指定目标验收后沉淀

```text
使用 $project-prompt-evolver，当前指定目标已验收。
依据可读取的过程、最终文件和检查结果提炼通用经验。
如使用过已有提示词，基于实际使用版本迭代；没有新增可复用经验时保持原版。
按已有配置发布。
```

尚无来源提示词时可以新增条目。已有条目更新时须核实实际使用原版，并处理远端同期改进。多轮对话本身不构成必须升级的理由。

### 4. 只生成预览

```text
使用 $project-prompt-evolver，为当前已完成目标生成沉淀预览，暂不发布。
```

执行结束应说明新增、更新、变体或无变化，列出来源与验证范围。成功发布返回实际提交或 PR 及提示词链接；未发布则给出草稿和具体原因。`.prompt-evolver/` 中的来源快照、review 和回执留在本地。

详细规范见 [格式与来源](skills/project-prompt-evolver/references/formats.md) 和 [发布与恢复](skills/project-prompt-evolver/references/publishing.md)。本项目采用 [MIT 许可证](LICENSE)。
