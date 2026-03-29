from __future__ import annotations

from backend.config.env_provider import build_env_translation_provider


# Compatibility shim: the app now reads translation API settings from environment variables.
def build_hardcoded_translation_provider():
    return build_env_translation_provider()
