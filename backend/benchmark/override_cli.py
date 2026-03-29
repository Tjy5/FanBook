from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.benchmark.override_suggestions import suggest_runtime_profile_overrides


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate runtime profile override suggestions from benchmark reports."
    )
    parser.add_argument(
        "report_paths",
        nargs="+",
        help="Benchmark report files or directories containing JSON/Markdown reports.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Fallback base URL used when a report does not record provider_base_url.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Fallback model name used when a report does not record model_name.",
    )
    parser.add_argument(
        "--runtime-profile",
        default=None,
        help="Fallback runtime_profile used when legacy reports do not record one.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path for a machine-readable JSON summary.",
    )
    parser.add_argument(
        "--output-markdown",
        default=None,
        help="Optional path for a Markdown summary.",
    )
    args = parser.parse_args(argv)

    report = suggest_runtime_profile_overrides(
        args.report_paths,
        fallback_base_url=args.base_url,
        fallback_model_name=args.model,
        fallback_runtime_profile=args.runtime_profile,
    )
    markdown = report.render_markdown()
    print(markdown)

    if args.output_json:
        output_json_path = Path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.output_markdown:
        output_markdown_path = Path(args.output_markdown)
        output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        output_markdown_path.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
