# CQ4OE 本地 Web 评测台实施计划

## 目标

构建一个可以随 GitHub 仓库分发的本地 Web 评测台。用户在自己的机器上启动服务，管理 Agent 和模型，下载领域 CQ 包，上传 CQ2Term / CQ2Onto 预测产物，运行隔离的评测流程，并查看、筛选和对比历史 run。

评测台不负责调用 LLM 生成预测，也不要求用户上传生成代码或生成时日志。Agent、模型、提供方和方法说明只作为提交元数据保存。

## 总体架构

- Web 层使用 FastAPI、Jinja2、原生 JavaScript 和 CSS。
- 元数据、运行状态、结构化指标和产物索引使用 SQLite。
- 大文件保存在 `data/runs/<run_id>/`，数据库只记录相对路径、类型、大小和 SHA-256。
- 每个 run 使用独立的输入、工作、日志、报告和结果目录，不写入共享的 `01_predictions`。
- 后台单队列按顺序执行评测，保存每个阶段的状态、stdout、stderr、失败原因和部分结果。
- Docker Compose 提供 Web、Python、Java/HermiT、Ollama embedding 服务；主机 `./data` 保存数据库和运行产物。

## 数据模型

- `users`：默认本地用户，为后续多用户部署保留归属字段。
- `agents`：用户维护的 Agent / 生成方案。
- `models`：隶属于 Agent 的模型配置。
- `runs`：一次上传和评测批次，包含唯一 `run_id`、配置快照、状态和时间。
- `run_items`：run 中的任务 / 领域组合，例如 `(CQ2Onto, wine)`。
- `artifacts`：上传文件、报告、日志、JSON、CSV、TXT、XLSX 和 Atomic TBox 的索引。
- `metrics`：按任务条目、维度、层级、指标和统计范围保存数值及 TP/FP/FN、分子、分母。
- `run_events`：按时间顺序保存阶段事件和日志摘要。

## 实施任务

### 任务 1：领域目录、CQ 包和上传校验

从 `CQ2Term/competency_question/` 和 `CQ2Onto/competency_question/` 动态发现领域。分别统计两个任务的 CQ，去除完全重复的 ID / 问题行，并保留源数量和有效数量。

CQ 包包含：

- `cqs.json`：当前任务的 CQ ID 和问题。
- `manifest.json`：任务、领域、版本、数量、完整 CQ ID 列表和 SHA-256。
- `README.txt`：输入格式说明。
- CQ2Term 专用的 `prediction_template.json`。

CQ2Term 必须校验 JSON、完整且不重复的 CQ ID、`class` / `property` 字符串数组。CQ2Onto 在上传前必须完成逐题确认。

### 任务 2：SQLite 和产物存储

使用版本化迁移初始化 SQLite，开启外键和忙等待。所有用户数据带 `user_id`；同一 run 不能重复添加同一个任务 / 领域组合。文件由产物服务复制到 run 目录，计算大小和 SHA-256 后写入索引。

### 任务 3：隔离评测适配器和指标提取

使用参数数组调用已有 CQ2Term / CQ2Onto 脚本，并设置正确的任务工作目录。所有输出路径必须位于当前 run 的目录内。按以下顺序保存和解析 CQ2Onto 结果：

1. 类和属性对齐。
2. 属性特征。
3. domain/range 三元组。
4. Atomic TBox 提取和公理评测。
5. HermiT 层级闭包。
6. CQ 覆盖率。

指标保留严格、AC、Global、semantic diagnostic、closure 等统计口径，不合成一个没有定义依据的总分。

### 任务 4：持久化运行队列、Worker 和 API

实现草稿创建、逐条上传、CQ 确认、开始运行、状态转换、事件查询和产物下载 API。启动时把中断的 running run 标记为失败并记录中断事件；模型未就绪时保留 queued 状态。关闭服务时等待当前阶段在宽限期内退出。

### 任务 5：中文 Web 页面

页面使用中文界面，侧栏包含：

- 运行：选择 Agent、模型、任务和领域并上传预测文件。
- 记录：筛选、趋势、分页和多选对比。
- 领域：查看领域详情、CQ 清单和下载 CQ 包。
- Agent 管理：管理多个 Agent 及其模型。

CQ2Onto 只醒目展示 CQ 数量，完整题目在抽屉中查看；上传确认使用弹窗，并支持键盘焦点管理和移动端布局。

### 任务 6：运行记录、报告、趋势和对比

记录列表每行对应一个 `run_id`。默认与上一条兼容记录比较指标，使用红绿箭头显示变化，用户可以关闭趋势或选择 2～4 条记录进入独立对比页。对比前校验任务、领域、评测器版本、金标准指纹和配置范围。

运行详情展示输入快照、配置、阶段日志、结构化指标、原始产物和 `report.md`。报告先净化 Markdown / HTML，再在页面内渲染，同时提供下载。

### 任务 7：Docker、文档和发布验证

Docker 镜像包含 Python、Java 17 和运行依赖；Compose 使用 `./data` 和 Ollama named volume。启动入口修正数据目录权限后以非 root 用户运行。README 和使用说明记录安装、启动、CQ 包、上传、备份和恢复流程。

## 验收标准

- CQ2Term 和 CQ2Onto 可分别下载 CQ 包并通过任务专属校验。
- 每个 run 的输入、输出、日志、报告和产物互不覆盖。
- SQLite 重启后保留 Agent、模型、run、指标和产物索引。
- 运行详情能展示 `report.md`、阶段状态和所有已生成产物。
- 记录页面支持筛选、趋势关闭、2～4 条记录对比。
- CQ2Onto 的层级、AC/Global 和诊断指标保持独立可核对。
- 中文页面在桌面和移动端可用，CQ 抽屉内容可滚动到底部。
- 单元测试、API 测试、浏览器交互检查和 JavaScript 语法检查通过。
