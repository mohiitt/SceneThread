"""Basic local health check for required configuration, including the local .env."""

from __future__ import annotations

from video_context_graph.config import Settings

REQUIRED_ENV_VARS = (
    "TWELVELABS_API_KEY",
    "OPENAI_API_KEY",
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
)


def missing_env_vars(settings: Settings | None = None) -> list[str]:
    configured = settings or Settings()
    values = {
        "TWELVELABS_API_KEY": configured.twelvelabs_api_key,
        "OPENAI_API_KEY": configured.openai_api_key,
        "NEO4J_URI": configured.neo4j_uri,
        "NEO4J_USERNAME": configured.neo4j_username,
        "NEO4J_PASSWORD": configured.neo4j_password,
    }
    return [name for name in REQUIRED_ENV_VARS if not values[name]]


def main() -> None:
    missing = missing_env_vars()
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required environment variables: {joined}")
    print("SceneThread health check passed.")


if __name__ == "__main__":
    main()
