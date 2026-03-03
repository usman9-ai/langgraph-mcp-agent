from langchain_openai import AzureChatOpenAI
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(r"C:\Langgraph Agent\.env")

llm = AzureChatOpenAI(
    # Use azure_deployment instead of deployment_name
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    temperature=0,
    # Direct arguments instead of model_kwargs
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY")
)

slightly_creative_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    temperature=0.2,
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY")
)


creative_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("OPENAI_CHAT_DEPLOYMENT"),
    temperature=0.4,
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=os.getenv("OPENAI_API_KEY")
)
