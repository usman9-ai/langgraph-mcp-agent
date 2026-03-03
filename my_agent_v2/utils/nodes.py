from .state import State
from .llm import llm, slightly_creative_llm, creative_llm, reasoning_llm, intent_classifier_llm
import json
import re
import uuid
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from fastmcp import Client
import copy
from langgraph.types import Overwrite
import ast
from .mcp_tools import get_query_structure_guidelines


mcp_client = Client("http://localhost:3927/tableau-mcp")
def intent_classifier(state: State):
    print("I am in intent classifier")
    """Determine if the user message is Tableau-related, a greeting, or other domain."""

    msg = intent_classifier_llm.invoke(f"""
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
    print(msg)
    return {"intent": msg["intent"]}

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
        print("I am in Greeting Handler ")

        msg = creative_llm.invoke(f"""
        You are a professional Tableau assistant.

        The user has greeted you.

        Your task:
        - Respond with a polite and professional greeting.
        - Acknowledge the user's message naturally.
        - Mention that you are a Tableau assistant.
        - Inform the user that you can help with Tableau-related business queries.

        Do NOT mention any limitations.
        Keep the tone professional and concise.

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
    print(msg)
    parsed = json.loads(msg.content)

    tool_call_counts = {'list-datasources':0, 'get-datasource-metadata':0, 'query-datasource':0}

    
    return {
        "follow_up": parsed["follow_up"], 
        "tool_call_counts": tool_call_counts,
        "current_tool_calls": {},
        "tool_execution_history": Overwrite([SystemMessage(content="Tool execution history so far:")]),
        "tool_calls": [],
        "feedback": {}
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
    
    msg = slightly_creative_llm.invoke(f"""You are a Tableau data analytics assistant with access to Tableau MCP(Model Context Protocol) tools.

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
        conversation_history = state.get("conversation_history", [])
        current_message = state['input']
        is_follow_up = state.get("follow_up", False)




        # Build enhancement prompt
        prompt = f"""You enhance follow-up business queries by intelligently carrying forward relevant context — but only when the user clearly implies continuation.

            INPUTS:
            - CONVERSATION_HISTORY: {conversation_history}
            - LAST_RETURNED_RESULTS: Structured rows returned previously (may include fields like name, salary, net_salary, etc.)
            - CURRENT_USER_MESSAGE: "{current_message}"

            GOAL:
            Produce ONE clear enhanced query sentence.
            No JSON. No explanation.

            ------------------------------------------------------------
            STEP 1 — DETERMINE INTENT

            Classify CURRENT_USER_MESSAGE as one of:

            1) CONTINUATION  
            (Uses signals like: "also", "and", "for them", "those people",
            "same employees", "that person", "among them")

            2) FILTER_REPLACEMENT  
            (User explicitly changes a filter value)

            3) METRIC_ADDITION  
            (User adds another metric to retrieve)

            4) ENTITY_REFERENCE  
            (User refers to a previously returned entity by partial name or pronoun)

            5) NEW_QUERY  
            (No linguistic signal of continuation; introduces new concept;
            does not reference previous entities or filters)

            If NEW_QUERY → DO NOT carry forward previous filters or entities.

            ------------------------------------------------------------
            STEP 2 — ENTITY HANDLING

            If user refers to:
            - "these people", "those employees", "them"
            → Use ALL names from LAST_RETURNED_RESULTS (exact spelling)
            → Wrap each in double quotes.

            If user provides partial name:
            - Match case-insensitive against LAST_RETURNED_RESULTS.name
            - Ignore honorifics (Mr, Mrs, Ms, Dr)
            - If ONE match → use exact full name wrapped in double quotes
            - If MULTIPLE matches → include all exact matches quoted
            - If NO match → keep user text literal (do not invent)

            Always reuse exact returned spelling.

            ------------------------------------------------------------
            STEP 3 — FILTER RULES

            - CONTINUATION → keep previous filters.
            - FILTER_REPLACEMENT → replace only that filter.
            - METRIC_ADDITION → add metric, keep filters.
            - ENTITY_REFERENCE → restrict to matched entities.
            - NEW_QUERY → drop all previous filters unless explicitly restated.

            Never assume a filter continues unless user implies it.

            ------------------------------------------------------------
            STEP 4 — SAFETY

            - Do not invent values.
            - Escape internal quotes inside quoted values.
            - Output exactly ONE clear sentence.

            ------------------------------------------------------------
            EXAMPLES

            Previous: Names of employees with salary between 50k and 70k  
            Returned: ["Ali Khan", "Sara Begum"]

            User: "get net and gross salary of these people"  
            Output: Get name, net salary, and gross salary for "Ali Khan" and "Sara Begum" whose salary is between 50,000 and 70,000.

            User: "get performance analytics for Ali"  
            Output: Get performance analytics for "Ali Khan".

            User: "give me names of employees who received travel allowance"  
            Output: Get names of employees who received travel allowance.

            ------------------------------------------------------------

            Return only the enhanced query sentence.
            """

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
        You are a Tableau MCP(Model Context Protocol) assistant agent with full access to Tableau server and
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
        You are a Senior Business Intelligence (BI) Engineer working in a bank.

        Your job is to provide accurate, structured, and business-ready responses
        based on conversation history and the user's latest request.

        Inputs:

        1. Full conversation history:
        {conversation_history}

        2. Latest user request (enhanced if applicable):
        {enhanced_input}

        Instructions:

        - Carefully analyze the entire conversation.
        - Pay special attention to the most recent user request.
        - If the user is asking to modify, sort, filter, or adjust a previously generated result:
            - Apply the requested transformation logically.
            - Do NOT restate the instruction.
            - Do NOT rephrase the question.
            - Produce the updated final result.
        - If no data transformation is needed, provide a clear and professional answer.
        - Think step-by-step internally before generating the final response.
        - Provide only the final business-ready answer.
        - Do not output JSON.
        - Do not explain your reasoning.
        """)

    assistant_reply = msg.content.strip()



    return {"output": assistant_reply, "conversation_history": [AIMessage(content=assistant_reply)]}


def plan_implementation(state: State):
    tool_execution_history = state.get("tool_execution_history", [])
    print("Planning implementation. Tool execution history so far:", tool_execution_history)
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

        msg = creative_llm.invoke(f"""
        You are a Tableau MCP(Model Context Protocol) planning agent operating in a banking analytics environment.

        Your task is to create a precise, step-by-step implementation plan using ONLY the provided tools to fulfill the user's request.

        User Request:
        {enhanced_input}

        Available Tools:
        {mcp_tool_descriptions}

        Previous plan if any:
        {state.get("implementation_plan", "")}

        Previous Tool Execution History if any:
        {tool_execution_history}

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
        - For transaction related metrics, always use Trxn Hour field.
        - All time-based aggregations must first be reasoned at hour level unless explicitly requested otherwise.
        - Never casually aggregate across mixed grains.


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

        ---------------------------------
        10. STATIC VS TRANSACTION FIELD RULE (CRITICAL)
        ---------------------------------

        If the requested metric is a STATIC ATTRIBUTE (e.g., salary, allowance, employee data, master record fields):
            DO NOT apply SUM.
            DO NOT apply AVG.
            DO NOT group by HOUR.
            Simply filter by entity (e.g., employee name or ID).
            Return the field value as-is.


        Aggregation rules apply ONLY to:

        Transactional

        Time-series

        Performance metrics
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

        return {"implementation_plan": implementation_plan,
        "tool_execution_history": Overwrite([SystemMessage(content="Tool execution history so far:")])
        }


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
    with open("C:\\Langgraph Agent\\my_agent_v2\\utils\\instruction.txt", "r") as f:
        instructions = f.read()

    with open("C:\\Langgraph Agent\\my_agent_v2\\utils\\query_rules.txt", "r") as f:
        query_guidelines = f.read()


    langchain_tools = state.get("langchain_tools", [])
    llm_with_tools = llm.bind_tools(langchain_tools)
    tool_execution_history = state.get("tool_execution_history", [])

    while True:
        prompt = f"""You are a Tableau MCP assistant agent operating in a banking analytics environment.
        User has asked:
        {state.get("enhanced_input", "")}
        Your task is to implement the following plan to fulfill the user's request:
        {state.get("implementation_plan", "")}
        Follow the instructions below carefully as you execute the plan step by step. Adhere strictly to the guidelines and rules provided:
        {instructions}

        And here are specific guidelines for formulating queries to the Tableau server:
        {query_guidelines}


        You will emit tool calls and receive tool results in a loop until the plan is fully executed. 
        You can emit max one tool call at a time, and you must wait for the result before emitting the next tool call.
        After each tool call, you will get the result and feedback, and you can adjust your next steps accordingly.

        IMPORTANT:
        - Always Emit one tool call at a time
        - If trying to filter a Dimesnion column by a number value, use 'SET' filter with 'values' parameter.
        - If trying to filter non numeric values, use Filtertype 'MATCH' with parameter 'contains'

        Tool Call Datatype:
        - Tool Call must be a Valid JSON object, No string or Stringified JSON
        - Specifically, check the query field to be JSON,  when calling query datasource tool
        
        Grain Size:
        - For calculating metrics, use the grain size of 1 Hour, sum the raw data per hour before calculating any metric.
        - For transaction metrics use 'Trxn Hour' field. 

        Update plan:
        - You must create a updated plan, given then original implementation plan and results of the tool calls. 
        - This updated plan will help you track what you have done so far and what should be next decision. 
        - Also output your plan, in addition to tool calls.

        Multi-Step Plan:
        - If you identify that you need to execute multiple quries, then you must provide your complete step by step plan in the content section of response. 
        - This will help you in next iteration to track what has been done and what is remaining   
        
        
        You can see the history of your tool calls and their results so far:
        {tool_execution_history}
        
        """
        msg = llm_with_tools.invoke(prompt)
        
        ai_message = msg.content
        print("Length of tool execution history:", len(tool_execution_history))
        print("\n"*10)
        # LangChain/OpenAI tool calls may occasionally omit `id`. Our downstream tool
        # nodes and frontend streaming rely on stable IDs to correlate call->result.
        raw_tool_calls = getattr(msg, "tool_calls", []) or []
        tool_calls = []
        for tc in raw_tool_calls:
            if isinstance(tc, dict):
                call = dict(tc)
                call.setdefault("id", str(uuid.uuid4()))
                call.setdefault("type", "tool_call")
                tool_calls.append(call)
            else:
                # Best-effort normalization for non-dict tool call objects.
                call = {
                    "name": getattr(tc, "name", None),
                    "args": getattr(tc, "args", {}) or {},
                    "id": getattr(tc, "id", None) or str(uuid.uuid4()),
                    "type": getattr(tc, "type", None) or "tool_call",
                }
                tool_calls.append(call)
        if tool_calls != [] and len(tool_execution_history) > 3:
            return  {
            "tool_calls": tool_calls,
            "need_summarization": True,
            "tool_execution_history": [msg],
            "output": msg.content,
            "follow_up": False,
            "intent": 'None'
            }

        else:

            return  {
            "tool_calls": tool_calls,
            "need_summarization": False,
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

    if tool_name in current_tool_calls:
        previous_args = current_tool_calls[tool_name].get("arguments", {})
        previous_status = current_tool_calls[tool_name].get("status", "unknown")
        previous_response = current_tool_calls[tool_name].get("response")

        if previous_args == tool_args:
            print(f"Identical tool call detected for '{tool_name}'.")
            # print(f"Previous status: {previous_status}")
            # print(f"Previous response: {previous_response}")

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
    print( "I am in cached tool node")

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
    if tool_name == 'list-datasources':
        print(f"Checking for cached result for tool '{tool_name}'. Previous args: {previous_args}, Current args: {tool_args}, Previous status: {previous_status}")
        print(f"current tool args: {tool_args}")
    if previous_args == tool_args and previous_status == "completed":
        tool_msg = most_recent_tool_calls[tool_name]["response"]

        # Reset prompts counter safely
        most_recent_tool_calls[tool_name]["prompts_after_last_call"] = 0
        print(f"Using cached result for tool '{tool_name}' with identical arguments. Previous status: {previous_status}")
        print("="*50)
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
        elif tool_name == "get_query_structure_guidelines":
            return {"next_tool_name": "get_query_structure_guidelines"}
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
    tool_calls = state.get('tool_call_under_str_resolution', [])
    retry_attempts_for_str_resolution = state.get('retry_attempts_for_str_resolution', 0)
    print("tool call: ", tool_calls)

    if not isinstance(tool_calls, list) or not tool_calls:
        return {
        "string_resolution_tool_calls": [ToolMessage(content="No valid tool calls found for string resolution.")],
        "retry_attempts_for_str_resolution": retry_attempts_for_str_resolution + 1
        }

    tool_call = tool_calls[0]
    if not isinstance(tool_call, dict):
        return {
        "string_resolution_tool_calls": [ToolMessage(content="Invalid tool call payload for string resolution.")],
        "retry_attempts_for_str_resolution": retry_attempts_for_str_resolution + 1
        }

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

    
def summarize_string_validation_process(previous_summary,tool_execution_history):
    prompt = f"""
    Your task is to create a rolling summary. You are given a list of tool calls and their results from a multi-turn tool execution process responsible for searching possible matches of substrings based on actual values.

    For example, if the original query has filter value = 'Jhehlum', but the actual name in the datasource is 'Jhelum', the agent splits the actual value into substring candidates like 'jhe', 'hlem', and 'lum' and executes queries with these substrings.

    Your task is to summarize these raw tool calls and results into structured JSON.
    Look for filters using a "contains" keyword and a value, for example:

        "filterType": "MATCH",
        "contains": "Clifton Karachi",
        "exclude": false

    For each such field, summarize it as:
    - Field name
    - Candidate tried
    - Result of that candidate

    Previous summary:
    {previous_summary}

    Here is the list of tool calls:
    {tool_execution_history}

    Additional notes:
    - If a tool call returns an error, include only the error in the summary.
    - Do not add explanations or reasoning.

    Guidelines for JSON:
    - Use valid JSON objects for all tool calls.
    - Ensure the query field is a JSON object when calling the datasource tool.
    """


    msg = llm.invoke(prompt)
    return msg


async def string_validation_node(tool_call, user_msg, meta_data, tools, error_message):

        # ai_message = f"""After many attempts, the string resolution process has not been successful. 
        #                     The tool calls made for string resolution and their results are as follows:\n\n"""

        # ai_message += """Given the repeated failures in resolving the string issue, it is likely that there is a fundamental 
        #     mismatch between the user's input and the data available in the datasource. This could be due to various reasons such as 
        #     incorrect assumptions about the data structure, significant discrepancies in string values, or limitations in the tools 
        #     being used for resolution. It may be necessary to revisit the user's original request, clarify their intent, and possibly 
        #     adjust the approach to better align with the actual data and its structure."""



        # # a general message for user to state the agnent tried repeatedly to retrieve the result but failed.
        # # please check your input and try again with different values or check the datasource for available values.
        # output_msg = """
        # After multiple attempts, the system was unable to retrieve the results. 
        # Please check your input and try again with different values, or verify the available values in the datasource."""

        # return {
        #     "tool_call_under_str_resolution": [],
        #     "string_resolution_tool_calls": [AIMessage(content=ai_message)],
        #     "output": output_msg
        # }

    with open("C:\\Langgraph Agent\\my_agent_v2\\utils\\query_rules.txt", "r") as f:
        query_guidelines = f.read()
    string_resolution_tool_calls = []
    llm_with_tools = llm.bind_tools(tools)
    summarized_histrory = None
    print("I am on string validation node")
    attempts = 0
    flag = True
    msg = ''
    while flag and attempts < 4:
        prompt = f"""
        You are assisting with Tableau query execution through Tableau MCP(Model Context Protocol) Server. here are the query guidelines {query_guidelines}

        You are provided with:
        - The original tool call arguments
        - Field metadata
        - Execution history
        - The latest error message (if any)

        Your objective is to help resolve string filtering issues in Tableau queries.

        Common issue:
        Filtering fails when the string value in the MATCH filter does not exactly match the value stored in the datasource.

        Example:
        Query filter value = 'Clifton Branch'
        Actual datasource value = 'Clifton, Karachi'

        In such cases, substring matching using MATCH with "contains" may help.

        Strategy:

        1. If the error message indicates a specific field or operator issue:
        - Focus only on resolving the field mentioned in the error.
        - Use metadata to validate field names and data types.
        - Adjust only the relevant field.

        2. If the problematic field is of type STRING (typically a dimension):
        - First check its distinct count using COUNTD.
        - If distinct count is approximately 100 or fewer:
                - Retrieve all distinct values of that field.
                - Return them as possible candidates.
        - If distinct count is greater than 100:
                - Apply substring-based candidate strategy described below.

        Substring Candidate Strategy:

        - If the filter contains multiple words:
            Split into individual words and try each separately.
        - If a single word:
            Try original word first.
            If no match, split into at most 3 substrings.
        - If error message suggests close matches, use those.
        - Avoid repeating previously tried candidates (refer to execution history).

        Important behavioral guidelines:

        - Modify only STRING type filters.
        - Do not change filters for INT, FLOAT, DATETIME, or other non-string fields.
        - If the original query does not output the STRING field being validated,
        adjust the query temporarily to output only that STRING field for validation purposes.
        - Preserve other filters unless they are directly causing errors.

        Error Handling:

        If query fails due to invalid field or operator:
        - Cross-check metadata.
        - Retry once after correction.

        For other errors:
        - Provide a clear explanation in plain English.
        - Avoid exposing raw JSON error traces.

        Stopping Conditions:

        - Stop when no new unique candidates remain.
        - Stop when all words from the original string have been tested.
        - Stop if the same arguments would be repeated.
        - Stop if a valid match is found and return final result.

        Inputs:

        Original Query:
        {tool_call}

        Field Metadata:
        {meta_data}

        Execution History:
        {summarized_histrory}

        Latest Error Message:
        {error_message}

        Return either:
        - A tool call with corrected arguments, OR
        - A clear final explanation if resolution is complete.
        """
        print(prompt)
        msg = llm_with_tools.invoke(prompt)
        print("RAW LLM RESPONSE: ", msg)

        tool_calls = getattr(msg, "tool_calls", [])
        # print("Tool calls extracted from LLM response:", tool_calls)
        if tool_calls == []:
            # string_resolution_tool_calls.append(msg)

            flag = False

        attempts += 1
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            tool_call_history = []
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

            query = tool_args.get("query")
            print("Old query: ", query)
            query = query.strip("'") if isinstance(query, str) else query
            if isinstance(query, str):
                query = json.loads(query)
            print("New query: ", query)

            tool_args["query"] = query

            tool_call_history.append(msg)

            # print("Tool call", tool_args)
            tool_result = await call_tool(tool_name, tool_args)
            # print("tool result ",tool_result )
            tool_msg = ToolMessage(
                content=tool_result,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
            )

            tool_call_history.append(tool_msg)
            summarized_histrory = summarize_string_validation_process(string_resolution_tool_calls ,tool_call_history)
            # string_resolution_tool_calls.append(summarized_histrory)



    return  string_resolution_tool_calls, msg
        


async def query_datasource_tool(state: dict):
    max_allowed_attempts = 5

    print( "I am in query datasource tool node")
    tool_call_counts = state.get('tool_call_counts')
    count = tool_call_counts.get('query-datasource')
    if count > max_allowed_attempts:
        print("limit exceeded")
        print("+"*150)
        return 
    else:
        tool_call_counts['query-datasource'] += 1
    print(tool_call_counts)
    tool_calls = state.get("tool_calls", [])
    if len(tool_calls) > 1:
        print("Warning: Multiple tool calls detected. Only the first one will be executed.")

        return {
            "tool_execution_history": [
                ToolMessage(content="Multiple tool calls detected, please emit one tool call at a time",
                tool_name = 'query-datasource',
                tool_call_id = "")
            ]
        }
    print("tool call: ", tool_calls)

    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.")
            ], 

            "string_validation": "pass"
        }
    if not isinstance(tool_calls[0], dict):
        return {
            "tool_execution_history": [
                ToolMessage(content="Invalid tool call payload: expected object.")
            ],
            "string_validation": "fail"
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
    query = query.strip("'") if isinstance(query, str) else query
    if isinstance(query, str):
        try:
            query = json.loads(query)
        except Exception:
            return {
                "tool_execution_history": [
                    ToolMessage(
                        content="Invalid query payload format. Expected JSON object in `query`.",
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                    )
                ],
                "string_validation": "fail"
            }
    if not isinstance(query, dict):
        return {
            "tool_execution_history": [
                ToolMessage(
                    content="Invalid query payload type. `query` must be an object.",
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                )
            ],
            "string_validation": "fail"
        }
    tool_args["query"] = query  # Update the tool_args with the cleaned query
    # print("Original Query:", query)
    print("Type of query before parsing:", type(query))
    # Example usage inside your tool function
    datasource_id = tool_args.get("datasourceLuid")
    query_raw = tool_args.get("query")
    # print("Original Query:", query_raw)

    fields = query.get("fields", [])
    field_names = [f.get("fieldCaption") for f in fields if isinstance(f, dict)]

    # print("Parsed fields:", field_names)


    if field_names == []:
        # print("No fields found in query. Skipping metadata check.")
        return {
            "tool_execution_history": [
                ToolMessage(content="No Field name found in the tool call.")
            ], 

            "string_validation": "pass"
        }
    meta_data = state.get("datasource_metadata", {})
    try:
        meta_data =  json.loads(meta_data)
    except:
        try:
            meta_data = json.loads(meta_data.replace("'", '"'))
        except json.JSONDecodeError:
            print("Error decoding JSON:", meta_data)

            meta_data = {}

    query_fields = []
    filtered_meta_data = []
    for field in meta_data.get("fields", []):
        field_name = field.get("name", "")

        if field_name in field_names:
                filtered_meta_data.append(field)

                query_fields.append({
                "fieldCaption": field_name,
                "function": "MAX",
                "fieldAlias": f"Sample {field_name}"
                })


    query_dict = {
        "fields": query_fields
        }

    args = {
    "datasourceLuid": datasource_id,
    "query": query_dict,
    "limit": 1
}
    # response = await call_tool('query-datasource', args)
    # response =  json.loads(response)
    # sample_values = response.get("data", [])
    # print("Sample values from datasource:", sample_values)

    tool_descriptions = state.get("langchain_tools")
    for tool in tool_descriptions:
        if tool.name == 'query-datasource':
                query_datasource_description = tool

    

    prompt = f"""
        You have sample values from a datasource and a query with filter values.

        For each field in the query filters:
        1. Look at the sample value for that field and extract its format pattern
        2. Compare the filter value in the query to that pattern
        3. If the format is different, reformat the filter value to match — keeping the same data, just fixing the format
        4. If the format already matches, leave it as is


        Your next task is to adjust the query structure and filter names to match the syntax required by the tableau server
        and the query-datasource tool. For this you need to review the query-datasource tool description and 
        meta data of the fields being used in the query, and understand the 
        correct syntax for filters and aggregations when making tool calls.



        Sample Values:

        Query:
        {tool_call}

        query datasource tool description:
        {query_datasource_description}

        Meta Data:
        {filtered_meta_data}

                
        Return the query as a valid JSON object.
        Do NOT return a JSON string.
        The "query" field must be an object, not a string.
        Do Not return any markdown formatting or explanations, just the JSON object.
        """
    # # print("tool description:", query_datasource_description)

    # print("Raw response: ", msg.content)
    # new_tool_call = json.loads(msg.content)


    tool_name = tool_call.get('name','')
    # print(tool_name)
    tool_args = tool_call.get('args', '')
    tool_call_id = tool_call.get('id')


    response = await call_tool(tool_name, tool_args)
    # print("New tool call response: ", response)
    
    response = str(response)
    if "Filter validation failed for field" in response:
        print("error detected")
        print("response: ", response)
        max_allowed_attempts = 2
        # query = tool_args.get("query", {}) 
        # query_filter_fields = query.get("filters", [])
        # query_filter_field_names = []
        # for f in query_filter_fields:
        #     query_filter_field_name = f.get("fieldCaption", "")
        #     query_filter_field_names.append(query_filter_field_name)


        # # print("Filtered metadata : ", filtered_meta_data)
        # for field in filtered_meta_data:
        #     if field.get("dataType", "") == 'STRING' and field.get("name", "") in query_filter_field_names:




        #         for f in query_filter_fields:
        #             if f.get("filterType", "") == "MATCH":
        #                 starts_with_value = f.get("startsWith", "")
        #                 ends_with_value = f.get("endsWith", "")
        #                 contains_value = f.get("contains", "")
        #                 filter_value = {"startsWith": starts_with_value, "endsWith": ends_with_value, "contains": contains_value}


        #             elif f.get("filterType", "") == "SET":
        #                 values = f.get("values", [])
        #                 filter_value = {"values": values}


        user_input = state.get("enhanced_input", '')
        langchain_tools = state.get("langchain_tools", {})

        tool_calls_history, final_msg = await string_validation_node(tool_call, user_input, filtered_meta_data, langchain_tools, response)

        tool_result = f"""Original tool call returned error: {response}, \n
                          In Order to resolve any possible issue in filter values, we executed a Fuzzy match search.\n 
                          Below is the summary of tool calls and their responses. \n 
                          {tool_calls_history} \n 
                          and final answer from fuzzy matching is {final_msg}
                          You can now use the results of this search to correct or use closet match in your query parameters and re-execute the original query"""


        tool_msg = ToolMessage(
            content=tool_result,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )
    else:
        tool_msg = ToolMessage(
            content=response,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )


    return {
            "tool_call_counts": tool_call_counts,
            "tool_execution_history": [tool_msg],
            "string_validation": "pass"
        }


    # try:
    #     async with Client("http://localhost:3927/tableau-mcp") as client:
    #         tool_result = await client.call_tool(tool_name, tool_args)

    #     tool_msg = ToolMessage(
    #     content=tool_result,
    #     tool_name=tool_name,
    #     tool_call_id=tool_call_id,
    #     )

    #     current_tool_calls[tool_name] = {
    #         "arguments": tool_args,
    #         "response": tool_msg,
    #         "status": "completed"
    #     }

    #     most_recent_tool_calls[tool_name] = {
    #         "arguments": tool_args,
    #         "response": tool_msg,
    #         "status": "completed",
    #         "prompts_after_last_call": 0
    #     }


    #     return {
    #         "tool_execution_history": [tool_msg],
    #         "string_validation": "pass"
    #     }
    # except Exception as e:
    #     tool_msg = ToolMessage(
    #     content=e,
    #     tool_name=tool_name,
    #     tool_call_id=tool_call_id,
    #     )
    #     return {
    #         "tool_execution_history": [tool_msg],
    #         "string_validation": "pass"
    #     }


def execution_logs_node(state: dict):
    print( "I am in execution logs node")
    tool_execution_history = state.get("tool_execution_history", [])

    prompt = f"""You are an intelligent Execution Summarizer for a multi-step tool-calling agent. 
    Your goal is to create a compact, informative summary of the execution so far.

        Guidelines:

        1. Focus on key decisions and entities, such as:
        - Datasources selected for querying (name and ID)
        - Fields chosen for queries along with their metadata insights (data type, dataCategory, etc.)
        - Summary of errors encountered and their corrections
        - Query operations executed

        2. Only include information that has actually happened; do NOT invent fields, decisions, or results.

        3. Maintain continuity of the execution history:
        - Preserve knowledge from previous summaries
        - Update it with the outcomes of tool calls and agent decisions

        4. Be compact and token-efficient:
        - Summarize large outputs like metadata by reporting counts or representative samples
        - Do not repeat unnecessary details

        5. Structure your summary so that it clearly reflects:
        - What the agent decided based on the results
        - How the results influenced the next tool call
        - Any errors and corrections

        6. Output format:
        - A structured JSON
        - Should be suitable for feeding back into the agent as a rolling execution history

        Your task: Generate a rolling summary of all executed actions so far,
        highlighting decisions, selected fields, metadata insights, and errors, while keeping it concise and deterministic.
        
        
        Execution History to Summarize:
        {tool_execution_history}
        """
    # "tool_execution_history": Overwrite([SystemMessage(content="Tool execution history so far:")]),
    # print("last message in tool execution history:", tool_execution_history[-1] if tool_execution_history else "No tool calls yet")
    msg = creative_llm.invoke(prompt)
    ai_message = AIMessage(content="The plan execution logs so far: " + msg.content.strip())
    new_tool_execution_history = [ai_message, tool_execution_history[-1]]

    print("Execution Logs Summary:", new_tool_execution_history)
    print("="*50)
 # Simulate processing time
    return {
        "tool_execution_history": Overwrite(new_tool_execution_history)
    }


async def fetch_query_guidelines(state: dict):
    tool_calls = state.get("tool_calls", [])
    tool_name = tool_calls[0].get("name") if tool_calls else "unknown_tool"
    tool_args = tool_calls[0].get("args", {}) if tool_calls else {}
    tool_call_id = tool_calls[0].get("id") if tool_calls else str(uuid.uuid4())
    # This node would fetch query guidelines and best practices for the identified datasource from a knowledge base or documentation.
    # The output would be a structured set of guidelines that can be used to inform the query construction and execution process.
    tool_result = await get_query_structure_guidelines()
    tool_msg = ToolMessage(
            content=f"Result from tool {tool_name}: {tool_result}",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )

    return {
        "tool_execution_history": [tool_msg]
    }


def handle_incomplete_requests(state: dict):
    print("I am in handle incomplete requests node")

    user_input = state.get("enhanced_input", "")
    implementation_plan = state.get("implementation_plan", "")
    execution_history = state.get("tool_execution_history", [])

    prompt = fprompt = f"""
        You are a senior Business Intelligence Engineer in a large bank.

        A business user asked:
        {user_input}

        We attempted to fulfill the request using the following plan:
        {implementation_plan}

        During execution, these actions were performed:
        {execution_history}

        However, the request could not be completed.

        Instructions:
        - Summarize what was attempted in simple business terms.
        - Explain the issue at a high level (e.g., "processing limitation", "data constraints").
        - Do NOT expose technical details.
        - Do NOT mention tools, system architecture, internal errors, or limits.
        - Maintain a calm, professional tone.
        - Suggest what the user can do next.
        - Keep it concise (8–12 lines max).

        Return only the final response message.
        """

    response = llm.invoke(prompt)

    return {
        "output": response.content
    }

async def list_datasources_tool(state: dict):
    print( "I am in list datasources tool node")
    tool_call_counts = state.get('tool_call_counts')
    count = tool_call_counts.get('list-datasources')
    if count > 2:
        return 
    else:
        tool_calls = state.get("tool_calls", [])
        

    tool_calls = state.get("tool_calls", [])
    if len(tool_calls) > 1:

        return {
            "tool_execution_history": [
                ToolMessage(content="Multiple tool calls detected, please emit one tool call at a time",
                tool_name = 'list-datasources',
                tool_call_id = None)
            ]
        }
    else:
        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id", str(uuid.uuid4()))
    tool_execution_history = state.get("tool_execution_history", [])
    if tool_execution_history:
        tool_execution_history.pop()


    # Keep the displayed tool call id and the ToolMessage.tool_call_id aligned,
    # otherwise the frontend step can remain stuck at "Response: waiting...".
    tool_call = {
        'name': 'list-datasources',
        'args': {'filter': '', 'pageSize': 100, 'limit': 100},
        'id': tool_call_id,
        'type': 'tool_call'
    }
    print("Tool calls to execute:", tool_call)

    ai_msg = AIMessage(content="""In order to get list of all datasources and their descriptions to
                                    identify relevant datasources, the following tool call is executed: """, tool_calls=[tool_call])

    tool_execution_history.append(ai_msg)

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

        tool_execution_history.append(tool_msg)
        return {
            "tool_call_counts": tool_call_counts,
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": Overwrite(tool_execution_history),
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
            "tool_call_counts": tool_call_counts,
            "current_tool_calls": current_tool_calls,
            "most_recent_tool_calls": most_recent_tool_calls,
            "tool_execution_history": [tool_msg],
            "all_datasources": []

        }



async def get_datasource_metadata_tool(state: dict):
    print( "I am in get datasource metadata tool node")
    tool_call_counts = state.get('tool_call_counts')
    count = tool_call_counts.get('get-datasource-metadata')
    if count > 3:
        return 
    else:
        tool_calls = state.get("tool_calls", [])

    tool_calls = state.get("tool_calls", [])
    if len(tool_calls) > 1:
        print("Warning: Multiple tool calls detected. Only the first one will be executed.")

        return {
            "tool_execution_history": [
                ToolMessage(content="Multiple tool calls detected, please emit one tool call at a time",
                tool_name = 'get-datasource-metadata',
                tool_call_id = "")
            ]
        }
    print("Tool calls to execute:", tool_calls)
    if not tool_calls:
        return {
            "tool_execution_history": [
                ToolMessage(content="No tool calls detected in response JSON.",
                tool_name = 'get-datasource-metadata',
                tool_call_id = "")
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



        response_text = tool_result.content[0].text if tool_result and tool_result.content else None
        if isinstance(response_text, str):
            metadata = json.loads(response_text)

        fields = metadata.get("fields", [])
        filtered_fields = {}
        unique_roles = []
        for field in fields:
            role = field.get("role", "")
            name = field.get("name", "")
            data_type = field.get("dataType", "")
            dataCategory = field.get("dataCategory", "")
            if role not in unique_roles:
                unique_roles.append(role)
                filtered_fields[role] = [[name, data_type, dataCategory]]

            else:
                filtered_fields[role].append([name, data_type, dataCategory])
        metadata["fields"] = filtered_fields


        tool_msg = ToolMessage(
            content=metadata,
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
            "tool_call_counts": tool_call_counts,
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
            "tool_call_counts": tool_call_counts,
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
    feedback = state.get("feedback", {})


    msg = creative_llm.invoke(f"""
        You are a Tableau assistant.

        Based on the conversation so far and the user's latest request, generate
        a concise and accurate response for a business user.

        Inputs you can use:
        1. Enhanced user input:
        {enhanced_input}

        2. Final results from tool calls:
        {final_results}

        3. Evaluation feedback for the current response:
        {feedback}

        Instructions:
        - In your final human readable output, do not modify the data retrieved from query results. Just present the results in human readable form.
        - In case of any errors in tool execution, clearly explain to the user what went wrong and what was attempted, but in a non-technical way. 
        - If the tool calls were successful and you have the results, present them in a manner that directly addresses the user's request/business question.
        - If the assistant reply contains fuzzy matches instead of exact user's entered value, clarify that assitant found this, instead of you filtered value.
        - If the assistant reply contains any place holder, then you should not show placeholders, instead gracefully handle that assistant could not retrieve the required information.
        Example of place holders: 'Her **Net Salary** is [Salary value retrieved from the datasource]'
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
    final_response = state.get("output", "")
    original_request = state.get("input", "")
    enhanced_input = state.get("enhanced_input", "")
    is_follow = state.get("follow_up", "False")

    msg = llm.invoke(f"""
            You are an evaluator for a Tableau assistant's response.

            Your task is to evaluate the final response generated by the assistant against the user's original request.

            Inputs you can use:
            1. User's original request:
            {enhanced_input}

            2. Plan that was created for execution to fulfill the user's request:
            {state.get("implementation_plan", "")}

            3. Assistant's final response:
            {final_response}

            Instructions:
            - Focus on whether the final result satisfies the user's intent, NOT on the methodology used.
            - If the assistant tried an alternative approach because the direct approach failed, and the final result is still correct, this should be considered a PASS.
            - In some cases, assistant will be replying with fuzzy matches instead of exact matches which is acceptable. 
            - For example, Clifton Branch => Clifton Karachi, Miss => Ms. , Jhehlam => Jhelum and vice versa.
            - The agent may use creative problem-solving — reward outcomes, not rigid process adherence.
            - If response is satisfactory, respond with "Verdict: pass", nothing else.
            - If not satisfactory, respond with "Verdict: fail" and specify what is missing or incorrect in the response.
            - Determine why final response was not correct and what immediate actions the assistant can take to correct it.
            - For example, if the response is incorrect because of an error in the tool call, then suggest to re-execute the tool call with corrected arguments. 
            - If the response is incorrect because of a wrong interpretation of user intent, then suggest to re-interpret the user intent and adjust the implementation plan accordingly.
            - Respond only in this JSON format and nothing else:

            {{"Verdict": "<Your verdict here>", "evaluation": "<Your evaluation here>" }}
    """)
    # read the JSON response and convert it to a dictionary
    try:
        evaluation = json.loads(msg.content)
    except json.JSONDecodeError:
        evaluation = {"Verdict": "fail", "evaluation": "LLM response could not be parsed as JSON. Please ensure the evaluator node responds with valid JSON."}
    print("Evaluation result:", evaluation)
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

