# L3: source intake and coverage ledger

## Purpose

Establish the exact full-text boundary that semantic distillation must cover.

## Procedure

1. Accept only supported visible files and reject unsupported or unreadable inputs rather than silently skipping them.
2. Archive the imported original bytes and SHA-256, then copy normalized UTF-8 text into the workspace with its own hash.
3. Split every physical line exactly once into deterministic chunks. Record source ID/path, chunk ID/path/hash, start/end lines, and PDF page range when the opted-in adapter provides it.
4. Create one pending work item and artifact path per chunk.
5. Refuse completeness if text/chunk hashes change, chunks have gaps/overlaps, or any queue item remains pending.

## Boundaries

A hash proves identity, not truth, authorship, license, or semantic completeness. Directory intake rejects unsupported visible files; hidden files are intentionally outside the declared source set. PDF extraction requires explicit adapter authorization and successful local `pdftotext` output.

## Provenance

Derived from synthetic source chunk `chunk-199c1e4f467e3bd46732`, lines 3–6.
