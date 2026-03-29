from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, frozen=True)
class RuntimeProfileOverrideEntry:
    target_key: str
    provider_name: str
    model_name: str
    base_url: str
    runtime_profile: str
    source: str = "endpoint_capability_detection"
    evidence: dict[str, Any] | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeProfileOverrideEntry":
        return cls(
            target_key=str(data.get("target_key") or ""),
            provider_name=str(data.get("provider_name") or ""),
            model_name=str(data.get("model_name") or ""),
            base_url=str(data.get("base_url") or ""),
            runtime_profile=str(data.get("runtime_profile") or ""),
            source=str(data.get("source") or "endpoint_capability_detection"),
            evidence=(
                dict(data["evidence"])
                if isinstance(data.get("evidence"), dict)
                else None
            ),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checkpoint_version"] = 1
        return payload


class RuntimeProfileOverrideStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def build_target_key(
        *,
        model_name: str,
        base_url: str,
    ) -> str:
        normalized_model_name = str(model_name or "").strip().lower()
        normalized_base_url = str(base_url or "").strip().lower().rstrip("/")
        if not normalized_model_name or not normalized_base_url:
            return ""
        return f"{normalized_model_name}@{normalized_base_url}"

    @staticmethod
    def build_cache_key(target_key: str) -> str:
        normalized_target_key = str(target_key or "").strip().lower()
        if not normalized_target_key:
            normalized_target_key = "runtime-profile-override"
        return hashlib.sha256(normalized_target_key.encode("utf-8")).hexdigest()

    def load(
        self,
        *,
        model_name: str,
        base_url: str,
    ) -> RuntimeProfileOverrideEntry | None:
        target_key = self.build_target_key(model_name=model_name, base_url=base_url)
        if not target_key:
            return None
        path = self.snapshot_path(target_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        entry = RuntimeProfileOverrideEntry.from_dict(data)
        if entry.target_key != target_key:
            return None
        if not entry.runtime_profile:
            return None
        return entry

    def save(self, entry: RuntimeProfileOverrideEntry) -> Path:
        path = self.snapshot_path(entry.target_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomically(path, entry.to_dict())
        return path

    def upsert(
        self,
        *,
        provider_name: str,
        model_name: str,
        base_url: str,
        runtime_profile: str,
        source: str = "endpoint_capability_detection",
        evidence: dict[str, Any] | None = None,
    ) -> RuntimeProfileOverrideEntry | None:
        target_key = self.build_target_key(model_name=model_name, base_url=base_url)
        normalized_runtime_profile = str(runtime_profile or "").strip().lower()
        if not target_key or not normalized_runtime_profile:
            return None
        existing = self.load(model_name=model_name, base_url=base_url)
        now_iso = _now().isoformat()
        entry = RuntimeProfileOverrideEntry(
            target_key=target_key,
            provider_name=str(provider_name or "").strip().lower(),
            model_name=str(model_name or "").strip().lower(),
            base_url=str(base_url or "").strip().rstrip("/"),
            runtime_profile=normalized_runtime_profile,
            source=str(source or "endpoint_capability_detection").strip()
            or "endpoint_capability_detection",
            evidence=dict(evidence) if evidence else None,
            created_at=existing.created_at or now_iso if existing is not None else now_iso,
            updated_at=now_iso,
        )
        self.save(entry)
        return entry

    def snapshot_path(self, target_key: str) -> Path:
        cache_key = self.build_cache_key(target_key)
        return self.root / f"{cache_key}.json"

    @staticmethod
    def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        last_error: PermissionError | None = None
        for attempt in range(5):
            try:
                temp_path.replace(path)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt >= 4:
                    break
                time.sleep(0.01 * (attempt + 1))

        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        if last_error is not None:
            raise last_error
