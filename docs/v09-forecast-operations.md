# v0.9 — Archived prediction reliability and automated operating schedule

## Why an apparently successful site might have shown no accuracy

The site rebuilds ratings and upcoming fixtures from provider files, but a **real forward accuracy percentage requires an independent Git-committed pregame prediction and later settlement**. A green GitHub Pages deployment alone does not prove that separate archive action ever ran.

The repository's previous first deployment had **no committed `web/public/forecasts/index.json`**. It was therefore correct to display **—** rather than 0% or a guessed success rate. v0.9 adds a monitor so a missing/delayed archive cannot go unnoticed as if everything were fine.

## Eastern time schedule

Local DST-aware GitHub Actions cron with `timezone: America/New_York`:

| Local time | Workflow | Purpose |
|---|---|---|
| 02:07 ET Nov–Apr | `archive-pregame.yml` | Independently verify overnight finals and settle previously frozen picks; snapshot only still-future fixtures |
| 02:47 ET daily | `deploy-pages.yml` | Publish refreshed source scores, models, graded winners/misses and future-game forecasts (year-round) |
| 06:07 ET Nov–Apr | `archive-pregame.yml` | Recheck late West Coast finals and delayed NCAA score feed |
| 06:47 ET Nov–Apr | `deploy-pages.yml` | Republish verified overnight settlements and newest NCAA-source information |
| 03:41 ET Nov–Apr | `monitor-archive.yml` | Check missing overnight archive and dispatch an idempotent recovery |
| 09:07 ET Nov–Apr | `archive-pregame.yml` | Capture verified future pretipoff picks and retry pending finals |
| 10:17 ET Nov–Apr | `deploy-pages.yml` | Publish the newest morning Git-committed accuracy evidence |
| 07:41 ET Nov–Apr | `monitor-archive.yml` | Inspect late-night settlement capture; dispatch recovery if missing |
| 11:41 ET Nov–Apr | `monitor-archive.yml` | Recover absent/stale morning archive and alert until healthy |
| 16:07 ET Nov–Apr | `archive-pregame.yml` | Capture evening fixtures and retry unresolved scores |
| 22:07 ET Nov–Apr | `archive-pregame.yml` | Same-evening source-verified finals and remaining future pretipoff picks |
| 17:17 ET Nov–Apr | `deploy-pages.yml` | Republish verified afternoon picks and updated models |
| 22:47 ET Nov–Apr | `deploy-pages.yml` | Rebuild ESPN-confirmed recent finals panel and newest NCAA-derived Elo |
| 18:41 ET Nov–Apr | `monitor-archive.yml` | Recheck afternoon archive and dispatch safe recovery if missing |
| 23:41 ET Nov–Apr | `monitor-archive.yml` | Recheck 22:07 evening archival evidence and recover if missing |

GitHub Actions is **best effort**; scheduled jobs may run late, be skipped under load or fail if third-party endpoints are unavailable. The monitor itself is best-effort. The page never guarantees second-by-second scores.

Important: GitHub Actions runs made with the default `GITHUB_TOKEN` do not reliably fire downstream `push` workflows, so the explicit **02:47/06:47/10:17/17:17/22:47** Pages refreshes serve the immutable archive captured at 02:07/06:07/09:07/16:07 respectively. A successful archival `workflow_run` also requests a Pages build; the independent schedule is a backup when that event fails.

## Final-status validation and failure behavior

`forecast.snapshot` now fetches real ESPN source scoreboard for future scheduled dates and for previously archived game dates within a bounded 45-day lookback (checking the oldest 12 pending dates plus the three latest dates per run). The original NCAA scored-game source still builds the 2027 team strength.

**For a settlement to count**, there must be exactly one matching NCAA source result and an independently retrieved ESPN status of `STATUS_FINAL`, `completed=true`, with the exact ESPN event ID, matching date and **identical positive home/away score**. A postponed or still-in-progress match is not graded. A provider rate-limit/timeout is recorded as a source warning and leaves that event pending. Nothing is settled simply because the NCAA feed shows a nonzero score.

New and historical scores in the public Git archive are immutable files; only `index.json` is regenerated as a derived rollup. Repeated workflow runs must not create a second settlement for the same `snapshotId:eventId`. The audit checks source/as-of, time buffer, original forecast probability, actual score arithmetic, frozen candidate probability bounds, result identity, and index aggregation.

The daily archive outputs **`archiveHealth`** in `index.json`: run time, new predictions, verified new settlements, total archived predictions, count of completed ESPN events checked, source warnings and current status. The independent Pages rebuild evaluates age and publishes **`/current/archive-health.json`** with state `current`, `stale`, `source-partial`, `no-picks-yet`, or `awaiting-first-archive`. The website displays that honestly; a missing index is not replaced by a manufactured percentage.

`monitor-archive.yml` now runs independently at **03:41/07:41/11:41/18:41/23:41 ET** and also after successful Pages deployments. It fails if the in-season Git-committed ledger is missing, older than **4 hours**, or cannot provide an eligible verified archive. If only freshness is failing, it first checks for an already-running archive and dispatches `archive-pregame.yml` on `main` if none is active; the archived snapshot code still prevents post-tipoff prediction backfill. An actionable issue stays open while evidence is stale, and closes only after a genuinely fresh, audited archive exists. GitHub's workflow failure notifications remain an additional alert, not a promise of perfectly timed cron.

## Model training and score audit

Every site refresh rebuilds `2027.json`, `2027-games.json`, `2027-online-model.json`, `2027-opponents.json`, `2027-state-space.json`, `upcoming.json`, `archive-health.json` from exact current provider captures. The overnight, morning and afternoon archiver runs rebuild the underlying rating/model artifacts before it freezes future predictions, and commits **only** the public immutable archive receipts.

Opponent-adjusted margins and fixed/adaptive state-space predictions are **research alternatives**. All are frozen with their name and source as-of in each future-game snapshot where valid. The selected main chance remains Elo or the carefully gated online logistic correction. Missed games are permanently recorded. New **previous-date** sourced outcomes feed the next fit; no instant retroactive correction is permitted.

The new `uniqueGames.pairedModelComparisons` provides actual paired first-pick Brier, accuracy, date counts, and descriptive bootstrap interval for each challenger. The model lab displays the unambiguous distinction from retrospective date-frozen experiments.

## Runbook for a failed refresh or missing picks

1. Open [GitHub Actions archive](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/archive-pregame.yml), [monitor](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/monitor-archive.yml), and [Pages](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/deploy-pages.yml).
2. Check whether the archive workflow exists/has run on `main`, and whether a provider failed or a Git push was rejected. The previous green Pages build cannot substitute for this check.
3. The archive watchdog automatically requests a safe `workflow_dispatch` when a capture is missing and no archive run is active. Inspect the watcher first; only manually dispatch the archive on **main** if recovery is blocked. Never invent previously unseen predicted probabilities or alter immutable snapshot contents.
4. Inspect `web/public/forecasts/index.json`, `archiveHealth`, and the source-explicit `/current/archive-health.json`. Expect the game picker to display **—** for accuracy if no first-pick settlement has been verified.
5. If there was a source mismatch, preserve the original forecast. Recheck ESPN final status and NCAA final score; do not force its settlement.
6. After a successful archival commit, the archive-completion Pages trigger and independent scheduled Pages builds can republish it. For late games, check again after 06:47 ET. A separate `recover-pages.yml` automatically dispatches a fresh Pages run when a genuine Pages **deployment step only** fails even though exactly one artifact was uploaded. Do not retry that same failed job: a repeated upload under the same run ID can make two `github-pages` artifacts and block deployment. See [full incident analysis](nightly-recovery-2026-11-18.md).

### Reproduce locally

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_archive_reliability.py" -v
py -m unittest discover -s research/tests -p "test_archive_health.py" -v
py -m forecast.archive_health --ledger web/public/forecasts --out web/public/current/archive-health.json
py -m forecast.audit --dir web/public/forecasts
```

Monitoring `--require-recent` is intentionally strict and exits nonzero in season when no genuine archive exists or it is stale. A dry-run/CI unit test can validate code but does **not** certify an actual daily provider schedule has happened before its first local time.

### Limitations

The ESPN scoreboard and NCAA-derived schedule may both lag and could share data-origin errors. The absence of a final status prevents settlement but does not establish a canceled game. Sources have dates but not independently guaranteed true tipoff clocks; a valid archived forecast asserts timing relative to the ESPN *listed* start. Date changes and conflicting scores are handled conservatively. A completed flow cannot guarantee future game prediction accuracy. No forecasts for seasons beyond the explicitly sourced 2027 regular season are invented.


## v2.3 recovery hardening, November 18–19, 2026

The previous scheduled site refresh built successfully but GitHub's Pages deploy API temporarily failed to find the already-uploaded artifact. Repeating that job under the same run ID then uploaded a duplicate artifact and failed again. Pages builds now verify that **exactly one** artifact exists before attempting deployment and allow extra propagation time; a guarded `workflow_run` recovery dispatches a **fresh run** only for the specific deploy-only error. Separate explicit Eastern archive cron expressions plus the independent four-hour watchdog address dropped scheduler invocations. The first-pick archive remains immutable, and GitHub's scheduling remains best-effort rather than a continuous service. Full verified failure evidence, recovery guards, CI procedures and response steps: [nightly recovery incident runbook](nightly-recovery-2026-11-18.md).


## v2.4 daily final-score visibility (Nov 19, 2026)

The regularly refreshed NCAA-derived schedule is not an instantaneous authoritative final-status feed. An evening Nov 19 Pages deployment used 953 source-accepted games but included only games through Nov 18. Separately, the main fixture list hid already-started games, making successful updates appear absent. The Game Center now includes a dedicated [ESPN-confirmed Recent Finals scoreboard](daily-games-2026-11-19.md) (past four Eastern dates), which does **not** silently add unconfirmed ESPN results into Elo or immutable grading. The browser rechecks static JSON every ten minutes/on tab return, and an evening 22:07 archive, 22:47 site refresh and 23:41 watchdog reduce long after-school gaps. A green build is not proof the NCAA source has today's scores; compare ESPN `mostRecentEspnFinalDate` and NCAA `lastGameDate` separately.


## v2.5 source-reconciled Elo in existing overnight and evening jobs

The nightly pipeline now actually updates 2027 Elo when a qualifying
ESPN-completed game is available ahead of the delayed NCAA schedule.
The archive workflow runs `forecast.live --save-espn-receipts` before
`retrain`, `state_space` and the pretipoff snapshot. It commits the
durable `web/public/forecasts/espn-final-receipts.json` alongside
immutable forecast/settlement artifacts. The Pages workflow reads those
receipts and also checks the latest seven Eastern days of ESPN finals
before it retrains and publishes the upcoming fixtures.

Check `current/2027.json.sourceReconciliation` after a run:
`ratedEspnOnlyFinals` should be positive when the NCAA file is behind
but uniquely ID-verified ESPN finals have arrived. `ncaaLastGameDate`
can lag while `lastGameDate` reflects newer rated ESPN games.
Review `rejectedOrReconciled` and source warnings for skipped outcomes.
On a provider outage, the committed receipts protect earlier rated
ESPN-only games; no nonexistent scores or pretipoff picks are manufactured.
The archive's **actual original forecast grading** remains strictly
dual-provider, even when the Elo input accepts source-ID-verified ESPN
finals earlier. No guarantee of instant buzzer publication or steadily
improving accuracy. See [daily Elo research and incident runbook](daily-elo-2026-11-19.md).


## v2.6 Monday AP Top 25 research capture

The existing archive now also runs `python -m forecast.ap_poll` after
source-verified 2027 Elo is built. New AP editions (strict `AP Top 25`
from the ESPN men's NCAA rankings feed) are compared against **Elo replayed
only through the Sunday before the new AP poll week**, using exact
season-2027 source ESPN IDs. Each source week is committed once in the
same non-force archival Git push as the frozen forecast ledger:
`web/public/research/ap-poll-history.json`.

**New Monday slots:** 18:07 Eastern for AP poll/forecast archive; 18:47
Eastern for website publication. Every other standard archival run also
checks if an AP edition has appeared late; an unavailable poll leaves
the prior history intact and cannot block game scores or first picks.
Model Lab shows AP-versus-Elo overlap, gap, correlation, outsiders and
the weekly trend. These are rank-agreement diagnostics only, never
prospective forecast accuracy. See [AP comparison research runbook](ap-poll-weekly.md).


## v2.7 Elo 2.0 research replay (unchanged live pick schedule)

The Pages workflow now runs two additional **non-operational** steps after the existing source audits: `forecast.elo_v2_historical` downloads the SHA-pinned Kaggle men's compact regular-season games and constructs **2016–2025 fixed-policy same-match heldout evidence**, then `forecast.elo_v2_current` compares source-accepted current-season results with a carryover-plus-prior-opponent-adjusted shadow rating and stored AP editions. The historical step writes `web/public/research/elo-v2-historical.json`; the current shadow report writes `web/public/current/elo-v2-research.json`. If the pinned historical raw source cannot be reached, the report must be explicitly unavailable, not a fabricated historical gain. Neither script mutates first-pick forecasts or invokes promotion. The current 2026 historical prior is only through Kaggle day 118 and name-joined, **not independently ID-verified**. A future model switch requires independent prior-year coverage plus paired prospectively issued forecasts—not merely AP rank agreement. See [the research runbook](elo-v2-research.md).
