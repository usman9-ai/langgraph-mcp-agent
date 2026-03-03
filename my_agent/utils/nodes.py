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
        You are analyzing whether a user message is a FOLLOW-UP question (needs previous context) or an INDEPENDENT question (standalone).

        RECENT CONVERSATION:
        {conversation_history}

        CURRENT USER MESSAGE: "{user_msg}"

        A message is a FOLLOW-UP if it:
        1. **Adds to previous query**: "and what was the transaction count", "also show me", "what about"
        2. **Modifies previous query**: "for DHA branch instead", "now for kemari", "change to monthly"
        3. **Refines failed attempt**: "try with clifton karachi", "search for X instead"
        4. **References previous results**: "break that down by month", "show me more details", "compare with"
        5. **Uses pronouns/incomplete context**: "and for that branch?", "what about it?", "the same but"
        6. **Continues same topic**: "give me monthly breakdown for year 2025" (after discussing same metrics)

        A message is INDEPENDENT if it:
        1. **Asks completely new question**: "what is the branch code of clifton branch" (after discussing transaction amounts)
        2. **Starts fresh topic**: "show me sales data" (after discussing branches)
        3. **Has complete context**: Includes all necessary information without needing previous messages
        4. **Greetings/Meta questions**: "hello", "what can you do?", "help me understand"

        CRITICAL INDICATORS:
        - Words like "and", "also", "too", "instead", "now for", "what about" → Usually FOLLOW-UP
        - Incomplete filters/context (e.g., just "for DHA" without mentioning what metric) → FOLLOW-UP
        - Complete, self-contained question with all details → INDEPENDENT
        - Question on completely different topic than last message → INDEPENDENT

        EXAMPLES:

        Previous: "avg transaction amount of clifton branch"
        Current: "and what was the transaction count" 
        → FOLLOW-UP (adding metric to same query)

        Previous: "branch code of clifton branch"
        Current: "try with clifton karachi branch"
        → FOLLOW-UP (refining failed search)

        Previous: "avg transaction amount and count for DHA"
        Current: "now for kemari"
        → FOLLOW-UP (changing filter, incomplete context)

        Previous: "sales by region"
        Current: "what is the branch code of clifton branch"
        → INDEPENDENT (completely different question, self-contained)

        Previous: "transaction data for feb 2025"
        Current: "give me monthly breakdown for year 2025"
        → FOLLOW-UP (changing aggregation level, continuing same analysis)

        RESPOND ONLY IN THIS EXACT FORMAT:
        {{"follow_up": "True"}}  OR {{"follow_up": "False"}}

        No explanation. Just the JSON.
        """)
    
    parsed = json.loads(msg.content)
    
    return {
        "follow_up": parsed["follow_up"], 
        "current_tool_calls": {},
        "tool_execution_history": Overwrite([]),
        "tool_calls": [],
        "feedback": {},
        "replanning_attempts": 0
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
        prompt = f"""You are enhancing a follow-up question by carrying forward relevant context from previous conversation.

        CONVERSATION HISTORY:
        {conversation_history}

        CURRENT USER MESSAGE: "{current_message}"

        TASK: Create an enhanced query that:
        1. ACCUMULATES metrics (don't drop previous metrics unless explicitly replaced)
        2. UPDATES filters when user specifies new values (e.g., "and for DHA branch?" replaces clifton with DHA)
        3. KEEPS unchanged filters (e.g., if month was feb 2025, keep it unless user changes time period)
        4. ADJUSTS aggregation level (e.g., "monthly breakdown" → "month-wise")
        5. REFINES failed searches with new terms user provides

        EXAMPLES:

        Previous: "avg transaction amount of clifton branch from feb 2025"
        User says: "and what was the transaction count"
        Enhanced: "what is the avg transaction amount and transaction count of clifton branch from the month of feb 2025"

        Previous: "avg transaction amount and transaction count of clifton branch from feb 2025"
        User says: "and for DHA branch"
        Enhanced: "what is the avg transaction amount and transaction count of DHA branch from the month of feb 2025"

        Previous: "avg transaction amount and transaction count of DHA branch from feb 2025"
        User says: "give me monthly breakdown for year 2025"
        Enhanced: "what is the month-wise avg transaction amount and transaction count of DHA branch for year 2025"

        Previous: Failed search for "clifton branch"
        User says: "try with clifton karachi branch"
        Enhanced: "search the branch code of branch named as 'clifton karachi branch'"

        Previous: "branch code of branch named as 'clifton karachi branch'"
        User says: "now for kemari"
        Enhanced: "search the branch code of branch named as 'kemari' or including 'kemari'"

        RULES:
        - If user adds a metric (e.g., "and transaction count"), ADD it to existing metrics
        - If user changes a filter (e.g., "for DHA"), REPLACE that specific filter value
        - Keep all other context unless explicitly changed
        - If previous query failed, use user's refined search term but keep the query structure
        - Be literal with user's phrasing (e.g., "monthly breakdown" → "month-wise")

        Return ONLY the enhanced query as a single clear sentence. No JSON, no explanations."""

        msg = llm.invoke(prompt)
        enhanced_input = msg.content.strip()
        print("Enhanced follow-up query:", enhanced_input)
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

        2. DISTINCT HOUR MEANS
        `
        ---------------------------------
        - When we say "distinct hour", we refer to unique hourly time slots in the data.
        - For example, if data exists for 9 AM, 10 AM, and 10 AM again, the distinct hours are 9 AM and 10 AM.
        - This concept is crucial for accurate average calculations and time-based aggregations.

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
    # read txt file for query rules and guidelines for the agent
    with open("C:\\Langgraph Agent\\my_agent\\utils\\query_rules_v2.txt", "r") as f:
        query_guidelines = f.read()

    

    langchain_tools = state.get("langchain_tools", [])
    llm_with_tools = llm.bind_tools(langchain_tools)

    while True:
        # Build the prompt with all context
        prompt = f"""
        You are a Tableau data assistant with full access to Tableau Server via MCP tools.
        You have the user's input, implementation plan, context anchors, and tool execution history.

        CRITICAL EXECUTION RULES:

        1. Average Metrics:
        - NEVER use AVG aggregation directly on RAW DATA.
        - Always query SUM grouped by hour.
        - Compute final average outside the query using:
            Average = Total hourly sum / Distinct hours count.
        - Distinct hour means count of unique hours in the dataset after applying filters. For example, 
        if data exists for 9 AM, 10 AM, and 10 AM again, the distinct hours are 9 AM and 10 AM (2 distinct hours).
        - There must exist a distinct hour field in the dataset to perform this calculation. 
        - If not, you must first check metadata and find the appropriate time field to use as distinct hour.

        2. Sample Value Substitution Rules:
        - Dates: ISO format (YYYY-MM-DD).
        - Datetime fields: include Tableau-allowed time variable if allowed.
        - Strings:
            - First try exact match.
            - If exact match fails, split string by space, comma, or hyphen.
            - Search each part separately.
            - Merge results using logical AND.
        - Numeric / Amounts / Reals:
            - Remove commas from input if user wrote 1,000,000 or 10,000,000.
            - Keep the original numeric data type (int/float) compatible with Tableau.

        3. String Resolution / Fuzzy Matching:
        - Multi-word strings → split → search separately → merge results with logical AND.
        - Apply the final merged value as a filter in the query.
        - If user string cannot be directly matched, use other deterministic filters (date, branch, region) to narrow dataset and then apply fuzzy matching.

        4. Execution Flow:
        - Review implementation plan step-by-step.
        - Map all metrics, filters, dimensions correctly with datasource metadata.
        - Validate field formats using sample values before execution.
        - NEVER replace actual user-provided filter values with sample values.
        - Chain tool calls according to implementation plan.
        - Execute tools in proper order automatically.
        - After each tool call, review results and determine next steps.
        - Handle errors and retries:
            - Invalid filter → parse suggestions, pick closest match, retry, mention adjustment in final response.
            - Invalid field/operator → re-check metadata, correct, retry once.
            - Any other errors → translate into plain language; do not show raw JSON errors.

        IMPORTANT INSTRUCTIONS FOR TOOL CALLS:

        - The 'query' field for the 'query-datasource' tool must be a JSON object, NOT a string.
        - Do NOT wrap the JSON in quotes.

        5. Allowed Aggregations:
        - SUM, COUNT, MIN, MAX
        - Disallowed: AVG (on raw data)

        Before adding a function to any non-measure field:
        - Verify that the function exists in the allowed aggregation list.
        - If not explicitly allowed → do not use it.

        6. Output Instructions:
        - Generate a single, human-readable summary message.
        - Include:
            - Final results if the request is fulfilled.
            - Any adjustments or retries that occurred (e.g., fuzzy matching applied, filter corrected).
            - Don't represent amounts with any currency symbols.
        - Do not output JSON or extra formatting in the final response.
        - Ensure the final computation of average is performed outside of the query using SUMs from hourly grouping.

        User Enhanced Input:
        {state.get("enhanced_input", "")}

        Implementation Plan:
        {state.get("implementation_plan", "")}

        Conversation History:
        {state.get("tool_execution_history", [])}

        Must use the filters as specified in below Query Guidelines, no not generate new filters:
        {query_guidelines}
        """
        # Invoke LLM
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
        "tool_calls": tool_calls,
        "tool_execution_history": [AIMessage(content=ai_message)],
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

    if tool_name in current_tool_calls:
        previous_args = current_tool_calls[tool_name].get("arguments", {})
        previous_status = current_tool_calls[tool_name].get("status", "unknown")
        previous_response = current_tool_calls[tool_name].get("response")

        if previous_args == tool_args:
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
    current_tool_calls = state.get("current_tool_calls", {})
    most_recent_tool_calls = state.get("most_recent_tool_calls", {})

    datasource_id = tool_args.get("datasourceLuid")
    query = tool_args.get("query")
    print("Original Query:", query)
    print("Type of query before parsing:", type(query))


    response = await call_tool(tool_name, tool_args)
    # print("New tool call response: ", response)

    tool_msg = ToolMessage(
        content=response,
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
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "string_validation": "pass"
        }


async def list_datasources_tool(state: dict):
    print( "I am in list datasources tool node")

    tool_calls = state.get("tool_calls", [])
    print("Tool calls to execute:", tool_calls)

    tool_call = {'name': 'list-datasources', 'args': {}, 'id': 'call_2vUAGEKOvb3WLESS14A1PL6k', 'type': 'tool_call'}
    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ]
        }

#     tool_call = tool_calls[0]
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
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "all_datasources": tool_result.content[0].text if tool_result and tool_result.content else []
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
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "all_datasources": tool_result.content[0].text if tool_result and tool_result.content else []

        }


def identify_relevant_datasource(state: dict):
    langchain_tools = state.get("langchain_tools", [])
    print("Langchain tools available:", langchain_tools)

    # This node would analyze the enhanced user input and the list of datasources to identify which datasource is relevant to the user's request.
    # It would use the metadata of each datasource (e.g., fields, metrics, dimensions) to determine relevance.
    # The output would be the ID or name of the most relevant datasource to be used in subsequent tool calls.


async def get_datasource_metadata_tool(state: dict):
    print( "I am in get datasource metadata tool node")

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
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
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
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
                "datasource_metadata": {}
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

