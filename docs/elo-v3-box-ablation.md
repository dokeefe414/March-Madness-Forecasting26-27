# Historical box-score ablations for Elo 3.0

## Goal

Test whether historical **observed basketball box-score data**, not just historical final scores, improves the predictive probabilities used by Elo 3.0. This test is research only; its output is separately published in Model Lab, not substituted into archived first-pick predictions or the deployed game forecasting engine.

## Independent historical source

- **Score-only baseline:** the original pinned Kaggle men's compact regular-season results used by the repository and Elo 2.0/Elo 3.0 historical benchmarking.
- **Detailed box source:** a separately pinned copy of the Kaggle March Machine Learning Mania 2026 `MRegularSeasonDetailedResults.csv`, at `ryanbiancavilla/march-ml-mania-2026`, Git commit `e0c70940b0e807df89380740b3a6e0e18d76d01a`, path `data/MRegularSeasonDetailedResults.csv`, Git blob SHA-1 `c2e4a7a5355120373d92a84250fc0f1eda044842`.
- The downloader explicitly checks the byte-for-byte Git blob digest before using the data. The final artifact includes **SHA-256 of both downloaded sources**.
- Historical Kaggle numeric team IDs are stable across these two source families. No team name joins are performed. Every detailed game must exactly match the separately pinned compact record in **season, date/day, winner ID, loser ID, winning score, losing score, and winner location**.
- Duplicate identities and contradictory source outcomes are withheld. Coverage is reported by season. A held-out season must have **at least 90% source-box coverage** to enter the benchmark; otherwise it is excluded with a reason.

**Source trust:** both are republished Kaggle dataset mirrors, not individually inspected original NCAA play-by-play. A mirror label alone is not proof that every statistic is official or perfect. The test documents what is actually verifiable from the columns and cross-source records.

## Which statistics are actually available

The historical detailed columns contain two-sided measured **game-level box counts**:

| Family | Inputs | Interpretation |
|---|---|---|
| Shooting | FGM, FGA, FGM3, FGA3, FTM, FTA | Total FG%, eFG%, three-point accuracy, free-throw accuracy and attempt rates |
| Possession outcomes | TO, OR, DR | Turnovers, offensive rebounds, and defensive rebounding opportunities |
| Ball movement | Ast | Assists per made basket |
| Defensive pressure | Stl, Blk | Steals per estimated possession; blocks per opponent FGA |
| Physicality | PF | Fouls per estimated possession |
| Scores, venue | WScore, LScore, WLoc | Validated exact final scores and baseline Elo venue context |

**Possessions are not a recorded column** in these Kaggle detailed game results. For this experiment, estimated possessions are derived solely from observed counts:

```
teamPossEst = FGA - ORB + TO + 0.475 × FTA
gamePossEst = (winnerPossEst + loserPossEst) / 2
offPer100Est = pointsFor / gamePossEst × 100
defPer100Est = pointsAgainst / gamePossEst × 100
```

Estimated possessions are bounded and rejected if inconsistent. Using the same symmetric estimate for both sides prevents claiming an unattested offensive/defensive possession difference. This is a heuristic efficiency estimator, **not a verified observed possession count**. The current 2027 NCAA-derived `o_poss/d_poss` fields remain a separate source.

## Exact ablation design

The models share the same source-matched games, date-frozen predictions, stable Kaggle prior-year team IDs, Elo update rules and fixed hyperparameters. Four variants are replayed independently:

1. `scoreOnly`: Elo 3.0 from the score-only historical inputs, opponent strength, recent form and strictly earlier-year priors.
2. `efficiency`: score-only + estimated offensive and defensive efficiency from **earlier completed** detailed boxes.
3. `fourFactors`: efficiency + source-observed effective FG%, turnover rate, offensive rebounding%, and FTA/FGA.
4. `extended`: Four Factors + small bounded additional effects from previous assists, steals, blocks, personal fouls, 3PT accuracy, and FT accuracy.

For fairness, all metrics are computed only on games where **both teams** had at least three prior-date paired observed box scores. All variants are evaluated on the **identical contest IDs and outcomes**, including the score-only control. A game's box statistics enter the history **after** that entire calendar day's probabilities have been frozen.

The extended features are experimental, heavily shrunk and potentially redundant with scoring/efficiency. They are included to measure incremental evidence, not because more features automatically improve predictions.

### Reported outcomes

The report gives pooled and per-season Brier score, log loss, winner accuracy, expected calibration error and a deterministic season-block 95% bootstrap interval for differences in Brier. **Positive Brier gain** means adding the observed box-stat family lowered average squared probability error compared to score-only Elo 3.0. Small or negative gains must be shown rather than hidden. Testing hypotheses on fixed prior holdouts introduces selection risk; one cannot claim an untouched holdout after observing these years.

## Verified first historical run (November 25, 2026)

The pinned detailed source passed byte-level Git blob validation, then
matched **52,763 of 53,010** independently pinned compact-score games.
Another **247** detailed records were excluded for invalid box measurements.
No box record or possession count was invented.

- Detailed-source SHA-256: `d9e8fc8a22ea3ac74baf246af9ad49012fb55746c88ca34d1be483f43f7d71e3`
- Compact-source SHA-256: `79b15ea3016c7887f1031c31a47b68494d5c08d4ba745ad1954a7af0ca3542b4`
- Complete test years: 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025.
- Date-frozen **38,942 identical eligible game predictions**.

| Ablation | Brier ↓ | Log loss ↓ | Winner accuracy ↑ | ECE ↓ |
|---|---:|---:|---:|---:|
| Score-only Elo 3.0 | 0.193204 | 0.568352 | 70.1582% | 0.024139 |
| + Estimated-possession efficiency | 0.190746 | 0.562103 | 70.5716% | 0.019478 |
| + Observed Four Factors | 0.190645 | 0.561841 | 70.5845% | 0.019484 |
| + Supplementary box counts | **0.190582** | **0.561680** | **70.5999%** | 0.019492 |

The incremental Four Factors gain after efficiency is only about
**+0.000101** Brier. Supplementary assists, steals, blocks, fouls, and extra
shooting add just **+0.000063** beyond Four Factors. Adding all observed
box-count groups improved Brier by **+0.002622** over score-only.

All eight eligible seasons showed positive incremental improvements in the
initial run. The next CI report includes explicit season-block bootstrap
intervals **for each incremental ablation**, not merely for the combined
model. These are still retrospective, previously observed holdout years, not
an untouched prospective trial; do not auto-promote them to 2027 forecasts.

## Reproduction

```bash
PYTHONPATH=research python -m unittest research.tests.test_elo_v3_box_historical -v
PYTHONPATH=research python -m forecast.elo_v3_box_historical --out research/outputs/elo3-historical-box-ablation.json
```

For offline repeatability pass `--compact-csv /path/to/MRegularSeasonCompactResults.csv --raw-csv /path/to/MRegularSeasonDetailedResults.csv`. In offline mode the source is labeled a local file and byte verification against the published blob pin is not claimed; exact contest/score joins still apply.

CI runs the full unit suite and generates the source-linked report as a retained artifact. The Pages workflow publishes `web/public/research/elo-v3-historical-box.json`, and Model Lab displays the comparison.

## Non-promotional policy

Even if Four Factors improve retrospective Brier score, **do not promote them to the active forecast automatically**. The current 2027 NCAA-derived box provider often omits complete historical shooting and rebounding columns. The historical feature ablation cannot silently invent their 2027 values or prove a direct, prospective improvement for this season.

Before promotion, require an independent, source-complete 2027 feature-availability audit, frozen real pretipoff candidate forecasts, improved first-pick scores, calibration checks, and uncertainty analysis on unseen dates. Published archives never change with a new model version.
