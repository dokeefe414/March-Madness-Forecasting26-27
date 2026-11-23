# Visual language, interaction, and accessibility

March Forecast uses a custom **after-dark basketball research studio** design rather than a generic dashboard template. Its visual identity makes every metric feel exciting without passing generated artwork or decorative numbers off as real scores.

## Design tokens

| Color token | Hex | Purpose |
| --- | --- | --- |
| `--bg` | `#070e16` | Dark midnight background |
| `--panel` | `#0e1b26` | Layered content surfaces |
| `--line` | `#25414a` | Deliberately subdued borders |
| `--mint` | `#a6ffce` | Calls to action, winning model signal |
| `--blue` | `#8bd8ff` | Secondary model comparisons |
| `--amber` | `#ffc47b` | Opening Round/caution indicator |
| `--red` | `#ff8f83` | Errors and unfavorable changes |

Headlines use **Barlow Condensed**, while body/control labels use **DM Sans**. Large condensed numbers, linear court-style grids and subtle rings build a recognizable sporting identity. The banners are CSS backgrounds and typography, not photo imports or simulated athlete imagery.

## Information architecture

Main tabs: 2027 Pulse → Historical → Matchups → Bracket → Research → Archive → About.

- **2027 Pulse** is the default page, because recent-season activity is the most actionable experience. A source-date card sits adjacent to its statistical content.
- **Historical** has a rich hero and source-note treatment. This large hero does not repeat on every other tab, reducing unnecessary vertical scrolling.
- **Matchups** uses high-contrast probability bars and comparative records.
- **Bracket** emphasizes a region selector, verified seed slots and an interactive progression probability spotlight.
- **Research** compares models first, then shows calibration/reliability, uncertainty and detailed holdout-year data.
- **Archive** retains source-specific actual final scores for historical inspection.
- **About** explains the transparent modeling boundaries.

## Responsive behavior

- Desktop max-width shell: 1540 px; sticky navigation minimizes lost scroll context.
- ~1200 px: compact header controls; bracket pairing grid becomes two columns.
- ~990 px: research/live/contender two-column analysis surfaces collapse to one column; side spotlights cease to be sticky.
- ~880 px: horizontal sticky navigation instead of dense desktop links.
- ~600 px: two-column metric tiles, single-column bracket fixtures and scorecards, condensed mobile table, no large decorative banner watermarks.
- Tables with many columns scroll horizontally instead of clipping values or hiding source metadata.

## Accessibility

Semantic navigation, keyboard-operable buttons, visible focus outlines and native labels remain mandatory. Probability visuals have numeric text in addition to bars. The calibration SVG has labeled confidence/accuracy axes and tooltips to make points interpretable. Color is **not the sole carrier** of win probabilities or good/bad changes; values are printed. `prefers-reduced-motion` disables transitions and decorative movement.

Some SVG visuals and tables need continued manual audit with screen readers. Before a release, check 375 px/850 px/1440 px layouts, browser zoom at 200%, keyboard focus order, color contrast, pointer interactions and loading/error states.

## Data integrity as a design requirement

- Never display a fabricated "live" ranking from demo team names.
- Current source status must show **latest included game date** and **UTC retrieval time** separately.
- Research scores come from `web/public/research/benchmark.json`, not a hard-coded chart.
- Historical results, unknown 2027 selections and Monte Carlo outputs must have distinct labels.
- External failures produce useful unavailable states rather than placeholder predictions.
- The future 76-team field is shown as a *format capability*, not a known selection.

CSS lives in `web/app/globals.css`; the complete component list and design ownership are in the root README.

## v0.6 editorial additions and source status

New studio workspaces: `SelectionLab.tsx` has an amber 76-slot motif, per-conference power cards, restrained provisional seed tiers, and a visible **source-coverage gate**. `ForecastTracker.tsx` has an ink-blue pregame receipt concept with locked timestamps, scored-result cards and separate unsettled status. `TeamTrend.tsx` is a focusable SVG trajectory of true sequential Elo updates, not a generic stock chart. `LiveSeason.tsx` adds three visibly separate evidence categories — NCAA team/conference source, independent 2027 Division I subdivision membership, and actual box-score possessions — with an honest empty state per source.

Responsive breakpoints progressively collapse from multi-column cards to one-column sheets under 990/730/500px. A Playwright test on real Chromium at **390px** detected an overflow from a non-wrapping "Immutable Forecast Archive" pill; fixed by allowing section headings and badges to wrap at 650px while preserving text legibility. The test remains in CI, rather than simply setting `overflow-x:hidden` to conceal the problem.

For sourced study, the chart and number labels must be independently readable without color. Keyboard focusable SVG points support Enter/Space and `title` values; a full screen-reader and 200%-zoom audit remains a manual review item.

Visual quality CI: [browser-quality.md](browser-quality.md).


## v0.8 Game Center and forward scorecard UX

The default homepage is now **Find a Game**, rather than a nine-tab research-only entrance. A hero conveys live-forward accuracy honestly (an em dash if not yet measured), then a searchable, date-filtered fixture list focuses a full-width actual game detail. Odds are displayed two-sided with accessible text and a color-independent probability bar. Explanations distinguish four separate descriptive factors from the true selected model's probability formula. A date, exact opponent, source score and W/L are shown for every related result; shared opponent outcomes and historical meetings cannot be silently fabricated.

CSS components are in `web/app/globals.css`: `.gc-*` for game/fixture/related evidence, `.fp-*` for forward accuracy/real misses and calibration, and `.selection-lens` for tournament hypothetical comparisons. The navy-to-green editorial color scheme uses cool-blue against mint for two-sided odds; research comparison panels have a distinct lower-contrast treatment. At <=840px columns stack, with further mobile adjustments at <=600/440px. Keyboard-operable fixture buttons and input labels retain accessible text; reduced-motion preference disables transitions.

When a listed source start time has passed, the game disappears from the default **upcoming** list; the optional user-controlled toggle displays the frozen captured probability with a visible non-live warning. The browser tests use mock source data only in the test runtime; do not add demo fixtures to production JSON.


## v0.9 easy access and real-game reports

The navigation adds a directly accessible **Model Lab** beside **Find a Game** and **Accuracy & Picks**. Real game details have a `?view=games&game=<ESPN ID>` shareable link. The existing 2027 team pulse has a one-tap `View upcoming games` action that passes the verified team ID as `?team=<id>`. A tap on a match scrolls to its report on mobile; long team/fixture lists remain filterable without extensive scrolling. `?view=models` opens the lab directly.

The redesigned individual game panel provides team Elo history curves, source-matched opponent-quality explanation, research-only model alternatives, and a separately labelled evidence/audit card. A real archived game can show **an original before-tipoff probability trajectory**, captured times, and later source-confirmed final score with correctness/Brier. No archival data = explicit unavailability, never a fake percentage.

Visual classes `.ml-*` cover the model showdown with paired-score Brier bars and cautious confidence bounds; `.ga-*` covers actual frozen game captures and postgame receipts; `.gc-recent-settled` brings finished results into the main view; `.gc-archive-health` shows the status of the independent archiver. CSS includes responsive layouts at 1130/930/830/700/620px and reduced-motion preferences. The new Playwright test fixtures are generated **only inside browser tests**, not committed as real sports data.

[Full model comparison trust contract](v09-model-validation.md).


## v2.2 / Forecast Intelligence cockpit (current design)

Five main navigation destinations remain intact. The Model Lab hosts one new
responsive Forecast Intelligence cockpit rather than adding more pages or tabs.

**Visual:** dark forest/navy layered surfaces, transparent court grid,
mint/cyan source evidence colors, high-contrast condensed numbers, bounded
glowing verified-score orb, and small restrained 01–04 data-source stages.
CSS is scoped under `.fi` in `web/app/globals.css` so old navigation,
historical tables, matchup and mobile layouts remain intact.

**Information hierarchy:** 1) genuinely verified forward picks and latest
source-game date; 2) historical/source-box/adaptive/forward coverage counters;
3) a three-choice interactive experiment workbench and identical-cohort Brier
comparison; 4) source-settled original-pick calibration; 5) existing detailed
Model Lab and historical tournament evidence. Negative Brier gains must not
be styled as successful model promotions, and all unverified states display
pending/missing text. Pair with [v2.2 scientific contract](v22-forecast-intelligence.md).

**UI controls:** native buttons with `aria-pressed` for the workbench; metrics
are text in addition to color-coded bars; chart rows preserve count and
percentage labels; `aria-live` only for the workbench, not the whole page;
visible `:focus-visible` outlines; reduced-motion safe; mobile grid at
1100/730/490px breakpoints. Source retrieval mismatches withhold invalid
research comparisons. Tests continue to run at the exact GitHub Pages project
prefix, and browser navigation remains tied to the original five main tabs.


## v2.6 AP Top 25 vs Elo lab

The five primary navigation destinations do not change. Under
**Model Lab** after Forecast Intelligence, a scoped `.ap-lab`
comparison visually separates poll *opinion* from game *prediction*:
mint/blue historical-overlap bars, large condensed numeric evidence,
one controlled week picker, a 25-school AP/Elo rank table, disagreement
filter, week-over-week timeline and model Top-25 outsiders. The two data
sources are labeled, source cutoff dates are shown, unverified poll
identities display dashes, and partial source coverage does not appear
as a complete comparison. The UI includes keyboard-visible focus,
explicit `aria-label` for the panel, row counts and mobile layouts at
1100/680/420 px. AP agreement bars are not styled as successful
probabilistic prediction-validation claims. Scientific definitions:
[AP comparison contract](ap-poll-weekly.md).


## v2.7 Elo Reimagined / three-way evidence studio

The Elo 2.0 challenger is placed **inside existing Model Lab**, ahead of the AP-vs-original-Elo panel, rather than adding a navigation tab. The scoped `.ev2` design preserves the existing mint/blue midnight color language and uses condensed Barlow numerical evidence with conspicuous `ACTIVE PREDICTOR UNCHANGED` messaging. A three-way view switch isolates source-aligned *current ratings*, independently held-out *historical tests* (Brier, accuracy, ECE, bootstrap intervals) and AP vs original-vs-shadow Elo with explicit reconstructed-time caveats. Tables scroll **inside** the card on small devices; no page-wide horizontal overflow. Focus indicators, keyboard-operable button groups, proper table headers and honest missing-source states are required. See [the Elo2 methods guide](elo-v2-research.md).
