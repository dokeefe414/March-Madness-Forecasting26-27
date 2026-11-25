# Elo 3.0 prospective cohort and disagreement diagnostics

## Purpose

This stage makes the scheduled Elo 3.0 shadow test independently auditable.
It separates all recorded shadow probabilities from **original earliest
first-pick** probabilities for each ESPN event, keeping older published picks
immutable. The new report lives inside the published current accuracy research
artifact under the key prospectiveElo3.diagnostics; Model Lab displays its
coverage, upcoming disagreements, and fixed performance breakdowns.

The historical 2016–2025 test does NOT become prospective evidence. This
report only uses original first-published pretipoff snapshots and independent
ESPN-final / matching-NCAA-score settlements.

## Cohort and coverage accounting

The diagnostics report:
- All captured Elo 3.0 probability rows, including later revisions
- Distinct ESPN event IDs with any Elo 3.0 capture
- Earliest first picks that actually included a valid Elo 3.0 candidate
- Events with an Elo 3.0 probability **only in later snapshots**, excluded
  from prospective first-pick scoring even if a result is known
- First picks after Elo 3.0 shadow launch, with a denominator for missing
  Elo 3.0 first-pick coverage
- Verified original outcomes and pending first picks, each with explicit status

Missing or unsettled results are never considered losses. The original model
probabilities, archive snapshots and production game picks are never rewritten.

## Upcoming disagreement list

From the eligible original first-pick cohort, a maximum of 12 not-yet-started
games are shown, sorted by the absolute difference between frozen Elo baseline
and frozen Elo 3.0 home-win probabilities. Each item includes its ESPN event ID,
scheduled UTC start, team names, neutral-site status, original probabilities,
percentage-point gap and whether the picked winner differs. A 50% tie does not
count as picking a winning side. After the originally listed start, a game
leaves the upcoming list. Listed start alone does not certify actual tipoff.

The watchlist is not an assessment of success, not a claim of calibration and
not a wagering recommendation.

## Predeclared segments

Every segment counts eligible FIRST picks for coverage, but calculates Brier,
winner accuracy and gain only from independently settled, matched outcomes:

| Group | Fixed categories |
|---|---|
| Incumbent model confidence | Close (50–59%), moderate favorite (60–74%), strong (75%+) |
| Probability disagreement | Under 5 percentage points, 5–under 10, 10 or more |
| Venue | Listed home, neutral |
| Snapshot lead before listed tipoff | 15 min–under 6 h, 6–under 24 h, 24+ h |
| Selected winner | Same or tied, different |

Each subgroup is **descriptive only** until at least 30 verified games and
six independent game dates. The much stricter model-level prospective review
gate remains: at least 100 verified paired games, 12 game dates, Brier gain
at least 0.002 and a positive lower date-block confidence bound.

Five fixed probability confidence bands also compare model confidence against
verified winner frequency; their ECE is not evidence of stable calibration at
small sample sizes. No subgroup automatically promotes a model.

## Technical safeguards

- Original first picks are chosen from archive files sorted by timestamp and
  distinct ESPN event ID. Later updates never substitute for earlier picks.
- A shadow candidate must retain its original same-snapshot Elo baseline;
  any mismatch with the independently derived settlement evaluation raises.
- Any nonfinite, nonprobability, duplicated outcome, or forecast missing
  the existing 15-minute source/tipoff timing guard is rejected.
- Same-source 2027 team and box checks, prior-date-only model replay,
  and no guessed 2026 team-ID carryover remain unchanged.
- The new diagnostic report is reconstructed from append-only Git JSON, not
  stored as a new source of results or altered after a game is complete.

## Reproducible checks

Run the new unit and archive integrity checks:

    PYTHONPATH=research python -m unittest research.tests.test_elo_v3_forward_diagnostics -v
    PYTHONPATH=research python -m unittest research.tests.test_elo_v3_prospective -v
    PYTHONPATH=research python -m forecast.audit --dir web/public/forecasts
    PYTHONPATH=research python -m forecast.accuracy_research --ledger web/public/forecasts --out web/public/current/accuracy-research.json

The generated accuracy report must satisfy all these invariants:
eligibleOriginalFirstPicks equals prospectiveElo3.firstFrozenPicks;
verifiedPairedFinals equals prospectiveElo3.verifiedPairedFinals;
allCapturedShadowPredictions is never smaller than eligible original first
picks; pending counts are nonnegative; activePredictorReplaced is false.

CI tests both hermetic synthetic edge cases and the actual source-linked
historical archive. GitHub Pages regenerates the diagnostics with every
accepted archive refresh.

## Limits

A large forecast disagreement is a hypothesis, not a verified correct pick.
Segments are exploratory: testing several groups raises selection bias.
Historical box-score improvements do not prove a 2027 forward improvement.
Current NCAA 2027 Four Factors coverage remains incomplete; missing
statistics must never be fabricated. The primary model stays unchanged until
an explicitly reviewed prospective decision is justified.
