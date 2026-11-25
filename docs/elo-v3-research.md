# Elo 3.0: six research improvements (November 2026)

This candidate is **research-only** and does not alter current production Elo,
published predictions, immutable first picks or prior benchmark artifacts.

1. **Opponent-adjusted efficiency:** use only externally verified, two-sided
   ORTG/DRTG/possession boxes keyed by contest ID, day and team IDs. Shrink
   small possession samples and require three earlier matched boxes per team.
   No box means no efficiency signal. Historical compact score data do not
   contain possession boxes, so this feature is *not active* in the historical
   Elo 3.0 comparison. A separate current-season source-backed benchmark
   evaluates available box features.
2. **Adaptive home court:** start at 65 Elo, slowly update on prior completed
   home/away results, bound the estimate to 15–110, and never assume a neutral
   site is a home game.
3. **Margin of victory:** bounded logarithmic margin update with attenuation
   for wins by an already-favored team.
4. **Recent form and uncertainty:** exponentially smooth past rating updates,
   shrink by number of previous games, cap the form adjustment, and reduce
   update aggressiveness when a team has limited earlier evidence.
5. **Offseason carryover:** previous-season stable Kaggle team IDs only, with
   the existing 55% regressed and capped prior. No speculative 2026-to-2027
   school-name crosswalk for production.
6. **Probability calibration:** choose a conservative temperature using only
   completed earlier game dates, minimum 120 games and 15 dates; compare
   candidate Brier with and without temperature scaling.

Run from repository root:

```bash
PYTHONPATH=research python -m forecast.elo_v3 --out research/outputs/elo3-historical.json
python -m unittest research.tests.test_elo_v3
```

The historical evaluator compares against the *actual*
`GameAwareEloEngine` on identical, date-frozen 2016–2025 regular-season
fixtures using prior-season IDs. Reports include paired Brier, log loss,
per-season gains and source provenance.

**Limits:** Fixed parameters have not undergone nested out-of-season tuning.
This is retrospective game-date replay, not independently settled forward
picks. There is no justified Elo 3.0 promotion until historical and real
forward comparisons support a gain. The source has no verified possession
features for the historical cohort, so the six features are implemented as
optional research capabilities, not falsely claimed as six empirically
validated improvements.
