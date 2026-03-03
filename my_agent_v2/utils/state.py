from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from typing import TypedDict
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class State(TypedDict):
    intent: str
    context_window_size: int
    conversation_history: Annotated[list[BaseMessage], add_messages]
    input: str
    follow_up: bool
    enhanced_input: str
    context_anchors: list[str]
    need_tools: bool
    tool_call_counts: dict
    implementation_plan: str
    mcp_tool_descriptions: list
    langchain_tools: dict
    current_tool_calls: dict
    most_recent_tool_calls: dict
    most_recent_tool_calls_life_span: int
    all_datasources: list[dict]
    current_datasource: dict
    rejected_datasources: list[dict]
    tool_execution_history: Annotated[list[BaseMessage], add_messages]
    datasource_metadata: dict
    filtered_metadata: list
    next_tool_name: str
    cached_result_flag: bool
    identical_tool_call: bool
    tool_calls: list[dict]
    tool_call_under_str_resolution: list[dict]
    final_response: str
    evaluation: dict
    verdict: str
    feedback: dict
    replanning_attempts: int
    max_replanning_attempts: int
    output: str
    string_validation: str
    string_resolution_tool_calls: Annotated[list[BaseMessage], add_messages]
    retry_attempts_for_str_resolution: int
    identified_datasource: str

    list_datasources_tool_call_id: str
    get_datasource_metadata_tool_call_id: str
    need_summarization: bool


