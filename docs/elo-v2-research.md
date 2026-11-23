# Elo 2.0 — prior-season carryover, causal opponent schedule and true held-out evaluation

**Release:** v2.7 research challenger, November 23, 2026  
**Status:** Research only — *no change* to the operating source-aware Elo, immutable pretipoff picks, first-pick accuracy or automatic selection policy.

## Why this experiment exists

The operating 2027 Elo restarts every team at **1500**. That makes early November results overly influential because a returning strong program and a rebuilding program start with identical numerical strength. The baseline already adjusts an individual game's expected winner for **that opponent's pregame Elo**, and uses bounded winning-margin updates. It is **incorrect** to claim the baseline never accounts for who you play.

This work tests two *additional* hypotheses, rather than assuming they're improvements:

1. Previous-season strength can improve the preseason rating prior, if a team has an accurately matched historical identity.
2. An individual's **past opponent schedule** can supply a small shrinkage-adjusted residual strength signal, in addition to the baseline's normal game-opponent Elo.

The important test is whether the combination reduces **same-game, out-of-season Brier error** without worsening calibration, not whether it resembles the AP Top 25.

## Actual source coverage and identity warning

The 2026 historical Kaggle file committed in the project:

`web/public/seasons/2026.json`

is from a pinned source, **Kaggle day 118**, with `isComplete:false`. It is not a complete 2026 season. Therefore the current 2027 research prior is **provisional** and must not become the live predictor. The provisional historical lookup requires **exact case-insensitive school-name equality**, no nickname guess, no UConn = Connecticut automatic join and no ambiguous duplicate-name rows. This matching is *not equivalent to an independently authenticated NCAA/Kaggle ID crosswalk*. A genuinely unmatched team starts at 1500.

The historical **2016–2025** backtest, by contrast, uses the stable **Kaggle numerical team IDs across the previous and evaluated seasons** of one publicly pinned compact-results file:

`https://raw.githubusercontent.com/Andreachurchwell/march-madness-bracket-simulator/f8c521735ec41580711ce2d3e27dfd40f24e9e29/data/raw/MRegularSeasonCompactResults.csv`

The full raw source's SHA-256 is recorded in the historical research JSON. Incomplete holdout years are excluded. Its fixed 2026 snapshot is intentionally *not* presented as a complete season. Every historical evaluation season Y uses only previous season Y-1 for carryover.

**No AP poll votes, NCAA seeds, bookmaker spreads, postseason outcomes or future games are used to train the new Elo.**

## Elo 2.0 mathematical definition

### A. Historical carryover

Let \(R_{i,Y-1}\) be the team's rating at the end of the **previous** season in the source's historical Elo replay. Initial Elo for season Y is

\[
R_{i,Y}^{(0)} = 1500 + 0.55\, \operatorname{clip}(R_{i,Y-1}-1500,-160,160).
\]

The corresponding historical model's previous-season rating is never trained on the evaluated season's outcomes. A program with no strictly linked previous-season result starts at **1500**. Within the season, both winners' and losers' updates remain exactly zero-sum relative to these initial ratings; aggregate starting ratings no longer have to equal \(1500N\).

### B. Causal previous-opponent schedule adjustment

For a team with \(n_i\) earlier games, let \(r_{ij}^{\mathrm{pre}}\) be its opponent's Elo **before that earlier game's entire calendar date**, not the eventual end-of-season strength. The adjustment used **before today's games** is

\[
S_{i,t} = \operatorname{clip}\!\left(
    \frac{0.16\sum_{j=1}^{n_i}(r_{ij}^{\mathrm{pre}}-1500)}
    {n_i + 6},-35,35\right).
\]

This signal is bounded, shrinks small samples toward zero and is explicitly independent of current-day final scores.

### C. Outcome probability and team movements

For a scheduled contest (winner-oriented notation below), with real source-coded venue \(V\in\{-65,0,+65\}\),

\[
p_{\mathrm{winner}} =
\frac{1}{1+10^{-[(R_w+S_w)-(R_l+S_l)+V]/400}}.
\]

The same bounded-margin multiplier used by the existing Elo gives

\[
\Delta = 24 \times m(\text{winning margin}) \times (1-p_{\mathrm{winner}}),
\]

and \(R_w\gets R_w+\Delta\), \(R_l\gets R_l-\Delta\). Every game on the **same reported source date** first receives its prediction using *start-of-day* ratings and schedule statistics, and only then are the whole day's updates committed. This prevents a game with an unknown tipoff time from using another result on that same date. The schedule adjustment does not directly alter the public Elo rating or rewrite past games. The historical fixed hyperparameters are hypotheses, not values optimized on holdout scores.

## The historical test is real, not just a ranking difference

`research/forecast/elo_v2_historical.py` reads a SHA-pinned original **game-by-game regular-season results file**, groups by Kaggle season and evaluates 2016–2025 on identical fixtures for four independent replays:

| Model | Previous-season prior | Prior-opponent schedule |
|---|---|---|
| Production game-aware Elo control | No, starts 1500 | Game-time opponent Elo already in win probability |
| Carryover only | Yes, 0.55 regression, ±160 cap | No extra schedule term |
| Schedule only | No | Additional historical opponent average, 0.16, ±35 cap |
| Elo 2.0 combined | Yes | Yes |

The baseline and every challenger have the **same K factor, venue term, bounded score margin, game dates and winner/loser outcomes**. They differ only in the two isolated scientific hypotheses. The script reports:

- Whole-season Brier, accuracy and log loss from identically oriented source game predictions.
- Five-bin probability calibration (ECE) from **the same teams and actual outcomes**, with pooled sufficient statistics rather than misleading averages of season ECE.
- Early-season performance for game dates through Kaggle day 45.
- Season-by-season paired Brier gains and a **fixed-seed season-block bootstrap descriptive 95% interval** to reflect season dependence.
- Per-season counts, previous-season game counts and the number of team identities with genuine prior-year history.

A positive Brier gain means \(\mathrm{Brier}_{control}-\mathrm{Brier}_{challenger}>0\). A bootstrap interval containing zero is weak evidence; even an apparently favorable historical comparison does not imply the challenger was actually prospectively published. The holdout years were not used to fit or select the two fixed parameters. This benchmark **does not** use today's AP ranking to tune team strength.

**Source outage:** if the public pinned raw CSV cannot be fetched during a site build, the script writes a report marked `unavailable` and the dashboard withholds all historical numeric claims. It does not fail the main NCAA/ESPN Elo or invent historical evidence. Offline tests may pass a local `--raw-csv` and fail closed for invalid fixture records.

## 2027 operational data and the three-way AP study

`research/forecast/elo_v2_current.py` builds a **shadow** challenger from the same, deduplicated, source-accepted games as the live website. It verifies that `2027-games.json.retrievedAtUtc` and `2027.json.retrievedAtUtc` match before doing any work. Replays current-season games under the three hypotheses; publishes exact D-I source-ID cohort ranks for both current and shadow Elo. It exposes how many **exact-name** provisional 2026 priors matched, how many were missing, and explicitly blocks model promotion.

For each already **archived** AP poll edition, it also reconstructs the shadow model using only games through the **Sunday before the AP source week**, with team identities still sourced from the current verified 2027 ESPN-ID membership. It contrasts the **first-frozen** original Elo/AP Top 25 overlap and the *reconstructed* Elo2/AP overlap on a common AP edition. It flags that previously played game scores could have been backfilled after the original AP publication. This is not claimed to be frozen at the historic poll instant. Neither AP ranking nor its difference trains or promotes a model.

Two JSON artifacts are published after each successful site build:

- `web/public/research/elo-v2-historical.json` — pinned multi-year historical game evaluation.
- `web/public/current/elo-v2-research.json` — same-source 2027 shadow rankings, source/match coverage, AP three-way comparison.

The website **Model Lab → Elo Reimagined** has three accessible views: *Current Rankings*, *Historical Tests*, and *Elo 2.0 vs AP*. It uses responsive tables, explicit missing states, source-matched timestamps, and separate original/challenger labels without adding a new top-level navigation tab.

## Promotion criteria — deliberately not met automatically

The operating source-aware Elo and frozen probabilities remain unchanged. There is **no automatic promotion**, no override of an archived first-pick probability, and no retroactive regrading. Before revisiting promotion, require:

1. An independently maintained, verified **cross-year school identity** mapping to replace provisional exact-name 2026 lookups, and a completed valid prior-season dataset or transparent alternative source.
2. Multiple independently held-out historical seasons with favorable Brier/accuracy/calibration performance, including early-season evidence and a credible season-block interval.
3. **Prospective** paired first-published, time-stamped pregame probabilities for both models, with independently settled final results. Research replays do *not* satisfy that condition.
4. Manual release review after source coverage, drift monitoring, failure-mode and documentation review.

This is an important distinction: AP-poll agreement is an interesting ranking measure, but predicting college basketball outcomes is the real goal.

## Reproducibility

```powershell
$env:PYTHONPATH="research"
py -m unittest discover -s research/tests -p "test_elo_v2.py" -v
py -m unittest discover -s research/tests -v
py -m forecast.elo_v2_historical --out web/public/research/elo-v2-historical.json
py -m forecast.elo_v2_current --games web/public/current/2027-games.json --ratings web/public/current/2027.json --previous web/public/seasons/2026.json --ap web/public/research/ap-poll-history.json --historical web/public/research/elo-v2-historical.json --out web/public/current/elo-v2-research.json
cd web
npm install
npm run typecheck
npm run build
npm run test:e2e
```

If the local current source files are absent (they are generated during GitHub Pages deployment), run the existing `forecast.live` source build first. Offline historical benchmarking can be reproduced with `--raw-csv path/to/pinned-source.csv` and the published pinned SHA for source verification.

The CI test file `test_elo_v2.py` tests score-time causality, frozen same-day results, stable nonzero initial rating mass, no leakage on later results, previous-season-only priors, ID and name safeguards, same-game comparisons, source outages and current model safety. The browser suite tests all three dashboard views, cohort ranks and mismatched timestamps; the nightly workflow contract ensures the challenger does **not** run in the first-pick archive.
