import asyncio
from fastmcp import Client
from langchain_core.tools import StructuredTool

from pydantic import create_model
import asyncio
from pydantic import BaseModel

class GetQueryStructureGuidelines(BaseModel):
    pass


async def get_query_structure_guidelines():
    with open("C:\\Langgraph Agent\\my_agent_v2\\utils\\query_rules_v2.txt", "r") as f:
        qds_description = f.read()
    return qds_description

def convert_tools_to_llm_functions(mcp_tools):
    llm_functions = {}
    for tool in mcp_tools:
        tool_info = {}
        if hasattr(tool, "dict"):
            tool = tool.dict()
            # print("Converted tool to dict:", tool)
            for key, value in tool.items():
                if value is not None:
                    tool_info[key] = value
            

        llm_functions[tool_info['name']] = tool_info

    tool_info = {
        "name": "get_query_structure_guidelines",
        "description": """Retrieves query structure guidelines for proper usage 
            of 'query-datasource' tool. Must refer to if before calling 'query-datasource' 
            to ensure correct query construction and avoid errors.""",
        "inputSchema": None}
    llm_functions['get_query_structure_guidelines'] = tool_info
    return llm_functions

def get_tool_descriptions(tool_list):
    allowed_tools = ["list-datasources", "get-datasource-metadata", "query-datasource"]
    custom_tool_name = "get_query_structure_guidelines"
    custom_tool_description = """Retrieves query structure guidelines for proper usage 
            of 'query-datasource' tool. Must refer to if before calling 'query-datasource' 
            to ensure correct query construction and avoid errors."""

    descriptions = []
    for tool in tool_list:
        if tool.name not in allowed_tools:
            continue

        if tool.name == 'list-datasources':
            tool.description = "Lists all available datasources in the Tableau environment. No input parameters are required for this tool."
        elif tool.name == 'get-datasource-metadata':
            tool.description = "Retrieves metadata for a specific datasource in Tableau. Input parameter: datasource_id."
        elif tool.name == 'query-datasource':
            with open("my_agent_v2/utils/QDS_Description_for_planning.txt", "r") as f:
                qds_description = f.read()
            tool.description = qds_description


        # Access attributes directly from the Tool object
        desc = f"Tool Name: {tool.name}\nDescription: {tool.description}\n"
        descriptions.append(desc)
    desc = f"Tool Name: {custom_tool_name}\nDescription: {custom_tool_description}\n"
    descriptions.append(desc)
    return "\n".join(descriptions)



def convert_mcp_tools_to_langchain_tools(mcp_tools, mcp_url):
    # allowed_tools = ["list-datasources", "get-datasource-metadata", "query-datasource", "get-workbook", "get-view-data",
    #                  "get-view-image","list-workbooks", "list-views"]

    allowed_tools = ["list-datasources", "get-datasource-metadata", "query-datasource"]
    langchain_tools = []

    for tool in mcp_tools:
        # Convert object to dict if needed
        if hasattr(tool, "dict"):
            tool = tool.dict()

        tool_name = tool.get("name")

        if tool_name not in allowed_tools:
            continue
        
        if tool_name == 'list-datasources':
            tool["description"] = "Lists all available datasources in the Tableau environment. No input parameters are required for this tool."
        elif tool_name == 'get-datasource-metadata':
            tool["description"] = "Retrieves metadata for a specific datasource in Tableau. Input parameter: datasource_id."
        elif tool_name == 'query-datasource':
            with open("my_agent_v2/utils/QDS_Description_for_planning.txt", "r") as f:
                qds_description = f.read()
            tool["description"] = qds_description

        description = tool.get("description", "")
        schema = tool.get("inputSchema", {})

        fields = {}
        properties = schema.get("properties", {})

        for field_name, field_info in properties.items():
            field_type = str
            if field_info.get("type") == "integer":
                field_type = int
            elif field_info.get("type") == "number":
                field_type = float
            elif field_info.get("type") == "boolean":
                field_type = bool

            fields[field_name] = (field_type, ...)

        ArgsModel = create_model(f"{tool_name}_args", **fields)

        # IMPORTANT: closure fix
        def make_tool_func(tool_name):

            async def tool_func(**kwargs):
                return await call_mcp_tool(tool_name, kwargs, mcp_url)

            return tool_func

        tool_func = make_tool_func(tool_name)

        structured_tool = StructuredTool.from_function(
            name=tool_name,
            description=description,
            args_schema=ArgsModel,
            coroutine=tool_func
        )
        # print("structured_tool:", structured_tool)

        langchain_tools.append(structured_tool)

    return langchain_tools


async def initialize_tools(mcp_url: str):
    async with Client(mcp_url) as mcp_client:
        tools = await mcp_client.list_tools()
        # llm_functions = convert_tools_to_llm_functions(tools)
        mcp_tool_descriptions = get_tool_descriptions(tools)
        langchain_tools = convert_mcp_tools_to_langchain_tools(tools, mcp_url)



        custom_tool = StructuredTool.from_function(
            name="get_query_structure_guidelines",
            description="""Retrieves query structure guidelines for proper usage 
            of 'query-datasource' tool. Must refer to if before calling 'query-datasource' 
            to ensure correct query construction and avoid errors.""",
            args_schema=GetQueryStructureGuidelines,
            coroutine=get_query_structure_guidelines
        )

        langchain_tools.append(custom_tool)
        return mcp_tool_descriptions, langchain_tools

MCP_URL = "http://localhost:3927/tableau-mcp"

# Use asyncio.run to actually await the coroutine
# mcp_tool_descriptions, langchain_tools = asyncio.run(initialize_tools(MCP_URL))

