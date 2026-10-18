# 格式、来源与命令

## B 仓库布局

```text
prompts/report-ppt/prompt.md
prompts/report-ppt/changes/1.0.0.md
prompts/report-ppt/changes/1.1.0.md
```

每个 ID 一个目录，prompt.md 为完整当前版，原文历史由 Git 保存，变更说明按版本保留。通过元数据检索，不维护容易并发冲突的中央索引。`.prompt-evolver/`、原始聊天和私有素材不进入公开库。

## prompt.md 元数据

参考 `../assets/prompt-template.md`。`---` 内使用 **JSON 对象**，之后为可直接交给 agent 的 Markdown。JSON 属于 YAML 子集；辅助工具仅解析这一约定，不依赖第三方包、不接受任意 YAML 语法。

| 字段 | 约定 |
|---|---|
| schema_version | 整数 1 |
| id | 小写字母、数字和单连字符，最长 64 字符；更新不改 ID |
| title、summary、tags | 标题、适用范围和字符串标签数组，用于检索 |
| version | 无 v 前缀的 MAJOR.MINOR.PATCH |
| inputs | 参数数组；name、required、description 必填，default 可选 |
| requires | 工具能力、模板或资源依赖的字符串数组，无依赖用 [] |
| validation | level 和真实验证范围 note |
| lineage | 首次新增为 null；迭代或变体记录实际使用来源 |

正文参数写作 `{{source_materials}}`，名称使用小写字母、数字和下划线，必须有 inputs 定义。正文结构可随任务调整，但应涵盖方法、关键决策、验收与交付，不能依赖不可见的“上次做法”。

验证级别：`reviewed` 仅内容和依赖检查；`single-project` 指这份方法已实际用于一个项目并验收；`replayed` 指已在代表任务重新执行。原项目成功不等于新提炼的提示词已复现。修改正文后重新判断旧验证是否适用，未执行的新步骤不能继承更高验证结论。

版本建议：兼容修正用 patch，兼容扩展用 minor，输入或交付约定不兼容用 major。只有参数替换、无实际增益或纯措辞变化时无需升级。

## 不可变来源

source 必须恰有 repository、path、commit、id、version、sha256 六个字段。commit 由真实工具读取，为完整 SHA；sha256 是**完整提示词经 UTF-8、LF 标准化后的 SHA-256**，不是 Git blob SHA。

更新时：`lineage={"kind":"update","source":实际使用来源}`。变体用 `kind=variant` 并使用新 ID。lineage.source 保留项目开始时实际使用的原版，不能被发布时最新版替换。

远端目标提示词已经变化时，比较原版、最新版和本次经验；候选另填 integration_base，字段结构与 source 相同，指向最新目标文件和快照提交。版本号必须超过远端版本，无法解决的冲突留在本地。

不要在提示词文件中写它自身的最终提交 SHA，避免循环依赖。使用时从 GitHub 获取 SHA 写入本地 run；发布后的最终 SHA 写入本地 receipt。手动复制时应保留元数据及原文，最好附带 GitHub 的提交固定链接；无法恢复确切来源时不宣称已基于旧版迭代。

## 配置

配置顺序：用户指定路径、当前项目 `.prompt-evolver/config.json`、`$CODEX_HOME/project-prompt-evolver/config.json`；未设置 CODEX_HOME 时最后一项为 `~/.codex/project-prompt-evolver/config.json`。不改写环境变量。项目配置只适用于该项目。

publishing.authorized 是已有用户授权的记录，配置本身不授予权限。随 skill 分发的示例保持 false。privacy.deny_terms 存放不希望公开的名称或短语，保存在本地；扫描输出只显示规则名，不显示匹配内容。

## 本地命令

HELPER 是本 skill 内 scripts/prompt_library.py 的实际路径，由 agent 解析。命令只操作本地 UTF-8 文件，不访问网络。

```text
python HELPER init-config --repo owner/library --branch main --mode direct --authorized --out .prompt-evolver/config.json
python HELPER search --library LOCAL_SNAPSHOT --query "季度 汇报 PPT"
python HELPER record-use --prompt original.md --repo owner/library --path prompts/report-ppt/prompt.md --commit ACTUAL_SHA --out .prompt-evolver/runs/RUN_ID
python HELPER check --prompt draft.md --note change.md --config CONFIG
python HELPER review-template --prompt draft.md --note change.md --out review.json
```

review-template 的复查字段初始为 false，完成状态为 incomplete。实际阅读、检查后再填写：completion.status 为 user-accepted、checks-passed 或 user-and-checks，evidence 是可核实的验收依据；validation_evidence 是实际做过的提示词检查。原始证据只存本地。文件变化后重新检查并更新绑定的哈希，不能自动把全部字段勾为通过。

发布前在**同一个实际提交**读取拟写路径。存在的文件保存正文；明确确认不存在的路径记为 absent。认证失败、403、无法判断的 404 均不能当作不存在。

```text
python HELPER snapshot --root REMOTE --repo owner/library --branch main --commit HEAD_SHA --present prompts/report-ppt/prompt.md --absent prompts/report-ppt/changes/1.1.0.md
python HELPER plan --prompt draft.md --note change.md --library REMOTE --head HEAD_SHA --config CONFIG --review review.json --run .prompt-evolver/runs/RUN_ID/run.json --out attempt-1.json
python HELPER verify-plan --plan attempt-1.json --config CONFIG
```

首次新增省略 run，快照中 prompt 和变更记录均为确认不存在。无变化返回 no-op，不写远端。错误返回 blocked，退出码 2；检查通过退出码 0。每次尝试用新 plan 文件名，避免误用旧计划。

snapshot 保存 agent 已通过真实工具核实的结果，不联网证明远端身份。agent 负责获取真实 SHA、内容和存在性。辅助工具检查快照完整性，拒绝把“没有下载”当成“不存在”。第一版发布清单仅支持 prompt 和脱敏变更说明两个 UTF-8 文件；素材作为依赖声明，额外附件需另行授权、检查与实现。
