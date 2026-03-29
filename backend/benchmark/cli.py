from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

from backend.benchmark.baseline_summary import summarize_benchmark_baselines
from backend.benchmark.override_suggestions import suggest_runtime_profile_overrides
from backend.benchmark.runner import run_translation_benchmark
from backend.domain.enums import ExportArtifactKind

_BENCHMARK_EXPORT_KINDS = (
    ExportArtifactKind.ZH,
    ExportArtifactKind.BILINGUAL,
)


def main(argv: list[str] | None = None) -> int:
    normalized_argv = list(argv if argv is not None else sys.argv[1:])
    if normalized_argv and normalized_argv[0] == "suggest-overrides":
        return _main_suggest_overrides(normalized_argv[1:])
    if normalized_argv and normalized_argv[0] == "summarize-baselines":
        return _main_summarize_baselines(normalized_argv[1:])
    return _main_run_benchmark(normalized_argv)


def _main_run_benchmark(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run a local Fanbook translation benchmark.")
    parser.add_argument("epub_path", help="Path to the EPUB file to benchmark.")
    parser.add_argument(
        "--runtime-root",
        default=str(Path("temp") / "benchmark_runtime"),
        help="Directory for temporary runtime data.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("temp") / "benchmark_results"),
        help="Directory where JSON/Markdown reports are written.",
    )
    parser.add_argument("--provider", default="mock", help="Translation provider name.")
    parser.add_argument("--model", default=None, help="Optional model name override.")
    parser.add_argument(
        "--benchmark-name",
        default=None,
        help="Optional report title override.",
    )
    parser.add_argument(
        "--export-kind",
        choices=[kind.value for kind in _BENCHMARK_EXPORT_KINDS],
        default=ExportArtifactKind.BILINGUAL.value,
        help="Export kind to validate after translation.",
    )
    parser.add_argument(
        "--provider-option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Provider/runtime option override. Can be passed multiple times.",
    )
    parser.add_argument(
        "--chunk-sweep",
        nargs="+",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Run the benchmark multiple times with different chunk_target_tokens values.",
    )
    args = parser.parse_args(argv)

    provider_options = _parse_provider_options(args.provider_option)
    sweep_targets = _normalize_chunk_sweep(args.chunk_sweep)
    if sweep_targets:
        summaries: list[dict[str, object]] = []
        benchmark_name = args.benchmark_name or Path(args.epub_path).stem
        for chunk_target_tokens in sweep_targets:
            sweep_options = dict(provider_options)
            sweep_options["chunk_target_tokens"] = chunk_target_tokens
            artifacts = run_translation_benchmark(
                epub_path=args.epub_path,
                runtime_root=Path(args.runtime_root) / f"chunk-{chunk_target_tokens}",
                output_dir=args.output_dir,
                provider_name=args.provider,
                model_name=args.model,
                provider_options=sweep_options,
                benchmark_name=f"{benchmark_name}-chunk-{chunk_target_tokens}",
                export_kind=ExportArtifactKind(args.export_kind),
            )
            summaries.append(
                {
                    "chunk_target_tokens": chunk_target_tokens,
                    "json_report": str(artifacts.json_path),
                    "markdown_report": str(artifacts.markdown_path),
                    "quality_gate_status": artifacts.result.quality_gate_status,
                    "duration_seconds": artifacts.result.duration_seconds,
                }
            )
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return 0

    artifacts = run_translation_benchmark(
        epub_path=args.epub_path,
        runtime_root=args.runtime_root,
        output_dir=args.output_dir,
        provider_name=args.provider,
        model_name=args.model,
        provider_options=provider_options,
        benchmark_name=args.benchmark_name,
        export_kind=ExportArtifactKind(args.export_kind),
    )
    print(f"JSON report: {artifacts.json_path}")
    print(f"Markdown report: {artifacts.markdown_path}")
    return 0


def _main_suggest_overrides(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate runtime profile override suggestions from benchmark reports."
    )
    parser.add_argument(
        "report_paths",
        nargs="*",
        help="Benchmark JSON or Markdown report paths.",
    )
    parser.add_argument(
        "--report-glob",
        action="append",
        default=[],
        metavar="GLOB",
        help="Glob pattern for benchmark reports. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("temp") / "benchmark_override_suggestions"),
        help="Directory where JSON/Markdown suggestion reports are written.",
    )
    parser.add_argument(
        "--suggestion-name",
        default=None,
        help="Optional suggestion report title override.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Fallback base URL used when reports do not contain runtime target metadata.",
    )
    args = parser.parse_args(argv)
    report_paths = _collect_report_paths(
        args.report_paths,
        report_globs=args.report_glob,
    )
    if not report_paths:
        raise ValueError("At least one benchmark report path or --report-glob is required.")
    report = suggest_runtime_profile_overrides(
        report_paths,
        fallback_base_url=args.base_url,
    )
    json_path, markdown_path = _write_override_suggestion_artifacts(
        report=report,
        output_dir=args.output_dir,
        suggestion_name=args.suggestion_name,
    )
    print(f"JSON suggestions: {json_path}")
    print(f"Markdown suggestions: {markdown_path}")
    return 0


def _main_summarize_baselines(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize benchmark baselines by runtime_profile and capability tier."
    )
    parser.add_argument(
        "report_paths",
        nargs="*",
        help="Benchmark JSON or Markdown report paths.",
    )
    parser.add_argument(
        "--report-glob",
        action="append",
        default=[],
        metavar="GLOB",
        help="Glob pattern for benchmark reports. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("temp") / "benchmark_baselines"),
        help="Directory where JSON/Markdown baseline summaries are written.",
    )
    parser.add_argument(
        "--summary-name",
        default=None,
        help="Optional summary report title override.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Fallback base URL used when reports do not contain runtime target metadata.",
    )
    parser.add_argument(
        "--min-distinct-targets",
        type=int,
        default=2,
        help="Coverage gap threshold for unique targets per runtime_profile/capability tier group.",
    )
    args = parser.parse_args(argv)
    report_paths = _collect_report_paths(
        args.report_paths,
        report_globs=args.report_glob,
    )
    if not report_paths:
        raise ValueError("At least one benchmark report path or --report-glob is required.")
    summary = summarize_benchmark_baselines(
        report_paths,
        fallback_base_url=args.base_url,
        min_distinct_targets=max(1, int(args.min_distinct_targets)),
    )
    json_path, markdown_path = _write_benchmark_baseline_artifacts(
        summary=summary,
        output_dir=args.output_dir,
        summary_name=args.summary_name,
    )
    print(f"JSON baseline summary: {json_path}")
    print(f"Markdown baseline summary: {markdown_path}")
    return 0


def _parse_provider_options(pairs: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator:
            raise ValueError(f"Invalid provider option '{pair}'. Expected KEY=VALUE.")
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError(f"Invalid provider option '{pair}'. Key cannot be empty.")
        parsed[normalized_key] = _parse_scalar(value.strip())
    return parsed


def _parse_scalar(value: str) -> object:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _normalize_chunk_sweep(values: list[int] | None) -> list[int]:
    if not values:
        return []
    normalized = sorted({max(64, int(value)) for value in values})
    return normalized


def _collect_report_paths(
    report_paths: list[str],
    *,
    report_globs: list[str],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in report_paths:
        path = Path(raw_path).resolve()
        if path.is_dir():
            for child in sorted(path.rglob("*.json")):
                resolved = str(child.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    normalized.append(resolved)
            for child in sorted(path.rglob("*.md")):
                if child.with_suffix(".json").exists():
                    continue
                resolved = str(child.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    normalized.append(resolved)
            continue
        resolved = str(path)
        if resolved not in seen:
            seen.add(resolved)
            normalized.append(resolved)
    for pattern in report_globs:
        for matched in sorted(glob.glob(pattern, recursive=True)):
            resolved = str(Path(matched).resolve())
            if resolved not in seen:
                seen.add(resolved)
                normalized.append(resolved)
    return normalized


def _write_override_suggestion_artifacts(
    *,
    report,
    output_dir: str | Path,
    suggestion_name: str | None,
) -> tuple[Path, Path]:
    normalized_output_dir = Path(output_dir).resolve()
    normalized_output_dir.mkdir(parents=True, exist_ok=True)
    normalized_name = (
        suggestion_name.strip().replace(" ", "-")
        if suggestion_name is not None and suggestion_name.strip()
        else "override-suggestions"
    )
    json_path = normalized_output_dir / f"{normalized_name}.json"
    markdown_path = normalized_output_dir / f"{normalized_name}.md"
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        report.render_markdown(),
        encoding="utf-8",
    )
    return json_path, markdown_path


def _write_benchmark_baseline_artifacts(
    *,
    summary,
    output_dir: str | Path,
    summary_name: str | None,
) -> tuple[Path, Path]:
    normalized_output_dir = Path(output_dir).resolve()
    normalized_output_dir.mkdir(parents=True, exist_ok=True)
    normalized_name = (
        summary_name.strip().replace(" ", "-")
        if summary_name is not None and summary_name.strip()
        else "baseline-summary"
    )
    json_path = normalized_output_dir / f"{normalized_name}.json"
    markdown_path = normalized_output_dir / f"{normalized_name}.md"
    json_path.write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        summary.render_markdown(),
        encoding="utf-8",
    )
    return json_path, markdown_path


if __name__ == "__main__":
    raise SystemExit(main())
