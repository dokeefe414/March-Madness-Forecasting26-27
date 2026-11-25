"""Date-frozen, verified paired-box offensive/defensive latent research.

Only source_game_boxes' two-sided NCAA contest-ID joins are accepted.
Each day's forecasts use PREVIOUS days' boxes; the same-day update is atomic.
Elo, latent offense/defense and convex ensemble are scored on identical
eligible games. Weights may use only earlier completed DATE blocks.
No published forecast or immutable archive is changed.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import matchup_probability
from .possession_research import source_game_boxes
from .efficiency import BOX_URL

EASTERN = ZoneInfo("America/New_York")
HOME_ELO = 65.
INITIAL_VARIANCE = 18.**2
PROCESS_VARIANCE = 1.5**2
OBSERVATION_VARIANCE = 24.**2
MIN_TEAM_GAMES = 3
MIN_WEIGHT_GAMES = 40
MIN_WEIGHT_DAYS = 6
WEIGHTS = (0., .1, .2, .3, .4)
SHRINK = 400.


class Skill:
    def __init__(self):
        self.off = 0.
        self.defence = 0.
        self.off_var = INITIAL_VARIANCE
        self.def_var = INITIAL_VARIANCE
        self.games = 0
        self.possessions = 0.

    def update(self, scored: float, allowed: float, poss: float, league: float) -> None:
        # A conservative independent offense/defense scalar Gaussian filter.
        # Previous-day posterior uncertainty governs the next update.
        self.off, self.off_var = _kalman(self.off, self.off_var, scored - league, poss)
        self.defence, self.def_var = _kalman(self.defence, self.def_var, allowed - league, poss)
        self.games += 1
        self.possessions += poss


def _kalman(mean: float, variance: float, observation: float, poss: float) -> tuple[float,float]:
    prior = variance + PROCESS_VARIANCE
    noise = OBSERVATION_VARIANCE * (70. / poss)
    gain = prior / (prior + noise)
    return mean + gain * (observation - mean), max(1., (1. - gain) * prior)


def _brier(rows: list[dict], field: str) -> float | None:
    return round(sum((r[field] - r["y"]) ** 2 for r in rows) / len(rows), 6) if rows else None


def _logloss(rows: list[dict], field: str) -> float | None:
    if not rows:
        return None
    return round(-sum(math.log(max(1e-12, r[field] if r["y"] else 1. - r[field])) for r in rows) / len(rows), 6)


def _candidate_weight(prior: list[dict]) -> float:
    if len(prior) < MIN_WEIGHT_GAMES or len({r["date"] for r in prior}) < MIN_WEIGHT_DAYS:
        return 0.
    base = _brier(prior, "elo")
    options = []
    for w in WEIGHTS:
        score = sum(((1-w)*r["elo"] + w*r["latent"] - r["y"])**2 for r in prior)/len(prior)
        # Complexity penalty discourages reacting to small random differences.
        options.append((score + .0005*(w/.4)**2, w))
    best = min(options)[1]
    improvement = base - sum(((1-best)*r["elo"] + best*r["latent"] - r["y"])**2 for r in prior)/len(prior)
    return best if improvement >= .002 else 0.


def evaluate(games: list[dict], ratings: dict, boxes: dict,
             now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Aware research timestamp required")
    cutoff = now.astimezone(EASTERN).date().isoformat()
    if ratings.get("mode") != "current" or ratings.get("season") != 2027:
        raise ValueError("Expected source-verified 2027 ratings")
    if ratings.get("regularSeasonGames") != len(games):
        raise ValueError("Scored-game source count mismatch")
    if ratings.get("retrievedAtUtc") != boxes.get("retrievedAtUtc"):
        raise ValueError("Score/box retrieval timestamps differ")
    if boxes.get("schemaVersion") != 1 or boxes.get("season") != 2027:
        raise ValueError("Unexpected paired-box schema or season")
    if boxes.get("sourceUrl") != BOX_URL:
        raise ValueError("Unknown team-box source")
    if boxes.get("acceptedScoreGames") != len(games):
        raise ValueError("Paired-box score manifest count mismatch")
    ids = {str(g["id"]): g for g in games}
    if len(ids) != len(games):
        raise ValueError("Duplicate scored contest ID")
    paired = {}
    for row in boxes.get("games", []):
        g = ids.get(str(row.get("id")))
        if g is None or str(row["id"]) in paired or any(row[k] != g[k] for k in ("date","home","away")):
            raise ValueError("Box event identity/date mismatch")
        for side in ("homeBox", "awayBox"):
            b = row[side]
            for key,lo,hi in (("off",25,250),("def",25,250),("poss",30,180)):
                v = b.get(key)
                if type(v) not in (float,int) or not math.isfinite(v) or not lo <= v <= hi:
                    raise ValueError("Invalid paired possession metric")
        paired[str(row["id"])] = row
    grouped = defaultdict(list)
    for g in games:
        if g["date"] >= cutoff:
            continue
        if g["date"] > ratings.get("lastGameDate", ""):
            raise ValueError("Future score beyond rating source")
        grouped[g["date"]].append(g)
    elo = defaultdict(lambda:1500.)
    skills = defaultdict(Skill)
    history = []
    scored = []
    withheld = 0
    weights = []
    for day in sorted(grouped):
        batch = sorted(grouped[day],key=lambda g:str(g["id"]))
        # Both components and blend weight are frozen before this day's games.
        weight = _candidate_weight(history)
        eligible = []
        for g in batch:
            h,a = g["home"],g["away"]
            p_elo = matchup_probability(elo[h],elo[a],HOME_ELO)
            box = paired.get(str(g["id"]))
            if box is None or min(skills[h].games,skills[a].games) < MIN_TEAM_GAMES:
                withheld += 1
                continue
            # Opponent-adjusted latent scoring margin from independent
            # attack and defensive strengths, not end-of-season features.
            net = (skills[h].off - skills[a].defence -
                   skills[a].off + skills[h].defence)
            # Shrink small-sample latent signals and high posterior uncertainty.
            evidence = min(skills[h].possessions,skills[a].possessions)
            reliability = evidence/(evidence+SHRINK)
            uncertainty = sum((skills[t].off_var+skills[t].def_var for t in (h,a)))
            reliability *= 1/(1+uncertainty/3000.)
            p_latent = matchup_probability(1500.+18.*net*reliability,1500.,HOME_ELO)
            y = int(g["homeScore"]>g["awayScore"])
            eligible.append({"date":day,"id":str(g["id"]),"y":y,
                             "elo":p_elo,"latent":p_latent,
                             "ensemble":(1-weight)*p_elo+weight*p_latent,
                             "weight":weight})
        # Strict date boundary: no same-day outcomes or boxes before scoring.
        scored.extend(eligible)
        history.extend(eligible)
        weights.append({"date":day,"weight":weight,"eligibleGames":len(eligible),
                        "priorEligibleGames":len(history)-len(eligible)})
        for g in batch:
            h,a = g["home"],g["away"]
            y = int(g["homeScore"]>g["awayScore"])
            p = matchup_probability(elo[h],elo[a],HOME_ELO)
            change = 24*(y-p)
            elo[h] += change
            elo[a] -= change
            box = paired.get(str(g["id"]))
            if box is not None:
                hb,ab = box["homeBox"],box["awayBox"]
                # League 100 per 100 possessions is a fixed research prior,
                # NOT a future-season average estimated from test outcomes.
                skills[h].update(hb["off"],hb["def"],hb["poss"],100.)
                skills[a].update(ab["off"],ab["def"],ab["poss"],100.)
    return {
        "schemaVersion":1,"mode":"retrospective-date-frozen-research",
        "season":2027,"sourceRetrievedAtUtc":ratings["retrievedAtUtc"],
        "asOfDateExclusive":cutoff,"pairedSourceGames":len(paired),
        "scoredSourceGames":len(games),"eligibleComparedGames":len(scored),
        "withheldGames":withheld,"evaluatedDates":len({r["date"] for r in scored}),
        "baseline":{"brier":_brier(scored,"elo"),"logLoss":_logloss(scored,"elo")},
        "latent":{"brier":_brier(scored,"latent"),"logLoss":_logloss(scored,"latent")},
        "prequentialEnsemble":{"brier":_brier(scored,"ensemble"),
                               "logLoss":_logloss(scored,"ensemble")},
        "weightsByDate":weights,
        "modelParameters":{"minTeamBoxGames":MIN_TEAM_GAMES,
                           "observationVariance":OBSERVATION_VARIANCE,
                           "processVariance":PROCESS_VARIANCE,
                           "shrinkPossessions":SHRINK,
                           "weightCandidates":list(WEIGHTS)},
        "promotionEligible":False,
        "limitations":["Retrospective previous-date evaluation, not originally published pretipoff forecasts.",
                       "Uses source-confirmed NCAA schedule score/paired boxes, not independently verified ESPN settlements.",
                       "Fixed 100-point league prior and fixed Kalman/noise mapping are uncalibrated research assumptions.",
                       "The baseline is a matched simple Elo comparator, not necessarily identical to the active game-aware production Elo.",
                       "Same-date embargo, matched coverage, and past-only ensemble weights do not prove improved forward accuracy.",
                       "No official prediction, archive, or production model is modified."]
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games",type=Path,default=Path("web/public/current/2027-games.json"))
    p.add_argument("--ratings",type=Path,default=Path("web/public/current/2027.json"))
    p.add_argument("--boxes",type=Path,default=Path("web/public/current/2027-source-game-boxes.json"))
    p.add_argument("--out",type=Path,default=Path("web/public/current/efficiency-latent-research.json"))
    a=p.parse_args()
    games_artifact=json.loads(a.games.read_text(encoding="utf-8"))
    games=games_artifact["games"]
    ratings=json.loads(a.ratings.read_text(encoding="utf-8"))
    boxes=json.loads(a.boxes.read_text(encoding="utf-8"))
    report=evaluate(games,ratings,boxes)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("pairedSourceGames","eligibleComparedGames","withheldGames","promotionEligible")}))


if __name__=="__main__":
    main()
