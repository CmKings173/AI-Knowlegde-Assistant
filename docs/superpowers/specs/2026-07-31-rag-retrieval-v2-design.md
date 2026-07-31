# RAG Retrieval V2 Design

Date: 2026-07-31

## Status

Approved in discussion. This document is the implementation source of truth and
must be reviewed before code changes begin.

## Problem

The current RAG path can retrieve a correct chunk but also place unrelated chunks
into the final context. It then accepts a generated answer when citation IDs are
syntactically valid even if the cited source does not support the claim.

The observed regression has these systemic causes:

- RRF rank-fusion scores are treated like relevance confidence.
- The final context is selected by taking a fixed number of top-ranked chunks.
- Raw dense and lexical evidence is not retained for final selection.
- Query routing and evidence gating depend on growing keyword lists.
- Metadata supplied by ingestion may be incorrect and is unsafe as an inferred
  hard filter.
- Citation validation checks source IDs, not whether the selected context is
  coherent enough to ground an answer.
- Existing tests rely heavily on fake retrieval results and do not prove
  end-to-end retrieval and answer behavior over real indexed documents.

Commit `4721cf0` is the confirmed stable baseline. Commit `4ac2f57` and its local
follow-up experiments are preserved but are not the base for V2.

## Goals

- Restore a stable serving baseline without rewriting Git history.
- Improve retrieval and final-context precision for unseen Vietnamese phrasing.
- Use one conversational LLM model: Qwen through Ollama.
- Keep the normal path to one Qwen generation call.
- Allow one adaptive rewrite call with the same Qwen only when initial retrieval
  is demonstrably weak or incoherent.
- Keep dense embeddings, BM25 and Qdrant.
- Return partial answers when only part of a question is supported.
- Keep failure states distinguishable and observable.
- Prove improvement with a tracked, end-to-end evaluation dataset.

## Non-goals

- No dedicated planner model.
- No reranker model or Infinity dependency in V2.
- No LLM verifier model.
- No Redis or new database dependency.
- No domain-specific keyword patch for individual reported questions.
- No attempt to guarantee correct answers for every possible input.
- No CI/CD work in this scope.

## Git recovery

The current experimental state is preserved at:

```text
archive-rag-experiments-e931279
```

The remote regression is reverted without force-pushing:

```text
origin/main: 4ac2f57
└── hotfix-restore-rag-baseline
    └── 42433c7 Revert "Harden RAG evidence gating and add optional reranker"
```

V2 is developed from the restored tree on:

```text
feature-rag-retrieval-v2
```

The hotfix and feature branches must be reviewed and tested independently before
merge. Future fixes and features must not be committed directly to `main`.

## Architecture

```text
User query + bounded conversation history + explicit document scope
→ Normalize
→ Apply hard access/document/version filters
→ Initial dense search + BM25 search
→ RRF candidate fusion
→ Candidate quality assessment
   ├── coherent evidence: continue
   └── weak or cross-domain evidence:
       → Qwen structured query rewrite
       → one second retrieval pass
→ Evidence/context selection
→ Qwen grounded answer generation
→ Deterministic response and citation validation
→ API response with citations and related images
```

### Model contract

Qwen is the only conversational LLM. Embedding remains a separate embedding
provider because vector retrieval requires it, but it is not a chat/planning
model.

The normal answer path invokes Qwen once. An adaptive path may invoke the same
Qwen once to produce a short structured rewrite and once to generate the answer.
Rewrite failure falls back to the original retrieval result.

## Routing

Deterministic routing is limited to safe fast paths:

- empty input;
- clear greeting;
- explicit continuation;
- `document_scope="selected"` with no selected documents.

Other inputs should attempt retrieval before being classified as unavailable or
out of scope. Retrieval must not depend on an ever-growing list of HR, IT or
policy phrases.

Conversation history may resolve a follow-up subject, but it is never evidence.
Only retrieved document context can support business facts.

## Retrieval

### Candidate generation

For each retrieval pass:

1. Apply hard filters.
2. Embed the search query.
3. Run Qdrant dense search.
4. Run BM25 lexical search.
5. Fuse the ranked candidate IDs with RRF.

RRF is only a candidate-fusion mechanism. It must not be interpreted as semantic
confidence.

Each candidate must retain retrieval provenance:

```json
{
  "dense_score": 0.82,
  "dense_rank": 1,
  "bm25_score": 4.12,
  "bm25_rank": 3,
  "rrf_score": 0.031,
  "matched_queries": ["original"],
  "document_id": "doc-id",
  "domain": "HR_POLICY",
  "section": "section path"
}
```

Missing dense or lexical participation is represented explicitly rather than
inventing a score.

### Hard and soft metadata

Hard filters are limited to:

- document IDs explicitly selected by the user;
- authorization/access scope;
- published/current document version;
- document readiness.

Inferred domain and knowledge type are ranking signals only. They must not remove
global candidates because ingestion metadata can be wrong.

### Candidate quality assessment

Quality is evaluated using calibrated retrieval signals, not a single arbitrary
RRF threshold:

- raw dense similarity;
- normalized lexical evidence;
- agreement between dense and lexical retrieval;
- score separation;
- concentration versus dispersion across document/domain;
- duplicate-content ratio.

Thresholds must be calibrated against the tracked evaluation dataset. Low-quality
or incoherent results trigger adaptive rewrite; they do not immediately trigger a
false `insufficient_context` response.

### Adaptive rewrite

When initial retrieval is weak or incoherent, Qwen receives only:

- the current user query;
- bounded history when the query is a follow-up;
- a strict JSON rewrite schema.

It must not answer the question or invent facts. The original query is always
retained, and the rewrite adds at most two short search queries. A second
retrieval pass fuses original and rewritten-query candidates.

## Evidence selection

The final context must not be `retrieval.chunks[:N]`.

The selector must:

- reject candidates below calibrated evidence quality;
- avoid unrelated cross-domain chunks when coherent evidence exists;
- deduplicate substantially overlapping content;
- prefer coverage of distinct relevant sections;
- preserve explicit document scope;
- use same-document structure only when it improves evidence coverage;
- order the strongest evidence early and avoid burying critical evidence;
- enforce the token budget after evidence selection.

The selector may return fewer than `FINAL_CONTEXT_TOP_N` chunks. A fixed number
is a maximum, not a target.

## Generation

Qwen receives:

1. system prompt;
2. bounded, source-labelled context;
3. the user query;
4. bounded history only when needed for follow-up resolution.

Generation rules:

- use only context as business evidence;
- cite every important business claim;
- do not infer a specific penalty, policy, IP, port, credential or step that is
  not present;
- return `partial` when evidence supports only part of the request;
- return `insufficient_context` only when core evidence is absent;
- return concise Vietnamese with correct diacritics.

One retry is allowed only for malformed structured output or disallowed language.

## Validation and statuses

The heuristic fact guard remains disabled and is not reintroduced in V2.

Deterministic validation covers:

- valid JSON response schema;
- allowed status;
- known `SOURCE_n` identifiers;
- exact agreement between inline citations and returned source IDs;
- critical literal values such as times, IPs and ports appearing in cited
  evidence.

It must not pretend to perform general semantic entailment.

Statuses remain distinct:

- `answered`: core requested information is supported;
- `partial`: only some requested information is supported;
- `insufficient_context`: retrieval has no usable core evidence;
- `conflict`: retrieved sources disagree;
- `generation_failed`: Qwen output remains unusable after the allowed retry;
- dependency failure/degradation is reported separately and must not masquerade
  as missing documentation.

## Error handling

- Rewrite timeout or invalid rewrite: use original candidates.
- Qdrant unavailable: return a dependency error; do not ask Qwen to answer from
  memory.
- BM25 unavailable: dense-only degradation may continue with explicit logging.
- Qwen timeout/failure: return `generation_failed`.
- No usable candidate: return the standard gentle insufficient-context response.
- Optional future dependencies must be fail-open or remain disabled.

## Observability

Each request trace must make the failing stage identifiable:

- route and fast-path reason;
- original and rewritten search queries;
- dense/BM25 ranks and scores;
- RRF score and retrieval provenance;
- quality-assessment decision and reasons;
- selected versus rejected chunk IDs with reasons;
- context token count;
- generation attempts and latency;
- final status and citation IDs.

Logs must not contain secrets or full sensitive document content.

## Evaluation

The evaluation dataset must be versioned in the repository rather than stored
only under ignored runtime `data/`.

It must cover:

- exact factual questions;
- paraphrases and colloquial Vietnamese;
- light spelling mistakes;
- consequence questions;
- procedural questions;
- broad/list questions;
- multi-part questions;
- history-dependent follow-ups;
- partially answerable questions;
- unanswerable internal questions;
- clearly out-of-scope conversation;
- cross-domain distractors;
- selected-document filtering;
- newly ingested documents.

Representative regression cases are examples of categories, not keyword rules.
At least one holdout set must remain unused while tuning thresholds.

Required reports:

- Recall@K and MRR;
- expected-section hit rate;
- final-context precision;
- wrong-domain context rate;
- citation-section correctness;
- answer/refusal/partial outcome accuracy;
- critical unsupported-fact count;
- normal-path and adaptive-path latency percentiles.

Initial merge gates:

- answerable retrieval Recall@5 is at least 90% and does not regress from
  `4721cf0`;
- citation-section correctness is at least 95% on the reviewed evaluation set;
- no unsupported critical literal is accepted;
- wrong-domain chunks are excluded from final context when coherent in-domain
  evidence is available;
- V2 does not increase normal-path P95 latency by more than 20% over the measured
  baseline;
- unit, integration, ingestion and frontend checks pass.

If a numerical gate is not achievable with the current corpus/model, the result
must be reported and the design revisited rather than weakening the gate silently.

## Implementation slices

1. Preserve and verify the stable baseline.
2. Add tracked evaluation cases and baseline measurement.
3. Retain raw retrieval provenance through fusion.
4. Add candidate quality assessment and evidence selection.
5. Change ambiguous/domain routing to retrieval-first.
6. Add adaptive rewrite with the same Qwen.
7. Separate failure statuses and harden deterministic validation.
8. Run focused tests, full tests, evaluation and manual smoke checks.
9. Perform code review and push only the reviewed feature branch.

Each slice must start with a failing test or evaluation case and land as a
coherent commit.

## Risks and controls

- **Adaptive path latency:** only trigger it for calibrated weak retrieval and
  measure normal/adaptive paths separately.
- **Rewrite hallucination:** strict schema, no factual output, retain original
  query, at most two rewrites and safe fallback.
- **Metadata false negatives:** inferred metadata is never a hard filter.
- **Over-filtered context:** calibrate on holdout data and preserve strongest
  original evidence.
- **Qwen still infers unsupported semantics:** use clean context, strict prompt,
  literal checks, citation review metrics and partial answers; do not claim full
  semantic verification.
- **Evaluation overfitting:** use category coverage plus a holdout set.
- **Operational regression:** keep baseline and V2 branches independently
  deployable until V2 passes all gates.

## Definition of done

- Stable baseline is recoverable and the experimental history remains preserved.
- V2 is implemented on its feature branch without a dedicated reranker/planner
  model.
- Normal queries use one Qwen generation call.
- Weak retrieval can use an adaptive rewrite with the same Qwen.
- Final context is selected by evidence quality rather than fixed top-N slicing.
- Failure statuses identify retrieval, dependency and generation failures
  correctly.
- Evaluation and full repository checks pass the documented gates.
- Original reported regressions and unseen holdout categories are verified
  end-to-end.
- The reviewed feature branch is ready for merge without force-pushing `main`.
