from langchain_openai import AzureChatOpenAI
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


# Load .env
load_dotenv(r"C:\Langgraph Agent\.env")

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

intent_classifier_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY"),
)



intent_classifier_llm = intent_classifier_llm.with_structured_output(
    method="json_schema",
    schema={
        "title": "intent_classification_schema",
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "Single word representing the classified user intent"
            }
        },
        "required": ["intent"],
        "additionalProperties": False
    },
    strict=True
)




slightly_creative_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY")
)


creative_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY")
)


reasoning_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY"),

)

reasoning_expert_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY"),

)


# reasoning_llm = reasoning_llm.with_structured_output(
#     method="json_schema",
#     schema={
#         "title": "tool_call_schema",
#         "type": "object",
#         "properties": {
#             "name": {
#                 "type": "string",
#                 "enum": ["query-datasource"]
#             },
#             "args": {
#                 "type": "object",
#                 "properties": {
#                     "datasourceLuid": {
#                         "type": "string"
#                     },
#                     "query": {
#                         "type": "string",
#                         "description": "Serialized JSON string of Tableau query"
#                     },
#                     "limit": {
#                         "type": "integer"
#                     }
#                 },
#                 "required": ["datasourceLuid", "query", "limit"]
#             },
#             "id": {
#                 "type": "string"
#             },
#             "type": {
#                 "type": "string",
#                 "enum": ["tool_call"]
#             }
#         },
#         "required": ["name", "args", "id", "type"]
#     },
#     strict=True
# )







executor_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    temperature=0,
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version= "2024-12-01-preview",
    api_key=os.getenv("OPENAI_API_KEY"),
).with_structured_output(
    method="json_schema",
    schema={
        "title": "ExecutorOutput",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["tool_call", "final_answer"]
            },
            "internal_reasoning": {
                "type": "string",
                "description": "Step-by-step reasoning used for execution and retries."
            },
            "tool_call": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": [
                            "list-datasources",
                            "get-datasource-metadata",
                            "query-datasource",
                            "get_query_structure_guidelines"
                        ]
                    },
                    "args": {
                        "type": "object",
                        "description": "Arguments for the tool ({} if tool requires none).",
                        "additionalProperties": False
                    }
                },
                "required": ["name", "args"]  # only name required
            },
            "final_message": {
                "type": "string",
                "description": "Final human-readable message when task is done and no more tool calls are pending."
            }
        },
        "required": ["mode", "internal_reasoning"],
    },
    strict=True
)