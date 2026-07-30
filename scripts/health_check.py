"""Basic local health check for required configuration."""

from __future__ import annotations

import os


REQUIRED_ENV_VARS = (
    "TWELVELABS_API_KEY",
    "OPENAI_API_KEY",
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
)


def missing_env_vars() -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]


def main() -> None:
    missing = missing_env_vars()
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required environment variables: {joined}")
    print("SceneThread health check passed.")


if __name__ == "__main__":
    main()
