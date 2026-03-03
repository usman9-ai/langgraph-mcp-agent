from .state import State
from .llm import llm, slightly_creative_llm, creative_llm
import json
import re
import uuid
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from fastmcp import Client
import copy
from langgraph.types import Overwrite
import ast


mcp_client = Client("http://localhost:3927/tableau-mcp")
def intent_classifier(state: State):
    """Determine if the user message is Tableau-related, a greeting, or other domain."""

    msg = slightly_creative_llm.invoke(f"""
        You are an intent classifier for a banking data analytics assistant powered by Tableau.

        CONTEXT: Your Tableau server contains banking data including:
        - Branch information (codes, locations, names)
        - Customer data and accounts
        - Transaction records
        - Financial metrics and KPIs
        - Employee information
        - Sales and performance data
        - Any other business/banking datasets

        CLASSIFICATION RULES:

        1. "Tableau Related" → Classify here if the query asks for:
        - Specific data points (e.g., branch codes, account numbers, customer info)
        - Analytics or metrics (e.g., sales totals, performance trends)
        - Reports or dashboards (e.g., "show me the sales dashboard")
        - Business questions answerable with data (e.g., "which branch has highest revenue?")
        - Filtering or searching existing data (e.g., "branches in Karachi")
        
        EXAMPLES OF TABLEAU RELATED:
        ✓ "What is the branch code of Virtual Hub Clifton Karachi?"
        ✓ "Show me sales by region"
        ✓ "How many customers do we have?"
        ✓ "What are this month's KPIs?"
        ✓ "Find all transactions over 100k"

        2. "Greeting" → Classify here if the user is:
        - Saying hello, hi, hey
        - Making polite courtesies ("thank you", "please")
        - Just greeting, not asking for anything
        
        EXAMPLES:
        ✓ "Hello"
        ✓ "Hi there!"
        ✓ "Thanks!"

        3. "Other" → Classify here ONLY if completely unrelated to data/banking/Tableau:
        - Philosophy, history, science trivia
        - Personal advice (cooking, relationships)
        - General knowledge unrelated to business
        
        EXAMPLES:
        ✓ "What's the capital of France?"
        ✓ "How do I bake a cake?"

        IMPORTANT: When in doubt, classify as "Tableau Related" because:
        - It's better to attempt answering a business question and fail gracefully
        - The downstream tools will determine if data exists
        - Banking questions are almost always data-answerable

        Respond ONLY in valid JSON format with no additional text:
        {{"intent": "Tableau Related" | "Greeting" | "Other"}}

        User Message: {state['input']}
        """)

    parsed = json.loads(msg.content)
    return {"intent": parsed["intent"]}

def other_domain_message_handler(state: State):
        msg = creative_llm.invoke(f"""You are a Tableau assistant. 
                             The user has asked a question that is not related to tableau data analytics.
                             You must not entertain this request and politely inform the user that
                             you can only assist with tableau related queries.

                             User Message: {state['input']}
        """)
        reply = msg.content
        return {"output": reply, "conversation_history": [AIMessage(content=reply)]}

def greeting_handler(state: State):
        msg = creative_llm.invoke(f"""You are a Tableau assistant. 
                             The user has greeted you.
                             You must respond with a polite greeting message and inform the user that
                             you can assist with tableau related queries.

                             User Message: {state['input']}
        """)
        reply = msg.content
        return {"output": reply,"conversation_history":[AIMessage(content=reply)] }

def is_follow_or_not(state: State):
    """
    Determines if user's message is a follow-up question requiring previous context
    or an independent new question.
    """
    conversation_history = state.get("conversation_history", [])
    user_msg = state.get('input', "")
    
    
    msg = llm.invoke(f"""
        You are a strict conversation continuity classifier.

        Your job is to decide whether the CURRENT USER MESSAGE truly depends on the previous message for meaning.

        RECENT CONVERSATION:
        {conversation_history}

        CURRENT USER MESSAGE:
        "{user_msg}"

        IMPORTANT PRINCIPLE:
        A message is FOLLOW-UP ONLY if it CANNOT be fully understood without the previous message.

        A message is INDEPENDENT if it is complete and self-contained, even if it is topically related.

        ----------------------------------
        FOLLOW-UP if:
        1. It uses pronouns or missing context:
        - "and for that branch?"
        - "what about him?"
        - "now for kemari"
        - "same for 2025"
        2. It modifies previous filters:
        - "for DHA instead"
        - "change to monthly"
        3. It adds metrics without repeating subject:
        - "and transaction count?"
        4. It refines failed query:
        - "try with clifton karachi branch"

        ----------------------------------
        INDEPENDENT if:
        1. It clearly specifies full subject + metric.
        Example:
        - "What is the performance report of Asad Ali?"
        (Even if Asad Ali appeared earlier — this is complete.)
        2. It switches subject entity type:
        - From branch customers → employee salaries
        - From salary list → performance report
        3. It does NOT rely on previous filters.
        4. It contains full context in one sentence.

        ----------------------------------
        CRITICAL RULE:
        If the current message introduces a NEW PRIMARY ENTITY
        (e.g., from branch → employee),
        classify as INDEPENDENT unless it uses pronouns or missing info.

        ----------------------------------
        Respond ONLY in this exact JSON format. No Markdown, No explanation, No extra text:
        {{"follow_up": "True"}}
        OR
        {{"follow_up": "False"}}
""")
    response_text = msg.content.strip()
    print("Raw follow-up classification response:", response_text)
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        try:
            response_text = response_text.strip("```json").strip("```").strip()
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            print("Error decoding JSON:", response_text)
            return {
                "follow_up": "False",
                "current_tool_calls": {},
                "tool_execution_history": Overwrite([]),
                "tool_calls": [],
                "feedback": {},
                "current_datasource": {},
                "rejected_datasources": []
            }


    return {
        "follow_up": parsed["follow_up"], 
        "current_tool_calls": {},
        "tool_execution_history": Overwrite([]),
        "tool_calls": [],
        "feedback": {}, 
        "current_datasource": {},
        "rejected_datasources": []
        }




def manage_conversation_history(state: State):
        conversation_history = state.get("conversation_history", [])
        if len(conversation_history) > 21:
            messages_to_be_summarized = conversation_history[:11]
            conversation_history = conversation_history[11:]

            msg = llm.invoke(f"""You are a helpful assistant that summarizes conversation history
                                 for a tableau assistant agent. Briefly summarize what user has been asking and 
                                 what the assistant has been responding in the conversation history. 
                                 The summary should be concise and capture the main points and key entities of the conversation.

                                 Conversation History: {messages_to_be_summarized}
            """)
            summary = msg.content.strip()
            conversation_history = [SystemMessage(content=f"Summary of previous conversation: {summary}")] + conversation_history
        return {"conversation_history": conversation_history}


def enhance_new_prompt(state: State):
    """
    Enhance a new independent question (not a follow-up).
    Clarifies intent and makes the query more specific without adding external information.
    """
    user_msg = state.get('input', "")
    print("Original user message for enhancement:", user_msg)
    
    msg = slightly_creative_llm.invoke(f"""You are a Tableau data analytics assistant with access to Tableau MCP tools.

        USER MESSAGE: "{user_msg}"

        TASK: Enhance this message to be clear, specific, and actionable for query execution.

        ENHANCEMENT GUIDELINES:

        1. **Clarify Intent:**
        - If user asks "what is X", clarify they want to retrieve/search for X
        - If user asks "show me", clarify they want to see/display data
        - Make the action explicit (search, retrieve, calculate, compare, etc.)

        2. **Expand Abbreviations & Vague Terms:**
        - "avg" → "average"
        - "trans" → "transaction"
        - "feb" → "february" 
        - "breakdown" → "break down by" or "group by"
        - Be specific about what "breakdown" means (monthly, daily, by category, etc.)



        EXAMPLES:

        Original: "avg transaction amount clifton branch feb 2025"
        Enhanced: "what is the average transaction amount for clifton branch in february 2025"

        Original: "branch code of clifton"
        Enhanced: "search for the branch code of branch named clifton"


        CRITICAL RULES:
        - Keep all original information (branch names, dates, metrics)
        - Make the intent and structure clear
        - Expand abbreviations for clarity
        - DO NOT add details not in the original message
        - DO NOT ask follow-up questions
        - Return ONLY the enhanced query as a single clear sentence
    """)
    enhanced_input = msg.content.strip()
    print("Enhanced new prompt:", enhanced_input)  
    return {"enhanced_input": enhanced_input,
        "conversation_history": [HumanMessage(content=enhanced_input)]
        }

def enhance_follow_up_prompt(state: State):
        """
        Enhance follow-up questions by carrying forward context and detecting changes.
        Uses conversation_history to accumulate metrics, filters, and aggregation levels.
        """
        print("Enhancing follow-up prompt:")  
        conversation_history = state.get("conversation_history", [])
        current_message = state['input']
        is_follow_up = state.get("follow_up", False)

        print("Conversation history for enhancement:", conversation_history)
        print("Current message for enhancement:", current_message)
        print("Is follow-up:", is_follow_up)



        # Build enhancement prompt
        prompt = f"""You are enhancing a follow-up query intelligently.

        CONVERSATION HISTORY:
        {conversation_history}

        CURRENT USER MESSAGE:
        "{current_message}"

        Your goal:
        Enhance ONLY what the user clearly expects.
        Do NOT blindly carry forward all previous filters.

        ----------------------------------

        STEP 1: Identify the PRIMARY ENTITY in the current message.
        Examples:
        - Branch
        - Employee
        - Customer
        - Metric request
        - Time filter

        STEP 2: Determine user intent category:
        A) Same entity, adding/modifying metrics
        B) Same entity, changing filters
        C) Refining failed search
        D) New entity focus (e.g., now asking about one employee)

        ----------------------------------

        RETENTION RULES:

        1. If SAME ENTITY → retain previous filters unless explicitly replaced.

        2. If NEW ENTITY TYPE (e.g., from branch-level query → specific employee):
        - Retain ONLY the entity identifier if user referenced partially.
        - DROP unrelated filters (branch, salary range, etc.)
        - Do NOT merge unrelated metrics.

        3. If user mentions specific metric:
        - Include only that metric.
        - Do not add extra metrics unless explicitly requested.

        4. If user gives partial name (e.g., "Asad"):
        - Resolve to full name from previous result.
        - Do NOT carry previous numeric filters.

        5. Default safety:
        When unsure, RETAIN LESS context, not more.

        ----------------------------------

        Return ONLY the enhanced query as a single sentence.
        No JSON. No explanation.
        """

        msg = llm.invoke(prompt)
        enhanced_input = msg.content.strip()
        print("Enhanced follow-up query:", enhanced_input)
        import time
        time.sleep(30)  # Small delay to ensure logs are readable
        return {
            "enhanced_input": enhanced_input,
            "conversation_history": [HumanMessage(content=enhanced_input)]
        }



def context_anchors_node(state: State):
    """
    Extract context anchors (key entities, metrics, filters, dimensions) from enhanced prompt.
    - For FOLLOW-UP: Update existing anchors with new values or add new anchors
    - For NEW question: Replace all anchors
    """
    
    enhanced_input = state.get("enhanced_input", "")
    previous_anchors = state.get("context_anchors", [])
    is_follow_up = state.get("follow_up") == "True"
    
    msg = llm.invoke(f"""You are extracting context anchors from a Tableau data query.

        ENHANCED USER QUERY:
        "{enhanced_input}"

        {'Previous context anchors:' if is_follow_up else 'This is a new question.'}
        {json.dumps(previous_anchors, indent=2) if is_follow_up else ''}

        Examples:

        Query: "average transaction amount for clifton branch in february 2025"
        Response:
        [
        {{"field": "metric", "value": "average transaction amount"}},
        {{"field": "branch", "value": "clifton"}},
        {{"field": "date_filter", "value": "february 2025"}}
        ]


        Please respond with a JSON array of objects containing "field" and "value". Include all relevant context. No explanation, No Markdown formatting is needed.

        Context Anchors:
        """
        )

    # print("Raw context anchors response:", msg.content)
    try:
        new_anchors = json.loads(msg.content.strip())
        
        # Ensure it's a list of dicts
        if not isinstance(new_anchors, list):
            new_anchors = []
        
        # Normalize structure
        new_anchors = [
            {"field": a.get("field"), "value": a.get("value")} 
            for a in new_anchors 
            if isinstance(a, dict) and a.get("field")
        ]
        
    except json.JSONDecodeError:
        new_anchors = []
    
    # Merge logic based on follow-up status
    if is_follow_up and previous_anchors:
        merged_anchors = merge_context_anchors(previous_anchors, new_anchors)
    else:
        # New question: replace all anchors
        merged_anchors = new_anchors
    
    return {"context_anchors": merged_anchors}


def merge_context_anchors(previous: list, new: list) -> list:
    """
    Intelligently merge previous and new context anchors for follow-up questions.
    
    Rules:
    1. If a field exists in both, UPDATE with new value (e.g., branch: clifton → DHA)
    2. If a field only in new, ADD it (e.g., new metric added)
    3. If a field only in previous and not in new, KEEP it (e.g., date filter unchanged)
    
    Special handling for metrics: accumulate multiple metrics
    """
    
    # Group anchors by field
    previous_dict = {}
    for anchor in previous:
        field = anchor.get("field")
        value = anchor.get("value")
        
        if field == "metric":
            # Metrics can be multiple, store as list
            if field not in previous_dict:
                previous_dict[field] = []
            previous_dict[field].append(value)
        else:
            # Single-value fields
            previous_dict[field] = value
    
    # Process new anchors
    new_dict = {}
    for anchor in new:
        field = anchor.get("field")
        value = anchor.get("value")
        
        if field == "metric":
            if field not in new_dict:
                new_dict[field] = []
            new_dict[field].append(value)
        else:
            new_dict[field] = value
    
    # Merge logic
    merged = {}
    
    # For metrics: accumulate (union of previous and new)
    if "metric" in previous_dict or "metric" in new_dict:
        prev_metrics = previous_dict.get("metric", [])
        new_metrics = new_dict.get("metric", [])
        # Combine and deduplicate
        all_metrics = list(set(prev_metrics + new_metrics))
        merged["metric"] = all_metrics
    
    # For other fields: new values override previous, keep unchanged
    all_fields = set(previous_dict.keys()) | set(new_dict.keys())
    all_fields.discard("metric")  # Already handled
    
    for field in all_fields:
        if field in new_dict:
            # New value provided, use it (UPDATE)
            merged[field] = new_dict[field]
        elif field in previous_dict:
            # No new value, keep previous (KEEP)
            merged[field] = previous_dict[field]
    
    # Convert back to list format
    result = []
    
    # Add metrics
    if "metric" in merged:
        for metric in merged["metric"]:
            result.append({"field": "metric", "value": metric})
    
    # Add other fields
    for field, value in merged.items():
        if field != "metric":
            result.append({"field": field, "value": value})
    
    return result


def need_tools_node(state: State):
    """
    Determine if the current user message requires using tools, querying Tableau server,
    or fetching new data, versus just explanation/reformatting.
    """

    enhanced_input = state.get("enhanced_input", "")
    conversation_history = state.get("conversation_history", [])

    msg = slightly_creative_llm.invoke(f"""
        You are a Tableau MCP assistant agent with full access to Tableau server and
        tools to communicate with it.

        Your task:
        Analyze the user's current request and the conversation history. Decide whether
        fulfilling the request requires:

        1. Communicating with Tableau server or using tools to fetch/update data (respond "True")
        2. Or, if the request is purely about explanation, reformatting, or working
           with data already available from previous conversation (respond "False")
        3. If the users request is about enhancing the previous response and implies that user 
        is again asking for the same data but with some adjustments like different filters or metrics, 
        you should respond "True" because it implies that user is asking for new data from tableau server with adjustments.

        Respond ONLY in this JSON format and nothing else:
        {{"need_tools": "True"}}  or  {{"need_tools": "False"}}

        Conversation history: {conversation_history}
        User's Enhanced Input: {enhanced_input}
    """)


    cleaned = msg.content.strip()

    try:
        parsed = json.loads(cleaned)
        need_tools = parsed.get("need_tools", "False")
    except json.JSONDecodeError as e:
        need_tools = "False"

    # print("Determined need_tools:", need_tools)
    return {"need_tools": need_tools}


def final_response_node(state: State):
    """
    Generate the final response to the user using:
    - conversation_history
    - enhanced_input
    - context_anchors
    - optionally tools (if need_tools=True)
    """

    conversation_history = state.get("conversation_history", [])
    enhanced_input = state.get("enhanced_input", "")
    context_anchors = state.get("context_anchors", [])


    msg = creative_llm.invoke(f"""
        You are a helpful Tableau assistant.

        Based on the conversation so far and the user's latest request, generate
        a concise and accurate response.

        Inputs you can use:
        1. Conversation history:
        {conversation_history}

        2. Enhanced user input:
        {enhanced_input}


        Instructions:
        - Respond only with the message text, no JSON or extra formatting.
    """)

    assistant_reply = msg.content.strip()



    return {"output": assistant_reply, "conversation_history": [AIMessage(content=assistant_reply)]}


def plan_implementation(state: State):
    tool_execution_history = state.get("tool_execution_history", [])
    print("Planning implementation. Tool execution history so far:", tool_execution_history)
    import time
    time.sleep(10)  # Simulate some processing time
    """
    Generate an implementation plan if tools are needed.
    This node would be invoked after need_tools_node determines that tools are required.
    It should create a step-by-step plan to fulfill the user's request using available tools.
    """
    if state.get("need_tools") == "True":
        # conversation_history = state.get("conversation_history", [])
        enhanced_input = state.get("enhanced_input", "")
        # context_anchors = state.get("context_anchors", [])
        mcp_tool_descriptions = state.get("mcp_tool_descriptions", [])

        msg = llm.invoke(f"""
        You are a Tableau MCP planning agent operating in a banking analytics environment.

        Your task is to create a precise, step-by-step implementation plan using ONLY the provided tools to fulfill the user's request.

        User Request:
        {enhanced_input}

        Available Tools:
        {mcp_tool_descriptions}

        Feedback on previous plan (if any):
        {state.get("feedback", "")}


        ==============================
        BANKING ANALYTICAL INTELLIGENCE
        ==============================

        GENERAL PRINCIPLE:
        Think like a BI Engineer preparing analysis for CEO / senior management.
        Be precise, structured, and grain-aware.


        ---------------------------------
        1. DEFAULT TIME GRAIN RULE
        ---------------------------------
        - Default analytical grain is HOUR.
        - All time-based aggregations must first be reasoned at hour level unless explicitly requested otherwise.
        - Never casually aggregate across mixed grains.


        ---------------------------------
        2. BRANCH vs DIGITAL LOGIC
        ---------------------------------

        Branch Banking:
        - Transactions occur only during working hours (typically 09:00–18:00).
        - Distinct hour count must reflect only active working hours.

        Digital Banking:
        - Operates 24 hours.
        - Distinct hour count may include full 24 hours.

        Always reason about which context applies.


        ---------------------------------
        3. AVERAGE CALCULATION RULE (CRITICAL)
        ---------------------------------

        NEVER directly use AVG for transaction metrics.

        If user asks for "average":
            a) Group by HOUR.
            b) Sum metric per hour.
            c) Compute:
            Average = (Total of hourly sums) / (Number of distinct hours).

        If user specifies a specific hour (e.g., 9 AM):
            - Filter hour first.
            - Aggregate across requested date range.
            - Divide by number of distinct days in that range.

        If user asks for multi-day / monthly average:
            - Keep grain at HOUR.
            - Aggregate hourly totals across entire period.
            - Divide by distinct hours in that full period.


        ---------------------------------
        4. MULTI-DAY / MONTH / WEEK LOGIC
        ---------------------------------

        If user asks for:
        - 3 days
        - 1 week
        - 1 month
        - Specific weekday
        - Week of month
        - Same period comparison

        Then:
        - Apply time filters first.
        - Maintain hour-level grouping unless explicitly told otherwise.
        - Then perform aggregation.


        ---------------------------------
        5. DIMENSIONAL FILTER LOGIC
        ---------------------------------

        If user specifies:
        - Branch
        - Region
        - Transaction type
        - Channel
        - Weekday
        - Month
        - Week of month

        Apply filters BEFORE aggregation.

        Never aggregate first and filter later.


        ---------------------------------
        6. EXECUTIVE / CEO LEVEL QUERY HANDLING
        ---------------------------------

        The user may ask high-level performance questions.

        Handle these categories carefully:

        A. Trend Analysis:
        - Group by appropriate time hierarchy (day/week/month).
        - Compare sequential periods.
        - Calculate change or percentage if required.

        B. Comparison Queries:
        - Group by compared dimension (e.g., branch vs branch).
        - Aggregate metrics separately.
        - Maintain consistent grain.

        C. Ranking Queries:
        - Group by entity.
        - Aggregate metric.
        - Sort appropriately.
        - Apply limit if required (Top/Bottom).

        D. Ratio / KPI Queries:
        - Identify numerator and denominator clearly.
        - Perform division AFTER aggregation.
        - Never average pre-calculated percentages.

        E. Peak / Lowest Detection:
        - Group by HOUR (default).
        - Identify max/min aggregated value.


        ---------------------------------
        7. METADATA AWARENESS
        ---------------------------------

        - Do NOT assume field names.
        - If required dimensions or time fields are unclear,
        first step must be metadata retrieval.
        - Do NOT hallucinate fields.


        ---------------------------------
        8. ERROR CORRECTION STRATEGY
        ---------------------------------

        If previous feedback indicates:
        - Wrong field
        - Invalid filter
        - Wrong aggregation

        Then:
        - First step must correct the issue.
        - Re-fetch metadata if necessary.
        - Explicitly mention the correction in the plan.


        ---------------------------------
        9. PLANNING DISCIPLINE
        ---------------------------------

        - Do NOT generate the final query.
        - Do NOT output JSON.
        - Do NOT invent tools.
        - Each step must clearly mention:
            - The exact tool name
            OR
            - "No tool – reasoning step"

        - Explicitly mention:
            - Filters
            - Grouping strategy
            - Aggregation logic
            - Any sorting or comparison logic


        ==============================
        OUTPUT FORMAT
        ==============================

        - Produce ONLY a numbered step-by-step implementation plan.
        - No explanations outside the plan.
        - No JSON.
        - No extra formatting.
        """)
        implementation_plan = msg.content.strip()
        print("Generated Implementation Plan:", implementation_plan)

        return {"implementation_plan": implementation_plan}


def update_most_recent_tool_calls(state: State):
    most_recent_tool_calls = state.get("most_recent_tool_calls", {})
    lifespan = state.get("most_recent_tool_calls_life_span", 5)

    keys_to_delete = []

    for tool_name, data in most_recent_tool_calls.items():
        if data.get("status") == "Completed":
            data["prompts_after_last_call"] = data.get("prompts_after_last_call", 0) + 1

        if data.get("prompts_after_last_call", 0) >= lifespan:
            keys_to_delete.append(tool_name)

    for key in keys_to_delete:
        del most_recent_tool_calls[key]

    return {"most_recent_tool_calls": most_recent_tool_calls}

        




def autonomous_executor(state: dict):
    print("i am in autonomous executor node")
    # read txt file for query rules and guidelines for the agent
    with open("C:\\Langgraph Agent\\my_agent\\utils\\query_rules_v2.txt", "r") as f:
        query_guidelines = f.read()

    

    langchain_tools = state.get("langchain_tools", [])
    llm_with_tools = llm.bind_tools(langchain_tools)

    prompt = f"""
    You are a Tableau MCP executor agent with full access to Tableau Server tools.

    Your mission is to automatically execute the implementation plan using only valid tool calls.

    CRITICAL RULES:

    1. Aggregation & Averages:
    - Never apply AVG to raw measures.
    - Always query SUM grouped by hour for average metrics.
    - Compute final average outside the query: Average = SUM(hourly sums) / COUNT(distinct hours with transactions).
    - Only allowed aggregations: SUM, COUNT, MIN, MAX. Do NOT use other functions.

    2. Hour/Granularity:
    - If implementation plan requires hourly grouping, locate an explicit hour field (examples: "Trxn Hour", "Hour", "Hour of Day") in metadata.
    - Use that field for grouping. NEVER derive hour from a date field if explicit field exists.

    3. Field fidelity:
    - All field names must match metadata exactly (case-sensitive). Do not invent or rename fields.
    - Include all fields required for aggregation, filters, grouping, or derived metrics.
    - Missing fields = critical failure.

    4. Filters & Sample Values:
    - Dates: ISO format YYYY-MM-DD.
    - Datetimes: Tableau-allowed time variable.
    - Strings: Try exact match; if not found, split by space, comma, hyphen and merge results with AND.
    - Numbers: Remove commas, preserve numeric type.
    - Never replace user-provided filters with sample values.

    5. Tool Call Format:
    - The 'query' parameter for 'query-datasource' must be a JSON object, NOT a string.
    - Ensure all arguments are valid according to MCP Query Rules.
    - Validate each aggregation function against allowed list.
    - Validate all filter fields exist in metadata.
    - Validate grouping fields exist and correspond to implementation plan.

    6. Fuzzy Matching:
    - Only apply when exact match fails.
    - Narrow search using other deterministic filters (date, branch, region) before fuzzy matching.
    - Merge fuzzy results with logical AND.

    7. Execution flow:
    - Step through the implementation plan sequentially.
    - Map all metrics, filters, dimensions to metadata accurately.
    - Validate field formats using sample values without replacing actual filter values.
    - After each tool call, check results and decide next step.
    - Retry once on invalid filter/field using correction heuristics.
    - Any other errors → explain in plain language in final output.

    8. Output:
    - After executing the plan, produce a final response to the user that includes:
    - Single human-readable message summarizing:
        - Results
        - Adjustments/retries applied
        - Average metrics computation performed outside query
    - Do NOT return JSON in final output.
    - Do NOT output raw errors.

    USER INPUT:
    {state.get("enhanced_input", "")}

    IMPLEMENTATION PLAN:
    {state.get("implementation_plan", "")}

    TOOL EXECUTION HISTORY:
    {state.get("tool_execution_history", [])}

    MCP QUERY RULES:
    {query_guidelines}
    """
        # Invoke LLM
    msg = llm_with_tools.invoke(prompt)
    
    ai_message = msg.content

    tool_calls = getattr(msg, "tool_calls", [])
    # print("Tool calls extracted from LLM response:", tool_calls)

    # ✅ FIX 1: Only return tool_calls if they actually exist
    if not tool_calls:
        print("[autonomous_executor] No tool calls generated. Returning final response.")
        return {
            "tool_calls": [],
            "tool_execution_history": [msg],
            "output": msg.content,
            "follow_up": False,
            "intent": 'None'
        }

    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        ai_message += f"\n\n[Executing tool: '{tool_name}' with arguments: {tool_args}]"

    # print("AI Message:", ai_message)
    return {
        "tool_calls": tool_calls,
        "tool_execution_history": [msg],
        "output": msg.content,
        "follow_up": False,
        "intent": 'None'
    }


def check_identical_tool_call(state: dict):
    # print( "I am in identical tool call node")
    tool_calls = state.get("tool_calls", [])
    current_tool_calls = state.get("current_tool_calls", {})

    if not tool_calls:
        return {"identical_tool_call": False}

    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    tool_call_id = tool_call.get("id", str(uuid.uuid4()))

    # ✅ FIX 2: Normalize tool arguments for comparison
    def normalize_args(args):
        """Convert args to canonical JSON string for comparison"""
        return json.dumps(args, sort_keys=True, default=str)

    if tool_name in current_tool_calls:
        previous_args = current_tool_calls[tool_name].get("arguments", {})
        previous_status = current_tool_calls[tool_name].get("status", "unknown")
        previous_response = current_tool_calls[tool_name].get("response")

        # ✅ Normalize before comparing
        if normalize_args(previous_args) == normalize_args(tool_args):
            print(f"⚠️ INFINITE LOOP DETECTED for '{tool_name}'.")
            print(f"Same tool with identical arguments already executed.")
            print(f"Previous status: {previous_status}")

            error_msg = (
                f"⚠️ INFINITE LOOP DETECTED for '{tool_name}'.\n"
                f"Same tool with identical arguments already executed.\n"
                f"Previous status: {previous_status}\n"
                f"Previous response: {previous_response}\n"
                f"Adjust your plan to avoid this."
            )
            
            tool_msg = ToolMessage(
                content=error_msg,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
            )

            return {
                "tool_execution_history": [tool_msg],
                "identical_tool_call": True
            }
        return {"identical_tool_call": False}

def check_cached_tool_result(state: dict):
    # print( "I am in cached tool node")

    tool_calls = state.get("tool_calls", [])
    most_recent_tool_calls = state.get("most_recent_tool_calls", {})

    # print("Tool calls to execute:", tool_calls)
    if not tool_calls:
        return {
            "tool_execution_history": [ToolMessage(content="No tool calls detected in response JSON.")],
            "cached_result_flag": False
        }

    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    
    if tool_name not in most_recent_tool_calls:
        return {"cached_result_flag": False}

    previous_args = most_recent_tool_calls[tool_name].get("arguments", {})
    previous_status = most_recent_tool_calls[tool_name].get("status", "")

    if previous_args == tool_args and previous_status == "completed":
        tool_msg = most_recent_tool_calls[tool_name]["response"]

        # Reset prompts counter safely
        most_recent_tool_calls[tool_name]["prompts_after_last_call"] = 0
        # print(f"Using cached result for tool '{tool_name}' with identical arguments. Previous status: {previous_status}")
        # print("="*50)
        # # print(tool_msg, "\n tool args:", tool_args)

        return {
        "most_recent_tool_calls": most_recent_tool_calls,
        "tool_execution_history": [tool_msg],
        "cached_result_flag": True
        }
    return {"cached_result_flag": False}

def router_node(state: dict):
        tool_name = state["tool_calls"][0].get("name", "")
        if tool_name == "list-datasources":
            return {"next_tool_name": "list-datasources"}
        elif tool_name == "get-datasource-metadata":
            return {"next_tool_name": "get-datasource-metadata"}
        elif tool_name == 'query-datasource':
            return {"next_tool_name": "query-datasource"}
        elif tool_name != "":
            return {"next_tool_name": "other_tool_calls"}
        return {"next_tool_name": "no_tool_calls"}


async def call_tool(tool_name, tool_args):

        try:
                async with Client("http://localhost:3927/tableau-mcp") as client:
                        tool_result = await client.call_tool(tool_name, tool_args)

                tool_msg = ToolMessage(
                content=f"Result from tool {tool_name}: {tool_result}",
                tool_name=tool_name,
                tool_call_id=str(uuid.uuid4()),
                )
                return tool_result.content[0].text


        # ==========================================================
        # 4️⃣ Handle Tool Error
        # ==========================================================
        except Exception as e:
                return e


async def query_ds(state:dict):
    print(" I am on query ds node")
    tool_calls = state.get('tool_call_under_str_resolution', '')
    retry_attempts_for_str_resolution = state.get('retry_attempts_for_str_resolution', 0)
    print("tool call: ", tool_calls)

    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    try:
        async with Client("http://localhost:3927/tableau-mcp") as client:
                tool_result = await client.call_tool(tool_name, tool_args)

        tool_msg = ToolMessage(
        content=f"Result from tool {tool_name}: {tool_result}",
        tool_name=tool_name,
        tool_call_id=str(uuid.uuid4()),
        )
        return  {
        "string_resolution_tool_calls": [tool_msg],
        "retry_attempts_for_str_resolution": retry_attempts_for_str_resolution
        }
    except Exception as e:
        tool_msg = ToolMessage(
        content=f"Result from tool {tool_name}: {e}",
        tool_name=tool_name,
        tool_call_id=str(uuid.uuid4()),
        )
        return  {
        "string_resolution_tool_calls": [tool_msg],
        "retry_attempts_for_str_resolution": retry_attempts_for_str_resolution + 1
        }

    

def string_validation_node(state: dict):
    retry_attempts_for_str_resolution = state.get('retry_attempts_for_str_resolution', 0)
    if retry_attempts_for_str_resolution > 3:
        ai_message = f"""After {retry_attempts_for_str_resolution} attempts, the string resolution process has not been successful. 
                            The tool calls made for string resolution and their results are as follows:\n\n"""

        ai_message += """Given the repeated failures in resolving the string issue, it is likely that there is a fundamental 
            mismatch between the user's input and the data available in the datasource. This could be due to various reasons such as 
            incorrect assumptions about the data structure, significant discrepancies in string values, or limitations in the tools 
            being used for resolution. It may be necessary to revisit the user's original request, clarify their intent, and possibly 
            adjust the approach to better align with the actual data and its structure."""



        # a general message for user to state the agnent tried repeatedly to retrieve the result but failed.
        # please check your input and try again with different values or check the datasource for available values.
        output_msg = """
        After multiple attempts, the system was unable to retrieve the results. 
        Please check your input and try again with different values, or verify the available values in the datasource."""

        return {
            "tool_call_under_str_resolution": [],
            "string_resolution_tool_calls": [AIMessage(content=ai_message)],
            "output": output_msg
        }



    user_msg = state.get('enhanced_input', '')
    org_call = state.get('tool_call_under_str_resolution', '')
    tool_call_history = state.get('string_resolution_tool_calls', '')
    filtered_metadata = state.get('filtered_metadata', [])

    # print("User message", user_msg)
    # print(org_call)
    # print(tool_call_history)
    # print(filtered_metadata)



    
    langchain_tools = state.get("langchain_tools", [])
    llm_with_tools = llm.bind_tools(langchain_tools)

    print("I am on string validation node")

    prompt = f"""You are a Tableau master, you are resposible for the successful execution of tableau quries via 
    Tableau MCP Server. You have access to use query-datasource tool and you are provided with tool call arguments and 
    user message that explains what is expected as the output of this query. 
    
    A common issue in quries is string matching. Our Most relaible way to filter results on string type columns is by using 
    MATCH Filter with 'contains' keyword. This can match even the substrings, but problem accurs when there is a small mismatch 
    in the string value in the contains filter. 

    For example, query args use text = 'Clifton Branch', but actual value in datasource is 'Clifton, Karachi'. So query fails!

    Solution: 
    1. Search for each word separatley => 'Clifton Branch' splits into 'Clifton', 'Branch'. 
    2. Execute tool call with each of these candidates
    3. For each execution, save the response and append upcoming responses of next candidates. 
    4. After executing for all cadidates, select the closet match with the original string values i.e, 'Clifton Branch'


    User Intent Understanding:
    1. You must clearly understand what user needs as result.
    2. If he want a filter on a specific string value, For example, user asks for transactional data of branch named as 'ABC XYZ '
       Then you have to create candidates and generate one string value with closet match.
    3. If he want multiple results from string fileds. For example, 'List branch codes of all branches in DHA Lahore', then you will
       match all fields matching with "DHA Lahore"

    Crtitical Instructions:
    1. Do not modify filters on the fields with data types other than STRING.
    2. If multiple STRING fields are there and have some filters, apply this strategy of splitting cadidates on all 
       of them simultaneously. 
    3. If the original query is structured in such a way, that it applies filters on string field and some other fields like 
       INT or DATETIME, etc. But in fields to output, do not include Sting field. You will modify the query, 
       to output only the STRING filed. 

       Example: {{
      "fields": [
        {{
          "fieldCaption": "Br Code"
        }}
      ],
      "filters": [
        {{
          "field": {{
            "fieldCaption": "Branch Name"
          }},
          "filterType": "MATCH",
          "startsWith": "Clifton Karachi",
          "exclude": false
        }}
      ]
    }}

    In this case, You can modify query to output the 'Branch Name'. So you can see all matches 
    against all cadidates.


    4. After recieving all matches, then look for the closet match. 
    5. Substitue that match in the Original query.
    6. After resolving string filters, must execute the original tool call, with resolved string filters.

    User Message:{user_msg}
    Original Query:{org_call}
    Meta Data of fields: {filtered_metadata}
    string_resolution_tool_calls:{tool_call_history}


    If query fails due to invalid field/operator:
        - Re-check datasource metadata.
        - Retry once after correcting field names or operators.
        - If still failing, explain clearly in plain English.

    For other errors:
        - Never show raw JSON errors.
        - Translate technical errors into plain language.
        - Explain what was attempted and why it failed.


    Your output should be a single human-readable message, summarizing:
        - Final results if user request is fulfilled.
        - Explanation of errors or adjustments if retries occurred.
    """

    msg = llm_with_tools.invoke(prompt)
        
    ai_message = msg.content

    tool_calls = getattr(msg, "tool_calls", [])
    # print("Tool calls extracted from LLM response:", tool_calls)

    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        ai_message += f"\n\n[Executing tool: '{tool_name}' with arguments: {tool_args}]"

    # print("AI Message:", ai_message)


    return  {
        "tool_call_under_str_resolution": tool_calls,
        "string_resolution_tool_calls": [AIMessage(content=ai_message)],
        "output": msg.content
        }


async def query_datasource_tool(state: dict):
    print( "I am in query datasource tool node")

    tool_calls = state.get("tool_calls", [])
    print("tool call: ", tool_calls)

    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ], 

            "string_validation": "pass"
        }
    tool_call = tool_calls[0]

    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    tool_call_id = tool_call.get("id")

    # 🔒 ALWAYS COPY STATE STRUCTURES (IMMUTABLE PATTERN)
    current_tool_calls = copy.deepcopy(state.get("current_tool_calls", {}))
    most_recent_tool_calls = copy.deepcopy(state.get("most_recent_tool_calls", {}))

    datasource_id = tool_args.get("datasourceLuid")
    query = tool_args.get("query")
    print("Original Query:", query)
    print("Type of query before parsing:", type(query))

    try:
        async with Client("http://localhost:3927/tableau-mcp") as client:
            tool_result = await client.call_tool(tool_name, tool_args)

        tool_msg = ToolMessage(
        content=tool_result,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        )

        current_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed"
        }

        most_recent_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed",
            "prompts_after_last_call": 0
        }


        print(state.get("tool_execution_history", []))
        return {
            "tool_execution_history": [tool_msg],
            "string_validation": "pass"
        }
    except Exception as e:
        tool_msg = ToolMessage(
        content=e,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        )
        return {
            "tool_execution_history": [tool_msg],
            "string_validation": "pass"
        }









async def list_datasources_tool(state: dict):
    print( "I am in list datasources tool node")

    tool_calls = state.get("tool_calls", [])
    tool_call = tool_calls[0] if tool_calls else {}
    print("Tool calls to execute:", tool_calls)
    tool_call_id = tool_call.get("id", str(uuid.uuid4()))
    print("Tool call ID:", tool_call_id)


    tool_call = {'name': 'list-datasources', 'args': {}, 'id': tool_call_id, 'type': 'tool_call'}
    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ]
        }

#     tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})

    # 🔒 ALWAYS COPY STATE STRUCTURES (IMMUTABLE PATTERN)
    current_tool_calls = copy.deepcopy(state.get("current_tool_calls", {}))
    most_recent_tool_calls = copy.deepcopy(state.get("most_recent_tool_calls", {}))

    try:
        async with Client("http://localhost:3927/tableau-mcp") as client:
            tool_result = await client.call_tool(tool_name, tool_args)

        tool_msg = ToolMessage(
            content=tool_result,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )


        # Update tracking dictionaries safely
        current_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed"
        }

        most_recent_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed",
            "prompts_after_last_call": 0
        }

        all_datasources = json.loads(tool_result.content[0].text) if tool_result and tool_result.content else []
        return {
            "list_datasources_tool_call_status": "success",
            "list_datasources_tool_call_id": tool_call_id,
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "all_datasources": all_datasources
        }

    # ==========================================================
    # 4️⃣ Handle Tool Error
    # ==========================================================
    except Exception as e:

        error_msg = f"Error executing tool '{tool_name}': {str(e)}"

        tool_msg = ToolMessage(
            content=error_msg,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )

        return {
            "list_datasources_tool_call_status": "error",
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "all_datasources": []

        }


def identify_relevant_datasource(state: dict):
    langchain_tools = state.get("langchain_tools", [])
    # print("Langchain tools available:", langchain_tools)
    all_datasources = state.get("all_datasources", [])
    # all_datasources = "\n".join([f"- {ds}" for ds in all_datasources])
    # print("All datasources retrieved:", all_datasources)
    current_datasource = state.get("current_datasource", None)
    print("Current datasource before identification:", current_datasource)
    rejected_datasources = state.get("rejected_datasources", [])
    rejected_datasources.append(current_datasource)
    print("Rejected datasources so far:", rejected_datasources)

    prompt = f"""You are a Tableau expert with deep understanding of Tableau datasources and their structures.
You have access to a list of all datasources available on the Tableau Server, along with their descriptions. 
Your task is to identify the most relevant datasource(s) for a given user request.

Optionally, you will be provided with list of rejected datasources which you have already identified as irrelevant 
in previous steps but they does not contain the data required for the current user request. You should not consider these datasources 
while identifying the relevant datasource for the current user request.

User Request: {state.get("input", "")}

Available Datasources:
{all_datasources}

Rejected Datasources:
{rejected_datasources}


You will only output the ID of the most relevant datasource as string datatype (with double quotes), without any explanations or formatting.
"""
    msg = creative_llm.invoke(prompt)
    relevant_datasource = msg.content.strip('"')

    for ds in all_datasources:
        # print("Checking datasource:", ds)
        # print("ID:", ds.get("id", ""))
        # print("ID TYPE:", type(ds.get("id", "")))
        # print("DS ID TYPE:", type(relevant_datasource))
        if relevant_datasource == ds.get("id", ""):
            relevant_datasource = ds
            # print("Exact match found for datasource ID:", relevant_datasource)
    current_datasource = relevant_datasource

    print("Identified relevant datasource:", current_datasource)
    tool_call_id = state.get("list_datasources_tool_call_id", str(uuid.uuid4()))
    tool_msg = ToolMessage(
        content=current_datasource,
        tool_name="list-datasources",
        tool_call_id=tool_call_id,
    )
    return {
        "current_datasource": current_datasource,
        "tool_execution_history": [tool_msg]
    }


async def get_datasource_metadata_tool(state: dict):
    print( "I am in get datasource metadata tool node")

    tool_calls = state.get("tool_calls", [])
    print("Tool calls to execute:", tool_calls)
    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ]
        }

    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    tool_call_id = tool_call.get("id", str(uuid.uuid4()))

    # 🔒 ALWAYS COPY STATE STRUCTURES (IMMUTABLE PATTERN)
    current_tool_calls = copy.deepcopy(state.get("current_tool_calls", {}))
    most_recent_tool_calls = copy.deepcopy(state.get("most_recent_tool_calls", {}))

    try:
        async with Client("http://localhost:3927/tableau-mcp") as client:
            tool_result = await client.call_tool(tool_name, tool_args)

        tool_msg = ToolMessage(
            content=f"Result from tool {tool_name}: {tool_result}",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )


        # Update tracking dictionaries safely
        current_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed"
        }

        most_recent_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed",
            "prompts_after_last_call": 0
        }

        return {
            "get_datasource_metadata_tool_call_status": "success",
            "get_datasource_metadata_tool_call_id": tool_call_id,
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "datasource_metadata": tool_result.content[0].text if tool_result and tool_result.content else {}
        }

    # ==========================================================
    # 4️⃣ Handle Tool Error
    # ==========================================================
    except Exception as e:

        error_msg = f"Error executing tool '{tool_name}': {str(e)}"

        tool_msg = ToolMessage(
            content=error_msg,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )


        return {
            "get_datasource_metadata_tool_call_status": "error",
            "get_datasource_metadata_tool_call_id": tool_call_id,
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
                "datasource_metadata": {}
        }



def filter_metadata_node(state: dict):
    datasource_metadata = state.get("datasource_metadata", {})
    enhanced_input = state.get("enhanced_input", "")
    implementation_plan = state.get("implementation_plan", "")
    tool_call_id = state.get("get_datasource_metadata_tool_call_id", str(uuid.uuid4()))

    prompt = f"""
    You are a Tableau VizQL execution planning expert.

    GOAL:
    You are identifying ALL fields required to successfully execute the user's implementation plan.
    Missing a required field is a critical execution failure.  

    ====================================================================

    DATASOURCE METADATA:
    {datasource_metadata}

    USER REQUEST:
    {enhanced_input}

    IMPLEMENTATION PLAN:
    {implementation_plan}

    ====================================================================

    TASK:

    1) Identify all execution-critical fields.  
    A field is REQUIRED if removing it would cause:
    - Aggregation failure
    - Filter failure
    - Grouping failure
    - Granularity mismatch
    - Metric miscalculation
    - Inability to compute derived metrics outside the query (e.g., hourly average from sums)

    You MUST include:
    - All aggregation fields (SUM, COUNT, MIN, MAX)
    - All filter fields
    - All grouping dimensions
    - All granularity fields required by grouping logic
    - Any field explicitly referenced in the implementation plan
    - Any field required to correctly compute derived metrics outside the query

    ====================================================================

    GRANULARITY RULE:

    - If the plan requires grouping by hour:
        - Search metadata for explicit hour-level field (e.g., Trxn Hour, Hour, Txn Hour)
        - If an explicit hour field exists, INCLUDE it.
        - Do NOT derive hour from Transaction Date if hour field exists.
        - Prefer explicit granularity fields over datetime truncation.

    ====================================================================

    SEMANTIC MATCHING RULE:

    - You may semantically interpret abbreviated field names in metadata to identify required fields.
    - Examples: "Trxn" → "Transaction", "Amt" → "Amount"
    - This reasoning is INTERNAL only for selecting fields.

    OUTPUT FIDELITY RULE (MANDATORY):

    - In the final output, COPY the selected fields EXACTLY as they appear in metadata.
    - Do NOT rewrite, expand, normalize, or change any field name.
    - Copy the full metadata object for each field as-is.
    - Do not infer roles, data types, or other properties.
    - If no exact match exists in metadata, do NOT invent it. Return "fields not found".

    ROLE PRESERVATION RULE:

    - Use the "role" exactly as defined in metadata.
    - Do NOT infer role from data type.
    - Preserve all metadata properties (dataType, columnClass, defaultAggregation, dataCategory, role, etc.) exactly.

    SELF-VERIFICATION (MANDATORY):

    Before finalizing:
    1) List all aggregation fields required by plan
    2) List all filter fields required by plan
    3) List all grouping fields required by plan
    4) List all granularity fields required by plan
    5) Compare against your selected fields
    6) If ANY required field is missing, correct selection

    Do NOT include reasoning in the output.

    ====================================================================

    OUTPUT FORMAT (STRICT JSON ONLY):

    {{
        "status": "fields found" | "fields not found",
        "relevant_fields": [
            {{ full metadata object for each selected field }}
        ],
        "reason": "null or detailed explanation if fields missing"
    }}

    IMPORTANT:
    - Output a pure JSON Object. No markdown, no explanations, no summarization.
    - Include all selected fields with full metadata objects.
    - Semantic matching is allowed for evaluation but NEVER changes the actual metadata field names in output.
    """  
    msg = llm.invoke(prompt)
    print("Raw response from LLM for filtered metadata: ", msg.content)
    try:
        filtered_metadata = json.loads(msg.content)
    except:
        msg_content = msg.content.strip("```json").strip("```")
        try:
            filtered_metadata = json.loads(msg_content)
        except Exception as e:
            print("Failed to parse LLM response for filtered metadata. Returning empty list. Error: ", str(e))
            filtered_metadata = {
                "status": "fields not found",
                "relevant_fields": [],
                "reason": f"Failed to parse LLM response for filtered metadata. Error: {str(e)}"
            }


    if filtered_metadata.get("status") == "fields not found":
        tool_msg = ToolMessage(
            content=f"Relevant fields not found in metadata. Reason: {filtered_metadata.get('reason', 'No reason provided')} \n Call list-datasources to retry to fetch metadata of a different datasource",
            tool_name="filter_metadata_node",
            tool_call_id=tool_call_id,
        )
        # print("tool message for no fields found: ", tool_msg)
        # print("tool execution history for no fields found: ", state.get("tool_execution_history", []) + [tool_msg])
        # import time
        # time.sleep(30)
        return {
            "filtered_metadata": [],
            "rejected_datasources": state.get("rejected_datasources", []) + [state.get("current_datasource", None)],
            "tool_execution_history": [tool_msg]
        }
    elif filtered_metadata.get("status") == "fields found":
        tool_msg = ToolMessage(
            content=filtered_metadata.get('relevant_fields', []),
            tool_name="get-datasource-metadata",
            tool_call_id=tool_call_id,
        )
        # print("tool message for fields found: ", tool_msg)
        # print("tool execution history for fields found: ", state.get("tool_execution_history", []) + [tool_msg])

        # import time
        # time.sleep(30)
        return {
            "filtered_metadata": json.dumps(filtered_metadata.get("relevant_fields", [])),
            "current_datasource": state.get("current_datasource", None),
            "tool_execution_history": [tool_msg]
        }

async def execute_tool(state: dict):
    print( "I am in execute tool node")
    tool_calls = state.get("tool_calls", [])
    # print("Tool calls to execute:", tool_calls)
    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ]
        }

    tool_call = tool_calls[0]
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    tool_call_id = tool_call.get("id", str(uuid.uuid4()))

    # 🔒 ALWAYS COPY STATE STRUCTURES (IMMUTABLE PATTERN)
    current_tool_calls = copy.deepcopy(state.get("current_tool_calls", {}))
    most_recent_tool_calls = copy.deepcopy(state.get("most_recent_tool_calls", {}))

    # ==========================================================
    # 1️⃣ Prevent infinite loop (same tool + same args in current tick)
    # ==========================================================
    if tool_name in current_tool_calls:
        previous_args = current_tool_calls[tool_name].get("arguments", {})

        if previous_args == tool_args:
            previous_status = current_tool_calls[tool_name].get("status", "unknown")
            previous_response = current_tool_calls[tool_name].get("response")

            error_msg = (
                f"Identical tool call detected for '{tool_name}'.\n"
                f"Previous status: {previous_status}\n"
                f"Previous response: {previous_response}\n"
                "Adjust plan to avoid infinite loop."
            )
            # # print(error_msg, "\n tool args:", tool_args)
            tool_msg = ToolMessage(
                content=error_msg,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
            )

            return {
                "tool_execution_history": [tool_msg]
            }

    # ==========================================================
    # 2️⃣ Use cached result if already completed previously
    # ==========================================================
    if tool_name in most_recent_tool_calls:
        previous_args = most_recent_tool_calls[tool_name].get("arguments", {})
        previous_status = most_recent_tool_calls[tool_name].get("status", "")

        if previous_args == tool_args and previous_status == "completed":
            response = most_recent_tool_calls[tool_name]["response"]

            tool_msg = ToolMessage(content=response,
            tool_name=tool_name,
            tool_call_id=tool_call_id)


            # Reset prompts counter safely
            most_recent_tool_calls[tool_name]["prompts_after_last_call"] = 0
            # print(f"Using cached result for tool '{tool_name}' with identical arguments. Previous status: {previous_status}")
            # print("="*50)
            # # print(tool_msg, "\n tool args:", tool_args)

            return {
                "most_recent_tool_calls": most_recent_tool_calls,
                "tool_execution_history": [tool_msg]
            }

    # ==========================================================
    # 3️⃣ Execute Tool
    # ==========================================================
    try:
        async with Client("http://localhost:3927/tableau-mcp") as client:
            tool_result = await client.call_tool(tool_name, tool_args)

        tool_msg = ToolMessage(
            content=f"Result from tool {tool_name}: {tool_result}",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )


        # # print(tool_msg, "\n tool args:", tool_args)
        # Update tracking dictionaries safely
        current_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed"
        }

        most_recent_tool_calls[tool_name] = {
            "arguments": tool_args,
            "response": tool_msg,
            "status": "completed",
            "prompts_after_last_call": 0
        }

        return {
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "datasource_metadata": metadata_json if tool_name == 'get-datasource-metadata' else {}
        }

    # ==========================================================
    # 4️⃣ Handle Tool Error
    # ==========================================================
    except Exception as e:

        error_msg = f"Error executing tool '{tool_name}': {str(e)}"

        tool_msg = ToolMessage(
            content=error_msg,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )
        # # print(tool_msg, "\n tool args:", tool_args)


        return {
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "datasource_metadata": {}
        }


def final_response_after_tool_call_node(state: State):
    print("final_response_after_tool_call_node ")
    """
    Generate the final response to the user using:
    - enhanced_input
    - implementation_plan
    - context_anchors
    - tool execution history (to summarize results and explain any adjustments)
    - final results from tool calls
    """

    enhanced_input = state.get("enhanced_input", "")
    implementation_plan = state.get("implementation_plan", "")
    context_anchors = state.get("context_anchors", [])
    tool_execution_history = state.get("tool_execution_history", [])
    final_results = state.get("output", [])


    msg = creative_llm.invoke(f"""
        You are a Tableau assistant.

        Based on the conversation so far and the user's latest request, generate
        a concise and accurate response.

        Inputs you can use:
        1. Enhanced user input:
        {enhanced_input}

        2. Implementation plan:
        {implementation_plan}

        3. Context anchors extracted:
        {context_anchors}

        4. Tool execution history:
        {tool_execution_history}

        5. Final results from tool calls:
        {final_results}

        Instructions:
        - Respond only with the message text, no JSON or extra formatting.
    """)

    assistant_reply = msg.content.strip()


    return {"output": assistant_reply, "conversation_history":[AIMessage(content=assistant_reply)]}


def evaluator_node(state: State):
    print("I am in evaluator node")

    """
    This node would evaluate the final response against the user's original request and determine if the request has been fulfilled or if further tool calls are needed.
    It can also provide feedback on the quality of the response and suggest improvements for future iterations.
    """
    tool_execution_history = state.get("tool_execution_history", [])
    print("Tool execution history for evaluation:", tool_execution_history)
    final_response = state.get("output", "")
    original_request = state.get("input", "")
    enhanced_input = state.get("enhanced_input", "")
    implementation_plan = state.get("implementation_plan", "")
    is_follow = state.get("follow_up", "False")

    msg = llm.invoke(f"""
            You are an evaluator for a Tableau assistant's response.

            Your task is to evaluate the final response generated by the assistant against the user's original request.

            Inputs you can use:
            1. User's original request:
            {enhanced_input}

            2. Which was to be fulfilled by executing the following implementation plan:
            {implementation_plan}

            3. Assistant's final response:
            {final_response}

            Instructions:
            - Focus ONLY on whether the final result satisfies the user's intent, NOT on the methodology used.
            - If the assistant tried an alternative approach because the direct approach failed, and the final result is still correct, this should be considered a PASS.
            - The agent may use creative problem-solving — reward outcomes, not rigid process adherence.
            - Determine if the assistant's response fulfills the user's request.
            - If yes, respond with "Verdict: pass", nothing else.
            - If no, respond with "Verdict: fail" and specify what is missing or incorrect in the response.
            - Provide constructive feedback on how the assistant can improve its response in future iterations.
            - Respond only in this JSON format and nothing else:

            {{"Verdict": "<Your verdict here>", "evaluation": "<Your evaluation here>" }}

            - Do not include any explanations, formatting or reasoning in your response
    """)
    # read the JSON response and convert it to a dictionary
    try:
        evaluation = json.loads(msg.content)
    except json.JSONDecodeError:
        evaluation = {"Verdict": "fail", "evaluation": "LLM response could not be parsed as JSON. Please ensure the evaluator node responds with valid JSON."}
    # print("Evaluation result:", evaluation)
    return {"evaluation": evaluation}

def feedback_node(state: State):
    print("I am in feedback node")

    """
    This node would take the evaluation from the evaluator_node and provide feedback to the autonomous_executor to improve future responses and tool usage.
    It can also update the implementation plan or tool usage based on the feedback received.
    """
    evaluation = state.get("evaluation", "")
    verdict = evaluation.get('Verdict', 'fail')
    feedback = evaluation.get('evaluation', '')
    feedback_logs = state.get("feedback", {})
    if verdict == "fail":
        attempt_no = state.get("replanning_attempts", 0)
        feedback_logs[f"Attempt {attempt_no+1}"] = {
            "verdict": verdict,
                "evaluation": feedback}
        # print(f"Feedback for attempt {attempt_no+1}: Verdict - {verdict}, Evaluation - {feedback_logs}")
        return {"verdict": verdict, "feedback": feedback_logs, "replanning_attempts": attempt_no + 1 }
    # print(f"Feedback: Verdict - {verdict}, Evaluation - {feedback_logs}")
    return {'verdict': verdict, 'feedback': feedback_logs}

