import asyncio
# import utils
from .utils.graphv3 import build_graph

from .utils.mcp_tools import initialize_tools
from langchain_core.messages import HumanMessage, SystemMessage

MCP_URL = "http://localhost:3927/tableau-mcp"


def create_initial_state(mcp_tool_descriptions, langchain_tools):
    return {
        "intent": "",
        "conversation_history": [
            SystemMessage(
                content="You are a Tableau MCP assistant with access to tools."
            )
        ],
        "input": "",
        "context_window_size": 5,
        "follow_up": False,
        "enhanced_input": "",
        "context_anchors": [],
        "need_tools": True,
        "implementation_plan": "",
        "mcp_tool_descriptions": mcp_tool_descriptions,
        "langchain_tools": langchain_tools,
        "current_tool_calls": {},
        "most_recent_tool_calls": {},
        "most_recent_tool_calls_life_span": 10,
        "tool_execution_history": [],
        "tool_calls": [],
        "tool_call_under_str_resolution": [],
        "final_response": "",
        "evaluation": {"Verdict": "", "Feedback": ""},
        "verdict": "",
        "feedback": {},
        "replanning_attempts": 0,
        "max_replanning_attempts": 3,
        "output": "",
        "string_validation": "",
        "string_resolution_tool_calls": [],
        "filtered_metadata": [],
        "datasource_metadata": {},
        "retry_attempts_for_str_resolution": 0,
        "identified_datasource": "",
            "list_datasources_tool_call_id": "",
            "get_datasource_metadata_tool_call_id": "",
            "current_datasource": {},
            "rejected_datasources": []
    }


async def main():
    # 🔹 Initialize MCP tools ONCE
    mcp_tool_descriptions, langchain_tools = await initialize_tools(MCP_URL)

    graph = build_graph()

    # 🔹 Create fresh state
    state = create_initial_state(
        mcp_tool_descriptions,
        langchain_tools
    )

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        # ✅ Reset retry attempts for each new user input
        state["replanning_attempts"] = 0
        state["input"] = user_input

        # Run LangGraph with human message as delta
        result = await graph.ainvoke(state)


        # print("\nEnhanced Input:", result.get("enhanced_input", ""))
        # print("Context Anchors:", result.get("context_anchors", []))
        # print("current_tool_calls:", result.get("current_tool_calls", {}))
        # print("\nImplementation Plan:", result.get("implementation_plan", ""))
        assistant_reply = result.get("output", "")
        print("\nAssistant:", assistant_reply)


        # Update full state from graph result
        state.update(result)


if __name__ == "__main__":
    asyncio.run(main())
