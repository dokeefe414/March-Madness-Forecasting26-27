# Verified date-frozen efficiency, latent offense/defense and ensemble research

## Implementation

`research/forecast/efficiency_latent.py` is a standalone research benchmark
over the existing `source_game_boxes` artifact. It requires the **same
retrieval timestamp** as the score/rating snapshot, the exact NCAA contest
ID, full home/away identity, paired possession/ORTG/DRTG records and bounded
finite values. Missing, one-sided, duplicate or contradictory records fail
closed or abstain; they never become estimated possession data.

For a game dated D, all predictions use team states from games dated
strictly before D. All updates happen only after the full date's games have
been evaluated. Current Eastern-date results are entirely embargoed.

Each team has independent Gaussian offense and defense latent effects
(per 100 possessions), with possession-scaled observation noise and
process variance. The opponent attack/defense matchup yields a
shrunk, uncertainty-attenuated probability. An Elo comparator is evaluated
on **exactly the same eligible games**. A convex Elo/latent ensemble uses
weights chosen exclusively from prior game dates, requiring at least 40
eligible past games, six dates and 0.002 past Brier improvement before
any nonzero blend.

## Run

From the repository root (after generating current score/rating/paired-box
artifacts with the existing pipeline):

```bash
python -m research.forecast.efficiency_latent \\
  --games web/public/current/2027-games.json \\
  --ratings web/public/current/2027.json \\
  --boxes web/public/current/2027-source-game-boxes.json \\
  --out web/public/current/efficiency-latent-research.json

python -m unittest research.tests.test_efficiency_latent
```

The output reports paired source games, eligible comparison games, withheld
games, matched Brier and log loss, date-by-date blend weights, and all
research assumptions.

## Interpretation and next scientific gates

This is **retrospective date-frozen research**, not genuinely archived
before-tipoff forecasts. NCAA-derived final-score acceptance is not the
independent ESPN+NCAA settlement used for public pick grading. Its
matched simple Elo baseline is not the production margin-aware Elo engine.
No live winner probability or historical snapshot is overwritten.

The filter's 100-point scoring prior, noise constants, 18 Elo per net
point and reliability shrinkage are fixed starting assumptions, not
historically tuned or claimed optimal. The next steps are source-complete
historical seasons, expanding-season hyperparameter validation, genuinely
frozen candidate probabilities, independent settlements, candidate-specific
calibration and a comparison against the **actual** game-aware production
Elo on identical first-pick fixtures. Until then promotion is disabled.
