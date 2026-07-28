# ADR-001: Use the repository as the agent harness system of record

## Status

Accepted

## Date

2026-07-28

## Context

This project is developed with long-running AI-agent assistance. Chat history,
local memory, and human recollection are not durable sources of truth for future
agent sessions. Future agents need a fast way to answer: what the system is, how it
is organized, how it runs, how it is verified, and what the current state is.

## Decision

Use the repository itself as the system of record for agent work:

- Root `AGENTS.md` is the landing page for every new agent session.
- Root `CONSTRAINTS.md` records hard project constraints.
- Root `PROGRESS.md` records durable current state and known limitations.
- Module-level `ARCHITECTURE.md` files live beside important code.
- `scripts/check_harness.py` and unit tests verify the harness exists.
- Makefile exposes standardized `harness-check` and `check` targets.

## Alternatives considered

### Keep knowledge in chat history

- Pros: No extra files.
- Cons: Not durable across fresh sessions; future agents cannot reliably see it.
- Rejected because it fails the fresh-session test.

### Put everything in one large guide

- Pros: One file to open.
- Cons: High discovery cost, easy to become stale, poor locality near code.
- Rejected in favor of a small landing page plus local module docs.

## Consequences

- Agents must update repo docs when durable state or constraints change.
- Harness documentation becomes part of the verification surface.
- The repo becomes easier for both humans and agents to resume safely.
