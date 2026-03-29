from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from backend.benchmark.override_suggestions import (
    BenchmarkOverrideSuggestionReport,
    suggest_runtime_profile_overrides as build_override_suggestion_report,
)


@dataclass(slots=True, frozen=True)
class BenchmarkOverrideSuggestionArtifacts:
    json_path: Path
    markdown_path: Path
    report: BenchmarkOverrideSuggestionReport


def suggest_runtime_profile_overrides(
    *,
    report_paths: list[str],
    output_dir: str | Path | None = None,
    suggestion_name: str | None = None,
    fallback_base_url: str | None = None,
) -> BenchmarkOverrideSuggestionArtifacts:
    report = build_override_suggestion_report(
        report_paths,
        fallback_base_url=fallback_base_url,
    )
    normalized_output_dir = Path(
        output_dir or Path("temp") / "benchmark_override_suggestions"
    ).resolve()
    normalized_output_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    suggestion_title = suggestion_name or f"override-suggestions-{run_id}"
    json_path = normalized_output_dir / f"{run_id}.json"
    markdown_path = normalized_output_dir / f"{run_id}.md"
    payload = {
        "suggestion_name": suggestion_title,
        **report.to_dict(),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        "\n".join(
            [
                f"# {suggestion_title}",
                "",
                report.render_markdown(),
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )
    return BenchmarkOverrideSuggestionArtifacts(
        json_path=json_path,
        markdown_path=markdown_path,
        report=report,
    )
