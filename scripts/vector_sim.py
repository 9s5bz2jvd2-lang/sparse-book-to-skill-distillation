#!/usr/bin/env python3
"""Deterministic vector similarity module for graph-sparse atomic routing.

Provides:
- named multi-dimensional vectors per atomic node with channel/dimension/model metadata
- deterministic local cosine-similarity scoring using synthetic numeric fixtures
- multi-channel weighted fusion (semantic/task/risk)
- pluggable embedder/index contract for future local embedding model
- strict fail-closed policy for invalid vectors, channels, backends, metadata
- no network or external dependency

Vectors are a sparse-addressing signal, not source truth.  Fixture vectors
are NOT real semantic embeddings — they are deterministic synthetic numeric
fixtures for interface validation only.
"""

from __future__ import annotations

import math
from typing import Any

from contract_validation import ContractError


class VectorError(ContractError):
    """Vector interface failure with machine-assertable code."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_vector(values: list[float], expected_dim: int, label: str = "vector") -> None:
    """Fail closed on invalid vectors: wrong dimension, non-finite, empty."""
    if not isinstance(values, list) or not values:
        raise VectorError("invalid_vector", f"{label}: vector is empty or not a list")
    if not isinstance(expected_dim, int) or isinstance(expected_dim, bool) or expected_dim < 1:
        raise VectorError("invalid_channel_config", f"{label}: expected dimension must be a positive integer")
    if len(values) != expected_dim:
        raise VectorError("dimension_mismatch", f"{label}: expected dim={expected_dim}, got dim={len(values)}")
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise VectorError("invalid_vector", f"{label}: non-numeric value at index {i}")
        if not math.isfinite(v):
            raise VectorError("invalid_vector", f"{label}: non-finite value at index {i}: {v}")


def validate_channel_config(channels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate unique, positive, fully specified channel metadata."""
    by_name: dict[str, dict[str, Any]] = {}
    for channel in channels:
        name = channel.get("channel_name")
        if not isinstance(name, str) or not name.strip():
            raise VectorError("missing_metadata", "vector channel missing non-empty channel_name")
        if name in by_name:
            raise VectorError("duplicate_channel", f"duplicate vector channel config: {name}")
        dimension = channel.get("dimension")
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
            raise VectorError("invalid_channel_config", f"channel {name}: dimension must be a positive integer")
        weight = channel.get("weight", 1.0)
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not math.isfinite(weight) or weight <= 0:
            raise VectorError("invalid_channel_config", f"channel {name}: weight must be finite and > 0")
        for field in ("model_id", "model_version"):
            if not isinstance(channel.get(field), str) or not channel[field].strip():
                raise VectorError("missing_metadata", f"channel {name}: missing non-empty {field}")
        by_name[name] = channel
    return by_name


def validate_node_vectors(
    node: dict[str, Any],
    channels: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Validate node vectors, uniqueness and optional channel metadata binding."""
    vectors = node.get("vectors", [])
    configured = validate_channel_config(channels) if channels is not None else None
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    node_id = node.get("node_id", "?")
    for vec in vectors:
        for field in ("channel_name", "dimension", "model_id", "model_version", "values"):
            if field not in vec:
                raise VectorError("missing_metadata", f"node {node_id}: vector missing {field}")
        name = vec["channel_name"]
        if name in seen:
            raise VectorError("duplicate_channel", f"node {node_id}: duplicate vector channel {name}")
        seen.add(name)
        if configured is not None:
            if name not in configured:
                raise VectorError("unknown_channel", f"node {node_id}: unconfigured vector channel {name}")
            meta = configured[name]
            for field in ("dimension", "model_id", "model_version"):
                if vec[field] != meta[field]:
                    raise VectorError(
                        "vector_metadata_mismatch",
                        f"node {node_id} channel {name}: {field}={vec[field]!r} does not match configured {meta[field]!r}",
                    )
        validate_vector(vec["values"], vec["dimension"], f"node={node_id} channel={name}")
        validated.append(vec)
    return validated


# ---------------------------------------------------------------------------
# Deterministic cosine similarity (default/local)
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity; fail closed on dimension mismatch."""
    if len(a) != len(b):
        raise VectorError("dimension_mismatch", f"cosine_similarity: dim_a={len(a)} != dim_b={len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Embedder backend interface (pluggable)
# ---------------------------------------------------------------------------

class EmbedderBackend:
    """Abstract embedder backend.  Default implementation uses synthetic fixtures.

    Future backends (local_model, sidecar_index) can be attached by subclassing
    and registering via register_backend().
    """

    def __init__(self, backend_type: str = "none") -> None:
        self.backend_type = backend_type

    def is_available(self) -> bool:
        """Whether this backend can produce/query embeddings."""
        return self.backend_type == "none"  # Default: no embedding, use fixtures

    def embed_query(self, query_text: str, channel: str, dimension: int) -> list[float] | None:
        """Produce a query vector.  Returns None if not available (caller falls back)."""
        return None  # Default: no embedding available

    def query_index(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        """Query a sidecar index.  Returns list of {node_id, similarity_score}."""
        return []  # Default: no index


# Global registry of backends
_BACKENDS: dict[str, EmbedderBackend] = {"none": EmbedderBackend("none")}


def register_backend(name: str, backend: EmbedderBackend) -> None:
    """Register a pluggable embedder backend."""
    _BACKENDS[name] = backend


def get_backend(name: str) -> EmbedderBackend:
    """Get a registered backend; fail closed if unavailable."""
    if name not in _BACKENDS:
        raise VectorError("backend_unavailable", f"embedder backend '{name}' is not registered")
    return _BACKENDS[name]


def resolve_backend(backend_type: str) -> EmbedderBackend:
    """Resolve and return the configured backend; fail closed if not registered."""
    return get_backend(backend_type)


# ---------------------------------------------------------------------------
# Multi-channel vector fusion scoring
# ---------------------------------------------------------------------------

def score_vector_candidates(
    nodes: list[dict[str, Any]],
    query_vectors: dict[str, list[float]],
    channels: list[dict[str, Any]],
    top_k: int = 5,
    minimum_similarity: float = 0.0,
) -> dict[str, Any]:
    """Score atomic nodes by multi-channel weighted vector similarity; return full trace.

    Channels from graph registry vector_config with weights.
    Fused score = sum(weight_ch * cosine_sim_ch) / sum(weight_ch) for scored channels.

    Returns:
        {
            "candidate_vectors_scored": int,
            "vector_candidates": [{node_id, fused_score, channel_scores}, ...],
            "vector_exclusions": [{node_id, reason}, ...],
            "error": str | None,
        }
    """
    if not query_vectors:
        return {
            "candidate_vectors_scored": 0,
            "vector_candidates": [],
            "vector_exclusions": [],
            "error": None,
        }

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise VectorError("invalid_top_k", "vector top_k must be a positive integer")

    # Build strictly validated channel metadata.
    channel_meta = validate_channel_config(channels)

    # Validate all query vectors against channel configs
    for ch_name, qvec in query_vectors.items():
        if ch_name not in channel_meta:
            raise VectorError("unknown_channel", f"query vector for unknown channel: {ch_name}")
        expected_dim = channel_meta[ch_name]["dimension"]
        validate_vector(qvec, expected_dim, f"query_vector:{ch_name}")

    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    scored = 0

    for node in nodes:
        node_vectors = node.get("vectors", [])
        if not node_vectors:
            exclusions.append({"node_id": node["node_id"], "reason": "no_vectors_attached"})
            continue

        # Fail closed on duplicate, malformed or metadata-mismatched node vectors.
        validated_vectors = validate_node_vectors(node, channels)
        node_vec_by_ch = {vec["channel_name"]: vec for vec in validated_vectors}

        channel_scores: dict[str, float] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for ch_name, qvec in query_vectors.items():
            if ch_name not in node_vec_by_ch:
                exclusions.append({"node_id": node["node_id"], "reason": f"no_vector_for_channel:{ch_name}"})
                continue

            node_vec = node_vec_by_ch[ch_name]
            expected_dim = channel_meta[ch_name]["dimension"]

            # Dimension check
            if len(qvec) != expected_dim or node_vec["dimension"] != expected_dim:
                exclusions.append({
                    "node_id": node["node_id"],
                    "reason": f"dimension_mismatch_channel:{ch_name}",
                })
                continue

            sim = cosine_similarity(qvec, node_vec["values"])
            weight = channel_meta[ch_name].get("weight", 1.0)
            channel_scores[ch_name] = round(sim, 10)
            total_weight += weight
            weighted_sum += weight * sim

        if not channel_scores:
            continue

        scored += 1
        fused_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        fused_score = round(fused_score, 10)

        if fused_score >= minimum_similarity:
            candidates.append({
                "node_id": node["node_id"],
                "fused_score": fused_score,
                "channel_scores": channel_scores,
            })

    # Sort by fused_score descending, then node_id for determinism
    candidates.sort(key=lambda x: (-x["fused_score"], x["node_id"]))
    candidates = candidates[:top_k]

    return {
        "candidate_vectors_scored": scored,
        "vector_candidates": candidates,
        "vector_exclusions": exclusions,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Symbolic reranking after vector recall
# ---------------------------------------------------------------------------

def symbolic_rerank(
    vector_candidates: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    intent_tokens: list[str],
    anti_trigger_matches: set[str],
    safety_config: dict[str, Any],
    risk_domains: list[str],
) -> dict[str, Any]:
    """Symbolic reranking after vector candidate recall.

    Applies: anti-trigger exclusion, provenance validation.
    Safety nodes are NOT appended globally here; they are handled by scoped
    safety expansion in closure.

    Returns:
        {
            "reranked_ids": [node_id, ...],
            "exclusions": [{node_id, reason}, ...],
        }
    """
    reranked: list[str] = []
    exclusions: list[dict[str, str]] = []

    for vc in vector_candidates:
        nid = vc["node_id"]
        node = nodes_by_id.get(nid)
        if node is None:
            exclusions.append({"node_id": nid, "reason": "node_not_found_in_registry"})
            continue

        # Anti-trigger exclusion
        node_anti = set(a.lower() for a in node.get("anti_triggers", []))
        if node_anti & anti_trigger_matches:
            exclusions.append({"node_id": nid, "reason": "anti_trigger_match"})
            continue

        # Provenance validation: must have valid source_ref
        ref = node.get("source_ref", {})
        if ref.get("ref_type") == "chunk" and not ref.get("chunk_id"):
            exclusions.append({"node_id": nid, "reason": "invalid_provenance"})
            continue

        reranked.append(nid)

    return {
        "reranked_ids": reranked,
        "exclusions": exclusions,
    }
