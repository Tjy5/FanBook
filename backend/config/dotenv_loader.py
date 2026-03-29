from __future__ import annotations

import os
from pathlib import Path


def default_dotenv_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def load_project_dotenv(
    *,
    env_path: str | Path | None = None,
    override: bool = False,
) -> Path | None:
    path = Path(env_path) if env_path is not None else default_dotenv_path()
    resolved_path = path.resolve()
    if not resolved_path.is_file():
        return None

    for raw_line in resolved_path.read_text(encoding="utf-8-sig").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue

        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value

    return resolved_path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[7:].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    normalized_key = key.strip()
    if not normalized_key:
        return None

    normalized_value = value.strip()
    if (
        len(normalized_value) >= 2
        and normalized_value[0] == normalized_value[-1]
        and normalized_value[0] in {"'", '"'}
    ):
        normalized_value = normalized_value[1:-1]
    elif " #" in normalized_value:
        normalized_value = normalized_value.split(" #", 1)[0].rstrip()

    return normalized_key, normalized_value
