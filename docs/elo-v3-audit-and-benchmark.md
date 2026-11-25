# Elo 3.0 power ranking audit and matched Elo 2.0 holdouts

## Research question

Do shrinkage, source-verified box statistics, earlier-date opponent quality, and one-to-three-year team priors produce **more accurate date-frozen probabilities** than Elo 2.0, without artificially promoting a short undefeated schedule to #1?

The Teams tab remains **research rankings**, not the published game-pick engine. Re-run after each successful Pages rebuild. The actual Oregon State rank must be read from the generated artifact; no manual rating overrides, fabricated outlier ranking or authoritative prior-year team match has been added.

## Live 2027 features and ranking definition

For a team at date T, Elo 3.0 constructs the same strength used for the displayed power ranking and for its previous-date matchup probabilities:

- **Elo:** game outcome with bounded score-margin adjustment, adaptive home advantage and 24-point update scale. Within-date probabilities *and* update sizes are frozen.
- **Reliability:** prior + `(0.65 + 0.35*n/(n+8)) * (Elo-prior)`. Early-season jumps away from the prior are damped, then gradually released.
- **SOS:** `clip(0.20 * sum(opponent **pregame** Elo − 1500)/(games+8), ±24)`. Every accepted game can contribute, even if no box file exists. It never uses the opponent's end-season rating.
- **Recent form:** exponentially decayed surprise in earlier result updates, capped ±20, then shrunken by `n/(n+12)`.
- **Efficiency:** for three or more verified paired team game boxes, a capped ±24 score from opponent-aware *observed* offensive–defensive efficiency with an extra 500-possession denominator to limit noise.
- **Four Factors:** observed effective field goal rate, turnovers per verified possessions, offensive rebound share using the opponent's defensive rebounds, free-throw attempts per field goal attempt. Minimum three independently paired boxes; a fixed neutral reference and eight-game shrinkage; capped ±12. No fabricated steals, blocks or advanced possession data.

**Power rating** = reliable Elo + SOS + form + verified efficiency + verified Four Factors. The generator saves each part in `current/elo-v3-teams.json` under `teams[].components`, along with `underlyingElo`, `games`, `boxGames`, and `fourFactorGames`. `top25OutlierAudit` flags unusually few games or weak previous opponents in the first 25 ranks so an Oregon State-style anomaly can be investigated. The audit flags fewer than ten games as an early-season limited sample,
and separately surfaces verified Division I status, as-of source-adjusted
net efficiency, and recorded opponent pregame Elo for transparent comparison
with the Elo 3.0 decomposition. A flag does not automatically change a rating.
In the November 25 source snapshot, the provider had 1,331 complete paired
possession boxes but **zero** complete verified Four Factor boxes, so all
Four Factor contributions were zero rather than imputed.

These are fixed research coefficients; overusing correlated data can degrade real forecasts. Claims of precision from missing boxes or unverified player stats are forbidden.

## Previous seasons and identity safety

For **historical** 2016–2025 holdout years, use the pinned Kaggle men's regular-season compact game IDs, which persist between those files. One-year priors and the alternate three-year Elo 3.0 priors come only from complete seasons **strictly before** the test year, computed as regressions of historical final Elo toward 1500. Three-year weights are 0.65, 0.25, 0.10 for years T−1, T−2, T−3. Each historical year is processed as a separate replay.

For **current 2027**, historical Kaggle IDs and source-local NCAA names/hashes **are not linked by any verified cross-provider longitudinal identity**. The incomplete 2026 historical JSON is also missing the end of the season. Therefore Elo 3.0 live rankings currently use honest **neutral 1500 previous-season priors**, not a possibly wrong team history. Prior seasons inform the benchmark, not a false live-season carryover. A future source-proven 2026/2027 ESPN-stable-ID bridge with complete 2026 results should be added before changing this policy.

## Reproducible Elo 2.0 versus Elo 3.0 benchmark

The Pages workflow runs:

```bash
PYTHONPATH=research python -m forecast.elo_v3 --out web/public/research/elo-v3-historical.json
PYTHONPATH=research python -m unittest research.tests.test_elo_v3 research.tests.test_elo_v3_current
```

The report includes ten fixed held-out seasons (2016–2025) if the pinned source contains full regular seasons, per-season results, and same-cohort:

- **Elo 2.0:** prior-year 55%-regressed rating with previous-opponent SOS, fixed home term, date-frozen probability
- **Elo 3.0 / one year:** exactly the same prior-year ratings as Elo 2.0, isolating different scoring and adjustment methods
- **Elo 3.0 / three years:** same Elo 3.0 calculation but with predeclared three-year priors; isolates the additional history

Measure Brier score, log loss, accuracy, ECE/calibration bins, early season through day 45, per-year positive gains and a seeded 600-resample **season-block bootstrap** CI. All models must share immutable game IDs, dates, outcomes, and timing. A positive Brier gain means Elo 3.0 has lower loss. The uncertainty interval and each year's results must be checked before claiming improvement. The source SHA256 is written to the report; if retrieval is unavailable the report says `unavailable` rather than inserting imagined results.

The historical compact results source has **no paired box scores**. As a result this historical benchmark measures Elo 3.0's score-only + schedule + history configuration, *not* its live verified efficiency/Four Factors contribution. A future independent possession-rich historical corpus would be needed to test that part. No trained player/roster or AP-poll features are added without a validated source.

## Verified pinned-data results (CI, November 25, 2026)

The end-to-end historical benchmark ran against pinned raw-data SHA256
`79b15ea3016c7887f1031c31a47b68494d5c08d4ba745ad1954a7af0ca3542b4`.

**Eight** of the ten predeclared holdout years had the required complete
regular-season coverage: 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025.
The 2020 and 2021 source seasons did not meet the minimum regular-season-day
gate and were omitted instead of treated as complete. There were **43,827
identical scored-game predictions** in each model's paired cohort.

| Retrospective measure | Elo 2.0 | Elo 3.0 (1-year) | Elo 3.0 (3-year) |
| --- | ---: | ---: | ---: |
| Brier (lower better) | 0.192457 | 0.191266 | 0.191155 |
| Log loss (lower better) | 0.569204 | 0.564503 | 0.564406 |
| Accuracy (higher better) | 71.6122% | 70.9209% | 70.8981% |
| 10-bin ECE (lower better) | 0.068243 | 0.031350 | 0.032841 |

The paired Brier improvement was **+0.001191** for one-year Elo 3.0
(season-block descriptive 95% interval **[+0.000977, +0.001380]**)
and **+0.001302** for multi-year Elo 3.0
(**[+0.000970, +0.001603]**). All eight eligible seasons showed a positive
Brier gain; in the first 45 days, one-year Elo 3.0 Brier was 0.182921
versus Elo 2.0's 0.186561.

**Critical tradeoff:** winner classification accuracy was **lower** for both
Elo 3.0 variants even though probability calibration, Brier score and log
loss improved. This is not unqualified superiority, and season-block
intervals do not account for selection/tuning on these same historical
periods. Production publication and first-pick models remain unchanged.

## Current-season paired score-and-box shadow test

The Elo 3.0 team artifact also reports `currentRetrospective`, a match of
Elo 2.0 against Elo 3.0 on **the identical currently accepted 2027 games**.
Both begin at 1500 because the historical Kaggle-to-NCAA team mapping is not
authoritative. Elo 3.0 includes verified prior-date paired box efficiency
and Four Factors where sample eligibility permits. The report discloses
the count of games with enough earlier paired boxes and separately scores
that eligible subset. These are reconstructed prior-date predictions,
not archived first-published pretipoff forecasts, and are research only.

## CI / deployment gates

- Tests: date embargo and same-day freeze, paired box identities, previous-year-only priors, schedule effect, small-sample shrinkage, identical Elo 2/3 game cohort, end-of-season component contract.
- Workflow generates the historical comparison in `web/public/research/elo-v3-historical.json` and then source-consistent team rankings.
- The **original** live upcoming probabilities, settled archives and bracket predictions are not silently switched; retrospective improvement is not equivalent to first-published predictive skill.
