from __future__ import annotations

import importlib
import importlib.metadata
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_settings = importlib.import_module("src.config").load_settings

REQUIRED_PACKAGES = (
    "anthropic",
    "pydantic",
    "python-dotenv",
    "reportlab",
    "streamlit",
)


def main() -> int:
    settings = load_settings()
    print(f"Python version supported: {sys.version_info >= (3, 12)}")
    print(f"Anthropic API key available: {settings.api_key_configured}")
    print(f"Research model: {settings.research_model}")
    print(f"Web search tool: {settings.web_search_tool}")

    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            version = importlib.metadata.version(package)
            print(f"{package}: {version}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            print(f"{package}: NOT INSTALLED")

    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Cache directory writable: {settings.cache_dir.exists()}")
    print(f"Output directory writable: {settings.output_dir.exists()}")

    if not settings.api_key_configured or missing:
        print("Setup check failed.")
        return 1
    print("Setup check passed. The API key value was not displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
