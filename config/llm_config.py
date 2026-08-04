from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.embeddings import DashScopeEmbeddings
from .settings import settings


def get_llm() -> BaseChatModel:
    """统一获取OpenAI兼容对话大模型，适配通义、OpenAI、Ollama、DeepSeek等"""
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL_NAME,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )


def get_embedding() -> Embeddings:
    """统一OpenAI格式向量模型；不单独配置则复用LLM的key和地址"""
    embed_key = settings.EMBED_API_KEY
    embed_model = settings.EMBED_MODEL_NAME

    return DashScopeEmbeddings(dashscope_api_key=embed_key, model=embed_model)
