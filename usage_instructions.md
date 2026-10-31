# CQ4OE 使用说明

CQ4OE 是评测流水线，不会替你生成本体。你需要先在六个领域之一运行自己的 LLM/Agent，再把预测产物交给 CQ4OE，与按 CQ 对齐的金标准比较，最后读取 Markdown 报告和结构化指标。

推荐使用仓库自带的本地 Web 评测台；如果需要批量或脚本化运行，也可以按下面的命令行流程执行。

## 1. 安装环境

```bash
git clone https://github.com/oeg-upm/cq4oe-benchmark.git
cd cq4oe-benchmark
conda create -n cq4oe python=3.10 -y
conda activate cq4oe
pip install -r requirements.txt
```

CQ2Onto 的层级评测需要 Java/HermiT；请确认 `java -version` 可用。Triple、Axiom 和词项对齐会使用 Ollama 的 embedding 模型，请安装 Ollama 并拉取模型：

```bash
ollama pull embeddinggemma
ollama serve
```

Docker Compose 会自动提供 Python、Java、Ollama 和持久化目录；普通使用建议优先采用 Docker 方式。

## 2. 选择任务和输入

| 任务 | 评估内容 | 需要提供 | 主要输出 |
|---|---|---|---|
| **CQ2Term** | 模型是否能为每个 CQ 找到所需的显式类和属性 | 每个模型 / 领域一个 JSON | 词项级 P/R/F1 和按 CQ 覆盖率 |
| **CQ2Onto** | 模型是否生成能回答整组 CQ 的 OWL 本体 | 每个模型 / 领域一个 OWL/RDF/Turtle 文件 | 词项、属性特征、三元组、公理、层级和 CQ 覆盖率 |

CQ2Onto 支持 `.owl`、`.rdf`、`.xml`、`.ttl`、`.turtle` 等 rdflib 可解析格式。文件名建议以领域名开头，例如 `wine_my_model.owl`。

## 3. CQ2Term

### 输入目录

传统脚本使用如下目录结构：

```text
CQ2Term/
├── 00_gold_standard/<domain>/
├── 01_predictions/<model_name>/<domain>_terms.json
├── 03_evaluation_results/
├── 04_summary/
├── competency_question/
└── scripts/
```

领域标识为 `wine`、`awo`、`odrl`、`water`、`vgo`、`swo`。预测 JSON 应为列表，每个对象对应一个 CQ，包含 `id`、`class` 和 `property` 字段；`class`、`property` 必须是字符串数组，并且必须覆盖该领域任务要求的全部 CQ ID。

### 运行

```bash
cd CQ2Term
python -u scripts/run_all_cq2term.py
```

常用参数：

```bash
python -u scripts/run_all_cq2term.py --models my_model --datasets wine
python -u scripts/run_all_cq2term.py --no_leaderboard
```

主要输出：

```text
03_evaluation_results/<model>/<dataset>/06_cq_terms/
├── eval_cq_terms_result.json
├── cqterm_class_best_matching.csv
├── cqterm_prop_best_matching.csv
├── cqterm_class_trace.csv
├── cqterm_prop_trace.csv
├── cq_coverage.csv
└── term_coverage.csv

04_summary/<model>/<dataset>_report.md
```

也可以直接调用单个领域：

```bash
python scripts/eval_cq_terms.py \
  --gold_cq_to_terms 00_gold_standard/wine/cq_to_terms_wine.json \
  --pred_cq_to_terms 01_predictions/my_model/wine_terms.json \
  --final_threshold 0.6 \
  --save_result_json 03_evaluation_results/my_model/wine/06_cq_terms/eval_cq_terms_result.json \
  --save_report_md 04_summary/my_model/wine_report.md
```

## 4. CQ2Onto

### 输入目录

```text
CQ2Onto/
├── 00_gold_standard/<domain>/
├── 01_predictions/<mode>/<model_name>/ontology/<dataset>_*.owl
├── 02_atomic_axioms/
├── 03_evaluation_results/
├── 04_summary/
├── competency_question/
├── prompts/
└── scripts/
```

`ClassProperty` 和 `PropertyCharacteristics` 是下游层的前置步骤。Triple、Axiom、Hierarchy 会读取前两层生成的对齐 CSV；如果跳过前两层，后续层无法正确评测。

### 运行

```bash
cd CQ2Onto
python -u scripts/run_all_evaluation_agent_datasets.py
```

可以限制模式、层级或关闭排行榜刷新：

```bash
python -u scripts/run_all_evaluation_agent_datasets.py --modes mymodel
python -u scripts/run_all_evaluation_agent_datasets.py --layers concept,property
python -u scripts/run_all_evaluation_agent_datasets.py --layers axioms --no_leaderboard
```

五个主要目标按以下顺序执行：类、属性、三元组、TBox 公理、层级闭包。Atomic TBox 是从预测本体抽取的中间产物，为公理评测提供输入。

单领域运行时只放入一个预测文件即可，其余领域会显示 `SKIP`。不同模式、模型或配置会写入各自的结果目录，不会覆盖已有结果。

## 5. 查看金标准

- CQ2Term：`CQ2Term/00_gold_standard/<domain>/cq_to_terms_<domain>.json` 保存每个 CQ 的金标准类和属性；`term_to_cqs_<domain>.json` 保存反向映射。
- CQ2Onto：`CQ2Onto/00_gold_standard/<domain>/ontology/sub_<domain>.owl` 是 CQ 对齐的金标准本体；`axioms/<domain>_axiom_gold.json` 保存带 CQ 来源标记的 TBox 公理。
- `sub_<domain>_atomic_tbox.{json,txt,xlsx}` 是参考用 Atomic TBox 文件，评测脚本实际使用 JSON 公理金标准。

## 6. 指标如何读取

每个层都会输出 TP、FP、FN、Precision、Recall、F1；F1 是最容易比较的摘要指标，但建议同时观察精确率和召回率。

CQ2Onto 还区分两种统计口径：

- **Global**：包含所有预测项，反映完整生成结果。
- **AC（Alignment-Conditioned）**：只在词项已经对齐后比较结构，帮助区分词汇错误和结构错误。

CQ 覆盖率包含“至少一项”“平均”“完整”三种口径。Axiom 和 Hierarchy 会分别给出严格结果和推理闭包结果；两者差值可说明 HermiT 推理挽回了多少 CQ 覆盖。

## 7. 报告和排行榜

优先阅读 `04_summary/` 下的 `report.md`。结构化结果在 `03_evaluation_results/` 中，包含对齐轨迹、最佳匹配、覆盖率、Triple TXT、Atomic TBox JSON/TXT/XLSX 等文件。

成功的原有 runner 会刷新 `leaderboard/`。如果只想做本地评测而不刷新排行榜，可使用 `--no_leaderboard`。

本地 Web 评测台会把每次 run 的所有输入、日志、`report.md` 和结构化产物独立保存到 `data/runs/<run-id>/`，并在运行记录页面支持筛选、趋势和 2～4 条记录的对比。
