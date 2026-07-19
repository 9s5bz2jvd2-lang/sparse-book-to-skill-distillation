#!/usr/bin/env python3
"""Standard-library source-to-sparse lifecycle implementation.

Deterministic code owns intake, hashing, chunking, queue/template creation,
contract/provenance/completeness validation, registry building, and lexical
selection.  It does not perform semantic distillation: an agent or human must
read every chunk and author the distilled records before validation can pass.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

from artifact_io import copy_file_atomic, write_json_atomic
from contract_validation import CONTRACT_VERSION, ContractError, load_json, validate_instance

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
ROUTING_POLICY = CONTRACTS / "routing-policy.v2.json"
MAX_FILES = 1000
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


class PipelineError(ContractError):
    """Stable lifecycle failure with a machine-assertable code."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    """Persist one lifecycle artifact without fixed-name temp collisions."""
    write_json_atomic(path, value)


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def workspace_path(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError as exc:
        raise PipelineError("unsafe_workspace_path", f"path escapes workspace: {relative}") from exc
    return candidate


def _schema(name: str) -> dict[str, Any]:
    schema = load_json(CONTRACTS / name)
    if not isinstance(schema, dict):
        raise PipelineError("invalid_schema", f"schema root is not an object: {name}")
    return schema


def _validate_manifest_identity(manifest: dict[str, Any]) -> None:
    base = {key: value for key, value in manifest.items() if key != "manifest_id"}
    expected_manifest_id = "manifest-" + sha256_bytes(canonical_bytes(base))[:20]
    if manifest["manifest_id"] != expected_manifest_id:
        raise PipelineError("manifest_identity_mismatch", "manifest_id does not match canonical manifest content")
    for source in manifest["sources"]:
        expected_source_id = "src-" + sha256_bytes(
            (source["relative_path"] + "\0" + source["source_sha256"]).encode("utf-8")
        )[:16]
        if source["source_id"] != expected_source_id:
            raise PipelineError("source_identity_mismatch", f"source_id does not match path/hash: {source['source_id']}")
        suffix = Path(source["relative_path"]).suffix.casefold()
        if source["original_path"] != f"source-originals/{source['source_id']}{suffix}" or source["text_path"] != f"sources/{source['source_id']}.txt":
            raise PipelineError("source_identity_mismatch", f"source archive/text paths are noncanonical: {source['source_id']}")
    for chunk in manifest["chunks"]:
        if chunk["path"] != f"chunks/{chunk['chunk_id']}.txt":
            raise PipelineError("chunk_identity_mismatch", f"chunk path is noncanonical: {chunk['chunk_id']}")


def _validate_queue_mapping(workspace: Path, manifest: dict[str, Any], queue: dict[str, Any]) -> None:
    manifest_path = workspace / "source-manifest.json"
    if queue["source_manifest_sha256"] != sha256_bytes(manifest_path.read_bytes()):
        raise PipelineError("manifest_hash_mismatch", "work queue does not match source-manifest bytes")
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}
    queue_ids = [item["chunk_id"] for item in queue["items"]]
    if set(queue_ids) != set(chunks) or len(queue_ids) != len(set(queue_ids)):
        raise PipelineError("queue_manifest_mismatch", "work queue must contain every manifest chunk exactly once")
    for item in queue["items"]:
        chunk = chunks[item["chunk_id"]]
        expected_artifact = f"distilled/records/{item['chunk_id']}.json"
        if item["chunk_path"] != chunk["path"] or item["artifact_path"] != expected_artifact:
            raise PipelineError("queue_manifest_mismatch", f"queue paths differ from manifest/contract: {item['chunk_id']}")
        workspace_path(workspace, item["chunk_path"])
        workspace_path(workspace, item["artifact_path"])


def _queue_plan_sha256(queue: dict[str, Any]) -> str:
    """Hash only immutable queue identity/path fields, never mutable progress."""

    plan = [
        {
            "chunk_id": item["chunk_id"],
            "chunk_path": item["chunk_path"],
            "artifact_path": item["artifact_path"],
        }
        for item in queue["items"]
    ]
    return sha256_bytes(canonical_bytes(plan))


def _expected_batch_id(chunk_ids: list[str], start: int) -> str:
    end = start + len(chunk_ids)
    fingerprint = sha256_bytes(canonical_bytes(chunk_ids))[:12]
    return f"batch-{start + 1:06d}-{end:06d}-{fingerprint}"


def _source_files(source: Path) -> tuple[Path, list[Path]]:
    source = source.expanduser()
    # Check the caller-supplied path before resolving it. Resolving first would
    # erase the fact that the source root itself is a symlink.
    if source.is_symlink():
        raise PipelineError("source_symlink_denied", "source symlinks are not accepted")
    source = source.resolve()
    if not source.exists():
        raise PipelineError("source_not_found", f"source does not exist: {source}")
    if source.is_file():
        if source.suffix.casefold() not in SUPPORTED_SUFFIXES:
            raise PipelineError("unsupported_source_type", f"supported extensions are {sorted(SUPPORTED_SUFFIXES)}")
        return source.parent, [source]
    if not source.is_dir():
        raise PipelineError("unsupported_source_type", "source must be a regular file or directory")

    files: list[Path] = []
    unsupported: list[str] = []
    stack = [source]
    while stack:
        directory = stack.pop()
        for candidate in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
            if candidate.name.startswith("."):
                continue
            if candidate.is_symlink():
                raise PipelineError("source_symlink_denied", f"source contains symlink: {candidate.relative_to(source)}")
            if candidate.is_dir():
                stack.append(candidate)
            elif candidate.is_file():
                if candidate.suffix.casefold() in SUPPORTED_SUFFIXES:
                    files.append(candidate)
                else:
                    unsupported.append(candidate.relative_to(source).as_posix())
            if len(files) + len(unsupported) > MAX_FILES:
                raise PipelineError("source_limit_exceeded", f"directory exceeds {MAX_FILES} visible files")
    if unsupported:
        preview = unsupported[:5]
        raise PipelineError("unsupported_source_type", f"unsupported visible files present: {preview}")
    if not files:
        raise PipelineError("source_empty", "no supported non-hidden source files found")
    return source, sorted(files, key=lambda item: item.relative_to(source).as_posix().casefold())


def _canonical_text(raw: bytes, relative_path: str) -> tuple[str, str, list[int]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PipelineError("invalid_utf8", f"source is not valid UTF-8: {relative_path}: {exc}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        raise PipelineError("source_empty", f"source has no text: {relative_path}")
    lines = text.splitlines(keepends=True)
    if not lines:
        raise PipelineError("source_empty", f"source has no lines: {relative_path}")
    return text, "complete_utf8", []


def _pdf_text(path: Path, relative_path: str, allow_pdftotext: bool) -> tuple[str, str, list[int]]:
    if not allow_pdftotext:
        raise PipelineError(
            "pdf_adapter_not_authorized",
            "PDF input requires explicit --allow-pdftotext after reviewing the local adapter action",
        )
    executable = shutil.which("pdftotext")
    if executable is None:
        raise PipelineError("pdf_adapter_unavailable", "pdftotext is not installed; convert PDF to UTF-8 text externally")
    try:
        completed = subprocess.run(
            [executable, "-layout", str(path), "-"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PipelineError("pdf_adapter_failed", f"pdftotext could not run: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()[-500:]
        raise PipelineError("pdf_adapter_failed", f"pdftotext exited {completed.returncode}: {stderr}")
    try:
        extracted = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PipelineError("pdf_adapter_failed", f"pdftotext output is not UTF-8: {relative_path}") from exc
    extracted = extracted.replace("\r\n", "\n").replace("\r", "\n")
    pages = extracted.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    combined_lines: list[str] = []
    page_by_line: list[int] = []
    for page_number, page in enumerate(pages, 1):
        page_lines = page.splitlines(keepends=True)
        if not page_lines:
            continue
        if combined_lines and not combined_lines[-1].endswith("\n"):
            combined_lines[-1] += "\n"
        combined_lines.extend(page_lines)
        page_by_line.extend([page_number] * len(page_lines))
    text = "".join(combined_lines)
    if not text.strip() or not page_by_line:
        raise PipelineError("pdf_adapter_failed", f"pdftotext produced no usable text: {relative_path}")
    return text, "complete_pdftotext", page_by_line


def intake_sources(
    source: Path,
    workspace: Path,
    *,
    max_lines_per_chunk: int = 80,
    allow_pdftotext: bool = False,
) -> dict[str, Any]:
    if not 1 <= max_lines_per_chunk <= 1000:
        raise PipelineError("invalid_chunk_size", "max_lines_per_chunk must be between 1 and 1000")
    source_root, files = _source_files(source)
    workspace = workspace.resolve()
    source_resolved = source.resolve()
    if source_resolved.is_dir():
        try:
            workspace.relative_to(source_resolved)
        except ValueError:
            pass
        else:
            raise PipelineError("unsafe_workspace_path", "workspace must not be inside the source directory")
    if workspace.exists() and not workspace.is_dir():
        raise PipelineError("workspace_not_directory", "workspace must be a directory path")
    if workspace.exists() and any(workspace.iterdir()):
        raise PipelineError("workspace_not_empty", "workspace must be new or empty; existing files are never overwritten")
    workspace.mkdir(parents=True, exist_ok=True)

    total_bytes = sum(path.stat().st_size for path in files)
    if total_bytes > MAX_TOTAL_BYTES:
        raise PipelineError("source_limit_exceeded", f"total source bytes exceed {MAX_TOTAL_BYTES}")
    if len(files) > MAX_FILES:
        raise PipelineError("source_limit_exceeded", f"source file count exceeds {MAX_FILES}")

    source_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    for path in files:
        relative_path = path.relative_to(source_root).as_posix()
        raw = path.read_bytes()
        if len(raw) > MAX_SOURCE_BYTES:
            raise PipelineError("source_limit_exceeded", f"source exceeds {MAX_SOURCE_BYTES} bytes: {relative_path}")
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            text, status, page_by_line = _pdf_text(path, relative_path, allow_pdftotext)
            source_kind = "pdf_pdftotext"
        else:
            text, status, page_by_line = _canonical_text(raw, relative_path)
            source_kind = "utf8_markdown" if suffix == ".md" else "utf8_text"
        text_bytes = text.encode("utf-8")
        source_hash = sha256_bytes(raw)
        source_id = "src-" + sha256_bytes((relative_path + "\0" + source_hash).encode("utf-8"))[:16]
        original_relative = f"source-originals/{source_id}{suffix}"
        original_path = workspace_path(workspace, original_relative)
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(raw)
        text_relative = f"sources/{source_id}.txt"
        text_path = workspace_path(workspace, text_relative)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_bytes(text_bytes)
        lines = text.splitlines(keepends=True)
        chunk_ids: list[str] = []
        for start_index in range(0, len(lines), max_lines_per_chunk):
            chunk_lines = lines[start_index:start_index + max_lines_per_chunk]
            chunk_bytes = "".join(chunk_lines).encode("utf-8")
            start_line = start_index + 1
            end_line = start_index + len(chunk_lines)
            chunk_id = "chunk-" + sha256_bytes(
                source_id.encode("utf-8")
                + f":{start_line}:{end_line}:".encode("ascii")
                + chunk_bytes
            )[:20]
            chunk_relative = f"chunks/{chunk_id}.txt"
            chunk_path = workspace_path(workspace, chunk_relative)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            chunk_path.write_bytes(chunk_bytes)
            pages = sorted(set(page_by_line[start_index:end_line])) if page_by_line else []
            page_range = [pages[0], pages[-1]] if pages else []
            chunk_rows.append({
                "chunk_id": chunk_id,
                "source_id": source_id,
                "source_path": relative_path,
                "path": chunk_relative,
                "sha256": sha256_bytes(chunk_bytes),
                "start_line": start_line,
                "end_line": end_line,
                "page_range": page_range,
            })
            chunk_ids.append(chunk_id)
        source_rows.append({
            "source_id": source_id,
            "relative_path": relative_path,
            "source_kind": source_kind,
            "full_text_status": status,
            "source_sha256": source_hash,
            "original_path": original_relative,
            "text_sha256": sha256_bytes(text_bytes),
            "text_path": text_relative,
            "line_count": len(lines),
            "chunk_ids": chunk_ids,
        })

    manifest_base = {
        "contract_version": CONTRACT_VERSION,
        "source_label": source.name,
        "full_text_status": "complete",
        "chunking": {"strategy": "fixed_lines_v1", "max_lines_per_chunk": max_lines_per_chunk},
        "limits": {
            "max_files": MAX_FILES,
            "max_source_bytes": MAX_SOURCE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
        },
        "sources": source_rows,
        "chunks": chunk_rows,
    }
    manifest = dict(manifest_base)
    manifest["manifest_id"] = "manifest-" + sha256_bytes(canonical_bytes(manifest_base))[:20]
    # Preserve schema field order only for readability; canonical hashes are sort-key based.
    manifest = {
        "contract_version": manifest["contract_version"],
        "manifest_id": manifest["manifest_id"],
        "source_label": manifest["source_label"],
        "full_text_status": manifest["full_text_status"],
        "chunking": manifest["chunking"],
        "limits": manifest["limits"],
        "sources": manifest["sources"],
        "chunks": manifest["chunks"],
    }
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    _validate_manifest_identity(manifest)
    manifest_path = workspace / "source-manifest.json"
    write_json(manifest_path, manifest)
    manifest_sha = sha256_bytes(manifest_path.read_bytes())
    queue = {
        "contract_version": CONTRACT_VERSION,
        "source_manifest_sha256": manifest_sha,
        "semantic_processing": "required_for_every_chunk_by_agent_or_human",
        "items": [
            {
                "chunk_id": row["chunk_id"],
                "chunk_path": row["path"],
                "artifact_path": f"distilled/records/{row['chunk_id']}.json",
                "status": "pending",
            }
            for row in chunk_rows
        ],
    }
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    write_json(workspace / "work-queue.json", queue)
    return manifest


def prepare_distillation(workspace: Path) -> dict[str, int]:
    workspace = workspace.resolve()
    manifest = load_json(workspace / "source-manifest.json")
    queue = load_json(workspace / "work-queue.json")
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    _validate_manifest_identity(manifest)
    _validate_queue_mapping(workspace, manifest, queue)
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}
    record_schema = _schema("distilled-chunk.v2.schema.json")
    created = 0
    for item in queue["items"]:
        chunk = chunks[item["chunk_id"]]
        artifact_path = workspace_path(workspace, item["artifact_path"])
        if artifact_path.exists():
            # Resume is allowed only from a complete, identity-bound artifact.
            # A truncated or mismatched file must never be silently skipped.
            if artifact_path.is_symlink() or not artifact_path.is_file():
                raise PipelineError("existing_artifact_invalid", f"existing artifact is not a regular file: {item['chunk_id']}")
            try:
                existing = load_json(artifact_path)
                validate_instance(existing, record_schema)
            except (ContractError, OSError, ValueError) as exc:
                raise PipelineError("existing_artifact_invalid", f"existing artifact cannot be resumed: {item['chunk_id']}") from exc
            expected_provenance = {
                "source_id": chunk["source_id"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "page_range": chunk["page_range"],
            }
            if (
                existing["chunk_id"] != item["chunk_id"]
                or existing["chunk_sha256"] != chunk["sha256"]
                or existing["chunk_provenance"] != expected_provenance
            ):
                raise PipelineError("existing_artifact_invalid", f"existing artifact identity differs: {item['chunk_id']}")
            continue
        template = {
            "contract_version": CONTRACT_VERSION,
            "artifact_type": "distilled_chunk",
            "chunk_id": chunk["chunk_id"],
            "chunk_sha256": chunk["sha256"],
            "processing_status": "pending",
            "chunk_summary": "",
            "chunk_provenance": {
                "source_id": chunk["source_id"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "page_range": chunk["page_range"],
            },
            "knowledge_nodes": [],
            "anti_trigger_notes": [],
            "uncertainties": [],
            "no_reusable_reason": "",
        }
        write_json(artifact_path, template)
        created += 1
    source_map = {
        "contract_version": CONTRACT_VERSION,
        "source_manifest_sha256": queue["source_manifest_sha256"],
        "full_text_status": "complete",
        "entries": [
            {
                "chunk_id": item["chunk_id"],
                "artifact_path": item["artifact_path"],
                "processing_status": "pending",
                "node_ids": [],
            }
            for item in queue["items"]
        ],
    }
    write_json(workspace / "distilled" / "source-map.json", source_map)
    shared_core = workspace / "distilled" / "shared-core.md"
    if not shared_core.exists():
        shared_core.parent.mkdir(parents=True, exist_ok=True)
        shared_core.write_text(
            "# Shared core\n\n[AGENT MUST REPLACE: short stable rules, trust boundary, red lines, and mandatory sweep.]\n",
            encoding="utf-8",
        )
    review_state_path = workspace / "review-state.json"
    if not review_state_path.exists():
        review_state = {
            "contract_version": CONTRACT_VERSION,
            "source_manifest_sha256": queue["source_manifest_sha256"],
            "queue_plan_sha256": _queue_plan_sha256(queue),
            "batch_size": 3,
            "completed_chunk_ids": [],
            "active_batch_id": "",
            "active_chunk_ids": [],
            "all_chunks_checkpointed": False,
        }
        validate_instance(review_state, _schema("review-state.v2.schema.json"))
        write_json(review_state_path, review_state)
    semantic_review_path = workspace / "distilled" / "semantic-review.json"
    if not semantic_review_path.exists():
        write_json(semantic_review_path, {
            "contract_version": CONTRACT_VERSION,
            "review_status": "pending",
            "source_manifest_sha256": queue["source_manifest_sha256"],
            "reviewer": {"reviewer_type": "agent", "reviewer_label": "REPLACE_WITH_REVIEWER"},
            "review_method": "entire_chunk_read_with_source_locator_verification",
            "reviewed_chunk_ids": [],
            "criteria": {
                "claims_source_grounded": False,
                "meaning_faithful": False,
                "uncertainty_recorded": False,
                "routing_terms_reviewed": False,
                "l3_usefulness_reviewed": False,
            },
            "limitations": ["REPLACE_WITH_SOURCE_OR_REVIEW_LIMITATIONS"],
            "review_assertion": "REPLACE: this declaration must be authored after source-aware semantic review.",
            "semantic_quality_not_automated": True,
        })
    return {"chunks": len(queue["items"]), "templates_created": created}


def _review_context(workspace: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    workspace = workspace.resolve()
    manifest = load_json(workspace / "source-manifest.json")
    queue = load_json(workspace / "work-queue.json")
    state = load_json(workspace / "review-state.json")
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    validate_instance(state, _schema("review-state.v2.schema.json"))
    _validate_manifest_identity(manifest)
    _validate_queue_mapping(workspace, manifest, queue)
    if state["source_manifest_sha256"] != queue["source_manifest_sha256"]:
        raise PipelineError("review_state_mismatch", "review state does not match source manifest")
    if state["queue_plan_sha256"] != _queue_plan_sha256(queue):
        raise PipelineError("review_state_mismatch", "review state does not match immutable queue plan")
    queue_ids = [item["chunk_id"] for item in queue["items"]]
    completed = state["completed_chunk_ids"]
    active = state["active_chunk_ids"]
    if completed != queue_ids[:len(completed)]:
        raise PipelineError("review_state_mismatch", "completed review chunks are not an ordered queue prefix")
    expected_active = queue_ids[len(completed):len(completed) + len(active)]
    if active != expected_active:
        raise PipelineError("review_state_mismatch", "active review batch is not the next contiguous queue slice")
    if bool(active) != bool(state["active_batch_id"]):
        raise PipelineError("review_state_mismatch", "active batch ID/list presence differs")
    if active and state["active_batch_id"] != _expected_batch_id(active, len(completed)):
        raise PipelineError("review_state_mismatch", "active batch ID is not canonical")
    expected_all = len(completed) == len(queue_ids) and not active
    if state["all_chunks_checkpointed"] is not expected_all:
        raise PipelineError("review_state_mismatch", "all_chunks_checkpointed is inconsistent with ordered progress")

    allowed_nonpending = set(completed) | set(active)
    for item in queue["items"]:
        record = load_json(workspace_path(workspace, item["artifact_path"]))
        validate_instance(record, _schema("distilled-chunk.v2.schema.json"))
        if item["chunk_id"] in completed and record["processing_status"] == "pending":
            raise PipelineError("review_state_mismatch", f"checkpointed record reverted to pending: {item['chunk_id']}")
        if item["chunk_id"] not in allowed_nonpending and record["processing_status"] != "pending":
            raise PipelineError("out_of_order_review", f"record was completed outside the active contiguous batch: {item['chunk_id']}")
    return workspace, manifest, queue, state


def claim_review_batch(workspace: Path, *, batch_size: int = 3) -> dict[str, Any]:
    """Return the durable active batch, or atomically claim the next queue slice.

    Repeating this call after interruption returns the same batch. It never moves
    the cursor; only checkpoint_review_batch can advance an active slice. The
    stored batch size may change only between batches (empty active slice); an
    active slice is never resized, so old workspaces with a stored size of 20
    stay loadable and drain through repeated prefix checkpoints.
    """

    if not 1 <= batch_size <= 1000:
        raise PipelineError("invalid_batch_size", "batch_size must be between 1 and 1000")
    workspace, manifest, queue, state = _review_context(workspace)
    if not state["active_chunk_ids"]:
        state["batch_size"] = batch_size
    if not state["active_chunk_ids"] and not state["all_chunks_checkpointed"]:
        start = len(state["completed_chunk_ids"])
        state["active_chunk_ids"] = [item["chunk_id"] for item in queue["items"][start:start + state["batch_size"]]]
        state["active_batch_id"] = _expected_batch_id(state["active_chunk_ids"], start)
        write_json(workspace / "review-state.json", state)
    chunk_by_id = {chunk["chunk_id"]: chunk for chunk in manifest["chunks"]}
    item_by_id = {item["chunk_id"]: item for item in queue["items"]}
    items = []
    for chunk_id in state["active_chunk_ids"]:
        chunk = chunk_by_id[chunk_id]
        item = item_by_id[chunk_id]
        items.append({
            "chunk_id": chunk_id,
            "chunk_path": item["chunk_path"],
            "artifact_path": item["artifact_path"],
            "chunk_sha256": chunk["sha256"],
            "source_id": chunk["source_id"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "page_range": chunk["page_range"],
        })
    return {
        "batch_id": state["active_batch_id"],
        "items": items,
        "completed_chunks": len(state["completed_chunk_ids"]),
        "total_chunks": len(queue["items"]),
        "all_chunks_checkpointed": state["all_chunks_checkpointed"],
    }


def checkpoint_review_batch(workspace: Path) -> dict[str, Any]:
    """Commit the longest valid contiguous authored prefix of the active batch.

    Scanning starts at active_chunk_ids[0]. The first pending record ends the
    committable prefix; records past it are not inspected for commit. Any
    non-pending prefix record must pass every identity/hash/provenance/content
    check or the whole call hard-fails with review-state bytes unchanged. This
    validates structure, identity, hash, provenance, and required content shape
    only; source/semantic acceptance remains a separate review gate.
    """

    workspace, manifest, queue, state = _review_context(workspace)
    if not state["active_chunk_ids"]:
        if state["all_chunks_checkpointed"]:
            return {"checkpointed": 0, "completed_chunks": len(state["completed_chunk_ids"]), "total_chunks": len(queue["items"]), "all_chunks_checkpointed": True}
        raise PipelineError("no_active_review_batch", "claim a review batch before checkpointing")
    chunks = {chunk["chunk_id"]: chunk for chunk in manifest["chunks"]}
    items = {item["chunk_id"]: item for item in queue["items"]}
    prefix: list[str] = []
    for chunk_id in state["active_chunk_ids"]:
        record = load_json(workspace_path(workspace, items[chunk_id]["artifact_path"]))
        validate_instance(record, _schema("distilled-chunk.v2.schema.json"))
        if record["processing_status"] == "pending":
            break
        chunk = chunks[chunk_id]
        if record["chunk_id"] != chunk_id or record["chunk_sha256"] != chunk["sha256"]:
            raise PipelineError("chunk_artifact_mismatch", f"active artifact identity/hash differs: {chunk_id}")
        provenance = record["chunk_provenance"]
        if (
            provenance["source_id"] != chunk["source_id"]
            or provenance["start_line"] != chunk["start_line"]
            or provenance["end_line"] != chunk["end_line"]
            or provenance["page_range"] != chunk["page_range"]
        ):
            raise PipelineError("broken_provenance", f"active artifact provenance differs: {chunk_id}")
        if record["processing_status"] == "complete" and (not record["chunk_summary"].strip() or not record["knowledge_nodes"]):
            raise PipelineError("incomplete_review_batch", f"complete active artifact lacks semantic content: {chunk_id}")
        if record["processing_status"] == "complete_no_reusable_knowledge" and (record["knowledge_nodes"] or not record["no_reusable_reason"].strip()):
            raise PipelineError("incomplete_review_batch", f"no-reusable active artifact lacks a reviewed reason: {chunk_id}")
        prefix.append(chunk_id)
    if not prefix:
        raise PipelineError("incomplete_review_batch", f"no authored contiguous prefix to checkpoint: {state['active_chunk_ids'][0]} remains pending")
    remainder = state["active_chunk_ids"][len(prefix):]
    state["completed_chunk_ids"].extend(prefix)
    state["active_chunk_ids"] = remainder
    state["active_batch_id"] = _expected_batch_id(remainder, len(state["completed_chunk_ids"])) if remainder else ""
    state["all_chunks_checkpointed"] = len(state["completed_chunk_ids"]) == len(queue["items"]) and not remainder
    write_json(workspace / "review-state.json", state)
    return {"checkpointed": len(prefix), "completed_chunks": len(state["completed_chunk_ids"]), "total_chunks": len(queue["items"]), "all_chunks_checkpointed": state["all_chunks_checkpointed"]}


def finalize_queue_and_source_map(workspace: Path) -> None:
    """Derive queue statuses and source-map entries from agent-authored records.

    This does not judge semantic quality; the subsequent completeness validator
    checks provenance, coverage, L3 paths, hashes, and contract consistency.
    """

    workspace = workspace.resolve()
    manifest = load_json(workspace / "source-manifest.json")
    queue = load_json(workspace / "work-queue.json")
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    _validate_manifest_identity(manifest)
    _validate_queue_mapping(workspace, manifest, queue)
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}
    entries: list[dict[str, Any]] = []
    for item in queue["items"]:
        artifact_path = workspace_path(workspace, item["artifact_path"])
        if not artifact_path.is_file():
            raise PipelineError("unprocessed_chunk", f"artifact is missing: {item['chunk_id']}")
        record = load_json(artifact_path)
        validate_instance(record, _schema("distilled-chunk.v2.schema.json"))
        chunk = chunks[item["chunk_id"]]
        if record["chunk_id"] != item["chunk_id"] or record["chunk_sha256"] != chunk["sha256"]:
            raise PipelineError("chunk_artifact_mismatch", f"artifact identity/hash differs: {item['chunk_id']}")
        if record["processing_status"] == "pending":
            raise PipelineError("unprocessed_chunk", f"artifact remains pending: {item['chunk_id']}")
        item["status"] = record["processing_status"]
        entries.append({
            "chunk_id": item["chunk_id"],
            "artifact_path": item["artifact_path"],
            "processing_status": record["processing_status"],
            "node_ids": [node["node_id"] for node in record["knowledge_nodes"]],
        })
    write_json(workspace / "work-queue.json", queue)
    source_map = {
        "contract_version": CONTRACT_VERSION,
        "source_manifest_sha256": queue["source_manifest_sha256"],
        "full_text_status": "complete",
        "entries": entries,
    }
    write_json(workspace / "distilled" / "source-map.json", source_map)
    # Full-record inspection above is the only allowed fast-forward. It supports
    # externally authored complete bundles while still making false completion
    # impossible: every queue record was schema/identity/status checked first.
    state = load_json(workspace / "review-state.json")
    validate_instance(state, _schema("review-state.v2.schema.json"))
    if state["source_manifest_sha256"] != queue["source_manifest_sha256"] or state["queue_plan_sha256"] != _queue_plan_sha256(queue):
        raise PipelineError("review_state_mismatch", "review state binding differs during finalization")
    state["completed_chunk_ids"] = [item["chunk_id"] for item in queue["items"]]
    state["active_batch_id"] = ""
    state["active_chunk_ids"] = []
    state["all_chunks_checkpointed"] = True
    write_json(workspace / "review-state.json", state)


def install_authored_artifacts(workspace: Path, curated: Path) -> None:
    """Validate a complete authored bundle, then copy it without semantic inference."""

    workspace = workspace.resolve()
    if curated.is_symlink():
        raise PipelineError("invalid_curated_artifact", "authored bundle root must not be a symlink")
    curated = curated.resolve()
    if not curated.is_dir():
        raise PipelineError("invalid_curated_artifact", "authored bundle must be a directory")
    manifest = load_json(workspace / "source-manifest.json")
    queue = load_json(workspace / "work-queue.json")
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    _validate_manifest_identity(manifest)
    _validate_queue_mapping(workspace, manifest, queue)
    manifest_sha = sha256_bytes((workspace / "source-manifest.json").read_bytes())
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}

    # Preflight every semantic artifact before writing any authored bytes.
    record_dir = curated / "records"
    if record_dir.is_symlink():
        raise PipelineError("invalid_curated_artifact", "curated records directory must not be a symlink")
    records = sorted(record_dir.glob("*.json")) if record_dir.is_dir() else []
    record_by_chunk: dict[str, tuple[Path, dict[str, Any]]] = {}
    record_schema = _schema("distilled-chunk.v2.schema.json")
    for path in records:
        if path.is_symlink():
            raise PipelineError("invalid_curated_artifact", f"curated record is a symlink: {path.name}")
        record = load_json(path)
        validate_instance(record, record_schema)
        chunk_id = record["chunk_id"]
        if chunk_id in record_by_chunk:
            raise PipelineError("invalid_curated_artifact", f"duplicate curated chunk_id: {chunk_id}")
        if record["processing_status"] == "pending":
            raise PipelineError("invalid_curated_artifact", f"curated record remains pending: {path.name}")
        record_by_chunk[chunk_id] = (path, record)
    if set(record_by_chunk) != set(chunks):
        raise PipelineError(
            "invalid_curated_artifact",
            f"curated chunk IDs differ from manifest; missing={sorted(set(chunks)-set(record_by_chunk))} extra={sorted(set(record_by_chunk)-set(chunks))}",
        )

    l3_copies: list[tuple[Path, Path]] = []
    l3_paths: set[str] = set()
    for chunk_id, (_path, record) in record_by_chunk.items():
        if record["chunk_sha256"] != chunks[chunk_id]["sha256"]:
            raise PipelineError("invalid_curated_artifact", f"chunk hash mismatch in {chunk_id}")
        l3_paths.update(node["l3"]["path"] for node in record["knowledge_nodes"])
    for relative in sorted(l3_paths):
        if not relative.startswith("distilled/l3/") or ".." in Path(relative).parts:
            raise PipelineError("invalid_curated_artifact", f"curated L3 path is outside distilled/l3: {relative}")
        curated_relative = Path(relative.removeprefix("distilled/"))
        source_path = curated / curated_relative
        current = curated
        for part in curated_relative.parts:
            current = current / part
            if current.is_symlink():
                raise PipelineError("invalid_curated_artifact", f"curated L3 path contains a symlink: {relative}")
        if not source_path.is_file():
            raise PipelineError("invalid_curated_artifact", f"curated L3 file is missing/unsafe: {relative}")
        destination = workspace_path(workspace, relative)
        if destination.is_symlink():
            raise PipelineError("invalid_curated_artifact", f"workspace L3 destination is a symlink: {relative}")
        l3_copies.append((source_path, destination))

    shared_source = curated / "shared-core.md"
    review_source = curated / "semantic-review.json"
    for label, source_path in (("shared-core.md", shared_source), ("semantic-review.json", review_source)):
        if source_path.is_symlink() or not source_path.is_file():
            raise PipelineError("invalid_curated_artifact", f"curated {label} is missing/unsafe")
    review = load_json(review_source)
    validate_instance(review, _schema("semantic-review.v2.schema.json"))

    # Atomic graph artifacts are optional for base-v2 compatibility, but the pair
    # is all-or-nothing. Validate the entire pair before any semantic copy occurs.
    atoms_source = curated / "atoms"
    coverage_source = curated / "atom-coverage.json"
    if atoms_source.exists() and not atoms_source.is_dir():
        raise PipelineError("invalid_curated_artifact", "curated atoms must be a directory")
    if coverage_source.exists() and not coverage_source.is_file():
        raise PipelineError("invalid_curated_artifact", "curated atom-coverage.json must be a file")
    has_atoms = atoms_source.is_dir()
    has_coverage = coverage_source.is_file()
    if has_atoms != has_coverage:
        raise PipelineError("invalid_curated_artifact", "curated atoms/ and atom-coverage.json must be supplied together")

    atom_by_id: dict[str, tuple[Path, dict[str, Any]]] = {}
    coverage: dict[str, Any] | None = None
    if has_atoms:
        if atoms_source.is_symlink() or coverage_source.is_symlink():
            raise PipelineError("invalid_curated_artifact", "curated atomic artifacts must not be symlinks")
        atom_paths = sorted(atoms_source.iterdir(), key=lambda path: path.name)
        if not atom_paths:
            raise PipelineError("invalid_curated_artifact", "curated atoms directory is empty")
        if any(path.is_symlink() or not path.is_file() or path.suffix != ".json" for path in atom_paths):
            raise PipelineError("invalid_curated_artifact", "curated atoms must contain only regular JSON files")

        atom_schema = _schema("atomic-node.v1.schema.json")
        for path in atom_paths:
            atom = load_json(path)
            validate_instance(atom, atom_schema)
            node_id = atom["node_id"]
            if node_id in atom_by_id:
                raise PipelineError("invalid_curated_artifact", f"duplicate curated atom node_id: {node_id}")
            atom_by_id[node_id] = (path, atom)

        coverage = load_json(coverage_source)
        declared_manifest_sha = coverage.get("source_manifest_sha256")
        if declared_manifest_sha not in {manifest_sha, "PLACEHOLDER_MANIFEST_SHA"}:
            raise PipelineError("invalid_curated_artifact", "atom coverage is bound to a different source manifest")
        coverage["source_manifest_sha256"] = manifest_sha
        validate_instance(coverage, _schema("atom-coverage.v1.schema.json"))

        coverage_by_chunk: dict[str, dict[str, Any]] = {}
        declared_atom_ids: list[str] = []
        for entry in coverage["entries"]:
            chunk_id = entry["chunk_id"]
            if chunk_id in coverage_by_chunk:
                raise PipelineError("invalid_curated_artifact", f"duplicate atom coverage chunk_id: {chunk_id}")
            if entry["status"] == "pending":
                raise PipelineError("invalid_curated_artifact", f"atom coverage remains pending: {chunk_id}")
            if entry["status"] == "atoms_authored" and not entry["atom_ids"]:
                raise PipelineError("invalid_curated_artifact", f"atoms_authored coverage has no atom IDs: {chunk_id}")
            if entry["status"] == "no_atomizable_content" and entry["atom_ids"]:
                raise PipelineError("invalid_curated_artifact", f"no_atomizable_content coverage lists atoms: {chunk_id}")
            coverage_by_chunk[chunk_id] = entry
            declared_atom_ids.extend(entry["atom_ids"])
        manifest_chunk_ids = set(chunks)
        if set(coverage_by_chunk) != manifest_chunk_ids:
            raise PipelineError(
                "invalid_curated_artifact",
                f"atom coverage differs from manifest chunks; missing={sorted(manifest_chunk_ids-set(coverage_by_chunk))} extra={sorted(set(coverage_by_chunk)-manifest_chunk_ids)}",
            )
        if len(declared_atom_ids) != len(set(declared_atom_ids)):
            raise PipelineError("invalid_curated_artifact", "atom coverage declares an atom ID more than once")
        if set(declared_atom_ids) != set(atom_by_id):
            raise PipelineError(
                "invalid_curated_artifact",
                f"atom coverage differs from supplied atoms; missing={sorted(set(atom_by_id)-set(declared_atom_ids))} extra={sorted(set(declared_atom_ids)-set(atom_by_id))}",
            )

    # All authored inputs are valid. Commit each destination with same-directory
    # temporary files so an individual artifact is never observed half-written.
    def copy_atomic(source_path: Path, destination: Path) -> None:
        if destination.is_symlink():
            raise PipelineError("invalid_curated_artifact", f"workspace destination is a symlink: {destination}")
        try:
            copy_file_atomic(source_path, destination)
        except OSError as exc:
            raise PipelineError("artifact_install_failed", f"cannot install {destination}: {exc}") from exc

    for chunk_id, (source_path, _record) in sorted(record_by_chunk.items()):
        copy_atomic(source_path, workspace / "distilled" / "records" / f"{chunk_id}.json")
    for source_path, destination in l3_copies:
        copy_atomic(source_path, destination)
    copy_atomic(shared_source, workspace / "distilled" / "shared-core.md")
    copy_atomic(review_source, workspace / "distilled" / "semantic-review.json")

    if has_atoms:
        atoms_destination = workspace / "distilled" / "atoms"
        coverage_destination = workspace / "distilled" / "atom-coverage.json"
        if atoms_destination.exists() or coverage_destination.exists():
            raise PipelineError("invalid_curated_artifact", "workspace already contains atomic artifacts")
        atoms_destination.mkdir(parents=True)
        for path, _atom in atom_by_id.values():
            copy_atomic(path, atoms_destination / path.name)
        assert coverage is not None
        write_json(coverage_destination, coverage)


def install_curated_artifacts(workspace: Path, curated: Path) -> None:
    """Compatibility wrapper for the repository-authored synthetic demo bundle."""

    install_authored_artifacts(workspace, curated)


def validate_distillation(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    manifest_path = workspace / "source-manifest.json"
    queue_path = workspace / "work-queue.json"
    manifest = load_json(manifest_path)
    queue = load_json(queue_path)
    validate_instance(manifest, _schema("source-manifest.v2.schema.json"))
    validate_instance(queue, _schema("work-queue.v2.schema.json"))
    _validate_manifest_identity(manifest)
    _validate_queue_mapping(workspace, manifest, queue)
    manifest_sha = sha256_bytes(manifest_path.read_bytes())
    if manifest["full_text_status"] != "complete":
        raise PipelineError("incomplete_full_text", "source manifest full_text_status is not complete")

    sources = {row["source_id"]: row for row in manifest["sources"]}
    chunks = {row["chunk_id"]: row for row in manifest["chunks"]}
    if len(sources) != len(manifest["sources"]) or len(chunks) != len(manifest["chunks"]):
        raise PipelineError("duplicate_manifest_id", "source_id and chunk_id values must be unique")
    pending = [item["chunk_id"] for item in queue["items"] if item["status"] == "pending"]
    if pending:
        raise PipelineError("unprocessed_chunk", f"work queue still has pending chunks: {pending}")
    state = load_json(workspace / "review-state.json")
    validate_instance(state, _schema("review-state.v2.schema.json"))
    queue_ids = [item["chunk_id"] for item in queue["items"]]
    if (
        state["source_manifest_sha256"] != manifest_sha
        or state["queue_plan_sha256"] != _queue_plan_sha256(queue)
        or state["completed_chunk_ids"] != queue_ids
        or state["active_batch_id"]
        or state["active_chunk_ids"]
        or state["all_chunks_checkpointed"] is not True
    ):
        raise PipelineError("review_state_mismatch", "review state does not prove complete ordered queue coverage")

    chunks_by_source: dict[str, list[dict[str, Any]]] = {source_id: [] for source_id in sources}
    for chunk in manifest["chunks"]:
        if chunk["source_id"] not in sources:
            raise PipelineError("broken_provenance", f"chunk has unknown source_id: {chunk['chunk_id']}")
        if chunk["source_path"] != sources[chunk["source_id"]]["relative_path"]:
            raise PipelineError("broken_provenance", f"chunk source_path differs from source manifest: {chunk['chunk_id']}")
        if chunk["page_range"] and (len(chunk["page_range"]) != 2 or chunk["page_range"][0] > chunk["page_range"][1]):
            raise PipelineError("broken_provenance", f"chunk page_range must be empty or [start, end]: {chunk['chunk_id']}")
        chunks_by_source[chunk["source_id"]].append(chunk)
    for source_id, source_row in sources.items():
        original_path = workspace_path(workspace, source_row["original_path"])
        if not original_path.is_file():
            raise PipelineError("source_hash_mismatch", f"imported original source is missing: {source_id}")
        original_bytes = original_path.read_bytes()
        if sha256_bytes(original_bytes) != source_row["source_sha256"]:
            raise PipelineError("source_hash_mismatch", f"imported original source hash changed: {source_id}")
        text_path = workspace_path(workspace, source_row["text_path"])
        if not text_path.is_file() or sha256_bytes(text_path.read_bytes()) != source_row["text_sha256"]:
            raise PipelineError("source_text_hash_mismatch", f"normalized source text missing or changed: {source_id}")
        text = text_path.read_text(encoding="utf-8")
        if source_row["source_kind"] in {"utf8_text", "utf8_markdown"}:
            derived_text, derived_status, _ = _canonical_text(original_bytes, source_row["relative_path"])
            if text != derived_text or source_row["full_text_status"] != derived_status:
                raise PipelineError("source_text_hash_mismatch", f"normalized text is not derived from imported source: {source_id}")
        lines = text.splitlines(keepends=True)
        if len(lines) != source_row["line_count"]:
            raise PipelineError("source_text_hash_mismatch", f"line count changed: {source_id}")
        ordered = sorted(chunks_by_source[source_id], key=lambda row: row["start_line"])
        expected_start = 1
        if [row["chunk_id"] for row in ordered] != source_row["chunk_ids"]:
            raise PipelineError("chunk_coverage_failure", f"source chunk order differs: {source_id}")
        for chunk in ordered:
            if chunk["start_line"] != expected_start or chunk["end_line"] < chunk["start_line"]:
                raise PipelineError("chunk_coverage_failure", f"gap or overlap before {chunk['chunk_id']}")
            expected_bytes = "".join(lines[chunk["start_line"] - 1:chunk["end_line"]]).encode("utf-8")
            chunk_path = workspace_path(workspace, chunk["path"])
            if not chunk_path.is_file() or chunk_path.read_bytes() != expected_bytes:
                raise PipelineError("chunk_hash_mismatch", f"chunk content does not match source lines: {chunk['chunk_id']}")
            if sha256_bytes(expected_bytes) != chunk["sha256"]:
                raise PipelineError("chunk_hash_mismatch", f"chunk hash does not match: {chunk['chunk_id']}")
            expected_chunk_id = "chunk-" + sha256_bytes(
                source_id.encode("utf-8")
                + f":{chunk['start_line']}:{chunk['end_line']}:".encode("ascii")
                + expected_bytes
            )[:20]
            if chunk["chunk_id"] != expected_chunk_id:
                raise PipelineError("chunk_identity_mismatch", f"chunk_id does not match content/locator: {chunk['chunk_id']}")
            expected_start = chunk["end_line"] + 1
        if expected_start != source_row["line_count"] + 1:
            raise PipelineError("chunk_coverage_failure", f"source tail is not chunked: {source_id}")

    source_map = load_json(workspace / "distilled" / "source-map.json")
    validate_instance(source_map, _schema("source-map.v2.schema.json"))
    if source_map["source_manifest_sha256"] != manifest_sha:
        raise PipelineError("manifest_hash_mismatch", "source map does not match source-manifest bytes")
    entries = {entry["chunk_id"]: entry for entry in source_map["entries"]}
    if len(entries) != len(source_map["entries"]) or set(entries) != set(chunks):
        raise PipelineError("unreferenced_chunk", "source map must reference every chunk exactly once")

    records: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    referenced_chunks: set[str] = set()
    expert_titles: dict[str, str] = {}
    global_anti_actions: dict[str, str] = {}
    for item in queue["items"]:
        artifact_path = workspace_path(workspace, item["artifact_path"])
        if not artifact_path.is_file():
            raise PipelineError("unprocessed_chunk", f"distilled artifact is missing: {item['chunk_id']}")
        record = load_json(artifact_path)
        validate_instance(record, _schema("distilled-chunk.v2.schema.json"))
        chunk = chunks[item["chunk_id"]]
        if record["chunk_id"] != item["chunk_id"] or record["chunk_sha256"] != chunk["sha256"]:
            raise PipelineError("chunk_artifact_mismatch", f"artifact identity/hash mismatch: {item['chunk_id']}")
        if record["processing_status"] != item["status"] or record["processing_status"] == "pending":
            raise PipelineError("unprocessed_chunk", f"artifact/queue status is incomplete: {item['chunk_id']}")
        top = record["chunk_provenance"]
        if (
            top["source_id"] != chunk["source_id"]
            or top["start_line"] != chunk["start_line"]
            or top["end_line"] != chunk["end_line"]
            or top["page_range"] != chunk["page_range"]
        ):
            raise PipelineError("broken_provenance", f"chunk provenance does not match manifest: {item['chunk_id']}")
        if record["processing_status"] == "complete":
            if not record["chunk_summary"].strip() or not record["knowledge_nodes"]:
                raise PipelineError("unprocessed_chunk", f"complete artifact lacks semantic content: {item['chunk_id']}")
            if record["no_reusable_reason"].strip():
                raise PipelineError("invalid_distillation", "complete artifact must not set no_reusable_reason")
        else:
            if record["knowledge_nodes"] or not record["no_reusable_reason"].strip():
                raise PipelineError("invalid_distillation", "no-reusable artifact needs no nodes and a reason")
            referenced_chunks.add(item["chunk_id"])
        for note in record["anti_trigger_notes"]:
            normalized_note = normalize(note["term"])
            previous_action = global_anti_actions.get(normalized_note)
            if previous_action is not None:
                detail = "conflicting actions" if previous_action != note["action"] else "duplicate term"
                raise PipelineError("invalid_distillation", f"global anti-trigger has {detail}: {note['term']}")
            global_anti_actions[normalized_note] = note["action"]

        record_node_ids: list[str] = []
        own_chunk_referenced = False
        for node in record["knowledge_nodes"]:
            if node["node_id"] in node_ids:
                raise PipelineError("duplicate_node_id", f"duplicate node_id: {node['node_id']}")
            node_ids.add(node["node_id"])
            record_node_ids.append(node["node_id"])
            prior_title = expert_titles.setdefault(node["expert_id"], node["title"])
            if prior_title != node["title"]:
                raise PipelineError("invalid_distillation", f"expert title drift for {node['expert_id']}")
            normalized_terms = [normalize(term["term"]) for term in node["l0"]["trigger_terms"]]
            if len(normalized_terms) != len(set(normalized_terms)):
                raise PipelineError("invalid_distillation", f"duplicate normalized trigger term: {node['node_id']}")
            l3_path = workspace_path(workspace, node["l3"]["path"])
            if not node["l3"]["path"].startswith("distilled/l3/") or not l3_path.is_file():
                raise PipelineError("missing_l3", f"L3 path is absent/outside distilled/l3: {node['node_id']}")
            l3_text = l3_path.read_text(encoding="utf-8").strip()
            if len(l3_text) < 80 or "AGENT MUST REPLACE" in l3_text or "<write" in l3_text.casefold():
                raise PipelineError("missing_l3", f"L3 path is empty/template/non-substantive: {node['node_id']}")
            for provenance in node["provenance"]:
                cited = chunks.get(provenance["chunk_id"])
                if cited is None or provenance["source_id"] != cited["source_id"]:
                    raise PipelineError("broken_provenance", f"unknown chunk/source locator: {node['node_id']}")
                if not (
                    cited["start_line"] <= provenance["start_line"] <= provenance["end_line"] <= cited["end_line"]
                ):
                    raise PipelineError("broken_provenance", f"line locator escapes cited chunk: {node['node_id']}")
                referenced_chunks.add(cited["chunk_id"])
                if cited["chunk_id"] == item["chunk_id"]:
                    own_chunk_referenced = True
        if record["processing_status"] == "complete" and not own_chunk_referenced:
            raise PipelineError("unreferenced_chunk", f"artifact does not cite its own source chunk: {item['chunk_id']}")
        entry = entries[item["chunk_id"]]
        if (
            entry["artifact_path"] != item["artifact_path"]
            or entry["processing_status"] != item["status"]
            or entry["node_ids"] != record_node_ids
        ):
            raise PipelineError("source_map_mismatch", f"source-map entry differs from artifact: {item['chunk_id']}")
        records.append(record)
    if referenced_chunks != set(chunks):
        raise PipelineError("unreferenced_chunk", f"chunks not cited by semantic artifacts: {sorted(set(chunks)-referenced_chunks)}")

    shared_core = workspace / "distilled" / "shared-core.md"
    if not shared_core.is_file():
        raise PipelineError("missing_shared_core", "distilled/shared-core.md is missing")
    shared_text = shared_core.read_text(encoding="utf-8")
    if not shared_text.strip() or "AGENT MUST REPLACE" in shared_text:
        raise PipelineError("unprocessed_shared_core", "shared core is still empty/template content")
    semantic_review_path = workspace / "distilled" / "semantic-review.json"
    semantic_review = load_json(semantic_review_path)
    validate_instance(semantic_review, _schema("semantic-review.v2.schema.json"))
    if semantic_review["review_status"] != "complete":
        raise PipelineError("semantic_review_incomplete", "semantic review declaration remains pending")
    if semantic_review["source_manifest_sha256"] != manifest_sha:
        raise PipelineError("semantic_review_mismatch", "semantic review declaration does not match source manifest")
    if semantic_review["reviewed_chunk_ids"] != queue_ids:
        raise PipelineError("semantic_review_mismatch", "semantic review must list every queue chunk once in order")
    if not all(semantic_review["criteria"].values()):
        raise PipelineError("semantic_review_incomplete", "all source-aware semantic review criteria must be affirmed")
    if "REPLACE" in semantic_review["reviewer"]["reviewer_label"] or "REPLACE" in semantic_review["review_assertion"]:
        raise PipelineError("semantic_review_incomplete", "semantic review declaration still contains template markers")
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha,
        "queue": queue,
        "source_map": source_map,
        "records": records,
        "semantic_review": semantic_review,
        "node_count": len(node_ids),
    }


def _distillation_digest(workspace: Path, validated: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_bytes(validated["source_map"]))
    for record in sorted(validated["records"], key=lambda item: item["chunk_id"]):
        digest.update(canonical_bytes(record))
        for node in record["knowledge_nodes"]:
            digest.update(workspace_path(workspace, node["l3"]["path"]).read_bytes())
    digest.update((workspace / "distilled" / "shared-core.md").read_bytes())
    digest.update(canonical_bytes(validated["semantic_review"]))
    return digest.hexdigest()


def build_registry(workspace: Path) -> tuple[Path, Path, dict[str, Any]]:
    workspace = workspace.resolve()
    validated = validate_distillation(workspace)
    policy = load_json(ROUTING_POLICY)
    if not isinstance(policy, dict) or policy.get("contract_version") != CONTRACT_VERSION:
        raise PipelineError("schema_version_mismatch", "routing policy contract version mismatch")
    chunks = {row["chunk_id"]: row for row in validated["manifest"]["chunks"]}
    expert_acc: dict[str, dict[str, Any]] = {}
    global_anti: dict[tuple[str, str], dict[str, str]] = {}
    for record in sorted(validated["records"], key=lambda item: item["chunk_id"]):
        for note in record["anti_trigger_notes"]:
            if note["scope"] == "global":
                key = (normalize(note["term"]), note["action"])
                global_anti.setdefault(key, {
                    "term": note["term"],
                    "action": note["action"],
                    "reason": note["reason"],
                })
        for node in sorted(record["knowledge_nodes"], key=lambda item: item["node_id"]):
            expert = expert_acc.setdefault(node["expert_id"], {
                "expert_id": node["expert_id"],
                "title": node["title"],
                "tie_break_priority": node["routing_priority"],
                "one_liners": [],
                "trigger_terms_by_normalized": {},
                "anti_trigger_terms": [],
                "risk_tags": [],
                "l1_modules": [],
                "l2_modules": [],
                "l3_files_by_path": {},
                "chunks_by_id": {},
            })
            expert["tie_break_priority"] = min(expert["tie_break_priority"], node["routing_priority"])
            if node["l0"]["one_liner"] not in expert["one_liners"]:
                expert["one_liners"].append(node["l0"]["one_liner"])
            for term in node["l0"]["trigger_terms"]:
                key = normalize(term["term"])
                current = expert["trigger_terms_by_normalized"].get(key)
                if current is None or term["weight"] > current["weight"]:
                    expert["trigger_terms_by_normalized"][key] = dict(term)
            for term in node["l0"]["anti_trigger_terms"]:
                if term not in expert["anti_trigger_terms"]:
                    expert["anti_trigger_terms"].append(term)
            for tag in node["risk_tags"]:
                if tag not in expert["risk_tags"]:
                    expert["risk_tags"].append(tag)
            expert["l1_modules"].append({
                "node_id": node["node_id"],
                "brief": node["l1"]["brief"],
                "safety_red_lines": node["l1"]["safety_red_lines"],
                "uncertainties": node["l1"]["uncertainties"],
            })
            expert["l2_modules"].append({
                "node_id": node["node_id"],
                "workflow": node["l2"]["workflow"],
                "load_more_if": node["l2"]["load_more_if"],
            })
            l3_relative = node["l3"]["path"]
            expert["l3_files_by_path"].setdefault(l3_relative, {
                "path": l3_relative,
                "sha256": sha256_bytes(workspace_path(workspace, l3_relative).read_bytes()),
            })
            for provenance in node["provenance"]:
                chunk = chunks[provenance["chunk_id"]]
                expert["chunks_by_id"].setdefault(provenance["chunk_id"], {
                    "chunk_id": provenance["chunk_id"],
                    "path": chunk["path"],
                    "sha256": chunk["sha256"],
                    "source_id": chunk["source_id"],
                    "source_path": chunk["source_path"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "page_range": chunk["page_range"],
                })

    experts: list[dict[str, Any]] = []
    for expert_id in sorted(expert_acc):
        item = expert_acc[expert_id]
        experts.append({
            "expert_id": item["expert_id"],
            "title": item["title"],
            "tie_break_priority": item["tie_break_priority"],
            "one_liners": item["one_liners"],
            "trigger_terms": sorted(item["trigger_terms_by_normalized"].values(), key=lambda term: normalize(term["term"])),
            "anti_trigger_terms": item["anti_trigger_terms"],
            "risk_tags": sorted(item["risk_tags"]),
            "l1_modules": sorted(item["l1_modules"], key=lambda module: module["node_id"]),
            "l2_modules": sorted(item["l2_modules"], key=lambda module: module["node_id"]),
            "l3_files": [item["l3_files_by_path"][path] for path in sorted(item["l3_files_by_path"])],
            "chunks": [item["chunks_by_id"][chunk_id] for chunk_id in sorted(item["chunks_by_id"])],
        })
    if not experts:
        raise PipelineError("build_no_experts", "validated distillation contains no reusable expert nodes")
    distillation_sha = _distillation_digest(workspace, validated)
    registry_base = {
        "contract_version": CONTRACT_VERSION,
        "registry_id": "distilled-" + validated["manifest"]["manifest_id"].removeprefix("manifest-"),
        "source_manifest_sha256": validated["manifest_sha256"],
        "distillation_sha256": distillation_sha,
        "shared_core_path": "distilled/shared-core.md",
        "shared_core_sha256": sha256_bytes((workspace / "distilled" / "shared-core.md").read_bytes()),
        "routing": policy["scoring"],
        "safety_sweep": policy["safety_sweep"],
        "global_anti_triggers": [global_anti[key] for key in sorted(global_anti)],
        "experts": experts,
    }
    registry = dict(registry_base)
    registry["build_id"] = "build-" + sha256_bytes(canonical_bytes(registry_base))[:20]
    registry = {
        "contract_version": registry["contract_version"],
        "registry_id": registry["registry_id"],
        "build_id": registry["build_id"],
        "source_manifest_sha256": registry["source_manifest_sha256"],
        "distillation_sha256": registry["distillation_sha256"],
        "shared_core_path": registry["shared_core_path"],
        "shared_core_sha256": registry["shared_core_sha256"],
        "routing": registry["routing"],
        "safety_sweep": registry["safety_sweep"],
        "global_anti_triggers": registry["global_anti_triggers"],
        "experts": registry["experts"],
    }
    validate_instance(registry, _schema("expert-registry.v2.schema.json"))
    build_dir = workspace / "build"
    registry_path = build_dir / "expert-registry.v2.json"
    write_json(registry_path, registry)
    registry_sha = sha256_bytes(registry_path.read_bytes())
    index = {
        "contract_version": CONTRACT_VERSION,
        "registry_id": registry["registry_id"],
        "build_id": registry["build_id"],
        "registry_sha256": registry_sha,
        "routing": registry["routing"],
        "safety_sweep": registry["safety_sweep"],
        "global_anti_triggers": registry["global_anti_triggers"],
        "experts": [
            {
                "expert_id": expert["expert_id"],
                "tie_break_priority": expert["tie_break_priority"],
                "trigger_terms": expert["trigger_terms"],
                "anti_trigger_terms": expert["anti_trigger_terms"],
                "l3_files": expert["l3_files"],
                "chunk_ids": [chunk["chunk_id"] for chunk in expert["chunks"]],
            }
            for expert in registry["experts"]
        ],
    }
    validate_instance(index, _schema("expert-index.v2.schema.json"))
    index_path = build_dir / "expert-index.v2.json"
    write_json(index_path, index)
    return registry_path, index_path, registry


def query_registry(registry_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    registry_path = registry_path.resolve()
    registry = load_json(registry_path)
    validate_instance(registry, _schema("expert-registry.v2.schema.json"))
    validate_instance(request, _schema("query-request.v2.schema.json"))
    if not request["query"].strip():
        raise PipelineError("malformed_input", "query must contain non-whitespace text")
    registry_sha = sha256_bytes(registry_path.read_bytes())
    registry_base = {key: value for key, value in registry.items() if key != "build_id"}
    expected_build_id = "build-" + sha256_bytes(canonical_bytes(registry_base))[:20]
    if registry["build_id"] != expected_build_id:
        raise PipelineError("registry_identity_mismatch", "build_id does not match canonical registry content")
    workspace = registry_path.parent.parent
    manifest_path = workspace / "source-manifest.json"
    if not manifest_path.is_file() or sha256_bytes(manifest_path.read_bytes()) != registry["source_manifest_sha256"]:
        raise PipelineError("manifest_hash_mismatch", "built registry does not match workspace source-manifest bytes")
    index_path = registry_path.parent / "expert-index.v2.json"
    if not index_path.is_file():
        raise PipelineError("missing_index", "expert-index.v2.json is required beside the registry")
    index = load_json(index_path)
    validate_instance(index, _schema("expert-index.v2.schema.json"))
    expected_index = {
        "contract_version": CONTRACT_VERSION,
        "registry_id": registry["registry_id"],
        "build_id": registry["build_id"],
        "registry_sha256": registry_sha,
        "routing": registry["routing"],
        "safety_sweep": registry["safety_sweep"],
        "global_anti_triggers": registry["global_anti_triggers"],
        "experts": [
            {
                "expert_id": expert["expert_id"],
                "tie_break_priority": expert["tie_break_priority"],
                "trigger_terms": expert["trigger_terms"],
                "anti_trigger_terms": expert["anti_trigger_terms"],
                "l3_files": expert["l3_files"],
                "chunk_ids": [chunk["chunk_id"] for chunk in expert["chunks"]],
            }
            for expert in registry["experts"]
        ],
    }
    if index != expected_index:
        raise PipelineError("index_registry_mismatch", "sparse index does not exactly match its built registry")

    query_text = normalize(request["query"])
    scoring = index["routing"]
    top_k = request.get("top_k", scoring["default_top_k"])
    if top_k > scoring["max_top_k"]:
        raise PipelineError("malformed_input", "top_k exceeds built registry maximum")
    global_hits = [item for item in index["global_anti_triggers"] if normalize(item["term"]) in query_text]
    scores: list[dict[str, Any]] = []
    priorities: dict[str, int] = {}
    expert_by_id = {expert["expert_id"]: expert for expert in registry["experts"]}
    for expert in index["experts"]:
        priorities[expert["expert_id"]] = expert["tie_break_priority"]
        positive = [term["term"] for term in expert["trigger_terms"] if normalize(term["term"]) in query_text]
        positive_set = set(positive)
        score = sum(term["weight"] for term in expert["trigger_terms"] if term["term"] in positive_set)
        anti = [term for term in expert["anti_trigger_terms"] if normalize(term) in query_text]
        scores.append({
            "expert_id": expert["expert_id"],
            "score": score,
            "positive_hits": positive,
            "anti_trigger_hits": anti,
            "eligible": score >= scoring["minimum_score"] and not anti,
        })
    scores.sort(key=lambda item: (-item["score"], priorities[item["expert_id"]], item["expert_id"]))
    eligible = [item for item in scores if item["eligible"]]
    if global_hits:
        selected: list[str] = []
        status = "rejected" if any(item["action"] == "reject" for item in global_hits) else "bypassed"
        decision_reason = "global_anti_trigger"
    else:
        selected = [item["expert_id"] for item in eligible[:top_k]]
        status = "selected" if selected else "below_threshold"
        decision_reason = "selected_at_or_above_threshold" if selected else "no_expert_at_or_above_threshold"
    skipped = [item["expert_id"] for item in scores if item["expert_id"] not in selected]
    cutoff_tie = bool(
        selected
        and len(eligible) > len(selected)
        and eligible[len(selected) - 1]["score"] == eligible[len(selected)]["score"]
    )
    ambiguous = status == "below_threshold" or cutoff_tie

    sweep = index["safety_sweep"]
    risk_domains = list(request["risk_domains"])
    for domain, terms in sweep["risk_terms"].items():
        if domain not in risk_domains and any(normalize(term) in query_text for term in terms):
            risk_domains.append(domain)
    high_risk = bool(risk_domains)
    sweep_hits = [f"anti_trigger:{item['action']}:{item['term']}" for item in global_hits]
    for check_id, terms in sweep["lexical_indicators"].items():
        for term in terms:
            if normalize(term) in query_text:
                sweep_hits.append(f"indicator:{check_id}:{term}")
    sweep_hits.extend(f"high_risk:{domain}" for domain in risk_domains)
    safety_experts = [
        expert_id for expert_id in sweep["safety_expert_ids"]
        if (high_risk or ambiguous) and expert_id in expert_by_id
    ]
    active_ids = selected + [expert_id for expert_id in safety_experts if expert_id not in selected]

    module_paths: list[str] = []
    module_hashes: dict[str, str] = {}
    chunk_objects: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    for expert_id in active_ids:
        expert = expert_by_id[expert_id]
        for l3_file in expert["l3_files"]:
            relative = l3_file["path"]
            full = workspace_path(workspace, relative)
            if not full.is_file() or sha256_bytes(full.read_bytes()) != l3_file["sha256"]:
                raise PipelineError("missing_l3", f"built registry L3 path is missing/changed: {relative}")
            rendered = full.as_posix()
            if rendered not in module_paths:
                module_paths.append(rendered)
                module_hashes[rendered] = l3_file["sha256"]
        for chunk in expert["chunks"]:
            if chunk["chunk_id"] in seen_chunks:
                continue
            seen_chunks.add(chunk["chunk_id"])
            full = workspace_path(workspace, chunk["path"])
            if not full.is_file() or sha256_bytes(full.read_bytes()) != chunk["sha256"]:
                raise PipelineError("missing_chunk", f"built registry chunk path is missing/changed: {chunk['path']}")
            item = dict(chunk)
            item["path"] = full.as_posix()
            chunk_objects.append(item)
    shared_core_path = workspace_path(workspace, registry["shared_core_path"])
    if not shared_core_path.is_file() or sha256_bytes(shared_core_path.read_bytes()) != registry["shared_core_sha256"]:
        raise PipelineError("missing_shared_core", "built registry shared core is missing/changed")
    shared_core = shared_core_path.as_posix()
    files_to_load = [shared_core] + module_paths
    file_checksums = [{"path": shared_core, "sha256": registry["shared_core_sha256"], "role": "shared_core"}]
    file_checksums.extend({"path": path, "sha256": module_hashes[path], "role": "expert_l3"} for path in module_paths)
    output = {
        "contract_version": CONTRACT_VERSION,
        "registry_id": registry["registry_id"],
        "build_id": registry["build_id"],
        "registry_sha256": registry_sha,
        "query_id": request["query_id"],
        "status": status,
        "decision_reason": decision_reason,
        "route_scores": scores,
        "selected_experts": selected,
        "skipped_experts": skipped,
        "safety_sweep": {
            "activated": True,
            "phase": "post_route",
            "high_risk": high_risk,
            "ambiguous": ambiguous,
            "risk_domains": risk_domains,
            "baseline_checks": list(sweep["baseline_checks"]),
            "extra_checks": list(sweep["high_risk_or_ambiguous_extra_checks"]) if (high_risk or ambiguous) else [],
            "safety_experts_activated": safety_experts,
            "hits": sweep_hits,
        },
        "load_plan": {
            "path_base": workspace.as_posix(),
            "files_to_load": files_to_load,
            "file_checksums": file_checksums,
            "expert_module_files": module_paths,
            "source_chunks": chunk_objects,
        },
        "audit_log": [
            {"sequence": 1, "event": "query_and_index_validated", "details": {"explicit_risk_domains": request["risk_domains"], "registry_sha256": registry_sha}},
            {"sequence": 2, "event": "experts_scored", "details": {"threshold": scoring["minimum_score"], "scores": {item["expert_id"]: item["score"] for item in scores}}},
            {"sequence": 3, "event": "experts_selected", "details": {"status": status, "selected_experts": selected}},
            {"sequence": 4, "event": "mandatory_safety_sweep_completed", "details": {"high_risk": high_risk, "ambiguous": ambiguous, "hits": sweep_hits}},
            {"sequence": 5, "event": "exact_load_plan_created", "details": {"file_count": len(files_to_load), "chunk_count": len(chunk_objects)}},
        ],
    }
    validate_instance(output, _schema("query-output.v2.schema.json"))
    return output
