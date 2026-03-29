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
class EndpointCapabilitySnapshot:
    cache_key: str
    provider_name: str
    models_endpoint: str
    api_key_fingerprint: str
    model_name: str = ""
    model_listed: bool | None = None
    model_object: dict[str, Any] | None = None
    available_model_count: int | None = None
    probe_status: str = "ok"
    error_summary: str | None = None
    models_probe_status: str = "ok"
    models_error_summary: str | None = None
    verified_capabilities: dict[str, Any] | None = None
    verified_capability_metadata: dict[str, Any] | None = None
    retrieved_at: str = ""
    expires_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EndpointCapabilitySnapshot":
        return cls(
            cache_key=str(data.get("cache_key") or ""),
            provider_name=str(data.get("provider_name") or ""),
            models_endpoint=str(data.get("models_endpoint") or ""),
            api_key_fingerprint=str(data.get("api_key_fingerprint") or ""),
            model_name=str(data.get("model_name") or ""),
            model_listed=(
                bool(data.get("model_listed"))
                if data.get("model_listed") is not None
                else None
            ),
            model_object=(
                dict(data["model_object"])
                if isinstance(data.get("model_object"), dict)
                else None
            ),
            available_model_count=(
                int(data["available_model_count"])
                if data.get("available_model_count") is not None
                else None
            ),
            probe_status=str(data.get("probe_status") or "ok"),
            error_summary=(
                str(data["error_summary"])
                if data.get("error_summary") is not None
                else None
            ),
            models_probe_status=str(
                data.get("models_probe_status")
                or data.get("probe_status")
                or "ok"
            ),
            models_error_summary=(
                str(data["models_error_summary"])
                if data.get("models_error_summary") is not None
                else (
                    str(data["error_summary"])
                    if data.get("error_summary") is not None
                    else None
                )
            ),
            verified_capabilities=(
                dict(data["verified_capabilities"])
                if isinstance(data.get("verified_capabilities"), dict)
                else None
            ),
            verified_capability_metadata=(
                dict(data["verified_capability_metadata"])
                if isinstance(data.get("verified_capability_metadata"), dict)
                else None
            ),
            retrieved_at=str(data.get("retrieved_at") or ""),
            expires_at=str(data.get("expires_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checkpoint_version"] = 1
        return payload

    def is_fresh(self) -> bool:
        if not self.expires_at:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) > _now()
        except ValueError:
            return False


class EndpointCapabilityStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def build_cache_key(
        *,
        provider_name: str,
        models_endpoint: str,
        api_key: str,
        model_name: str,
    ) -> str:
        payload = "|".join(
            [
                str(provider_name or "").strip().lower(),
                str(models_endpoint or "").strip().lower(),
                EndpointCapabilityStore.api_key_fingerprint(api_key),
                str(model_name or "").strip().lower(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def api_key_fingerprint(api_key: str) -> str:
        normalized = str(api_key or "").strip()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def load(self, cache_key: str) -> EndpointCapabilitySnapshot | None:
        path = self.snapshot_path(cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return EndpointCapabilitySnapshot.from_dict(data)

    def save(self, snapshot: EndpointCapabilitySnapshot) -> Path:
        path = self.snapshot_path(snapshot.cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomically(path, snapshot.to_dict())
        return path

    def snapshot_path(self, cache_key: str) -> Path:
        return self.root / f"{str(cache_key).strip().lower() or 'endpoint-capability'}.json"

    @staticmethod
    def build_snapshot(
        *,
        provider_name: str,
        models_endpoint: str,
        api_key: str,
        model_name: str,
        model_listed: bool | None,
        model_object: dict[str, Any] | None = None,
        available_model_count: int | None = None,
        probe_status: str,
        ttl_seconds: int,
        error_summary: str | None = None,
        models_probe_status: str = "ok",
        models_error_summary: str | None = None,
        verified_capabilities: dict[str, Any] | None = None,
        verified_capability_metadata: dict[str, Any] | None = None,
    ) -> EndpointCapabilitySnapshot:
        cache_key = EndpointCapabilityStore.build_cache_key(
            provider_name=provider_name,
            models_endpoint=models_endpoint,
            api_key=api_key,
            model_name=model_name,
        )
        now = _now()
        expires_at = now.timestamp() + max(1, int(ttl_seconds))
        return EndpointCapabilitySnapshot(
            cache_key=cache_key,
            provider_name=str(provider_name or "").strip().lower(),
            models_endpoint=str(models_endpoint or "").strip(),
            api_key_fingerprint=EndpointCapabilityStore.api_key_fingerprint(api_key),
            model_name=str(model_name or "").strip().lower(),
            model_listed=model_listed,
            model_object=dict(model_object) if model_object is not None else None,
            available_model_count=(
                int(available_model_count)
                if available_model_count is not None
                else None
            ),
            probe_status=str(probe_status or "ok"),
            error_summary=(str(error_summary).strip() or None) if error_summary is not None else None,
            models_probe_status=str(models_probe_status or "ok"),
            models_error_summary=(
                (str(models_error_summary).strip() or None)
                if models_error_summary is not None
                else None
            ),
            verified_capabilities=(
                dict(verified_capabilities) if verified_capabilities is not None else None
            ),
            verified_capability_metadata=(
                dict(verified_capability_metadata)
                if verified_capability_metadata is not None
                else None
            ),
            retrieved_at=now.isoformat(),
            expires_at=datetime.fromtimestamp(expires_at, UTC).isoformat(),
        )

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
