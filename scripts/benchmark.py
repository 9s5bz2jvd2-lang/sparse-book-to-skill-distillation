#!/usr/bin/env python3
"""Report honest size/selection proxies for a real from-zero lifecycle; never infer token or quality savings."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from contract_validation import ContractError, load_json
from pipeline import ROOT, build_registry, finalize_queue_and_source_map, install_curated_artifacts, intake_sources, prepare_distillation, query_registry

WORKSPACE = ROOT / "build" / "benchmark-run"
SOURCE = ROOT / "examples" / "from-zero" / "source"
CURATED = ROOT / "examples" / "from-zero" / "curated"
REQUEST = ROOT / "examples" / "from-zero" / "request.json"


def chars_words(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    return len(text), len(text.split())


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    try:
        manifest = intake_sources(SOURCE, WORKSPACE, max_lines_per_chunk=6)
        prepare_distillation(WORKSPACE)
        install_curated_artifacts(WORKSPACE, CURATED)
        finalize_queue_and_source_map(WORKSPACE)
        _, _, registry = build_registry(WORKSPACE)
        output = query_registry(WORKSPACE / "build" / "expert-registry.v2.json", load_json(REQUEST))
        source_metrics = [chars_words(WORKSPACE / source["text_path"]) for source in manifest["sources"]]
        chunk_metrics = [chars_words(WORKSPACE / chunk["path"]) for chunk in manifest["chunks"]]
        all_l3 = sorted({item["path"] for expert in registry["experts"] for item in expert["l3_files"]})
        all_l3_metrics = [chars_words(WORKSPACE / path) for path in all_l3]
        selected_metrics = [chars_words(Path(path)) for path in output["load_plan"]["expert_module_files"]]
        report = {
            "benchmark_kind": "deterministic_proxy_only",
            "warning": "Character/whitespace-word counts and selection ratios are not model-token counts, cost, latency, semantic recall, or answer-quality measurements.",
            "source_characters": sum(item[0] for item in source_metrics),
            "source_words_whitespace_split": sum(item[1] for item in source_metrics),
            "all_chunk_characters": sum(item[0] for item in chunk_metrics),
            "registered_l3_characters": sum(item[0] for item in all_l3_metrics),
            "selected_l3_characters": sum(item[0] for item in selected_metrics),
            "registered_experts": len(registry["experts"]),
            "selected_experts": len(output["selected_experts"]),
            "selected_expert_ratio": len(output["selected_experts"]) / len(registry["experts"]),
            "manifest_chunks": len(manifest["chunks"]),
            "selected_source_chunks": len(output["load_plan"]["source_chunks"]),
            "selected_chunk_ratio": len(output["load_plan"]["source_chunks"]) / len(manifest["chunks"]),
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    except ContractError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    finally:
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
