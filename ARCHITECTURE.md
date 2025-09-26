# Architecture Overview

## Flow (Current Scope)
1. Fetch fixtures (scheduled GitHub Action)
2. Validate & persist (atomic write)
3. (Planned) Telegram parsing
4. (Planned) AI reasoning & prediction synthesis
5. (Planned) Consensus & scoring
6. (Planned) Frontend consumption & dashboards
7. (Planned) Post-match analytics

## Modules Roadmap
- core/: configuration, logging, persistence, models
- providers/: API adapters (future abstraction)
- telegram/: parsing & normalization (planned)
- ai/: feature engineering & reasoning (planned)
- consensus/: merging signals (planned)
- web/ or frontend/: UI delivery (planned)

## Data Contracts
- FixtureRecord (see models.py)

## Quality & CI
- Lint (Ruff)
- Typecheck (mypy strict gradually)
- Tests (+ coverage artifact)
- Scheduled data fetch
- Future: coverage badge + quality gates

## Future Enhancements
- Delta fixtures analytics
- Historical storage
- Prediction accuracy tracking
