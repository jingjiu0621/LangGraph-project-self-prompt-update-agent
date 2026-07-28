# Graph 模块概览

## 1. 简述

本项目实现了一个**自优化 Prompt Agent** 的 LangGraph 全链路管道，包含 12 个核心 Phase，覆盖从用户输入到进化的完整闭环：

| Phase | 节点 | 职责 |
|---|---|---|
| **Phase 1** | [event_recorder](nodes.py) | 记录交互事件、生成 `trace_id` + `conversation_id` |
| **Phase 2** | [context_retriever](nodes.py) | 混合检索：用户画像、项目知识、历史记忆 |
| **Phase 3** | [prompt_compiler](nodes.py) | 编译结构化个性化 Prompt 包 |
| **Phase 4** | [agent_executor](nodes.py) | 执行任务：推理 → 工具调用 → 产出 |
| **Phase 5** | [output_formatter](nodes.py) | 格式化最终用户输出 |
| **Phase 6** | [feedback_collector](nodes.py) | 收集/判断用户反馈（accept / correction） |
| **Phase 7** | [extraction_pipeline](nodes.py) | 抽取任务元数据、记忆候选、图谱关系候选 |
| **Phase 8** | [memory_updater](nodes.py) | 更新长期记忆、合并冲突、执行衰退 |
| **Phase 9** | [graph_updater](nodes.py) | 更新用户知识图谱节点和边（归一化 + 清理） |
| **Phase 10** | [evaluator](nodes.py) | AI judge 评分（completion / style / relevance） |
| **Phase 11** | [evolution_checker](nodes.py) | 判断是否触发 Prompt/Skill 进化提案 |
| **Phase 12** | [reliability_gate_checker](nodes.py) | ReliabilityGate 安全与质量门禁检查 |

**12 个 Phase** 分为三段：前置流水线（P1-P6）、记忆与图谱（P7-P9）、评估与进化治理（P10-P12）。

**2 个条件路由**（[edges.py](edges.py)）控制管道分支：

| 路由 | 决策逻辑 |
|---|---|
| `feedback_quality_router` | correction → 回 Phase 4 修订（最多 3 次）；accept → 进入抽取 |
| `evolution_router` | eval 结果存在 → Phase 10 进化检查；否则 END |

**状态定义**（[state.py](state.py)）：`GraphState` TypedDict 承载 26+ 字段，覆盖全链路输入输出，含 `ReliabilityGateResult` 子类型。

## 2. Mermaid

```mermaid
flowchart TD
    START([START]) --> P1["Phase 1<br/>event_recorder"]
    P1 --> P2["Phase 2<br/>context_retriever"]
    P2 --> P3["Phase 3<br/>prompt_compiler"]
    P3 --> P4["Phase 4<br/>agent_executor"]
    P4 --> P5["Phase 5<br/>output_formatter"]

    P5 --> P6["Phase 6<br/>feedback_collector"]

    P6 -->|"correction<br/>(rev<3)"| P4
    P6 -->|"accept"| P7["Phase 7<br/>extraction_pipeline"]

    P7 --> P8["Phase 8<br/>memory_updater"]
    P8 --> P9["Phase 9<br/>graph_updater"]
    P9 --> P10["Phase 10<br/>evaluator"]

    P10 -->|"eval exists"| P11["Phase 11<br/>evolution_checker"]
    P10 -->|"no eval"| END([END])

    P11 --> P12["Phase 12<br/>reliability_gate_checker"]
    P12 --> END

    style P1 fill:#E0F2FE,stroke:#0284C7
    style P2 fill:#E0F2FE,stroke:#0284C7
    style P3 fill:#E0F2FE,stroke:#0284C7
    style P4 fill:#E0F2FE,stroke:#0284C7
    style P5 fill:#E0F2FE,stroke:#0284C7
    style P6 fill:#FCE7F3,stroke:#DB2777
    style P7 fill:#D1FAE5,stroke:#059669
    style P8 fill:#D1FAE5,stroke:#059669
    style P9 fill:#D1FAE5,stroke:#059669
    style P10 fill:#FEF3C7,stroke:#D97706
    style P11 fill:#FEF3C7,stroke:#D97706
    style P12 fill:#F1F5F9,stroke:#94A3B8
```

## 3. 流程图

```
                    ┌──────────────────────────────────────┐
                    │         User Input                   │
                    └──────────────┬───────────────────────┘
                                   ▼
              ┌─────────────────────────────────────────┐
     Phase 1  │  event_recorder                         │
              │  记录用户输入，生成 trace_id              │
              └──────────────────┬──────────────────────┘
                                 ▼
              ┌─────────────────────────────────────────┐
     Phase 2  │  context_retriever                      │
              │  RAG 检索：记忆 / 画像 / 项目知识        │
              └──────────────────┬──────────────────────┘
                                 ▼
              ┌─────────────────────────────────────────┐
     Phase 3  │  prompt_compiler                        │
              │  编译结构化个性化 Prompt 包              │
              └──────────────────┬──────────────────────┘
                                 ▼
              ┌─────────────────────────────────────────┐
     Phase 4  │  agent_executor                         │
              │  推理 → 工具调用 → 执行结果              │
              └──────────────────┬──────────────────────┘
                                 ▼
              ┌─────────────────────────────────────────┐
     Phase 5  │  output_formatter                       │
              │  格式化最终输出                          │
              └──────────────────┬──────────────────────┘
                                 │
                                 ▼
              ┌─────────────────────────────────────────┐
     Phase 6  │  feedback_collector                     │
              │  判断反馈类型                            │
              └──────────────────┬──────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │  feedback_quality_router             │
              ├────────────────┬─────────────────────┤
              │  correction    │     accept          │
              │  (rev < 3)     │                     │
              └───────┬────────┴──────────┬──────────┘
                      │                   │
                      ▼                   ▼
              ┌──────────────┐  ┌─────────────────────────┐
              │  Phase 4     │  │  Phase 7                │
              │  agent_exec  │  │  extraction_pipeline    │
              │  (重新执行)   │  │  抽取元数据/记忆/关系     │
              └──────────────┘  └──────────┬──────────────┘
                                           ▼
                                ┌─────────────────────────┐
                       Phase 8  │  memory_updater          │
                                │  合并记忆 / 冲突/ 衰退    │
                                └──────────┬──────────────┘
                                           ▼
                                ┌──────────────────────────────┐
                       Phase 9  │  graph_updater               │
                                │  归一化节点/边 → 更新图谱     │
                                └──────────────┬───────────────┘
                                               ▼
                                ┌──────────────────────────────┐
                       Phase 10 │  evaluator                   │
                                │  AI judge 评分               │
                                └──────────┬───────────────────┘
                                           │
                                ┌──────────┴──────────┐
                                │  evolution_router   │
                                ├─────────┬───────────┤
                                │ eval 存在│ 无 eval  │
                                └────┬────┴─────┬─────┘
                                     │          │
                                     ▼          ▼
                           ┌────────────┐  ┌──────────┐
                  Phase 11 │ evolution  │  │   END    │
                           │ 进化检查    │  │          │
                           └─────┬──────┘  └──────────┘
                                 │
                                 ▼
                  ┌───────────────────────────┐
         Phase 12 │  reliability_gate_checker │
                  │  scope / 敏感信息 /注入    │
                  │  / 回归 / SLO 门禁检查     │
                  └─────────────┬─────────────┘
                                │
                                ▼
                             ┌──────┐
                             │ END  │
                             └──────┘
```

## 4. 设计决策说明

### 4.1 为什么 Phase 5 → Phase 6 是普通边而非条件边？

当前设计中每次输出后必然收集反馈。`acceptance_router` 曾是一个单分支条件边，现简化为普通边。如需跳过反馈（例如低风险确定性任务），在 `main.py` 中将 `add_edge` 改为 `add_conditional_edges` 即可。

### 4.2 为什么 evolution_router 不再设阈值？

`evolution_router` 仅检查 `eval_results` 是否存在，将"是否值得提进化提案"的阈值判断交给 `evolution_checker` 节点。这样避免了两处用不同阈值（3.5 vs 3.0）的重复逻辑。

### 4.3 ReliabilityGate 做了什么？

`reliability_gate_checker` 实现了 plan.md §17 的发布门禁要求。MVP 阶段仅做 scope 检查，后续需集成敏感信息扫描（detect-secrets）、Prompt Injection 检测（rebuff/llm-guard）、回归评测 runner 和 SLO error budget 计数器。

## 文件索引

| 文件 | 说明 |
|---|---|
| [state.py](state.py) | `GraphState` + `ReliabilityGateResult` — 全链路状态定义 |
| [nodes.py](nodes.py) | 12 个节点函数（Phase 1-12） |
| [edges.py](edges.py) | 2 个条件路由（feedback_quality / evolution） |
| [\_\_init\_\_.py](__init__.py) | 统一导出接口 |
| [overview.md](overview.md) | 本文 — 当前图流程文档 |
