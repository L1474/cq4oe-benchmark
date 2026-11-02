"""中文界面文案映射。

数据库和 API 继续使用稳定的英文枚举值；模板只在展示层调用这些函数。
"""

TASK_LABELS = {
    "cq2term": "CQ2Term",
    "cq2onto": "CQ2Onto",
}

STATUS_LABELS = {
    "draft": "草稿",
    "queued": "排队中",
    "running": "运行中",
    "completed": "已完成",
    "partial": "部分完成",
    "failed": "失败",
    "pending": "待处理",
    "blocked": "已阻塞",
    "started": "已开始",
}

DIMENSION_LABELS = {
    "term": "词项",
    "class": "类",
    "property": "属性",
    "property_characteristic": "属性特征",
    "class_hierarchy": "类层级",
    "property_hierarchy": "属性层级",
    "ClassProperty": "类与属性",
    "PropertyCharacteristics": "属性特征",
    "Triple": "三元组",
    "Axiom": "公理",
    "HierarchyClosure": "层级闭包",
    "CQCoverage": "CQ 覆盖率",
    "class_property": "类与属性",
    "property_characteristics": "属性特征",
    "triple": "三元组",
    "axiom": "公理",
    "hierarchy": "层级闭包",
    "cq_coverage": "CQ 覆盖率",
}

METRIC_LABELS = {
    "any_cq_coverage": "至少一项 CQ 覆盖率",
    "fully_cq_coverage": "完全 CQ 覆盖率",
    "average_cq_coverage": "平均 CQ 覆盖率",
    "hard_match": "硬匹配",
    "sequence_match": "序列匹配",
    "levenshtein_distance": "Levenshtein 距离",
    "jaro_winkler_distance": "Jaro-Winkler 距离",
    "semantic_cosine_similarity": "语义余弦相似度",
    "aggregated_top3": "Top-3 聚合",
    "precision": "精确率",
    "recall": "召回率",
    "f1": "F1",
    "embedding_diagnostic": "嵌入诊断",
    "at_least_one_coverage": "至少一项覆盖率",
    "mean_coverage": "平均覆盖率",
    "full_coverage": "完整覆盖率",
    "closure_rescue_coverage": "闭包补救覆盖率",
    "coverage": "覆盖率",
}

LAYER_LABELS = {
    "terms": "全领域词项",
    "aggregated": "综合对齐",
    "characteristics": "属性特征",
    "cq_coverage": "CQ 覆盖",
    "closure": "推理闭包",
    "layer2_semantic": "第 2 层（语义诊断）",
    "layer4_global": "第 4 层（全局）",
    "layer1": "第 1 层",
    "layer2": "第 2 层",
    "layer3": "第 3 层",
    "layer4": "第 4 层",
    "layer5": "第 5 层",
    "layer6": "第 6 层",
    "layer1_exact": "第 1 层（精确）",
    "layer2_pair": "第 2 层（配对）",
    "layer3_strict": "第 3 层（严格）",
    "layer4_atomic": "第 4 层（原子）",
    "layer5_closure": "第 5 层（闭包）",
    "layer6_cq": "第 6 层（CQ）",
}

SCOPE_LABELS = {
    "combined": "类与属性合并",
    "class_only": "仅类",
    "property_only": "仅属性",
    "aggregate": "综合",
    "semantic": "语义诊断",
    "strict": "严格匹配",
    "per_cq_mean": "逐题平均",
    "global": "整体",
    "per_cq": "按 CQ",
    "per_item": "按条目",
    "alignment_conditioned": "在对齐条件下",
    "gold_vocabulary": "金标准词汇",
    "predicted_vocabulary": "预测词汇",
    "closure": "推理闭包",
}

UNIT_LABELS = {
    "ratio": "比例",
    "count": "数量",
    "distance": "距离",
}

STAGE_LABELS = {
    "evaluate": "评测",
    "class": "类评测",
    "property": "属性评测",
    "triple": "三元组评测",
    "atomic": "原子 TBox 提取",
    "axiom": "公理评测",
    "hierarchy": "层级闭包评测",
    "predict": "生成预测",
    "stream": "流式执行",
}

EVENT_LABELS = {
    "stage": "阶段事件",
    "started": "已开始",
    "item_failed": "条目失败",
    "interrupted": "已中断",
    "legacy_failure": "历史失败记录",
}


def _lookup(value, mapping):
    if value is None:
        return ""
    text = str(value)
    return mapping.get(text, text)


def task_label(value):
    return _lookup(value, TASK_LABELS)


def status_label(value):
    return _lookup(value, STATUS_LABELS)


def dimension_label(value):
    return _lookup(value, DIMENSION_LABELS)


def metric_label(value):
    return _lookup(value, METRIC_LABELS)


def layer_label(value):
    return _lookup(value, LAYER_LABELS)


def scope_label(value):
    if isinstance(value, str) and value.startswith("cq:"):
        return f"{value[3:]}（逐题）"
    return _lookup(value, SCOPE_LABELS)


def unit_label(value):
    return _lookup(value, UNIT_LABELS)


def stage_label(value):
    return _lookup(value, STAGE_LABELS)


def event_label(value):
    return _lookup(value, EVENT_LABELS)


def metric_description(metric):
    name = metric.get("metric_name", "")
    scope = metric.get("scope", "")
    context = f"{dimension_label(metric.get('dimension'))}，{layer_label(metric.get('layer'))}，{scope_label(scope)}"
    meanings = {
        "precision": "预测为正确的项中真正匹配金标准的比例（TP / (TP + FP)）。",
        "recall": "金标准项中被预测覆盖的比例（TP / (TP + FN)）。",
        "f1": "精确率与召回率的调和平均；0 到 1，越高越好。",
        "coverage": "该 CQ 所需词项被预测覆盖的比例。",
        "any_cq_coverage": "至少有一项所需公理被覆盖的 CQ 比例。",
        "average_cq_coverage": "每个 CQ 的公理覆盖比例取平均。",
        "fully_cq_coverage": "全部所需公理均被覆盖的 CQ 比例。",
    }
    return f"{context}：{meanings.get(name, '查看原始报告了解该指标的计算方式。')}"
