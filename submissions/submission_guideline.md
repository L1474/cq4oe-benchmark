# CQ4OE 提交说明（示例提交）

这里是一份完整且有效的示例提交。结果文件来自基准中的
`cqbycq` / `deepseek-v4-pro` 基线，因此可以作为你准备提交内容时的格式和目录参考。
权威元数据位于 `metadata.yml`。

## 文件格式

**CQ2Onto**：`CQ2Onto/<domain>/<domain>_ontology.owl`。每个领域一个完整 OWL 本体，接受 rdflib 可以解析的序列化格式（`.owl`、`.rdf`、`.xml`、`.ttl`、`.turtle`）。

**CQ2Term**：`CQ2Term/<domain>/<domain>_cq2terms_terms.json`。这是一个 JSON 列表，每个能力问题对应一个对象，格式如下：

```json
{
  "id": "CQ1",
  "value": "Which animal eats which other animal?",
  "class": ["Animal"],
  "property": ["eats"]
}
```

请保留该领域 CQ 文件中的 `id` 和 `value`，只填写你的方法预测出的 `class` 和 `property`。字段名必须使用单数形式（`class`、`property`），这是评测器读取的格式。

## 任务与领域

本示例覆盖六个领域（`awo`、`odrl`、`swo`、`vgo`、`water`、`wine`）的两个任务。允许提交部分结果：只需包含实际运行过的任务 / 领域目录，并在 `metadata.yml` 中声明。

## 方法说明

CQbyCQ 方法逐个处理能力问题，生成每个 CQ 的本体片段，再把片段合并为每个领域的一个本体；同一个基础模型也用于 CQ2Term 任务的词项预测。提交自己的结果时，请把这一节替换为你的模型、提示词和生成流程说明。

## 复现信息

`code/` 保存验证者可以用来重新生成 `CQ2Onto/` 和 `CQ2Term/` 结果的源代码。准确的环境配置和运行命令写在 `metadata.yml` 的 `code:` 区块中。挑战赛 CI 不会执行 `code/`；CI 直接评测已提交的结果文件，保留代码是为了复核和复现。
