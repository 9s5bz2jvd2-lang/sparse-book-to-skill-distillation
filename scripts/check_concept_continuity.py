#!/usr/bin/env python3
"""Conceptual-continuity regression gate.

Fails if the network->ring->sphere design core, its connected low-power
invariants, or the implemented-versus-protocol-only status anchors are deleted
from the governing documents. This is deliberately more than a single-slogan
grep: each phrase is one connected invariant (concept, gate, or status boundary),
and the concept-to-implementation binding checks that the named executable
artifacts still exist. It is a phrase/binding regression gate, not proof that no
contradictory prose exists elsewhere; semantic review remains required.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (file, required phrase, invariant it protects). Phrases are matched
# casefolded; casefolding leaves CJK text unchanged.
REQUIRED_ANCHORS: list[tuple[str, str, str]] = [
    # Core statement and motto: network gives reachability, ring gives low power.
    ("README.md", "网给 skill 以通达，环给 skill 以低功耗", "core motto: network=reachability, ring=low-power"),
    ("README.md", "回流成丹", "sphere: branches return as compressed reusable structure"),
    ("README.md", "network → ring → sphere", "conclusion-first network/ring/sphere framing"),
    ("SKILL.md", "网给 skill 以通达，环给 skill 以低功耗", "core motto present at the agent entry"),
    # Structural invariant that carries all three concepts.
    ("README.md", "cyclic return-to-cache feedback loop", "structural invariant: return-to-cache loop"),
    ("SKILL.md", "cyclic return-to-cache feedback loop", "structural invariant at the agent entry"),
    ("ROUTING.yaml", "cyclic return-to-cache feedback loop", "structural invariant in the routing locator"),
    # Low-power gate: routing overhead below saved cost; small tasks bypass routing.
    ("README.md", "routing overhead stays below the cost it saves", "low-power acceptance gate"),
    ("SKILL.md", "路由成本必须小于其节省的成本", "low-power acceptance gate at the agent entry"),
    ("CACHE.md", "routing cost must stay below saved cost", "low-power gate in cache policy"),
    ("CACHE.md", "direct execution for small tasks", "small tasks execute without the router"),
    # Ring return leg and sphere acceptance across policy docs.
    ("CACHE.md", "回到命中的缓存", "ring returns to the hit cache"),
    ("GRAPH.md", "incomplete until it returns as compressed reusable structure", "sphere acceptance in graph doc"),
    ("RULES.md", "branching is incomplete until it returns as compressed reusable structure", "sphere acceptance as repository rule"),
    # Implemented vs protocol-only status boundary (must stay truthful).
    ("README.md", "not implemented — protocol only", "self-modifying signatures/cache are not implemented"),
    ("README.md", "not automatic learning", "residual bank is not automatic learning"),
    ("docs/self-evolution-loop.md", "inner loop (executable today)", "inner residual loop labeled executable"),
    ("docs/self-evolution-loop.md", "outer loop (this protocol, human-gated)", "outer improvement labeled human-gated protocol"),
    ("ROUTING.yaml", "human-gated", "status boundary in the routing locator"),
]

# The inner ring must remain bound to real executable artifacts, so the concept
# cannot silently become prose-only again.
IMPLEMENTATION_BINDINGS: list[tuple[str, str | None, str]] = [
    ("scripts/graph_query.py", "residual", "residual-bank inner return loop implementation"),
    ("scripts/graph_build.py", None, "graph/vector network build implementation"),
    ("contracts/residual-bank.v1.schema.json", None, "residual bank contract"),
    ("contracts/vector-index.v1.schema.json", None, "multidimensional vector contract"),
    ("contracts/graph-registry.v1.schema.json", None, "cross-linked graph contract"),
]


def collect_failures() -> list[str]:
    failures: list[str] = []
    for rel_path, phrase, invariant in REQUIRED_ANCHORS:
        path = ROOT / rel_path
        if not path.is_file():
            failures.append(f"{rel_path}: missing file ({invariant})")
            continue
        if phrase.casefold() not in path.read_text(encoding="utf-8").casefold():
            failures.append(f"{rel_path}: lost invariant {invariant!r} (expected {phrase!r})")
    for rel_path, phrase, invariant in IMPLEMENTATION_BINDINGS:
        path = ROOT / rel_path
        if not path.is_file():
            failures.append(f"{rel_path}: missing executable binding ({invariant})")
            continue
        if phrase is not None and phrase.casefold() not in path.read_text(encoding="utf-8").casefold():
            failures.append(f"{rel_path}: no longer references {phrase!r} ({invariant})")
    return failures


def main() -> int:
    failures = collect_failures()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(
        "PASS conceptual continuity: network/ring/sphere core, low-power gate, "
        f"return-to-cache invariant, and status boundary verified across {len(REQUIRED_ANCHORS)} anchors "
        f"and {len(IMPLEMENTATION_BINDINGS)} executable bindings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
