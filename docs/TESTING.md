# Testing Strategy

## Automated layers

1. Unit tests: timestamp parsing, source normalization, validation, time folds, metrics, and feature availability.
2. Contract tests: representative Taipei, New Taipei, and weather payloads.
3. Pipeline tests: raw fixture to normalized Parquet to labelled features.
4. API tests: health, query validation, upstream failure mapping, model-not-ready behaviour.
5. Frontend checks: TypeScript build, loading, failure, filtering, selection, desktop and mobile layout.
6. Deployment smoke tests: public health URL, live station count, freshness, CORS, and model version.

The synthetic end-to-end test trains every candidate, applies all chronological gates, writes the selected model, evaluation, and driver artifacts, serves bounded forecasts, and executes a weather what-if. Synthetic data validates plumbing only; it is never presented as real model performance.

## Required commands

```bash
pytest
ruff check src tests
cd frontend && npm run build
cd infra/cloudflare-collector && npm run typecheck
```

Release checks also run `npm run lint`, `npm audit`, `git diff --check`, and a backend Docker build when Docker is available.

## ML-specific tests

- No training timestamp may occur after its fold's train cutoff.
- Validation timestamps must begin after the 60-minute purge gap.
- The final 24 hours must not appear in model selection.
- Each target must match the same station within the 53-to-67-minute window.
- Weather issue time must be no later than observation time.
- Predictions must be finite and within station bounds after clipping.
- The saved feature order must match inference feature order.

