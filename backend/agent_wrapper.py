import asyncio
from my_agent_v2.utils.graph import build_graph
from my_agent_v2.utils.mcp_tools import initialize_tools

MCP_URL = "http://localhost:3927/tableau-mcp"

graph = None
initial_state = None

async def init_agent():
    global graph, initial_state

    mcp_tool_descriptions, langchain_tools = await initialize_tools(MCP_URL)
    graph = build_graph()

    from my_agent_v2.agent import create_initial_state
    initial_state = create_initial_state(
        mcp_tool_descriptions,
        langchain_tools
    )


async def run_agent_stream(user_input: str):
    if graph is None or initial_state is None:
        raise RuntimeError("Agent is not initialized")

    state = initial_state.copy()
    state["input"] = user_input
    state["replanning_attempts"] = 0

    emitted_plan = False
    emitted_tools = set()
    emitted_tool_results = set()
    pending_tool_calls_by_name = {}
    pending_tool_call_ids = []
    emitted_final = False
    terminal_final_nodes = {
        "greeting_handler",
        "other_domain_message_handler",
        "final_response_node",
        "final_response_after_tool_call_node",
        "Handle_Incomplete_Requests",
    }

    try:
        async for event in graph.astream(state, stream_mode="updates"):
            if emitted_final:
                # Once the user-facing final answer is emitted, suppress any late
                # tool-call/tool-result noise from trailing graph nodes.
                break
            # LangGraph updates come as: {"node_name": {"state_key": "value"}}
            updates = []
            if isinstance(event, dict):
                for node_name, value in event.items():
                    if isinstance(value, dict):
                        updates.append((node_name, value))
            elif isinstance(event, list):
                updates = [("unknown", item) for item in event if isinstance(item, dict)]

            for node_name, update in updates:
                if emitted_final:
                    break
                # -------------------------
                # 1) Planning Phase
                # -------------------------
                if not emitted_plan and update.get("implementation_plan"):
                    emitted_plan = True
                    yield {
                        "type": "planning",
                        "title": "Planning & Reasoning",
                        "content": update["implementation_plan"]
                    }

                # -------------------------
                # 2) Tool Calls
                # -------------------------
                tool_calls = update.get("tool_calls") or []
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue

                    call_id = tool_call.get("id")
                    tool_name = tool_call.get("name")
                    if call_id and call_id in emitted_tools:
                        continue
                    if call_id:
                        emitted_tools.add(call_id)
                        pending_tool_call_ids.append(call_id)
                    if tool_name and call_id:
                        pending_tool_calls_by_name.setdefault(tool_name, []).append(call_id)

                    yield {
                        "type": "tool_call",
                        "tool_id": call_id,
                        "tool_name": tool_name,
                        "query": tool_call.get("args", {})
                    }
                    yield {
                        "type": "tool_status",
                        "tool_id": call_id,
                        "tool_name": tool_name,
                        "status": "started"
                    }

                # -------------------------
                # 3) Tool Results
                # -------------------------
                history = update.get("tool_execution_history") or []
                if isinstance(history, list):
                    for item in history:
                        tool_id = getattr(item, "tool_call_id", None)
                        tool_name = getattr(item, "tool_name", None)
                        content = getattr(item, "content", item)

                        # Emit only actual tool outputs (skip system/ai narrative messages)
                        if not tool_id and not tool_name:
                            continue

                        if (not tool_id or tool_id not in emitted_tools) and tool_name:
                            pending_ids = pending_tool_calls_by_name.get(tool_name, [])
                            if pending_ids:
                                tool_id = pending_ids.pop(0)

                        # If id is still unresolved, force FIFO mapping using global pending queue
                        if not tool_id or tool_id not in emitted_tools:
                            if pending_tool_call_ids:
                                tool_id = pending_tool_call_ids.pop(0)

                        # Remove resolved id from queues to keep FIFO state clean
                        if tool_id in pending_tool_call_ids:
                            pending_tool_call_ids = [cid for cid in pending_tool_call_ids if cid != tool_id]
                        if tool_name and tool_name in pending_tool_calls_by_name:
                            pending_tool_calls_by_name[tool_name] = [
                                cid for cid in pending_tool_calls_by_name[tool_name] if cid != tool_id
                            ]

                        result_key = (str(tool_id), str(content))
                        if result_key in emitted_tool_results:
                            continue
                        emitted_tool_results.add(result_key)

                        yield {
                            "type": "tool_status",
                            "tool_id": tool_id,
                            "tool_name": tool_name,
                            "status": "completed"
                        }
                        yield {
                            "type": "tool_result",
                            "tool_id": tool_id,
                            "tool_name": tool_name,
                            "source_node": node_name,
                            "result": str(content)[:3000]
                        }

                # -------------------------
                # 4) Final Response
                # -------------------------
                if node_name in terminal_final_nodes and update.get("output"):
                    emitted_final = True
                    yield {
                        "type": "final",
                        "source_node": node_name,
                        "content": update["output"]
                    }
                    break

        if not emitted_final:
            result = await graph.ainvoke(state)
            final_output = result.get("output", "")
            if final_output:
                yield {
                    "type": "final",
                    "source_node": "ainvoke_fallback",
                    "content": final_output
                }
            else:
                yield {
                    "type": "error",
                    "content": "Agent completed without producing a response."
                }

    except Exception as exc:
        yield {
            "type": "error",
            "content": f"Agent execution failed: {str(exc)}"
        }
