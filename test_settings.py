from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

class EmbeddingSettings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }

    backend: str = Field(default="openai")

s = EmbeddingSettings()
print(f"Backend: {s.backend}")

# 尝试显式传入环境变量
import os
backend_env = os.getenv("EMBEDDING_BACKEND")
print(f"ENV EMBEDDING_BACKEND: {backend_env}")

# 尝试使用env参数
class EmbeddingSettings2(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_prefix": "",
        "case_sensitive": False
    }

    EMBEDDING_BACKEND: str = "openai"

s2 = EmbeddingSettings2()
print(f"Backend2: {s2.EMBEDDING_BACKEND}")
