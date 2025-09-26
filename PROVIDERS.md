# Providers

## Current
- API Football (fixtures, odds - partial scope)

## Abstraction Goals
- Unified interface: `fetch_fixtures(date_range)` → List[FixtureRecord]
- Normalization layer (naming, timestamps, odds formats)
- Retry & rate limiting strategy
- Error classification:
  - transient (retry)
  - fatal (raise & log)

## Planned Extensions
- Additional football APIs
- Telegram-derived pseudo-provider (signals)
- Synthetic provider for tests / replay

## Open Questions
- Timezone normalization (store all UTC)
- Odds source trust levels
- Incremental vs full refresh
