"""Elo 3.0: date-frozen power ratings and paired Elo 2.0 historical validation.

Power and probability use the SAME pregame strength components: previous-date
Elo, reliability, opponent strength, form and verified box statistics. No
future result, end-season opponent rating or guessed prior enters a prediction.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from itertools import groupby
from pathlib import Path

from .core import matchup_probability
from .game_aware_elo import GameAwareEloEngine, margin_multiplier
from .elo_v2 import Elo2Engine, SOS_WEIGHT, preseason_priors
from .elo_v2_historical import read_games, download, URL, HOLDOUT_YEARS

CENTER = 1500.
SOS_WEIGHT_V3 = .20
SOS_CAP_V3 = 24.
EARLY_GAMES = 8.
FORM_CAP = 20.
EFFICIENCY_CAP = 24.
FACTOR_CAP = 12.
HISTORICAL_WEIGHTS = (.65, .25, .10)
BOOTSTRAP_SEED = 62027


def clamp(x, limit):
    return max(-limit, min(limit, x))


def probability(gap, temperature=1.):
    return matchup_probability(CENTER + gap / temperature, CENTER)


def metrics(rows, key):
    """Paired first-team probabilities: 1 means lowest numeric team ID wins."""
    n = len(rows)
    if not n:
        return {"games": 0, "brier": None, "logLoss": None,
                "accuracy": None, "ece": None, "calibrationBins": []}
    brier = sum((r[key] - r["y"]) ** 2 for r in rows) / n
    logloss = -sum(r["y"] * math.log(max(1e-12, min(1 - 1e-12, r[key])))
                   + (1 - r["y"]) * math.log(max(1e-12, min(1 - 1e-12, 1 - r[key])))
                   for r in rows) / n
    accuracy = sum(.5 if r[key] == .5 else 1. if ((r[key] > .5) == bool(r["y"])) else 0. for r in rows) / n
    bins = [[0, 0., 0.] for _ in range(10)]
    for row in rows:
        i = min(9, int(row[key] * 10))
        bins[i][0] += 1
        bins[i][1] += row[key]
        bins[i][2] += row["y"]
    ece = sum(abs(pred - actual) for count, pred, actual in bins if count) / n
    return {"games": n, "brier": round(brier, 6),
            "logLoss": round(logloss, 6), "accuracy": round(accuracy, 6),
            "ece": round(ece, 6),
            "calibrationBins": [[c, round(p, 4), round(y, 4)] for c, p, y in bins]}


def _asof_temperature(history):
    """Calibrate only on games from dates already in the replay.

    Used both at historical game dates and for brand-new pretipoff Elo 3.0
    shadow snapshots. Never fit temperature on the forecast day's result.
    """
    if len(history) < 120 or len({r["day"] for r in history}) < 15:
        return 1.
    temperatures = (.8, .9, 1., 1.1, 1.2, 1.35)
    return min(temperatures, key=lambda t: (
        sum((probability(r["gap"], t) - r["y"]) ** 2 for r in history)
        / len(history) + .0003 * (t - 1.) ** 2, abs(t - 1.)))


def _four_factor_residual(box, other):
    f, opponent = box.get("factors"), other.get("factors")
    if f is None or opponent is None:
        return None
    keys = ("fga", "fgm", "fg3m", "fta", "tov", "orb", "drb")
    if any(type(f.get(k)) not in (int, float) or not math.isfinite(f[k]) or
           f[k] < 0 for k in keys):
        raise ValueError("Invalid verified Four Factors")
    if type(opponent.get("drb")) not in (int, float) or not math.isfinite(opponent["drb"]) or opponent["drb"] < 0:
        raise ValueError("Invalid opponent defensive rebounds")
    if f["fga"] <= 0 or f["fgm"] > f["fga"] or f["fg3m"] > f["fgm"]:
        raise ValueError("Impossible verified shooting totals")
    # Neutral references are fixed heuristic baselines, NOT sourced
    # opponent averages or trained future-season statistics.
    efg = (f["fgm"] + .5 * f["fg3m"]) / f["fga"]
    tov = f["tov"] / max(30., box["poss"])
    orb = f["orb"] / max(1., f["orb"] + opponent["drb"])
    ftr = f["fta"] / f["fga"]
    return clamp((efg - .50) - (tov - .18) + .20 * (orb - .30) + .10 * (ftr - .30), .5)


def _extended_box_residual(box, opponent):
    """A bounded predeclared exploratory residual from additional actual box totals.

    Every input is an observed count from one finished game. It is never
    estimated, cross-source-imputed, or exposed to the game's own prediction.
    These contributions are NOT part of the live model.
    """
    f = box.get("factors")
    x = box.get("extras")
    other = opponent.get("factors")
    if not isinstance(f, dict) or not isinstance(x, dict) or not isinstance(other, dict):
        return None
    for key, maximum in (("fg3a", 75.), ("ftm", 75.), ("ast", 65.),
                         ("stl", 40.), ("blk", 30.), ("pf", 65.)):
        v = x.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= maximum:
            raise ValueError("Invalid historical supplementary box totals")
    if (x["fg3a"] < f["fg3m"] or x["fg3a"] > f["fga"]
            or x["ftm"] > f["fta"] or x["ast"] > f["fgm"]+3):
        raise ValueError("Inconsistent historical supplementary box totals")
    assist = x["ast"] / max(1., f["fgm"])
    three = x["fg3a"] and (f["fg3m"] / x["fg3a"] - .34) or 0.
    free = f["fta"] and (x["ftm"] / f["fta"] - .73) or 0.
    steal = x["stl"] / box["poss"]
    block = x["blk"] / max(1., other["fga"])
    foul = x["pf"] / box["poss"]
    # Fixed, deliberately small coefficients. Validate out-of-time before
    # considering promotion; these features substantially overlap efficiency.
    return clamp(.15*(assist-.55) + .08*three + .07*free
                 + .20*(steal-.095) + .15*(block-.07)
                 - .10*(foul-.25), .3)


def replay(games, priors=None, paired_boxes=None, stats_variant="fourFactors"):
    """Date-frozen prediction; explicit independent box-stat ablation policies."""
    if stats_variant not in ("scoreOnly", "efficiency", "fourFactors", "extended"):
        raise ValueError("Unknown Elo 3 historical box-stat experiment")

    games = sorted(games, key=lambda g: (g.day_num, min(g.winner, g.loser),
                    max(g.winner, g.loser), g.contest_id))
    if not games:
        return {"rows": [], "pairedBoxes": 0, "boxEligible": 0,
                "nextForecastTemperature":1., "finalHomeAdvantage":65.,
                "ratings": {}, "powerRatings": {}, "ratingComponents": {},
                "gamesPlayed": {}, "recentForm": {}, "boxGames": {}, "fourFactorGames": {}}
    if len({g.season for g in games}) != 1:
        raise ValueError("Multiple seasons in Elo 3 replay")
    ids = [g.contest_id for g in games]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("Duplicate or missing contest ID")
    initial = dict(priors or {})
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 1000 <= v <= 2000
           for v in initial.values()):
        raise ValueError("Invalid cross-season prior")
    ratings = defaultdict(lambda: CENTER, initial)
    form = defaultdict(float)
    counts = defaultdict(int)
    opponent_sums = defaultdict(float)
    off, defence, poss = defaultdict(float), defaultdict(float), defaultdict(float)
    boxcount = defaultdict(int)
    factor_sum, factor_count = defaultdict(float), defaultdict(int)
    extended_sum, extended_count = defaultdict(float), defaultdict(int)
    home, history, rows, matched, eligible = 65., [], [], 0, 0
    participants = set()

    def strength(team):
        n = counts[team]
        initial_rating = initial.get(team, CENTER)
        reliability = .65 + .35 * n / (n + EARLY_GAMES)
        base = initial_rating + reliability * (ratings[team] - initial_rating)
        sos = clamp(SOS_WEIGHT_V3 * opponent_sums[team] / (n + 8.), SOS_CAP_V3)
        recent = clamp(form[team] * n / (n + 12.), FORM_CAP)
        efficiency = 0.
        factors = 0.
        if stats_variant != "scoreOnly" and boxcount[team] >= 3:
            # Possession-shrunk net efficiency against verified paired box data.
            efficiency = clamp(2. * (off[team] - defence[team]) /
                               (poss[team] + 500.) * 100., EFFICIENCY_CAP)
        if stats_variant in ("fourFactors", "extended") and factor_count[team] >= 3:
            factors = clamp(25. * factor_sum[team] /
                            (factor_count[team] + 8.), FACTOR_CAP)
        extended = 0.
        if stats_variant == "extended" and extended_count[team] >= 3:
            extended = clamp(75. * extended_sum[team] /
                             (extended_count[team] + 8.), 8.)
        return {"extended": round(extended, 4),
                "rawElo": round(ratings[team], 4),
                "prior": round(initial_rating, 4),
                "reliability": round(reliability, 5),
                "reliableElo": round(base, 4),
                "sos": round(sos, 4), "form": round(recent, 4),
                "efficiency": round(efficiency, 4),
                "fourFactors": round(factors, 4),
                "power": round(base + sos + recent + efficiency + factors + extended, 4),
                "games": n, "boxGames": boxcount[team],
                "fourFactorGames": factor_count[team],
                "extendedGames": extended_count[team]}

    for day, group in groupby(games, key=lambda g: g.day_num):
        batch = list(group)
        if any(g.day_num < 0 or g.winner == g.loser or
               g.winner_location not in ("H", "A", "N") or
               g.winner_score <= g.loser_score or g.loser_score <= 0
               for g in batch):
            raise ValueError("Invalid scored game")
        # Temperature only fitted on previous dates. This is NOT a prospective
        # out-of-sample hyperparameter search.
        temp = _asof_temperature(history)
        frozen = []
        for g in batch:
            w, l = g.winner, g.loser
            participants.update((w, l))
            before_w, before_l = ratings[w], ratings[l]
            wpower, lpower = strength(w)["power"], strength(l)["power"]
            venue = {"H": home, "A": -home, "N": 0.}[g.winner_location]
            gap = wpower - lpower + venue
            raw = probability(gap)
            p = probability(gap, temp)
            y = 1. if w < l else 0.
            rows.append({"contestId": g.contest_id, "day": day, "y": y,
                         "elo3": p if y else 1 - p,
                         "uncalibrated": raw if y else 1 - raw,
                         "temperature": temp,
                         "boxUsed": stats_variant != "scoreOnly" and boxcount[w] >= 3 and boxcount[l] >= 3,
                         "fourFactorsUsed": stats_variant in ("fourFactors","extended") and
                         factor_count[w] >= 3 and factor_count[l] >= 3,
                         "extendedUsed": stats_variant == "extended" and
                         extended_count[w] >= 3 and extended_count[l] >= 3})
            k = 24. * margin_multiplier(g.winner_score - g.loser_score) / (
                1. + max(0., before_w - before_l) / 1800.)
            k *= .65 + .35 * min(counts[w], counts[l]) / (min(counts[w], counts[l]) + 6.)
            frozen.append((g, gap, raw, k * (1 - raw), before_w, before_l))
            if boxcount[w] >= 3 and boxcount[l] >= 3:
                eligible += 1

        # Freeze ALL within-date deltas and opponent ratings before any result
        # is incorporated. Prevent multiple same-day games from leaking order.
        for g, gap, raw, delta, before_w, before_l in frozen:
            w, l = g.winner, g.loser
            ratings[w] += delta
            ratings[l] -= delta
            form[w] = .8 * form[w] + .2 * delta
            form[l] = .8 * form[l] - .2 * delta
            counts[w] += 1
            counts[l] += 1
            opponent_sums[w] += before_l - CENTER
            opponent_sums[l] += before_w - CENTER
            if g.winner_location != "N":
                home_won = g.winner_location == "H"
                expected_home = raw if home_won else 1 - raw
                home = max(15., min(110., home + 1.5 * (
                    (1. if home_won else 0.) - expected_home)))
            box = (paired_boxes or {}).get(g.contest_id)
            if box is not None:
                if (box.get("winnerId") != w or box.get("loserId") != l or
                    box.get("dayNum") != day):
                    raise ValueError("Paired-box identity mismatch")
                for team, side in ((w, "winner"), (l, "loser")):
                    b = box[side]
                    if any(type(b.get(k)) not in (float, int) or not math.isfinite(b[k]) or
                           not (30 <= b[k] <= 180 if k == "poss" else 25 <= b[k] <= 250)
                           for k in ("poss", "off", "def")):
                        raise ValueError("Invalid source paired-box metric")
                    off[team] += b["off"] * b["poss"] / 100.
                    defence[team] += b["def"] * b["poss"] / 100.
                    poss[team] += b["poss"]
                    boxcount[team] += 1
                    opponent = box["loser" if side == "winner" else "winner"]
                    residual = _four_factor_residual(b, opponent)
                    if residual is not None:
                        factor_sum[team] += residual
                        factor_count[team] += 1
                    if stats_variant == "extended":
                        extra = _extended_box_residual(b, opponent)
                        if extra is not None:
                            extended_sum[team] += extra
                            extended_count[team] += 1
                matched += 1
        for g, gap, raw, delta, before_w, before_l in frozen:
            y = 1. if g.winner < g.loser else 0.
            history.append({"day": day, "gap": gap if y else -gap, "y": y})

    components = {team: strength(team) for team in sorted(participants)}
    return {"rows": rows, "pairedBoxes": matched, "boxEligible": eligible,
            "finalHomeAdvantage": round(home, 3),
            "nextForecastTemperature": _asof_temperature(history),
            "ratings": {t: ratings[t] for t in participants},
            "powerRatings": {t: v["power"] for t, v in components.items()},
            "ratingComponents": components, "gamesPlayed": dict(counts),
            "recentForm": dict(form), "boxGames": dict(boxcount),
            "fourFactorGames": dict(factor_count),
            "extendedGames": dict(extended_count)}


def historical_priors(grouped, year, current_ids, lag_count=3):
    """Only same stable historical Kaggle IDs; never join live NCAA names."""
    if lag_count not in (1, 3):
        raise ValueError("Unsupported historical lookback")
    years = []
    for lag, weight in enumerate(HISTORICAL_WEIGHTS[:lag_count], 1):
        past = grouped.get(year - lag, [])
        if not past or max(g.day_num for g in past) < 132:
            continue
        fitted = GameAwareEloEngine().fit(past, {})
        years.append((weight, {i: state.rating for i, state in fitted.states.items()}))
    out = {}
    for team in current_ids:
        available = [(weight, ratings[team]) for weight, ratings in years if team in ratings]
        if not available:
            continue
        denominator = sum(weight for weight, _ in available)
        deviation = sum(weight * clamp(rating - CENTER, 160.)
                        for weight, rating in available) / denominator
        out[team] = CENTER + .55 * deviation
    return out


def _paired_cohort(elo2, elo3):
    receipts = {r["contestId"]: r for r in elo2}
    if len(receipts) != len(elo2) or len(elo3) != len(elo2):
        raise ValueError("Duplicate/missing Elo2/Elo3 historical fixtures")
    rows = []
    for row in elo3:
        original = receipts.get(row["contestId"])
        if original is None or original["dayNum"] != row["day"]:
            raise ValueError("Paired Elo2/Elo3 date/contest mismatch")
        won = original["winnerId"] < original["loserId"]
        if bool(row["y"]) != won:
            raise ValueError("Paired Elo2/Elo3 winner mismatch")
        rows.append({**row, "elo2": original["winnerProbability"] if won else
                     1 - original["winnerProbability"]})
    if len({x["contestId"] for x in rows}) != len(rows):
        raise ValueError("Duplicate Elo3 contest")
    return rows


def _gain_ci(years, variant):
    if len(years) < 5:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    for _ in range(600):
        cohort = [years[rng.randrange(len(years))] for _ in years]
        total = sum(x["games"] for x in cohort)
        draws.append(sum(x["gains"][variant] * x["games"] for x in cohort) / total)
    draws.sort()
    return [round(draws[int(.025 * (len(draws) - 1))], 6),
            round(draws[int(.975 * (len(draws) - 1))], 6)]


def evaluate(grouped, years=HOLDOUT_YEARS):
    """Paired held-out seasons, identical 2027-excluded sources and prior policy."""
    reports, all_rows = [], []
    for year in years:
        now = grouped.get(year, [])
        previous = grouped.get(year - 1, [])
        if not now or not previous or max(g.day_num for g in now) < 132 or max(g.day_num for g in previous) < 132:
            continue
        ids = {g.winner for g in now} | {g.loser for g in now}
        one = historical_priors(grouped, year, ids, 1)
        multi = historical_priors(grouped, year, ids, 3)
        elo2 = Elo2Engine(one, SOS_WEIGHT).fit(now, {})
        v3 = replay(now, one)
        v3multi = replay(now, multi)
        cohort = _paired_cohort(elo2.game_receipts, v3["rows"])
        longer = _paired_cohort(elo2.game_receipts, v3multi["rows"])
        if [r["contestId"] for r in cohort] != [r["contestId"] for r in longer]:
            raise ValueError("Different Elo 3 multi-season comparison cohort")
        for a, b in zip(cohort, longer):
            a["elo3Multi"] = b["elo3"]
        early = [row for row in cohort if row["day"] <= 45]
        base, three, many = (metrics(cohort, k) for k in ("elo2", "elo3", "elo3Multi"))
        reports.append({"season": year, "priorSeasons": [year-3, year-2, year-1],
                        "games": len(cohort), "priorCoverage": len(one),
                        "multiYearPriorCoverage": len(multi),
                        "elo2": base, "elo3": three, "elo3Multi": many,
                        "earlySeason": {k: metrics(early, k) for k in ("elo2","elo3","elo3Multi")},
                        "gains": {"elo3": round(base["brier"] - three["brier"], 8),
                                  "elo3Multi": round(base["brier"] - many["brier"], 8)}})
        all_rows.extend(cohort)
    base, three, many = (metrics(all_rows, k) for k in ("elo2","elo3","elo3Multi"))
    early_all = [x for x in all_rows if x["day"] <= 45]
    return {"schemaVersion": 2, "type": "elo3-versus-elo2-season-holdout",
            "status": "ready" if len(reports) >= 5 else "insufficient-complete-seasons",
            "holdoutSeasons": [x["season"] for x in reports],
            "games": len(all_rows), "elo2": base, "elo3": three, "elo3Multi": many,
            "brierGain": round(base["brier"] - three["brier"], 6) if all_rows else None,
            "multiYearBrierGain": round(base["brier"] - many["brier"], 6) if all_rows else None,
            "earlySeason": {k: metrics(early_all, k) for k in ("elo2","elo3","elo3Multi")},
            "seasonBlockGain95": {k: _gain_ci(reports, k) for k in ("elo3","elo3Multi")},
            "positiveGainSeasons": {k: sum(1 for row in reports if row["gains"][k] > 0)
                                    for k in ("elo3","elo3Multi")},
            "bySeason": reports, "source": URL, "automaticPromotion": False,
            "historicalIDPolicy": "Stable source Kaggle team IDs, trailing 1 or 3 complete seasons, each strictly before the test year",
            "capabilities": {"verifiedFourFactors": "unavailable in pinned historical compact-results source",
                             "opponentStrength": True, "margin": True,
                             "sampleReliability": True, "recentForm": True,
                             "homeAdjustment": True, "previousDateCalibration": True,
                             "priorSeasonCarryover": True},
            "limitations": [
                "Box-score efficiency and Four Factors cannot be benchmarked from historical compact scores; those features are disabled, not imputed.",
                "The ten holdout years are fixed; model coefficients were not nested-tuned and retrospective gains are not prospective published picks.",
                "2027 names/hashes cannot be joined to historical Kaggle IDs without independent season-spanning identity evidence.",
                "Historical accuracy alone does not authorize replacing a published production forecasting model."]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-csv", type=Path)
    p.add_argument("--out", type=Path, default=Path("research/outputs/elo3-historical.json"))
    args = p.parse_args()
    try:
        grouped, digest = read_games(args.raw_csv.read_bytes() if args.raw_csv else download())
        report = evaluate(grouped)
        report["sourceSha256"] = digest
    except (OSError, TimeoutError, ValueError, KeyError) as exc:
        if args.raw_csv:
            raise
        report = {"schemaVersion": 2, "type": "elo3-versus-elo2-season-holdout",
                  "status": "unavailable", "games": 0,
                  "reason": f"Pinned source unavailable: {type(exc).__name__}: {str(exc)[:180]}",
                  "source": URL, "holdoutSeasons": [], "automaticPromotion": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "games", "brierGain", "multiYearBrierGain")}, indent=2))


if __name__ == "__main__":
    main()
