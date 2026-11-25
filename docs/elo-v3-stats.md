## Elo 3.0 verified basketball-stat extension

Elo 3.0 now incorporates all **available validated** source box dimensions,
not an invented all-stat claim. For teams with at least three earlier paired
boxes, it adds a bounded net-efficiency signal (offensive minus defensive
rating), adjusts for prior opponent Elo, and optionally incorporates the
source-verified Four Factors: effective FG%, turnover rate, offensive
rebounding share and free-throw attempts per FGA. The Four Factors require
both sides of the same contest and at least three earlier complete samples
for each team. Both net efficiency and Four Factors are shrunken and capped
to reduce small-sample instability and overlapping evidence.

Unverified steals, blocks, injuries, roster continuity, travel, recruiting,
and other features are **not** imputed. No historical future information is
used to construct an earlier game's rating. Missing stats fall back to Elo.
Current school-name priors remain neutral until independently matched IDs
are available. This is not yet evidence of improved championship forecasting:
the model must beat baseline on matched, out-of-time outcomes.

The Teams tab's Elo 3.0 ranks are experimental; original Elo game history
and original forward prediction engine remain separately labeled.
