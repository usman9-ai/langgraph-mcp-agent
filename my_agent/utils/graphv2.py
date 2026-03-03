from langgraph.graph import StateGraph
from .state import State
from .nodesv2 import *
from langgraph.prebuilt import ToolNode
from langgraph.graph import END



def build_graph(return_builder=False):
    builder = StateGraph(State)

    builder.add_node("is_follow_or_not", is_follow_or_not)
    builder.add_node("context_window_manager", manage_conversation_history)
    builder.add_node("intent_classifier", intent_classifier)
    builder.add_node("other_domain_message_handler", other_domain_message_handler)
    builder.add_node("greeting_handler", greeting_handler)
    builder.add_node("enhance_new_prompt", enhance_new_prompt)
    builder.add_node("enhance_follow_up_prompt", enhance_follow_up_prompt)
    builder.add_node("context_anchors_node", context_anchors_node)
    builder.add_node("need_tools_node", need_tools_node)
    builder.add_node("final_response_node", final_response_node)
    builder.add_node("plan_implementation_node", plan_implementation)
    builder.add_node("update_most_recent_tool_calls", update_most_recent_tool_calls)

    builder.add_edge("context_window_manager", "is_follow_or_not")
    # ✅ FOLLOW UP CHECK FIRST
    def check_follow_up(state):

        if state.get("follow_up") == "True":
            return "follow_up"
        else:
            return "not_follow_up"

    builder.add_conditional_edges(
        source="is_follow_or_not",
        path=check_follow_up,
        path_map={
            "follow_up": "enhance_follow_up_prompt",
            "not_follow_up": "intent_classifier"
        }
    )

    # ✅ INTENT ROUTING
    def intent_path(state):

        if state.get("intent") == "Greeting":
            return "greet"
        elif state.get("intent") == "Other":
            return "other"
        elif state.get("intent") == "Tableau Related":
             return "tableau_related"
        

    builder.add_conditional_edges(
        source="intent_classifier",
        path=intent_path,
        path_map={
            "greet": "greeting_handler",
            "other": "other_domain_message_handler",
            "tableau_related": "enhance_new_prompt"
        }
    )

    builder.add_edge("enhance_new_prompt", "context_anchors_node")
    builder.add_edge("enhance_follow_up_prompt", "context_anchors_node")

    builder.add_edge("context_anchors_node", "need_tools_node")


        # ✅ FOLLOW UP CHECK FIRST
    def check_tools_requirements(state):

        if state.get("need_tools") == "True":
            return "need_tools"
        else:
            return "not_need_tools"


    
    builder.add_conditional_edges(
        source="need_tools_node",
        path=check_tools_requirements,
        path_map={
            "need_tools": "plan_implementation_node",
            "not_need_tools": "final_response_node"
        }
    )

    # builder.add_node("check_current_tool_calls", populate_current_tool_calls)
    builder.add_edge("plan_implementation_node", "update_most_recent_tool_calls")

    builder.add_node("agent", autonomous_executor)
    builder.add_node("identical_tool_calls", check_identical_tool_call)
    builder.add_node("cached_tool_results", check_cached_tool_result)
    builder.add_node("router", router_node)
    builder.add_edge("update_most_recent_tool_calls", "agent")
    builder.add_node("list-datasources", list_datasources_tool)
    builder.add_node("identify_relevant_datasource", identify_relevant_datasource)
    builder.add_node("get-datasource-metadata", get_datasource_metadata_tool)
    builder.add_node("filter_metadata", filter_metadata_node)
    builder.add_node("query-datasource", query_datasource_tool)
    builder.add_node("tool_calls", execute_tool, async_node=True)
    builder.add_node("final_response_after_tool_call_node", final_response_after_tool_call_node)
    builder.add_node("Evaluator", evaluator_node)
    builder.add_node("feedback", feedback_node)


    def check_tool_calls(state: State):
        if state.get("tool_calls"):
            return "has_tool_calls"
        else:
            return "no_tool_calls"

    def check_identical_tool_calls_result(state: State):
        if state.get("identical_tool_call", None) == True:
            return "identical_tool_call"
        else:
            return "check_cached_results"

    def check_cached_tool_results(state: State):
        if state.get("cached_result_flag", None) == True:
            return "cached_result_available"
        else:
            return "no_cached_result"

    # If tool calls exist → go to tools
    def route_tool_call(state: State):
        tool_name = state["next_tool_name"]
        if tool_name == "list-datasources":
            return "list-datasources"
        elif tool_name == "get-datasource-metadata":
            return "get-datasource-metadata"
        elif tool_name == 'query-datasource':
             return "query-datasource"
        elif tool_name != "":
            return "other_tool_calls"


    builder.add_conditional_edges(
        source="agent",
        path=check_tool_calls,
        path_map={
            "has_tool_calls": "identical_tool_calls",
            "no_tool_calls": "Evaluator"
        }
    )

    builder.add_conditional_edges(
        source="identical_tool_calls",
        path=check_identical_tool_calls_result,
        path_map={
            "identical_tool_call": "Evaluator",  # ✅ FIX 3: Jump to Evaluator instead of agent
            "check_cached_results": "cached_tool_results"
        }
    )

    builder.add_conditional_edges(
        source="cached_tool_results",
        path=check_cached_tool_results,
        path_map={
            "cached_result_available": "agent",
            "no_cached_result": "router"
        }
    )


    builder.add_conditional_edges(
        source="router",
        path=route_tool_call,
        path_map={
            "list-datasources": "list-datasources",
            "get-datasource-metadata": "get-datasource-metadata",
            "query-datasource": "query-datasource",
                "other_tool_calls": "tool_calls"        }
    )

    # builder.add_conditional_edges(
    #     source="agent",
    #     path=should_continue,
    #     path_map={
    #         "list-datasources": "list-datasources",
    #         "get-datasource-metadata": "get-datasource-metadata",
    #         "query-datasource": "query-datasource",
    #             "other_tool_calls": "tool_calls",
    #             "no_tool_calls": "final_response_after_tool_call_node"
    #     }
    # )


    def check_query_datasource_response(state: State):
        string_validation = state.get('string_validation','')
        if string_validation == "pass":
            return "Pass"
        elif string_validation == "fail":
            return "Fail"
        return "Pass"

    # After tool execution → go back to agent
    def check_list_datasources_status(state: State):
        list_datasources_status = state.get('list_datasources_tool_call_status', '')
        if list_datasources_status == "success":
            return "Success"
        elif list_datasources_status == "error":
            return "Error"
        else:
            return "Success"




    builder.add_conditional_edges(
        source="list-datasources",
        path=check_list_datasources_status,
        path_map={
            "Success": "identify_relevant_datasource",
            "Error": "agent"
         }
    )


    builder.add_edge("identify_relevant_datasource", "agent")

        # After tool execution → go back to agent
    def check_metadata_status(state: State):
        metadata_status = state.get('get_datasource_metadata_tool_call_status', '')
        if metadata_status == "success":
            return "Success"
        elif metadata_status == "error":
            return "Error"
        else:
            return "Success"


    builder.add_conditional_edges(
        source="get-datasource-metadata",
        path=check_metadata_status,
        path_map={
            "Success": "filter_metadata",
            "Error": "agent"
         }
    )

    builder.add_edge("filter_metadata", "agent")


    builder.add_node("string_validation_node", string_validation_node)
    # builder.add_conditional_edges(
    #     source="query-datasource",
    #     path=check_query_datasource_response,
    #     path_map={
    #         "Pass": "agent",
    #         "Fail": "string_validation_node"
    #      }
    # )

    builder.add_edge("query-datasource", "agent")



    builder.add_node("QDS For STR Resolution", query_ds)


    def check_str_resolution_tool_calls(state: State):
        if state.get("tool_call_under_str_resolution"):
            return "has_tool_calls"
        else:
            return "no_tool_calls"
    
    builder.add_conditional_edges(
        source="string_validation_node",
        path=check_str_resolution_tool_calls,
        path_map={
            "has_tool_calls": "QDS For STR Resolution",
            "no_tool_calls": "Evaluator"
        }
    )

    builder.add_edge("QDS For STR Resolution", "string_validation_node")









    # builder.add_edge("query-datasource", "agent")
    builder.add_edge("tool_calls", "agent")
    builder.add_edge("Evaluator", "feedback")

    def check_feedback(state: State):
        verdict = state.get("verdict", "")
        retry_attempts = state.get("replanning_attempts", 0)
        max_retries = state.get("max_replanning_attempts", 3)
        print(f"Feedback Check - Verdict: {verdict}, Retry Attempts: {retry_attempts}, Max Retries: {max_retries}")

        if verdict == 'pass':
            print("Evaluation passed. Proceeding to final response.")
            return "pass"

        # ✅ FIX 4: Reduce max retries and add safeguard
        if verdict == "fail" and retry_attempts < max_retries:
            if retry_attempts >= 2:  # After 2 failures, give up
                print("Too many failures (2+ retries). Ending process.")
                return "Failed Many Times"
            
            print(f"Evaluation failed. Attempting retry {retry_attempts + 1} of {max_retries}.")
            return "Retry"  
        
        print("Evaluation failed and max retries reached. Ending process.")
        return "Failed Many Times"

    
    builder.add_conditional_edges(
        source="feedback",
        path=check_feedback,
        path_map={
            "pass": "final_response_after_tool_call_node",
            "Retry": "plan_implementation_node",
            "Failed Many Times": END}
    )


    # ✅ CORRECT ENTRY POINT
    builder.set_entry_point("context_window_manager")

    if return_builder:
        return builder

    return builder.compile()
