---
{
  "schema_version": 1,
  "id": "task-workflow",
  "title": "任务类型名称",
  "version": "1.0.0",
  "summary": "填写本提示词适用的具体目标、受众和交付物。",
  "tags": ["任务类型"],
  "inputs": [
    {"name": "task_goal", "required": true, "description": "本次任务的目标"},
    {"name": "source_materials", "required": true, "description": "可读取的资料或素材"},
    {"name": "acceptance", "required": true, "description": "本次验收标准"}
  ],
  "requires": [],
  "validation": {
    "level": "reviewed",
    "note": "仅完成提炼与内容检查，尚未在新项目中复现。"
  },
  "lineage": null
}
---

完成以下项目目标：{{task_goal}}。

使用这些资料：{{source_materials}}。缺少影响结果的关键资料时先说明并补充获取，不虚构资料内容。

## 执行方法

将成功项目中实际有效的步骤和决策条件写在这里。区分可调整默认值与必须满足的约束，纳入经过验证的关键修正，并说明依赖或输入缺失时如何处理。

## 验收与交付

按照 {{acceptance}} 检查最终成果。在这里补充该任务类型的具体验收项、交付格式和已知边界。没有执行的检查要明确标记，不能报告为通过。
