# CQ4OE：从能力问题评估 LLM 辅助本体生成

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20080309.svg)](https://doi.org/10.5281/zenodo.20080309)

CQ4OE 用统一的能力问题（Competency Questions，CQ）评估不同的 LLM 本体生成方法。仓库包含六个由领域专家标注的本体，以及与 CQ 对齐的 CQ2Term 和 CQ2Onto 金标准。

金标准和完整标注过程也发布在 HuggingFace 数据集：[oeg/CQ4OE](https://huggingface.co/datasets/oeg/CQ2Onto)。

## 两个评测任务

- **[CQ2Term](https://w3id.org/cq4oe/task/CQ2Term)**：给定一个能力问题，预测回答该问题所需的类和属性。
- **[CQ2Onto](https://w3id.org/cq4oe/task/CQ2Onto)**：给定一个领域的一组能力问题，生成能够回答这些问题的完整 OWL 本体。

## 已有领域

- [Wine](https://github.com/UCDavisLibrary/wine-ontology)：葡萄酒本体
- [VGO](https://vocab.linkeddata.es/vgo/)：电子游戏本体
- [SWO](https://obofoundry.org/ontology/swo.html)：软件本体
- [AWO](https://people.cs.uct.ac.za/~mkeet/OEbook/ontologies/AfricanWildlifeOntology1.owl)：非洲野生动物本体
- [ODRL](https://www.w3.org/ns/odrl/2/)：开放数字权利语言本体
- [Water](https://saref.etsi.org/saref4watr/v1.1.1/#clause-4-2-7)：SAREF4WATR 本体

## 本地 Web 评测台（Docker Compose）

安装 Docker Desktop 或带 Compose 插件的 Docker Engine，然后在仓库根目录执行：

```sh
docker compose up --build -d
docker compose ps
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。`/health` 会报告数据库和 embedding 模型状态。首次启动时 Ollama 会把 `embeddinggemma` 下载到持久化卷；下载期间页面仍可访问，排队中的评测会等待模型就绪。查看启动日志：

```sh
docker compose logs -f app ollama
```

### Web 评测流程

1. 在 **Agent 管理** 页面创建 Agent，并为它添加一个或多个模型名称标签。它们只用于标记被评估的提交；评测台不会调用这些模型。
2. 在 **新建运行** 页面选择 Agent、模型和一个或多个“任务 / 领域”条目。打开领域详情可以查看完整 CQ 清单，也可以下载领域专属 CQ 包。
3. 在评测台外运行你的 Agent。CQ 包包含 `cqs.json`、带版本和完整 CQ ID 的 `manifest.json`、README，以及 CQ2Term 的 `prediction_template.json`；包内不包含金标准答案。
4. 每个任务 / 领域上传一个最终预测文件：CQ2Term 上传填写完整的 UTF-8 `prediction_template.json`；CQ2Onto 上传该领域合并后的 `.owl`、`.rdf`、`.xml`、`.ttl`、`.nt` 或 `.n3` 本体。`normal`、`cqbycq`、`agent` 是生成方式，不是三种上传文件；生成日志不参与评分。CQ2Onto 需要在上传前确认 Agent 已获得清单中的全部 CQ。
5. 点击“准备运行”。评测台会为本次 run 建立独立目录，保存输入快照、阶段日志、`report.md`、指标和评测脚本生成的 JSON/CSV/TXT/XLSX/Atomic TBox 等产物。
6. 在 **运行记录** 中筛选 Agent、模型、任务、领域、状态和日期。列表默认显示与上一条可比记录的指标趋势，可关闭趋势；选择 2～4 条记录后可以进入对比页查看共同条目和指标变化。

记录页优先展示有明确口径的关键分数，网页数值保留两位小数；数据库和原始文件保留完整精度。运行详情的中文指标摘要由 Web 从结构化结果整理。下载的 `report.md` 仍是原项目 CQ2Term/CQ2Onto 评测脚本生成的英文原文，可在详情页展开查看。

### 模型标签和 API

Agent 管理页面只需填写模型名称。它是运行记录的标签，不是模型连接配置；当前 Web 不需要接口地址或 API Key。

也可以通过 HTTP 或 Python 管理模型：

```bash
curl -X POST http://127.0.0.1:8000/api/agents/<agent_id>/models \
  -H "Content-Type: application/json" \
  -d '{"name":"deepseek-v4-pro"}'
```

对应的 Python 调用：

```python
import requests

requests.post(
    "http://127.0.0.1:8000/api/agents/<agent_id>/models",
    json={"name": "deepseek-v4-pro"},
).raise_for_status()
```

编辑模型使用 `PATCH /api/models/<model_id>`，查询使用 `GET /api/agents/<agent_id>/models`。

### 数据保存与备份

主机 `./data` 挂载到容器的 `/app/data`，包含 `evaluator.sqlite3` 和 `runs/<run-id>/` 下的输入、日志、工作文件、报告与结果。停止并重启不会丢失数据：

```sh
docker compose down
docker compose up -d
```

做备份时先停止 Compose，再完整复制 `./data` 目录；数据库和所有 run 文件必须一起保存。恢复时将备份目录放回 `./data` 后重新启动 Compose。Ollama 模型保存在单独的 Docker volume 中。

## 评测产物和指标

CQ2Onto 采用分层评测，页面默认按维度和层级展示指标，详细结果可在运行详情中查看：

1. **类与属性（ClassProperty）**：硬匹配、序列匹配、编辑距离、Jaro-Winkler 距离、语义余弦相似度、Top-3 聚合，以及精确率、召回率、F1。
2. **属性特征（PropertyCharacteristics）**：功能性、传递性等 OWL 属性特征的精确率、召回率、F1。
3. **三元组（Triple）**：domain/range 三元组的精确率、召回率、F1 和嵌入诊断。
4. **公理（Axiom）**：原子 TBox 公理的精确率、召回率、F1、嵌入诊断，以及至少一项、平均、完整覆盖率。
5. **层级闭包（HierarchyClosure）**：使用 HermiT 推理器计算类和属性继承闭包的精确率、召回率、F1，以及闭包补救覆盖率。
6. **CQ 覆盖率（CQCoverage）**：每个 CQ 所需 TBox 公理在生成本体中的至少一项、平均、完整覆盖率，并统计闭包补救覆盖率。

CQ2Term 评估显式类和属性，主要包含类与属性匹配指标、整体精确率 / 召回率 / F1，以及按 CQ 的覆盖率指标。评测台会保存 TP、FP、FN、分子、分母等可复核计数。

## 标注流程

每个源本体的标注分为四个阶段：

1. **核心词项选择**：结合连接度统计、可视化和领域相关性确定核心类与属性。
2. **CQ 筛选与标注**：排除依赖外部知识、无法由本体回答或只涉及 ABox 的 CQ，并标注显式、隐式和派生词项。
3. **CQ 补充**：为没有被任何 CQ 覆盖的核心词项新增可回答的 CQ；新增 CQ 在数据集中以 `⋆` 标记。
4. **金标准构建**：同时构建 CQ2Term 和 CQ2Onto。CQ2Term 保留显式词项；CQ2Onto 保留显式、隐式、派生词项及其必要公理，并记录 CQ 到词项 / 公理的来源关系。

每个决定由三人独立审核，至少两人同意才保留。

## 数据集规模

| 本体 | 规模 | 源 CQ | 保留 | 新增 `⋆` | CQ2Onto | CQ2Term |
|---|---:|---:|---:|---:|---:|---:|
| Wine | 小 | 7 | 4 | 1 | 5 | 5 |
| AWO | 小 | 14 | 7 | 0 | 7 | 7 |
| ODRL | 中 | 35 | 13 | 6 | 19 | 19 |
| Water | 中 | 43 | 21 | 0 | 21 | 20 |
| VGO | 大 | 68 | 30 | 1 | 31 | 22 |
| SWO | 大 | 88 | 35 | 0 | 35 | 26 |

## 命令行评测

如果不使用 Web 评测台，也可以把预测产物放入对应任务的 `01_predictions/` 目录，然后在仓库根目录分别执行：

```bash
# CQ2Term
(cd CQ2Term && python scripts/run_all_cq2term.py)

# CQ2Onto：按 01_predictions/<mode>/<model>/ontology/ 扫描
(cd CQ2Onto && python scripts/run_all_evaluation_agent_datasets.py)
```

评测脚本会读取金标准，执行各个维度，并把结果写入 `03_evaluation_results/` 和 `04_summary/`。

## 贡献结果

如果希望提交新的评测结果，请创建 Issue 并提供：每个本体的生成文件、对应任务（CQ2Term 或 CQ2Onto），以及模型和生成方法说明。审核通过后，结果会加入仓库。

## 相关页面

- [在线排行榜](https://oeg-upm.github.io/cq4oe-benchmark/leaderboard/)
- [使用说明](usage_instructions.md)
- 启动本地 Web 后，从侧栏进入“评测说明”，查看各模块的计算方法和解读口径。
- [提交说明](submissions/submission_guideline.md)
- [设计规格](docs/superpowers/specs/2026-10-30-local-web-evaluator-design.md)
- [实施计划](docs/superpowers/plans/2026-10-30-local-web-evaluator.md)

## 致谢

本项目得到 SOEL 项目资助：[Supporting Ontology Engineering with Large Language Models](https://w3id.org/soel)，项目编号 PID2023-152703NA-I00，由 MCIN/AEI/10.13039/501100011033 和 ERDF/UE 资助。感谢 EDINT（Espacios de Datos para las Infraestructuras Urbanas Inteligentes）本体开发团队分享评测资源。
