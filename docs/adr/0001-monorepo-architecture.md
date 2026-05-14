# ADR 0001 — Monorepo architecture

- **Status**: Accepted
- **Date**: 2026-05
- **Deciders**: CDO Platform Working Group

## Context

Pipelines, models, and analyses are spread across many separate
repositories. Engineers spend hours finding existing code. Auditors take
days to answer questions that should take minutes.

## Decision

Consolidate every data pipeline into a single monorepo with:
- One folder per project under `apps/`.
- Shared code under `libs/`.
- Infrastructure under `infra/`.
- Standard `AGENTS.md` rulebooks at root + per-folder for AI agents.

## Consequences

- Cross-team visibility improves; duplicated code becomes visible.
- Onboarding drops from weeks to days.
- CI fan-out via affected-only paths keeps build times bounded.
- AI agents can suggest code that fits our standards because the
  rulebook lives next to the code.
