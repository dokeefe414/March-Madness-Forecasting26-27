"""Elo 3.0 pretipoff shadow: source-frozen, strictly earlier-date game replay.

Only frozen prospective predictions may be scored as real model evidence.
This module never changes the active probability or previously saved picks.
No historical name-based 2026/2027 priors; optional boxes are the exact
source-matched 2027 NCAA-derived paired event data.
"""
from __future__ import annotations

import math
from datetime import date
from .elo_v2_current import _to_games
from .elo_v3 import replay, probability

MODEL_VERSION = "elo3-prospective-shadow-v1"


class Elo3Pregame:
    """Validate all as-of source identities once; replay prior dates only."""

    def __init__(self, ratings:dict, scored:dict, boxes:dict):
        stamp = ratings.get("retrievedAtUtc")
        if (ratings.get("mode")!="current" or ratings.get("season")!=2027
                or scored.get("season")!=2027 or boxes.get("season")!=2027
                or not stamp or scored.get("retrievedAtUtc")!=stamp
                or boxes.get("retrievedAtUtc")!=stamp):
            raise ValueError("Elo 3.0 shadow source retrieval/season mismatch")
        records = scored.get("games")
        if not isinstance(records,list) or len(records)!=ratings.get("regularSeasonGames"):
            raise ValueError("Elo 3.0 shadow scored-game coverage mismatch")
        if not isinstance(ratings.get("teams"),list):
            raise ValueError("Elo 3.0 shadow requires source-backed team identities")
        source = {row.get("name"):row.get("teamId") for row in ratings["teams"]}
        if len(source)!=len(ratings["teams"]) or len(set(source.values()))!=len(source):
            raise ValueError("Ambiguous Elo 3.0 source team IDs")
        fixtures,names = _to_games(records)
        if len({g.contest_id for g in fixtures})!=len(fixtures):
            raise ValueError("Duplicate Elo 3.0 source game contest ID")
        if (set(names.values())!=set(source) or
                (records and max(row["date"] for row in records)!=ratings.get("lastGameDate"))):
            raise ValueError("Elo 3.0 shadow games and source team/date coverage mismatch")
        known={game.contest_id:game for game in fixtures}
        original={str(row["id"]):row for row in records}
        pairs={}
        listed = boxes.get("games")
        if not isinstance(listed,list):
            raise ValueError("Invalid Elo 3.0 source box manifest")
        for box in listed:
            gid=str(box.get("id",""))
            g=known.get(gid)
            if not g or gid in pairs:
                raise ValueError("Duplicate or unmatched Elo 3.0 paired box")
            source_game=original[gid]
            if (box.get("date")!=source_game["date"] or
                    box.get("home")!=source_game["home"] or
                    box.get("away")!=source_game["away"]):
                raise ValueError("Elo 3.0 source paired-box matchup/date mismatch")
            if names[g.winner] not in (box["home"],box["away"]) or names[g.loser] not in (
                    box["home"],box["away"]):
                raise ValueError("Elo 3.0 paired-box team mismatch")
            home_won=names[g.winner]==box["home"]
            pairs[gid]={
                "winnerId":g.winner,"loserId":g.loser,"dayNum":g.day_num,
                "winner":box["homeBox"] if home_won else box["awayBox"],
                "loser":box["awayBox"] if home_won else box["homeBox"],
            }
        self.stamp=stamp
        self.fixture_count=len(fixtures)
        self.names=names
        self.fixtures=fixtures
        self.pairs=pairs
        self.records=records
        self.box_status=boxes.get("status","unknown")
        self._by_day={}

    def _asof(self, day:str)->dict:
        if day in self._by_day:
            return self._by_day[day]
        cutoff=date.fromisoformat(day)
        eligible_ids={str(row["id"]) for row in self.records
                      if date.fromisoformat(row["date"])<cutoff}
        earlier=[g for g in self.fixtures if g.contest_id in eligible_ids]
        # Strictly before the local scheduled *calendar date*, even if the
        # capture happened after another game ended on that same date.
        previous={gid:box for gid,box in self.pairs.items() if gid in eligible_ids}
        report=replay(earlier, paired_boxes=previous)
        model={
            "ratings":{self.names[i]:strength for i,strength in report["powerRatings"].items()},
            "homeAdvantage":report["finalHomeAdvantage"],
            "temperature":report["nextForecastTemperature"],
            "trainedThroughDate":max((row["date"] for row in self.records
                                      if str(row["id"]) in eligible_ids),default=None),
            "sourceGames":len(earlier),
            "pairedBoxGames":report["pairedBoxes"],
            "fourFactorTeamGames":sum(report["fourFactorGames"].values()),
        }
        if model["trainedThroughDate"] is not None and model["trainedThroughDate"]>=day:
            raise ValueError("Elo 3.0 prospective model used same-date games")
        self._by_day[day]=model
        return model

    def predict(self, home:str, away:str, day:str, neutral:bool)->tuple[float,dict]:
        if home==away:
            raise ValueError("Elo 3.0 cannot predict self matchups")
        if home not in set(self.names.values()) or away not in set(self.names.values()):
            raise ValueError("Elo 3.0 prospective team identity is not source-confirmed")
        model=self._asof(day)
        home_rating=model["ratings"].get(home,1500.)
        away_rating=model["ratings"].get(away,1500.)
        venue=0. if neutral else model["homeAdvantage"]
        prob=probability(home_rating-away_rating+venue,model["temperature"])
        if not math.isfinite(prob) or not 0<prob<1:
            raise ValueError("Elo 3.0 prospective probability invalid")
        return prob,{
            "modelVersion":MODEL_VERSION,
            "ratingRetrievedAtUtc":self.stamp,
            "boxRetrievedAtUtc":self.stamp,
            "trainedThroughDate":model["trainedThroughDate"],
            "ratingCutoffExclusive":day,
            "sourceGames":model["sourceGames"],
            "pairedBoxGames":model["pairedBoxGames"],
            "fourFactorTeamGames":model["fourFactorTeamGames"],
            "temperature":model["temperature"],
            "homeAdvantage":model["homeAdvantage"],
            "boxStatus":self.box_status,
            "preseasonPriorPolicy":"neutral-2027-until-verified-crossyear-ID",
            "evaluationPolicy":"paired earliest frozen first-pick vs contemporaneous Elo",
        }
