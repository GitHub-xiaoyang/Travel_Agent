# -*- coding: utf-8 -*-
"""
Mermaid 流程图生成器（重构版）

新流程拓扑：
  用户输入 → 意图解析 → 任务+参数提取 → 工具调用(并行) → 资源汇总 → 模板分析 → 输出结果
"""

import os
import json
from typing import Optional

from travel_agent.nodes.constants import (
    NODE_INTENT, NODE_TASK_PARAM, NODE_TOOL_CALLS,
    NODE_RESOURCE_AGG, NODE_TEMPLATE_ANALYSIS, NODE_OUTPUT,
    NODE_FALLBACK, NODE_DISPLAY_NAMES,
)


def generate_mermaid() -> str:
    """
    生成旅行 Agent Graph 的 Mermaid 流程图文本（新流程 7 阶段串行拓扑）

    Returns:
        Mermaid flowchart 语法字符串
    """
    node_labels = NODE_DISPLAY_NAMES

    nodes = [
        "flowchart TD",
        '    START(["用户输入"])',
        '    END(["输出结果"])',
        '    FALLBACK["异常兜底"]',
        "",
        # Step 1: 意图解析
        '    subgraph S1["Step 1: 意图解析"]',
        f'        INTENT["{node_labels[NODE_INTENT]}"]',
        "    end",
        "",
        # Step 2: 任务+参数提取
        '    subgraph S2["Step 2: 任务+参数提取"]',
        f'        TASK_PARAM["{node_labels[NODE_TASK_PARAM]}"]',
        "    end",
        "",
        # Step 3: 工具调用（并行）
        '    subgraph S3["Step 3: 工具调用（并行）"]',
        f'        TOOL_CALLS["{node_labels[NODE_TOOL_CALLS]}"]',
        "    end",
        "",
        # Step 4: 资源汇总
        '    subgraph S4["Step 4: 资源汇总"]',
        f'        RESOURCE_AGG["{node_labels[NODE_RESOURCE_AGG]}"]',
        "    end",
        "",
        # Step 5: 模板分析
        '    subgraph S5["Step 5: 模板分析"]',
        f'        TEMPLATE_ANALYSIS["{node_labels[NODE_TEMPLATE_ANALYSIS]}"]',
        "    end",
        "",
        # Step 6: 输出渲染
        '    subgraph S6["Step 6: 输出渲染"]',
        f'        OUTPUT["{node_labels[NODE_OUTPUT]}"]',
        "    end",
        "",
    ]

    edges = [
        "    START --> INTENT",
        "",
        "    %% Step 1→2",
        "    INTENT --> TASK_PARAM",
        '    INTENT -.->|"异常"| FALLBACK',
        "",
        "    %% Step 2→3",
        "    TASK_PARAM --> TOOL_CALLS",
        '    TASK_PARAM -.->|"异常"| FALLBACK',
        "",
        "    %% Step 3→4",
        "    TOOL_CALLS --> RESOURCE_AGG",
        '    TOOL_CALLS -.->|"异常"| FALLBACK',
        "",
        "    %% Step 4→5",
        "    RESOURCE_AGG --> TEMPLATE_ANALYSIS",
        '    RESOURCE_AGG -.->|"异常"| FALLBACK',
        "",
        "    %% Step 5→6",
        "    TEMPLATE_ANALYSIS --> OUTPUT",
        '    TEMPLATE_ANALYSIS -.->|"异常"| FALLBACK',
        "",
        "    %% Step 6→END",
        "    OUTPUT --> END",
        '    OUTPUT -.->|"异常"| FALLBACK',
        "",
        "    %% 异常处理",
        "    FALLBACK --> END",
        "",
    ]

    styles = [
        "    %% 节点样式",
        "    style START fill:#F5F5F5,stroke:#D9D9D9,color:#000000",
        "    style END fill:#F5F5F5,stroke:#D9D9D9,color:#000000",
        "    style INTENT fill:#4C6FFF,stroke:#3A5BD4,color:#000000",
        "    style TASK_PARAM fill:#FA8C16,stroke:#D46B08,color:#000000",
        "    style TOOL_CALLS fill:#52C41A,stroke:#3F9A14,color:#000000",
        "    style RESOURCE_AGG fill:#13C2C2,stroke:#08979C,color:#000000",
        "    style TEMPLATE_ANALYSIS fill:#722ED1,stroke:#531DAB,color:#000000",
        "    style OUTPUT fill:#EB2F96,stroke:#C41D7F,color:#000000",
        "    style FALLBACK fill:#FF4D4F,stroke:#CF1322,color:#000000",
        "",
        "    %% 子图背景色",
        "    style S1 fill:#E8EDFF,stroke:#4C6FFF,color:#000000",
        "    style S2 fill:#FFF4E5,stroke:#FA8C16,color:#000000",
        "    style S3 fill:#E8F7E3,stroke:#52C41A,color:#000000",
        "    style S4 fill:#E6FFFB,stroke:#13C2C2,color:#000000",
        "    style S5 fill:#F3E8FF,stroke:#722ED1,color:#000000",
        "    style S6 fill:#FFF0F6,stroke:#EB2F96,color:#000000",
    ]

    return "\n".join(nodes + edges + styles)


def generate_mermaid_with_data(
    intent_node: str = "",
    task_info: str = "",
    template_type: str = "",
    has_error: bool = False,
    error_node: str = "",
) -> str:
    """生成带实时数据的 Mermaid 流程图"""
    base = generate_mermaid()
    annotations = []
    if intent_node:
        annotations.append(f'    INTENT["{NODE_DISPLAY_NAMES.get(NODE_INTENT, "意图解析")}\\n{intent_node}"]')
    if task_info:
        annotations.append(f'    TASK_PARAM["{NODE_DISPLAY_NAMES.get(NODE_TASK_PARAM, "任务+参数")}\\n{task_info}"]')
    if template_type:
        annotations.append(f'    TEMPLATE_ANALYSIS["{NODE_DISPLAY_NAMES.get(NODE_TEMPLATE_ANALYSIS, "模板分析")}\\n{template_type}"]')
    if has_error and error_node:
        error_label = NODE_DISPLAY_NAMES.get(error_node, error_node)
        annotations.append(f'    FALLBACK["异常兜底\\n错误节点: {error_label}"]')
    if annotations:
        base += "\n\n    %% 实时状态标注"
        base += "\n".join(annotations)
    return base


def save_mermaid_html(
    output_path: Optional[str] = None,
    title: str = "Travel Agent Graph Debug",
) -> str:
    """生成包含 Mermaid 流程图的 HTML 文件"""
    mermaid_code = generate_mermaid()
    if output_path is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, "graph_debug.html")

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
        .mermaid {{ display: flex; justify-content: center; padding: 20px; background: #fafafa; border-radius: 8px; border: 1px solid #e8e8e8; }}
        .legend {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 14px; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 {title}</h1>
        <div class="mermaid">{mermaid_code}</div>
        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background:#4C6FFF"></div>意图解析</div>
            <div class="legend-item"><div class="legend-color" style="background:#FA8C16"></div>任务+参数提取</div>
            <div class="legend-item"><div class="legend-color" style="background:#52C41A"></div>工具调用</div>
            <div class="legend-item"><div class="legend-color" style="background:#13C2C2"></div>资源汇总</div>
            <div class="legend-item"><div class="legend-color" style="background:#722ED1"></div>模板分析</div>
            <div class="legend-item"><div class="legend-color" style="background:#EB2F96"></div>输出渲染</div>
            <div class="legend-item"><div class="legend-color" style="background:#FF4D4F"></div>异常兜底</div>
        </div>
    </div>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'base', flowchart: {{ htmlLabels: true, curve: 'basis' }} }});
    </script>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


def get_graph_summary() -> dict:
    """获取 Graph 结构摘要"""
    return {
        "topology": "7阶段串行",
        "flow": [
            "START → INTENT (意图解析: 规则+TF-IDF+LLM)",
            "INTENT → TASK_PARAM (任务+参数提取)",
            "TASK_PARAM → TOOL_CALLS (工具调用, 并行)",
            "TOOL_CALLS → RESOURCE_AGG (资源汇总)",
            "RESOURCE_AGG → TEMPLATE_ANALYSIS (模板分析)",
            "TEMPLATE_ANALYSIS → OUTPUT (输出渲染)",
            "OUTPUT → END",
            "任意节点异常 → FALLBACK → END",
        ],
        "templates": {
            "query_weather": "weather_template",
            "query_traffic": "traffic_template",
            "query_scenic": "scenic_template",
            "query_food": "food_template",
            "query_hotel": "hotel_template",
            "query_luggage": "luggage_template",
            "query_fun": "fun_template",
            "full_plan": "plan_template",
            "multi_task": "combined_template",
        },
    }
