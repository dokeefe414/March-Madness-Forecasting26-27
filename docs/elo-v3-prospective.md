# Prospective Elo 3.0 shadow validation

## Purpose and strict separation

Elo 3.0 now produces **actual pretipoff shadow probabilities** beside the existing active Elo forecast. A shadow probability is not a production prediction and cannot replace historical picks. The goal is to determine whether the historical Elo 3.0 gains transfer to **real first-published forecasts** with external final-score verification.

Before this integration, Elo 3.0's 2027 comparisons were reconstructed retrospectively from previously completed game results; those cannot be presented as real captured pregame predictions. The new records start **only when the scheduled archive next produces an eligible first-pick snapshot**. There is no retrospective backfill, even if the archive already contains predictions for the same future ESPN event.

## Recording pipeline and source provenance

`.github/workflows/archive-pregame.yml` already captures scheduled future ESPN fixtures several times per day. It now also generates the source-paired `current/2027-box-games.json` data from the **same** invocation that creates `2027-games.json` and `2027.json`. These are temporary same-run inputs. The public committed snapshot is the source of truth once archived; no external daily data file is assumed immutable.

For each scheduled event:

1. Verify its `STATUS_SCHEDULED`, ESPN event ID, unique home/away team identities, scheduled UTC time, and at least the existing **15-minute pretipoff buffer**.
2. Require source retrieval timestamps, season=2027, accepted NCAA scored-game count, team identities, latest game date, and paired-box event identities to match exactly.
3. Rebuild Elo 3.0 from games with a **game date strictly earlier** than the fixture's scheduled US/Eastern calendar date. Exclude even completed **same-day** games and box scores to eliminate same-day hindsight. The model reconstructs only earlier games and their source-paired box statistics.
4. Freeze Elo 3.0's opponent/schedule, form, efficiency, and Four Factors adjustment, dynamic home-court advantage and the calibration temperature trained on those **earlier dates only**. No unverified Kaggle historical-name carryover is assigned to 2027 schools.
5. Store `elo3HomeWinProbability` and `elo3Research` beside the **unchanged** `homeWinProbability` and same-snapshot `baselineHomeWinProbability`. Freeze provenance: `modelVersion: elo3-prospective-shadow-v1`, source timestamps, `trainedThroughDate`, exclusive date cutoff, matched box count, Four Factors count, previous-game count, temperature and box-status label.
6. Append the snapshot via exclusive file creation. A source or future-time violation fails closed instead of quietly substituting a made-up probability. When verified Four Factors are unavailable, the frozen metadata identifies the missing coverage; the model does not fabricate player or possession statistics.

Other named research variants remain separate. **The active forecast model is not switched, the live bracket is not changed, and immutable original picks remain unchanged.**

## Scoring and evidence gate

The existing verified settlement pipeline first requires **independent ESPN `STATUS_FINAL`** and matching NCAA scores and date. `forecast.accuracy_research` then:

- Chooses **exactly one earliest original source-timestamped snapshot for each ESPN event**.
- Only pairs a first-published Elo 3.0 probability with the **Elo baseline saved in the same snapshot**. Even if a subsequent snapshot for the same event adds Elo 3.0, it cannot be backfilled into the earliest first pick.
- Reports the number of new first-frozen Elo 3.0 forecasts, dates, verified settled outcomes and awaiting results. **Pending is not a loss**.
- Calculates paired Brier score, winner accuracy, and date-block bootstrap 95% Brier-gain uncertainty. All comparisons use identical game IDs and verified outcomes.
- Marks evidence as *review eligible* only after at least **100 paired verified games**, **12 independent result dates**, Brier improvement of at least **0.002**, and a positive lower bound on the date-block gain interval. This is a **review threshold**, not automatic model promotion.

The report lives at `web/public/current/accuracy-research.json`, with the new `prospectiveElo3` section. Model Lab displays a separate prospective evidence panel. With no first-published Elo 3.0 games, the correct state is **zero picks, no paired accuracy**.

## Verification and reproducible commands

```bash
PYTHONPATH=research python -m unittest research.tests.test_elo_v3_prospective -v
PYTHONPATH=research python -m unittest discover -s research/tests -v
PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
PYTHONPATH=research python -m forecast.accuracy_research --ledger web/public/forecasts --out /tmp/elo3-forward-evidence.json
```

Additional hermetic regression tests cover exact source matching, model timestamps, prior-date-only calculation, same-date outcome perturbations, invalid future candidate values, immutable original-first-pick selection, independent final settlement, and pending status. CI separately instantiates the shadow model on **real** current source game/box datasets and freezes a synthetic future-date matchup for source contract verification (this sanity record is **not** counted as a public prediction).

## Limits and conditions for later promotion

Historical detailed Kaggle boxes cover seasons unavailable in the current 2027 NCAA-derived Four Factors feed; the source now and historical source are not interchangeable. Current 2027 probabilities use only **verified current source fields** and fall back to the simpler Elo 3.0 components when those fields are missing. The 2027 cross-provider past-year identity bridge remains unverified; no 2026 player/team strength is silently assigned by name.

The original archived production model and the shadow candidate are not randomized, and opponent difficulty and forecast coverage could vary. A positive pooled Brier gain does not mean every schedule segment or confidence bin is good. Review year-to-year robustness, calibration, date-block uncertainty, and genuinely first-published source coverage before proposing a separate explicit, reviewed promotion. The research module itself never promotes.
