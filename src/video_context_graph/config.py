"""Application configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    twelvelabs_api_key: str = ""
    twelvelabs_index_id: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: str = "low"
    neo4j_uri: str = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    app_data_dir: str = "./data"
    app_max_video_mb: int = 200
    app_max_video_minutes: int = 15
    app_graph_node_limit: int = 100
    app_search_top_k: int = 5
    app_use_fixtures: bool = False
    app_log_level: str = "INFO"
    pipeline_version: str = Field(default="v1")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
