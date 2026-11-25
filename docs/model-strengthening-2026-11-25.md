# Model strengthening: verified implementation and remaining work

Updated November 25, 2026.

## What is already implemented

The repository contains current-season source-aware margin/venue Elo, an
experimental historical-carryover Elo 2.0, state-space and adaptive state-space
research, logistic and boosted historical challengers, optional source-pinned
historical box-score features, a forward shadow ensemble, out-of-season
historical evaluation, and first-published forward accuracy monitoring.

**None of these automatically becomes the production winner predictor.**
Historical tournament-day features are not equivalent to pretipoff regular-season
features. A box-score source URL alone does not prove a verified NCAA identity.

## New: independent readiness audit

Run from the repository root:

```bash
python -m research.forecast.model_readiness --ledger web/public/forecasts --out web/public/current/model-readiness.json
python -m unittest research.tests.test_model_readiness
```

The read-only audit uses the existing immutable-first-pick accuracy report. It
checks 150 paired settled games, 20 independent dates, a 0.002 Brier improvement,
and a positive lower 95% date-block interval. It separately reports baseline
reliability with a 100-game minimum and 0.06 descriptive ECE threshold.

**Promotion remains blocked even if all these pass** because independently
measured *candidate-specific* forward calibration, verified matchup coverage,
historical season robustness, and a manual model review are still necessary.
The audit does not manufacture candidate calibration from the baseline.

## Six-stage strengthening plan and acceptance criteria

1. **Historical identities:** source-pin a complete team-ID crosswalk per
   season, audit missing/conflicting mappings, and reject ambiguous matches.
   No cross-season inference from a similar school name. Verify a complete
   historical score and box-score manifest before using efficiency features.
2. **Pregame offensive/defensive efficiency:** build a possession-normalized
   offense/defense store from independently verified game boxes, with one
   immutable previous-date cutoff per fixture. Compare against Elo on identical
   coverage and dates; abstain rather than invent possessions.
3. **Dynamic state-space:** fit independent offense/defense latent strengths,
   shrink uncertainty for low-sample teams, and tune process/observation
   noise using earlier seasons only. Compare fixed and adaptive variants on
   future held-out seasons.
4. **Calibration and tuning:** nested expanding-season validation, regularized
   logistic and boosted candidates, and calibration trained strictly before
   each test season. Report Brier, log loss, ECE, uncertainty and sample counts.
5. **Ensemble:** fit convex nonnegative weights from earlier first-pick
   component forecasts, then freeze before later-date evaluation. Keep a
   paired Elo comparison and publish abstentions/coverage, not just accuracy.
6. **Forward dashboard and promotion:** show first-pick paired samples,
   per-model reliability, game-date confidence intervals, source coverage,
   season/regime slices, and explicit review blockers. Never rewrite picks.

## Integrity rules

- No future-day or same-day final enters a pregame prediction.
- All component and ensemble forecasts must be frozen before tipoff.
- The original earliest prediction, settlement and source receipts remain immutable.
- Source identities and possession counts must be verified; no guessed data.
- Improvement is not claimed until a held-out and forward comparison supports it.
- No auto-promotion from retrospective research or a small positive result.

## Current boundary

This change **implements the readiness audit and regression tests**, not the
entire six-stage data-engineering and modeling program above. The existing
research modules provide much of the foundation, but a new verified historical
box-score corpus and candidate-specific forward calibration are not yet supplied.
The production Elo is intentionally unchanged.
