"""
LangGraph Map-Reduce 示例：规划 → 并行检索 → 汇总对比。

运行方式（在 openinterview 目录下）:
  python3 -m venv .venv && source .venv/bin/activate   # 可选：创建并激活虚拟环境
  pip install -r requirements.txt
  python LangGraph-demo.py
"""
from typing import List, TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langgraph.types import Send


class AgentState(TypedDict):
    question: str
    sub_queries: List[str]
    # auto-merge parallel results
    retrieved_contexts: Annotated[list, operator.add]
    final_comparison: str
    retry_count: int
    quality_check: bool


def checker(state: AgentState):
    retry_count = state.get("retry_count", 0)
    # 质量达标，或重试已达 3 次则不再循环，避免 GraphRecursionError
    is_good_enough = len(state["retrieved_contexts"]) > 10 or retry_count >= 3
    return {
        "quality_check": is_good_enough,
        "retry_count": retry_count + 1,
    }


def route_after_check(state: AgentState):
    # 使用 path_map 时路由函数应返回 map 的 key（True/False），不是 list[Send]
    return state["quality_check"]


# def retry(state: AgentState):
#     return {"retry_count": state["retry_count"] + 1, "quality_check": False}


def query_planner(state: AgentState):
    question = state["question"]
    # 伪实现：真实场景可用 LLM/规则从 question 解析出实体，这里写死演示
    entities = ["公司A", "公司B"]
    sub_queries = [f"针对「{question}」检索关于 {e} 的财务数据" for e in entities]
    return {"sub_queries": sub_queries}


def parallel_retriever(state: dict):  # ✅ receives {"sub_query": "..."}
    sub_query = state["sub_query"]
    context = f"来自向量库的关于【{sub_query}】的局部片段..."
    return {"retrieved_contexts": [context]}


def comparison_summarizer(state: AgentState):
    contexts = "\n".join(state["retrieved_contexts"])
    prompt = f"基于以下背景信息进行深度对比分析：\n{contexts}"
    return {"final_comparison": "这是 A 和 B 的多维度对比报告..."}


def route_to_retrievers(state: AgentState):  # ✅ Send a dict, not a raw string
    return [Send("parallel_retriever", {"sub_query": q}) for q in state["sub_queries"]]


# ========== 图的组装：谁先跑、谁接谁 ==========
#
#   ┌─────────┐
#   │  START  │
#   └────┬────┘
#        │ set_entry_point
#        ▼
#   ┌─────────┐  route_to_retrievers 返回 [Send(...), Send(...)]
#   │ planner │ ──────────────────────────────────────────────┐
#   └─────────┘                                                │
#        │                                                     │ 动态分支（并行）
#        │  add_conditional_edges                              ▼
#        │                                            ┌────────────────────┐
#        │                                            │ parallel_retriever │ (可能多份)
#        │                                            └────────┬───────────┘
#        │                                                     │ add_edge
#        │                                                     ▼
#        │                                            ┌─────────────┐
#        │                                            │ summarizer  │
#        │                                            └──────┬──────┘
#        │                                                   │ add_edge
#        │                                                   ▼
#        │                                              ┌─────┐
#        └──────────────────────────────────────────────│ END │
#                                                        └─────┘
#
builder = StateGraph(AgentState)   # 全局状态长什么样（字段 + 类型）
builder.add_node("planner", query_planner)                      # 节点名 -> 实际函数
builder.add_node("parallel_retriever", parallel_retriever)
builder.add_node("summarizer", comparison_summarizer)
builder.add_node("checker", checker)

# 入口：从 planner 开始
builder.set_entry_point("planner")
# planner 之后：由路由函数决定去谁那儿（这里去多份 parallel_retriever）
builder.add_conditional_edges("planner", route_to_retrievers)
# 每个 retriever 跑完后都到 summarizer
builder.add_edge("parallel_retriever", "summarizer")
# summarizer 跑完就到 checker
builder.add_edge("summarizer", "checker")
builder.add_conditional_edges(
    "checker",
    route_after_check,
    {
        True: END,
        False: "summarizer"
    }
)    # checker 之后：由路由函数决定去谁那儿（这里去 summarizer 或 retry）

# 把“图”编译成可执行的 graph
graph = builder.compile()


if __name__ == "__main__":
    initial = {"question": "对比公司A和公司B的财务表现", "retry_count": 0}
    result = graph.invoke(initial)
    print("=== 最终状态 ===")
    print("question:", result.get("question"))
    print("sub_queries:", result.get("sub_queries"))
    print("retrieved_contexts:", result.get("retrieved_contexts"))
    print("final_comparison:", result.get("final_comparison"))
