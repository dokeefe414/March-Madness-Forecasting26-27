# v0.8 — Browse a real game and understand the forecast

## Future fixtures on a date with already-recorded scores (2026-11-23 fix)

Previously the pretipoff recorder and Game Center rejected **every** future
fixture whose Eastern game date was on or before `ratings.lastGameDate`.
For busy same-day schedules, this unnecessarily withheld valid predictions.

Both consumers now pass the **exact retrieved, accepted scored-game ledger**
(`web/public/current/2027-games.json`, with the same `retrievedAtUtc`
as `2027.json`) to the shared `forecast.snapshot.forecast_scheduled`.
When a future fixture's date could overlap a scored date, it replays the
**production bounded-margin game-aware Elo** exclusively on games dated
**strictly before that fixture date**. Current-day results, form, records,
and possession figures cannot leak into the forecast. A school without any
earlier valid game retains the neutral 1500 Elo initialization; it is not
credited with fictitious games or team efficiency. Experimental score estimates
abstain in the date-frozen fallback where full-day box data cannot be safely
reproduced. The served matchup cards show this prior-date replay explicitly
and reflect the same rating inputs as the archived probability.

The original 15-minute start-time buffer, exact ESPN event IDs, strict
NCAA↔ESPN identity matching and immutable first-pick record remain unchanged.
An omitted or mismatched score ledger fails closed; no score is ever
reconstructed by querying future outcomes. Missing team identities remain
unpredicted, now with a specific diagnostic rather than a generic label.
The update adds hermetic tests for day-score leakage, rating/record display
consistency and source count mismatches.


## A game-first experience

The website opens on **Find a Game** rather than an unrelated research table. The site lists the next **five Eastern calendar days** of ESPN-public scheduled Division I fixtures at build time. Each real event can be selected by tapping its card. Its URL includes `?game=<ESPN event ID>`, making a verified game report directly shareable.

The focused game panel shows both teams, the source-listed tipoff, two-sided win percentages, the **actual** model responsible, and a four-part explanation of the evidence. Real recent games for each program, shared opponents, and previous head-to-head fixtures appear below. Dates, scores, and opponents come from the **same NCAA-derived 2027 scored-game source** used for rating computation.

Use the search box and game-date filter to narrow upcoming games. If no schedule is accessible, the page shows a missing-source state instead of making up games. The separate **Matchup sandbox** allows any two sourced programs to be compared at a hypothetical neutral site; those hypothetical odds never enter the real prediction record.

## Two distinct systems: schedule and results

- **Scheduled future fixtures:** ESPN public men's basketball scoreboard, sourced separately for each day. The status must be exactly `STATUS_SCHEDULED`, marked incomplete, and listed start more than **15 minutes after source capture UTC**. The game must fall on or before the 2027 Selection Sunday regular-season cutoff (March 14, 2027). A date alone is not proof of actual tipoff.
- **Past real scores and team ratings:** SportsDataverse NCAA-source `ncaa_mbb_schedule_2027.csv.gz` after existing strict validation. Model ratings have fresh `retrievedAtUtc`; no historical Kaggle ID is guessed as a present-day team.
- **Identity:** Season-2027 ESPN team ID obtained by independently source-verified NCAA-to-ESPN membership or alias evidence is preferred. When that ID is missing, exact unambiguous canonical program-name matching is possible. A conflicting known ESPN ID prevents a name-only guess. Unmatched ESPN fixtures remain visible but have **no probability**.
- **Cross-source availability:** If ESPN fails for one or more dates, `sourceWarnings` and `scheduleSourceAvailable` disclose gaps. Even if every ESPN date fails, the underlying NCAA score/rating refresh can still publish; Game Center says the schedule is unavailable, rather than silently pretending there are no games.

The build command is:

```powershell
$env:PYTHONPATH="research"
py -m forecast.gamecenter --ratings web/public/current/2027.json --games web/public/current/2027-games.json --online-model web/public/current/2027-online-model.json --state-space web/public/current/2027-state-space.json --out web/public/current/upcoming.json
```

The input scored-game snapshot, online model and state-space report must share exactly the current ratings' source-retrieval timestamp. The result is a public, static JSON file at `/current/upcoming.json` under the Pages base path. It is built at each scheduled site refresh, not fetched from ESPN by the user's browser.

## Where the percentage comes from

For the actual Elo fallback:

```text
P(home) = 1 / (1 + 10^(-(rating_home + homeAdv - rating_away)/400))
homeAdv = 65 Elo points at non-neutral venue, 0 at neutral
P(away) = 1 - P(home)
```

The new source-confirmed, regular-season `online logistic` challenger has distinct learned coefficients for strength gap, bounded causal form and smoothed win percentage. It may replace Elo for **future non-neutral fixtures only** when both historical-date and genuine archived-forward evaluation gates pass. The public screen also shows frozen baseline Elo, shadow challenger and experimental state-space probabilities **as research comparisons**, never as the headline operational win chance. A probability is a forecasted chance, *not* the platform's historical correctness rate.

## What other games contribute

Team ratings are updated sequentially as earlier source scores arrive. A win or loss modifies each team's Elo state and therefore influences its predicted probability against the next opponent.

For explanation, Game Center displays:

1. **Elo strength gap** (the actual source-rated team-strength difference).
2. **Home-court Elo adjustment** (65 points or zero for neutral).
3. **Recent Elo form gap** (descriptive; a fitted model feature only if the learned model is selected).
4. **Average opponent Elo gap**, a descriptive measure of who each team has faced. This is **not** an extra regression coefficient and should never be added again to the published probability.

The last five completed earlier-date games for each team are shown with win/loss, score, date and opponent. A separate table compares games against **shared opponents** with honest margins. Shared-opponent margins and prior head-to-head games are useful context, but they do not independently multiply the model's odds; they already contribute via rating histories.

Game evidence excludes the **entire current Eastern date** because the third-party score feed may expose nonzero in-progress scores and reliable tipoff timestamps are not universally available.

## Browser freshness rules

At page load, fixtures whose *scheduled* start is already past are hidden. A user may explicitly enable **Include started since last refresh** to inspect an expired source capture, but the detail panel clearly labels that number a **historical captured pregame probability**, not live in-game odds. It may also be stale due to event postponements.

The website refreshes on GitHub Actions at **1:00 a.m. America/New_York daily** and **5:17 a.m. Eastern Nov–Apr**, subject to GitHub and upstream publication delays. Clicking a game or refreshing the browser does **not** call a new real-time prediction backend. The site is a versioned static Pages publication.

## Test and maintenance

- `research/tests/test_gamecenter.py`: real source-ID joins even when display names conflict, actual prior-game evidence and shared opponents, unknown team odds held unavailable, and started events withheld.
- `web/e2e/platform.spec.ts`: browser matchup navigation with a hermetic *test-only* fixture, not published fake games; responsive layout and keyboard/accessibility smoke checks.
- The archiver reuses `forecast.snapshot.forecast_scheduled` as the probability source of truth. Do not duplicate forecast math in the browser for actual scheduled predictions.
- Next-year migration requires an intentional 2028 data-source, conference, cutoff, online-model and schedule-validation update. No evergreen season rollover is claimed.


## v0.9 direct game sharing, team jump and real postgame explanation

The main navigation now exposes **Find a Game**, **Accuracy & Picks**, and **Model Lab** directly, with shareable `?view=games&game=<ESPN event ID>` and `?view=models` links. A source-rated program in **2027 Pulse** has a one-tap **View upcoming games** action, which opens a team-filtered Game Center through `?team=<verified ncaa teamId>`. Selecting a fixture on mobile scrolls directly to its report, avoiding excessive swiping through the game list.

The team-strength panels now render compact per-game Elo curves, last-game changes and the exact prior five outcomes. The displayed opponent-aware margin-adjustment strength signal, fixed versus adaptive state-space odds, and repeated normalized-innovation drift-watch flags are **research comparisons**. Only the specifically labeled operational model determines the main winning percentage. See [model math](v09-model-validation.md).

If the Git-committed pretipoff ledger contains one or more genuine snapshots of that exact ESPN event, the individual game report renders an accessible probability-over-time plot and exact captured times. After a later independently confirmed final, it displays the original frozen percentage, real final score, winner correctness and Brier. Only the earliest settled first-pick contributes to site-wide unique-game accuracy; later snapshots may be displayed for context but cannot inflate the score. Recent verified games also appear in a compact finished-game browser. Without the archive, these panels disclose **no captured history** instead of inventing a past forecast. Source warnings and stale captures are prominently labeled.
