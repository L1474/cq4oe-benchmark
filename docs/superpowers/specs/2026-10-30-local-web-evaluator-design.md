# CQ4OE 本地 Web 评测台设计

## 目标与边界

为 CQ4OE 增加一个可随 GitHub 仓库分发的本地 Web 评测界面。使用者下载项目，在自己的机器上启动服务，上传 CQ2Term 预测 JSON 或 CQ2Onto 本体文件，运行现有评测流水线，并管理、查看和比较历史评测。

评测台不负责调用生成模型，也不要求使用者提供生成代码或生成时日志。可选的模型提供方、模型名称和方法说明只作为 Agent/模型元数据保存。

首版是单机本地应用，不提供公网托管、账号注册或跨用户共享。服务默认仅监听本机地址。数据和预测文件保留在使用者自己的机器上。

## 分发与运行架构

- 通过 Docker Compose 提供统一运行环境，涵盖 Web 服务、评测器、Java/HermiT 和 embedding 服务，减少 Python、Java 与服务地址的手工配置。
- 首版使用 SQLite 保存元数据、运行状态、结构化指标和产物索引；SQLite 文件位于持久数据目录。
- 输入、输出、报告和日志等文件保存在 `data/runs/<run_id>/`。数据库记录相对路径、文件类型、大小和 SHA-256，不把大文件作为数据库 BLOB。
- 评测期间使用每次运行独立的输入和输出路径，不暂存到仓库的共享 `01_predictions`，避免同名覆盖和跨运行结果混合。
- 每次运行保存评测器版本、黄金标准版本或文件哈希、评测阈值、匹配方法、embedding 模型、启用层等配置快照。
- 单机首版以后台队列顺序运行评测，持久保存各阶段状态和 stdout/stderr。取消或失败的运行仍保留已有输入、日志和部分输出。
- 评测完成后不刷新共享 leaderboard；运行结果只属于对应的 run。

## 数据模型

- `users`：本地实例中的默认用户；为未来多用户部署保留所有权字段，不在首版提供登录。
- `agents`：用户维护的生成方案或智能体条目，保存名称、描述和时间戳。
- `models`：隶属于 Agent 的模型配置，保存展示名、提供方、模型标识和可选备注。
- `runs`：一次上传和评测批次，具有唯一 `run_id`，关联用户、Agent 和可选模型，并保存状态、开始/结束时间及配置快照。
- `run_items`：该次运行中的任务与领域组合，例如 `(CQ2Onto, wine)`；保存每项状态、阶段时间和 CQ 包版本/完成确认。
- `artifacts`：输入预测、报告、指标原始 JSON、CSV/XLSX/TXT、原子 TBox、日志等文件的索引。
- `metrics`：按 run item、维度、层、指标名和统计范围存储数值，可附 TP/FP/FN、分子分母和单位。
- `run_events`：按序记录运行阶段、级别、时间、消息和可选日志文件位置。

任务与领域目录从仓库的黄金标准和 CQ 文件动态读取，不在数据库中复制成另一份可编辑目录。运行记录保留提交时选择的任务、领域和显示名称快照。

## 页面与工作流

侧栏包含“运行”“记录”“领域目录”“Agent 管理”。

- **Agent 管理**：创建和编辑多个 Agent；每个 Agent 下维护一个或多个模型条目。
- **运行**：选择 Agent、模型，并通过任务与领域选择控件逐项添加一个或多个评测项；运行表单不直接铺开完整领域目录。只显示已选领域及任务对应的 CQ 数量，题目全文从详情抽屉查看。所选任务和领域可打包下载。
- **CQ 包**：按任务和领域分别提供 CQ JSON、包含 task/domain/version/count/expected CQ IDs 的 manifest，以及简明输入说明。CQ2Term 包另含一个保留全部 CQ ID、待填写 class/property 的预测模板。CQ 包不包含黄金答案或专家标注。
- **产物上传**：CQ2Term 接收预测 JSON，CQ2Onto 接收 rdflib 可解析的 OWL/RDF/Turtle 文件。CQ2Term 服务端校验预测是否包含该领域该任务全部必需 CQ ID，并拒绝缺失、重复或未知 ID。CQ2Onto 合并本体不携带可靠的逐 CQ 生成来源，因此在 CQ 详情抽屉中提供逐题“已提供给 Agent”核对；只有全部完成后，上传检查弹窗才允许确认并提交本体。弹窗醒目显示已完成数/总数，并可跳转查看题目详情。这个确认记录与 CQ 包版本一并保存到 run item。
- **领域目录**：独立页面动态列出仓库内已有领域。详情抽屉按 CQ2Term/CQ2Onto 显示各自题数、完整问题和预测格式要求，并提供对应 CQ 包下载；新增黄金标准领域后可以自动发现。
- **记录**：每一行代表一个 `run_id`。支持按 Agent、模型、任务、领域、状态和时间筛选。展示运行状态、领域覆盖和主要指标。
- **运行详情**：展示输入快照、评测配置、阶段状态和实时/完整日志、分任务领域指标、原始产物清单。Markdown 报告在页面渲染，并可下载；JSON、CSV、TXT、XLSX 和上传输入也可下载。
- **趋势与对比**：列表默认对比相同 Agent、模型、任务、领域和评测配置的上一条成功记录；趋势可关闭。用户可选择多条记录显式对比。跨模型对比允许模型不同，但任务、领域和评测配置须匹配；不匹配时说明差异，不计算误导性的增降箭头。跨领域汇总仅用共同领域并显示覆盖数。

## 评测指标与展示

### CQ2Term

展示类、属性及合并术语的 TP/FP/FN、Precision、Recall、F1；各匹配方法分数及最终一对一对齐；按 CQ 和按术语的覆盖明细；CQ 的至少覆盖一个、平均覆盖和完全覆盖率。详情可查看错配、漏项、额外术语和 alignment trace。

### CQ2Onto

不计算单一总分，按维度展示：

1. 类对齐：各匹配方法及综合匹配的 P/R/F1 和 alignment trace。
2. 属性对齐与属性特性：属性匹配，以及 Functional、InverseFunctional、Transitive、Symmetric、Asymmetric、Reflexive、Irreflexive 特性评估。
3. Triple：domain/range 三元组统计、embedding 语义诊断、已对齐属性上的严格 AC 指标和包含未对齐项的 Global 指标。
4. Atomic TBox：从预测本体抽取原子 TBox 公理，作为公理评测输入，不作为单独得分维度。
5. Axiom：公理数量、可选 embedding 候选诊断、严格 AC 比较、Global 比较，以及按 CQ 的严格公理覆盖。
6. Hierarchy：HermiT 推理得到的类/属性包含关系 P/R/F1，以及基于闭包的 CQ 覆盖与严格评测相比新增挽回的覆盖。

Triple 与 Axiom 的 embedding 层标记为语义诊断，不与严格结构匹配分数混为一谈。所有指标保留其 AC/Global、strict/closure 等统计口径，趋势比较要求口径一致。

## 产物保存清单

每个 run item 保存上传的预测文件、配置与黄金标准指纹、每阶段日志，以及评测器生成的原始文件。若某层失败，也保存该层之前已生成的产物并标注缺失阶段。

- CQ2Term：`eval_cq_terms_result.json`、`cqterm_class_trace.csv`、`cqterm_prop_trace.csv`、类/属性 `best_matching.csv`、`cq_coverage.csv`、`term_coverage.csv`、合并 `report.md`。
- CQ2Onto Class / Property：各自的结果 JSON、alignment trace CSV/JSON、best matching CSV，并合并进领域 `report.md`。
- CQ2Onto Triple：`triple_result.json`、`triple_layer3_pairs.csv/json`、自动生成的 `triple_result_report.txt`，并合并进领域 `report.md`。
- CQ2Onto Axiom：`eval_axioms_result.json`、`axiom_details.csv`、`strict_cq_coverage.csv`；运行器启用 embedding 候选明细输出时一并保存 Layer 2 pairs CSV；并合并进领域 `report.md`。
- CQ2Onto Hierarchy：`hierarchy_result.json`、`hierarchy_pairs.csv`，并合并进领域 `report.md`。
- CQ2Onto Atomic：`*_atomic_tbox.json`、`*_atomic_tbox.txt`、`*_atomic_tbox.xlsx`。这些是现有评测流水线生成的中间产物，首版也归档并提供下载。
- Web 运行日志：每个 run item 的 stdout/stderr、阶段状态、失败原因和时间信息。
- 报告：现有各评测阶段向同一个领域 Markdown 文件追加内容；Web 保存完整文件并展示完整报告，同时可按阶段定位章节。

embedding 磁盘缓存属于评测环境内部缓存，不作为某个 run 的结果产物。仓库 leaderboard 和提交 PR 的 `result_data.js` 属于发布流程，不属于单次本地 Web 运行。

## 验证与异常处理

- 上传前校验任务对应文件、扩展名、JSON 结构和领域 CQ ID；CQ2Term 必须覆盖完整且不重复的必需 ID；CQ2Onto 必须通过逐 CQ 完成核对和上传弹窗确认。本体文件尝试解析后才排入评测。
- 各评测阶段按现有依赖顺序执行；Triple、Axiom、Hierarchy 在缺少上游对齐或原子公理时显示阻塞原因，不伪造指标。
- 指标存储从现有 JSON/CSV 解析并保留原始文件，确保网页摘要可重建、细节可追溯。
- 对比前校验任务、领域、评测器/黄金标准指纹和评估配置；不可比项不展示增降方向。
- Docker 数据卷同时包含 SQLite 与运行文件；备份/恢复作为后续明确操作，避免用户误以为容器重建会保留未挂载数据。

## 首版不包含

- Web 内调用 LLM 生成 CQ2Term 或 CQ2Onto 预测。
- 公网账号系统、远端托管、团队权限或公开分享链接。
- 对单个 CQ2Onto 运行压缩成一个综合总分。
- 自动修改黄金标准或全局排行榜。
