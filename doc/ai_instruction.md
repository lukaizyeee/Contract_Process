# AI 工作指引

为了避免误读仓库状态或把规划内容当成现状，在执行任何代码修改前，请按以下顺序建立上下文。

## 1. 必读顺序

1. 先读 [doc/project_structure.md](/Users/aizyeee/ZZH/dentons_work/code/doc/project_structure.md)
   * 这是当前仓库现状的主文档
   * 用来确认模块职责边界和当前主数据流
2. 如果任务与业务规则相关，再读 [doc/audit_implementation_plan.md](/Users/aizyeee/ZZH/dentons_work/code/doc/audit_implementation_plan.md)
   * 注意区分“已实现 / 部分实现 / 未实现”
3. 如果任务涉及长期方向或大改动，再读 [doc/master_plan.md](/Users/aizyeee/ZZH/dentons_work/code/doc/master_plan.md)
4. 如果任务涉及实施路径或接口层落地，再读 [doc/implementation_plan.md](/Users/aizyeee/ZZH/dentons_work/code/doc/implementation_plan.md)
5. 如果任务涉及优先级或现有缺口，再读 [doc/tasks.md](/Users/aizyeee/ZZH/dentons_work/code/doc/tasks.md)

## 2. 需求源优先级

与合同审计业务直接相关的最终需求源，优先参考：

* [needs-260211.txt](/Users/aizyeee/ZZH/dentons_work/code/needs-260211.txt)

如果文档与需求源冲突，应以需求源和当前代码真实行为为准，并同步修正文档。

## 3. 执行原则

* 先确认“当前代码真实行为”，再写方案
* 不要把未来规划写成当前能力
* 如果修改了模块职责、数据流或任务状态，要同步更新文档
* 如果引入了语义审计能力，要明确它接入的是：
  * 独立检索接口
  * 还是主审计链路

## 4. 当前容易误判的点

* 搜索引擎已经实现，但主审计流程还没有完成语义化
* 当前“批注”主要是可见文本插入，不是完整 Word comment
* 当前签字区、退款、银行账户、代扣税等核心需求尚未完成

## 5. 回答或规划时建议显式说明

建议在回复中主动说明你参考了哪些文件，例如：

* “根据 `project_structure.md`，主审计链路仍然在 `WordProcessor` 中。”
* “根据 `audit_implementation_plan.md` 与 `needs-260211.txt`，退款条款仍未实现。”
