from __future__ import annotations

import json
import re
import shutil
import time
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_chunk_filename(chunk_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(chunk_id).strip())
    return normalized or "chunk"


@dataclass(slots=True, frozen=True)
class JobCheckpointSnapshot:
    job_id: int
    book_id: int
    status: str
    provider_profile_name: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    progress: float = 0.0
    translated_segments: int = 0
    total_segments: int = 0
    runtime_settings: dict[str, Any] | None = None
    error_summary: str | None = None
    checkpoint_reason: str = "heartbeat"
    thread_name: str | None = None
    created_at: str = ""
    updated_at: str = ""
    finished_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobCheckpointSnapshot":
        created_at = str(data.get("created_at") or "")
        updated_at = str(data.get("updated_at") or created_at or _now_iso())
        return cls(
            job_id=int(data.get("job_id") or 0),
            book_id=int(data.get("book_id") or 0),
            status=str(data.get("status") or "pending"),
            provider_profile_name=(
                str(data["provider_profile_name"])
                if data.get("provider_profile_name") is not None
                else None
            ),
            provider_name=(
                str(data["provider_name"])
                if data.get("provider_name") is not None
                else None
            ),
            model_name=(
                str(data["model_name"]) if data.get("model_name") is not None else None
            ),
            progress=float(data.get("progress") or 0.0),
            translated_segments=int(data.get("translated_segments") or 0),
            total_segments=int(data.get("total_segments") or 0),
            runtime_settings=(
                dict(data["runtime_settings"])
                if isinstance(data.get("runtime_settings"), dict)
                else None
            ),
            error_summary=(
                str(data["error_summary"])
                if data.get("error_summary") is not None
                else None
            ),
            checkpoint_reason=str(data.get("checkpoint_reason") or "heartbeat"),
            thread_name=(
                str(data["thread_name"]) if data.get("thread_name") is not None else None
            ),
            created_at=created_at or updated_at,
            updated_at=updated_at,
            finished_at=(
                str(data["finished_at"]) if data.get("finished_at") is not None else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checkpoint_version"] = 2
        return payload


@dataclass(slots=True, frozen=True)
class ChunkCheckpointSnapshot:
    chunk_id: str
    job_id: int
    book_id: int
    chapter_id: int
    segment_ids: tuple[int, ...]
    sequence_no: int
    status: str
    attempt_count: int = 0
    segment_count: int = 0
    source_char_count: int = 0
    estimated_tokens: int = 0
    fallback_count: int = 0
    provider_name: str | None = None
    model_name: str | None = None
    term_snapshot_version: str | None = None
    last_error: str | None = None
    failure_reason_code: str | None = None
    fallback_reason_code: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkCheckpointSnapshot":
        created_at = str(data.get("created_at") or "")
        updated_at = str(data.get("updated_at") or created_at or _now_iso())
        raw_segment_ids = data.get("segment_ids") or []
        segment_ids = tuple(int(item) for item in raw_segment_ids if item is not None)
        return cls(
            chunk_id=str(data.get("chunk_id") or ""),
            job_id=int(data.get("job_id") or 0),
            book_id=int(data.get("book_id") or 0),
            chapter_id=int(data.get("chapter_id") or 0),
            segment_ids=segment_ids,
            sequence_no=int(data.get("sequence_no") or 0),
            status=str(data.get("status") or "pending"),
            attempt_count=int(data.get("attempt_count") or 0),
            segment_count=int(data.get("segment_count") or len(segment_ids)),
            source_char_count=int(data.get("source_char_count") or 0),
            estimated_tokens=int(data.get("estimated_tokens") or 0),
            fallback_count=int(data.get("fallback_count") or 0),
            provider_name=(
                str(data["provider_name"]) if data.get("provider_name") is not None else None
            ),
            model_name=(
                str(data["model_name"]) if data.get("model_name") is not None else None
            ),
            term_snapshot_version=(
                str(data["term_snapshot_version"])
                if data.get("term_snapshot_version") is not None
                else None
            ),
            last_error=(
                str(data["last_error"]) if data.get("last_error") is not None else None
            ),
            failure_reason_code=(
                str(data["failure_reason_code"])
                if data.get("failure_reason_code") is not None
                else None
            ),
            fallback_reason_code=(
                str(data["fallback_reason_code"])
                if data.get("fallback_reason_code") is not None
                else None
            ),
            created_at=created_at or updated_at,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checkpoint_version"] = 2
        return payload


class CheckpointStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()

    def save(self, snapshot: JobCheckpointSnapshot) -> Path:
        with self._write_lock:
            checkpoint_path = self.checkpoint_path(snapshot.job_id)
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_json_atomically(checkpoint_path, snapshot.to_dict())
            return checkpoint_path

    def save_state(
        self,
        *,
        job_id: int,
        book_id: int,
        status: str,
        provider_profile_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        progress: float = 0.0,
        translated_segments: int = 0,
        total_segments: int = 0,
        runtime_settings: dict[str, Any] | None = None,
        error_summary: str | None = None,
        checkpoint_reason: str = "heartbeat",
        thread_name: str | None = None,
        finished_at: str | None = None,
    ) -> JobCheckpointSnapshot:
        with self._write_lock:
            previous = self.load(job_id)
            now = _now_iso()
            snapshot = JobCheckpointSnapshot(
                job_id=int(job_id),
                book_id=int(book_id),
                status=str(status),
                provider_profile_name=(
                    provider_profile_name
                    if provider_profile_name is not None
                    else (previous.provider_profile_name if previous is not None else None)
                ),
                provider_name=provider_name,
                model_name=model_name,
                progress=float(progress),
                translated_segments=int(translated_segments),
                total_segments=int(total_segments),
                runtime_settings=(
                    dict(runtime_settings)
                    if runtime_settings is not None
                    else (
                        dict(previous.runtime_settings)
                        if previous is not None and previous.runtime_settings is not None
                        else None
                    )
                ),
                error_summary=error_summary,
                checkpoint_reason=checkpoint_reason,
                thread_name=thread_name,
                created_at=previous.created_at if previous is not None else now,
                updated_at=now,
                finished_at=finished_at,
            )
            self.save(snapshot)
            return snapshot

    def save_chunk(self, job_id: int, snapshot: ChunkCheckpointSnapshot) -> Path:
        with self._write_lock:
            chunk_path = self.chunk_path(job_id, snapshot.chunk_id)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_json_atomically(chunk_path, snapshot.to_dict())
            return chunk_path

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

    def save_chunk_state(
        self,
        *,
        job_id: int,
        chunk_id: str,
        book_id: int,
        chapter_id: int,
        segment_ids: tuple[int, ...] | list[int],
        sequence_no: int,
        status: str,
        attempt_count: int = 0,
        segment_count: int | None = None,
        source_char_count: int | None = None,
        estimated_tokens: int | None = None,
        fallback_count: int | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        term_snapshot_version: str | None = None,
        last_error: str | None = None,
        failure_reason_code: str | None = None,
        fallback_reason_code: str | None = None,
    ) -> ChunkCheckpointSnapshot:
        with self._write_lock:
            previous = self.load_chunk(job_id, chunk_id)
            now = _now_iso()
            resolved_fallback_count = int(
                fallback_count
                if fallback_count is not None
                else (previous.fallback_count if previous is not None else 0)
            )
            snapshot = ChunkCheckpointSnapshot(
                chunk_id=str(chunk_id),
                job_id=int(job_id),
                book_id=int(book_id),
                chapter_id=int(chapter_id),
                segment_ids=tuple(int(item) for item in segment_ids),
                sequence_no=int(sequence_no),
                status=str(status),
                attempt_count=int(attempt_count),
                segment_count=int(
                    segment_count
                    if segment_count is not None
                    else (previous.segment_count if previous is not None else len(segment_ids))
                ),
                source_char_count=int(
                    source_char_count
                    if source_char_count is not None
                    else (previous.source_char_count if previous is not None else 0)
                ),
                estimated_tokens=int(
                    estimated_tokens
                    if estimated_tokens is not None
                    else (previous.estimated_tokens if previous is not None else 0)
                ),
                fallback_count=resolved_fallback_count,
                provider_name=provider_name,
                model_name=model_name,
                term_snapshot_version=term_snapshot_version,
                last_error=last_error,
                failure_reason_code=(
                    failure_reason_code
                    if failure_reason_code is not None
                    else (
                        previous.failure_reason_code
                        if previous is not None and str(status) == "failed"
                        else None
                    )
                ),
                fallback_reason_code=(
                    fallback_reason_code
                    if fallback_reason_code is not None
                    else (
                        previous.fallback_reason_code
                        if previous is not None and resolved_fallback_count > 0
                        else None
                    )
                ),
                created_at=previous.created_at if previous is not None else now,
                updated_at=now,
            )
            self.save_chunk(job_id, snapshot)
            return snapshot

    def load(self, job_id: int) -> JobCheckpointSnapshot | None:
        checkpoint_path = self.checkpoint_path(job_id)
        if not checkpoint_path.exists():
            return None
        try:
            raw = checkpoint_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return JobCheckpointSnapshot.from_dict(data)

    def load_chunk(self, job_id: int, chunk_id: str) -> ChunkCheckpointSnapshot | None:
        chunk_path = self.chunk_path(job_id, chunk_id)
        if not chunk_path.exists():
            return None
        try:
            raw = chunk_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return ChunkCheckpointSnapshot.from_dict(data)

    def list_chunks(self, job_id: int) -> tuple[ChunkCheckpointSnapshot, ...]:
        chunk_root = self.chunks_dir(job_id)
        if not chunk_root.exists():
            return ()
        snapshots: list[ChunkCheckpointSnapshot] = []
        for path in sorted(chunk_root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                snapshots.append(ChunkCheckpointSnapshot.from_dict(data))
        return tuple(snapshots)

    def list_job_ids(self) -> tuple[int, ...]:
        job_ids: list[int] = []
        checkpoints_root = self.root / "checkpoints"
        if not checkpoints_root.exists():
            return ()
        for entry in checkpoints_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                job_ids.append(int(entry.name))
            except ValueError:
                continue
        return tuple(sorted(job_ids))

    def clear(self, job_id: int) -> None:
        with self._write_lock:
            checkpoint_dir = self.job_dir(job_id)
            if checkpoint_dir.exists():
                shutil.rmtree(checkpoint_dir, ignore_errors=True)

    def clear_chunks(self, job_id: int) -> None:
        with self._write_lock:
            chunks_dir = self.chunks_dir(job_id)
            if chunks_dir.exists():
                shutil.rmtree(chunks_dir, ignore_errors=True)

    def job_dir(self, job_id: int) -> Path:
        return self.root / "checkpoints" / str(int(job_id))

    def checkpoint_path(self, job_id: int) -> Path:
        return self.job_dir(job_id) / "state.json"

    def chunks_dir(self, job_id: int) -> Path:
        return self.job_dir(job_id) / "chunks"

    def chunk_path(self, job_id: int, chunk_id: str) -> Path:
        return self.chunks_dir(job_id) / f"{_safe_chunk_filename(chunk_id)}.json"
