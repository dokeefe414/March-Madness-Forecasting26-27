# GitHub Actions, publishing, maintenance and incident runbook

## Automated workflows

| Workflow | Trigger | Guarantees |
|---|---|---|
| `CI` | feature branch push, main push, pull request | Hermetic Python tests, held-out historical benchmark, JSON report artifact, 42-year data consistency, TypeScript bracket simulations, TypeScript typecheck and production Next build |
| `Deploy website to GitHub Pages` | main push, dispatch, daily best-effort 2:47 a.m. Eastern all year + 6:47 a.m. Eastern Nov–Apr backup | Real NCAA-source 2027 finals → current Elo snapshot → historical research report → data check → static Next export → GitHub Pages |
| `Archive real pre-tipoff forecasts` | 2:07, 6:07, 9:07, 16:07 and 22:07 Eastern Nov–Apr; dispatch; own workflow push | Independently settle exact-source final scores against frozen pretipoff picks and append valid new future predictions |
| `Monitor before-tipoff prediction archive freshness` | 3:41, 7:41, 11:41, 18:41 and 23:41 Eastern Nov–Apr plus successful Pages runs | Automatically request a safe archive workflow dispatch if no active archiver and committed forecast evidence is over four hours old; alert if still stale |
| `Recover transient Pages artifact deployment failures` | Pages workflow completion with deploy-only failure | Dispatch one fresh Pages workflow run when exactly one uploaded Pages artifact existed; never retry same-run artifact upload |
| `Rebuild historical snapshots` | manual dispatch | Regenerate source-pinned historical artifacts without silently changing main |

Historical unit tests and website builds do not require a live network feed. Publishing and pretipoff archival jobs fetch it, and an upstream error must **fail closed**. GitHub's scheduled cron is best-effort; it may skip or delay a run under load.

## v2.4 independent ESPN final-score display

A separate `forecast.recent_finals` step fetches the last four Eastern days of ESPN scoreboards on every GitHub Pages build and writes `web/public/current/recent-finals.json`. Only actual ESPN `STATUS_FINAL`, `completed=true`, valid final scores and valid IDs appear. The output discloses its own retrieval timestamp, warnings, coverage, most recent ESPN final date and the independent NCAA scored-game cutoff. It is a **display feed**, not model training or archive grading. A daily source release can lag while the GitHub workflow stays green; current-season Elo continues to use validated NCAA-scored data. The browser refreshes JSON every ten minutes and on visibility return, with manual refresh. The seasonal evening archive/site/watchdog slots are 22:07/22:47/23:41 Eastern. See [full runbook](daily-games-2026-11-19.md).

## Published files versus committed historical archives

```text
web/data/rankings.json                   # committed, frozen complete 2025 season
web/data/history-index.json              # committed, 42-year historical metadata
web/public/seasons/*.json                # committed historical Elo snapshots
web/public/tournaments/*.json            # committed historical tournament results
web/public/current/2027.json             # generated only on deployment
web/public/research/benchmark.json       # generated only on deployment
```

Generated reports are in `.gitignore` to avoid committing stale daily feed data. Site API routes are **not** required: Next.js exports a static site under the Pages repository base path.

## Local release checks

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -v
py -m forecast.benchmark --out web/public/research/benchmark.json
py -m forecast.live --out web/public/current/2027.json
cd web
npm install
npm run check:data
npm run test:bracket
npm run typecheck
npm run build
```

If your machine is offline, omit only `forecast.live`; the frontend explicitly marks the current feed unavailable. Do not skip test coverage or substitute synthetic results as live.

## Scheduled Pages deployment fails after artifact upload

A scheduled 2026-11-18 deployment built the website and uploaded its artifact but failed when the Pages API couldn't see it. Rerunning that **same** failed job created duplicate `github-pages` artifacts under one run ID, causing a second failure. The recovered workflow now polls for exactly one current-run artifact, waits for API propagation, and uses a separate `recover-pages.yml` workflow that dispatches a **new Pages run** if and only if the failure is at the deploy step (not source/model/build). Automatic retry is bounded to one fresh workflow dispatch and will not loop on an auto-dispatched failure. Full investigation and recovery tests: [nightly incident runbook](nightly-recovery-2026-11-18.md).

## GitHub Pages deployment fails at configure-pages

The repository must have **Settings → Pages → Build and deployment → Source: GitHub Actions** configured. The failure `Get Pages site failed / Not Found` happens before any app build and is a Pages setting issue, not a Python forecasting error. After setup, use [the deploy workflow](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/deploy-pages.yml) to run a fresh build.

Expected URL: `https://dokeefe414.github.io/March-Madness-Forecasting26-27/`. The production build sets `NEXT_PUBLIC_BASE_PATH=/March-Madness-Forecasting26-27` so season/tournament/current/research JSON loads under the correct static prefix.

## 2027 refresh fails

Inspect the `Validate and build 2027 NCAA-source results` step:
1. Confirm [SportsDataverse schedule release](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/ncaa_mbb_schedule) exposes `ncaa_mbb_schedule_2027.csv.gz`.
2. Compare upstream source update timestamp to the last accepted result date.
3. Confirm expected CSV headers, season=2027, no inconsistent duplicates, positive final scores, and valid dates.
4. If the source is late/unavailable, **do not** publish fictitious results: keep previous successful site and display its recorded timestamps.
5. Any upstream format change needs a documented importer/schema change and new hermetic tests.

## Research or bracket regressions

If benchmarking fails, check source pin matches for history-index/snapshots/tournament files and avoid arbitrarily omitting difficult seasons. If bracket validation fails, verify exactly four regions with ordered slots and actual source team ratings. The Opening Round slot count should be 0, 1, 4 or 12 (fields 64, 65, 68 or 76). Expected simulated advancement sums: Round of 32 = 32, Final Four = 4, finalists = 2, champion = 1.

## Maintenance responsibility

- Update `docs/validation.md` if models/features/calibration shift.
- Update `docs/current-season.md` for external source contracts and dates.
- Update `docs/bracket-engine.md` when official field formats or region crossover rules change.
- Update `docs/design-system.md` for tab/component redesigns.
- Before the 2028 season, explicitly review the feed name, source URL, Python `SEASON` and cutoff, unit tests and front-end year label. A 2027 snapshot must not accidentally masquerade as live 2028.

## v0.6 additional workflows and production verification

### Pre-tipoff forecast archiver

`.github/workflows/archive-pregame.yml` schedules **2:07, 6:07, 9:07 a.m. and 4:07 p.m. America/New_York best-effort** daily runs during Nov–Apr and permits manual dispatch. It fetches validated 2027 source Elo data, lists ESPN scheduled games that start >15 minutes after forecast creation, and Git-commits **new** snapshot/settlement JSON files under `web/public/forecasts` with bot author. GitHub branch protection / token `contents:write` may block bot pushes. Inspect the scheduled job and archive files before saying the audit is operational. Missing future matches is not an error; no forecast is backfilled. After archiver commits, the next regular Pages rebuild will make the derived index visible.

### Source coverage runbook

Four source families determine the 2027 UI, with different fail policies:
1. SportsDataverse NCAA schedule (`ncaa_mbb_schedule_2027.csv.gz`): **mandatory** and strict on invalid core schema; no published scores if broken.
2. NCAA 2027 team IDs/conferences (`ncaa_mbb_team_ids_2027.csv.gz`): optional. Exact full-name join; reports source match count, never guesses other teams.
3. NCAA 2027 team box (`ncaa_mbb_team_box_2027.csv.gz`): optional. Only game-ID-matched, genuine possession rows become per-100 efficiency profiles.
4. Season group reference (`mbb_group_seasons.csv` and `mbb_team_group_seasons_2027.csv`): optional. Independently confirms `divisionIConfirmed` when a documented season-2027 Division I `subdivision_id` matches the scored team by exact normalized name. Otherwise status unavailable or team unverified. **This is not postseason eligibility certification.**

The watchlist requires both D-I subdivision membership and NCAA conference matching, and at least 76 candidates in exactly 32 mapped leagues. Source absence returns an explicitly missing/hypothetical field, not 76 invented selections.

### Historical model order

Deploy runs `forecast.benchmark` **before** `forecast.live`, so `productionCalibration` contains only historical outcomes through 2025 and is available for clearly labeled regular-season *scenarios*. Never train the current production calibration with 2027 scores or tune it to the same day's held-out outcome. `forecast.snapshot` intentionally records baseline Elo for pregame audit, not these unvalidated March-to-November scenarios.

### CI and browser quality

The third `CI` job now executes Playwright desktop and mobile against the **Next static export**, preventing false confidence from dev-server HMR. Checks include navigation, actual historical bracket interaction, full-page horizontal width, and automated critical WCAG axe violations. Upload `playwright-v06-visual-checks` includes test traces/screenshots for CI failures. All three CI jobs must pass before merging. [Browser guide](browser-quality.md).

### Fixing a failed production release

Inspect the first failure in the [Pages workflow](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/deploy-pages.yml). If the mandatory source, historical calibration generation or production build fails, do not invent data or bypass a cutoff. Fix source parsing using a new hermetic regression test, merge through passing CI, and confirm the next Pages deployment returns success with a current `lastGameDate` and `retrievedAtUtc`. A successful web build alone does not prove the user's website has been deployed.

The 2027 source convention must be reviewed before the 2028 season; never display a 2027 report as new-season 2028 ratings.

### 2027 name-space reconciliation runbook

The initial v0.6 source-run returned **365 exact NCAA directory matches but 0 direct ESPN-subdivision-name matches**. Check [SportsDataverse `mbb_groups`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_groups) asset `mbb_team_aliases.csv`. The importer now consumes only NCAA-source name aliases with a matching 2027-valid season window and the original ESPN group team ID, then checks the source team's 2027 Division I membership. If no matches appear, inspect schema, provider alias dates and coverage **without relaxing** the ID/season validation. The watchlist is deliberately unavailable until joined Division I membership is actually verified.

### Season-specific NCAA-to-ESPN ID crosswalk

The team-group source uses ESPN team IDs, while the NCAA schedule/team-directory uses distinct, season-specific stats.ncaa.org team IDs. The 2026–27 `ncaa_espn_team_crosswalk.csv` in [`mbb_crosswalk`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/mbb_crosswalk) provides the explicit dated numeric mapping. It is now the **primary** cross-provider lookup when a 2027 mapping exists; old/source-dated NCAA name aliases are additional conservative fallback.

Check deployed `divisionCoverage.seasonNCAAIdMatchedTeams` and `divisionIConfirmed` after refreshing. If zero, confirm whether the upstream crosswalk already contains `season=2026-27` rows before considering fixes. **Do not** use 2025–26 NCAA IDs for 2026–27 because the NCAA issues new team IDs each year. Keep the hypothetical watchlist unavailable rather than inventing a field.

### 32 source conferences but 31 display labels

The deployment artifact may report 32 independently verified 2027 D-I conference groups and only 31 distinct NCAA team-directory conference display strings. This is not evidence of missing a D-I league; it is a difference in data labeling. Field Watch now requires and groups by `divisionConferenceGroupId` from verified season-2027 group membership, not the display label. Validate output `selectionWatchlist.matchedConferences=32`, `distinctConferenceDisplayNames=31`, `conferenceLeaders=32`, `atLargeCandidates=44`, and `len(teams)=76` on the first successful production build, and confirm the UI still calls it hypothetical. Do not bypass D-I verification or re-label an Elo AQ proxy as a real conference champion.

## Nightly update automation (November 2026 configuration)

The publishing job's primary scheduled trigger is **`cron: "47 2 * * *"`, `timezone: "America/New_York"`**, every day of the year. This is **2:47 a.m. local Eastern** even when daylight saving changes. In season, the **2:07 a.m. forecast archival run** precedes it so verified finals can be graded before publishing. A second **6:07 a.m. archive** followed by a **6:47 a.m. Pages backup** catches late West Coast games and upstream final-score delays. GitHub's scheduled actions are best-effort and can start late or be dropped under load. Do **not** remove the main-push and manual dispatch triggers: they provide recovery after outages and publish verified code changes.

The independent `archive-pregame.yml` job also runs at **9:07 a.m. and 4:07 p.m. Eastern** during basketball months to preserve pretipoff coverage. Its source-linked picks are immutably committed if and only if it can find valid scheduled events with more than a 15-minute pregame buffer. It also settles previous picks once accepted results appear; it never overwrites prior prediction files. A bot commit to main is not relied upon to trigger another push-based workflow. Pages instead listens for successful archive completion and maintains explicit **2:47/6:47/10:17/17:17 ET** backup publishing. Independent archive-health monitoring runs at **7:35/11:35/18:35 ET** with a six-hour age limit; a successful Pages build alone does not prove that settled forecasts were archived.

`research/forecast/freshness.py` runs **after** the real source ingest and **before** the Next.js build. It fails deployment for incorrect season or source provenance, source retrieved more than two hours earlier, future timestamps, invalid rating or duplicate ID, impossible win/loss totals, mismatched latest result date, or inconsistent sequential pregame evaluation count. It writes `web/public/current/refresh-status.json`, which reports real UTC refresh time, most recent scored game, total accepted games, team count, verified D-I program count and the provider lag. A feed with no recent games is disclosed as `source-may-be-delayed`, not silently represented as live. This guard verifies internal consistency, **not** the truth or final-state of every upstream game.

```powershell
$env:PYTHONPATH="research"
py -m forecast.benchmark --web-dir web --out web/public/research/benchmark.json
py -m forecast.live --model-report web/public/research/benchmark.json --out web/public/current/2027.json
py -m forecast.freshness --input web/public/current/2027.json --out web/public/current/refresh-status.json
py -m forecast.audit --dir web/public/forecasts
```

If no update appears after the expected time, inspect [deploy runs](https://github.com/dokeefe414/March-Madness-Forecasting26-27/actions/workflows/deploy-pages.yml), the last game date and both UTC timestamps. Try the **Run workflow** control on the Actions page; a scheduled event is not guaranteed to execute on the dot. If `forecast.freshness` rejects a malformed feed, repair the cause with a hermetic regression test rather than bypassing the validation. GitHub disables scheduled actions on inactive public repositories after 60 days; check the Actions tab in the off-season. GitHub Actions also requires that workflow files reside on default `main`.

## v0.7 in-season model retraining

The Pages job runs `forecast.live --games-out web/public/current/2027-games.json` followed by `forecast.retrain --games ... --ratings web/public/current/2027.json --out web/public/current/2027-online-model.json`. Each 2:07/6:07/9:07/16:07 Eastern prediction archive repeats both source-linked steps before it freezes upcoming predictions. A retraining error fails the job rather than producing an unverified forecast. The model scores and Brier improvement gate are publicly inspectable in Current Pulse and in `/current/2027-online-model.json`. The raw scored-game archive and model report are generated deployment artifacts, not permanently source-controlled histories. [Full chronological methodology](online-retraining.md).


## v0.8 Game Center publishing, forward performance, and missed-call operations

After the 2027 ratings and regular-season logistic model are rebuilt from the same source retrieval, the Pages workflow also runs:

```powershell
$env:PYTHONPATH="research"
py -m forecast.state_space --games web/public/current/2027-games.json --ratings web/public/current/2027.json --out web/public/current/2027-state-space.json
py -m forecast.gamecenter --games web/public/current/2027-games.json --ratings web/public/current/2027.json --online-model web/public/current/2027-online-model.json --state-space web/public/current/2027-state-space.json --out web/public/current/upcoming.json
py -m forecast.audit --dir web/public/forecasts
```

The ESPN schedule requests are **best-effort over five Eastern days**. One bad day is logged in `sourceWarnings`; a complete outage is explicitly marked as unavailable, **not** an invented set of fixtures, and should not block the unrelated NCAA scored-game rebuild. Actual historical time-series data remains separately sourced. The Game Center shows no odds for an ambiguous/unverified NCAA↔ESPN link. A selected fixture whose listed start has passed is hidden unless the user explicitly elects to see a historical capture.

At each 2:07/6:07/9:07/16:07 Eastern archive run, the archiver also fits the state-space **research** candidate then freezes its probability (when source-supported), alongside actual selected Elo or logistic and optional shadow challenger probabilities. The immutable source files still own the evidence. The score index now includes `uniqueGames` for one earliest pick per event; `forecast.audit` independently recomputes the aggregate. If there are no genuinely settled predictions, forward winner accuracy is *unavailable*, never inferred from a backtest.

Missing/wrong predictions remain frozen. After newly accepted previous-day finals appear, the standard nightly retraining uses them chronologically. Before promoting the learned challenger, require existing date-block thresholds plus **at least 40 genuine earliest-game settled Elo and shadow candidate comparisons** with prospective Brier gain >=0.002. Never force an update after an individual upset or silently edit a previously public pick.

Public reference endpoints: `/current/upcoming.json` and `/current/2027-state-space.json` for sourced schedule and experimental team trajectories, `/current/2027-online-model.json` for model status, and `/forecasts/index.json` for actual pregame accuracy (created only when the archive has run). See [game-center](game-center.md), [forward scoring](forward-performance.md) and [state-space](state-space.md).


## v0.9 independent-final archiving and monitor

The primary runbook is [v09-forecast-operations.md](v09-forecast-operations.md). It covers Eastern local workflow schedule, newly required **ESPN completed final + matching NCAA scores** before settling, what happens on delayed or mismatched data, twice-daily website re-publication after archival changes, and a visible GitHub Actions alert when `monitor-archive.yml` finds a stale, absent or zero-pick archive. The website publishes `/current/archive-health.json` and must distinguish genuine source status from a green Pages compilation.

All new artifacts are versioned current 2027-source-generated outputs. `python -m forecast.archive_health --ledger web/public/forecasts --require-recent` is intentionally strict in season; it may fail before the first genuine scheduled archive. Never substitute historical replay accuracy to make it green.


## v1.1 operational evidence and recovery

The pregame workflow now runs when its own definition changes on main, in addition to best-effort scheduled archiving and manual dispatch. Once a verified ESPN schedule check and independently sourced ratings are complete, the derived index is committed even if there are zero eligible future picks. Its `archiveHealth.fixtureCoverage` and `verifiedFixtureRun` fields provide a non-fabricated receipt. The monitor recognizes a fully verified clean `no-eligible-fixtures` outcome; it still fails a missing, stale, ambiguous or partial run. Git pushes retry non-forced after a fetch/rebase, with any conflict failing closed. See [v1.1 implementation](v11-season-intelligence.md) for the exact states, review steps and model diagnostics.


## v1.3 verified capture operations dashboard

The Pages rebuild publishes `current/operations.json` from source-controlled immutable prediction snapshots and final settlements. This file exposes archive capture age, source coverage, ambiguous ESPN fixture identities, repeated before-tipoff snapshots, unique ESPN events, independently settled game IDs and unresolved older-than-48h entries. The checklist is descriptive: old listed tipoff does **not** prove a game completed. When an ESPN event with the same ID appears in refreshed scoreboard data with a changed time, the original forecast is not edited; `archiveHealth.observedScheduleChanges` records a review warning. A changed date can prevent settlement because the original settlement rules refuse to invent a consistent result. Inspect [the v1.3 recovery and chronology guide](v13-research-tournament-operations.md) before intervening. The GitHub monitor remains independent of a successful Pages deployment and CI success is not evidence of actual prospective skill.


## AP poll: independent Monday research schedule

No new navigation, worker, paid API key, or additional persistent service
is needed. `archive-pregame.yml` reuses the accepted current-season
Elo/game inputs, fetches ESPN's **AP-only** basketball rankings, freezes
the first valid source poll edition against a Sunday-cutoff Elo replay,
and safely commits `web/public/research/ap-poll-history.json`. Weekly
Monday 18:07 ET archival and 18:47 ET Pages publishing complement the
existing daily jobs, which retry if AP is delayed. The site reads the
committed JSON under Model Lab; a missing poll is visibly pending.
First-pick win/loss grading is completely separate; see
[weekly AP method and controls](ap-poll-weekly.md).


## Elo 2.0 nonoperational Page-build experiment

Pages now publishes an entirely separate Elo 2.0 *research* report after the existing live source-aware Elo step, but **before** downstream challenger training. Its pinned historical 2016–2025 evaluation uses same-date fixed-policy control/challenger game streams, true previous-season team-ID carryover and strictly causal prior opponent ratings. The provisional 2027 study uses a **partial 2026 source** and exact-name links only, so automatic model replacement is prohibited. If the external pinned historical raw file is offline, the report must say unavailable; daily live game updates and first-pick grading stay independent. Audit the `elo-v2-historical.json.status` and `elo-v2-research.json.ratingRetrievedAtUtc` source-match before interpreting its Model Lab display. [Complete methodology](elo-v2-research.md).
