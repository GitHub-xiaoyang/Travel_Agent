from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # 基础项目配置
    PROJECT_NAME: str = "Travel Agent Platform"
    DEBUG: bool = True

    # ========== 统一OpenAI兼容大模型配置（所有模型共用） ==========
    LLM_API_KEY: str
    LLM_BASE_URL: str | None = None
    LLM_MODEL_NAME: str = "qwen3.7-plus"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000

    # 向量Embedding 同套接口复用
    EMBED_API_KEY: str | None = None
    EMBED_BASE_URL: str | None = None
    EMBED_MODEL_NAME: str = "text-embedding-v4"

    # Agent限制
    MAX_TOOL_CALL_TIMES: int = 8

    # ========== 第三方业务API ==========
    AMAP_API_KEY: str | None = None
    AMAP_JS_API_KEY: str | None = None  # Web端JS Key（前端地图/搜索/定位，与AMAP_API_KEY不同）
    AMAP_JS_SECURITY_CODE: str | None = None  # Web端JS Key的安全密钥（AMap控制台获取）
    HEFENG_WEATHER_KEY: str | None = None

    # ========== 路径配置 ==========
    CHROMA_DB_PATH: Path = BASE_DIR / "data" / "chroma_db"
    KNOWLEDGE_PATH: Path = BASE_DIR / "data" / "travel_knowledge"
    TEMP_EXPORT_PATH: Path = BASE_DIR / "data" / "temp_export"
    LOG_PATH: Path = BASE_DIR / "logs"

    def create_all_dirs(self):
        dir_list = [
            self.CHROMA_DB_PATH,
            self.KNOWLEDGE_PATH,
            self.TEMP_EXPORT_PATH,
            self.LOG_PATH,
        ]
        for dir_path in dir_list:
            dir_path.mkdir(exist_ok=True, parents=True)


settings = AppSettings()
settings.create_all_dirs()