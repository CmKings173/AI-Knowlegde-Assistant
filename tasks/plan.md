# Implementation Plan: RAG Router, Faithfulness And Citation Hardening

## Overview
Fix the current production-risk bugs where out-of-scope questions can be answered by the conversational LLM, vague NAS follow-ups can bypass retrieval or retrieve the wrong section, cited answers can contain unsupported modality claims, and frontend citation labels can show mismatched `SOURCE_X` markers.

## Architecture Decisions
- Keep rule-based fast paths for clear cases, but tighten domain gating before any conversational LLM call.
- Route contextual NAS/mobile/detail follow-ups into query rewrite plus retrieval instead of conversational generation.
- Extend fact validation from day/time claims to critical retrieval modality terms such as mobile app vs internal network access.
- Keep citation IDs stable from backend to frontend; UI labels must reflect `citation_id`, not render order.
- Use regression tests for each reported behavior before implementation.

## Task List

### Phase 1: Reproduction Tests
- [ ] Add router tests for out-of-scope cat questions.
- [ ] Add router tests for NAS mobile follow-up classification.
- [ ] Add parser/UI tests for comma-separated `SOURCE_X` markers.
- [ ] Add guard tests for answers that mention mobile/app terms not supported by cited context.

### Phase 2: Backend Guardrails
- [ ] Tighten out-of-scope gating before conversational LLM.
- [ ] Expand contextual follow-up detection for mobile/detail terms.
- [ ] Strengthen query rewrite prompt for vague follow-ups.
- [ ] Extend fact guard with critical support terms.

### Phase 3: Frontend Citation UX
- [ ] Convert comma-separated source markers like `[SOURCE_1, SOURCE_3]` to `[1], [3]`.
- [ ] Render source panel labels from `citation.citation_id`.

### Checkpoint
- [ ] `uv run ruff check . --no-cache`
- [ ] `uv run python -m pytest tests/unit -q`
- [ ] `npm run build` from `frontend/`

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Over-blocking normal chat | Medium | Only block clear out-of-domain factual topics before LLM; keep greetings/meta questions conversational |
| False positive modality guard | Medium | Guard only critical explicit terms that must be present in cited context |
| Follow-up rewrite adds unsupported context | High | Prompt rewrite to use only current question plus conversation history, not external assumptions |
| Citation label mismatch remains confusing | Medium | Derive displayed label directly from backend `citation_id` |
