# Spec: RAG End-to-End Evaluation Harness

## Objective

Build a production-grade evaluation harness that can tell whether a bad answer is
caused by routing, retrieval, evidence selection, generation, or response
validation. The current repository already has retrieval-level evaluation, but it
does not execute the full user-facing RAG path and cannot explain failures like
"retrieved enough evidence but answered/refused incorrectly".

The harness must run against the same production pipeline used by the API, with
real Qdrant, embedding provider, and configured Qwen/Ollama model on GX10 for
live evaluation. Unit tests must keep the metric and failure-classification logic
deterministic without requiring external services.

## Assumptions

- The live evaluation command is intended to run on GX10 or another environment
  where Qdrant, embeddings, and Ollama are already configured.
- No new reranker, judge model, Langfuse, Ragas, DeepEval, Redis, or database is
  added in this phase.
- Existing retrieval-level evaluation remains supported.
- Ground-truth cases are versioned in Git, while generated reports under `data/`
  are runtime artifacts and must not be committed.
- The first implementation should prefer deterministic assertions over an LLM
  judging another LLM.

## Tech Stack

- Python `>=3.11`
- uv for all local Python commands
- Pytest and pytest-asyncio for unit tests
- Existing RAG stack: FastAPI, Qdrant, BM25, RRF, Ollama/Qwen, configured
  embedding provider
- Existing source layout under `app/rag/`, `scripts/`, and `tests/evaluation/`

## Commands

Focused unit tests:

```powershell
uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py -q
uv run python -m pytest tests/unit/test_retrieval_evaluation.py -q
```

Live evaluation:

```powershell
uv run python scripts/evaluate_rag.py
uv run python scripts/evaluate_rag.py --case-id leave_late_policy
uv run python scripts/evaluate_rag.py --category routing
uv run python scripts/evaluate_rag.py --limit 10
```

Final gate:

```powershell
uv run python -m pytest tests/unit -q
uv run ruff check . --no-cache
uv run python scripts/check_harness.py
```

## Project Structure

- `tests/evaluation/rag_cases.json`: canonical versioned case dataset. Existing
  retrieval fields remain valid; new end-to-end fields are optional but typed.
- `app/rag/evaluation.py`: shared evaluation models, deterministic metrics, and
  first-failure-stage classification.
- `scripts/evaluate_retrieval.py`: existing retrieval-only runner, kept
  backward compatible.
- `scripts/evaluate_rag.py`: new live end-to-end runner using production
  `RAGPipeline`.
- `data/evaluation/rag_e2e_report.json`: generated detailed runtime report.
- `data/evaluation/rag_e2e_summary.md`: generated human-readable runtime summary.

## Dataset Contract

Each case may contain retrieval-only fields and/or end-to-end fields. Existing
retrieval cases continue to work.

```json
{
  "id": "leave_late_policy",
  "category": "fact",
  "question": "nếu tôi đi muộn có sao không",
  "history": [],
  "document_scope": "all",
  "document_ids": [],
  "expected_capability": "rag",
  "expected_intent": "ask_information",
  "expected_outcome": "answered",
  "expected_documents": ["noi-quy-va-van-hoa"],
  "expected_sections": ["Điều 1", "Thời gian làm việc"],
  "required_fact_groups": [
    ["đi muộn", "đến muộn"],
    ["thông báo", "báo cho cấp trên"]
  ],
  "forbidden_fact_groups": [
    ["hàng hóa", "tài sản"]
  ],
  "citation_required": true,
  "notes": "Regression case: retrieval must not cite asset policy for lateness."
}
```

`required_fact_groups` and `forbidden_fact_groups` use normalized any-of matching
inside each group. This avoids brittle checks such as failing `8h00` vs `8:00`
while still catching unsupported claims.

## Pipeline Execution

The live runner must execute the same branch path as the API by calling the
production pipeline, not a separate simplified retriever. It must collect the
final answer from the stream/final response and attach a typed evaluation trace.

The evaluator must not parse application logs to understand what happened. If
the current trace is not enough, add an internal evaluation observer or trace
collector that records stage outputs without exposing raw document contents
beyond what is already returned as citations.

## Metrics

Router metrics:

- route accuracy
- capability confusion matrix
- RAG false positive rate
- RAG false negative rate
- Qwen structured-classifier fallback rate

Retrieval metrics:

- Hit@K
- Recall@K
- MRR
- expected document hit
- expected section hit
- rewrite rate
- rewrite success/failure rate

Evidence metrics:

- context recall
- precision proxy based on forbidden document/section/fact matches
- zero-context-after-retrieval count
- evidence loss count, where retrieval found the right source but selection
  dropped it

Generation and response metrics:

- expected outcome accuracy
- required fact recall
- forbidden fact violation count
- citation validity
- citation coverage for cited claims
- Vietnamese compliance
- parse error count
- literal validation error count
- false refusal count
- false answer count

Performance metrics:

- router latency
- retrieval latency
- rewrite latency
- LLM generation latency
- total latency
- average, p50, p95, and max latency
- Qwen calls per case

## Failure Classification

Each failed case must include:

- `first_failure_stage`: `router`, `retrieval`, `evidence`, `generation`,
  `validation`, or `none`
- `failure_reasons`: stable reason codes
- enough trace metadata to debug without reading raw server logs

Classification rules:

- If expected capability is RAG but actual capability is not RAG, the first
  failure stage is `router`.
- If routing is correct but expected document/section is absent from top-K
  candidates, the first failure stage is `retrieval`.
- If retrieval found the expected evidence but selected context omitted it, the
  first failure stage is `evidence`.
- If selected context contains the expected evidence but the final answer has the
  wrong outcome, missing required facts, forbidden facts, invalid citations, or
  wrong language, the first failure stage is `generation` or `validation`
  depending on the violated check.

## Initial Coverage

The first dataset should cover at least these categories:

- exact policy facts
- paraphrase in natural Vietnamese
- typo and no-diacritics queries
- broad section queries
- multi-step procedure queries
- follow-up questions with history
- selected-document scope
- internal but unanswerable questions
- clearly out-of-scope questions
- social/conversation messages
- ambiguous questions that should clarify
- previous regressions: GitHub query, current-time query, lateness policy, room
  count, leave/quit ambiguity, Vietnamese language guard

The dataset must not become a list of production keyword rules. Cases are tests
of behavior, not routing logic.

## Quality Gates

Initial gates for live evaluation:

- router accuracy at least 95 percent
- retrieval Recall@5 at least 90 percent on answerable RAG cases
- evidence context recall at least 90 percent
- expected outcome accuracy at least 90 percent
- citation validity 100 percent
- Vietnamese compliance 100 percent
- false answers on unanswerable or out-of-scope cases: 0

Latency is reported in the first phase but does not fail the gate until a GX10
baseline is recorded and agreed.

## Error Handling

- Missing live dependencies must produce a clear evaluation error, not a fake pass.
- Malformed dataset entries must fail fast with case IDs and schema errors.
- Missing optional expectations should skip only the metric that depends on them.
- If the production pipeline returns a dependency error, the report records the
  case as failed with `dependency_error`.
- Generated reports may overwrite prior generated reports, but versioned case
  files must not be modified by live evaluation.

## Boundaries

Always:

- Preserve existing retrieval-only evaluation.
- Use `uv` for commands.
- Keep generated reports out of Git.
- Use deterministic metric logic for unit tests.
- Use production pipeline code for live end-to-end evaluation.

Ask first:

- Add external observability such as Langfuse.
- Add an LLM judge.
- Add dependencies or new model-serving components.
- Delete or replace the existing retrieval evaluator.

Never:

- Commit `.env`, uploaded documents, processed chunks, extracted images, vector
  data, or generated runtime reports.
- Hard-code seed documents or one-off query strings in production routing logic.
- Treat an LLM-generated judgment as the only correctness signal.
- Lower gates silently just to make a run pass.

## Success Criteria

- A developer can run retrieval-only evaluation as before.
- A developer can run live end-to-end RAG evaluation with one `uv run` command.
- Reports show aggregate metrics and per-case failures.
- A failed case identifies the likely first bad stage.
- Unit tests cover schema loading, normalization, metric calculation, and failure
  classification.
- Existing unit tests, Ruff, and harness check pass.
- `app/rag/PROGRESS.md` records the new evaluation capability and any known
  limitations.

## Open Questions

None blocking. Dataset expansion depends on the actual indexed company documents,
so the first implementation may upgrade existing checked-in cases and add only
source-reviewed cases that can be verified from available processed document
content.
