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
    return _lookup(value, SCOPE_LABELS)


def unit_label(value):
    return _lookup(value, UNIT_LABELS)


def stage_label(value):
    return _lookup(value, STAGE_LABELS)


def event_label(value):
    return _lookup(value, EVENT_LABELS)
